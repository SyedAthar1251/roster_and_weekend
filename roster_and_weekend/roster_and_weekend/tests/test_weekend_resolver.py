"""Pure-logic tests for the weekend resolver. frappe is stubbed, so this runs without a bench:
    python -m unittest roster_and_weekend.roster_and_weekend.tests.test_weekend_resolver
"""
import sys
import types
import unittest
from datetime import date, datetime

fr = types.ModuleType("frappe")
fu = types.ModuleType("frappe.utils")
fu.getdate = lambda v: v if isinstance(v, date) and not isinstance(v, datetime) else (v.date() if isinstance(v, datetime) else datetime.strptime(str(v)[:10], "%Y-%m-%d").date())
fr.utils = fu
fr.local = types.SimpleNamespace()
sys.modules.setdefault("frappe", fr)
sys.modules.setdefault("frappe.utils", fu)

from roster_and_weekend.roster_and_weekend import weekend_policy as wp  # noqa: E402


def row(**k):
	return types.SimpleNamespace(**k)


class Policy(dict):
	__getattr__ = dict.get


def fixed(days, eff="2026-01-01", active=1, hist=None):
	return Policy(policy_type="Fixed", effective_from=eff, is_active=active, weekend_days=[row(day=d, is_weekend_off=1) for d in days],
		custom_weekend_policy_history=hist or [], rotation_cycle=[])


def rotational(start, cycle, weeks, eff="2026-01-01"):
	return Policy(policy_type="Rotational", effective_from=eff, is_active=1, cycle_start_date=start, rotation_weeks=weeks,
		rotation_cycle=[row(week_number=w, weekend_day=d, is_weekend_off=1) for w, d in cycle], weekend_days=[], custom_weekend_policy_history=[])


class TestResolver(unittest.TestCase):
	def hit(self, policy, d):
		return wp._rule_hit(wp._rule_for(policy, d), d)

	def test_fixed(self):
		p = fixed(["Friday", "Saturday"])
		self.assertTrue(self.hit(p, date(2026, 10, 9)))   # Friday
		self.assertFalse(self.hit(p, date(2026, 10, 11)))  # Sunday

	def test_inactive_policy_is_never_weekend(self):
		self.assertFalse(self.hit(fixed(["Friday"], active=0), date(2026, 10, 9)))

	def test_rotational_week_counts_from_cycle_start(self):
		start = date(2026, 10, 12)  # Monday
		p = rotational(start, [(1, "Monday"), (2, "Wednesday")], 2)
		self.assertTrue(self.hit(p, date(2026, 10, 12)))    # week 1 Monday
		self.assertFalse(self.hit(p, date(2026, 10, 14)))   # week 1 Wednesday
		self.assertTrue(self.hit(p, date(2026, 10, 21)))    # week 2 Wednesday
		self.assertTrue(self.hit(p, date(2026, 10, 26)))    # week 3 -> week 1 Monday
		self.assertFalse(self.hit(p, date(2026, 10, 11)))   # before cycle start

	def test_past_dates_use_history_after_policy_edit(self):
		hist = [row(previous_policy_type="Fixed", previous_effective_from="2026-01-01", previous_effective_to="2026-06-30",
			previous_is_active=1, previous_weekend_days="Friday, Saturday")]
		p = fixed(["Saturday", "Sunday"], eff="2026-07-01", hist=hist)
		self.assertTrue(self.hit(p, date(2026, 3, 6)))    # old Friday still weekend
		self.assertFalse(self.hit(p, date(2026, 3, 8)))   # old Sunday was a working day
		self.assertTrue(self.hit(p, date(2026, 10, 11)))  # new Sunday weekend
		self.assertFalse(self.hit(p, date(2026, 10, 9)))  # new Friday works

	def test_date_before_any_history_is_not_weekend(self):
		p = fixed(["Friday"], eff="2026-07-01")
		self.assertFalse(self.hit(p, date(2026, 3, 6)))

	def test_history_rotational_snapshot(self):
		hist = [row(previous_policy_type="Rotational", previous_effective_from="2026-01-01", previous_effective_to="2026-06-30", previous_is_active=1,
			previous_rotation_weeks=1, previous_cycle_start_date="2026-01-05",
			previous_rotation_cycle='[{"week_number":1,"weekend_day":"Tuesday","is_weekend_off":1}]')]
		p = fixed(["Friday"], eff="2026-07-01", hist=hist)
		self.assertTrue(self.hit(p, date(2026, 2, 3)))   # a Tuesday
		self.assertFalse(self.hit(p, date(2026, 2, 4)))


if __name__ == "__main__":
	unittest.main()
