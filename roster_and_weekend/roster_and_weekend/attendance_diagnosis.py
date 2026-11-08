# Copyright (c) 2026, NeoTec and contributors
# For license information, please see license.txt

"""Shift Type -> "Mark Attendance" report.

Replaces the stock "attendance marked" message with what really happened:
  * how many Present / Absent records were created,
  * for everything that was NOT marked: the reason, the affected dates, and the solution,
  * one-click fixes for the safe cases (cancel conflicting Absent records, un-skip check-ins, re-link check-ins).

Where the reasons come from (no logic is duplicated here):
  * Absent pipeline  : CustomShiftType._evaluate_dates in overrides/shift_type.py records why it skipped a date.
  * Check-in pipeline: HRMS marks a check-in "skip auto attendance" and writes the error as a Comment on it;
                       this module reads that comment and classifies the check-ins that are still unprocessed.

Security: every function re-computes its targets on the server from the Shift Type; the browser only sends
the Shift Type name and the names of the fixes. Fixes run with the caller's own permissions.
"""

import frappe
from frappe import _
from frappe.utils import cint, getdate, now_datetime, strip_html

from roster_and_weekend.roster_and_weekend.weekend_policy import get_weekend_dates

MAX_EMPLOYEES = 500  # employees handled per run / fix
MAX_CHECKINS = 3000  # check-ins inspected per run
PREVIEW_MAX_EMPLOYEES = 200  # above this the confirmation skips the exact Absent count
QUEUE_ABOVE = 1000  # same limit as stock HRMS: larger runs go to the background queue

# order = order shown to the user
REASONS = {
	"conflict": dict(
		title=("Attendance already exists under another shift"),
		kind="fix",
		solution=("Only one attendance per day is allowed, so nothing new can be marked for this shift on these dates. "
			"If the existing records are wrong Absent records, cancel them and process again. "
			"Present, On Leave and manual (no shift) records are never cancelled automatically."
		),
		action="cancel_conflicting_absent",
	),
	"checkin_skipped": dict(
		title=("Check-ins are set to skip auto attendance"),
		kind="fix",
		solution=("HRMS skips a check-in when it cannot create attendance for it. The reason it recorded is shown below. "
			"Fix that reason first (for example the conflicting attendance), then un-skip the check-ins."
		),
		action="unskip_checkins",
	),
	"checkin_other_shift": dict(
		title=("Check-ins are linked to a different shift"),
		kind="fix",
		solution=(
			"These check-ins were saved before this shift's assignment existed, so they point to another shift. "
			"Re-saving them links them to the shift assigned on that date."
		),
		action="relink_checkins",
	),
	"checkin_overlap": dict(
		title=("Employee has two active shift assignments on these dates"),
		kind="fix",
		solution=(
			"A check-in can belong to only one shift, and the other assignment shown here wins. Cancel or shorten "
			"the assignment you do not need (Shift Assignment list), then process again. Re-linking cannot fix this."
		),
		action=None,
	),
	"checkin_relink_blocked": dict(
		title=("Check-ins cannot be re-linked automatically"),
		kind="fix",
		solution=(
			"HR Settings allows multiple shift assignments on the same day, so HRMS does not change the shift of an "
			"existing check-in. Link them manually (open the check-in and set the Shift), or turn that setting off."
		),
		action=None,
	),
	"checkin_no_shift": dict(
		title=("Check-ins have no shift"),
		kind="fix",
		solution=("These check-ins were saved before a Shift Assignment existed. Re-saving them links them to the shift "
			"assigned on that date."
		),
		action="relink_checkins",
	),
	"absent_failed": dict(
		title=("Absent could not be created"),
		kind="fix",
		solution=("Fix the reason shown for each date, then process again."),
		action=None,
	),
	"checkin_offshift": dict(
		title=("Check-ins are outside the shift window"),
		kind="warn",
		solution=("A punch must fall between (shift start minus the check-in buffer) and (shift end plus the check-out "
			"buffer). Check the punch time, or widen the buffers on this Shift Type."
		),
		action=None,
	),
	"checkin_not_closed": dict(
		title=("Shift not finished yet (Last Sync of Check-in is behind)"),
		kind="warn",
		solution=("Check-ins are only processed after the shift has ended and Last Sync of Check-in has moved past it. "
			"Turn on Auto Update Last Sync of Check-in, or wait for the hourly update."
		),
		action=None,
	),
	"not_scheduled": dict(
		title=("This shift is not the employee's shift on these dates"),
		kind="warn",
		solution=("No active Shift Assignment of this shift covers the date, and this is not the employee's default shift. "
			"Create or extend the Shift Assignment if attendance is expected here."
		),
		action=None,
	),
	"roster_not_work": dict(
		title=("Roster says the employee is not working this shift"),
		kind="info",
		solution=("The published roster has Off, Leave or another shift on these dates. Nothing to fix."),
		action=None,
	),
	"checkin_on_weekend": dict(
		title=("Check-ins on a weekly off were ignored"),
		kind="info",
		solution=("These days are weekly offs by Roster or Weekend Policy, so check-ins are not turned into Present. "
			"If the employee really worked, change the roster / policy or use an Attendance Request."
		),
		action=None,
	),
	"checkin_on_holiday": dict(
		title=("Check-ins on a holiday were ignored"),
		kind="info",
		solution=("Tick 'Mark Auto Attendance on Holidays' on this Shift Type if worked holidays should count."),
		action=None,
	),
	"weekend": dict(
		title=("Weekly off (no Absent marked)"),
		kind="info",
		solution=("Skipped by Roster or Weekend Policy. Nothing to fix."),
		action=None,
	),
	"holiday": dict(
		title=("Holiday (no Absent marked)"),
		kind="info",
		solution=("Skipped because of the Holiday List. Nothing to fix."),
		action=None,
	),
	"already_marked": dict(
		title=("Already marked for this shift, leave or half day"),
		kind="info",
		solution=("Nothing to fix."),
		action=None,
	),
}

