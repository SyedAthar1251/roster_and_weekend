frappe.pages["roster-report"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({ parent: wrapper, title: "Roster Report", single_column: true });

	const CSS = `
	.rcr{--bg:#f3f5f7;--cd:#fff;--tx:#18222e;--mu:#667384;--bd:#dfe5eb;--ac:#0f766e;--acbg:#e3f3f1;--warn:#9a6700;--warnbg:#fcf1d6;--bad:#c8352f;--badbg:#fbe6e4;--ok:#23794f;--okbg:#e0f3e8;--O:#e8ecf0;--we:rgba(120,130,150,.08);
		background:var(--bg);color:var(--tx);padding:12px;max-width:1500px;margin:0 auto;font-size:13px;box-sizing:border-box}
	[data-theme="dark"] .rcr{--bg:#11161c;--cd:#1a222b;--tx:#e6ebf1;--mu:#93a0b0;--bd:#2b3643;--ac:#35b8a9;--acbg:#14302d;--warn:#e0b04c;--warnbg:#3a2f14;--bad:#ef6a64;--badbg:#3b1d1c;--ok:#4cc38a;--okbg:#14301f;--O:#242d38;--we:rgba(160,170,190,.07)}
	.rcr *{box-sizing:border-box}
	.rcr .c{background:var(--cd);border:1px solid var(--bd);border-radius:10px;padding:12px 14px;margin-bottom:12px}
	.rcr h3{margin:0 0 8px;font-size:14px;font-weight:600}
	.rcr .r{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
	.rcr .sp{flex:1}
	.rcr .mu{color:var(--mu)}
	.rcr .ok{color:var(--ok)} .rcr .no{color:var(--bad);font-weight:600} .rcr .wn{color:var(--warn)}
	.rcr button,.rcr select,.rcr input{font:inherit;color:var(--tx);background:var(--cd);border:1px solid var(--bd);border-radius:7px;padding:4px 9px;height:30px}
	.rcr button{cursor:pointer}
	.rcr button:hover{border-color:var(--ac)}
	.rcr button:focus-visible,.rcr select:focus-visible,.rcr input:focus-visible{outline:2px solid var(--ac);outline-offset:1px}
	.rcr .seg{display:inline-flex}
	.rcr .seg button{border-radius:0;margin-left:-1px}
	.rcr .seg button:first-child{border-radius:7px 0 0 7px;margin-left:0}
	.rcr .seg button:last-child{border-radius:0 7px 7px 0}
	.rcr .seg button.on,.rcr button.on{background:var(--ac);border-color:var(--ac);color:#fff}
	.rcr .tabs{border-bottom:1px solid var(--bd);margin:-4px 0 10px;gap:0}
	.rcr .tabs button{border:none;background:none;border-bottom:2px solid transparent;border-radius:0;height:34px;color:var(--mu);font-weight:500;padding:0 14px}
	.rcr .tabs button.on{color:var(--ac);border-bottom-color:var(--ac);background:none}
	.rcr .fl{display:inline-flex;align-items:center;gap:6px;color:var(--mu)}
	.rcr .fl input{color-scheme:light dark}
	.rcr input[type=search]{min-width:200px}
	.rcr .note{padding:8px 12px;border-radius:8px;background:var(--warnbg);color:var(--warn);margin-bottom:12px}
	.rcr .msg{padding:22px;text-align:center;color:var(--mu)}
	/* summary + kpis */
	.rcr .head{display:flex;gap:16px;flex-wrap:wrap;align-items:baseline;justify-content:space-between;margin-bottom:10px}
	.rcr .head b{font-size:16px}
	.rcr .kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:10px;margin-bottom:12px}
	.rcr .kpi{background:var(--cd);border:1px solid var(--bd);border-radius:10px;padding:10px 12px}
	.rcr .kpi .v{font-size:22px;font-weight:600;line-height:1.2}
	.rcr .kpi .l{color:var(--mu);font-size:12px}
	.rcr .kpi.bad{border-color:var(--bad)} .rcr .kpi.bad .v{color:var(--bad)}
	.rcr .kpi.warn .v{color:var(--warn)}
	.rcr .pb{height:6px;border-radius:4px;background:var(--O);overflow:hidden;margin:6px 0}
	.rcr .pb i{display:block;height:100%;background:var(--ac)}
	.rcr .steps{display:flex;gap:6px;flex-wrap:wrap}
	.rcr .steps div{padding:5px 12px;border-radius:14px;background:var(--O);color:var(--mu)}
	.rcr .steps .d{background:var(--acbg);color:var(--ac);font-weight:600}
	.rcr .steps .a{outline:2px solid var(--ac);color:var(--tx)}
	.rcr .cols{display:grid;grid-template-columns:repeat(auto-fit,minmax(340px,1fr));gap:12px;margin-bottom:12px}
	.rcr .cols .c{margin:0}
	.rcr .li{display:flex;justify-content:space-between;gap:8px;padding:6px 0;border-bottom:1px solid var(--bd)}
	.rcr .li:last-child{border-bottom:none}
	/* tables */
	.rcr .sc{overflow:auto;max-height:70vh;border:1px solid var(--bd);border-radius:8px}
	.rcr table{border-collapse:separate;border-spacing:0;width:100%}
	.rcr th,.rcr td{padding:5px 7px;text-align:center;font-size:12px;border-bottom:1px solid var(--bd);border-right:1px solid var(--bd);white-space:nowrap}
	.rcr th:last-child,.rcr td:last-child{border-right:none}
	.rcr thead th{position:sticky;top:0;background:var(--cd);z-index:3;color:var(--mu);font-weight:500;line-height:1.25}
	.rcr th .dn{display:block;color:var(--tx);font-weight:600;font-size:13px}
	.rcr th.td{box-shadow:inset 0 -3px 0 var(--ac)}
	.rcr td.we,.rcr th.we{background:var(--we)}
	.rcr td.nm,.rcr th.nm{position:sticky;left:0;z-index:2;background:var(--cd);text-align:left;min-width:170px;max-width:240px;overflow:hidden;text-overflow:ellipsis;font-weight:600}
	.rcr thead th.nm{z-index:4}
	.rcr td.nm .sub{display:block;font-weight:400;font-size:11px}
	.rcr td.tt,.rcr th.tt{background:var(--cd);font-weight:600;min-width:44px}
	.rcr tbody tr:hover td{background:var(--O)}
	.rcr tbody tr:hover td.nm,.rcr tbody tr:hover td.tt{background:var(--O)}
	.rcr tr.g td{background:var(--O);text-align:left;font-weight:600;cursor:pointer;position:sticky;left:0}
	.rcr tfoot td{font-weight:600;background:var(--cd);position:sticky;bottom:0;border-top:1px solid var(--bd)}
	.rcr tfoot td.nm{z-index:3}
	.rcr .cmp th,.rcr .cmp td{padding:3px 3px;font-size:11px}
	.rcr .cmp td.nm,.rcr .cmp th.nm{min-width:130px}
	.rcr .cmp .k{min-width:22px;padding:2px 3px}
	/* chips */
	.rcr .k{display:inline-block;min-width:44px;padding:3px 6px;border-radius:6px;font-weight:600;font-size:11px;cursor:pointer;border:1.5px solid transparent;position:relative;line-height:1.4}
	.rcr .k.draft{border-style:dashed;border-color:rgba(0,0,0,.5)}
	[data-theme="dark"] .rcr .k.draft{border-color:rgba(255,255,255,.7)}
	.rcr .k.none{background:transparent;color:var(--mu);cursor:default;font-weight:400}
	.rcr .k.off{background:var(--O);color:var(--mu)}
	.rcr .k.leave{background:#7c5cd6;color:#fff}
	.rcr .k.sick{background:var(--bad);color:#fff}
	.rcr .k .dot{position:absolute;top:-3px;right:-3px;width:8px;height:8px;border-radius:50%;background:var(--warn);border:1.5px solid var(--cd)}
	.rcr td.hc{font-weight:600}
	.rcr td.hc.bad{background:var(--badbg);color:var(--bad)}
	.rcr td.hc.warn{background:var(--warnbg);color:var(--warn)}
	.rcr td.hc.ok{background:var(--okbg);color:var(--ok)}
	.rcr td.hc.na{color:var(--mu);font-weight:400}
	.rcr .sw{display:inline-block;width:10px;height:10px;border-radius:3px;margin-right:6px;vertical-align:baseline}
	.rcr .legend{display:flex;gap:12px;flex-wrap:wrap;align-items:center;margin-top:8px;font-size:12px;color:var(--mu)}
	.rcr .pill{display:inline-block;padding:2px 8px;border-radius:10px;font-size:11px;font-weight:600;background:var(--O);color:var(--mu)}
	.rcr .pill.ok{background:var(--okbg);color:var(--ok)} .rcr .pill.wn{background:var(--warnbg);color:var(--warn)} .rcr .pill.no{background:var(--badbg);color:var(--bad)}
	.rcr .lvs{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:10px;margin-bottom:12px}
	.rcr .lvs .c{margin:0}
	.rcr .chartbox{min-height:120px}
	@media print{.navbar,.page-head,.rcr .nop{display:none !important}.rcr{padding:0;background:#fff}.rcr .sc{max-height:none;overflow:visible}}
	`;
	$("<style>" + CSS + "</style>").appendTo(page.wrapper);

	// ---------- helpers ----------
	const api = (m, args) => frappe.call({ method: "roster_and_weekend.roster_and_weekend.api." + m, args: args || {} }).then(r => r.message);
	const esc = s => frappe.utils.escape_html(s == null ? "" : String(s));
	const today = frappe.datetime.get_today();
	const addD = (d, n) => frappe.datetime.add_days(d, n);
	const iso = d => String(d).slice(0, 10);
	const parse = d => new Date(iso(d) + "T00:00:00");
	const toIso = dt => dt.getFullYear() + "-" + String(dt.getMonth() + 1).padStart(2, "0") + "-" + String(dt.getDate()).padStart(2, "0");
	const dayDiff = (a, b) => Math.round((parse(b) - parse(a)) / 864e5);
	const daysIn = (a, b) => { const out = []; for (let i = 0; i <= dayDiff(a, b); i++) out.push(addD(iso(a), i)); return out; };
	const monthEnd = d => { const t = parse(d); return toIso(new Date(t.getFullYear(), t.getMonth() + 1, 0)); };
	const weekStart = d => addD(d, -parse(d).getDay());   // weeks start on Sunday
	const isWeekend = d => [5, 6].includes(parse(d).getDay());   // Friday and Saturday
	const wd = d => parse(d).toLocaleDateString("en", { weekday: "short" });
	const dm = d => parse(d).toLocaleDateString("en", { day: "numeric", month: "short" });
	const dlong = d => parse(d).toLocaleDateString("en", { weekday: "long", day: "numeric", month: "short", year: "numeric" });
	const fmtH = n => String(Math.round(n * 10) / 10);
	const hm = v => v ? String(v).slice(11, 16) : "–";
	const MAX_DAYS = 31;

	const PALETTE = ["#2563eb", "#0f9d77", "#7c5cd6", "#d9822b", "#d6455d", "#0891b2", "#5b8c2a", "#c2559e", "#a8691a", "#4f6d7a", "#b45309", "#7a3fb0"];
	const colorFor = s => { let h = 0; const str = String(s || ""); for (let i = 0; i < str.length; i++) h = (h * 31 + str.charCodeAt(i)) >>> 0; return PALETTE[h % PALETTE.length]; };

	const PRESETS = [
		["this_week", "This week", () => [weekStart(today), addD(weekStart(today), 6)]],
		["next_week", "Next week", () => [addD(weekStart(today), 7), addD(weekStart(today), 13)]],
		["this_month", "This month", () => [iso(today).slice(0, 8) + "01", monthEnd(today)]],
		["next_month", "Next month", () => { const s = addD(monthEnd(today), 1); return [s, monthEnd(s)]; }],
	];

	const st = {
		tab: "overview", from: PRESETS[0][2]()[0], to: PRESETS[0][2]()[1],
		loc: "", dept: "", company: "", shiftType: "", status: "", q: "",
		view: "employee", group: "none", compact: false, collapsed: {},
		data: null, tok: 0, liveDate: today, liveTimer: null,
	};

	// ---------- shell ----------
	const shell = $(`
	<div class="c" id="rcr-top">
		<div class="r tabs nop" id="rcr-tabs"></div>
		<div class="r nop" id="rcr-fdate">
			<div class="seg" id="rcr-presets"></div>
			<label class="fl">From <input type="date" id="rcr-from"></label>
			<label class="fl">To <input type="date" id="rcr-to"></label>
			<span class="mu" id="rcr-span"></span>
			<span class="sp"></span>
			<span id="rcr-act"><button id="rcr-csv">Export CSV</button> <button id="rcr-print">Print</button></span>
		</div>
		<div class="r nop" id="rcr-fsel" style="margin-top:8px">
			<select id="rcr-company"><option value="">All companies</option></select>
			<select id="rcr-loc"><option value="">All locations</option></select>
			<select id="rcr-dept"><option value="">All departments</option></select>
			<select id="rcr-shift"><option value="">All shift types</option></select>
			<select id="rcr-status"><option value="">Draft and published</option><option value="Published">Published only</option><option value="Draft">Draft only</option></select>
			<input type="search" id="rcr-q" placeholder="Search employee">
		</div>
	</div>
	<div id="rcr-body"></div>`);
	$('<div class="rcr"></div>').append(shell).appendTo(page.body);
	const $body = $("#rcr-body");

	const TABS = [["overview", "Overview"], ["grid", "Roster grid"], ["live", "Live today"], ["me", "My roster"], ["queue", "Swap queue"]];

	function renderTabs() {
		$("#rcr-tabs").html(TABS.map(([k, t]) => `<button class="${st.tab === k ? "on" : ""}" data-t="${k}">${t}</button>`).join(""))
			.find("button").on("click", function () { st.tab = this.dataset.t; render(); });
	}

	function syncBar() {
		const t = st.tab;
		$("#rcr-fdate").toggle(["overview", "grid", "me"].includes(t));
		$("#rcr-act").toggle(["overview", "grid"].includes(t));
		$("#rcr-fsel").toggle(["overview", "grid", "live"].includes(t));
		$("#rcr-fsel select").not("#rcr-loc").add("#rcr-q").toggle(["overview", "grid"].includes(t));
		$("#rcr-from").val(st.from); $("#rcr-to").val(st.to);
		$("#rcr-span").text(dm(st.from) + " – " + dm(st.to) + " · " + (dayDiff(st.from, st.to) + 1) + " days");
		$("#rcr-presets").html(PRESETS.map(([k, t, fn]) => { const r = fn(); return `<button data-p="${k}" class="${r[0] === st.from && r[1] === st.to ? "on" : ""}">${t}</button>`; }).join(""))
			.find("button").on("click", function () {
				const r = PRESETS.find(p => p[0] === this.dataset.p)[2]();
				st.from = r[0]; st.to = r[1]; reload();
			});
	}

	function reload() { st.data = null; render(); }

	// ---------- data ----------
	function load() {
		const tok = ++st.tok;
		return api("get_report_data", {
			from_date: st.from, to_date: st.to, shift_location: st.loc, department: st.dept,
			company: st.company, shift_type: st.shiftType, status: st.status,
		}).then(d => {
			if (tok !== st.tok) return;
			const rows = (d.rows || []).map(r => Object.assign({}, r, { date: iso(r.date) }));
			const byName = {};
			rows.forEach(r => { byName[r.name] = r; });
			st.data = { rows, byName, meta: d.employees || {}, shiftInfo: d.shift_info || {}, rules: d.rules || [], truncated: d.truncated, days: daysIn(d.from_date, d.to_date) };
		});
	}

	const hoursOf = r => r.entry_type === "Work" ? ((st.data.shiftInfo[r.shift_type] || {}).hours || 0) : 0;

	function derive() {
		const d = st.data, q = st.q.trim().toLowerCase();
		const rows = d.rows.filter(r => !q || (r.employee_name || "").toLowerCase().includes(q) || r.employee.toLowerCase().includes(q));
		const names = {}, byEmp = {};
		rows.forEach(r => { names[r.employee] = r.employee_name || r.employee; (byEmp[r.employee] = byEmp[r.employee] || {})[r.date] = r; });
		const emps = Object.keys(names).sort((a, b) => names[a].localeCompare(names[b]));
		const work = rows.filter(r => r.entry_type === "Work");
		const hours = {};
		work.forEach(r => { hours[r.employee] = (hours[r.employee] || 0) + hoursOf(r); });
		const pub = rows.filter(r => r.status === "Published");
		return {
			rows, names, byEmp, emps, work, hours, days: d.days, meta: d.meta,
			totalHours: work.reduce((s, r) => s + hoursOf(r), 0),
			off: rows.filter(r => r.entry_type === "Off").length,
			absent: rows.filter(r => r.entry_type === "Leave" || r.entry_type === "Sick").length,
			draft: rows.filter(r => r.status === "Draft").length,
			ackPct: pub.length ? Math.round(100 * pub.filter(r => r.acknowledged).length / pub.length) : null,
			cov: coverage(work, d.days),
		};
	}

	// coverage per location + shift per day, compared with Roster Site Rule minimums
	function coverage(work, days) {
		const d = st.data;
		const rules = d.rules.filter(r => (!st.loc || r.shift_location === st.loc) && (!st.shiftType || r.shift_type === st.shiftType));
		const cnt = {}, need = {};
		work.forEach(r => {
			const k = (r.shift_location || "-") + "|" + r.shift_type;
			((cnt[k] = cnt[k] || {})[r.date] = cnt[k][r.date] || []).push(r.employee_name || r.employee);
		});
		const keys = new Set(Object.keys(cnt));
		rules.forEach(r => { const k = (r.shift_location || "-") + "|" + r.shift_type; keys.add(k); need[k] = Math.max(need[k] || 0, r.min_staff || 0); });
		const list = [...keys].sort().map(k => ({ key: k, loc: k.split("|")[0], shift: k.split("|")[1], min: need[k] || null, byDay: cnt[k] || {} }));
		let slots = 0, ok = 0; const gaps = [];
		list.forEach(c => { if (c.min) days.forEach(day => { slots++; const n = (c.byDay[day] || []).length; if (n >= c.min) ok++; else gaps.push({ date: day, loc: c.loc, shift: c.shift, have: n, need: c.min }); }); });
		gaps.sort((a, b) => a.date.localeCompare(b.date));
		return { list, slots, ok, gaps, pct: slots ? Math.round(100 * ok / slots) : null };
	}

	// ---------- shared pieces ----------
	const colCls = d => (isWeekend(d) ? "we" : "") + (d === today ? " td" : "");
	const dayHead = d => `<th class="${colCls(d)}" title="${esc(dlong(d))}">${wd(d)}<span class="dn">${parse(d).getDate()}</span></th>`;

	function chip(r) {
		if (!r) return '<span class="k none" title="No entry">–</span>';
		const si = st.data.shiftInfo[r.shift_type] || {};
		const tip = `${dlong(r.date)}\n${r.entry_type}${r.shift_type ? " · " + r.shift_type : ""}${si.start ? " " + si.start + "–" + si.end : ""}${r.shift_location ? "\n" + r.shift_location : ""}\n${r.status}${r.status === "Published" ? (r.acknowledged ? " · acknowledged" : " · not acknowledged") : ""}`;
		const draft = r.status === "Draft" ? " draft" : "";
		const dot = r.status === "Published" && !r.acknowledged ? '<i class="dot"></i>' : "";
		if (r.entry_type === "Work") {
			const bg = colorFor(r.shift_type);
			return `<span class="k${draft}" data-n="${esc(r.name)}" style="background:${bg};color:#fff" title="${esc(tip)}">${esc((r.shift_type || "Work").slice(0, st.compact ? 3 : 6))}${dot}</span>`;
		}
		const cls = { Off: "off", Leave: "leave", Sick: "sick" }[r.entry_type] || "off";
		const label = st.compact ? r.entry_type.slice(0, 1) : r.entry_type;
		return `<span class="k ${cls}${draft}" data-n="${esc(r.name)}" title="${esc(tip)}">${esc(label)}${dot}</span>`;
	}

	function covTable(cov, days, withTotals) {
		if (!cov.list.length) return '<div class="msg">No work shifts or staffing rules in this selection.</div>';
		const lvl = (n, min) => min == null ? (n ? "na" : "na") : n < min ? "bad" : n === min ? "warn" : "ok";
		const rowsHtml = cov.list.map(c => `<tr>
			<td class="nm"><span class="sw" style="background:${colorFor(c.shift)}"></span>${esc(c.loc === "-" ? "No location" : c.loc)} / ${esc(c.shift)}<span class="sub mu">${c.min ? "needs " + c.min : "no minimum set"}</span></td>
			${days.map(d => { const names = c.byDay[d] || []; return `<td class="hc ${lvl(names.length, c.min)} ${colCls(d)}" title="${esc(names.join(", ") || "Nobody rostered")}">${names.length || "–"}</td>`; }).join("")}</tr>`).join("");
		return `<div class="sc"><table><thead><tr><th class="nm">Location / shift</th>${days.map(dayHead).join("")}</tr></thead><tbody>${rowsHtml}</tbody></table></div>`;
	}

	function mkChart(sel, cfg) {
		try { if (frappe.Chart) new frappe.Chart(sel, cfg); else $(sel).html('<div class="msg">Charts are not available.</div>'); }
		catch (e) { console.error(e); $(sel).html('<div class="msg">Could not draw this chart.</div>'); }
	}

	// ---------- tab: overview ----------
	function tab_overview() {
		const D = derive(), cov = D.cov, rows = D.rows;
		if (!rows.length) {
			$body.html('<div class="c"><div class="msg">No roster entries for this selection. Try another date range or clear a filter.</div></div>');
			return;
		}
		const created = rows.length > 0, published = rows.every(r => r.status === "Published"), acked = published && rows.every(r => r.acknowledged);
		const flags = [created, published, acked], labels = ["Entries created", "Published", "Acknowledged"];
		const firstOpen = flags.findIndex(f => !f);
		const steps = labels.map((t, i) => `<div class="${flags[i] ? "d" : i === firstOpen ? "a" : ""}">${flags[i] ? "✔ " : ""}${t}</div>`).join("");
		const gapN = cov.gaps.length;
		const headline = cov.slots === 0
			? 'No minimum staffing is set for this selection. Add one in <a href="/app/roster-site-rule">Roster Site Rule</a>.'
			: gapN === 0 ? "Every shift meets its minimum staffing." : `<span class="no">${gapN} understaffed slot${gapN > 1 ? "s" : ""}</span> need attention.`;
		const filtered = st.dept || st.company || st.q;

		const kpi = (l, v, cls, extra) => `<div class="kpi ${cls || ""}"><div class="v">${v}</div><div class="l">${l}</div>${extra || ""}</div>`;
		const kpis = [
			kpi("Staff", D.emps.length),
			kpi("Work shifts", D.work.length),
			kpi("Work hours", fmtH(D.totalHours)),
			kpi("Days off", D.off),
			kpi("Leave and sick days", D.absent),
			kpi("Coverage met", cov.pct == null ? "–" : cov.pct + "%", cov.pct != null && cov.pct < 100 ? "warn" : ""),
			kpi("Understaffed slots", gapN, gapN ? "bad" : ""),
			kpi("Acknowledged", D.ackPct == null ? "–" : D.ackPct + "%", D.ackPct != null && D.ackPct < 100 ? "warn" : "", D.ackPct != null ? `<div class="pb"><i style="width:${D.ackPct}%"></i></div>` : ""),
			kpi("Draft entries", D.draft, D.draft ? "warn" : ""),
		].join("");

		const gapList = gapN ? cov.gaps.slice(0, 8).map(g => `<div class="li"><span><b>${wd(g.date)} ${dm(g.date)}</b> · ${esc(g.loc === "-" ? "No location" : g.loc)} / ${esc(g.shift)}</span><span class="no">${g.have} of ${g.need}</span></div>`).join("") + (gapN > 8 ? `<div class="mu" style="padding-top:6px">and ${gapN - 8} more</div>` : "") : '<div class="mu">No gaps.</div>';

		// people needing follow-up
		const unack = {}; D.rows.forEach(r => { if (r.status === "Published" && !r.acknowledged) unack[r.employee] = (unack[r.employee] || 0) + 1; });
		const unackList = Object.keys(unack).sort((a, b) => unack[b] - unack[a]).slice(0, 6).map(e => `<div class="li"><span>${esc(D.names[e])}</span><span class="wn">${unack[e]} not acknowledged</span></div>`).join("") || '<div class="mu">Everyone has acknowledged.</div>';
		const noWork = D.emps.filter(e => !Object.values(D.byEmp[e]).some(r => r.entry_type === "Work")).slice(0, 6).map(e => `<div class="li"><span>${esc(D.names[e])}</span><span class="mu">no work shifts</span></div>`).join("") || '<div class="mu">Everyone has at least one work shift.</div>';

		$body.html(`
		${st.data.truncated ? '<div class="note">Too many entries to show. Narrow the date range or add a filter.</div>' : ""}
		<div class="c">
			<div class="head"><div class="steps">${steps}</div><span class="mu">${D.emps.length} staff, ${D.days.length} days, ${rows.length} entries</span></div>
			<div class="head" style="margin-bottom:0"><b>${headline}</b></div>
		</div>
		<div class="kpis">${kpis}</div>
		<div class="c">
			<h3>Staffing by shift and day</h3>
			${covTable(cov, D.days)}
			<div class="legend"><span><span class="sw" style="background:var(--ok)"></span>Above minimum</span><span><span class="sw" style="background:var(--warn)"></span>At minimum</span><span><span class="sw" style="background:var(--bad)"></span>Below minimum</span><span>Hover a cell to see who is rostered.</span>${filtered ? '<span class="wn">Filtered staff only, so gaps may be overstated.</span>' : ""}</div>
		</div>
		<div class="cols">
			<div class="c"><h3>Staff per day by shift</h3><div id="rcr-ch1" class="chartbox"></div></div>
			<div class="c"><h3>Day types</h3><div id="rcr-ch2" class="chartbox"></div></div>
			<div class="c"><h3>Work hours per employee</h3><div id="rcr-ch3" class="chartbox"></div></div>
		</div>
		<div class="cols">
			<div class="c"><h3>Understaffed slots</h3>${gapList}</div>
			<div class="c"><h3>Waiting for acknowledgement</h3>${unackList}</div>
			<div class="c"><h3>No work shifts in range</h3>${noWork}</div>
		</div>`);

		// charts
		const shifts = [...new Set(D.work.map(r => r.shift_type))].sort();
		const labelsX = D.days.map(d => wd(d).slice(0, 2) + " " + parse(d).getDate());
		if (shifts.length) {
			mkChart("#rcr-ch1", {
				type: "bar", height: 240, colors: shifts.map(colorFor), barOptions: { stacked: 1, spaceRatio: 0.35 },
				data: { labels: labelsX, datasets: shifts.map(s => ({ name: s, values: D.days.map(d => D.work.filter(r => r.date === d && r.shift_type === s).length) })) },
			});
		} else $("#rcr-ch1").html('<div class="msg">No work shifts.</div>');
		const types = [["Work", D.work.length], ["Off", D.off], ["Leave", D.rows.filter(r => r.entry_type === "Leave").length], ["Sick", D.rows.filter(r => r.entry_type === "Sick").length]].filter(t => t[1] > 0);
		if (types.length) mkChart("#rcr-ch2", { type: "donut", height: 240, colors: ["#0f9d77", "#9aa7b5", "#7c5cd6", "#d6455d"].slice(0, types.length), data: { labels: types.map(t => t[0]), datasets: [{ values: types.map(t => t[1]) }] } });
		else $("#rcr-ch2").html('<div class="msg">No entries.</div>');
		const top = Object.keys(D.hours).sort((a, b) => D.hours[b] - D.hours[a]).slice(0, 12);
		if (top.length) mkChart("#rcr-ch3", { type: "bar", height: 240, colors: ["#0f766e"], data: { labels: top.map(e => D.names[e].split(" ").slice(0, 2).join(" ")), datasets: [{ name: "Hours", values: top.map(e => Math.round(D.hours[e] * 10) / 10) }] } });
		else $("#rcr-ch3").html('<div class="msg">No work hours.</div>');
	}

	// ---------- tab: roster grid ----------
	function tab_grid() {
		const D = derive(), days = D.days;
		if (!D.rows.length) { $body.html('<div class="c"><div class="msg">No roster entries for this selection.</div></div>'); return; }
		const seg = (key, opts) => `<div class="seg">${opts.map(([k, t]) => `<button data-${key}="${k}" class="${st[key === "v" ? "view" : "group"] === k ? "on" : ""}">${t}</button>`).join("")}</div>`;
		const bar = `<div class="r nop" style="margin-bottom:10px">
			${seg("v", [["employee", "By employee"], ["shift", "By shift"], ["location", "By location"]])}
			${st.view === "employee" ? `<label class="fl">Group by <select id="rcr-grp"><option value="none">Nothing</option><option value="dept">Department</option><option value="loc">Location</option></select></label>` : ""}
			<button id="rcr-cmp" class="${st.compact ? "on" : ""}">Compact</button>
			<span class="sp"></span><span class="mu">Click an entry for details. Dashed means draft. A dot means not acknowledged.</span></div>`;
		let table = "";
		if (st.view === "employee") table = gridEmployee(D);
		else if (st.view === "shift") table = covTable(D.cov, days);
		else table = gridLocation(D);
		const legend = `<div class="legend">${[...new Set(D.work.map(r => r.shift_type))].sort().map(s => `<span><span class="sw" style="background:${colorFor(s)}"></span>${esc(s)}</span>`).join("")}<span><span class="sw" style="background:var(--O)"></span>Off</span><span><span class="sw" style="background:#7c5cd6"></span>Leave</span><span><span class="sw" style="background:var(--bad)"></span>Sick</span></div>`;
		$body.html(`${st.data.truncated ? '<div class="note">Too many entries to show. Narrow the date range or add a filter.</div>' : ""}<div class="c ${st.compact ? "cmp" : ""}">${bar}${table}${legend}</div>`);
		$body.find("[data-v]").on("click", function () { st.view = this.dataset.v; tab_grid(); });
		$("#rcr-grp").val(st.group).on("change", function () { st.group = this.value; tab_grid(); });
		$("#rcr-cmp").on("click", () => { st.compact = !st.compact; tab_grid(); });
		$body.find("tr.g").on("click", function () { const k = this.dataset.g; st.collapsed[k] = !st.collapsed[k]; tab_grid(); });
	}

	function gridEmployee(D) {
		const days = D.days;
		const modeLoc = e => { const c = {}; Object.values(D.byEmp[e]).forEach(r => { if (r.shift_location) c[r.shift_location] = (c[r.shift_location] || 0) + 1; }); return Object.keys(c).sort((a, b) => c[b] - c[a])[0] || "No location"; };
		const groupOf = e => st.group === "dept" ? (D.meta[e] && D.meta[e].department) || "No department" : st.group === "loc" ? modeLoc(e) : "";
		const rowHtml = e => {
			const rs = D.byEmp[e]; let work = 0, off = 0, hrs = 0;
			days.forEach(d => { const r = rs[d]; if (!r) return; if (r.entry_type === "Work") { work++; hrs += hoursOf(r); } else if (r.entry_type === "Off") off++; });
			const m = D.meta[e] || {};
			return `<tr><td class="nm" title="${esc(D.names[e])}">${esc(D.names[e])}<span class="sub mu">${esc(m.designation || "")}</span></td>${days.map(d => `<td class="${colCls(d)}">${chip(rs[d])}</td>`).join("")}<td class="tt">${work}</td><td class="tt">${off}</td><td class="tt">${fmtH(hrs)}</td></tr>`;
		};
		let body = "";
		if (st.group === "none") body = D.emps.map(rowHtml).join("");
		else {
			const groups = {};
			D.emps.forEach(e => (groups[groupOf(e)] = groups[groupOf(e)] || []).push(e));
			Object.keys(groups).sort().forEach(g => {
				const closed = !!st.collapsed[g];
				body += `<tr class="g" data-g="${esc(g)}"><td colspan="${days.length + 4}">${closed ? "▸" : "▾"} ${esc(g)} <span class="mu" style="font-weight:400">${groups[g].length} staff</span></td></tr>`;
				if (!closed) body += groups[g].map(rowHtml).join("");
			});
		}
		const foot = `<tfoot><tr><td class="nm">Staff working</td>${days.map(d => `<td class="${colCls(d)}">${D.work.filter(r => r.date === d).length}</td>`).join("")}<td class="tt">${D.work.length}</td><td class="tt">${D.off}</td><td class="tt">${fmtH(D.totalHours)}</td></tr></tfoot>`;
		return `<div class="sc"><table><thead><tr><th class="nm">Employee</th>${days.map(dayHead).join("")}<th class="tt" title="Work days">Work</th><th class="tt" title="Days off">Off</th><th class="tt" title="Work hours">Hrs</th></tr></thead><tbody>${body}</tbody>${foot}</table></div>`;
	}

	function gridLocation(D) {
		const locs = {};
		D.work.forEach(r => { const k = r.shift_location || "No location"; ((locs[k] = locs[k] || {})[r.date] = locs[k][r.date] || []).push(r); });
		const keys = Object.keys(locs).sort();
		if (!keys.length) return '<div class="msg">No work shifts in this selection.</div>';
		const rowsHtml = keys.map(k => `<tr><td class="nm">${esc(k)}</td>${D.days.map(d => {
			const rs = locs[k][d] || [], by = {}; rs.forEach(r => { by[r.shift_type] = (by[r.shift_type] || 0) + 1; });
			const tip = Object.keys(by).map(s => s + ": " + by[s]).join("\n") || "Nobody rostered";
			return `<td class="hc ${rs.length ? "ok" : "na"} ${colCls(d)}" title="${esc(tip)}">${rs.length || "–"}</td>`;
		}).join("")}</tr>`).join("");
		return `<div class="sc"><table><thead><tr><th class="nm">Location</th>${D.days.map(dayHead).join("")}</tr></thead><tbody>${rowsHtml}</tbody></table></div>`;
	}

	// entry details
	$body.on("click", ".k[data-n]", function () {
		const r = st.data && st.data.byName[this.dataset.n];
		if (!r) return;
		const si = st.data.shiftInfo[r.shift_type] || {};
		const row = (l, v) => `<tr><td class="mu" style="padding:4px 14px 4px 0">${l}</td><td style="padding:4px 0"><b>${v}</b></td></tr>`;
		const dlg = new frappe.ui.Dialog({
			title: r.employee_name || r.employee,
			fields: [{ fieldtype: "HTML", fieldname: "b" }],
			primary_action_label: "Open roster entry",
			primary_action() { dlg.hide(); frappe.set_route("Form", "Roster Entry", r.name); },
		});
		dlg.fields_dict.b.$wrapper.html(`<table>
			${row("Date", esc(dlong(r.date)))}${row("Type", esc(r.entry_type))}
			${r.entry_type === "Work" ? row("Shift", esc(r.shift_type || "–") + (si.start ? ` (${si.start} – ${si.end}, ${fmtH(si.hours)} h)` : "")) : ""}
			${row("Location", esc(r.shift_location || "–"))}
			${row("Plan", r.plan ? `<a href="/app/roster-plan/${encodeURIComponent(r.plan)}">${esc(r.plan)}</a>` : "–")}
			${row("Status", esc(r.status) + (r.status === "Published" ? (r.acknowledged ? " · acknowledged" : " · not acknowledged yet") : ""))}</table>`);
		dlg.show();
	});

	// ---------- tab: live today ----------
	function tab_live(silent) {
		if (!silent) $body.html('<div class="c"><div class="msg">Loading…</div></div>');
		api("get_live_board", { shift_location: st.loc, date: st.liveDate }).then(d => {
			const sum = d.summary || [];
			const cards = sum.map(s => {
				const pct = Math.round(100 * (s.present + s.done) / (s.scheduled || 1));
				return `<div class="c"><b>${esc(s.key)}</b><div class="pb"><i style="width:${pct}%"></i></div>
				<div class="mu">${s.scheduled} scheduled · <span class="ok">${s.present} in</span> · <span class="${s.missing ? "no" : ""}">${s.missing} missing</span> · ${s.late} late · ${s.done} done</div></div>`;
			}).join("");
			const pill = x => `<span class="pill ${{ Present: "ok", Completed: "ok", Late: "wn", "Early Exit": "wn", Missing: "no", Absent: "no" }[x] || ""}">${esc(x)}</span>`;
			const rowsHtml = (d.rows || []).map(r => `<tr><td style="text-align:left">${esc(r.employee_name || r.employee)}</td><td>${esc(r.shift_location || "")}</td><td>${esc(r.shift_type)}</td><td>${hm(r.planned_in)} – ${hm(r.planned_out)}</td><td>${hm(r.actual_in)}</td><td>${hm(r.actual_out)}</td><td>${pill(r.status)}</td><td>${r.late_minutes || ""}</td><td>${r.ot_minutes || ""}</td></tr>`).join("");
			$body.html(`
			<div class="c"><div class="r">
				<label class="fl">Day <input type="date" id="rcr-live-date" value="${esc(st.liveDate)}"></label>
				<button id="rcr-live-next">Go to next roster day</button>
				<span class="sp"></span><span class="mu">Refreshes every minute. Uses the location filter only.</span></div></div>
			${sum.length ? `<div class="lvs">${cards}</div>
			<div class="c"><div class="sc"><table><thead><tr><th style="text-align:left">Employee</th><th>Location</th><th>Shift</th><th>Planned</th><th>In</th><th>Out</th><th>Status</th><th>Late min</th><th>OT min</th></tr></thead><tbody>${rowsHtml}</tbody></table></div></div>`
				: `<div class="c"><div class="msg">No published work shifts on ${esc(dlong(st.liveDate))}.</div></div>`}`);
			$("#rcr-live-date").on("change", function () { st.liveDate = this.value || today; tab_live(); });
			$("#rcr-live-next").on("click", () => api("next_roster_date", { from_date: st.liveDate, shift_location: st.loc }).then(n => {
				if (n) { st.liveDate = n; tab_live(); } else frappe.show_alert({ message: "No later published roster found.", indicator: "orange" });
			}));
		});
	}

	// ---------- tab: my roster ----------
	function tab_me() {
		$body.html('<div class="c"><div class="msg">Loading…</div></div>');
		api("my_employee").then(emp => {
			if (!emp) { $body.html('<div class="c"><div class="msg">No active employee is linked to your user, so there is no personal roster to show.</div></div>'); return; }
			return api("my_roster", { from_date: st.from, to_date: st.to }).then(rows => {
				const byDate = {}; (rows || []).forEach(r => { byDate[iso(r.date)] = r; });
				const trs = daysIn(st.from, st.to).map(d => {
					const r = byDate[d];
					const kind = !r ? '<span class="mu">No entry</span>' : r.entry_type === "Work" ? `<span class="k" style="background:${colorFor(r.shift_type)};color:#fff;cursor:default">${esc(r.shift_type || "Work")}</span>` : `<span class="k ${({ Leave: "leave", Sick: "sick" })[r.entry_type] || "off"}" style="cursor:default">${esc(r.entry_type)}</span>`;
					return `<tr class="${colCls(d)}"><td style="text-align:left">${esc(wd(d))} ${esc(dm(d))}</td><td>${kind}</td><td>${esc(r ? r.shift_location || "" : "")}</td><td>${r && r.acknowledged ? '<span class="ok">Acknowledged</span>' : r ? '<span class="wn">Not yet</span>' : ""}</td></tr>`;
				}).join("");
				$body.html(`<div class="c"><h3>${esc(emp)}: ${(rows || []).length} entries, ${esc(dm(st.from))} – ${esc(dm(st.to))}</h3><div class="sc"><table><thead><tr><th style="text-align:left">Day</th><th>Entry</th><th>Location</th><th>Acknowledged</th></tr></thead><tbody>${trs}</tbody></table></div></div>`);
			});
		});
	}

	// ---------- tab: swap queue ----------
	function tab_queue() {
		$body.html('<div class="c"><div class="msg">Loading…</div></div>');
		api("get_queue").then(q => {
			const sw = (q.swaps || []).map(s => {
				const checks = (s.checks || "").split("\n").filter(Boolean);
				const ok = checks.length === 0 || checks[0] === "All rules OK";
				return `<div class="li"><span><b>${esc(s.requester)}</b> and <b>${esc(s.counterpart)}</b> on ${esc(dm(s.date))}<br><span class="${ok ? "ok" : "no"}">${ok ? "All rules OK" : esc(checks.join("; "))}</span></span><span class="mu">${esc(s.status || "Pending manager")}</span></div>`;
			}).join("");
			const os = (q.open_shifts || []).map(o => `<div class="li"><span>${esc(dm(o.date))} · <b>${esc(o.shift_type)}</b> ${esc(o.shift_location || "")} · ${esc(o.reason || "")}</span><span class="mu">Open</span></div>`).join("");
			$body.html(`<div class="cols"><div class="c"><h3>Swap requests waiting for a manager</h3>${sw || '<span class="mu">None.</span>'}</div>
			<div class="c"><h3>Open shifts</h3>${os || '<span class="mu">None.</span>'}</div></div>
			<div class="c">Upcoming entries not yet acknowledged: <b>${q.unacknowledged || 0}</b>. Approve or reject requests in <a href="/app/roster-hub">Roster Hub</a>.</div>`);
		});
	}

	// ---------- export ----------
	function exportCsv() {
		if (!st.data) return;
		const D = derive(), q = v => '"' + String(v == null ? "" : v).replace(/"/g, '""') + '"';
		const lines = [["Employee", "Name", "Department", ...D.days, "Work days", "Off days", "Work hours"].map(q).join(",")];
		D.emps.forEach(e => {
			let work = 0, off = 0, hrs = 0;
			const cells = D.days.map(d => { const r = D.byEmp[e][d]; if (!r) return ""; if (r.entry_type === "Work") { work++; hrs += hoursOf(r); return r.shift_type + (r.status === "Draft" ? " (draft)" : ""); } if (r.entry_type === "Off") off++; return r.entry_type; });
			lines.push([e, D.names[e], (D.meta[e] || {}).department || "", ...cells, work, off, fmtH(hrs)].map(q).join(","));
		});
		const a = document.createElement("a");
		a.href = URL.createObjectURL(new Blob(["\ufeff" + lines.join("\n")], { type: "text/csv;charset=utf-8" }));
		a.download = `roster_${st.from}_${st.to}.csv`;
		document.body.appendChild(a); a.click(); a.remove();
	}

	// ---------- render ----------
	function render() {
		clearInterval(st.liveTimer);
		renderTabs(); syncBar();
		const t = st.tab;
		if ((t === "overview" || t === "grid") && !st.data) {
			$body.html('<div class="c"><div class="msg">Loading…</div></div>');
			return load().then(() => { if (st.data) render(); }).catch(() => { $body.html('<div class="c"><div class="msg">Could not load the roster. Check the date range and try again.</div></div>'); });
		}
		({ overview: tab_overview, grid: tab_grid, live: tab_live, me: tab_me, queue: tab_queue })[t]();
		if (t === "live") st.liveTimer = setInterval(() => { if ($(wrapper).is(":visible") && st.tab === "live") tab_live(true); }, 60000);
	}

	// ---------- wire up ----------
	function dateChanged() {
		let f = $("#rcr-from").val(), t = $("#rcr-to").val();
		if (!f || !t) return;
		if (f > t) { frappe.show_alert({ message: "From date must be on or before the To date.", indicator: "orange" }); syncBar(); return; }
		if (dayDiff(f, t) + 1 > MAX_DAYS) { t = addD(f, MAX_DAYS - 1); frappe.show_alert({ message: `Range limited to ${MAX_DAYS} days.`, indicator: "orange" }); }
		st.from = f; st.to = t; reload();
	}
	$("#rcr-from, #rcr-to").on("change", dateChanged);
	[["#rcr-company", "company"], ["#rcr-loc", "loc"], ["#rcr-dept", "dept"], ["#rcr-shift", "shiftType"], ["#rcr-status", "status"]].forEach(([sel, key]) =>
		$(sel).on("change", function () { st[key] = this.value; reload(); }));
	let qTimer;
	$("#rcr-q").on("input", function () { clearTimeout(qTimer); const v = this.value; qTimer = setTimeout(() => { st.q = v; if (st.data && ["overview", "grid"].includes(st.tab)) render(); }, 200); });
	$("#rcr-csv").on("click", exportCsv);
	$("#rcr-print").on("click", () => window.print());

	api("get_report_filters").then(f => {
		const fill = (sel, label, list) => $(sel).html(`<option value="">${label}</option>` + (list || []).map(x => `<option value="${esc(x)}">${esc(x)}</option>`).join(""));
		fill("#rcr-company", "All companies", f.companies); fill("#rcr-loc", "All locations", f.locations);
		fill("#rcr-dept", "All departments", f.departments); fill("#rcr-shift", "All shift types", f.shift_types);
	});

	render();
};