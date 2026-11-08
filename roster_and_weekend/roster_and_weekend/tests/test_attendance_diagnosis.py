"""Logic tests for the Mark Attendance report (no database needed):
    python -m unittest roster_and_weekend.roster_and_weekend.tests.test_attendance_diagnosis
"""
import sys
import types
import unittest
from datetime import date, datetime, timedelta


def _stub(name, **attrs):
	mod = sys.modules.get(name) or types.ModuleType(name)
	for k, v in attrs.items():
		setattr(mod, k, v)
	sys.modules[name] = mod
	return mod


def _install_stubs():
	if "frappe" in sys.modules and hasattr(sys.modules["frappe"], "get_all"):
		return  # real frappe present (running inside a bench)

	def _getdate(v):
		if isinstance(v, datetime):
			return v.date()
		if isinstance(v, date):
			return v
		return datetime.strptime(str(v)[:10], "%Y-%m-%d").date()

	fu = _stub(
		"frappe.utils",
		cint=lambda v: int(v or 0),
		getdate=_getdate,
		get_datetime=lambda v: v if isinstance(v, datetime) else datetime.strptime(str(v)[:19], "%Y-%m-%d %H:%M:%S"),
		get_time=lambda v: v,
		now_datetime=datetime.now,
		strip_html=lambda s: s,
	)
	fr = _stub(
		"frappe",
		_=lambda s: s,
		whitelist=lambda *a, **k: (lambda f: f),
		utils=fu,
		ValidationError=Exception,
		flags=types.SimpleNamespace(),
	)
	_stub("hrms")
	_stub("hrms.hr")
	_stub("hrms.hr.doctype")
	_stub("hrms.hr.doctype.shift_type")
	_stub("hrms.hr.doctype.shift_type.shift_type", ShiftType=type("ShiftType", (), {}))
	_stub("hrms.hr.doctype.attendance")
	_stub("hrms.hr.doctype.attendance.attendance", mark_attendance=lambda *a, **k: None)
	_stub("hrms.utils", get_date_range=lambda a, b: [])
	_stub("hrms.utils.holiday_list", get_holiday_dates_between=lambda *a, **k: [])
	_stub(
		"roster_and_weekend.roster_and_weekend.weekend_policy",
		get_weekend_dates=lambda *a, **k: [],
		is_weekend=lambda *a, **k: False,
		resolve_weekend_policy=lambda *a, **k: None,
	)
	return fr


_install_stubs()

from roster_and_weekend.overrides.shift_type import CustomShiftType  # noqa: E402
from roster_and_weekend.roster_and_weekend import attendance_diagnosis as ad  # noqa: E402

D = [date(2026, 10, 1), date(2026, 10, 2), date(2026, 10, 5), date(2026, 10, 6)]
LAST_SYNC = datetime(2026, 11, 1, 19, 1)


class FakeShift:
	"""Borrows the real decision code from CustomShiftType and fakes only the data lookups."""

	name = "Shift A"
	_collect_report = False
	_note = CustomShiftType._note

	def __init__(self, roster=False, scheduled=(), assigned=(), entries=None, existing=None):
		self._roster, self._scheduled, self._assigned = roster, set(scheduled), set(assigned)
		self._entries, self._existing = entries or {}, existing or {}

	def get_dates_for_attendance(self, employee):
		return list(D)

	def _is_roster_managed_employee(self, employee):
		return self._roster

	def _is_scheduled_for_shift(self, employee, d):
		return d in self._scheduled

	def _has_active_assignment_for_date(self, employee, d):
		return d in self._assigned

	def _get_published_roster_entry(self, employee, d):
		return self._entries.get(d)

	def _existing_attendance(self, employee, d):
		return self._existing.get(d)


def decisions(shift):
	return [(d.day, dec) for d, dec, _i in CustomShiftType._evaluate_dates(shift, "EMP")]


