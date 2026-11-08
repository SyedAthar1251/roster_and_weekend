"""Weekend resolution (replacement for the old centralhrms/utils/weekend_policy.py).

Order of authority for an employee on a date:
  1. Published Roster Entry  -> Off = weekend; Work / Leave / Sick = not weekend
  2. Weekend Policy (Shift Assignment policy, else Shift Type policy, else default shift's policy)

Public API is unchanged: is_weekend, get_weekend_dates (list of 'YYYY-MM-DD'),
get_employee_weekend_policy, resolve_weekend_policy.

Changes vs the previous version:
  * history-aware: dates before effective_from use the snapshot rows written on each policy edit
  * one policy resolution per range instead of 3-5 queries per day
  * deterministic when assignments overlap (latest start_date wins, then latest creation)
  * weekday names come from date.weekday(), not strftime (locale safe)
Rotation weeks still count from cycle_start_date, exactly as before, so existing policies resolve identically.
"""
import json

import frappe
from frappe.utils import getdate

DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


# ---------- pure rule logic (no database) ----------
def _current_rule(policy):
	if policy.policy_type == "Fixed":
		return {"type": "Fixed", "days": {r.day for r in (policy.weekend_days or []) if r.is_weekend_off and r.day}}
	rows = policy.rotation_cycle or []
	weeks = policy.rotation_weeks or max((r.week_number for r in rows if r.week_number), default=1)
	return {"type": "Rotational", "start": getdate(policy.cycle_start_date) if policy.cycle_start_date else None, "weeks": weeks,
		"cycle": [(r.week_number, r.weekend_day) for r in rows if r.is_weekend_off and r.weekend_day and r.week_number]}


def _history_rule(policy, d):
	rows = [h for h in (policy.get("custom_weekend_policy_history") or []) if h.previous_effective_from and h.previous_effective_to]
	for h in sorted(rows, key=lambda x: getdate(x.previous_effective_from), reverse=True):
		if getdate(h.previous_effective_from) <= d <= getdate(h.previous_effective_to):
			if not h.previous_is_active:
				return None
			if h.previous_policy_type == "Fixed":
				days = {x.strip() for x in (h.previous_weekend_days or "").split(",") if x.strip() and x.strip() != "None"}
				return {"type": "Fixed", "days": days}
			try:
				cyc = json.loads(h.previous_rotation_cycle or "[]")
			except ValueError:
				cyc = []
			weeks = h.previous_rotation_weeks or max((c.get("week_number") or 0 for c in cyc), default=1) or 1
			return {"type": "Rotational", "start": getdate(h.previous_cycle_start_date) if h.previous_cycle_start_date else None, "weeks": weeks,
				"cycle": [(c["week_number"], c["weekend_day"]) for c in cyc if c.get("is_weekend_off") and c.get("weekend_day") and c.get("week_number")]}
	return None


def _rule_for(policy, d):
	if d >= getdate(policy.effective_from):
		return _current_rule(policy) if policy.is_active else None
	return _history_rule(policy, d)


def _rule_hit(rule, d):
	if not rule:
		return False
	name = DAY_NAMES[d.weekday()]
	if rule["type"] == "Fixed":
		return name in rule["days"]
	if not rule["start"] or d < rule["start"]:
		return False
	week = ((d - rule["start"]).days // 7) % rule["weeks"] + 1
	return any(w == week and day == name for w, day in rule["cycle"])


# ---------- database access ----------
def _has_roster():
	v = getattr(frappe.local, "_roster_table", None)
	if v is None:
		v = frappe.local._roster_table = bool(frappe.db.table_exists("Roster Entry"))
	return v


def _roster_range(employee, start, end):
	if not _has_roster():
		return {}
	rows = frappe.get_all("Roster Entry", filters={"employee": employee, "status": "Published", "date": ["between", [start, end]]},
		fields=["date", "entry_type"], limit_page_length=0)
	return {getdate(r.date): r.entry_type for r in rows}


class _Resolver:
	def __init__(self, employee, start, end):
		self.employee = employee
		emp = frappe.get_cached_doc("Employee", employee)
		self.company, self.branch, self.default_shift = emp.get("company"), emp.get("branch"), emp.get("default_shift")
		self.assignments = frappe.get_all("Shift Assignment", filters={"employee": employee, "docstatus": ["!=", 2], "status": "Active",
			"start_date": ["<=", end]}, or_filters=[["end_date", "is", "not set"], ["end_date", ">=", start]],
			fields=["shift_type", "start_date", "end_date", "custom_weekend_policy"], order_by="start_date desc, creation desc")

	def policy_name_for(self, d):
		for a in self.assignments:
			if getdate(a.start_date) <= d and (not a.end_date or getdate(a.end_date) >= d):
				return a.custom_weekend_policy or frappe.get_cached_value("Shift Type", a.shift_type, "custom_weekend_policy") or None
		if self.default_shift:
			return frappe.get_cached_value("Shift Type", self.default_shift, "custom_weekend_policy") or None
		return None

	def policy_for(self, d):
		name = self.policy_name_for(d)
		if not name:
			return None
		policy = frappe.get_cached_doc("Weekend Policy", name)
		if not self.company or policy.company != self.company:
			return None
		if policy.branch and policy.branch != self.branch:
			return None
		return policy

	def is_weekend(self, d):
		policy = self.policy_for(d)
		return bool(policy and _rule_hit(_rule_for(policy, d), d))


# ---------- public API ----------
def is_weekend(employee, date):
	d = getdate(date)
	roster = _roster_range(employee, d, d)
	if d in roster:
		return roster[d] == "Off"
	return _Resolver(employee, d, d).is_weekend(d)


def get_weekend_dates(employee, start_date, end_date):
	start, end = getdate(start_date), getdate(end_date)
	if start > end:
		return []
	roster = _roster_range(employee, start, end)
	resolver = None
	out, d = [], start
	while d <= end:
		if d in roster:
			if roster[d] == "Off":
				out.append(d.strftime("%Y-%m-%d"))
		else:
			resolver = resolver or _Resolver(employee, start, end)
			if resolver.is_weekend(d):
				out.append(d.strftime("%Y-%m-%d"))
		d = frappe.utils.add_days(d, 1)
	return out


def resolve_weekend_policy(employee, date):
	if not employee or not date:
		return None
	d = getdate(date)
	return _Resolver(employee, d, d).policy_name_for(d)


def get_employee_weekend_policy(employee, date):
	d = getdate(date)
	policy = _Resolver(employee, d, d).policy_for(d)
	return policy if policy and _rule_for(policy, d) else None
