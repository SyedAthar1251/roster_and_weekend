import frappe
from hrms.hr.doctype.shift_assignment.shift_assignment import ShiftAssignment


def patched_create_shift_assignment(
	employee, company, shift_type, start_date, end_date, status, shift_location=None,
	shift_schedule_assignment=None, custom_weekend_policy=None, custom_time_exception=None
):
	assignment = frappe.new_doc("Shift Assignment")
	assignment.employee = employee
	assignment.company = company
	assignment.shift_type = shift_type
	assignment.start_date = start_date
	assignment.end_date = end_date
	assignment.status = status
	assignment.shift_location = shift_location
	assignment.shift_schedule_assignment = shift_schedule_assignment
	assignment.custom_weekend_policy = custom_weekend_policy
	# explicit value wins; otherwise inherit the one set on the Shift Schedule Assignment that generates this shift
	if not custom_time_exception and shift_schedule_assignment:
		custom_time_exception = frappe.db.get_value(
			"Shift Schedule Assignment", shift_schedule_assignment, "custom_time_exception"
		)
	assignment.custom_time_exception = custom_time_exception or None
	assignment.save()
	assignment.submit()
	return assignment


def patch_shift_assignment_tool():
	import hrms.hr.doctype.shift_assignment_tool.shift_assignment_tool as tool_module
	tool_module.create_shift_assignment = patched_create_shift_assignment