class TestDecisions(unittest.TestCase):
	def test_plain_employee_mark_conflict_and_not_scheduled(self):
		other = {"name": "ATT-1", "status": "Absent", "shift": "Afternoon", "docstatus": 1}
		s = FakeShift(scheduled=[D[0], D[2], D[3]], existing={D[2]: other})
		self.assertEqual(decisions(s), [(1, "mark"), (2, "not_scheduled"), (5, "conflict"), (6, "mark")])

	def test_roster_off_day_is_not_absent(self):
		entry = types.SimpleNamespace(entry_type="Off", shift_type=None)
		s = FakeShift(roster=True, assigned=[D[0], D[1], D[3]], entries={D[1]: entry})
		self.assertEqual(
			decisions(s), [(1, "mark"), (2, "roster_not_work"), (5, "not_scheduled"), (6, "mark")]
		)

	def test_roster_work_on_other_shift_is_not_marked_here(self):
		entry = types.SimpleNamespace(entry_type="Work", shift_type="Shift B")
		s = FakeShift(roster=True, assigned=D, entries={D[0]: entry})
		self.assertEqual(decisions(s)[0], (1, "roster_not_work"))


class TestNotes(unittest.TestCase):
	def test_notes_only_collected_when_enabled(self):
		s = FakeShift()
		s._note("weekend", "E1", D[0])
		self.assertFalse(hasattr(s, "_skip_report"))
		s._collect_report = True
		s._note("weekend", "E1", D[0])
		s._note("weekend", "E2", D[1])
		row = s._skip_report["weekend"]
		self.assertEqual((row["count"], len(row["employees"]), row["samples"]), (2, 2, ["2026-10-01", "2026-10-02"]))


class TestCheckinClassification(unittest.TestCase):
	def row(self, **kw):
		base = dict(shift="Shift A", skip_auto_attendance=0, offshift=0, shift_actual_end=datetime(2026, 10, 1, 19, 0))
		base.update(kw)
		return base

	def test_codes(self):
		c = lambda r, covered=True: ad.classify_checkin(r, "Shift A", LAST_SYNC, covered)
		self.assertEqual(c(self.row(skip_auto_attendance=1)), "checkin_skipped")
		self.assertEqual(c(self.row(offshift=1)), "checkin_offshift")
		self.assertEqual(c(self.row(shift="Other")), "checkin_other_shift")
		self.assertEqual(c(self.row(shift=None)), "checkin_no_shift")
		self.assertEqual(c(self.row(shift_actual_end=datetime(2026, 11, 2, 19, 0))), "checkin_not_closed")
		self.assertIsNone(c(self.row()))

	def test_overlapping_assignment_is_not_a_relink_case(self):
		r = self.row(shift="Other")
		self.assertEqual(
			ad.classify_checkin(r, "Shift A", LAST_SYNC, True, overlap={"shift": "Other", "name": "SA-1"}),
			"checkin_overlap",
		)

	def test_multiple_assignments_setting_blocks_relink(self):
		r = self.row(shift="Other")
		self.assertEqual(ad.classify_checkin(r, "Shift A", LAST_SYNC, True, multiple_allowed=True), "checkin_relink_blocked")

	def test_other_shift_ignored_when_assignment_does_not_cover_date(self):
		self.assertIsNone(ad.classify_checkin(self.row(shift="Other"), "Shift A", LAST_SYNC, False))


class TestCancelRules(unittest.TestCase):
	def test_only_submitted_absent_of_another_shift_is_cancelable(self):
		ok = {"status": "Absent", "docstatus": 1, "shift": "Afternoon"}
		self.assertTrue(ad._is_cancelable(ok, "Shift A"))
		for bad in (
			dict(ok, status="Present"),
			dict(ok, status="On Leave"),
			dict(ok, docstatus=0),
			dict(ok, shift=None),
			dict(ok, shift="Shift A"),
		):
			self.assertFalse(ad._is_cancelable(bad, "Shift A"), bad)


if __name__ == "__main__":
	unittest.main()