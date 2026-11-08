import frappe


def redirect_roster():
	try:
		path = frappe.request.path
	except Exception:
		return

	if path == "/hr/roster" or path.startswith("/hr/roster/"):
		frappe.local.response["redirect"] = "/roster"
