app_name = "roster_and_weekend"
app_title = "Roster And Weekend"
app_publisher = "neotec.ai"
app_description = "Roster planning, weekend policy and week-off swaps for Frappe HRMS"
app_email = "neotec@gmail.com"
app_license = "mit"

required_apps = ["hrms"]

# ---------------------------------------------------------------------------
# Desk scripts
# Paths are relative to the app package (apps/roster_and_weekend/roster_and_weekend/).
# ---------------------------------------------------------------------------
doctype_js = {
	"Shift Assignment": "public/js/shift_assignment.js",
	"Roster Plan": "public/js/roster_plan.js",
	"Roster Pattern": "public/js/roster_pattern.js",
	"Shift Type": "roster_and_weekend/shift_type_form.js",
}

# ---------------------------------------------------------------------------
# Controller overrides (stock HRMS doctypes)
#   Shift Type                 roster + weekend aware auto attendance
#   Shift Assignment           default-shift rules
#   Shift Schedule Assignment  carries custom_weekend_policy into generated assignments
# ---------------------------------------------------------------------------
override_doctype_class = {
	"Shift Assignment": "roster_and_weekend.overrides.shift_assignment_override.CustomShiftAssignment",
	"Shift Type": "roster_and_weekend.overrides.shift_type.CustomShiftType",
	"Shift Schedule Assignment": "roster_and_weekend.overrides.shift_schedule_assignment.CustomShiftScheduleAssignment",
}

# ---------------------------------------------------------------------------
# Document events
# ---------------------------------------------------------------------------
doc_events = {
	"Employee": {
		"on_update": "roster_and_weekend.roster_and_weekend.events.employee_updated",
	},
	"Shift Assignment": {
		"validate": "roster_and_weekend.roster_and_weekend.time_exception.validate_shift_assignment",
		"on_submit": "roster_and_weekend.shift_assignment.update_employee_shift",
	},
	"Employee Checkin": {
		"validate": "roster_and_weekend.roster_and_weekend.time_exception.apply_to_checkin",
	},
	"Attendance": {
		"before_insert": "roster_and_weekend.roster_and_weekend.time_exception.set_on_attendance",
	},
	"Shift Type": {
		"validate": "roster_and_weekend.roster_and_weekend.shift_type_checks.validate_shift_type",
	},
	"Leave Application": {
		"on_submit": "roster_and_weekend.roster_and_weekend.events.leave_submitted",
		"on_cancel": "roster_and_weekend.roster_and_weekend.events.leave_cancelled",
	},
	# Only fires when an "Overtime Request" doctype exists on the site (it ships with CentralHrms).
	"Overtime Request": {
		"on_submit": "roster_and_weekend.roster_and_weekend.overtime.on_submit",
		"on_cancel": "roster_and_weekend.roster_and_weekend.overtime.on_cancel",
	},
}

# ---------------------------------------------------------------------------
# Scheduler
# ---------------------------------------------------------------------------
scheduler_events = {
	"cron": {
		# Sunday 18:00 - weekend bridge attendance alert
		"0 18 * * 0": [
			"roster_and_weekend.roster_and_weekend.weekend_bridge.notify_weekend_bridge_cases",
		],
		# every 5 minutes - no-show, missed check-out, understaffing, unacknowledged rosters
		"*/5 * * * *": [
			"roster_and_weekend.roster_and_weekend.alerts.run",
		],
	},
}

# The roster board is served at /hr/roster: www/roster.* in this app has the same page name as the one in HRMS,
# so this app's page replaces the stock one (router base in the built bundle is /hr/roster).

# ---------------------------------------------------------------------------
# Install / migrate
# ---------------------------------------------------------------------------
after_install = "roster_and_weekend.setup.install.after_install"
after_migrate = "roster_and_weekend.setup.install.after_migrate"


# ---------------------------------------------------------------------------
# Runtime patches of HRMS functions (same three the CentralHrms app applies).
# They make HRMS leave-day counting, the HRMS roster board and the Shift Assignment Tool Weekend Policy aware.
# A failure here is printed (hooks.py has no logger) instead of breaking every request.
# ---------------------------------------------------------------------------
def _apply_runtime_patches():
	import traceback

	try:
		from roster_and_weekend.roster_and_weekend.leave_weekend_policy import patch_get_number_of_leave_days
		patch_get_number_of_leave_days()
	except Exception:
		print("roster_and_weekend: could not patch get_number_of_leave_days")
		traceback.print_exc()

	try:
		from roster_and_weekend.overrides.shift_assignment_tool import patch_shift_assignment_tool
		patch_shift_assignment_tool()
	except Exception:
		print("roster_and_weekend: could not patch Shift Assignment Tool")
		traceback.print_exc()

	try:
		from roster_and_weekend.overrides.roster_api import patch_roster_api
		patch_roster_api()
	except Exception:
		print("roster_and_weekend: could not patch hrms.api.roster")
		traceback.print_exc()


_apply_runtime_patches()