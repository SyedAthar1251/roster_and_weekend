// Shift Type: Auto Attendance setup check.
//
// On Save: sends the unsaved values to the server checks (roster_and_weekend/shift_type_checks.py).
//   - no problems  -> the save continues as normal.
//   - problems     -> the save is cancelled and a dialog lists each problem with a suggested value.
//                     "Apply and Save" writes the values into the form and saves once.
// The server runs the same checks again in Shift Type validate, so nothing here can be bypassed.
//
// On refresh: shows non-blocking warnings (stuck last sync, old start date, ...) as an orange banner.
//
// "Mark Attendance" button: replaces the stock button. Runs auto attendance and shows a report of what was
// marked and, for everything that was not, the reason and the solution (roster_and_weekend/attendance_diagnosis.py).

frappe.provide("roster_and_weekend.shift_checks");

roster_and_weekend.shift_checks = (() => {
	const METHOD = "roster_and_weekend.roster_and_weekend.shift_type_checks.check_shift_type";
	const PASS_FLAG = "__shift_checks_pass";

	function esc(v) {
		return frappe.utils.escape_html(v == null ? "" : String(v));
	}

	function resume(frm) {
		frm[PASS_FLAG] = true;
		frm.save();
	}

	function open_dialog(frm, errors) {
		const fields = [
			{
				fieldtype: "HTML",
				options: `<p>${esc(
					__(
						"Auto attendance will not work correctly with the current values. Check the suggested values below, change them if needed, then click Apply and Save."
					)
				)}</p>`,
			},
		];
		const added = {};

		errors.forEach((e) => {
			fields.push({
				fieldtype: "HTML",
				options: `<div class="text-danger" style="margin-top:10px"><b>${esc(e.label)}</b>: ${esc(
					e.message
				)}</div>`,
			});
			const has_value = e.suggested_value !== null && e.suggested_value !== undefined;
			if (!has_value || added[e.fieldname]) return;
			added[e.fieldname] = true;

			const df = (frm.fields_dict[e.fieldname] || {}).df || {};
			fields.push({
				fieldname: e.fieldname,
				fieldtype: df.fieldtype || "Data",
				label: __("Suggested value"),
				default: e.suggested_value,
				description: e.suggestion || "",
			});
		});

		const editable = Object.keys(added);
		const dialog = new frappe.ui.Dialog({
			title: __("Auto Attendance Setup Problem"),
			fields,
			primary_action_label: editable.length ? __("Apply and Save") : __("Close"),
			primary_action(values) {
				if (!editable.length) {
					dialog.hide();
					return;
				}
				dialog.hide();
				const jobs = editable.map((fn) => frm.set_value(fn, values[fn]));
				Promise.all(jobs).then(() => resume(frm));
			},
		});
		dialog.show();
	}

	function before_save(frm) {
		if (frm[PASS_FLAG]) {
			frm[PASS_FLAG] = false;
			return;
		}
		if (!frm.doc.enable_auto_attendance) return;

		// Cancel this save attempt; it is restarted once the checks pass or values are applied.
		frappe.validated = false;
		frappe.call({
			method: METHOD,
			args: { doc: frm.doc },
			freeze: true,
			freeze_message: __("Checking auto attendance setup..."),
			callback(r) {
				const errors = ((r && r.message) || {}).errors || [];
				if (errors.length) open_dialog(frm, errors);
				else resume(frm);
			},
			// If the check itself cannot run, let the save continue; the server validate still enforces it.
			error() {
				resume(frm);
			},
		});
	}

	function show_warnings(frm) {
		frm.set_intro("");
		if (!frm.doc.enable_auto_attendance || frm.doc.__islocal) return;
		frappe.call({
			method: METHOD,
			args: { doc: frm.doc },
			callback(r) {
				const warnings = ((r && r.message) || {}).warnings || [];
				if (!warnings.length) return;
				const html = warnings
					.map(
						(w) =>
							`<div><b>${esc(w.label)}</b>: ${esc(w.message)}${
								w.suggestion ? ` <i>${esc(w.suggestion)}</i>` : ""
							}</div>`
					)
					.join("");
				frm.set_intro(html, "orange");
			},
		});
	}

	return { before_save, show_warnings };
})();

