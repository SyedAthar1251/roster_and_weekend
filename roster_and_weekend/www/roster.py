import frappe
from frappe.boot import load_translations

no_cache = 1


def get_boot():
    bootinfo = frappe._dict(
        {
            "site_name": frappe.local.site,
            "push_relay_server_url": frappe.conf.get("push_relay_server_url") or "",
            "default_route": get_default_route(),
            "user": frappe.session.user,
        }
    )

    bootinfo.lang = frappe.local.lang
    load_translations(bootinfo)

    return bootinfo


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.local.response["location"] = "/login?redirect-to=%2Froster"
        raise frappe.Redirect
    csrf_token = frappe.sessions.get_csrf_token()
    frappe.db.commit()

    context = frappe._dict()
    context.csrf_token = csrf_token
    context.boot = get_boot()
    context.site_name = frappe.local.site
    context.is_login_page = False
    return context


def get_default_route():
    return "/roster"
