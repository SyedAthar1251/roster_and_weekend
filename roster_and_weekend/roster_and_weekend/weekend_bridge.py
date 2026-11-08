import frappe
from frappe.utils import add_days, getdate, nowdate


def has_missing_record(employee, date):
	"""True if the employee has approved leave or an Absent / On Leave attendance on that date."""
	if frappe.db.exists("Leave Application", {"employee": employee, "docstatus": 1, "status": "Approved",
			"from_date": ["<=", date], "to_date": [">=", date]}):
		return True
	status = frappe.db.get_value("Attendance", {"employee": employee, "attendance_date": date, "docstatus": 1}, "status")
	return status in ("Absent", "On Leave")


def get_hr_emails():
	return frappe.get_all("Has Role", filters={"role": "HR Manager", "parenttype": "User"}, pluck="parent")


def notify_weekend_bridge_cases():
	"""Sunday alert: employees missing on both the previous Thursday and today.
	Fixed: helper functions were defined after the code that called them (UnboundLocalError on every run)."""
	today = getdate(nowdate())
	if today.weekday() != 6:
		return
	previous_thursday = add_days(today, -3)
	flagged = [f"{e.employee_name} ({e.name})" for e in frappe.get_all("Employee", filters={"status": "Active"}, fields=["name", "employee_name"])
		if has_missing_record(e.name, previous_thursday) and has_missing_record(e.name, today)]
	if flagged:
		frappe.sendmail(recipients=get_hr_emails(), subject="Weekend Bridge Attendance Alert",
			message="Weekend Bridge Alert<br><br>The following employees were absent/on leave on Thursday and Sunday:<br><br>" + "<br>".join(flagged))
