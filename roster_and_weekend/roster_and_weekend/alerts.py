from datetime import timedelta

import frappe
from frappe.utils import add_days, getdate, now_datetime, nowdate

from roster_and_weekend.roster_and_weekend import engine, notify


def _flag(entry_name, flag):
	cur = frappe.db.get_value("Roster Entry", entry_name, "alerts_sent") or ""
	if flag in cur.split(","):
		return False
	frappe.db.set_value("Roster Entry", entry_name, "alerts_sent", f"{cur},{flag}".strip(","), update_modified=False)
	return True


def run():
	"""Every 5 minutes: no-show, missed check-out, understaffing, unacknowledged rosters."""
	from roster_and_weekend.roster_and_weekend.api import actuals

	s, now = engine.settings(), now_datetime()
	grace = timedelta(minutes=s.grace_minutes or 0)
	ents = frappe.get_all("Roster Entry", filters={"date": ["between", [add_days(nowdate(), -1), nowdate()]], "entry_type": "Work",
		"status": "Published"}, fields=["name", "employee", "employee_name", "date", "shift_type", "shift_location"])
	act = actuals(ents)
	for e in ents:
		st, en = engine.window(e)
		i, o = act.get((e.employee, getdate(e.date)), (None, None))
		if not i and now > st + grace and now < en and _flag(e.name, "NOSHOW"):
			notify.to_managers("No-show", f"{e.employee_name} has not checked in for {e.shift_type} at {e.shift_location or '-'}")
			if s.auto_open_shift:
				frappe.get_doc({"doctype": "Roster Open Shift", "date": e.date, "shift_type": e.shift_type, "shift_location": e.shift_location,
					"reason": "No Show", "original_employee": e.employee}).insert(ignore_permissions=True)
		if i and not o and now > en + grace and _flag(e.name, "NOOUT"):
			notify.to_managers("Missed check-out", f"{e.employee_name} has no check-out for {e.shift_type} on {e.date}")
	understaffed(now)
	unacknowledged(s, now)
	frappe.db.commit()


def understaffed(now):
	for r in frappe.get_all("Roster Site Rule", fields=["shift_location", "shift_type", "min_staff"]):
		start_td = engine.shift_times(r.shift_type)[0]
		for d in (getdate(now), getdate(add_days(now, 1))):
			st = engine.cycle.window(d, *engine.shift_times(r.shift_type))[0]
			if not (now <= st <= now + timedelta(hours=4)):
				continue
			n = frappe.db.count("Roster Entry", {"date": d, "shift_location": r.shift_location, "shift_type": r.shift_type,
				"entry_type": "Work", "status": "Published"})
			key = f"roster_short:{r.shift_location}:{r.shift_type}:{d}"
			if n < r.min_staff and not frappe.cache().get_value(key):
				frappe.cache().set_value(key, 1, expires_in_sec=6 * 3600)
				notify.to_managers("Understaffed shift", f"{r.shift_location} {r.shift_type} on {d}: {n} rostered, minimum {r.min_staff}")


def unacknowledged(s, now):
	cutoff = now - timedelta(hours=s.ack_hours or 12)
	for p in frappe.get_all("Roster Plan", filters={"status": "Published", "published_on": ["<", cutoff]}, fields=["name"]):
		for emp in frappe.get_all("Roster Entry", filters={"plan": p.name, "acknowledged": 0, "status": "Published", "date": [">=", nowdate()]},
				pluck="employee", distinct=True):
			key = f"roster_ack:{p.name}:{emp}:{nowdate()}"
			if not frappe.cache().get_value(key):
				frappe.cache().set_value(key, 1, expires_in_sec=24 * 3600)
				notify.to_employee(emp, "Please acknowledge your roster", "Your published roster is waiting for your acknowledgement.")
