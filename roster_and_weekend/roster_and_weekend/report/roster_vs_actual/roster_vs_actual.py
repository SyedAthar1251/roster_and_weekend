from roster_and_weekend.roster_and_weekend.api import _mgr, board_rows


def execute(filters=None):
	_mgr()
	f = filters or {}
	cols = [("employee", "Employee", "Link/Employee", 110), ("employee_name", "Name", "Data", 160), ("date", "Date", "Date", 95),
		("shift_location", "Location", "Link/Shift Location", 130), ("shift_type", "Shift", "Link/Shift Type", 110),
		("planned_in", "Planned In", "Datetime", 150), ("planned_out", "Planned Out", "Datetime", 150),
		("actual_in", "Actual In", "Datetime", 150), ("actual_out", "Actual Out", "Datetime", 150),
		("status", "Status", "Data", 90), ("late_minutes", "Late (min)", "Int", 80), ("ot_minutes", "OT (min)", "Int", 80)]
	columns = [{"fieldname": a, "label": b, "fieldtype": c.split("/")[0], "options": c.split("/")[1] if "/" in c else None, "width": w} for a, b, c, w in cols]
	return columns, board_rows(f.get("from_date"), f.get("to_date"), f.get("shift_location"))
