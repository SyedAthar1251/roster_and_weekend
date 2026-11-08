from datetime import timedelta

import frappe
from frappe.utils import add_days, getdate, now_datetime, nowdate, to_timedelta

from roster_and_weekend.roster_and_weekend import engine, notify

MGR = ("Roster Manager", "HR Manager", "System Manager")
REPORT_MAX_DAYS = 31


def _mgr():
	frappe.only_for(MGR)


def _me():
	emp = frappe.db.get_value("Employee", {"user_id": frappe.session.user, "status": "Active"}, "name")
	if not emp:
		frappe.throw("No active Employee is linked to your user")
	return emp


def actuals(entries):
	"""{(employee, date): (first_in, last_out)} from Employee Checkin, matched to each entry's shift window."""
	if not entries:
		return {}
	wins = {e.name: engine.window(e) for e in entries}
	lo = min(w[0] for w in wins.values()) - timedelta(hours=3)
	hi = max(w[1] for w in wins.values()) + timedelta(hours=6)
	logs = frappe.get_all("Employee Checkin", filters={"employee": ["in", list({e.employee for e in entries})],
		"time": ["between", [lo, hi]]}, fields=["employee", "time", "log_type"], order_by="time")
	by_emp = {}
	for l in logs:
		by_emp.setdefault(l.employee, []).append(l)
	out = {}
	for e in entries:
		s, f = wins[e.name]
		mine = by_emp.get(e.employee, [])
		ins = [l.time for l in mine if l.log_type == "IN" and s - timedelta(hours=3) <= l.time <= f]
		first_in = min(ins) if ins else None
		outs = [l.time for l in mine if l.log_type == "OUT" and first_in and first_in < l.time <= f + timedelta(hours=6)]
		out[(e.employee, getdate(e.date))] = (first_in, max(outs) if outs else None)
	return out


