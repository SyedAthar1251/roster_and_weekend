"""Integration tests. Run on a bench:  bench --site <site> run-tests --app roster_and_weekend
Needs: Company, 3 Employees, 2 Shift Types (Morning/Night), 1 Shift Location. Adjust fixtures to your site."""
import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, getdate, nowdate


class TestRosterFlow(FrappeTestCase):
	def setUp(self):
		self.emps = frappe.get_all("Employee", filters={"status": "Active"}, pluck="name", limit=3)
		self.shift = frappe.db.get_value("Shift Type", {}, "name")
		if len(self.emps) < 3 or not self.shift:
			self.skipTest("Needs 3 active employees and a Shift Type on the test site")

	def _plan(self):
		plan = frappe.get_doc({"doctype": "Roster Plan", "from_date": add_days(nowdate(), 1), "to_date": add_days(nowdate(), 14),
			"employees": [{"employee": e, "pattern": "6 on 1 off", "start_day_no": i + 1, "shift_type": self.shift} for i, e in enumerate(self.emps)]}).insert()
		plan.generate()
		return plan

	def test_generate_creates_staggered_off_days(self):
		plan = self._plan()
		self.assertEqual(plan.reload().generated_count, 3 * 14)
		offs = frappe.get_all("Roster Entry", filters={"plan": plan.name, "entry_type": "Off", "date": plan.from_date}, pluck="employee")
		self.assertLessEqual(len(offs), 1)

	def test_regenerate_is_idempotent(self):
		plan = self._plan(); plan.generate()
		self.assertEqual(frappe.db.count("Roster Entry", {"plan": plan.name}), 3 * 14)

	def test_leave_converts_work_days(self):
		plan = self._plan()
		frappe.db.set_value("Roster Entry", {"plan": plan.name}, "status", "Published")
		doc = frappe._dict(employee=self.emps[0], employee_name="T", from_date=plan.from_date, to_date=add_days(plan.from_date, 2))
		from roster_and_weekend.roster_and_weekend import events
		events.leave_submitted(doc)
		self.assertFalse(frappe.db.exists("Roster Entry", {"plan": plan.name, "employee": self.emps[0], "date": plan.from_date, "entry_type": "Work"}))
