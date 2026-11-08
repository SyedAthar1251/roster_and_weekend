from datetime import timedelta

import frappe
from frappe.utils import add_days, getdate, now, now_datetime

from roster_and_weekend.roster_and_weekend import cycle, notify


def settings():
	return frappe.get_cached_doc("Roster Settings")


def shift_times(shift_type):
	s, e = frappe.get_cached_value("Shift Type", shift_type, ["start_time", "end_time"])
	return s, e


def window(entry):
	return cycle.window(getdate(entry.date), *shift_times(entry.shift_type))


def leave_dates(employees, start, end):
	out = {}
	rows = frappe.get_all("Leave Application", filters={"employee": ["in", employees], "status": "Approved",
		"docstatus": 1, "from_date": ["<=", end], "to_date": [">=", start]}, fields=["employee", "from_date", "to_date"])
	for r in rows:
		for d in cycle.daterange(max(getdate(r.from_date), start), min(getdate(r.to_date), end)):
			out.setdefault(r.employee, set()).add(d)
	return out


def rule_issues(emp, cells, s=None):
	"""cells: {date: (entry_type, shift_type)}. Returns human-readable rule violations."""
	s, out = s or settings(), []
	one = lambda d, n: d + timedelta(days=n)
	for d in sorted(cells):
		et, sh = cells[d]
		if et != "Work":
			continue
		run, k = 1, one(d, -1)
		while k in cells and cells[k][0] == "Work":
			run, k = run + 1, one(k, -1)
		if run == s.max_consecutive_days + 1:
			out.append(f"{emp}: more than {s.max_consecutive_days} consecutive work days on {d}")
		p = cells.get(one(d, -1))
		if p and p[0] == "Work" and p[1] and sh:
			gap = cycle.rest_hours(one(d, -1), shift_times(p[1]), d, shift_times(sh))
			if gap < s.min_rest_hours:
				out.append(f"{emp}: only {gap:.1f}h rest before {d}")
	return out


def cells_for(employee, start, end, override=None):
	rows = frappe.get_all("Roster Entry", filters={"employee": employee, "date": ["between", [start, end]],
		"status": ["!=", "Cancelled"]}, fields=["date", "entry_type", "shift_type"])
	cells = {getdate(r.date): (r.entry_type, r.shift_type) for r in rows}
	cells.update(override or {})
	return cells


def generate_entries(plan, skip_employees=None, skip_conflicts=None):
	start, end = getdate(plan.from_date), getdate(plan.to_date)
	anchor = getdate(plan.anchor_date or plan.from_date)
	emps = [r.employee for r in plan.employees]
	if skip_employees:
		emps = [e for e in emps if e not in skip_employees]
		plan_employees = [r for r in plan.employees if r.employee not in skip_employees]
	else:
		plan_employees = plan.employees
	skip_conflict_set = {(sc["employee"], getdate(sc["date"])) for sc in (skip_conflicts or [])}
	frappe.db.delete("Roster Entry", {"plan": plan.name})
	taken = {(r.employee, getdate(r.date)) for r in frappe.get_all("Roster Entry", filters={
		"employee": ["in", emps], "date": ["between", [start, end]],
		"status": ["!=", "Cancelled"]}, fields=["employee", "date"])}
	taken.update(skip_conflict_set)
	leaves = leave_dates(emps, start, end)
	names = dict(frappe.get_all("Employee", filters={"name": ["in", emps]}, fields=["name", "employee_name"], as_list=True))
	fields = ["name", "owner", "creation", "modified", "modified_by", "docstatus", "idx", "employee", "employee_name",
		"date", "entry_type", "shift_type", "shift_location", "plan", "status", "source", "acknowledged"]
	ts, user, values, log, s = now(), frappe.session.user, [], [], settings()
	skipped_conflicts = []
	for r in plan_employees:
		pat = frappe.get_cached_doc("Roster Pattern", r.pattern)
		slots = cycle.build_slots((d.day_no, d.day_type, d.shift_type) for d in pat.days)
		cells = {}
		for d, typ, shift in cycle.expand(anchor, r.start_day_no or 1, pat.cycle_days, slots, start, end, r.shift_type):
			if (r.employee, d) in taken:
				if (r.employee, d) in skip_conflict_set:
					skipped_conflicts.append(f"{r.employee} {d}: skipped due to published entry from another plan")
					log.append(f"Skipped {r.employee} {d}: already has an entry from another plan")
				else:
					log.append(f"Skipped {r.employee} {d}: already has an entry from another plan")
				continue
			if typ == "Work" and not shift:
				frappe.throw(f"{r.employee}: pattern day has no shift and no default shift set on the plan row")
			etype = "Leave" if typ == "Work" and d in leaves.get(r.employee, ()) else typ
			cells[d] = (etype, shift)
			values.append([frappe.generate_hash(length=10), user, ts, ts, user, 0, 0, r.employee, names.get(r.employee),
				d, etype, shift, r.shift_location, plan.name, "Draft", "Leave" if etype == "Leave" else "Plan", 0])
		log += rule_issues(r.employee, cells, s)
	if values:
		frappe.db.bulk_insert("Roster Entry", fields, values)
	plan.db_set("generated_count", len(values))
	return log or ["No rule violations found"], skipped_conflicts


