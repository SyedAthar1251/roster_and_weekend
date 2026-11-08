import unittest
from datetime import date, timedelta

from roster_and_weekend.roster_and_weekend import cycle

W, O = "Work", "Off"
SIX_ONE = cycle.build_slots([(i + 1, W if i < 6 else O, None) for i in range(7)])


class TestCycle(unittest.TestCase):
	def test_day_no_wraps(self):
		a = date(2026, 10, 12)
		self.assertEqual(cycle.day_no(a, a, 1, 7), 1)
		self.assertEqual(cycle.day_no(a + timedelta(7), a, 1, 7), 1)
		self.assertEqual(cycle.day_no(a, a, 3, 7), 3)
		self.assertEqual(cycle.day_no(a + timedelta(5), a, 3, 7), 1)

	def test_staggered_offsets_give_different_off_days(self):
		a = date(2026, 10, 12)
		offs = set()
		for off in range(1, 8):
			rows = list(cycle.expand(a, off, 7, SIX_ONE, a, a + timedelta(6), "M"))
			off_days = [d for d, t, _ in rows if t == O]
			self.assertEqual(len(off_days), 1)
			offs.add(off_days[0])
		self.assertEqual(len(offs), 7)

	def test_ten_day_cycle_and_extension_continuity(self):
		a = date(2026, 10, 12)
		slots = cycle.build_slots([(i + 1, W if i < 7 else O, None) for i in range(10)])
		whole = [(d, t) for d, t, _ in cycle.expand(a, 1, 10, slots, a, a + timedelta(29), "M")]
		first = [(d, t) for d, t, _ in cycle.expand(a, 1, 10, slots, a, a + timedelta(14), "M")]
		second = [(d, t) for d, t, _ in cycle.expand(a, 1, 10, slots, a + timedelta(15), a + timedelta(29), "M")]
		self.assertEqual(whole, first + second)
		self.assertEqual(sum(t == O for _, t in whole), 9)

	def test_default_shift_and_explicit_shift(self):
		a = date(2026, 10, 12)
		slots = cycle.build_slots([(1, W, "Night"), (2, W, None), (3, O, None)])
		got = [s for _, t, s in cycle.expand(a, 1, 3, slots, a, a + timedelta(2), "Morning")]
		self.assertEqual(got, ["Night", "Morning", None])

	def test_night_shift_crosses_midnight(self):
		s, e = cycle.window(date(2026, 10, 12), timedelta(hours=22), timedelta(hours=6))
		self.assertEqual((e - s).total_seconds() / 3600, 8)
		self.assertEqual(e.date(), date(2026, 10, 13))

	def test_rest_hours_night_to_morning(self):
		night, morning = (timedelta(hours=22), timedelta(hours=6)), (timedelta(hours=6), timedelta(hours=14))
		self.assertEqual(cycle.rest_hours(date(2026, 10, 12), night, date(2026, 10, 13), morning), 0)
		self.assertEqual(cycle.rest_hours(date(2026, 10, 12), morning, date(2026, 10, 13), morning), 16)

	def test_merge_runs(self):
		d = date(2026, 10, 12)
		rows = [(d, "M", "A", "P"), (d + timedelta(1), "M", "A", "P"), (d + timedelta(2), "E", "A", "P"), (d + timedelta(4), "E", "A", "P")]
		self.assertEqual([(r[0], r[1], r[2]) for r in cycle.merge_runs(rows)],
			[(d, d + timedelta(1), "M"), (d + timedelta(2), d + timedelta(2), "E"), (d + timedelta(4), d + timedelta(4), "E")])


if __name__ == "__main__":
	unittest.main()
