frappe.query_reports["Roster vs Actual"] = {
	filters: [
		{ fieldname: "from_date", label: "From", fieldtype: "Date", default: frappe.datetime.add_days(frappe.datetime.get_today(), -7), reqd: 1 },
		{ fieldname: "to_date", label: "To", fieldtype: "Date", default: frappe.datetime.get_today(), reqd: 1 },
		{ fieldname: "shift_location", label: "Shift Location", fieldtype: "Link", options: "Shift Location" },
	],
};
