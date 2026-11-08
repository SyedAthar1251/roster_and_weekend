import frappe
from frappe.utils import add_days, getdate, nowdate

from roster_and_weekend.roster_and_weekend import engine, notify


def _open_shift(entry, reason):
	if getdate(entry.date) < getdate(nowdate()):
		return
	frappe.get_doc({"doctype": "Roster Open Shift", "date": entry.date, "shift_type": entry.shift_type,
		"shift_location": entry.shift_location, "reason": reason, "original_employee": entry.employee}).insert(ignore_permissions=True)


def leave_submitted(doc, method=None):
	rows = frappe.get_all("Roster Entry", filters={"employee": doc.employee, "entry_type": "Work",
		"date": ["between", [doc.from_date, doc.to_date]]}, fields=["name", "date", "employee", "shift_type", "shift_location", "status"])
	for r in rows:
		frappe.db.set_value("Roster Entry", r.name, {"entry_type": "Leave", "source": "Leave"})
		if r.status == "Published":
			_open_shift(r, "Leave")
	if rows:
		engine.rebuild_assignments(doc.employee, doc.from_date, doc.to_date)
		notify.to_managers("Leave on rostered days", f"{doc.employee_name} is on leave {doc.from_date} to {doc.to_date}. {len(rows)} shift(s) need cover.")


def leave_cancelled(doc, method=None):
	for r in frappe.get_all("Roster Entry", filters={"employee": doc.employee, "entry_type": "Leave", "source": "Leave",
			"date": ["between", [doc.from_date, doc.to_date]]}, fields=["name"]):
		frappe.db.set_value("Roster Entry", r.name, {"entry_type": "Work", "source": "Plan"})
	for o in frappe.get_all("Roster Open Shift", filters={"original_employee": doc.employee, "reason": "Leave", "status": "Open",
			"date": ["between", [doc.from_date, doc.to_date]]}, pluck="name"):
		frappe.db.set_value("Roster Open Shift", o, "status", "Cancelled")
	engine.rebuild_assignments(doc.employee, doc.from_date, doc.to_date)


def employee_updated(doc, method=None):
	"""Resignation or relieving date set: drop later roster entries and flag the headcount gap."""
	if not doc.relieving_date:
		return
	cut = getdate(doc.relieving_date)
	n = frappe.db.count("Roster Entry", {"employee": doc.name, "date": [">", cut]})
	if not n:
		return
	frappe.db.delete("Roster Entry", {"employee": doc.name, "date": [">", cut]})
	engine.rebuild_assignments(doc.name, add_days(cut, 1), add_days(cut, 365))
	notify.to_managers("Employee leaving", f"{doc.employee_name} leaves on {cut}. {n} roster day(s) removed, plan replacement.")
