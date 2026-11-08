# Copyright (c) 2026, NeoTec and contributors
# For license information, please see license.txt

"""Auto Attendance setup checks for Shift Type.

One list of rules, used in three places:
  1. Browser  : shift_type_form.js calls `check_shift_type` when Save is clicked (dialog with suggestions)
                and on form refresh (orange banner for warnings).
  2. Server   : `validate_shift_type` (doc_events -> Shift Type -> validate) blocks the save when a rule
                of severity "error" fails, so import / API / console saves cannot skip the checks.
  3. Tests    : `run_checks(doc, now)` is pure, no database needed for the unit tests.

Errors   = the configuration will make auto attendance skip or mis-mark entries. They block the save.
Warnings = the configuration works but is risky or stuck. They are only shown on the form.

The server never changes values by itself. Suggested values are applied only when the user clicks
"Apply and Save" in the dialog.
"""

from datetime import datetime, timedelta

import frappe
from frappe import _
from frappe.utils import cint, get_datetime, get_time, getdate, now_datetime

DATE_FMT = "%Y-%m-%d"
DATETIME_FMT = "%Y-%m-%d %H:%M:%S"
FUTURE_TOLERANCE_MINUTES = 5
BACKFILL_WARN_DAYS = 31
STALE_AFTER_DAYS = 1

LABELS = {
	"process_attendance_after": "Process Attendance After",
	"last_sync_of_checkin": "Last Sync of Check-in",
	"auto_update_last_sync": "Auto Update Last Sync of Check-in",
	"begin_check_in_before_shift_start_time": "Begin Check-in Before Shift Start Time (mins)",
	"allow_check_out_after_shift_end_time": "Allow Check-out After Shift End Time (mins)",
	"holiday_list": "Holiday List",
}


# ----------------------------------------------------------------------------------------------
# helpers (pure)
# ----------------------------------------------------------------------------------------------
def _finding(fieldname, message, value=None, suggestion=None):
	return {
		"fieldname": fieldname,
		"label": _(LABELS.get(fieldname, fieldname)),
		"message": message,
		"suggested_value": value,
		"suggestion": suggestion,
	}


def _date_str(d):
	return d.strftime(DATE_FMT)


def _dt_str(d):
	return d.strftime(DATETIME_FMT)


def last_finished_sync(doc, now):
	"""Value HRMS itself would store in Last Sync of Check-in: the end of the latest shift (including the
	check-out grace time) that is already over, plus one minute. Looks back up to 3 days."""
	start_t = get_time(doc.get("start_time"))
	end_t = get_time(doc.get("end_time"))
	grace = timedelta(minutes=cint(doc.get("allow_check_out_after_shift_end_time")))

	for back in (0, 1, 2, 3):
		day = now.date() - timedelta(days=back)
		end_day = day if end_t > start_t else day + timedelta(days=1)
		actual_end = datetime.combine(end_day, end_t) + grace
		if actual_end <= now:
			return actual_end + timedelta(minutes=1)
	return None


def _earliest_assignment_start(shift_name):
	if not shift_name or not frappe.db.exists("Shift Type", shift_name):
		return None
	rows = frappe.db.sql(
		"""select min(start_date) from `tabShift Assignment`
		where shift_type = %s and docstatus = 1 and status = 'Active'""",
		(shift_name,),
	)
	return getdate(rows[0][0]) if rows and rows[0][0] else None


def default_process_after(doc, today):
	"""Suggested Process Attendance After: first assignment date of this shift, but never in the future
	and never more than ~30 days back (older dates create a lot of Present/Absent records at once)."""
	candidate = _earliest_assignment_start(doc.get("name")) or today
	floor = today - timedelta(days=BACKFILL_WARN_DAYS - 1)
	return min(today, max(candidate, floor))


def _pending_checkins(shift_name, from_date):
	if not shift_name or not frappe.db.exists("Shift Type", shift_name):
		return 0
	return frappe.db.count(
		"Employee Checkin",
		{
			"shift": shift_name,
			"attendance": ["is", "not set"],
			"skip_auto_attendance": 0,
			"time": [">=", from_date],
		},
	)


