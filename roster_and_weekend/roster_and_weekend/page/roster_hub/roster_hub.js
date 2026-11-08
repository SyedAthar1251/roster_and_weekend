frappe.pages["roster-hub"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({ parent: wrapper, title: "Roster Hub", single_column: true });
	const $b = $(page.body);
	const api = (m, args) => frappe.call({ method: "roster_and_weekend.roster_and_weekend.api." + m, args: args || {} }).then((r) => r.message);
	const COL = { Present: "#3fae78", Completed: "#2f6fed", Late: "#e8a317", "Early Exit": "#e8a317", Missing: "#e5484d", Absent: "#e5484d", Upcoming: "#8e99a8" };
	const TABS = { live: "Live board", grid: "Roster grid", ot: "Overtime", queue: "Action queue", mine: "My roster" };
	const isMgr = frappe.user.has_role(["Roster Manager", "HR Manager", "System Manager"]);
	let tab = isMgr ? "live" : "mine", timer = null;
	const f_loc = page.add_field({ fieldname: "loc", label: "Shift Location", fieldtype: "Link", options: "Shift Location", change: () => render() });
	const f_from = page.add_field({ fieldname: "from", label: "From", fieldtype: "Date", default: frappe.datetime.get_today(), change: () => render() });
	const f_to = page.add_field({ fieldname: "to", label: "To", fieldtype: "Date", default: frappe.datetime.add_days(frappe.datetime.get_today(), 6), change: () => render() });
	if (isMgr) {
		page.set_primary_action("New roster plan", () => frappe.new_doc("Roster Plan"));
		page.add_inner_button("Call-out (sick / emergency)", callOut);
	}
	const bar = $('<div class="mb-3"></div>').appendTo($b);
	const body = $('<div></div>').appendTo($b);
	Object.keys(TABS).filter((k) => isMgr || k === "mine").forEach((k) =>
		$(`<button class="btn btn-sm btn-default mr-2" data-t="${k}">${TABS[k]}</button>`).appendTo(bar).on("click", () => { tab = k; render(); }));
	const esc = frappe.utils.escape_html;
	const pill = (s) => `<span style="background:${COL[s] || "#999"};color:#fff;padding:2px 8px;border-radius:10px;font-size:11px">${s}</span>`;
	const hhmm = (t) => (t ? frappe.datetime.str_to_user(t).split(" ").slice(-2).join(" ") : "–");
	const table = (head, rows) => `<div class="table-responsive"><table class="table table-bordered table-sm"><thead><tr>${head.map((h) => `<th>${h}</th>`).join("")}</tr></thead><tbody>${rows.join("") || `<tr><td colspan="${head.length}" class="text-muted">Nothing to show</td></tr>`}</tbody></table></div>`;

	function render() {
		clearInterval(timer);
		bar.find("button").removeClass("btn-primary").filter(`[data-t=${tab}]`).addClass("btn-primary");
		body.html('<div class="text-muted">Loading…</div>');
		({ live, grid, ot, queue, mine })[tab]();
	}
	function live() {
		const LIVE_COLS = ["Employee", "Location", "Shift", "Planned", "In", "Out", "Status", "Late min", "OT min"];
		const drawLive = (d) => {
			const cards = d.summary.map((s) => `<div class="col-sm-3"><div class="card p-2 mb-2"><b>${esc(s.key)}</b><div>Scheduled ${s.scheduled} · In ${s.present} · <span style="color:#e5484d">Missing ${s.missing}</span> · Late ${s.late} · Done ${s.done}</div></div></div>`).join("");
			const rows = d.rows.map((r) => `<tr><td>${esc(r.employee_name || r.employee)}</td><td>${esc(r.shift_location || "")}</td><td>${esc(r.shift_type)}</td><td>${hhmm(r.planned_in)}–${hhmm(r.planned_out)}</td><td>${hhmm(r.actual_in)}</td><td>${hhmm(r.actual_out)}</td><td>${pill(r.status)}</td><td>${r.late_minutes || ""}</td><td>${r.ot_minutes || ""}</td></tr>`);
			return body.html(`<p class="text-muted">Live board for <b>${f_from.get_value()}</b> · change the <b>From</b> date to look at another day · refreshes every 60s</p>` +
				`<div class="row">${cards}</div><p class="text-muted">Open shifts: <b>${d.open_shifts}</b></p>` + table(LIVE_COLS, rows));
		};
		const draw = () => api("get_live_board", { shift_location: f_loc.get_value(), date: f_from.get_value() }).then((d) => {
			if (d.rows.length) return drawLive(d);
			// Nothing published on the selected day: point at the next day that has roster.
			return api("next_roster_date", { from_date: f_from.get_value(), shift_location: f_loc.get_value() }).then((nd) => {
				if (nd && nd !== f_from.get_value()) {
					f_from.set_value(nd);
					frappe.show_alert({ message: `No roster on that day. Showing ${nd} instead.`, indicator: "blue" });
					return;
				}
				return drawLive(d);
			});
		});
		draw(); timer = setInterval(draw, 60000);
	}
	function grid() {
		api("get_roster_grid", { from_date: f_from.get_value(), to_date: f_to.get_value(), shift_location: f_loc.get_value() }).then((rows) => {
			const days = []; for (let d = f_from.get_value(); d <= f_to.get_value(); d = frappe.datetime.add_days(d, 1)) days.push(d);
			const by = {}; rows.forEach((r) => { (by[r.employee_name || r.employee] = by[r.employee_name || r.employee] || {})[r.date] = r; });
			const cell = (r) => !r ? "" : r.entry_type === "Work" ? `<span title="${r.status}${r.acknowledged ? " ✓" : ""}">${esc((r.shift_type || "").slice(0, 6))}</span>` : `<span class="text-muted">${r.entry_type.toUpperCase()}</span>`;
			body.html(table(["Employee"].concat(days.map((d) => d.slice(5))), Object.keys(by).sort().map((n) => `<tr><td>${esc(n)}</td>${days.map((d) => `<td>${cell(by[n][d])}</td>`).join("")}</tr>`)));
		});
	}
	function ot() {
		api("get_ot_summary", { from_date: f_from.get_value(), to_date: f_to.get_value(), shift_location: f_loc.get_value() }).then((rows) =>
			body.html(table(["Employee", "OT hours", "Days with OT", "Days over daily cap"], rows.map((r) => `<tr><td>${esc(r.employee_name)}</td><td>${(r.ot_minutes / 60).toFixed(1)}</td><td>${r.days}</td><td class="${r.over_cap_days ? "text-danger" : ""}">${r.over_cap_days}</td></tr>`))));
	}
	function queue() {
		api("get_queue").then((q) => {
			const sw = q.swaps.map((s) => `<tr><td>${esc(s.requester)} (${esc(s.requester_cell)}) ⇄ ${esc(s.counterpart)} (${esc(s.counterpart_cell)})</td><td>${s.date}</td><td>${esc(s.checks || "")}</td><td><button class="btn btn-xs btn-success" data-a="${s.name}" data-v="1">Approve</button> <button class="btn btn-xs btn-danger" data-a="${s.name}" data-v="0">Reject</button></td></tr>`);
			const os = q.open_shifts.map((o) => `<tr><td>${o.date}</td><td>${esc(o.shift_type)}</td><td>${esc(o.shift_location || "")}</td><td>${o.reason}</td><td><button class="btn btn-xs btn-default" data-o="${o.name}">Find cover</button></td></tr>`);
			body.html(`<h5>Swap requests awaiting approval</h5>${table(["Swap", "Date", "Rule checks", ""], sw)}<h5>Open shifts</h5>${table(["Date", "Shift", "Location", "Reason", ""], os)}<p class="text-muted">Unacknowledged upcoming entries: <b>${q.unacknowledged}</b></p>`);
			body.find("[data-a]").on("click", function () { api("decide_swap", { name: this.dataset.a, approve: this.dataset.v }).then(() => render()); });
			body.find("[data-o]").on("click", function () { api("get_candidates", { open_shift: this.dataset.o }).then((c) => showCover(this.dataset.o, c)); });
		});
	}
	function showCover(osName, cands) {
		const d = new frappe.ui.Dialog({ title: "Cover for " + osName, fields: [{ fieldtype: "HTML", fieldname: "h" }] });
		const html = cands.length ? table(["Employee", "Location", "Rules", ""], cands.map((c) => `<tr><td>${esc(c.employee_name)}</td><td>${esc(c.location || "")}${c.same_location ? "" : " (other site)"}</td><td>${c.ok ? "✔ OK" : esc(c.issues.join("; "))}</td><td><button class="btn btn-xs btn-success" data-e="${c.employee}" ${c.ok ? "" : "disabled"}>Assign (OT)</button></td></tr>`)) : "<p>Nobody eligible. Escalate to the area manager.</p>";
		d.fields_dict.h.$wrapper.html(html);
		d.fields_dict.h.$wrapper.find("[data-e]").on("click", function () { api("fill_open_shift", { open_shift: osName, employee: this.dataset.e }).then(() => { d.hide(); render(); }); });
		d.show();
	}
	function callOut() {
		frappe.prompt([{ fieldname: "employee", label: "Employee", fieldtype: "Link", options: "Employee", reqd: 1 },
			{ fieldname: "date", label: "Date", fieldtype: "Date", default: frappe.datetime.get_today(), reqd: 1 },
			{ fieldname: "reason", label: "Reason", fieldtype: "Select", options: "Sick\nEmergency\nOther", default: "Sick" }],
			(v) => api("call_out", v).then((r) => showCover(r.open_shift, r.candidates)), "Call-out");
	}
	function mine() {
		api("my_roster", { from_date: f_from.get_value(), to_date: f_to.get_value() }).then((rows) => {
			const un = rows.filter((r) => !r.acknowledged).length;
			body.html((un ? `<button class="btn btn-primary btn-sm mb-2" id="ack">Acknowledge roster (${un} day(s))</button>` : '<p class="text-success">✓ Roster acknowledged</p>') +
				table(["Date", "Type", "Shift", "Location", ""], rows.map((r) => `<tr><td>${r.date}</td><td>${r.entry_type}</td><td>${esc(r.shift_type || "")}</td><td>${esc(r.shift_location || "")}</td><td>${["Work", "Off"].includes(r.entry_type) ? `<button class="btn btn-xs btn-default" data-d="${r.date}">Request swap</button>` : ""}</td></tr>`)));
			body.find("#ack").on("click", () => api("acknowledge", { from_date: f_from.get_value(), to_date: f_to.get_value() }).then(() => render()));
			body.find("[data-d]").on("click", function () {
				frappe.prompt([{ fieldname: "counterpart", label: "Swap with (Employee)", fieldtype: "Link", options: "Employee", reqd: 1 }, { fieldname: "reason", label: "Reason", fieldtype: "Small Text" }],
					(v) => api("request_swap", { date: this.dataset.d, counterpart: v.counterpart, reason: v.reason }).then(() => frappe.show_alert({ message: "Swap requested", indicator: "green" })), "Request swap");
			});
		});
	}
	render();
	$(wrapper).on("hide", () => clearInterval(timer));
};
