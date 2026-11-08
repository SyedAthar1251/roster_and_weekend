"""Pure-logic tests for the Shift Type auto attendance checks (no database needed):
    python -m unittest roster_and_weekend.roster_and_weekend.tests.test_shift_type_checks
"""
import sys
import types
import unittest
from datetime import date, datetime, time, timedelta

fr = types.ModuleType("frappe")
fu = types.ModuleType("frappe.utils")


def _getdate(v):
	if isinstance(v, datetime):
		return v.date()
	if isinstance(v, date):
		return v
	return datetime.strptime(str(v)[:10], "%Y-%m-%d").date()


def _get_datetime(v):
	if isinstance(v, datetime):
		return v
	return datetime.strptime(str(v)[:19], "%Y-%m-%d %H:%M:%S")


def _get_time(v):
	if isinstance(v, time):
		return v
	if isinstance(v, timedelta):
		return (datetime.min + v).time()
	return datetime.strptime(str(v), "%H:%M:%S").time()


fu.cint = lambda v: int(v or 0)
fu.getdate, fu.get_datetime, fu.get_time = _getdate, _get_datetime, _get_time
fu.now_datetime = datetime.now
fr.utils = fu
fr._ = lambda s: s
fr.whitelist = lambda *a, **k: (lambda f: f)
fr.flags = types.SimpleNamespace()
sys.modules.setdefault("frappe", fr)
sys.modules.setdefault("frappe.utils", fu)

from roster_and_weekend.roster_and_weekend import shift_type_checks as sc  # noqa: E402

NOW = datetime(2026, 11, 2, 10, 0, 0)  # Monday morning


def shift(**kw):
	base = dict(
		enable_auto_attendance=1, start_time="12:30:00", end_time="20:30:00",
		begin_check_in_before_shift_start_time=60, allow_check_out_after_shift_end_time=60,
		process_attendance_after="2026-10-25", last_sync_of_checkin="2026-11-01 21:31:00",
		auto_update_last_sync=1, holiday_list="2026",
	)
	base.update(kw)
	return base


def fields(findings):
	return [f["fieldname"] for f in findings]


class TestShiftTypeChecks(unittest.TestCase):
	def test_valid_setup_has_no_errors(self):
		errors, warnings = sc.run_checks(shift(), NOW)
		self.assertEqual(errors, [])
		self.assertEqual(warnings, [])

	def test_auto_attendance_off_skips_all_checks(self):
		errors, warnings = sc.run_checks(shift(enable_auto_attendance=0, process_attendance_after=None), NOW)
		self.assertEqual((errors, warnings), ([], []))

	def test_blank_dates_are_errors_with_suggestions(self):
		errors, _w = sc.run_checks(shift(process_attendance_after=None, last_sync_of_checkin=None), NOW)
		self.assertEqual(fields(errors), ["process_attendance_after", "last_sync_of_checkin"])
		self.assertEqual(errors[1]["suggested_value"], "2026-11-01 21:31:00")

	def test_last_sync_in_future_is_error(self):
		errors, _w = sc.run_checks(shift(last_sync_of_checkin="2026-11-05 23:59:59"), NOW)
		self.assertEqual(fields(errors), ["last_sync_of_checkin"])

	def test_last_sync_before_process_after_is_error(self):
		errors, _w = sc.run_checks(shift(process_attendance_after="2026-10-30", last_sync_of_checkin="2026-10-28 20:00:00"), NOW)
		self.assertEqual(fields(errors), ["last_sync_of_checkin"])

	def test_stuck_last_sync_with_auto_update_off_is_warning_not_error(self):
		errors, warnings = sc.run_checks(
			shift(auto_update_last_sync=0, process_attendance_after="2026-09-01", last_sync_of_checkin="2026-09-01 23:59:59"), NOW)
		self.assertEqual(errors, [])
		self.assertIn("auto_update_last_sync", fields(warnings))

	def test_future_process_after_is_warning(self):
		errors, warnings = sc.run_checks(shift(process_attendance_after="2026-11-10"), NOW)
		self.assertEqual(errors, [])
		self.assertIn("process_attendance_after", fields(warnings))

	def test_zero_buffers_and_missing_holiday_list_are_warnings(self):
		_e, warnings = sc.run_checks(
			shift(begin_check_in_before_shift_start_time=0, allow_check_out_after_shift_end_time=0, holiday_list=None), NOW)
		self.assertIn("begin_check_in_before_shift_start_time", fields(warnings))
		self.assertIn("holiday_list", fields(warnings))

	def test_suggestion_before_shift_end_uses_previous_day(self):
		self.assertEqual(sc.last_finished_sync(shift(), datetime(2026, 11, 2, 15, 0)), datetime(2026, 11, 1, 21, 31))

	def test_night_shift_suggestion(self):
		night = shift(start_time="22:00:00", end_time="06:00:00")
		self.assertEqual(sc.last_finished_sync(night, datetime(2026, 11, 2, 10, 0)), datetime(2026, 11, 2, 7, 1))

	def test_applying_all_suggestions_clears_errors(self):
		bad = shift(process_attendance_after=None, last_sync_of_checkin="2026-11-09 10:00:00")
		errors, _w = sc.run_checks(bad, NOW)
		for e in errors:
			bad[e["fieldname"]] = e["suggested_value"]
		self.assertEqual(sc.run_checks(bad, NOW)[0], [])


if __name__ == "__main__":
	unittest.main()