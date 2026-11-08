# Copyright (c) 2026, neotec.ai and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import getdate, date_diff, flt, cint

_original_get_number_of_leave_days = None


@frappe.whitelist()
def get_number_of_leave_days(employee, leave_type, from_date, to_date, half_day=None, half_day_date=None, holiday_list=None):
	"""Extended get_number_of_leave_days that excludes Weekend Policy days"""
	global _original_get_number_of_leave_days
	from roster_and_weekend.roster_and_weekend.weekend_policy import get_weekend_dates
	from erpnext.setup.doctype.employee.employee import get_holiday_list_for_employee

	from_date = getdate(from_date)
	to_date = getdate(to_date)

	leave_type_doc = frappe.get_cached_doc("Leave Type", leave_type)

	if leave_type_doc.include_holiday:
		if _original_get_number_of_leave_days:
			return _original_get_number_of_leave_days(
				employee, leave_type, from_date, to_date, half_day, half_day_date, holiday_list
			)
		return 0

	number_of_days = 0
	if cint(half_day) == 1:
		if from_date == to_date:
			number_of_days = 0.5
		elif half_day_date and from_date <= getdate(half_day_date) <= to_date:
			number_of_days = date_diff(to_date, from_date) + 0.5
		else:
			number_of_days = date_diff(to_date, from_date) + 1
	else:
		number_of_days = date_diff(to_date, from_date) + 1

	hl_name = holiday_list or get_holiday_list_for_employee(employee)
	public_holidays = set()
	weekly_offs_from_hl = set()

	if hl_name:
		holidays = frappe.get_all(
			"Holiday",
			filters={
				"parent": hl_name,
				"holiday_date": ["between", [from_date, to_date]]
			},
			fields=["holiday_date", "weekly_off"]
		)
		for h in holidays:
			d = str(h.holiday_date)
			if h.weekly_off:
				weekly_offs_from_hl.add(d)
			else:
				public_holidays.add(d)

	weekend_dates = set(get_weekend_dates(employee, from_date, to_date))

	if getattr(leave_type_doc, "custom_include_weekly_offs_as_leave_copy", False):
		excluded = public_holidays
	else:
		excluded = public_holidays | weekend_dates

	excluded_count = len(excluded)
	if cint(half_day) == 1 and half_day_date:
		hd_date = str(getdate(half_day_date))
		if hd_date in excluded:
			excluded_count -= 0.5

	result = flt(number_of_days) - flt(excluded_count)
	return max(result, 0)


def patch_get_number_of_leave_days():
	"""Monkey-patch core get_number_of_leave_days to use Weekend Policy"""
	global _original_get_number_of_leave_days
	import importlib
	core_module = importlib.import_module(
		"hrms.hr.doctype.leave_application.leave_application"
	)
	_original_get_number_of_leave_days = core_module.get_number_of_leave_days
	core_module.get_number_of_leave_days = get_number_of_leave_days
