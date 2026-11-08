frappe.ui.form.on('Roster Plan', {
    refresh(frm) {
        if (frm.is_new()) {
            frm.enable_save();
            frm.clear_custom_buttons();
            return;
        }

        // Published plans: entire form is read-only (UI + server-side validate).
        if (frm.doc.status === 'Published') {
            frm.disable_form();
            frm.clear_custom_buttons();
            frm.add_custom_button(__('Open Roster Hub'), () => {
                window.location.href = '/app/roster-hub';
            });
            frm.add_custom_button(__('Repeat Existing Roster'), repeat_dialog);
            frm.add_custom_button(__('Cancel'), cancel);
            return;
        }

        // Cancelled plans: read-only, no buttons.
        if (frm.doc.status === 'Cancelled') {
            frm.disable_form();
            frm.clear_custom_buttons();
            return;
        }

        // Saved (Draft) document: Save stays hidden until a field is edited.
        if (frm.doc.__unsaved) {
            frm.enable_save();
        } else {
            frm.disable_save();
        }
        frm.clear_custom_buttons();

        if (frm.doc.status === 'Draft') {
            if (frm.doc.generated_count > 0) {
                frm.add_custom_button(__('Publish'), publish);
            } else {
                frm.add_custom_button(__('Generate'), generate);
            }
        }
        // Cancel and Repeat Existing Roster are intentionally NOT added for Draft plans.
        // They are only shown in the Published branch above.
    },

    dirty(frm) {
        if (frm.doc.status !== 'Published') {
            frm.enable_save();
        }
    },

    // Runs on EVERY save path (Save button, Ctrl+S, menu, auto-save).
    before_save(frm) {
        if (frm.doc.status === 'Published') return;

        // Second pass: user already confirmed, let the save go through.
        if (frm.__conflicts_checked) {
            frm.__conflicts_checked = false;
            return;
        }

        const employees = (frm.doc.employees || []).map(e => e.employee).filter(Boolean);
        if (!employees.length || !frm.doc.from_date || !frm.doc.to_date) return;

        // Stop this save; it is re-triggered after the conflict check.
        frappe.validated = false;
        frappe.call({
            method: 'roster_and_weekend.roster_and_weekend.doctype.roster_plan.roster_plan.check_conflicts_for_dates',
            args: {
                employees: employees,
                from_date: frm.doc.from_date,
                to_date: frm.doc.to_date,
                plan: frm.is_new() ? null : frm.doc.name,
            },
            freeze: true,
            callback(r) {
                const result = r.message || {};
                const proceed = (confirmed) => {
                    frm.doc.confirmed_conflicts = JSON.stringify(confirmed || []);
                    frm.__conflicts_checked = true;
                    frm.save();
                };
                if (!result.conflict_pairs || !result.conflict_pairs.length) {
                    proceed([]);
                } else {
                    show_conflict_dialog(frm, result, proceed);
                }
            }
        });
    }
});

function show_conflict_dialog(frm, result, on_continue) {
    var conflict_lines = [];
    var confirmed_conflicts = [];
    (result.conflict_pairs || []).forEach(function (cp) {
        conflict_lines.push(
            '<b>' + frappe.utils.escape_html(cp.employee_name) + '</b> on ' + cp.date +
            ' from plan "' + frappe.utils.escape_html(cp.plan_label) + '"'
        );
        confirmed_conflicts.push({ employee: cp.employee, date: cp.date, plan: cp.plan });
    });
    var safe_names = (result.safe || []).map(function (e) { return e.label; }).join(', ');
    var msg = '<p>The following employee(s) already have Published roster entries for the selected date range:</p>' +
        '<ul><li>' + conflict_lines.join('</li><li>') + '</li></ul>' +
        '<p>These dates will be skipped during generation (existing roster will not be modified).</p>' +
        '<p>Safe to proceed with: ' + frappe.utils.escape_html(safe_names || 'none') + '</p>';

    // frappe.warn shows a primary "Continue" button and a "Cancel" button.
    frappe.warn(
        __('Roster Conflicts Found'),
        msg,
        function () {
            on_continue(confirmed_conflicts);
        },
        __('Continue')
    );
}

