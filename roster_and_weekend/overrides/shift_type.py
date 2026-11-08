# Copyright (c) 2026, NeoTec and contributors
# For license information, please see license.txt

from datetime import datetime, timedelta

from hrms.hr.doctype.shift_type.shift_type import ShiftType
from hrms.hr.doctype.attendance.attendance import mark_attendance
from hrms.utils import get_date_range
from hrms.utils.holiday_list import get_holiday_dates_between
import frappe
from frappe.utils import cint, get_datetime, get_time, getdate

from roster_and_weekend.roster_and_weekend.weekend_policy import get_weekend_dates, is_weekend, resolve_weekend_policy


class CustomShiftType(ShiftType):
	def should_mark_attendance(self, employee, attendance_date):
		if is_weekend(employee, attendance_date):
			self._note("checkin_on_weekend", employee, attendance_date)
			return False
		if not super().should_mark_attendance(employee, attendance_date):
			self._note("checkin_on_holiday", employee, attendance_date)
			return False
		return True

	# ---- skip-reason collection (used by the "Mark Attendance" report, see roster_and_weekend/attendance_diagnosis.py)
	# Only active when `_collect_report` is set, so the hourly scheduler run pays nothing for it.
	def _note(self, code, employee, date=None, extra=None):
		if not getattr(self, "_collect_report", False):
			return
		report = self.__dict__.setdefault("_skip_report", {})
		row = report.setdefault(code, {"count": 0, "employees": set(), "samples": [], "extra": []})
		row["count"] += 1
		row["employees"].add(employee)
		limit = 62 if code in ("weekend", "holiday") else 5
		if date is not None and len(row["samples"]) < limit:
			row["samples"].append(str(date))
		if extra is not None and len(row["extra"]) < 8:
			row["extra"].append(extra)

	def get_start_and_end_dates(self, employee):
		"""Date range in which Absent can be marked for this employee.

		Start = later of 'Process Attendance After' and joining date.
		End   = last day whose shift has fully ended before 'Last Sync of Check-in', capped by relieving date.

		Stock HRMS finds the end date by looking up this shift on the day before the last sync time; when that
		lookup fails it returns (None, None) and no Absent is ever marked. This version does not depend on it.
		"""
		if not self.process_attendance_after or not self.last_sync_of_checkin:
			return None, None

		date_of_joining, relieving_date, creation = frappe.db.get_value(
			"Employee", employee, ["date_of_joining", "relieving_date", "creation"]
		)
		if not date_of_joining:
			date_of_joining = creation.date()

		start_date = max(getdate(self.process_attendance_after), getdate(date_of_joining))
		end_date = self._last_closed_shift_date()
		if relieving_date:
			end_date = min(end_date, getdate(relieving_date))

		if end_date < start_date:
			return None, None
		return start_date, end_date

	def _last_closed_shift_date(self):
		"""Latest date whose shift (including the check-out grace time) is over at 'Last Sync of Check-in'."""
		sync = get_datetime(self.last_sync_of_checkin)
		day = sync.date()
		start_t, end_t = get_time(self.start_time), get_time(self.end_time)
		shift_end = datetime.combine(day if end_t > start_t else day + timedelta(days=1), end_t)
		actual_end = shift_end + timedelta(minutes=cint(self.allow_check_out_after_shift_end_time))
		return day if sync >= actual_end else day - timedelta(days=1)

	def get_dates_for_attendance(self, employee):
		start_date, end_date = self.get_start_and_end_dates(employee)
		if start_date is None:
			return []

		date_range = get_date_range(start_date, end_date)
		marked_attendance_dates = self.get_marked_attendance_dates_between(employee, start_date, end_date)

		# Weekly offs: Roster (Off) first, then Weekend Policy. One lookup for the whole range.
		weekend_dates = {getdate(d) for d in get_weekend_dates(employee, start_date, end_date)}

		# Holiday List: always skip public holidays. Skip its weekly offs only when the employee has no
		# Weekend Policy, otherwise the policy decides which days are weekly offs.
		holiday_dates = set()
		holiday_list = self.get_holiday_list(employee)
		if holiday_list:
			has_policy = bool(resolve_weekend_policy(employee, end_date))
			holiday_dates = set(
				get_holiday_dates_between(holiday_list, start_date, end_date, skip_weekly_offs=has_policy)
			)

		if getattr(self, "_collect_report", False):
			in_range = set(date_range)
			for code, dates in (
				("weekend", weekend_dates & in_range),
				("holiday", (holiday_dates - weekend_dates) & in_range),
				("already_marked", set(marked_attendance_dates) & in_range),
			):
				for d in sorted(dates):
					self._note(code, employee, d)

		return sorted(set(date_range) - holiday_dates - set(marked_attendance_dates) - weekend_dates)

	def _is_scheduled_for_shift(self, employee, date):
		"""True when this shift is the employee's shift on the date: an active Shift Assignment of this
		shift covers it, or no assignment covers it and this shift is the employee's default shift."""
		if self._has_active_assignment_for_date(employee, date):
			return True
		any_assignment = frappe.db.sql(
			"""select name from `tabShift Assignment`
			where employee = %s and docstatus = 1 and status = 'Active' and start_date <= %s
			and (end_date is null or end_date >= %s) limit 1""",
			(employee, date, date),
		)
		if any_assignment:
			return False
		return frappe.db.get_value("Employee", employee, "default_shift") == self.name

	def _evaluate_dates(self, employee):
		"""Single source of truth for Absent marking. Yields (date, decision, info) for every candidate date.

		decision: 'mark'           -> Absent should be created
		          'not_scheduled'  -> this shift is not the employee's shift on that date
		          'roster_not_work'-> the published roster says Off / Leave / another shift (info = roster entry)
		          'conflict'       -> an Attendance already exists on that date (info = that attendance)

		Roster-managed employees: the Roster Entry must say Work for this shift AND an active Shift Assignment
		must cover the date (Employee.default_shift is never a substitute).
		Other employees: an active Shift Assignment of this shift covers the date, else the default shift.
		"""
		roster_managed = self._is_roster_managed_employee(employee)

		for date in self.get_dates_for_attendance(employee):
			if roster_managed:
				entry = self._get_published_roster_entry(employee, date)
				if entry and (entry.entry_type != "Work" or entry.shift_type != self.name):
					yield date, "roster_not_work", entry
					continue
				if not self._has_active_assignment_for_date(employee, date):
					yield date, "not_scheduled", None
					continue
			elif not self._is_scheduled_for_shift(employee, date):
				yield date, "not_scheduled", None
				continue

			existing = self._existing_attendance(employee, date)
			if existing:
				yield date, "conflict", existing
				continue

			yield date, "mark", None

	def mark_absent_for_dates_with_no_attendance(self, employee):
		"""Marks Absent for the dates `_evaluate_dates` says should be marked, and notes why the others were not."""
		for date, decision, info in self._evaluate_dates(employee):
			if decision == "conflict":
				self._note("conflict", employee, date, extra=dict(info, date=str(date)))
				continue
			if decision == "roster_not_work":
				self._note("roster_not_work", employee, date, extra=f"{date}: {info.entry_type} {info.shift_type or ''}".strip())
				if self._has_active_assignment_for_date(employee, date):
					frappe.log_error(
						title="Roster Entry and Shift Assignment Conflict",
						message=f"Roster Entry for {employee} on {date} is {info.entry_type} "
						f"({info.shift_type or '-'}), but an active {self.name} Shift Assignment covers this date.",
					)
				continue
			if decision != "mark":
				self._note(decision, employee, date)
				continue

			try:
				frappe.db.savepoint("shift_absent_mark")
				attendance = mark_attendance(employee, date, "Absent", self.name)
			except frappe.ValidationError as e:
				frappe.db.rollback(save_point="shift_absent_mark")
				frappe.clear_messages()
				self._note("absent_failed", employee, date, extra=f"{date}: {frappe.utils.strip_html(str(e))[:200]}")
				continue
			if not attendance:
				continue

			frappe.get_doc(
				{
					"doctype": "Comment",
					"comment_type": "Comment",
					"reference_doctype": "Attendance",
					"reference_name": attendance,
					"content": frappe._("Employee was marked Absent due to missing Employee Checkins."),
				}
			).insert(ignore_permissions=True)

	def _is_roster_managed_employee(self, employee):
		"""An employee is roster-managed if a Published Roster Entry exists, or an active
		roster-linked Shift Assignment (roster_plan set by the roster engine) exists."""
		if frappe.db.get_value("Roster Entry", {"employee": employee, "status": "Published"}, "name"):
			return True
		return bool(
			frappe.db.get_value(
				"Shift Assignment",
				{
					"employee": employee,
					"roster_plan": ["is", "set"],
					"docstatus": 1,
					"status": "Active",
				},
				"name",
			)
		)

	def _get_published_roster_entry(self, employee, date):
		return frappe.db.get_value(
			"Roster Entry",
			{"employee": employee, "date": date, "status": "Published"},
			["entry_type", "shift_type"],
			as_dict=True,
		)

	def _has_active_assignment_for_date(self, employee, date):
		filters = {
			"employee": employee,
			"shift_type": self.name,
			"docstatus": 1,
			"status": "Active",
			"start_date": ["<=", date],
		}
		# open-ended assignments (no end date) or assignments ending on/after the candidate date
		if frappe.db.get_value("Shift Assignment", dict(filters, end_date=["is", "not set"]), "name"):
			return True
		return bool(frappe.db.get_value("Shift Assignment", dict(filters, end_date=[">=", date]), "name"))

	def _attendance_exists(self, employee, date):
		return bool(
			frappe.db.get_value(
				"Attendance",
				{"employee": employee, "attendance_date": date, "docstatus": ["<", 2]},
				"name",
			)
		)

	def _existing_attendance(self, employee, date):
		"""Any non-cancelled Attendance on the date, whatever its shift (one record per day is allowed)."""
		return frappe.db.get_value(
			"Attendance",
			{"employee": employee, "attendance_date": date, "docstatus": ["<", 2]},
			["name", "status", "shift", "docstatus"],
			as_dict=True,
		)