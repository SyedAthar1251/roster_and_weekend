"""Shift Time Exception: one Shift Type, different timing per assignment.

A Shift Assignment (or Shift Schedule Assignment) can point to a Shift Time Exception, which moves the Shift
Type's start and end by a number of minutes (start_offset / end_offset). The Shift Type itself never changes.

How attendance follows the exception (nothing in HRMS is modified):
  1. Employee Checkin.validate  : HRMS stamps shift_start / shift_end / shift_actual_start / shift_actual_end
                                  from the Shift Type. `apply_to_checkin` then moves those four stamps by the
                                  exception. Late entry, early exit and the check-in / check-out windows are all
                                  judged from these stamps, so they follow the exception automatically.
  2. Absent marking             : CustomShiftType._last_closed_shift_date (overrides/shift_type.py) uses the
                                  exception to know when the employee's shift has really ended.
  3. Attendance.before_insert   : `set_on_attendance` records which exception applied, for reports.

Which exception applies on a date: the active, submitted Shift Assignment of that employee and Shift Type covering
the date; if several cover it, the latest start_date wins, then the latest creation (same rule as the weekend resolver).
"""
from datetime import timedelta

import frappe
from frappe.utils import get_datetime, getdate


def get_time_exception(employee, shift_type, on_date):
	"""{"name", "start_offset", "end_offset"} for the exception that applies, else None."""
	if not (employee and shift_type and on_date):
		return None
	d = getdate(on_date)
	rows = frappe.db.sql(
		"""select custom_time_exception from `tabShift Assignment`
		where employee = %s and shift_type = %s and docstatus = 1 and status = 'Active'
		and start_date <= %s and (end_date is null or end_date >= %s)
		order by start_date desc, creation desc limit 1""",
		(employee, shift_type, d, d),
	)
	name = rows[0][0] if rows else None
	if not name:
		return None
	enabled, start_offset, end_offset = frappe.get_cached_value(
		"Shift Time Exception", name, ["enabled", "start_offset", "end_offset"]
	) or (0, 0, 0)
	if not enabled:
		return None
	return {"name": name, "start_offset": int(start_offset or 0), "end_offset": int(end_offset or 0)}


# ---------------------------------------------------------------- Employee Checkin
def apply_to_checkin(doc, method=None):
	"""Employee Checkin validate (runs after HRMS has stamped the shift). Idempotent: see the stamp token."""
	if not doc.get("shift") or not doc.get("shift_start"):
		doc.custom_time_exception = None
		doc.custom_exception_stamp = None
		return

	exc = get_time_exception(doc.employee, doc.shift, get_datetime(doc.shift_start).date())
	if not exc:
		doc.custom_time_exception = None
		doc.custom_exception_stamp = None
		return

	# If HRMS did not re-stamp on this save, shift_start is already the shifted value we wrote last time.
	if doc.get("custom_exception_stamp") == f"{exc['name']}|{get_datetime(doc.shift_start)}":
		return

	start_delta = timedelta(minutes=exc["start_offset"])
	end_delta = timedelta(minutes=exc["end_offset"])
	for field, delta in (
		("shift_start", start_delta),
		("shift_actual_start", start_delta),
		("shift_end", end_delta),
		("shift_actual_end", end_delta),
	):
		value = doc.get(field)
		if value:
			doc.set(field, get_datetime(value) + delta)

	doc.custom_time_exception = exc["name"]
	doc.custom_exception_stamp = f"{exc['name']}|{get_datetime(doc.shift_start)}"


# ---------------------------------------------------------------- Attendance
def set_on_attendance(doc, method=None):
	"""Attendance before_insert: remember which exception applied that day (for reports and audit)."""
	if doc.get("shift") and doc.get("attendance_date"):
		exc = get_time_exception(doc.employee, doc.shift, doc.attendance_date)
		doc.custom_time_exception = exc["name"] if exc else None


# ---------------------------------------------------------------- Shift Assignment
def validate_shift_assignment(doc, method=None):
	exc = doc.get("custom_time_exception")
	if exc and not frappe.db.get_value("Shift Time Exception", exc, "enabled"):
		frappe.throw(f"Shift Time Exception {exc} is disabled.")

	if doc.docstatus == 2 or not (doc.employee and doc.shift_type and doc.start_date):
		return

	# Same employee + same Shift Type on overlapping dates must agree on the exception, otherwise the timing of
	# an overlapping day would be ambiguous.
	rows = frappe.db.sql(
		"""select name, custom_time_exception from `tabShift Assignment`
		where employee = %s and shift_type = %s and docstatus < 2 and status = 'Active' and name != %s
		and start_date <= %s and (end_date is null or end_date >= %s)""",
		(doc.employee, doc.shift_type, doc.name or "", doc.end_date or "9999-12-31", doc.start_date),
		as_dict=True,
	)
	for r in rows:
		if (r.custom_time_exception or None) != (exc or None):
			frappe.throw(
				f"{r.name} already covers some of these dates for the same Shift Type with a different "
				f"Time Exception ({r.custom_time_exception or 'none'}). End or cancel it first, or use the same exception."
			)


# ---------------------------------------------------------------- Form helper
@frappe.whitelist()
def get_effective_timing(shift_type, time_exception=None):
	"""{"start": "09:30", "end": "18:30", "base_start": "09:00", "base_end": "18:00"} for the Shift Assignment form."""
	frappe.has_permission("Shift Type", "read", throw=True)
	start, end = frappe.get_cached_value("Shift Type", shift_type, ["start_time", "end_time"])
	start_offset = end_offset = 0
	if time_exception:
		start_offset, end_offset = frappe.get_cached_value(
			"Shift Time Exception", time_exception, ["start_offset", "end_offset"]
		) or (0, 0)

	def fmt(td, offset):
		minutes = int(td.total_seconds() // 60) + int(offset or 0)
		minutes %= 1440
		return f"{minutes // 60:02d}:{minutes % 60:02d}"

	return {
		"base_start": fmt(start, 0),
		"base_end": fmt(end, 0),
		"start": fmt(start, start_offset),
		"end": fmt(end, end_offset),
	}