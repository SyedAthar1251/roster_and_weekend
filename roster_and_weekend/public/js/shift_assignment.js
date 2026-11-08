frappe.ui.form.on("Shift Assignment", {
    custom_is_default_shift(frm) {

        if (!frm.doc.custom_is_default_shift) {
            return;
        }

        frappe.call({
            method: "roster_and_weekend.shift_assignment.check_default_shift",
            args: {
                employee: frm.doc.employee,
                current_doc: frm.doc.name
            },
            callback(r) {

                if (!r.message) return;

                frappe.confirm(
                    __("Another default shift exists. Replace it?"),
                    () => {

                        frappe.call({
                            method: "roster_and_weekend.shift_assignment.replace_default_shift",
                            args: {
                                employee: frm.doc.employee,
                                old_shift: r.message.name
                            }
                        });

                    },
                    () => {
                        frm.set_value("custom_is_default_shift", 0);
                    }
                );
            }
        });
    }
});
