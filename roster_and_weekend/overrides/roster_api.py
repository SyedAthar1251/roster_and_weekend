import frappe
from roster_and_weekend.roster_and_weekend.weekend_policy import get_weekend_dates
from erpnext.setup.doctype.employee.employee import get_holiday_list_for_employee


def patched_get_holidays(month_start, month_end, employee_filters):
	holidays = {}
	holiday_lists = {}

	for employee in frappe.get_list("Employee", filters=employee_filters, pluck="name"):
		emp_events = []

		holiday_list = get_holiday_list_for_employee(employee, raise_exception=False)
		if holiday_list:
			if holiday_list not in holiday_lists:
				holiday_lists[holiday_list] = frappe.get_all(
					"Holiday",
					filters={"parent": holiday_list, "holiday_date": ["between", [month_start, month_end]]},
					fields=["name as holiday", "holiday_date", "description", "weekly_off"],
				)
			emp_events = holiday_lists[holiday_list].copy()

		weekend_dates = get_weekend_dates(employee, month_start, month_end)
		weekend_set = set(weekend_dates)

		if weekend_set:
			emp_events = [h for h in emp_events if not h.get("weekly_off")]

		existing_dates = {h["holiday_date"] for h in emp_events}
		for date_str in weekend_dates:
			if date_str not in existing_dates:
				emp_events.append({
					"holiday": "Weekend Policy",
					"holiday_date": date_str,
					"description": "Weekend Policy",
					"weekly_off": 1,
				})

		holidays[employee] = emp_events

	return holidays


@frappe.whitelist()
def patched_insert_shift(
	employee, company, shift_type, start_date, end_date, status, shift_location=None, custom_weekend_policy=None,
	custom_time_exception=None
):
	from frappe.utils import add_days
	from hrms.hr.doctype.shift_assignment_tool.shift_assignment_tool import create_shift_assignment

	filters = {
		"doctype": "Shift Assignment",
		"employee": employee,
		"company": company,
		"shift_type": shift_type,
		"status": status,
		"shift_location": shift_location,
		# only join with a neighbouring assignment that has the same Time Exception (or none)
		"custom_time_exception": custom_time_exception or ["is", "not set"],
	}
	prev_shift = frappe.db.exists(dict({"end_date": add_days(start_date, -1)}, **filters))
	next_shift = (
		frappe.db.exists(dict({"start_date": add_days(end_date, 1)}, **filters)) if end_date else None
	)

	if prev_shift:
		if next_shift:
			end_date = frappe.db.get_value("Shift Assignment", next_shift, "end_date")
			frappe.db.set_value("Shift Assignment", next_shift, "docstatus", 2)
			frappe.delete_doc("Shift Assignment", next_shift)
		frappe.db.set_value("Shift Assignment", prev_shift, "end_date", end_date or None)

	elif next_shift:
		frappe.db.set_value("Shift Assignment", next_shift, "start_date", start_date)

	else:
		create_shift_assignment(
			employee, company, shift_type, start_date, end_date, status, shift_location,
			custom_weekend_policy=custom_weekend_policy, custom_time_exception=custom_time_exception
		)


@frappe.whitelist()
def patched_create_shift_schedule_assignment(
	employee, company, shift_type, status, start_date, end_date, repeat_on_days, frequency,
	shift_location=None, custom_weekend_policy=None, custom_time_exception=None
):
	from hrms.hr.doctype.shift_assignment_tool.shift_assignment_tool import get_or_insert_shift_schedule
	from frappe.utils import date_diff

	shift_schedule = get_or_insert_shift_schedule(shift_type, frequency, repeat_on_days)
	shift_schedule_assignment = frappe.get_doc(
		{
			"doctype": "Shift Schedule Assignment",
			"shift_schedule": shift_schedule,
			"employee": employee,
			"company": company,
			"shift_status": status,
			"shift_location": shift_location,
			"custom_weekend_policy": custom_weekend_policy,
			"custom_time_exception": custom_time_exception,
			"enabled": 0 if end_date else 1,
		}
	).insert()

	if not end_date or date_diff(end_date, start_date) <= 90:
		return shift_schedule_assignment.create_shifts(start_date, end_date)

	frappe.enqueue(
		shift_schedule_assignment.create_shifts, timeout=4500, start_date=start_date, end_date=end_date
	)


def patch_roster_api():
	import hrms.api.roster as roster_module
	roster_module.get_holidays = patched_get_holidays
	roster_module.insert_shift = patched_insert_shift
	roster_module.create_shift_schedule_assignment = patched_create_shift_schedule_assignment