// Generate directly, no confirmation dialog. Conflicts were already confirmed at Save time
// and are stored in confirmed_conflicts; dates held by other published plans are skipped by the engine.
function generate() {
    var frm = cur_frm;
    var confirmed_conflicts = [];
    try {
        confirmed_conflicts = JSON.parse(frm.doc.confirmed_conflicts || '[]');
    } catch (e) {}
    return regenerate({ skip_conflicts: confirmed_conflicts });
}

function regenerate(options) {
    var frm = cur_frm;
    var skip_conflicts = (options && options.skip_conflicts) ? options.skip_conflicts : [];
    var skip_employees = (options && options.skip_employees) ? options.skip_employees : [];
    var args = {};
    if (skip_employees && skip_employees.length) args.skip_employees = skip_employees;
    if (skip_conflicts && skip_conflicts.length) args.skip_conflicts = skip_conflicts;
    return frm.call('generate', args).then(r => {
        var msg = (r.message || []).join('\n');
        if (skip_conflicts.length) {
            msg += '\n\nSkipped ' + skip_conflicts.length + ' conflicting date(s) from other plans.';
        }
        frappe.msgprint(msg || 'Entries generated');
        frm.reload_doc();
    }).catch(err => frappe.msgprint(err.message || 'Generate failed'));
}

// Listens (once) for progress events sent by engine.publish_plan while it runs in the background.
function register_publish_listener() {
    if (frappe.__roster_publish_listener) return;
    frappe.__roster_publish_listener = true;
    frappe.realtime.on('roster_publish_progress', function (data) {
        var frm = cur_frm;
        if (!frm || !data || frm.doc.name !== data.plan) return;
        if (data.done) {
            finish_publish(frm, data.success, data.message);
        } else {
            frappe.show_progress(__('Publishing Roster'), data.percent, 100, data.description);
        }
    });
}

// Runs once per publish: fills the bar to 100%, hides it, then shows the success (or error) message.
function finish_publish(frm, success, message) {
    if (frm.__publish_finished) return;
    frm.__publish_finished = true;
    if (success) {
        frappe.show_progress(__('Publishing Roster'), 100, 100, __('Completed'));
    }
    setTimeout(function () {
        frappe.hide_progress();
        frm.reload_doc().then(function () {
            if (success) {
                var skipped = frm.__publish_skipped || 0;
                var msg = __('Roster published successfully.');
                if (skipped) {
                    msg += '<br>' + __('{0} previously confirmed conflict date(s) were skipped.', [skipped]);
                }
                frappe.msgprint({ title: __('Success'), indicator: 'green', message: msg });
            } else {
                frappe.msgprint({
                    title: __('Publish Failed'),
                    indicator: 'red',
                    message: message || __('Publish failed. Please check the Error Log.')
                });
            }
        });
    }, success ? 800 : 0);
}

function publish() {
    var frm = cur_frm;
    register_publish_listener();
    frm.__publish_finished = false;
    frm.clear_custom_buttons();
    frm.disable_save();
    var confirmed_conflicts = [];
    try {
        confirmed_conflicts = JSON.parse(frm.doc.confirmed_conflicts || '[]');
    } catch (e) {}
    frm.__publish_skipped = confirmed_conflicts.length;
    var args = {};
    if (confirmed_conflicts.length) args.skip_conflicts = confirmed_conflicts;

    frappe.show_progress(__('Publishing Roster'), 0, 100, __('Starting…'));
    return frm.call('publish', args).then(function () {
        // Progress and the final success message arrive through realtime events.
        // This poll is only a fallback in case the realtime event is missed.
        poll_publish_status(frm, 0);
    }).catch(function (err) {
        frappe.hide_progress();
        frappe.msgprint(err.message || 'Publish failed');
        frm.refresh();
    });
}

