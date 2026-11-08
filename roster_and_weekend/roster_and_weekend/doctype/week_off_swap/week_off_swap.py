# Copyright (c) 2026, neotec.ai and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate


class WeekOffSwap(Document):
    def validate(self):
        self._validate_required_fields()
        self._validate_dates()
        self._validate_weekend_policy_consistency()
        self._validate_no_conflicts()

    def _validate_required_fields(self):
        missing = []
        if not self.employee:
            missing.append("Employee")
        if not self.company:
            missing.append("Company")
        if not self.original_week_off_date:
            missing.append("Original Week Off Date")
        if not self.swapped_week_off_date:
            missing.append("Swapped Week Off Date")
        if missing:
            frappe.throw(
                _("Missing required fields: {0}").format(", ".join(missing))
            )

    def _validate_dates(self):
        original = getdate(self.original_week_off_date)
        swapped = getdate(self.swapped_week_off_date)

        if original == swapped:
            frappe.throw(
                _("Original Week Off Date and Swapped Week Off Date cannot be the same.")
            )

    def _validate_weekend_policy_consistency(self):
        original = getdate(self.original_week_off_date)
        swapped = getdate(self.swapped_week_off_date)

        original_is_weekend = _is_weekend_by_policy(self.employee, original)
        swapped_is_weekend = _is_weekend_by_policy(self.employee, swapped)

        if not original_is_weekend:
            frappe.throw(
                _("Original Week Off Date ({0}) is not a Week Off according to the Weekend Policy.")
                .format(frappe.utils.format_date(original))
            )

        if swapped_is_weekend:
            frappe.throw(
                _("Swapped Week Off Date ({0}) is already a Week Off according to the Weekend Policy.")
                .format(frappe.utils.format_date(swapped))
            )

    def _validate_no_conflicts(self):
        original = getdate(self.original_week_off_date)
        swapped = getdate(self.swapped_week_off_date)

        conflicts = frappe.get_all(
            "Week Off Swap",
            filters={
                "employee": self.employee,
                "docstatus": ["!=", 2],
                "name": ["!=", self.name or ""],
                "or_filters": [
                    ["original_week_off_date", "=", original],
                    ["swapped_week_off_date", "=", original],
                    ["original_week_off_date", "=", swapped],
                    ["swapped_week_off_date", "=", swapped],
                ],
            },
            fields=["name", "original_week_off_date", "swapped_week_off_date", "status"],
        )

        if conflicts:
            conflicting_dates = set()
            for row in conflicts:
                conflicting_dates.add(row.original_week_off_date)
                conflicting_dates.add(row.swapped_week_off_date)

            frappe.throw(
                _("A conflicting Week Off Swap already exists for employee {0} involving dates: {1}")
                .format(
                    self.employee,
                    ", ".join(
                        frappe.utils.format_date(d) for d in sorted(conflicting_dates)
                    ),
                )
            )


def _is_weekend_by_policy(employee, date):
    """Compute weekend status directly from Weekend Policy without swap overrides.

    This helper is used during validation to avoid circular dependencies:
    Week Off Swap validation must not go through is_weekend(), because
    is_weekend() would then query Week Off Swap and re-enter validation.
    """
    from roster_and_weekend.roster_and_weekend.weekend_policy import (
        get_employee_weekend_policy,
    )

    date = getdate(date)
    policy = get_employee_weekend_policy(employee, date)
    if not policy:
        return False

    if policy.policy_type == "Fixed":
        for row in policy.weekend_days:
            if row.is_weekend_off and row.day and date.strftime("%A") == row.day:
                return True
        return False

    if policy.policy_type == "Rotational":
        if not policy.cycle_start_date:
            return False

        cycle_start = getdate(policy.cycle_start_date)
        if date < cycle_start:
            return False

        days_since_start = (date - cycle_start).days
        rotation_weeks = policy.rotation_weeks or max(
            (row.week_number for row in policy.rotation_cycle if row.week_number),
            default=1,
        )
        week_number = (days_since_start // 7) % rotation_weeks + 1

        for row in policy.rotation_cycle:
            if row.week_number == week_number and row.is_weekend_off and row.weekend_day:
                if date.strftime("%A") == row.weekend_day:
                    return True
        return False

    return False
