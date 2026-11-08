import frappe
from datetime import timedelta
from frappe.model.document import Document
from frappe.utils import getdate
from math import gcd
import json


class RosterPlan(Document):
	def validate(self):
		if self.status == "Published":
			frappe.throw(
				"Published Roster Plans cannot be modified. "
				"Please cancel the plan if you need to make changes.",
				title="Read-only",
			)
		if self.from_date > self.to_date:
			frappe.throw("From Date must be on or before To Date")
		if not self.employees:
			frappe.throw("Add at least one employee")
		if not self.anchor_date:
			self.anchor_date = self.from_date
		seen = set()
		for r in self.employees:
			if r.employee in seen:
				frappe.throw(f"Duplicate employee {r.employee}")
			seen.add(r.employee)

		# --- Date conflict safeguard (prevents 100% overlap) ---
		# If every employee already has Published entries for the full date range,
		# we cannot create a meaningful plan. Server-side guard for API/background use.
		if self.status != "Published" and (self.is_new() or self.status == "Draft"):
			self._enforce_no_full_overlap()

		# --- Block save if any employee has published entries in the date range ---
		# Allow confirmed conflicts to bypass the check (user explicitly accepted)
		if frappe.flags.in_confirmed_roster_save:
			return
		self._check_and_throw_on_conflicts()


	def _enforce_no_full_overlap(self):
		"""Throw only if ALL employees have Published roster entries covering the entire date range.
		Partial overlaps are allowed — generate_entries handles them via the taken set."""
		start, end = getdate(self.from_date), getdate(self.to_date)
		emps = [r.employee for r in self.employees]
		if not emps:
			return
		# Count date-coverage per employee
		from collections import defaultdict
		coverage = defaultdict(set)
		for d in frappe.get_all("Roster Entry", filters={
			"employee": ["in", emps], "date": ["between", [start, end]], "status": "Published"
		}, fields=["employee", "date"]):
			coverage[d.employee].add(getdate(d.date))
		conflict_free = [e for e in emps if len(coverage.get(e, set())) < (end - start).days + 1]
		if not conflict_free:
			emp_names = dict(frappe.get_all("Employee", filters={"name": ["in", emps]},
				fields=["name", "employee_name"], as_list=True))
			conflict_list = ", ".join(
				f"{e} ({emp_names.get(e, e)})" for e in sorted(set(emps))
			)
			frappe.throw(
				f"All employees already have published roster entries covering the entire "
				f"date range ({start} to {end}). Conflicting employees: {conflict_list}.\n"
				"Please choose different dates or cancel the existing roster plans first."
			)

	def _check_and_throw_on_conflicts(self):
		"""Throw if any employee has published roster entries overlapping the plan's date range.
		Excludes this plan's own entries and previously confirmed conflicts when editing."""
		start, end = getdate(self.from_date), getdate(self.to_date)
		emps = [r.employee for r in self.employees]
		if not emps:
			return
		result = _check_conflicts_detail(emps, start, end, exclude_plan=self.name if self.name else None)
		if not result["conflict_pairs"]:
			return
		# Build set of confirmed conflicts from self.confirmed_conflicts
		confirmed_pairs = set()
		if self.confirmed_conflicts:
			try:
				confirmed_list = json.loads(self.confirmed_conflicts)
				for c in confirmed_list:
					confirmed_pairs.add((c.get("employee"), c.get("date"), c.get("plan", "")))
			except (ValueError, TypeError):
				pass
		# Only throw for conflicts that are NOT yet confirmed
		unconfirmed = [cp for cp in result["conflict_pairs"]
			if (cp["employee"], str(cp["date"]), cp.get("plan", "")) not in confirmed_pairs]
		if unconfirmed:
			msg_parts = []
			for cp in unconfirmed:
				msg_parts.append(f"{cp['employee_name']} has published entry on {cp['date']} from plan '{cp['plan_label']}'")
			frappe.throw(
				"Cannot save: Employee(s) already have published roster entries for this date range.<br>"
				+ "<br>".join(msg_parts) + "<br><br>Save with confirmed conflicts to proceed."
			)
	
	@frappe.whitelist()
	def get_conflicts(self):
		"""Return conflicts for the current plan's employee/date range."""
		frappe.only_for(("Roster Manager", "HR Manager", "System Manager"))
		start, end = getdate(self.from_date), getdate(self.to_date)
		emps = [r.employee for r in self.employees]
		if not emps:
			return {"conflicting": [], "safe": [], "conflict_pairs": []}
		return _check_conflicts_detail(emps, start, end, exclude_plan=self.name if self.name else None)

	@frappe.whitelist()
	def save_with_confirmed_conflicts(self, confirmed_conflicts):
		"""Save the plan, bypassing validate's conflict check when user confirmed the conflicts.
		confirmed_conflicts: JSON string of list of {"employee": "...", "date": "...", "plan": "..."}"""
		frappe.only_for(("Roster Manager", "HR Manager", "System Manager"))
		frappe.flags.in_confirmed_roster_save = True
		try:
			if isinstance(confirmed_conflicts, str):
				confirmed_conflicts = json.loads(confirmed_conflicts)
			self.confirmed_conflicts = json.dumps(confirmed_conflicts or [])
			self.save()
			self.reload()
			return {"message": "Plan saved with confirmed conflicts", "skipped": confirmed_conflicts or []}
		finally:
			frappe.flags.in_confirmed_roster_save = False


	@frappe.whitelist()
	def repeat(self, from_date=None, to_date=None, confirmed_conflicts=None):
		frappe.only_for(("Roster Manager", "HR Manager", "System Manager"))
		# Repeat is only allowed for Published plans
		if self.status != "Published":
			frappe.throw("Only Published plans can be repeated")
		# Conflicts the user confirmed in the Continue/Cancel dialog (JSON string from the client)
		if isinstance(confirmed_conflicts, str):
			try:
				confirmed_conflicts = json.loads(confirmed_conflicts)
			except (ValueError, TypeError):
				confirmed_conflicts = []
		if not from_date or not to_date:
			frappe.throw("From Date and To Date are required")
		new_from = getdate(from_date)
		new_to = getdate(to_date)
		if new_from > new_to:
			frappe.throw("From Date must be on or before To Date")
		if new_from < getdate(self.from_date):
			frappe.throw("New plan start date cannot be before the original plan start date")
		# Validate that the repeated range does not overlap the original's published entries
		conflict = frappe.get_all("Roster Entry", filters={
			"plan": self.name, "date": ["between", [new_from, new_to]], "status": "Published"
		}, pluck="name", limit=1)
		if conflict:
			frappe.throw(
				f"Cannot repeat roster for {new_from} to {new_to}: published entries already exist for this date range."
			)
		cycles = [
			frappe.get_cached_value("Roster Pattern", r.pattern, "cycle_days") or 0
			for r in self.employees
		]
		cycles = [c for c in cycles if c > 0]
		if not cycles:
			anchor_offset_days = 0
		else:
			lcm_cycle = cycles[0]
			for c in cycles[1:]:
				lcm_cycle = lcm_cycle * c // gcd(lcm_cycle, c)
			orig_anchor = getdate(self.anchor_date or self.from_date)
			anchor_offset_days = (new_from - orig_anchor).days % lcm_cycle
		new_anchor = new_from if anchor_offset_days == 0 else new_from - timedelta(days=anchor_offset_days)
		new_plan = frappe.get_doc({
			"doctype": "Roster Plan",
			"plan_title": f"{self.plan_title} (Repeat)",
			"company": self.company,
			"from_date": new_from,
			"to_date": new_to,
			"anchor_date": new_anchor,
			"status": "Draft",
			"confirmed_conflicts": json.dumps(confirmed_conflicts or []),
		})
		for r in self.employees:
			new_plan.append("employees", {
				"employee": r.employee,
				"pattern": r.pattern,
				"start_day_no": r.start_day_no,
				"shift_location": r.shift_location,
			})
		new_plan.insert(ignore_permissions=True)
		return new_plan.name

	@frappe.whitelist()
	def check_conflicts(self):
		"""Check employees for Published roster entries in this plan's date range.
		Returns {"conflicting": [...], "safe": [...]} with date ranges per employee."""
		frappe.only_for(("Roster Manager", "HR Manager", "System Manager"))
		start, end = getdate(self.from_date), getdate(self.to_date)
		emps = [r.employee for r in self.employees]
		if not emps:
			return {"conflicting": [], "safe": []}
		names_map = {n: e for n, e in frappe.get_all("Employee", filters={"name": ["in", emps]},
			fields=["name", "employee_name"], as_list=True)}
		# Get all published roster entry dates per employee
		rows = frappe.get_all("Roster Entry", filters={
			"employee": ["in", emps], "date": ["between", [start, end]], "status": "Published"
		}, fields=["employee", "date"])
		from collections import defaultdict
		by_emp = defaultdict(list)
		for r in rows:
			by_emp[r.employee].append(getdate(r.date))
		conflicting = []
		safe = []
		for e in emps:
			dates = sorted(by_emp.get(e, []))
			if dates:
				from datetime import timedelta as _td
				ranges = _merge_consecutive_dates(dates, _td(days=1))
				conflicting.append({"name": e, "label": names_map.get(e, e), "date_ranges": ranges})
			else:
				safe.append({"name": e, "label": names_map.get(e, e)})
		return {"conflicting": conflicting, "safe": safe}

	@frappe.whitelist()
	def generate(self, skip_employees=None, skip_conflicts=None):
		frappe.only_for(("Roster Manager", "HR Manager", "System Manager"))
		if self.status != "Draft":
			frappe.throw("Only Draft plans can be regenerated")
		from roster_and_weekend.roster_and_weekend import engine
		log, skipped = engine.generate_entries(self, skip_employees=skip_employees or [], skip_conflicts=skip_conflicts or [])
		self.db_set("last_log", "\n".join(log[:30])[:1000])
		if skipped:
			log.append(f"Skipped {len(skipped)} conflicting date(s) from other plans")
		return log[:30]

	@frappe.whitelist()
	def publish(self, skip_employees=None, skip_conflicts=None):
		frappe.only_for(("Roster Manager", "HR Manager", "System Manager"))
		if not frappe.db.count("Roster Entry", {"plan": self.name}):
			frappe.throw("Generate entries first")
		frappe.enqueue("roster_and_weekend.roster_and_weekend.engine.publish_plan", plan_name=self.name,
			skip_employees=skip_employees or [], skip_conflicts=skip_conflicts or [], queue="long", timeout=3000)
		return "Publishing in background. Staff are notified when done."

	@frappe.whitelist()
	def cancel_plan(self):
		"""Cancel the whole Published plan (only for its own From/To dates).
		Roster Entries are marked Cancelled and Shift Assignments are cancelled; nothing is deleted."""
		frappe.only_for(("Roster Manager", "HR Manager", "System Manager"))
		if self.status != "Published":
			frappe.throw("Only Published plans can be cancelled")
		from roster_and_weekend.roster_and_weekend import engine
		return engine.cancel_plan(self.name)


