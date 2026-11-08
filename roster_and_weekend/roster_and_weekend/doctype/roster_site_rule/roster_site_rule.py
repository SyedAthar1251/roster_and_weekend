import frappe
from frappe.model.document import Document


class RosterSiteRule(Document):
	def validate(self):
		if frappe.db.exists("Roster Site Rule", {"shift_location": self.shift_location, "shift_type": self.shift_type, "name": ["!=", self.name]}):
			frappe.throw("A rule for this location and shift already exists")
