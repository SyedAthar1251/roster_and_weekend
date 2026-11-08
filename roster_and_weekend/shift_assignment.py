import frappe


def update_employee_shift(doc, method=None):
	"""Runs on every Shift Assignment submit.
	Normal flow is unchanged (default shift follows the assignment, shift location is allowed on the Employee).
	During a roster publish (frappe.flags.roster_sync) it never overwrites an existing default shift, and it only
	saves the Employee when something actually changed, so hundreds of generated assignments do not re-run
	every Employee validation and on_update hook."""
	employee = frappe.get_doc("Employee", doc.employee)
	changed = False
	roster = bool(frappe.flags.get("roster_sync"))
	if (not roster and employee.default_shift != doc.shift_type) or (roster and not employee.default_shift):
		employee.default_shift = doc.shift_type
		changed = True
	# custom_allowed_shift_locations is a CentralHrms field on Employee; skip it when that app is not on the site
	if (doc.shift_location and employee.meta.has_field("custom_allowed_shift_locations")
			and doc.shift_location not in [d.shift_location for d in employee.custom_allowed_shift_locations]):
		employee.append("custom_allowed_shift_locations", {"shift_location": doc.shift_location})
		changed = True
	if changed:
		employee.save(ignore_permissions=True)


@frappe.whitelist()
def check_default_shift(employee, current_doc=None):
	frappe.has_permission("Shift Assignment", "read", throw=True)
	existing = frappe.get_all("Shift Assignment", filters={"employee": employee, "custom_is_default_shift": 1, "docstatus": 1,
		"name": ["!=", current_doc]}, fields=["name", "shift_type", "shift_location"], limit=1)
	return existing[0] if existing else None


@frappe.whitelist()
def replace_default_shift(employee, old_shift):
	frappe.has_permission("Shift Assignment", "write", throw=True)
	frappe.db.set_value("Shift Assignment", old_shift, "custom_is_default_shift", 0)
	return True
