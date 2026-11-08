"""Roster-driven overtime. Feeds the EXISTING Overtime Request pipeline (approval, OT Amount formula, payroll)
instead of creating pay records directly. Everything is created as a Draft for a manager to review and submit."""
from datetime import timedelta

import frappe
from frappe.utils import getdate

from roster_and_weekend.roster_and_weekend import engine
from roster_and_weekend.roster_and_weekend.api import board_rows

SERIES = "OTSR-.YY.-"


def _make(emp, ref, ot_type, start, end, reason, out):
	if frappe.db.exists("Overtime Request", {"employee": emp, "roster_ref": ref, "docstatus": ["<", 2]}):
		out["skipped"] += 1
		return
	if ot_type == "General" and (end - start) > timedelta(hours=8):
		end = start + timedelta(hours=8)  # the Overtime Request rule: General cannot exceed 8h
	try:
		frappe.get_doc({"doctype": "Overtime Request", "naming_series": SERIES, "employee": emp, "request_date": start.date(),
			"from_date": start.date(), "to_date": end.date(), "from_time": start.time().strftime("%H:%M:%S"),
			"to_time": end.time().strftime("%H:%M:%S"), "ot_type": ot_type, "reason": reason, "roster_ref": ref,
			"salary_component": engine.settings().ot_salary_component}).insert(ignore_permissions=True)
		out["created"] += 1
	except Exception as ex:
		out["errors"].append(f"{emp} {start.date()} {ot_type}: {ex}")


def _punches(employees, start, end):
	"""{(employee, date): (first_in, last_out)} on calendar days, for days without a rostered shift window."""
	logs = frappe.get_all("Employee Checkin", filters={"employee": ["in", list(employees) or [""]],
		"time": ["between", [f"{start} 00:00:00", f"{frappe.utils.add_days(end, 1)} 00:00:00"]]},
		fields=["employee", "time", "log_type"], order_by="time", limit_page_length=0)
	res = {}
	for l in logs:
		k = (l.employee, getdate(l.time))
		i, o = res.get(k, (None, None))
		if l.log_type == "IN" and not i:
			i = l.time
		elif l.log_type == "OUT" and i and l.time > i:
			o = l.time
		res[k] = (i, o)
	return res


def generate(from_date, to_date, shift_location=None):
	if not frappe.db.exists("DocType", "Overtime Request"):
		frappe.throw("Roster overtime needs the Overtime Request doctype (part of CentralHrms), which is not installed on this site.")
	start, end = getdate(from_date), getdate(to_date)
	out = {"created": 0, "skipped": 0, "errors": []}
	loc = {"shift_location": shift_location} if shift_location else {}

	# Emergency cover on a day off: the whole worked window is overtime
	cover = frappe.get_all("Roster Open Shift", filters={"status": "Filled", "overtime": 1, "date": ["between", [start, end]], **loc},
		fields=["filled_by", "date", "shift_type"])
	covered = {(c.filled_by, getdate(c.date)) for c in cover}
	punch = _punches({c.filled_by for c in cover}, start, end)
	for c in cover:
		i, o = punch.get((c.filled_by, getdate(c.date)), (None, None))
		if i and o:
			_make(c.filled_by, f"{c.filled_by}:{c.date}:EMG", "Emergency Cover", i, o, f"Emergency cover for {c.shift_type} (roster)", out)
		else:
			out["errors"].append(f"{c.filled_by} {c.date}: no complete check-in/out for emergency cover")

	# Time worked after the shift end (beyond the threshold)
	for r in board_rows(start, end, shift_location):
		if r["ot_minutes"] > 0 and (r["employee"], getdate(r["date"])) not in covered:
			_make(r["employee"], f"{r['employee']}:{r['date']}:GEN", "General", r["planned_out"], r["actual_out"], f"Time after {r['shift_type']} end (roster)", out)

	# Worked on a rostered day off (weekend)
	offs = frappe.get_all("Roster Entry", filters={"entry_type": "Off", "status": "Published", "date": ["between", [start, end]], **loc},
		fields=["employee", "date"], limit_page_length=0)
	punch = _punches({o.employee for o in offs}, start, end)
	for o in offs:
		i, out_t = punch.get((o.employee, getdate(o.date)), (None, None))
		if i and out_t and (out_t - i) >= timedelta(minutes=engine.settings().ot_threshold_minutes or 0):
			_make(o.employee, f"{o.employee}:{o.date}:WKD", "Weekend", i, out_t, "Worked on rostered day off", out)
	out["errors"] = out["errors"][:20]
	return out


def _factor(ot_type):
	s = engine.settings()
	return {"Weekend": s.weekend_ot_factor, "Emergency Cover": s.emergency_ot_factor}.get(ot_type) or 1


def on_submit(doc, method=None):
	"""Optional (Roster Settings > auto_additional_salary): create and submit the Additional Salary for approved OT."""
	s = engine.settings()
	if not s.auto_additional_salary or doc.additional_salary_ref:
		return
	component = doc.salary_component or s.ot_salary_component
	if not component:
		frappe.throw("Salary Component is required to create the Additional Salary")
	amount = round(doc.calculate_overtime_amount(doc.employee, doc.overtime_hours, getdate(doc.request_date)) * _factor(doc.ot_type), 2)
	a = frappe.get_doc({"doctype": "Additional Salary", "employee": doc.employee, "salary_component": component, "amount": amount,
		"payroll_date": doc.to_date, "company": frappe.db.get_value("Employee", doc.employee, "company"),
		"overwrite_salary_structure_amount": 0, "ref_doctype": "Overtime Request", "ref_docname": doc.name}).insert(ignore_permissions=True)
	a.submit()
	doc.db_set("additional_salary_ref", a.name)


def on_cancel(doc, method=None):
	if doc.additional_salary_ref and frappe.db.get_value("Additional Salary", doc.additional_salary_ref, "docstatus") == 1:
		frappe.get_doc("Additional Salary", doc.additional_salary_ref).cancel()
