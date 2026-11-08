# Copyright (c) 2026, neotec.ai and contributors
# For license information, please see license.txt

import unittest
from datetime import date
from unittest.mock import patch, MagicMock

import frappe
from frappe.utils import getdate

from roster_and_weekend.roster_and_weekend.weekend_policy import is_weekend
from roster_and_weekend.roster_and_weekend.doctype.week_off_swap.week_off_swap import WeekOffSwap


POLICY_FIXED_SAT_SUN = frappe._dict({
    "name": "POL-SAT-SUN",
    "policy_name": "POL-SAT-SUN",
    "policy_type": "Fixed",
    "company": "Test Company",
    "branch": None,
    "effective_from": getdate("2026-01-01"),
    "is_active": 1,
    "weekend_days": [
        frappe._dict({"day": "Saturday", "is_weekend_off": 1}),
        frappe._dict({"day": "Sunday", "is_weekend_off": 1}),
    ],
    "rotation_cycle": [],
    "rotation_weeks": 1,
    "cycle_start_date": None,
})

POLICY_ROT_MON = frappe._dict({
    "name": "POL-ROT-MON",
    "policy_name": "POL-ROT-MON",
    "policy_type": "Rotational",
    "company": "Test Company",
    "branch": None,
    "effective_from": getdate("2026-01-01"),
    "is_active": 1,
    "weekend_days": [],
    "rotation_cycle": [
        frappe._dict({"week_number": 1, "weekend_day": "Monday", "is_weekend_off": 1}),
    ],
    "rotation_weeks": 2,
    "cycle_start_date": getdate("2026-09-01"),
})


def _make_swap_doc(**kwargs):
    defaults = {
        "name": kwargs.get("name", "WOS-.26.-.00001"),
        "employee": kwargs.get("employee", "Test Employee"),
        "company": kwargs.get("company", "Test Company"),
        "original_week_off_date": kwargs.get("original_week_off_date", "2026-09-21"),
        "swapped_week_off_date": kwargs.get("swapped_week_off_date", "2026-09-25"),
        "reason": kwargs.get("reason", ""),
        "status": kwargs.get("status", "Draft"),
        "docstatus": kwargs.get("docstatus", 1),
    }
    return frappe._dict(defaults)