CANCEL_ACTION = "cancel_conflicting_absent"
UNSKIP_ACTION = "unskip_checkins"
RELINK_ACTION = "relink_checkins"
FIX_ORDER = [CANCEL_ACTION, RELINK_ACTION, UNSKIP_ACTION]


# ----------------------------------------------------------------------------------------------
# pure helpers
# ----------------------------------------------------------------------------------------------
def classify_checkin(row, shift_name, last_sync, covered_by_assignment, overlap=None, multiple_allowed=False):
	"""Why an unprocessed check-in is not turning into attendance. Returns a reason code or None.

	row: dict with shift, skip_auto_attendance, offshift, shift_actual_end
	covered_by_assignment: an active Shift Assignment of this shift covers the check-in date
	overlap: another active Shift Assignment (any other shift) covers the same date
	multiple_allowed: HR Settings allows several shift assignments per day (HRMS then never re-links a check-in)
	"""
	relevant = row.get("shift") == shift_name or covered_by_assignment
	if not relevant:
		return None
	if cint(row.get("skip_auto_attendance")):
		return "checkin_skipped"
	if cint(row.get("offshift")):
		return "checkin_offshift"
	if row.get("shift") == shift_name:
		end = row.get("shift_actual_end")
		if end and last_sync and end >= last_sync:
			return "checkin_not_closed"
		return None
	if overlap:
		return "checkin_overlap"
	if multiple_allowed:
		return "checkin_relink_blocked"
	return "checkin_no_shift" if not row.get("shift") else "checkin_other_shift"


def _is_cancelable(attendance, shift_name):
	"""Only submitted Absent records that belong to another shift are cancelled automatically."""
	return (
		attendance.get("status") == "Absent"
		and cint(attendance.get("docstatus")) == 1
		and attendance.get("shift")
		and attendance.get("shift") != shift_name
	)


# ----------------------------------------------------------------------------------------------
# data helpers
# ----------------------------------------------------------------------------------------------
def _load_shift(shift_type, permission="write"):
	st = frappe.get_doc("Shift Type", shift_type)
	st.check_permission(permission)
	if not hasattr(st, "_evaluate_dates"):
		frappe.throw(
			_(
				"The Shift Type override is not active. Add 'Shift Type' to override_doctype_class in hooks.py "
				"(roster_and_weekend.overrides.shift_type.CustomShiftType) and restart."
			)
		)
	return st


def _scope_employees(st):
	employees = sorted(set(st.get_assigned_employees(st.process_attendance_after, True)))
	return employees[:MAX_EMPLOYEES], len(employees) > MAX_EMPLOYEES


def _assignment_cover(st, employees):
	"""{employee: [(start, end or None), ...]} of active Shift Assignments of this shift."""
	cover = {}
	if not employees:
		return cover
	for a in frappe.get_all(
		"Shift Assignment",
		filters={"employee": ["in", employees], "shift_type": st.name, "docstatus": 1, "status": "Active"},
		fields=["employee", "start_date", "end_date"],
	):
		cover.setdefault(a.employee, []).append(
			(getdate(a.start_date), getdate(a.end_date) if a.end_date else None)
		)
	return cover