function poll_publish_status(frm, count) {
    if (frm.__publish_finished) return;
    if (count >= 120) {
        frappe.hide_progress();
        frappe.msgprint('Publish is taking longer than expected. Check the Job or reload later.');
        return;
    }
    frappe.timeout(5).then(function () {
        if (frm.__publish_finished) return;
        frappe.db.get_value('Roster Plan', frm.doc.name, 'status').then(function (r) {
            var status = r.message && r.message.status;
            if (status === 'Published') {
                finish_publish(frm, true);
            } else if (status === 'Cancelled') {
                finish_publish(frm, false, __('Plan was cancelled.'));
            } else {
                poll_publish_status(frm, count + 1);
            }
        });
    });
}

function cancel() {
    var frm = cur_frm;
    frappe.confirm(
        `Cancel <b>${frappe.utils.escape_html(frm.doc.name)}</b> (${frm.doc.from_date} to ${frm.doc.to_date})?<br><br>` +
        `All its Roster Entries will be marked <b>Cancelled</b> and the linked Shift Assignments will be cancelled. ` +
        `Nothing is deleted.`,
        () => {
            frm.call('cancel_plan')
                .then(r => {
                    var result = r.message;
                    if (result && result.errors && result.errors.length > 0) {
                        frappe.msgprint('Errors during cancellation: ' + result.errors.join(', '));
                    } else {
                        frappe.msgprint('Plan cancelled. Roster Entries marked Cancelled and Shift Assignments cancelled.');
                    }
                    frm.reload_doc();
                })
                .catch(err => {
                    frappe.msgprint(err.message || 'Cancel failed');
                    frm.reload_doc();
                });
        }
    );
}

function repeat_dialog() {
    var frm = cur_frm;
    var today = frappe.datetime.get_today();
    frappe.prompt(
        [
            {
                fieldname: 'from_date',
                fieldtype: 'Date',
                label: 'Start Date',
                reqd: 1,
                default: today
            },
            {
                fieldname: 'to_date',
                fieldtype: 'Date',
                label: 'End Date',
                reqd: 1,
                default: frappe.datetime.add_days(today, 13)
            }
        ],
        function (data) {
            var employees = (frm.doc.employees || []).map(function (e) { return e.employee; }).filter(Boolean);

            var do_repeat = function (confirmed_conflicts) {
                frm.call('repeat', {
                    from_date: data.from_date,
                    to_date: data.to_date,
                    confirmed_conflicts: JSON.stringify(confirmed_conflicts || [])
                }).then(function (r) {
                    var new_name = r.message;
                    frappe.confirm(
                        "New roster plan <b>" + new_name + "</b> created in Draft status.<br><br>Open it now to generate and publish?",
                        function () {
                            window.open('/app/roster-plan/' + new_name, '_blank');
                        },
                        function () {
                            frappe.msgprint("Plan created as Draft. Open it and click Generate + Publish when ready.");
                        }
                    );
                }).catch(function (err) {
                    frappe.msgprint(err.message || 'Repeat failed');
                });
            };

            if (!employees.length) {
                do_repeat([]);
                return;
            }

            // Same conflict check as Save, run against the NEW date range.
            frappe.call({
                method: 'roster_and_weekend.roster_and_weekend.doctype.roster_plan.roster_plan.check_conflicts_for_dates',
                args: {
                    employees: employees,
                    from_date: data.from_date,
                    to_date: data.to_date,
                    plan: frm.doc.name
                },
                freeze: true,
                callback: function (r) {
                    var result = r.message || {};
                    if (!result.conflict_pairs || !result.conflict_pairs.length) {
                        do_repeat([]);
                    } else {
                        show_conflict_dialog(frm, result, do_repeat);
                    }
                }
            });
        },
        __('Repeat Existing Roster'),
        'Repeat'
    );
}