def board_rows(start, end, location=None):
	s, now = engine.settings(), now_datetime()
	grace, thr = timedelta(minutes=s.grace_minutes or 0), timedelta(minutes=s.ot_threshold_minutes or 0)
	f = {"date": ["between", [start, end]], "entry_type": "Work", "status": "Published"}
	if location:
		f["shift_location"] = location
	ents = frappe.get_all("Roster Entry", filters=f, fields=["name", "employee", "employee_name", "date", "shift_type", "shift_location"],
		order_by="date, shift_type, employee_name", limit_page_length=5000)
	act, rows = actuals(ents), []
	for e in ents:
		st, en = engine.window(e)
		i, o = act.get((e.employee, getdate(e.date)), (None, None))
		late = int((i - st).total_seconds() // 60) if i and i > st + grace else 0
		if i:
			status = "Early Exit" if o and o < en - grace else ("Completed" if o else "Present")
			status = "Late" if late and status == "Present" else status
		else:
			status = "Upcoming" if now < st + grace else ("Missing" if now < en else "Absent")
		ot = int((o - en).total_seconds() // 60) if o and o > en + thr else 0
		rows.append(dict(employee=e.employee, employee_name=e.employee_name, date=e.date, shift_type=e.shift_type,
			shift_location=e.shift_location, planned_in=st, planned_out=en, actual_in=i, actual_out=o, status=status,
			late_minutes=late, ot_minutes=ot))
	return rows


@frappe.whitelist()
def next_roster_date(from_date=None, shift_location=None):
	"""Nearest date with a published work roster, on or after from_date.

	The live board renders a single day. A roster published for a future week
	would otherwise look empty when the page is opened on today's date.
	"""
	_mgr()
	d = from_date or nowdate()
	f = {"status": "Published", "entry_type": "Work", "date": [">=", getdate(d)]}
	if shift_location:
		f["shift_location"] = shift_location
	row = frappe.db.get_value("Roster Entry", f, "date", order_by="date asc")
	return str(getdate(row)) if row else None


@frappe.whitelist()
def get_live_board(shift_location=None, date=None):
	_mgr()
	d = date or nowdate()
	rows = board_rows(d, d, shift_location)
	summary = {}
	for r in rows:
		k = f"{r['shift_location'] or '-'} | {r['shift_type']}"
		x = summary.setdefault(k, dict(key=k, scheduled=0, present=0, late=0, missing=0, done=0))
		x["scheduled"] += 1
		x["present"] += r["status"] in ("Present", "Late")
		x["late"] += r["status"] == "Late"
		x["missing"] += r["status"] in ("Missing", "Absent")
		x["done"] += r["status"] in ("Completed", "Early Exit")
	return {"rows": rows, "summary": list(summary.values()), "open_shifts": frappe.db.count("Roster Open Shift", {"status": "Open"})}


@frappe.whitelist()
def get_roster_grid(from_date, to_date, shift_location=None):
	_mgr()
	# Cancelled entries are kept for audit but must never show on the roster
	f = {"date": ["between", [from_date, to_date]], "status": ["!=", "Cancelled"]}
	if shift_location:
		f["shift_location"] = shift_location
	rows = frappe.get_all("Roster Entry", filters=f,
		fields=["employee", "employee_name", "date", "entry_type", "shift_type", "shift_location", "status", "acknowledged"],
		limit_page_length=20000)
	return rows


# ---- Roster Report page ----
def _hhmm(td):
	if td is None:
		return ""
	secs = int(to_timedelta(td).total_seconds()) % 86400
	return f"{secs // 3600:02d}:{(secs % 3600) // 60:02d}"


def _shift_info():
	"""{shift_type: {start, end, hours}}; overnight shifts roll over midnight."""
	out = {}
	for s in frappe.get_all("Shift Type", fields=["name", "start_time", "end_time"], limit_page_length=0):
		hours = 0
		if s.start_time is not None and s.end_time is not None:
			diff = (to_timedelta(s.end_time) - to_timedelta(s.start_time)).total_seconds()
			if diff <= 0:
				diff += 86400
			hours = round(diff / 3600, 2)
		out[s.name] = {"start": _hhmm(s.start_time), "end": _hhmm(s.end_time), "hours": hours}
	return out


@frappe.whitelist()
def get_report_filters():
	"""Option lists for the Roster Report filter bar."""
	_mgr()
	return {
		"companies": frappe.get_all("Company", pluck="name", order_by="name"),
		"departments": frappe.get_all("Department", filters={"is_group": 0}, pluck="name", order_by="name"),
		"locations": frappe.get_all("Shift Location", pluck="name", order_by="name"),
		"shift_types": frappe.get_all("Shift Type", pluck="name", order_by="name"),
	}


@frappe.whitelist()
def get_report_data(from_date, to_date, shift_location=None, department=None, company=None, shift_type=None, status=None):
	"""Everything the Roster Report page needs in one call. Cancelled entries are always excluded.
	status: '' (Draft + Published), 'Draft' or 'Published'."""
	_mgr()
	start, end = getdate(from_date), getdate(to_date)
	if start > end:
		frappe.throw("From Date must be on or before To Date")
	if (end - start).days + 1 > REPORT_MAX_DAYS:
		frappe.throw(f"Please select at most {REPORT_MAX_DAYS} days")
	f = {"date": ["between", [start, end]], "status": ["in", ["Draft", "Published"]]}
	if status in ("Draft", "Published"):
		f["status"] = status
	if shift_location:
		f["shift_location"] = shift_location
	if shift_type:
		f["shift_type"] = shift_type
	if department or company:
		ef = {}
		if department:
			ef["department"] = department
		if company:
			ef["company"] = company
		f["employee"] = ["in", frappe.get_all("Employee", filters=ef, pluck="name", limit_page_length=0) or ["__none__"]]
	limit = 20000
	rows = frappe.get_all("Roster Entry", filters=f, order_by="employee_name, date", limit_page_length=limit,
		fields=["name", "employee", "employee_name", "date", "entry_type", "shift_type", "shift_location", "plan", "status", "acknowledged"])
	emps = list({r.employee for r in rows})
	meta = {}
	if emps:
		for e in frappe.get_all("Employee", filters={"name": ["in", emps]}, fields=["name", "department", "designation", "company"],
				limit_page_length=0):
			meta[e.name] = {"department": e.department, "designation": e.designation, "company": e.company}
	return {
		"from_date": str(start),
		"to_date": str(end),
		"rows": rows,
		"employees": meta,
		"shift_info": _shift_info(),
		"rules": frappe.get_all("Roster Site Rule", fields=["shift_location", "shift_type", "min_staff"], limit_page_length=500),
		"truncated": len(rows) >= limit,
	}


@frappe.whitelist()
def get_ot_summary(from_date, to_date, shift_location=None):
	_mgr()
	cap = (engine.settings().max_ot_hours_day or 0) * 60
	out = {}
	for r in board_rows(from_date, to_date, shift_location):
		if r["ot_minutes"]:
			x = out.setdefault(r["employee"], dict(employee=r["employee"], employee_name=r["employee_name"], ot_minutes=0, days=0, over_cap_days=0))
			x["ot_minutes"] += r["ot_minutes"]; x["days"] += 1; x["over_cap_days"] += r["ot_minutes"] > cap
	return sorted(out.values(), key=lambda x: -x["ot_minutes"])


@frappe.whitelist()
def create_overtime_requests(from_date, to_date, shift_location=None):
	"""Draft Overtime Requests from roster vs check-ins. Approval and payroll stay in the existing OT pipeline."""
	_mgr()
	from roster_and_weekend.roster_and_weekend import overtime
	return overtime.generate(from_date, to_date, shift_location)


@frappe.whitelist()
def get_queue():
	_mgr()
	return {
		"swaps": frappe.get_all("Roster Swap Request", filters={"status": "Pending Manager"}, fields=["name", "requester", "counterpart", "date", "requester_cell", "counterpart_cell", "checks", "reason"]),
		"open_shifts": frappe.get_all("Roster Open Shift", filters={"status": "Open"}, fields=["name", "date", "shift_type", "shift_location", "reason", "original_employee"], order_by="date"),
		"unacknowledged": frappe.db.count("Roster Entry", {"status": "Published", "acknowledged": 0, "date": [">=", nowdate()]}),
	}


# ---- employee side ----
@frappe.whitelist()
def my_employee():
	"""Employee linked to the current user, or None. Lets the page show a message instead of an error."""
	return frappe.db.get_value("Employee", {"user_id": frappe.session.user, "status": "Active"}, "name")


@frappe.whitelist()
def my_roster(from_date, to_date):
	return frappe.get_all("Roster Entry", filters={"employee": _me(), "status": "Published", "date": ["between", [from_date, to_date]]},
		fields=["name", "date", "entry_type", "shift_type", "shift_location", "acknowledged"], order_by="date")


@frappe.whitelist()
def acknowledge(from_date, to_date):
	for n in frappe.get_all("Roster Entry", filters={"employee": _me(), "status": "Published", "date": ["between", [from_date, to_date]]}, pluck="name"):
		frappe.db.set_value("Roster Entry", n, "acknowledged", 1)


def _entry(emp, d):
	return frappe.db.get_value("Roster Entry", {"employee": emp, "date": d, "status": "Published"},
		["name", "entry_type", "shift_type", "shift_location"], as_dict=True)


def _swap_checks(a, b, d):
	ea, eb = _entry(a, d), _entry(b, d)
	if not ea or not eb:
		frappe.throw("Both employees need a published roster entry on that date")
	if "Leave" in (ea.entry_type, eb.entry_type) or "Sick" in (ea.entry_type, eb.entry_type):
		frappe.throw("Cannot swap a leave or sick day")
	if (ea.entry_type, ea.shift_type) == (eb.entry_type, eb.shift_type):
		frappe.throw("Both have the same cell, nothing to swap")
	d = getdate(d)
	issues = []
	for emp, new in ((a, eb), (b, ea)):
		cells = engine.cells_for(emp, add_days(d, -8), add_days(d, 8), {d: (new.entry_type, new.shift_type)})
		issues += engine.rule_issues(emp, cells)
	return ea, eb, issues


@frappe.whitelist()
def request_swap(date, counterpart, reason=None):
	me = _me()
	ea, eb, issues = _swap_checks(me, counterpart, date)
	doc = frappe.get_doc({"doctype": "Roster Swap Request", "requester": me, "counterpart": counterpart, "date": date, "reason": reason,
		"requester_cell": f"{ea.entry_type} {ea.shift_type or ''}".strip(), "counterpart_cell": f"{eb.entry_type} {eb.shift_type or ''}".strip(),
		"checks": "\n".join(issues) or "All rules OK"}).insert(ignore_permissions=True)
	notify.to_employee(counterpart, "Swap request", f"{me} asked to swap with you on {date}. Open Roster Hub to respond.")
	return doc.name


@frappe.whitelist()
def respond_swap(name, accept):
	doc = frappe.get_doc("Roster Swap Request", name)
	if doc.counterpart != _me() or doc.status != "Pending Peer":
		frappe.throw("Not allowed")
	doc.status = "Pending Manager" if frappe.parse_json(accept) else "Rejected"
	doc.save(ignore_permissions=True)
	if doc.status == "Pending Manager":
		notify.to_managers("Swap awaiting approval", f"{doc.requester} and {doc.counterpart} on {doc.date}")
	else:
		notify.to_employee(doc.requester, "Swap declined", f"{doc.counterpart} declined the swap on {doc.date}.")


@frappe.whitelist()
def decide_swap(name, approve):
	_mgr()
	doc = frappe.get_doc("Roster Swap Request", name)
	if doc.status != "Pending Manager":
		frappe.throw("Request is not awaiting manager approval")
	if frappe.parse_json(approve):
		ea, eb, issues = _swap_checks(doc.requester, doc.counterpart, doc.date)
		if issues:
			frappe.throw("Rule violations:<br>" + "<br>".join(issues))
		for e, new in ((ea, eb), (eb, ea)):
			frappe.db.set_value("Roster Entry", e.name, {"entry_type": new.entry_type, "shift_type": new.shift_type,
				"shift_location": new.shift_location, "source": "Swap"})
		for emp in (doc.requester, doc.counterpart):
			engine.rebuild_assignments(emp, doc.date, doc.date)
		doc.status = "Approved"
	else:
		doc.status = "Rejected"
	doc.save(ignore_permissions=True)
	for emp in (doc.requester, doc.counterpart):
		notify.to_employee(emp, f"Swap {doc.status.lower()}", f"Swap on {doc.date} was {doc.status.lower()}.")


# ---- emergency ----
def _candidates(open_shift):
	d, sh, loc = getdate(open_shift.date), open_shift.shift_type, open_shift.shift_location
	out = []
	for e in frappe.get_all("Roster Entry", filters={"date": d, "entry_type": "Off", "status": "Published"}, fields=["employee", "employee_name", "shift_location"]):
		issues = engine.rule_issues(e.employee, engine.cells_for(e.employee, add_days(d, -8), add_days(d, 8), {d: ("Work", sh)}))
		out.append(dict(employee=e.employee, employee_name=e.employee_name, location=e.shift_location, same_location=e.shift_location == loc,
			ok=not issues, issues=issues, score=(2 if e.shift_location == loc else 0) + (1 if not issues else 0)))
	return sorted(out, key=lambda x: -x["score"])[:8]


@frappe.whitelist()
def call_out(employee, date, reason="Sick"):
	_mgr()
	e = _entry(employee, date)
	if not e or e.entry_type != "Work":
		frappe.throw("Employee has no work shift on that date")
	frappe.db.set_value("Roster Entry", e.name, {"entry_type": "Sick", "source": "Emergency"})
	engine.rebuild_assignments(employee, date, date)
	osh = frappe.get_doc({"doctype": "Roster Open Shift", "date": date, "shift_type": e.shift_type, "shift_location": e.shift_location,
		"reason": reason, "original_employee": employee}).insert(ignore_permissions=True)
	return {"open_shift": osh.name, "candidates": _candidates(osh)}


@frappe.whitelist()
def get_candidates(open_shift):
	_mgr()
	return _candidates(frappe.get_doc("Roster Open Shift", open_shift))


@frappe.whitelist()
def fill_open_shift(open_shift, employee):
	_mgr()
	osh = frappe.get_doc("Roster Open Shift", open_shift)
	if osh.status != "Open":
		frappe.throw("Shift is not open")
	e = _entry(employee, osh.date)
	if not e:
		frappe.throw("Employee has no published entry on that date")
	frappe.db.set_value("Roster Entry", e.name, {"entry_type": "Work", "shift_type": osh.shift_type, "shift_location": osh.shift_location, "source": "Emergency"})
	osh.update({"status": "Filled", "filled_by": employee, "overtime": 1 if e.entry_type == "Off" else 0}).save(ignore_permissions=True)
	engine.rebuild_assignments(employee, osh.date, osh.date)
	notify.to_employee(employee, "Emergency cover assigned", f"You are covering {osh.shift_type} on {osh.date}. Overtime rules apply.")


# ---- plan actions ----
@frappe.whitelist()
def get_plans():
	_mgr()
	return frappe.get_all("Roster Plan", fields=["name", "plan_title", "status", "from_date", "to_date", "generated_count"],
		order_by="modified desc", limit_page_length=50)


@frappe.whitelist()
def get_site_rules():
	_mgr()
	return frappe.get_all("Roster Site Rule", fields=["shift_location", "shift_type", "min_staff"], limit_page_length=500)


@frappe.whitelist()
def generate_plan(plan_name):
	_mgr()
	plan = frappe.get_doc("Roster Plan", plan_name)
	log, _skipped = engine.generate_entries(plan)  # generate_entries returns (log, skipped_conflicts)
	plan.db_set("last_log", "\n".join(log[:30])[:1000])
	return log[:30]


@frappe.whitelist()
def publish_plan(plan_name):
	_mgr()
	plan = frappe.get_doc("Roster Plan", plan_name)
	if not frappe.db.count("Roster Entry", {"plan": plan_name}):
		frappe.throw("Generate entries first")
	frappe.enqueue("roster_and_weekend.roster_and_weekend.engine.publish_plan", plan_name=plan_name, queue="long", timeout=3000)
	return "Publishing in background. Staff are notified when done."


@frappe.whitelist()
def cancel_plan(plan_name, from_date=None):
	"""from_date is accepted for old callers but ignored: engine.cancel_plan now cancels the whole plan."""
	_mgr()
	engine.cancel_plan(plan_name)
	return "Plan cancelled"