def rebuild_assignments(employee, start, end):
	"""Replace roster-owned Shift Assignments touching [start, end] with runs rebuilt from Roster Entry."""
	old = frappe.get_all("Shift Assignment", filters={"employee": employee, "docstatus": 1, "roster_plan": ["is", "set"],
		"start_date": ["<=", end], "end_date": [">=", start]}, fields=["name", "start_date", "end_date"])
	lo = min([getdate(start)] + [getdate(a.start_date) for a in old])
	hi = max([getdate(end)] + [getdate(a.end_date) for a in old])
	for a in old:
		frappe.get_doc("Shift Assignment", a.name).cancel()
	rows = frappe.get_all("Roster Entry", filters={"employee": employee, "entry_type": "Work", "status": "Published",
		"date": ["between", [lo, hi]]}, fields=["date", "shift_type", "shift_location", "plan"], order_by="date")
	company, errors = frappe.db.get_value("Employee", employee, "company"), []
	frappe.flags.roster_sync = True
	for i, (s, e, shift, loc, plan) in enumerate(cycle.merge_runs([(getdate(r.date), r.shift_type, r.shift_location, r.plan) for r in rows])):
		try:
			doc = frappe.get_doc({"doctype": "Shift Assignment", "employee": employee, "company": company, "shift_type": shift,
				"shift_location": loc, "start_date": s, "end_date": e, "status": "Active", "roster_plan": plan,
				"custom_is_default_shift": 1 if i == 0 else 0})
			doc.insert(ignore_permissions=True)
			doc.submit()
		except Exception as ex:
			errors.append(f"{employee} {s}..{e}: {ex}")
	frappe.flags.roster_sync = False
	return errors


def rebuild_assignments_safe(employee, start, end, skip_conflict_set):
	"""Like rebuild_assignments but skips employee/date combos that belong to other published plans."""
	old = frappe.get_all("Shift Assignment", filters={"employee": employee, "docstatus": 1, "roster_plan": ["is", "set"],
		"start_date": ["<=", end], "end_date": [">=", start]}, fields=["name", "start_date", "end_date"])
	lo = min([getdate(start)] + [getdate(a.start_date) for a in old])
	hi = max([getdate(end)] + [getdate(a.end_date) for a in old])
	for a in old:
		frappe.get_doc("Shift Assignment", a.name).cancel()
	rows = frappe.get_all("Roster Entry", filters={"employee": employee, "entry_type": "Work", "status": "Published",
		"date": ["between", [lo, hi]]}, fields=["date", "shift_type", "shift_location", "plan"], order_by="date")
	company, errors = frappe.db.get_value("Employee", employee, "company"), []
	# Filter out dates that have conflicts from other plans
	filtered_rows = [r for r in rows if (employee, getdate(r.date)) not in skip_conflict_set]
	frappe.flags.roster_sync = True
	for i, (s, e, shift, loc, plan) in enumerate(cycle.merge_runs([(getdate(r.date), r.shift_type, r.shift_location, r.plan) for r in filtered_rows])):
		try:
			doc = frappe.get_doc({"doctype": "Shift Assignment", "employee": employee, "company": company, "shift_type": shift,
				"shift_location": loc, "start_date": s, "end_date": e, "status": "Active", "roster_plan": plan,
				"custom_is_default_shift": 1 if i == 0 else 0})
			doc.insert(ignore_permissions=True)
			doc.submit()
		except Exception as ex:
			errors.append(f"{employee} {s}..{e}: {ex}")
	frappe.flags.roster_sync = False
	return errors


def _publish_progress(plan_name, percent, description, done=False, success=True, message=None):
	"""Realtime update for the progress bar on the Roster Plan form."""
	frappe.publish_realtime(
		"roster_publish_progress",
		{"plan": plan_name, "percent": percent, "description": description,
		 "done": done, "success": success, "message": message},
		user=frappe.session.user,
	)


def publish_plan(plan_name, skip_employees=None, skip_conflicts=None):
	"""Background job entry point: publishes the plan and reports success/failure to the form."""
	try:
		_publish_plan(plan_name, skip_employees, skip_conflicts)
	except Exception as ex:
		frappe.db.rollback()
		_publish_progress(plan_name, 100, "Publish failed", done=True, success=False, message=str(ex))
		raise


