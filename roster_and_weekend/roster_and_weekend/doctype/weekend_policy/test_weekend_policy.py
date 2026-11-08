# Copyright (c) 2026, neotec.ai and contributors
# For license information, please see license.txt

import unittest
from datetime import date
from unittest.mock import patch

import frappe
from frappe.utils import getdate

from roster_and_weekend.roster_and_weekend.weekend_policy import (
	get_employee_weekend_policy,
	is_weekend,
)


def _make_policy(
	name,
	policy_type="Fixed",
	company="Test Company",
	branch=None,
	effective_from="2026-01-01",
	is_active=1,
	weekend_days=None,
	rotation_cycle=None,
	rotation_weeks=1,
	cycle_start_date=None,
):
	policy = frappe._dict(
		{
			"name": name,
			"policy_name": name,
			"policy_type": policy_type,
			"company": company,
			"branch": branch,
			"effective_from": getdate(effective_from),
			"is_active": is_active,
			"weekend_days": weekend_days or [],
			"rotation_cycle": rotation_cycle or [],
			"rotation_weeks": rotation_weeks,
			"cycle_start_date": getdate(cycle_start_date) if cycle_start_date else None,
		}
	)
	return policy


def _make_day(day, is_weekend_off=1):
	return frappe._dict({"day": day, "is_weekend_off": is_weekend_off})


def _make_rotation_row(week_number, weekend_day, is_weekend_off=1):
	return frappe._dict(
		{"week_number": week_number, "weekend_day": weekend_day, "is_weekend_off": is_weekend_off}
	)


