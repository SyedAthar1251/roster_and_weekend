import frappe


def _log(user, subject, message):
	if not user:
		return
	try:
		frappe.get_doc({"doctype": "Notification Log", "for_user": user, "type": "Alert",
			"subject": subject, "email_content": message}).insert(ignore_permissions=True)
	except Exception:
		frappe.log_error(title="Roster notify failed")


def to_employee(employee, subject, message):
	user, mobile = frappe.db.get_value("Employee", employee, ["user_id", "cell_number"]) or (None, None)
	_log(user, subject, message)
	method = frappe.get_cached_doc("Roster Settings").whatsapp_method
	if method and mobile:
		try:
			frappe.get_attr(method)(mobile, f"{subject}\n{message}")
		except Exception:
			frappe.log_error(title="Roster WhatsApp hook failed")


def to_managers(subject, message):
	users = frappe.get_all("Has Role", filters={"role": "Roster Manager", "parenttype": "User"}, pluck="parent")
	for u in set(users) - {"Administrator"}:
		_log(u, subject, message)