class TestWeekOffSwapValidation(unittest.TestCase):
    def setUp(self):
        self.employee = "Test Employee"
        self.company = "Test Company"

    def _make_doc(self, **kwargs):
        doc = MagicMock()
        doc.employee = kwargs.get("employee", self.employee)
        doc.company = kwargs.get("company", self.company)
        doc.original_week_off_date = kwargs.get("original_week_off_date", "2026-09-21")
        doc.swapped_week_off_date = kwargs.get("swapped_week_off_date", "2026-09-25")
        doc.reason = kwargs.get("reason", "")
        doc.status = kwargs.get("status", "Draft")
        doc.name = kwargs.get("name", "WOS-.26.-.00001")
        doc.docstatus = kwargs.get("docstatus", 1)
        return doc

    def test_same_date_validation_fails(self):
        doc = self._make_doc(
            original_week_off_date="2026-09-21",
            swapped_week_off_date="2026-09-21",
        )
        with patch("frappe.throw") as mock_throw:
            WeekOffSwap._validate_dates(doc)
            mock_throw.assert_called()

    def test_original_must_be_weekend(self):
        doc = self._make_doc(
            original_week_off_date="2026-09-22",
            swapped_week_off_date="2026-09-25",
        )
        with patch(
            "roster_and_weekend.roster_and_weekend.doctype.week_off_swap.week_off_swap._is_weekend_by_policy",
            side_effect=lambda emp, dt: dt == getdate("2026-09-21"),
        ), patch("frappe.throw") as mock_throw:
            WeekOffSwap._validate_weekend_policy_consistency(doc)
            mock_throw.assert_called()

    def test_swapped_must_not_be_weekend(self):
        doc = self._make_doc(
            original_week_off_date="2026-09-21",
            swapped_week_off_date="2026-09-19",
        )
        with patch(
            "roster_and_weekend.roster_and_weekend.doctype.week_off_swap.week_off_swap._is_weekend_by_policy",
            side_effect=lambda emp, dt: dt in [getdate("2026-09-19"), getdate("2026-09-20")],
        ), patch("frappe.throw") as mock_throw:
            WeekOffSwap._validate_weekend_policy_consistency(doc)
            mock_throw.assert_called()

    def test_approved_swap_passes_validation(self):
        doc = self._make_doc(
            original_week_off_date="2026-09-21",
            swapped_week_off_date="2026-09-25",
        )
        with patch(
            "roster_and_weekend.roster_and_weekend.doctype.week_off_swap.week_off_swap._is_weekend_by_policy",
            side_effect=lambda emp, dt: dt == getdate("2026-09-21"),
        ), patch(
            "roster_and_weekend.roster_and_weekend.doctype.week_off_swap.week_off_swap.frappe.get_all",
            return_value=[],
        ):
            WeekOffSwap._validate_weekend_policy_consistency(doc)
            WeekOffSwap._validate_no_conflicts(doc)

    def test_conflicting_swap_validation_fails(self):
        doc = self._make_doc(
            original_week_off_date="2026-09-21",
            swapped_week_off_date="2026-09-25",
        )
        with patch(
            "roster_and_weekend.roster_and_weekend.doctype.week_off_swap.week_off_swap._is_weekend_by_policy",
            side_effect=lambda emp, dt: dt == getdate("2026-09-21"),
        ), patch(
            "roster_and_weekend.roster_and_weekend.doctype.week_off_swap.week_off_swap.frappe.get_all",
            return_value=[
                frappe._dict({
                    "name": "WOS-.26.-.00002",
                    "original_week_off_date": "2026-09-21",
                    "swapped_week_off_date": "2026-09-25",
                    "status": "Pending Approval",
                })
            ],
        ):
            with self.assertRaises(frappe.ValidationError):
                WeekOffSwap._validate_no_conflicts(doc)


