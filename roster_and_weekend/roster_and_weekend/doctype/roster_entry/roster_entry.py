import frappe
from frappe.model.document import Document


class RosterEntry(Document):
	def validate(self):
		if self.entry_type == "Work" and not self.shift_type:
			frappe.throw("Shift Type is required for a Work entry")
		if frappe.db.exists("Roster Entry", {"employee": self.employee, "date": self.date, "name": ["!=", self.name]}):
			frappe.throw(f"{self.employee} already has a roster entry on {self.date}")
