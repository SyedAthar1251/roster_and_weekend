import frappe
from frappe.model.document import Document

MAX_OFFSET_MINUTES = 360


class ShiftTimeException(Document):
	def validate(self):
		self.start_offset = int(self.start_offset or 0)
		self.end_offset = int(self.end_offset or 0)
		if not self.start_offset and not self.end_offset:
			frappe.throw("Both offsets are 0, so this exception changes nothing. Set a start and/or end offset.")
		for label, v in (("Start Offset", self.start_offset), ("End Offset", self.end_offset)):
			if abs(v) > MAX_OFFSET_MINUTES:
				frappe.throw(f"{label} cannot be more than {MAX_OFFSET_MINUTES} minutes either way.")
		self.block_edit_when_in_use()

	def block_edit_when_in_use(self):
		"""Attendance already judged with these offsets must not change meaning later: make a new exception instead."""
		if self.is_new():
			return
		if not (self.has_value_changed("start_offset") or self.has_value_changed("end_offset")):
			return
		used = frappe.db.count("Shift Assignment", {"custom_time_exception": self.name, "docstatus": ["<", 2]})
		if used:
			frappe.throw(
				f"{used} Shift Assignment(s) already use this exception. Offsets cannot be changed; create a new exception instead."
			)