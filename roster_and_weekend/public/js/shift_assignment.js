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

// Shift Time Exception: show the timing this assignment really has
frappe.ui.form.on("Shift Assignment", {
    refresh(frm) {
        roster_weekend_show_timing(frm);
    },
    shift_type(frm) {
        roster_weekend_show_timing(frm);
    },
    custom_time_exception(frm) {
        roster_weekend_show_timing(frm);
    }
});

function roster_weekend_show_timing(frm) {
    frm.set_intro("");
    if (!frm.doc.shift_type) return;
    frappe.call({
        method: "roster_and_weekend.roster_and_weekend.time_exception.get_effective_timing",
        args: {
            shift_type: frm.doc.shift_type,
            time_exception: frm.doc.custom_time_exception || null
        },
        callback(r) {
            const t = r.message;
            if (!t) return;
            if (frm.doc.custom_time_exception) {
                frm.set_intro(
                    __("Timing for this assignment: {0} to {1} (Shift Type {2} to {3}, exception {4})",
                        [t.start, t.end, t.base_start, t.base_end, frm.doc.custom_time_exception]),
                    "orange"
                );
            } else {
                frm.set_intro(__("Timing: {0} to {1}", [t.start, t.end]), "blue");
            }
        }
    });
}