class TestWeekOffSwapWeekendOverride(unittest.TestCase):
    def setUp(self):
        self.employee = "Test Employee"

    def _policy_side_effect(self, doctype, name=None):
        if doctype == "Employee":
            return frappe._dict({"company": "Test Company", "branch": None, "default_shift": None})
        if doctype == "Weekend Policy":
            return POLICY_FIXED_SAT_SUN
        return None

    def _shift_side_effect(self, employee, date):
        return "Test Shift"

    def test_approved_swap_original_becomes_working(self):
        saturday = "2026-09-19"
        swap = _make_swap_doc(
            original_week_off_date=saturday,
            swapped_week_off_date="2026-09-22",
            status="Approved",
            docstatus=1,
        )
        with patch(
            "roster_and_weekend.roster_and_weekend.weekend_policy._get_shift_type_for_employee_on_date",
            side_effect=self._shift_side_effect,
        ), patch(
            "frappe.db.get_value",
            return_value="POL-SAT-SUN",
        ), patch(
            "frappe.get_cached_doc",
            side_effect=self._policy_side_effect,
        ), patch(
            "roster_and_weekend.roster_and_weekend.weekend_policy._get_approved_weekend_swap",
            return_value=swap,
        ):
            self.assertFalse(is_weekend(self.employee, saturday))

    def test_approved_swap_swapped_becomes_weekend(self):
        tuesday = "2026-09-22"
        swap = _make_swap_doc(
            original_week_off_date="2026-09-19",
            swapped_week_off_date=tuesday,
            status="Approved",
            docstatus=1,
        )
        with patch(
            "roster_and_weekend.roster_and_weekend.weekend_policy._get_shift_type_for_employee_on_date",
            side_effect=self._shift_side_effect,
        ), patch(
            "frappe.db.get_value",
            return_value="POL-SAT-SUN",
        ), patch(
            "frappe.get_cached_doc",
            side_effect=self._policy_side_effect,
        ), patch(
            "roster_and_weekend.roster_and_weekend.weekend_policy._get_approved_weekend_swap",
            return_value=swap,
        ):
            self.assertTrue(is_weekend(self.employee, tuesday))

    def test_pending_swap_has_no_effect(self):
        saturday = "2026-09-19"
        swap = _make_swap_doc(
            original_week_off_date=saturday,
            swapped_week_off_date="2026-09-22",
            status="Pending Approval",
            docstatus=1,
        )
        with patch(
            "roster_and_weekend.roster_and_weekend.weekend_policy._get_shift_type_for_employee_on_date",
            side_effect=self._shift_side_effect,
        ), patch(
            "frappe.db.get_value",
            return_value="POL-SAT-SUN",
        ), patch(
            "frappe.get_cached_doc",
            side_effect=self._policy_side_effect,
        ), patch(
            "roster_and_weekend.roster_and_weekend.weekend_policy._get_approved_weekend_swap",
            return_value=None,
        ):
            self.assertTrue(is_weekend(self.employee, saturday))

    def test_rejected_swap_has_no_effect(self):
        saturday = "2026-09-19"
        swap = _make_swap_doc(
            original_week_off_date=saturday,
            swapped_week_off_date="2026-09-22",
            status="Rejected",
            docstatus=1,
        )
        with patch(
            "roster_and_weekend.roster_and_weekend.weekend_policy._get_shift_type_for_employee_on_date",
            side_effect=self._shift_side_effect,
        ), patch(
            "frappe.db.get_value",
            return_value="POL-SAT-SUN",
        ), patch(
            "frappe.get_cached_doc",
            side_effect=self._policy_side_effect,
        ), patch(
            "roster_and_weekend.roster_and_weekend.weekend_policy._get_approved_weekend_swap",
            return_value=None,
        ):
            self.assertTrue(is_weekend(self.employee, saturday))

    def test_no_swap_preserves_existing_fixed_policy(self):
        saturday = "2026-09-19"
        with patch(
            "roster_and_weekend.roster_and_weekend.weekend_policy._get_shift_type_for_employee_on_date",
            side_effect=self._shift_side_effect,
        ), patch(
            "frappe.db.get_value",
            return_value="POL-SAT-SUN",
        ), patch(
            "frappe.get_cached_doc",
            side_effect=self._policy_side_effect,
        ), patch(
            "roster_and_weekend.roster_and_weekend.weekend_policy._get_approved_weekend_swap",
            return_value=None,
        ):
            self.assertTrue(is_weekend(self.employee, saturday))
            self.assertFalse(is_weekend(self.employee, "2026-09-21"))  # Monday

    def test_no_swap_preserves_existing_rotational_policy(self):
        monday = "2026-09-21"
        with patch(
            "roster_and_weekend.roster_and_weekend.weekend_policy._get_shift_type_for_employee_on_date",
            side_effect=self._shift_side_effect,
        ), patch(
            "frappe.db.get_value",
            return_value="POL-ROT-MON",
        ), patch(
            "frappe.get_cached_doc",
            side_effect=lambda doctype, name=None: POLICY_ROT_MON if doctype == "Weekend Policy" else frappe._dict({"company": "Test Company", "branch": None, "default_shift": None}),
        ), patch(
            "roster_and_weekend.roster_and_weekend.weekend_policy._get_approved_weekend_swap",
            return_value=None,
        ):
            self.assertTrue(is_weekend(self.employee, monday))

    def test_swap_does_not_modify_weekend_policy_doc(self):
        original_policy_name = "POL-SAT-SUN"
        with patch(
            "roster_and_weekend.roster_and_weekend.weekend_policy._get_shift_type_for_employee_on_date",
            side_effect=self._shift_side_effect,
        ), patch(
            "frappe.db.get_value",
            return_value=original_policy_name,
        ), patch(
            "frappe.get_cached_doc",
            side_effect=self._policy_side_effect,
        ):
            policy = frappe.get_cached_doc("Weekend Policy", original_policy_name)
            original_days = [dict(row) for row in policy.weekend_days]
            is_weekend(self.employee, "2026-09-19")
            policy = frappe.get_cached_doc("Weekend Policy", original_policy_name)
            self.assertEqual(original_days, [dict(row) for row in policy.weekend_days])


if __name__ == "__main__":
    unittest.main()
