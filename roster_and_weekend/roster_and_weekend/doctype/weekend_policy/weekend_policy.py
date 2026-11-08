# Copyright (c) 2026, neotec.ai and contributors
# For license information, please see license.txt

import json

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_days, getdate, now


class WeekendPolicy(Document):
	def validate(self):
		self._handle_history_and_effective_validation()
		self._validate_required_fields()
		self._validate_policy_type()
		self._validate_fixed_policy()
		self._validate_rotational_policy()

	def _handle_history_and_effective_validation(self):
		if self.is_new() or not self.name:
			return

		original = frappe.get_doc(self.doctype, self.name)
		if not self._is_config_changed(original):
			return

		if getdate(self.effective_from) == getdate(original.effective_from):
			frappe.throw(
				_("Effective From must be changed when the Weekend Policy configuration is modified.")
			)

		self._create_history_entry(original)

	def _is_config_changed(self, original):
		if self.policy_type != original.policy_type:
			return True

		if self.is_active != original.is_active:
			return True

		if self.policy_type == "Fixed":
			return self._fixed_days_changed(original)

		if self.policy_type == "Rotational":
			return self._rotational_config_changed(original)

		return False

	def _fixed_days_changed(self, original):
		current = sorted(
			[
				{"day": d.day, "is_weekend_off": d.is_weekend_off}
				for d in (self.weekend_days or [])
			],
			key=lambda x: x["day"],
		)
		old = sorted(
			[
				{"day": d.day, "is_weekend_off": d.is_weekend_off}
				for d in (original.weekend_days or [])
			],
			key=lambda x: x["day"],
		)
		return current != old

	def _rotational_config_changed(self, original):
		if getdate(self.cycle_start_date) != getdate(original.cycle_start_date):
			return True

		if self.rotation_weeks != original.rotation_weeks:
			return True

		current = sorted(
			[
				{
					"week_number": r.week_number,
					"weekend_day": r.weekend_day,
					"is_weekend_off": r.is_weekend_off,
				}
				for r in (self.rotation_cycle or [])
			],
			key=lambda x: x["week_number"],
		)
		old = sorted(
			[
				{
					"week_number": r.week_number,
					"weekend_day": r.weekend_day,
					"is_weekend_off": r.is_weekend_off,
				}
				for r in (original.rotation_cycle or [])
			],
			key=lambda x: x["week_number"],
		)
		return current != old

	def _create_history_entry(self, original):
		history = self.append("custom_weekend_policy_history", {})
		history.previous_policy_type = original.policy_type
		history.previous_effective_from = original.effective_from
		history.previous_effective_to = add_days(getdate(self.effective_from), -1)
		history.previous_is_active = original.is_active
		history.changed_on = now()
		history.changed_by = frappe.session.user

		if original.policy_type == "Fixed":
			history.previous_weekend_days = ", ".join(
				d.day for d in (original.weekend_days or []) if d.day and d.is_weekend_off
			) or "None"
		else:
			history.previous_rotation_weeks = original.rotation_weeks
			history.previous_cycle_start_date = original.cycle_start_date
			history.previous_rotation_cycle = json.dumps(
				[
					{
						"week_number": r.week_number,
						"weekend_day": r.weekend_day,
						"is_weekend_off": r.is_weekend_off,
					}
					for r in (original.rotation_cycle or [])
				]
			)

	def _validate_required_fields(self):
		if not self.policy_name:
			frappe.throw(_("Policy Name is required."))

		if not self.company:
			frappe.throw(_("Company is required."))

		if not self.effective_from:
			frappe.throw(_("Effective From date is required."))

	def _validate_policy_type(self):
		valid_types = ["Fixed", "Rotational"]
		if self.policy_type not in valid_types:
			frappe.throw(
				_("Invalid Policy Type '{0}'. Must be one of: {1}").format(
					frappe.bold(self.policy_type),
					", ".join(valid_types),
				)
			)

	def _validate_fixed_policy(self):
		if self.policy_type != "Fixed":
			return

		if not self.weekend_days:
			frappe.throw(
				_("Weekend Days must be defined for Fixed policy.")
			)

		seen_days = set()
		for row in self.weekend_days:
			if not row.day:
				frappe.throw(_("Day is required in Weekend Days table."))

			if row.day in seen_days:
				frappe.throw(
					_("Duplicate day '{0}' found in Weekend Days table.").format(
						frappe.bold(row.day)
					)
				)
			seen_days.add(row.day)

	def _validate_rotational_policy(self):
		if self.policy_type != "Rotational":
			return

		if not self.cycle_start_date:
			frappe.throw(
				_("Cycle Start Date is required for Rotational policy.")
			)

		if not self.rotation_cycle:
			frappe.throw(
				_("Rotation Cycle must be defined for Rotational policy.")
			)

		defined_weeks = {row.week_number for row in self.rotation_cycle if row.week_number}
		max_defined_week = max(defined_weeks) if defined_weeks else 0

		if not self.rotation_weeks or self.rotation_weeks < 1:
			self.rotation_weeks = max_defined_week or 1
		else:
			missing_weeks = [w for w in range(1, self.rotation_weeks + 1) if w not in defined_weeks]
			if missing_weeks:
				frappe.throw(
					_("Rotation Cycle is incomplete. Missing entries for Week(s): {0}").format(
						frappe.bold(", ".join(str(w) for w in missing_weeks))
					)
				)

		seen_weeks = set()
		for row in self.rotation_cycle:
			if row.week_number is None:
				frappe.throw(_("Week Number is required in Rotation Cycle table."))

			if row.week_number < 1 or row.week_number > self.rotation_weeks:
				frappe.throw(
					_("Week Number must be between 1 and {0} for Rotational policy.").format(
						frappe.bold(self.rotation_weeks)
					)
				)

			if row.week_number in seen_weeks:
				frappe.throw(
					_("Duplicate entry for Week {0} in Rotation Cycle table.").format(
						frappe.bold(row.week_number)
					)
				)
			seen_weeks.add(row.week_number)

