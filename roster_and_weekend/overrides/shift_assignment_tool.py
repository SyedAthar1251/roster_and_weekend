import frappe
from frappe import _
from frappe.utils import get_link_to_form
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


def patched_bulk_assign(self, employees: list):
	success, failure = [], []
	count = 0
	savepoint = "before_assignment"
	if self.action == "Assign Shift":
		doctype = "Shift Assignment"
		event = "completed_bulk_shift_assignment"
	else:
		doctype = "Shift Schedule Assignment"
		event = "completed_bulk_shift_schedule_assignment"

	for d in employees:
		try:
			frappe.db.savepoint(savepoint)
			assignment = (
				self.create_shift_schedule_assignment(d)
				if self.action == "Assign Shift Schedule"
				else patched_create_shift_assignment(
					d,
					self.company,
					self.shift_type,
					self.start_date,
					self.end_date,
					self.status,
					self.shift_location,
					custom_weekend_policy=self.custom_weekend_policy,
					custom_time_exception=self.custom_time_exception,
				)
			)
			if self.action == "Assign Shift Schedule":
				assignment.create_shifts(self.start_date, self.end_date)

		except Exception:
			frappe.db.rollback(save_point=savepoint)
			frappe.log_error(
				f"Bulk Assignment - {doctype} failed for employee {d}.",
				reference_doctype=doctype,
			)
			failure.append(d)
		else:
			success.append({"doc": get_link_to_form(doctype, assignment.name), "employee": d})

		count += 1
		frappe.publish_progress(count * 100 / len(employees), title=_("Creating {0}...").format(doctype))

	frappe.clear_messages()
	frappe.publish_realtime(
		event,
		message={"success": success, "failure": failure},
		doctype="Shift Assignment Tool",
		after_commit=True,
	)


def patch_shift_assignment_tool():
	import hrms.hr.doctype.shift_assignment_tool.shift_assignment_tool as tool_module
	tool_module.create_shift_assignment = patched_create_shift_assignment
	tool_module.ShiftAssignmentTool._bulk_assign = patched_bulk_assign