class TestWeekendPolicyResolution(unittest.TestCase):
	def setUp(self):
		self.employee = "Test Employee"
		self.employee_doc = frappe._dict(
			{"company": "Test Company", "branch": None, "default_shift": None}
		)
		self.shift_type = "Test Shift"

	def _get_cached_doc_side_effect(self, doctype, name=None):
		if doctype == "Employee":
			return self.employee_doc
		if doctype == "Weekend Policy":
			return self.policy_doc
		return None

	def test_active_fixed_policy_saturday_sunday(self):
		self.policy_doc = _make_policy(
			"POL-SAT-SUN",
			weekend_days=[_make_day("Saturday"), _make_day("Sunday")],
		)
		with patch(
			"roster_and_weekend.roster_and_weekend.weekend_policy._get_shift_type_for_employee_on_date",
			return_value=self.shift_type,
		), patch(
			"frappe.db.get_value",
			return_value="POL-SAT-SUN",
		), patch(
			"frappe.get_cached_doc",
			side_effect=self._get_cached_doc_side_effect,
		):
			self.assertTrue(is_weekend(self.employee, "2026-09-19"))  # Saturday
			self.assertTrue(is_weekend(self.employee, "2026-09-20"))  # Sunday
			self.assertFalse(is_weekend(self.employee, "2026-09-21"))  # Monday

	def test_inactive_fixed_policy_returns_false(self):
		self.policy_doc = _make_policy("POL-INACTIVE", is_active=0)
		with patch(
			"roster_and_weekend.roster_and_weekend.weekend_policy._get_shift_type_for_employee_on_date",
			return_value=self.shift_type,
		), patch(
			"frappe.db.get_value",
			return_value="POL-INACTIVE",
		), patch(
			"frappe.get_cached_doc",
			side_effect=self._get_cached_doc_side_effect,
		):
			self.assertFalse(is_weekend(self.employee, "2026-09-19"))

	def test_policy_before_effective_from_returns_false(self):
		self.policy_doc = _make_policy("POL-FUTURE", effective_from="2026-12-01")
		with patch(
			"roster_and_weekend.roster_and_weekend.weekend_policy._get_shift_type_for_employee_on_date",
			return_value=self.shift_type,
		), patch(
			"frappe.db.get_value",
			return_value="POL-FUTURE",
		), patch(
			"frappe.get_cached_doc",
			side_effect=self._get_cached_doc_side_effect,
		):
			self.assertFalse(is_weekend(self.employee, "2026-06-15"))
			self.assertFalse(is_weekend(self.employee, "2026-11-30"))

	def test_policy_on_effective_from_returns_true(self):
		self.policy_doc = _make_policy(
			"POL-ACTIVE",
			effective_from="2026-07-01",
			weekend_days=[_make_day("Saturday")],
		)
		with patch(
			"roster_and_weekend.roster_and_weekend.weekend_policy._get_shift_type_for_employee_on_date",
			return_value=self.shift_type,
		), patch(
			"frappe.db.get_value",
			return_value="POL-ACTIVE",
		), patch(
			"frappe.get_cached_doc",
			side_effect=self._get_cached_doc_side_effect,
		):
			self.assertFalse(is_weekend(self.employee, "2026-06-30"))
			self.assertTrue(is_weekend(self.employee, "2026-07-04"))  # Saturday

	def test_matching_company_passes(self):
		self.policy_doc = _make_policy("POL-MATCH", company="Test Company")
		with patch(
			"roster_and_weekend.roster_and_weekend.weekend_policy._get_shift_type_for_employee_on_date",
			return_value=self.shift_type,
		), patch(
			"frappe.db.get_value",
			return_value="POL-MATCH",
		), patch(
			"frappe.get_cached_doc",
			side_effect=self._get_cached_doc_side_effect,
		):
			self.assertTrue(get_employee_weekend_policy(self.employee, "2026-09-19") is not None)

	def test_different_company_blocks(self):
		self.policy_doc = _make_policy("POL-OTHER", company="Other Company")
		with patch(
			"roster_and_weekend.roster_and_weekend.weekend_policy._get_shift_type_for_employee_on_date",
			return_value=self.shift_type,
		), patch(
			"frappe.db.get_value",
			return_value="POL-OTHER",
		), patch(
			"frappe.get_cached_doc",
			side_effect=self._get_cached_doc_side_effect,
		):
			self.assertTrue(get_employee_weekend_policy(self.employee, "2026-09-19") is None)

	def test_branch_match_passes(self):
		self.employee_doc = frappe._dict(
			{"company": "Test Company", "branch": "Branch A", "default_shift": None}
		)
		self.policy_doc = _make_policy(
			"POL-BRANCH", company="Test Company", branch="Branch A"
		)
		with patch(
			"roster_and_weekend.roster_and_weekend.weekend_policy._get_shift_type_for_employee_on_date",
			return_value=self.shift_type,
		), patch(
			"frappe.db.get_value",
			return_value="POL-BRANCH",
		), patch(
			"frappe.get_cached_doc",
			side_effect=self._get_cached_doc_side_effect,
		):
			self.assertTrue(get_employee_weekend_policy(self.employee, "2026-09-19") is not None)

	def test_different_branch_blocks(self):
		self.employee_doc = frappe._dict(
			{"company": "Test Company", "branch": "Branch B", "default_shift": None}
		)
		self.policy_doc = _make_policy(
			"POL-BRANCH", company="Test Company", branch="Branch A"
		)
		with patch(
			"roster_and_weekend.roster_and_weekend.weekend_policy._get_shift_type_for_employee_on_date",
			return_value=self.shift_type,
		), patch(
			"frappe.db.get_value",
			return_value="POL-BRANCH",
		), patch(
			"frappe.get_cached_doc",
			side_effect=self._get_cached_doc_side_effect,
		):
			self.assertTrue(get_employee_weekend_policy(self.employee, "2026-09-19") is None)

	def test_empty_policy_branch_allows_any_employee_branch(self):
		self.employee_doc = frappe._dict(
			{"company": "Test Company", "branch": "Branch A", "default_shift": None}
		)
		self.policy_doc = _make_policy(
			"POL-NOBRANCH", company="Test Company", branch=None
		)
		with patch(
			"roster_and_weekend.roster_and_weekend.weekend_policy._get_shift_type_for_employee_on_date",
			return_value=self.shift_type,
		), patch(
			"frappe.db.get_value",
			return_value="POL-NOBRANCH",
		), patch(
			"frappe.get_cached_doc",
			side_effect=self._get_cached_doc_side_effect,
		):
			self.assertTrue(get_employee_weekend_policy(self.employee, "2026-09-19") is not None)

	def test_no_policy_returns_false(self):
		with patch(
			"roster_and_weekend.roster_and_weekend.weekend_policy._get_shift_type_for_employee_on_date",
			return_value=None,
		):
			self.assertFalse(is_weekend(self.employee, "2026-09-19"))

	def test_no_shift_type_returns_false(self):
		with patch(
			"roster_and_weekend.roster_and_weekend.weekend_policy._get_shift_type_for_employee_on_date",
			return_value=None,
		):
			self.assertFalse(is_weekend(self.employee, "2026-09-19"))

	def test_assignment_policy_takes_priority_over_shift_type(self):
		self.policy_doc = _make_policy(
			"POL-ASSIGNMENT",
			weekend_days=[_make_day("Monday"), _make_day("Tuesday")],
		)
		with patch(
			"roster_and_weekend.roster_and_weekend.weekend_policy._get_shift_type_for_employee_on_date",
			return_value=self.shift_type,
		), patch(
			"frappe.get_all",
			return_value=[{"custom_weekend_policy": "POL-ASSIGNMENT"}],
		), patch(
			"frappe.db.get_value",
			return_value="POL-SHIFT-TYPE",
		), patch(
			"frappe.get_cached_doc",
			side_effect=self._get_cached_doc_side_effect,
		):
			self.assertTrue(is_weekend(self.employee, "2026-09-21"))  # Monday
			self.assertTrue(is_weekend(self.employee, "2026-09-22"))  # Tuesday
			self.assertFalse(is_weekend(self.employee, "2026-09-19"))  # Saturday

	def test_assignment_empty_falls_back_to_shift_type(self):
		self.policy_doc = _make_policy(
			"POL-SHIFT-TYPE",
			weekend_days=[_make_day("Monday"), _make_day("Tuesday")],
		)
		with patch(
			"roster_and_weekend.roster_and_weekend.weekend_policy._get_shift_type_for_employee_on_date",
			return_value=self.shift_type,
		), patch(
			"frappe.get_all",
			return_value=[{}],
		), patch(
			"frappe.db.get_value",
			return_value="POL-SHIFT-TYPE",
		), patch(
			"frappe.get_cached_doc",
			side_effect=self._get_cached_doc_side_effect,
		):
			self.assertTrue(is_weekend(self.employee, "2026-09-21"))  # Monday
			self.assertFalse(is_weekend(self.employee, "2026-09-19"))  # Saturday

	def test_both_empty_preserves_no_weekend_behavior(self):
		with patch(
			"roster_and_weekend.roster_and_weekend.weekend_policy._get_shift_type_for_employee_on_date",
			return_value=self.shift_type,
		), patch(
			"frappe.get_all",
			return_value=[{}],
		), patch(
			"frappe.db.get_value",
			return_value=None,
		):
			self.assertFalse(is_weekend(self.employee, "2026-09-19"))
			self.assertFalse(is_weekend(self.employee, "2026-09-21"))

	def test_assignment_policy_date_specific_selection(self):
		self.policy_doc = _make_policy(
			"POL-FRI-SAT",
			weekend_days=[_make_day("Friday"), _make_day("Saturday")],
		)
		with patch(
			"roster_and_weekend.roster_and_weekend.weekend_policy._get_shift_type_for_employee_on_date",
			return_value=self.shift_type,
		), patch(
			"frappe.get_all",
			return_value=[{"custom_weekend_policy": "POL-FRI-SAT"}],
		), patch(
			"frappe.db.get_value",
			return_value=None,
		), patch(
			"frappe.get_cached_doc",
			side_effect=self._get_cached_doc_side_effect,
		):
			self.assertTrue(is_weekend(self.employee, "2026-09-18"))  # Friday
			self.assertTrue(is_weekend(self.employee, "2026-09-19"))  # Saturday
			self.assertFalse(is_weekend(self.employee, "2026-09-21"))  # Monday

	def test_rotational_policy_via_assignment(self):
		self.policy_doc = _make_policy(
			"POL-ROT-ASSIGN",
			policy_type="Rotational",
			cycle_start_date="2026-09-01",
			rotation_weeks=2,
			rotation_cycle=[
				_make_rotation_row(1, "Friday"),
				_make_rotation_row(2, "Monday"),
			],
		)
		with patch(
			"roster_and_weekend.roster_and_weekend.weekend_policy._get_shift_type_for_employee_on_date",
			return_value=self.shift_type,
		), patch(
			"frappe.get_all",
			return_value=[{"custom_weekend_policy": "POL-ROT-ASSIGN"}],
		), patch(
			"frappe.db.get_value",
			return_value=None,
		), patch(
			"frappe.get_cached_doc",
			side_effect=self._get_cached_doc_side_effect,
		):
			self.assertTrue(is_weekend(self.employee, "2026-09-05"))  # Week 1 Friday
			self.assertTrue(is_weekend(self.employee, "2026-09-13"))  # Week 2 Monday
			self.assertFalse(is_weekend(self.employee, "2026-09-06"))  # Week 1 Saturday

	def test_existing_shift_type_policy_unchanged_when_no_assignment(self):
		self.policy_doc = _make_policy(
			"POL-EXISTING",
			weekend_days=[_make_day("Saturday"), _make_day("Sunday")],
		)
		with patch(
			"roster_and_weekend.roster_and_weekend.weekend_policy._get_shift_type_for_employee_on_date",
			return_value=self.shift_type,
		), patch(
			"frappe.get_all",
			return_value=[],
		), patch(
			"frappe.db.get_value",
			return_value="POL-EXISTING",
		), patch(
			"frappe.get_cached_doc",
			side_effect=self._get_cached_doc_side_effect,
		):
			self.assertTrue(is_weekend(self.employee, "2026-09-19"))  # Saturday
			self.assertTrue(is_weekend(self.employee, "2026-09-20"))  # Sunday
			self.assertFalse(is_weekend(self.employee, "2026-09-21"))  # Monday


if __name__ == "__main__":
	unittest.main()