def _covered(cover, employee, date):
	return any(s <= date and (e is None or date <= e) for s, e in cover.get(employee, []))


def _checkin_rows(st, employees):
	return frappe.get_all(
		"Employee Checkin",
		filters={
			"employee": ["in", employees],
			"attendance": ["is", "not set"],
			"time": [">=", st.process_attendance_after],
		},
		fields=["name", "employee", "time", "shift", "shift_actual_end", "skip_auto_attendance", "offshift"],
		order_by="employee, time",
		limit=MAX_CHECKINS,
	)


def _skip_reasons(names):
	"""Latest 'Reason for skipping auto attendance' comment HRMS wrote on each check-in."""
	if not names:
		return {}
	out = {}
	for c in frappe.get_all(
		"Comment",
		filters={
			"reference_doctype": "Employee Checkin",
			"reference_name": ["in", names],
			"content": ["like", "%Reason for skipping%"],
		},
		fields=["reference_name", "content"],
		order_by="creation asc",
	):
		text = strip_html(c.content or "").replace("Reason for skipping auto attendance:", "").strip()
		out[c.reference_name] = text[:200]
	return out


def _other_assignments(st, employees):
	"""{employee: [(start, end or None, shift, name)]} of active assignments of OTHER shifts."""
	other = {}
	if not employees:
		return other
	for a in frappe.get_all(
		"Shift Assignment",
		filters={
			"employee": ["in", employees],
			"shift_type": ["!=", st.name],
			"docstatus": 1,
			"status": "Active",
		},
		fields=["name", "employee", "shift_type", "start_date", "end_date"],
	):
		other.setdefault(a.employee, []).append(
			(getdate(a.start_date), getdate(a.end_date) if a.end_date else None, a.shift_type, a.name)
		)
	return other


def _find_overlap(other, employee, date):
	for start, end, shift, name in other.get(employee, []):
		if start <= date and (end is None or date <= end):
			return {"shift": shift, "name": name}
	return None


def _multiple_shifts_allowed():
	try:
		return cint(frappe.db.get_single_value("HR Settings", "allow_multiple_shift_assignments"))
	except Exception:
		return 0


def _classified_checkins(st, employees):
	"""Yields (row, date, code, overlap) for every unprocessed check-in that has a reason."""
	last_sync = frappe.utils.get_datetime(st.last_sync_of_checkin)
	cover = _assignment_cover(st, employees)
	other = _other_assignments(st, employees)
	multiple = _multiple_shifts_allowed()
	weekend_cache = {}
	today = getdate(now_datetime())

	for r in _checkin_rows(st, employees):
		d = getdate(r.time)
		if r.employee not in weekend_cache:
			weekend_cache[r.employee] = {
				getdate(x) for x in get_weekend_dates(r.employee, st.process_attendance_after, today)
			}
		if d in weekend_cache[r.employee]:
			continue  # weekly-off check-ins are reported by the weekend note instead
		overlap = _find_overlap(other, r.employee, d)
		code = classify_checkin(r, st.name, last_sync, _covered(cover, r.employee, d), overlap, multiple)
		if code:
			yield r, d, code, overlap


def _checkin_findings(st, employees):
	found = {}
	skipped_names = []

	for r, d, code, overlap in _classified_checkins(st, employees):
		item = found.setdefault(code, {"count": 0, "employees": set(), "samples": [], "extra": []})
		item["count"] += 1
		item["employees"].add(r.employee)
		if len(item["samples"]) < 5:
			item["samples"].append(str(d))
		if code == "checkin_skipped":
			skipped_names.append((r.name, str(d)))
		elif code == "checkin_overlap" and len(item["extra"]) < 5:
			item["extra"].append(
				_("{0}: also assigned to {1} ({2})").format(d, overlap["shift"], overlap["name"])
			)
		elif code in ("checkin_other_shift", "checkin_no_shift", "checkin_offshift", "checkin_relink_blocked") and len(
			item["extra"]
		) < 5:
			item["extra"].append(f"{d} {r.time.strftime('%H:%M')} ({r.shift or _('no shift')})")

	if skipped_names:
		reasons = _skip_reasons([n for n, _d in skipped_names])
		item = found["checkin_skipped"]
		seen = []
		for name, _d in skipped_names:
			text = reasons.get(name)
			if text and text not in seen and len(seen) < 3:
				seen.append(text)
		item["extra"] = seen
		# Only skips HRMS made itself (it leaves a reason comment) can be undone safely. Check-ins skipped on
		# purpose (manual tick, device integration) are left alone.
		item["fixable"] = sum(1 for n, _d in skipped_names if n in reasons)
		if item["fixable"] < item["count"]:
			item["extra"].append(
				_("{0} check-in(s) were skipped on purpose (no error recorded) and will not be changed.").format(
					item["count"] - item["fixable"]
				)
			)
	return found


