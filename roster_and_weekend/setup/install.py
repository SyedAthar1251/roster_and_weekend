"""Install / migrate setup for Roster And Weekend.

Everything here is idempotent: it runs after install AND after every `bench migrate`, so a missing role or
custom field is always put back. (Frappe marks patches.txt entries as done on a fresh install without running
them, which is why this is a hook and not a patch.)

Custom fields on stock HRMS doctypes:
  Shift Assignment           roster_plan, custom_weekend_policy, custom_is_default_shift
  Shift Type                 custom_weekend_policy
  Shift Schedule Assignment  custom_weekend_policy
The field names are the same ones CentralHrms already uses, so existing data keeps working.
"""
import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

ROLES = ("Roster Manager", "Roster Employee")

CUSTOM_FIELDS = {
	"Shift Assignment": [
		dict(fieldname="roster_plan", label="Roster Plan", fieldtype="Link", options="Roster Plan",
			read_only=1, hidden=1, insert_after="status"),
		dict(fieldname="custom_weekend_policy", label="Weekend Policy", fieldtype="Link", options="Weekend Policy",
			insert_after="shift_type"),
		dict(fieldname="custom_is_default_shift", label="Is Default Shift", fieldtype="Check",
			in_list_view=1, in_standard_filter=1, insert_after="shift_type"),
	],
	"Shift Type": [
		dict(fieldname="custom_weekend_policy", label="Weekend Policy", fieldtype="Link", options="Weekend Policy",
			description="Weekend Policy controls the weekly off days for employees using this Shift Type.",
			insert_after="holiday_list"),
	],
	"Shift Schedule Assignment": [
		dict(fieldname="custom_weekend_policy", label="Weekend Policy", fieldtype="Link", options="Weekend Policy",
			insert_after="shift_status"),
	],
}


def create_roles():
	for role in ROLES:
		if not frappe.db.exists("Role", role):
			frappe.get_doc({"doctype": "Role", "role_name": role, "desk_access": 1}).insert(ignore_permissions=True)


def create_fields():
	create_custom_fields(CUSTOM_FIELDS, ignore_validate=True)


def setup():
	create_roles()
	create_fields()


def after_install():
	setup()


def after_migrate():
	setup()