# ----------------------------------------------------------------------------------------------
# the rules
# ----------------------------------------------------------------------------------------------
def run_checks(doc, now=None):
	"""Returns (errors, warnings). `doc` is a Document, frappe._dict or plain dict (needs .get)."""
	errors, warnings = [], []

	if not cint(doc.get("enable_auto_attendance")):
		return errors, warnings

	now = now or now_datetime()
	today = now.date()
	paa = getdate(doc.get("process_attendance_after")) if doc.get("process_attendance_after") else None
	last_sync = get_datetime(doc.get("last_sync_of_checkin")) if doc.get("last_sync_of_checkin") else None
	sync_suggestion = last_finished_sync(doc, now) or now.replace(second=0, microsecond=0)
	paa_suggestion = default_process_after(doc, today)

	# ---- errors (block save) ---------------------------------------------------------------
	if not paa:
		errors.append(
			_finding(
				"process_attendance_after",
				_("It is empty. Auto attendance silently skips every check-in until a date is set."),
				_date_str(paa_suggestion),
				_("Use the date this shift starts being used (not in the future, not older than a month)."),
			)
		)

	if not last_sync:
		errors.append(
			_finding(
				"last_sync_of_checkin",
				_("It is empty. Auto attendance silently skips every check-in until a value is set."),
				_dt_str(sync_suggestion),
				_("Use the end of the latest finished shift."),
			)
		)
	elif last_sync > now + timedelta(minutes=FUTURE_TOLERANCE_MINUTES):
		errors.append(
			_finding(
				"last_sync_of_checkin",
				_("{0} is in the future. Days that have not happened yet could be marked Absent.").format(
					_dt_str(last_sync)
				),
				_dt_str(sync_suggestion),
				_("Use the end of the latest finished shift."),
			)
		)
	elif paa and paa <= today and getdate(last_sync) < paa and sync_suggestion.date() >= paa:
		errors.append(
			_finding(
				"last_sync_of_checkin",
				_(
					"{0} is before Process Attendance After ({1}), so nothing between these dates will be processed."
				).format(_dt_str(last_sync), _date_str(paa)),
				_dt_str(sync_suggestion),
				_("Use the end of the latest finished shift."),
			)
		)

	# ---- warnings (shown on the form, do not block) -----------------------------------------
	if paa and paa > today:
		warnings.append(
			_finding(
				"process_attendance_after",
				_("{0} is in the future. Nothing is processed until that date.").format(_date_str(paa)),
				_date_str(paa_suggestion),
				_("Use today, or the date the shift starts being used."),
			)
		)

	if paa and paa <= today and (today - paa).days > BACKFILL_WARN_DAYS:
		pending = _pending_checkins(doc.get("name"), paa)
		warnings.append(
			_finding(
				"process_attendance_after",
				_(
					"{0} is more than {1} days back. The next run can create many Present and Absent records at once ({2} unprocessed check-ins found)."
				).format(_date_str(paa), BACKFILL_WARN_DAYS, pending),
				_date_str(paa_suggestion),
				_("Use a closer date unless you really want to backfill."),
			)
		)

	if (
		not cint(doc.get("auto_update_last_sync"))
		and last_sync
		and last_sync <= now
		and last_finished_sync(doc, now)
		and last_sync < last_finished_sync(doc, now) - timedelta(days=STALE_AFTER_DAYS)
	):
		warnings.append(
			_finding(
				"auto_update_last_sync",
				_(
					"Last Sync of Check-in is still {0}, but the latest shift ended later. With Auto Update Last Sync off, newer days are not processed."
				).format(_dt_str(last_sync)),
				1,
				_("Tick Auto Update Last Sync of Check-in so it moves forward after every shift."),
			)
		)

	if (
		cint(doc.get("begin_check_in_before_shift_start_time")) == 0
		and cint(doc.get("allow_check_out_after_shift_end_time")) == 0
	):
		warnings.append(
			_finding(
				"begin_check_in_before_shift_start_time",
				_(
					"Both check-in and check-out buffers are 0. Punches even a minute outside the shift are treated as off-shift."
				),
				60,
				_("60 minutes before start and 60 minutes after end is a common starting point."),
			)
		)

	if not doc.get("holiday_list"):
		warnings.append(
			_finding(
				"holiday_list",
				_("No Holiday List selected. Public holidays may be marked Absent."),
				None,
				_("Select the company Holiday List."),
			)
		)

	return errors, warnings


# ----------------------------------------------------------------------------------------------
# entry points
# ----------------------------------------------------------------------------------------------
@frappe.whitelist()
def check_shift_type(doc):
	"""Called by shift_type_form.js with the unsaved form values."""
	frappe.has_permission("Shift Type", "read", throw=True)
	errors, warnings = run_checks(frappe._dict(frappe.parse_json(doc)))
	return {"errors": errors, "warnings": warnings}


def validate_shift_type(doc, method=None):
	"""doc_events -> Shift Type -> validate. Blocks the save when auto attendance would not work."""
	flags = frappe.flags
	if flags.in_patch or flags.in_install or flags.in_migrate or flags.in_import:
		return
	if flags.get("skip_shift_type_checks"):
		return

	errors, _warnings = run_checks(doc)
	if not errors:
		return

	rows = "".join(
		"<li><b>{0}</b>: {1}{2}</li>".format(
			frappe.utils.escape_html(e["label"]),
			frappe.utils.escape_html(e["message"]),
			"<br><i>{0}</i>".format(frappe.utils.escape_html(_("Suggested: {0}").format(e["suggested_value"])))
			if e.get("suggested_value") not in (None, "")
			else "",
		)
		for e in errors
	)
	frappe.throw(
		"<ul>{0}</ul>".format(rows),
		title=_("Auto Attendance Setup Problem"),
	)