def _format_extra(code, extra):
	out = []
	for e in extra:
		if code == "conflict" and isinstance(e, dict):
			out.append(
				_("{0}: {1} under {2} ({3})").format(
					e.get("date"), e.get("status"), e.get("shift") or _("no shift"), e.get("name")
				)
			)
		else:
			out.append(str(e))
	return out


def _build_findings(st, employees):
	merged = {}
	for code, v in (getattr(st, "_skip_report", None) or {}).items():
		merged[code] = {
			"count": v["count"],
			"employees": set(v["employees"]),
			"samples": list(v["samples"]),
			"extra": list(v["extra"]),
		}
	for code, v in _checkin_findings(st, employees).items():
		merged[code] = v

	findings = []
	for code, meta in REASONS.items():
		v = merged.get(code)
		if not v:
			continue
		details = _format_extra(code, v["extra"])
		fixable = True
		if code == "checkin_skipped":
			fixable = bool(v.get("fixable"))
		if code == "conflict":
			extras = [e for e in v["extra"] if isinstance(e, dict)]
			fixable = any(_is_cancelable(e, st.name) for e in extras)
		findings.append(
			{
				"code": code,
				"title": _(meta["title"]),
				"kind": meta["kind"],
				"count": v["count"],
				"employees": len(v["employees"]),
				"samples": v["samples"],
				"details": details,
				"solution": _(meta["solution"]),
				"action": meta["action"] if fixable else None,
			}
		)
	return findings


# ----------------------------------------------------------------------------------------------
# whitelisted entry points
# ----------------------------------------------------------------------------------------------
@frappe.whitelist(methods=["POST"])
def preview_attendance(shift_type):
	"""Read-only. What 'Mark Attendance' is about to do, shown in the confirmation before anything is written."""
	st = _load_shift(shift_type, "read")

	if st.has_incorrect_shift_config():
		return {
			"status": "config",
			"message": _(
				"Enable Auto Attendance and fill Process Attendance After and Last Sync of Check-in first."
			),
		}

	employees, truncated = _scope_employees(st)
	logs = st.get_employee_checkins()
	checkin_days = {(l.employee, getdate(l.shift_start)) for l in logs}

	out = {
		"status": "ok",
		"employees": len(employees),
		"truncated": truncated,
		"checkin_days": len(checkin_days),
		"absent": None,
		"from_date": None,
		"to_date": None,
	}

	starts, ends = [], []
	absent = 0
	exact = len(employees) <= PREVIEW_MAX_EMPLOYEES
	for emp in employees:
		start, end = st.get_start_and_end_dates(emp)
		if start:
			starts.append(start)
			ends.append(end)
		if not exact:
			continue
		for d, decision, _info in st._evaluate_dates(emp):
			# a day that has check-ins becomes Present (or Absent by working hours) from the check-ins, not by the Absent step
			if decision == "mark" and (emp, d) not in checkin_days:
				absent += 1

	if starts:
		out["from_date"], out["to_date"] = str(min(starts)), str(max(ends))
	if exact:
		out["absent"] = absent
	return out


