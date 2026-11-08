"""Pure date/cycle maths. No frappe imports so it can be unit-tested anywhere."""
from datetime import datetime, time, timedelta


def daterange(start, end):
	d = start
	while d <= end:
		yield d
		d += timedelta(days=1)


def day_no(d, anchor, start_day_no, cycle_days):
	"""1-based position of date d inside the cycle for an employee with the given offset."""
	return ((start_day_no - 1 + (d - anchor).days) % cycle_days) + 1


def build_slots(rows):
	"""rows: iterable of (day_no, day_type, shift_type) -> {day_no: (day_type, shift_type)}"""
	return {int(n): (t, s) for n, t, s in rows}


def expand(anchor, start_day_no, cycle_days, slots, start, end, default_shift=None):
	"""Yield (date, 'Work'|'Off', shift_type) for every date in [start, end]."""
	for d in daterange(start, end):
		typ, shift = slots[day_no(d, anchor, start_day_no, cycle_days)]
		yield d, typ, (shift or default_shift) if typ == "Work" else None


def window(d, start_td, end_td):
	"""Shift start/end datetimes. A shift ending at or before its start crosses midnight."""
	base = datetime.combine(d, time.min)
	s, e = base + start_td, base + end_td
	if e <= s:
		e += timedelta(days=1)
	return s, e


def rest_hours(prev_date, prev_times, d, times):
	return (window(d, *times)[0] - window(prev_date, *prev_times)[1]).total_seconds() / 3600


def merge_runs(rows):
	"""rows: sorted (date, shift_type, location, plan) -> [(start, end, shift_type, location, plan)]
	Consecutive days with the same shift and location become one Shift Assignment."""
	out = []
	for d, shift, loc, plan in rows:
		if out and out[-1][1] + timedelta(days=1) == d and out[-1][2] == shift and out[-1][3] == loc:
			out[-1][1] = d
		else:
			out.append([d, d, shift, loc, plan])
	return [tuple(r) for r in out]