def _check_conflicts_detail(emps, start, end, exclude_plan=None):
	"""Shared helper to find conflicting employee/date/plan pairs for published roster entries.
	Returns {"conflicting": [...], "safe": [...], "conflict_pairs": [{employee, date, plan, plan_label}]}.
	exclude_plan: when set, entries belonging to this plan are not considered conflicts."""
	from collections import defaultdict
	filters = {
		"employee": ["in", emps],
		"date": ["between", [start, end]],
		"status": "Published"
	}
	if exclude_plan:
		filters["plan"] = ["!=", exclude_plan]
	rows = frappe.get_all("Roster Entry", filters=filters,
		fields=["employee", "date", "plan", "employee_name"])
	names_map = {n: e for n, e in frappe.get_all("Employee", filters={"name": ["in", emps]},
		fields=["name", "employee_name"], as_list=True)}
	plan_names = {n: p for n, p in frappe.get_all("Roster Plan", filters={"name": ["in", [r.plan for r in rows if r.plan]]},
		fields=["name", "plan_title"], as_list=True)} if rows else {}
	by_emp = defaultdict(list)
	conflict_pairs = []
	for r in rows:
		emp_name = names_map.get(r.employee, r.employee)
		plan_label = (plan_names.get(r.plan) or str(r.plan)) if r.plan else "Unknown"
		conflict_pairs.append({
			"employee": r.employee,
			"employee_name": emp_name,
			"date": getdate(r.date),
			"plan": r.plan,
			"plan_label": plan_label
		})
		by_emp[r.employee].append(getdate(r.date))
	conflicting = []
	safe = []
	for e in emps:
		dates = sorted(by_emp.get(e, []))
		if dates:
			ranges = _merge_consecutive_dates(dates, timedelta(days=1))
			conflicting.append({"name": e, "label": names_map.get(e, e), "date_ranges": ranges})
		else:
			safe.append({"name": e, "label": names_map.get(e, e)})
	return {"conflicting": conflicting, "safe": safe, "conflict_pairs": conflict_pairs}