roster_and_weekend.mark_attendance = (() => {
	const REPORT = "roster_and_weekend.roster_and_weekend.attendance_diagnosis.process_with_report";
	const PREVIEW = "roster_and_weekend.roster_and_weekend.attendance_diagnosis.preview_attendance";
	const FIXES = "roster_and_weekend.roster_and_weekend.attendance_diagnosis.run_fixes";
	const ACTION_LABEL = {
		cancel_conflicting_absent: __("Cancel the conflicting Absent records (other shift)"),
		relink_checkins: __("Re-link check-ins to the shift assigned on that date"),
		unskip_checkins: __("Un-skip check-ins that HRMS skipped because of an error"),
	};
	const KIND_COLOR = { fix: "#c0392b", warn: "#d68910", info: "#7f8c8d" };

	function esc(v) {
		return frappe.utils.escape_html(v == null ? "" : String(v));
	}

	function replace_stock_button(frm) {
		if (frm.doc.__islocal) return;
		// HRMS adds its own button in its refresh handler; ours runs after it (next tick) and replaces it.
		setTimeout(() => {
			frm.remove_custom_button(__("Mark Attendance"));
			frm.add_custom_button(__("Mark Attendance"), () => start(frm));
		}, 0);
	}

	function start(frm) {
		if (frm.is_dirty()) {
			frappe.msgprint(__("Please save the Shift Type first."));
			return;
		}
		if (!frm.doc.enable_auto_attendance) {
			frm.scroll_to_field("enable_auto_attendance");
			frappe.throw(__("Please Enable Auto Attendance and complete the setup first."));
		}
		// Read-only preview first, so nothing is created before the user agrees.
		frappe.call({
			method: PREVIEW,
			args: { shift_type: frm.doc.name },
			freeze: true,
			freeze_message: __("Checking what will be marked..."),
			callback(r) {
				confirm_run(frm, r.message || {});
			},
		});
	}

	function confirm_run(frm, p) {
		if (p.status === "config") {
			frappe.msgprint({ title: __("Mark Attendance"), message: esc(p.message), indicator: "orange" });
			return;
		}
		const parts = [];
		if (p.from_date) {
			parts.push(`<div><b>${esc(__("Period"))}:</b> ${esc(p.from_date)} ${esc(__("to"))} ${esc(p.to_date)}</div>`);
		}
		parts.push(`<div><b>${esc(__("Employees"))}:</b> ${esc(p.employees)}</div>`);
		parts.push(
			`<div><b>${esc(__("Days with check-ins"))}:</b> ${esc(p.checkin_days)} ${esc(
				__("(marked Present, or Absent / Half Day by working hours)")
			)}</div>`
		);
		parts.push(
			`<div><b>${esc(__("Working days without check-ins"))}:</b> ${
				p.absent === null || p.absent === undefined
					? esc(__("too many employees to count here"))
					: esc(p.absent) + " " + esc(__("(marked Absent)"))
			}</div>`
		);
		parts.push(
			`<div class="text-muted" style="margin-top:6px">${esc(
				__("Weekly offs and holidays are skipped. Existing attendance is not changed.")
			)}</div>`
		);
		frappe.confirm(
			`<div style="margin-bottom:8px">${esc(__("Mark attendance for {0}?", [frm.doc.name]))}</div>${parts.join("")}`,
			() => run(frm)
		);
	}

	function run(frm) {
		frappe.call({
			method: REPORT,
			args: { shift_type: frm.doc.name },
			freeze: true,
			freeze_message: __("Marking attendance..."),
			callback(r) {
				show_report(frm, r.message || {});
			},
		});
	}

	function finding_html(f) {
		const color = KIND_COLOR[f.kind] || KIND_COLOR.info;
		const samples = (f.samples || []).length
			? `<div class="text-muted">${esc(__("Dates"))}: ${esc(f.samples.join(", "))}${
					f.count > f.samples.length ? " ..." : ""
			  }</div>`
			: "";
		const details = (f.details || []).length
			? `<div class="text-muted" style="margin-top:2px">${f.details.map(esc).join("<br>")}</div>`
			: "";
		return `<div style="border-left:4px solid ${color};padding:6px 10px;margin:8px 0;background:var(--control-bg, #f7f7f7)">
			<div><b>${esc(f.title)}</b> <span class="text-muted">(${esc(f.count)} ${esc(__("affected"))}, ${esc(f.employees)} ${esc(
			__("employee(s)")
		)})</span></div>
			${samples}${details}
			<div style="margin-top:4px">${esc(__("Solution"))}: ${esc(f.solution)}</div>
		</div>`;
	}

	function unique_sorted(list) {
		return Array.from(new Set(list || [])).sort();
	}

	// "2026-10-01, 2026-10-02" for one employee; "12 records, 2026-10-01 to 2026-10-30" for many.
	function dates_text(dates, count, many) {
		const d = unique_sorted(dates);
		if (!d.length) return "";
		if (many || d.length > 31) return `${count} ${__("records")}, ${d[0]} ${__("to")} ${d[d.length - 1]}`;
		return d.join(", ");
	}

	function line(label, value) {
		return `<div style="margin:3px 0"><b>${esc(label)}:</b> ${esc(value)}</div>`;
	}

	// Weekly offs and holidays that were skipped. Shown in both views.
	function skipped_days_html(res, findings) {
		const many = (res.employees || 0) > 1;
		let html = "";
		const wk = findings.find((f) => f.code === "weekend");
		if (wk) html += line(__("Weekly off, skipped") + ` (${wk.count})`, dates_text(wk.samples, wk.count, many));
		const hol = findings.find((f) => f.code === "holiday");
		if (hol) html += line(__("Holiday, skipped") + ` (${hol.count})`, dates_text(hol.samples, hol.count, many));
		return html;
	}

	// Everything worked: only what was marked and which days were weekly offs / holidays.
	function simple_html(res, findings) {
		const many = (res.employees || 0) > 1;
		const present = (res.marked || {}).Present || 0;
		const absent = (res.marked || {}).Absent || 0;
		const md = res.marked_dates || {};
		const by = (code) => findings.find((f) => f.code === code);
		let html = "";

		if (!present && !absent) {
			html += `<div style="font-size:14px"><b>${esc(__("Nothing new to mark."))}</b> ${esc(
				__("Every working day in the range already has attendance.")
			)}</div>`;
		} else {
			html += `<div style="font-size:14px;margin-bottom:4px"><b>${esc(__("Attendance marked"))}</b></div>`;
			if (present) html += line(__("Present") + ` (${present})`, dates_text(md.Present, present, many));
			if (absent) html += line(__("Absent") + ` (${absent})`, dates_text(md.Absent, absent, many));
		}
		html += skipped_days_html(res, findings);
		const notes = findings.filter((f) => f.code === "checkin_on_weekend" || f.code === "checkin_on_holiday");
		notes.forEach((f) => {
			html += `<div class="text-muted" style="margin-top:6px">${esc(f.title)} (${esc(f.count)}). ${esc(f.solution)}</div>`;
		});
		return html;
	}

	function show_report(frm, res) {
		if (res.status === "config" || res.status === "queued") {
			frappe.msgprint({ title: __("Mark Attendance"), message: esc(res.message), indicator: "orange" });
			return;
		}
		if (res.status === "error") {
			frappe.msgprint({
				title: __("Mark Attendance failed"),
				indicator: "red",
				message:
					esc(res.message) +
					(res.error_log
						? `<br><br>${esc(__("Details"))}: <a href="/app/error-log/${encodeURIComponent(res.error_log)}">${esc(
								res.error_log
						  )}</a>`
						: ""),
			});
			return;
		}

		const findings = res.findings || [];
		const problems = findings.filter((f) => f.kind === "fix" || f.kind === "warn");
		const order = { fix: 0, warn: 1 };
		problems.sort((a, b) => (order[a.kind] ?? 2) - (order[b.kind] ?? 2));

		const present = (res.marked || {}).Present || 0;
		const absent = (res.marked || {}).Absent || 0;
		let html;
		const actions = [];

		if (!res.has_problems) {
			html = simple_html(res, findings);
		} else {
			html = `<div style="font-size:14px;margin-bottom:4px"><b>${esc(__("Marked now"))}:</b> ${esc(present)} ${esc(
				__("Present")
			)}, ${esc(absent)} ${esc(__("Absent"))}</div>`;
			html += `<div style="margin-top:6px"><b>${esc(__("Some attendance could not be marked. Why:"))}</b></div>`;
			html += problems.map(finding_html).join("");
			html += `<div style="margin-top:10px">${skipped_days_html(res, findings)}</div>`;
			problems.forEach((f) => {
				if (f.action && !actions.includes(f.action)) actions.push(f.action);
			});
		}
		if (res.truncated) {
			html += `<div class="text-warning" style="margin-top:6px">${esc(
				__("Only the first 500 employees are shown in this report. Attendance itself was processed for all.")
			)}</div>`;
		}

		const fields = [{ fieldtype: "HTML", options: html }];
		if (actions.length) {
			fields.push({ fieldtype: "Section Break", label: __("Fix and process again") });
			actions.forEach((a) =>
				fields.push({ fieldname: a, fieldtype: "Check", label: ACTION_LABEL[a] || a, default: 1 })
			);
		}

		const dialog = new frappe.ui.Dialog({
			title: __("Mark Attendance: {0}", [frm.doc.name]),
			size: "large",
			fields,
			primary_action_label: actions.length ? __("Apply selected and process again") : __("Close"),
			primary_action(values) {
				if (!actions.length) {
					dialog.hide();
					return;
				}
				const chosen = actions.filter((a) => values[a]);
				if (!chosen.length) {
					frappe.msgprint(__("Tick at least one fix, or close this window."));
					return;
				}
				const go = () => {
					dialog.hide();
					apply_fixes(frm, chosen);
				};
				if (chosen.includes("cancel_conflicting_absent")) {
					frappe.confirm(
						__("This cancels Absent attendance records that belong to another shift. Continue?"),
						go
					);
				} else {
					go();
				}
			},
		});
		dialog.show();
	}

	function apply_fixes(frm, chosen) {
		frappe.call({
			method: FIXES,
			args: { shift_type: frm.doc.name, actions: chosen },
			freeze: true,
			freeze_message: __("Applying fixes..."),
			callback(r) {
				const res = r.message || {};
				const parts = [];
				let changed = 0;
				const c = res.cancel_conflicting_absent;
				if (c) {
					changed += c.cancelled;
					parts.push(__("{0} Absent record(s) cancelled", [c.cancelled]));
					if (c.kept_for_manual_review) parts.push(__("{0} kept for manual review", [c.kept_for_manual_review]));
					if ((c.failed || []).length) parts.push(__("{0} could not be cancelled: {1}", [c.failed.length, c.failed[0]]));
				}
				const l = res.relink_checkins;
				if (l) {
					changed += l.relinked;
					parts.push(__("{0} check-in(s) re-linked", [l.relinked]));
					if (l.unchanged) parts.push(__("{0} could not be re-linked", [l.unchanged]));
				}
				const u = res.unskip_checkins;
				if (u) {
					changed += u.unskipped;
					parts.push(__("{0} check-in(s) un-skipped", [u.unskipped]));
				}

				// Nothing changed: running the report again would show the same screen, so stop here.
				if (!changed) {
					frappe.msgprint({
						title: __("Nothing was changed"),
						indicator: "orange",
						message: esc(parts.join(", ")) + "<br><br>" + esc(
							__("The fix could not apply. Click Mark Attendance again to see the updated reason.")
						),
					});
					return;
				}
				frappe.show_alert({ message: parts.join(", "), indicator: "green" }, 7);
				run(frm);
			},
		});
	}

	return { replace_stock_button };
})();

frappe.ui.form.on("Shift Type", {
	refresh(frm) {
		roster_and_weekend.shift_checks.show_warnings(frm);
		roster_and_weekend.mark_attendance.replace_stock_button(frm);
	},
	before_save(frm) {
		return roster_and_weekend.shift_checks.before_save(frm);
	},
});