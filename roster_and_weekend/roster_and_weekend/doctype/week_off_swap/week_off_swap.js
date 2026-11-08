// Copyright (c) 2026, neotec.ai and contributors
// For license information, please see license.txt

frappe.ui.form.on("Week Off Swap", {
    refresh(frm) {
        frm.trigger("set_field_readonly");
    },

    set_field_readonly(frm) {
        if (frm.doc.docstatus === 1) {
            frm.read_only();
        }
    },
});