@frappe.whitelist(methods=["POST"])
def process_with_report(shift_type):
	"""Runs auto attendance for the Shift Type and returns what was marked and why the rest was not."""
	st = _load_shift(shift_type)

	if st.has_incorrect_shift_config():
		return {
			"status": "config",
			"message": _(
				"Enable Auto Attendance and fill Process Attendance After and Last Sync of Check-in first."
			),
		}

	employees, truncated = _scope_employees(st)
	logs = st.get_employee_checkins()

	if len(logs) > QUEUE_ABOVE:
		st.process_auto_attendance(is_manually_triggered=True)  # stock behaviour: runs in the background queue
		return {
			"status": "queued",
			"message": _(
				"More than {0} check-ins found. Attendance is being processed in the background. Open the Mark "
				"Attendance report again in a few minutes to see the result."
			).format(QUEUE_ABOVE),
		}

	started = now_datetime()
	st._collect_report = True
	try:
		st._process(logs)
		frappe.db.commit()
	except Exception as e:
		frappe.db.rollback()
		log = frappe.log_error(title="Mark Attendance report: processing failed")
		return {
			"status": "error",
			"message": strip_html(str(e))[:300],
			"error_log": log.name if log else None,
		}

	created = dict(
		frappe.db.sql(
			"""select status, count(*) from `tabAttendance`
			where shift = %s and creation >= %s and docstatus < 2 group by status""",
			(st.name, started),
		)
	)
	marked_dates = {"Present": [], "Absent": []}
	for status, d in frappe.db.sql(
		"""select status, attendance_date from `tabAttendance`
		where shift = %s and creation >= %s and docstatus < 2 and status in ('Present', 'Absent')
		order by attendance_date limit 400""",
		(st.name, started),
	):
		marked_dates[status].append(str(d))

	findings = _build_findings(st, employees)
	return {
		"status": "ok",
		"marked": {"Present": created.get("Present", 0), "Absent": created.get("Absent", 0)},
		"marked_dates": marked_dates,
		"other_marked": sum(v for k, v in created.items() if k not in ("Present", "Absent")),
		"employees": len(employees),
		"truncated": truncated,
		"has_problems": any(f["kind"] in ("fix", "warn") for f in findings),
		"findings": findings,
	}


@frappe.whitelist(methods=["POST"])
def run_fixes(shift_type, actions):
	"""Applies the selected safe fixes. Targets are recomputed here, never taken from the browser."""
	st = _load_shift(shift_type)
	actions = [a for a in FIX_ORDER if a in (frappe.parse_json(actions) or [])]
	if not actions:
		frappe.throw(_("No fix selected."))

	employees, _truncated = _scope_employees(st)
	result = {}
	if CANCEL_ACTION in actions:
		result[CANCEL_ACTION] = _fix_cancel_conflicting_absent(st, employees)
	if RELINK_ACTION in actions:
		result[RELINK_ACTION] = _fix_relink_checkins(st, employees)
	if UNSKIP_ACTION in actions:
		result[UNSKIP_ACTION] = _fix_unskip_checkins(st, employees)
	frappe.db.commit()
	return result


def _fix_cancel_conflicting_absent(st, employees):
	frappe.has_permission("Attendance", "cancel", throw=True)
	cancelled, failed, kept = 0, [], 0
	for emp in employees:
		for date, decision, info in st._evaluate_dates(emp):
			if decision != "conflict":
				continue
			if not _is_cancelable(info, st.name):
				kept += 1
				continue
			try:
				doc = frappe.get_doc("Attendance", info.name)
				doc.cancel()
				doc.add_comment(
					"Comment",
					_("Cancelled from the Shift Type {0} Mark Attendance report: Absent under shift {1} conflicted "
					"with {0}'s assignment on {2}.").format(st.name, info.shift, date),
				)
				cancelled += 1
			except Exception as e:
				frappe.db.rollback()
				failed.append(f"{info.name}: {strip_html(str(e))[:120]}")
	return {"cancelled": cancelled, "kept_for_manual_review": kept, "failed": failed[:5]}


def _fix_relink_checkins(st, employees):
	frappe.has_permission("Employee Checkin", "write", throw=True)
	relinked, unchanged = 0, 0
	for r, _d, code, _overlap in _classified_checkins(st, employees):
		if code not in ("checkin_other_shift", "checkin_no_shift"):
			continue  # overlaps / blocked cases cannot be fixed by re-saving
		try:
			doc = frappe.get_doc("Employee Checkin", r.name)
			doc.save()  # validate() looks up the shift again
			if doc.shift == st.name:
				relinked += 1
			else:
				unchanged += 1
		except Exception:
			frappe.db.rollback()
			unchanged += 1
	return {"relinked": relinked, "unchanged": unchanged}


def _fix_unskip_checkins(st, employees):
	frappe.has_permission("Employee Checkin", "write", throw=True)
	names = [
		r.name
		for r in _checkin_rows(st, employees)
		if r.shift == st.name and cint(r.skip_auto_attendance)
	]
	names = [n for n in names if n in _skip_reasons(names)]  # HRMS-made skips only
	for i in range(0, len(names), 500):
		frappe.db.set_value(
			"Employee Checkin", {"name": ["in", names[i : i + 500]]}, "skip_auto_attendance", 0
		)
	return {"unskipped": len(names)}