"""Pure-logic tests for Shift Time Exception. frappe is stubbed, so this runs without a bench:
    python -m unittest roster_and_weekend.roster_and_weekend.tests.test_time_exception
"""
import sys
import types
import unittest
from datetime import date, datetime, timedelta
from unittest.mock import patch

fr = types.ModuleType("frappe")
fu = types.ModuleType("frappe.utils")
fu.getdate = lambda v: v if isinstance(v, date) and not isinstance(v, datetime) else (v.date() if isinstance(v, datetime) else datetime.strptime(str(v)[:10], "%Y-%m-%d").date())
fu.get_datetime = lambda v: v if isinstance(v, datetime) else datetime.strptime(str(v)[:19], "%Y-%m-%d %H:%M:%S")
fr.utils = fu
fr.whitelist = lambda *a, **k: (lambda f: f) if not (a and callable(a[0])) else a[0]
fr.local = types.SimpleNamespace()
sys.modules.setdefault("frappe", fr)
sys.modules.setdefault("frappe.utils", fu)

from roster_and_weekend.roster_and_weekend import time_exception as te  # noqa: E402


class Doc(dict):
	__getattr__ = dict.get

	def __setattr__(self, k, v):
		self[k] = v

	def set(self, k, v):
		self[k] = v


def checkin():
	return Doc(employee="E1", shift="A", shift_start=datetime(2026, 11, 9, 9, 0), shift_end=datetime(2026, 11, 9, 18, 0),
		shift_actual_start=datetime(2026, 11, 9, 8, 0), shift_actual_end=datetime(2026, 11, 9, 19, 0))


class TestApplyToCheckin(unittest.TestCase):
	def test_shifts_all_four_stamps(self):
		d = checkin()
		with patch.object(te, "get_time_exception", return_value={"name": "Late +30", "start_offset": 30, "end_offset": 30}):
			te.apply_to_checkin(d)
		self.assertEqual(d.shift_start, datetime(2026, 11, 9, 9, 30))
		self.assertEqual(d.shift_end, datetime(2026, 11, 9, 18, 30))
		self.assertEqual(d.shift_actual_start, datetime(2026, 11, 9, 8, 30))
		self.assertEqual(d.shift_actual_end, datetime(2026, 11, 9, 19, 30))
		self.assertEqual(d.custom_time_exception, "Late +30")

	def test_second_save_without_restamp_does_not_shift_twice(self):
		d = checkin()
		exc = {"name": "Late +30", "start_offset": 30, "end_offset": 30}
		with patch.object(te, "get_time_exception", return_value=exc):
			te.apply_to_checkin(d)
			te.apply_to_checkin(d)
		self.assertEqual(d.shift_start, datetime(2026, 11, 9, 9, 30))

	def test_restamp_by_hrms_is_shifted_again(self):
		d = checkin()
		exc = {"name": "Late +30", "start_offset": 30, "end_offset": 30}
		with patch.object(te, "get_time_exception", return_value=exc):
			te.apply_to_checkin(d)
			d.shift_start, d.shift_end = datetime(2026, 11, 9, 9, 0), datetime(2026, 11, 9, 18, 0)  # HRMS stamped base again
			d.shift_actual_start, d.shift_actual_end = datetime(2026, 11, 9, 8, 0), datetime(2026, 11, 9, 19, 0)
			te.apply_to_checkin(d)
		self.assertEqual(d.shift_start, datetime(2026, 11, 9, 9, 30))
		self.assertEqual(d.shift_actual_end, datetime(2026, 11, 9, 19, 30))

	def test_no_exception_leaves_stamps_alone(self):
		d = checkin()
		with patch.object(te, "get_time_exception", return_value=None):
			te.apply_to_checkin(d)
		self.assertEqual(d.shift_start, datetime(2026, 11, 9, 9, 0))
		self.assertIsNone(d.custom_time_exception)

	def test_negative_and_different_offsets(self):
		d = checkin()
		with patch.object(te, "get_time_exception", return_value={"name": "X", "start_offset": -15, "end_offset": 0}):
			te.apply_to_checkin(d)
		self.assertEqual(d.shift_start, datetime(2026, 11, 9, 8, 45))
		self.assertEqual(d.shift_end, datetime(2026, 11, 9, 18, 0))

	def test_checkin_without_shift_is_cleared(self):
		d = Doc(employee="E1", shift=None, custom_time_exception="old")
		te.apply_to_checkin(d)
		self.assertIsNone(d.custom_time_exception)


class TestEffectiveTiming(unittest.TestCase):
	def test_timing_with_exception(self):
		def cached(dt, name, fields):
			if dt == "Shift Type":
				return (timedelta(hours=9), timedelta(hours=18))
			return (30, 30)
		with patch.object(te.frappe, "has_permission", create=True), patch.object(te.frappe, "get_cached_value", create=True, side_effect=cached):
			t = te.get_effective_timing("A", "Late +30")
		self.assertEqual((t["start"], t["end"], t["base_start"], t["base_end"]), ("09:30", "18:30", "09:00", "18:00"))

	def test_overnight_wraps_past_midnight(self):
		def cached(dt, name, fields):
			return (timedelta(hours=22), timedelta(hours=23, minutes=45)) if dt == "Shift Type" else (30, 30)
		with patch.object(te.frappe, "has_permission", create=True), patch.object(te.frappe, "get_cached_value", create=True, side_effect=cached):
			t = te.get_effective_timing("N", "Late +30")
		self.assertEqual((t["start"], t["end"]), ("22:30", "00:15"))


if __name__ == "__main__":
	unittest.main()