def _merge_consecutive_dates(dates, step):
	if not dates:
		return []
	from frappe.utils import add_days
	out = []
	cur_start, cur_end = dates[0], dates[0]
	for d in dates[1:]:
		if (d - cur_end).days <= step.days:
			cur_end = d
		else:
			out.append(f"{cur_start} to {cur_end}" if cur_start != cur_end else str(cur_start))
			cur_start, cur_end = d, d
	out.append(f"{cur_start} to {cur_end}" if cur_start != cur_end else str(cur_start))
	return out


@frappe.whitelist()
def check_conflicts_for_dates(employees, from_date, to_date, plan=None):
	"""Standalone whitelist: check if employees have published roster entries in [from_date, to_date].
	Returns {"conflicting": [...], "safe": [...], "conflict_pairs": [...]} with date_ranges per conflicting employee."""
	frappe.only_for(("Roster Manager", "HR Manager", "System Manager"))
	start, end = getdate(from_date), getdate(to_date)
	if isinstance(employees, str):
		try:
			employees = json.loads(employees)
		except (ValueError, TypeError):
			employees = [employees]
	if not employees or not start or not end:
		return {"conflicting": [], "safe": [], "conflict_pairs": []}
	result = _check_conflicts_detail(employees, start, end, exclude_plan=plan or None)
	result["conflict_pairs"] = [{
		"employee": cp["employee"],
		"employee_name": cp["employee_name"],
		"date": str(cp["date"]),
		"plan": cp["plan"],
		"plan_label": cp["plan_label"]
	} for cp in result["conflict_pairs"]]
	return result