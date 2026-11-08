# roster_and_weekend/overrides/shift_assignment_override.py
import frappe
from hrms.hr.doctype.shift_assignment.shift_assignment import ShiftAssignment

def _has_allowed_locations():
    return bool(frappe.db.exists("DocType", "Allowed Shift Locations")) and frappe.get_meta("Employee").has_field(
        "custom_allowed_shift_locations"
    )


class CustomShiftAssignment(ShiftAssignment):
    
    def validate(self):
        super().validate()
        if not self.custom_is_default_shift:
            return
        existing = frappe.get_all(
            "Shift Assignment",
            filters={
                "employee": self.employee,
                "custom_is_default_shift": 1,
                "name": ["!=", self.name],
                "status": "Active",
                "docstatus": ["<", 2]
            },
            fields=["name", "shift_type", "shift_location"]
        )
        if existing:
            frappe.throw(
                f"Employee already has Default Shift Assignment: "
                f"{existing[0].shift_type} - {existing[0].shift_location}"
            )
    
    def validate_overlapping_shifts(self):
        overlapping = frappe.db.sql("""
            select name, shift_type, shift_location, start_date, end_date
            from `tabShift Assignment`
            where employee = %s
            and docstatus < 2
            and shift_location = %s
            and shift_type = %s
            and (
                (start_date <= %s and end_date >= %s)
                or (start_date <= %s and end_date >= %s)
                or (start_date >= %s and end_date <= %s)
            )
            and name != %s
        """, (
            self.employee, self.shift_location, self.shift_type,
            self.end_date, self.start_date,
            self.start_date, self.end_date,
            self.start_date, self.end_date,
            self.name
        ), as_dict=True)

        for d in overlapping:
                # throw only if BOTH location and shift type are same
                if d.shift_location == self.shift_location and d.shift_type == self.shift_type:
                    self.throw_overlap_error(d)
                    
    def on_submit(self):
        # super().on_submit()
        if not self.custom_is_default_shift:
            return
        frappe.db.set_value(
            "Employee",
            self.employee,
            "default_shift",
            self.shift_type
        )
        # Allowed Shift Locations / Employee.custom_allowed_shift_locations come from CentralHrms.
        # Without them there is nothing more to do here.
        if not _has_allowed_locations():
            return
        locations = frappe.get_all("Allowed Shift Locations",
            filters={"parent": self.employee},
            fields=["shift_location"],
            distinct=True)
        location_list = [row.shift_location for row in locations]
        if self.shift_location not in location_list:
            child = frappe.get_doc({
                "doctype": "Allowed Shift Locations",
                "parent": self.employee,
                "parentfield": "custom_allowed_shift_locations",
                "parenttype": "Employee",
                "shift_location": self.shift_location
            })
            child.insert(ignore_permissions=True)

    def on_cancel(self):
        if self.custom_is_default_shift:
            frappe.db.set_value(
                "Employee",
                self.employee,
                "default_shift",
                ""
            )
        if _has_allowed_locations():
            frappe.db.delete("Allowed Shift Locations", {
                "parent": self.employee,
                "parentfield": "custom_allowed_shift_locations",
                "shift_location": self.shift_location
            })
