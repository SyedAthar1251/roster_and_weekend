import frappe
from frappe import _
from frappe.utils import flt


def execute(filters=None):
	filters = filters or {}
	columns = get_columns()
	data = get_data(filters)
	report_summary = get_summary(data)
	return columns, data, None, None, report_summary


def get_columns():
	return [
		{
			"label": _("Employee"),
			"fieldname": "employee",
			"fieldtype": "Link",
			"options": "Employee",
			"width": 120,
		},
		{
			"label": _("Employee Name"),
			"fieldname": "employee_name",
			"fieldtype": "Data",
			"width": 160,
		},
		{
			"label": _("Company"),
			"fieldname": "company",
			"fieldtype": "Link",
			"options": "Company",
			"width": 110,
		},
		{
			"label": _("Branch"),
			"fieldname": "branch",
			"fieldtype": "Link",
			"options": "Branch",
			"width": 100,
		},
		{
			"label": _("Department"),
			"fieldname": "department",
			"fieldtype": "Link",
			"options": "Department",
			"width": 110,
		},
		{
			"label": _("Shift Type"),
			"fieldname": "shift_type",
			"fieldtype": "Link",
			"options": "Shift Type",
			"width": 120,
		},
		{
			"label": _("Shift Time Exception"),
			"fieldname": "shift_time_exception",
			"fieldtype": "Link",
			"options": "Shift Time Exception",
			"width": 150,
		},
		{
			"label": _("Start Offset (hrs)"),
			"fieldname": "start_offset_hours",
			"fieldtype": "Float",
			"precision": 2,
			"width": 110,
		},
		{
			"label": _("End Offset (hrs)"),
			"fieldname": "end_offset_hours",
			"fieldtype": "Float",
			"precision": 2,
			"width": 110,
		},
		{
			"label": _("Total Exception (hrs)"),
			"fieldname": "total_exception_hours",
			"fieldtype": "Float",
			"precision": 2,
			"width": 120,
		},
		{
			"label": _("Start Date"),
			"fieldname": "start_date",
			"fieldtype": "Date",
			"width": 90,
		},
		{
			"label": _("End Date"),
			"fieldname": "end_date",
			"fieldtype": "Date",
			"width": 90,
		},
		{
			"label": _("Status"),
			"fieldname": "status",
			"fieldtype": "Data",
			"width": 90,
		},
	]


def get_data(filters):
	conditions = []
	values = {}
	if filters.get("company"):
		conditions.append("e.company = %(company)s")
		values["company"] = filters["company"]
	if filters.get("branch"):
		conditions.append("e.branch = %(branch)s")
		values["branch"] = filters["branch"]
	if filters.get("department"):
		conditions.append("e.department = %(department)s")
		values["department"] = filters["department"]
	if filters.get("shift_type"):
		conditions.append("sa.shift_type = %(shift_type)s")
		values["shift_type"] = filters["shift_type"]
	if filters.get("shift_time_exception"):
		conditions.append("sa.custom_time_exception = %(shift_time_exception)s")
		values["shift_time_exception"] = filters["shift_time_exception"]

	where = " AND ".join(conditions)
	if where:
		where = "AND " + where

	data = frappe.db.sql(f"""
		SELECT
			sa.employee,
			e.employee_name,
			e.company,
			e.branch,
			e.department,
			sa.shift_type,
			sa.custom_time_exception AS shift_time_exception,
			ste.start_offset / 60.0 AS start_offset_hours,
			ste.end_offset / 60.0 AS end_offset_hours,
			(ste.start_offset + ste.end_offset) / 60.0 AS total_exception_hours,
			sa.start_date,
			sa.end_date,
			sa.status
		FROM `tabShift Assignment` sa
		JOIN `tabEmployee` e ON e.name = sa.employee
		LEFT JOIN `tabShift Time Exception` ste ON ste.name = sa.custom_time_exception
		WHERE sa.custom_time_exception IS NOT NULL AND sa.custom_time_exception != '' {where}
		ORDER BY e.employee_name, sa.shift_type
	""", values, as_dict=True)

	for row in data:
		row["start_offset_hours"] = flt(row["start_offset_hours"], 2)
		row["end_offset_hours"] = flt(row["end_offset_hours"], 2)
		row["total_exception_hours"] = flt(row["total_exception_hours"], 2)

	return data


def get_summary(data):
	total = len(data)
	total_hours = flt(sum(row["total_exception_hours"] or 0 for row in data), 2)
	return [
		{
			"label": _("Total Assignments with Exception"),
			"value": total,
			"datatype": "Int",
		},
		{
			"label": _("Total Exception Hours"),
			"value": total_hours,
			"datatype": "Float",
		},
	]
