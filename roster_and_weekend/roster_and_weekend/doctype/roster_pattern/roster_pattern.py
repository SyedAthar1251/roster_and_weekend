import frappe
from frappe.model.document import Document


WEEKDAYS = ["Sunday", "Monday", "Tuesday", "Wednesday",
            "Thursday", "Friday", "Saturday"]


class RosterPattern(Document):
	def validate(self):
		try:
			cycle_days = int(self.cycle_days)
		except (ValueError, TypeError):
			frappe.throw("Cycle Days must be a valid number")

		if cycle_days < 1:
			frappe.throw("Cycle Days must be at least 1")
		if cycle_days > 31:
			frappe.throw("Cycle Days cannot exceed 31")

		# --- Auto-generate day rows (Task 1) ---
		existing_nums = {d.day_no for d in self.days if d.day_no}
		for day_no in range(1, cycle_days + 1):
			if day_no not in existing_nums:
				self.append("days", {
					"day_no": day_no,
					"day_type": "Work",
					"shift_type": None,
				})

		# --- Handle cycle-length reduction safely (Task 1) ---
		extra_rows = [d for d in self.days if d.day_no and d.day_no > cycle_days]
		if extra_rows:
			has_user_values = any(
				d.day_type != "Work" or d.shift_type
				for d in extra_rows
			)
			if has_user_values:
				frappe.throw(
					f"Reducing cycle days to {cycle_days} would remove "
					f"{len(extra_rows)} day(s) with user-entered values. "
					"Please review and remove them manually before saving."
				)
			for d in list(extra_rows):
				self.days.remove(d)

		# --- Compute weekday display (Task 3) ---
		for d in self.days:
			if d.day_no:
				d.weekday = WEEKDAYS[(d.day_no - 1) % 7]

		# --- Existing validation ---
		nums = sorted(d.day_no for d in self.days if d.day_no)
		if nums != list(range(1, cycle_days + 1)):
			frappe.throw(f"Pattern days must be exactly 1..{cycle_days}, one row each")
