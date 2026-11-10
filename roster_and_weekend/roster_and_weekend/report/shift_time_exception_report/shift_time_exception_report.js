frappe.query_reports["Shift Time Exception Report"] = {
    "filters": [
        {
            "fieldname": "company",
            "label": __("Company"),
            "fieldtype": "Link",
            "options": "Company",
            "reqd": 0
        },
        {
            "fieldname": "branch",
            "label": __("Branch"),
            "fieldtype": "Link",
            "options": "Branch",
            "reqd": 0
        },
        {
            "fieldname": "department",
            "label": __("Department"),
            "fieldtype": "Link",
            "options": "Department",
            "reqd": 0
        },
        {
            "fieldname": "shift_type",
            "label": __("Shift Type"),
            "fieldtype": "Link",
            "options": "Shift Type",
            "reqd": 0
        },
        {
            "fieldname": "shift_time_exception",
            "label": __("Shift Time Exception"),
            "fieldtype": "Link",
            "options": "Shift Time Exception",
            "reqd": 0
        }
    ]
};
