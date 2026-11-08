const WEEKDAYS = ["Sunday", "Monday", "Tuesday", "Wednesday",
    "Thursday", "Friday", "Saturday"];

frappe.ui.form.on("Roster Pattern", {
    cycle_days: function (frm) {
        const cycle_days = parseInt(frm.doc.cycle_days, 10);
        if (isNaN(cycle_days) || cycle_days < 1) return;

        const existing = new Set(
            (frm.doc.days || []).map((d) => d.day_no)
        );

        for (let i = 1; i <= cycle_days; i++) {
            if (!existing.has(i)) {
                const child = frappe.model.add_child(
                    frm.doc,
                    "Roster Pattern Day",
                    "days"
                );
                child.day_no = i;
                child.day_type = "Work";
                child.shift_type = "";
                child.weekday = WEEKDAYS[(i - 1) % 7];
            } else {
                (frm.doc.days || []).forEach((d) => {
                    if (d.day_no === i) {
                        d.weekday = WEEKDAYS[(i - 1) % 7];
                    }
                });
            }
        }

        // Remove excess rows if cycle was shortened
        const to_remove = (frm.doc.days || []).filter(
            (d) => d.day_no > cycle_days
        );
        if (to_remove.length) {
            const has_user_values = to_remove.some(
                (d) => d.day_type !== "Work" || d.shift_type
            );
            if (has_user_values) {
                frappe.msgprint(
                    `Reducing cycle days to ${cycle_days} would remove ${to_remove.length} day(s) with user-entered values. Please review and remove them manually before saving.`
                );
                return;
            }
            to_remove.forEach((d) => {
                frappe.model.remove_child(
                    frm.doc,
                    "Roster Pattern Day",
                    d.name
                );
            });
        }

        frm.refresh_field("days");
    },
});