def _publish_plan(plan_name, skip_employees=None, skip_conflicts=None):
	plan = frappe.get_doc("Roster Plan", plan_name)
	_publish_progress(plan_name, 2, "Checking for conflicts…")
	skip_conflict_set = {(sc["employee"], getdate(sc["date"])) for sc in (skip_conflicts or [])}
	# Recheck conflicts: new published entries may have appeared since save
	emps = [r.employee for r in plan.employees]
	start, end = getdate(plan.from_date), getdate(plan.to_date)
	filters = {"employee": ["in", emps], "date": ["between", [start, end]], "status": "Published",
		"plan": ["!=", plan_name]}
	new_conflicts = {(r.employee, getdate(r.date), r.plan) for r in frappe.get_all("Roster Entry",
		filters=filters, fields=["employee", "date", "plan"])}
	unconfirmed = new_conflicts - {(sc["employee"], getdate(sc["date"]), sc.get("plan")) for sc in (skip_conflicts or [])}
	if unconfirmed:
		conflict_details = []
		names_map = {n: e for n, e in frappe.get_all("Employee", filters={"name": ["in", emps]},
			fields=["name", "employee_name"], as_list=True)}
		plan_map = {p.name: p.plan_title for p in frappe.get_all("Roster Plan",
			filters={"name": ["in", [c[2] for c in unconfirmed]]}, fields=["name", "plan_title"])}
		for emp, dt, other_plan in unconfirmed:
			conflict_details.append(f"{names_map.get(emp, emp)} on {dt} from '{plan_map.get(other_plan, other_plan)}'")
		frappe.throw(
			"New conflicts detected during Publish. The following employee/date combinations "
			"already have published entries from other plans:<br>" + "<br>".join(conflict_details) +
			"<br><br>Cancel these other plans or regenerate to skip the new conflicts."
		)
	skip = set(skip_employees or [])
	_publish_progress(plan_name, 5, "Publishing roster entries…")
	frappe.db.set_value("Roster Entry", {"plan": plan_name, "status": "Draft"}, "status", "Published")
	errors = []
	total = len(plan.employees) or 1
	for idx, r in enumerate(plan.employees, 1):
		# progress runs from 5% to 95% across the employees
		_publish_progress(plan_name, 5 + int((idx - 1) / total * 90),
			f"Processing employee {idx} of {total}")
		if r.employee in skip:
			continue
		for entry in frappe.get_all("Roster Entry", filters={"employee": r.employee, "date": ["between", [start, end]],
			"status": "Published", "plan": ["!=", plan_name]}, fields=["date", "plan"]):
			if (r.employee, getdate(entry.date)) not in skip_conflict_set:
				skip_conflict_set.add((r.employee, getdate(entry.date)))
		errors += rebuild_assignments_safe(r.employee, plan.from_date, plan.to_date, skip_conflict_set)
		notify.to_employee(r.employee, "New roster published",
			f"Your roster {plan.from_date} to {plan.to_date} is ready. Please open My Roster and acknowledge it.")
	_publish_progress(plan_name, 97, "Finalizing…")
	plan.db_set({"status": "Published", "published_on": now_datetime(), "last_log": "\n".join(errors[:20])[:1000] or plan.last_log})
	frappe.db.commit()
	# Only now, after everything is saved, tell the form it is finished.
	_publish_progress(plan_name, 100, "Completed", done=True, success=True)


def cancel_plan(plan_name):
	"""Cancel a Published plan completely, only for its own From/To dates.
	Roster Entries are marked Cancelled (not deleted); Shift Assignments are cancelled (not deleted)."""
	plan = frappe.get_doc("Roster Plan", plan_name)
	if plan.status != "Published":
		frappe.throw("Only Published plans can be cancelled")
	start, end = getdate(plan.from_date), getdate(plan.to_date)

	# 1. Roster Entries of this plan -> Cancelled
	frappe.db.sql(
		"""update `tabRoster Entry` set status = 'Cancelled', modified = %s, modified_by = %s
		where plan = %s and date between %s and %s and status != 'Cancelled'""",
		(now(), frappe.session.user, plan_name, start, end),
	)

	# 2. Shift Assignments: cancel roster-owned ones in this date range, then rebuild
	#    from any remaining Published entries (other plans) so those dates stay covered.
	errors = []
	for r in plan.employees:
		errors += rebuild_assignments(r.employee, start, end)
	# 3. Cancel anything still linked to this plan in the range
	errors += cancel_roster_shift_assignments(plan_name, start, end)

	# 4. Plan status
	plan.db_set("status", "Cancelled")
	if errors:
		plan.db_set("last_log", "\n".join(errors[:20])[:1000])
	frappe.db.commit()
	if errors:
		frappe.throw(
			"Plan {0} cancelled, but {1} Shift Assignment(s) could not be cancelled: {2}".format(
				plan.name, len(errors), "; ".join(errors[:5])
			),
			title="Cancellation Incomplete",
		)
	return {"status": "Cancelled", "name": plan.name, "errors": errors}


def cancel_roster_shift_assignments(plan_name, start, end):
	"""Cancel all submitted Shift Assignments linked to *plan_name* that overlap [start, end].
	Returns a list of human-readable error strings for assignments that could not be cancelled."""
	assignments = frappe.get_all(
		"Shift Assignment",
		filters={
			"roster_plan": plan_name,
			"docstatus": 1,
			"status": "Active",
			"start_date": ["<=", end],
			"end_date": [">=", start],
		},
		fields=["name", "start_date", "end_date"],
	)
	errors = []
	for a in assignments:
		try:
			doc = frappe.get_doc("Shift Assignment", a.name)
			doc.cancel()
		except Exception as ex:
			errors.append(f"Shift Assignment {a.name}: {ex}")
	return errors