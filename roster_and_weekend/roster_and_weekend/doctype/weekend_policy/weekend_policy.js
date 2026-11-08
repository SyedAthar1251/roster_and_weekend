// Copyright (c) 2026, neotec.ai and contributors
// For license information, please see license.txt

frappe.ui.form.on('Weekend Policy', {
	policy_type: function(frm) {
		frm.toggle_display('weekend_days', frm.doc.policy_type === 'Fixed');
		frm.toggle_display('cycle_start_date', frm.doc.policy_type === 'Rotational');
		frm.toggle_display('rotation_weeks', frm.doc.policy_type === 'Rotational');
		frm.toggle_display('rotation_cycle', frm.doc.policy_type === 'Rotational');
		refresh_policy_summary(frm);
	},
	refresh: function(frm) {
		frm.toggle_display('weekend_days', frm.doc.policy_type === 'Fixed');
		frm.toggle_display('cycle_start_date', frm.doc.policy_type === 'Rotational');
		frm.toggle_display('rotation_weeks', frm.doc.policy_type === 'Rotational');
		frm.toggle_display('rotation_cycle', frm.doc.policy_type === 'Rotational');
		refresh_policy_info(frm);
		refresh_linked_shift_types(frm);
		refresh_policy_summary(frm);
		refresh_status_info(frm);
		refresh_effective_info(frm);
	},
	onload: function(frm) {
		if (frm.doc.__islocal) {
			return;
		}
		frm.fields_dict.custom_weekend_policy_history.grid.will_view.prevent_edit = function() {
			return true;
		};
	}
});

function refresh_policy_info(frm) {
	if (!frm.doc.name) {
		return;
	}
	const html = `
		<p style="font-size: 14px; color: #666; margin-bottom: 10px;">
			This Weekend Policy controls weekly off days for employees assigned to Shift Types linked to this policy.
		</p>
		<div style="background: #f5f5f5; padding: 10px; border-radius: 4px; font-family: monospace; font-size: 13px; line-height: 1.8;">
			Weekend Policy<br>
			&nbsp;&nbsp;&nbsp;&nbsp;&darr;<br>
			Shift Type<br>
			&nbsp;&nbsp;&nbsp;&nbsp;&darr;<br>
			Employee Shift Assignment<br>
			&nbsp;&nbsp;&nbsp;&nbsp;&darr;<br>
			Employee
		</div>
	`;
	frm.set_df_property('custom_policy_info', 'options', html);
}

function refresh_linked_shift_types(frm) {
	if (!frm.doc.name) {
		return;
	}
	frappe.call({
		method: 'frappe.client.get_list',
		args: {
			doctype: 'Shift Type',
			fields: ['name', 'custom_weekend_policy'],
			filters: {
				custom_weekend_policy: frm.doc.name
			}
		},
		callback: function(r) {
			if (!r.message || !r.message.length) {
				const no_link = `<p style="color: #666; font-style: italic;">No Shift Type is currently linked to this Weekend Policy.</p>`;
				frm.set_df_property('custom_linked_shift_types', 'options', no_link);
				return;
			}
			const rows = r.message.map(st => `<tr><td style="padding: 4px 8px;">${st.name}</td></tr>`).join('');
			const table = `
				<table style="width: 100%; border-collapse: collapse; font-size: 13px;">
					<thead>
						<tr style="background: #f0f0f0;">
							<th style="text-align: left; padding: 6px 8px; border-bottom: 1px solid #ddd;">Shift Type</th>
						</tr>
					</thead>
					<tbody>${rows}</tbody>
				</table>
			`;
			frm.set_df_property('custom_linked_shift_types', 'options', table);
		}
	});
}

function refresh_policy_summary(frm) {
	if (!frm.doc.name) {
		return;
	}
	let summary = '';
	if (frm.doc.policy_type === 'Fixed') {
		const days = (frm.doc.weekend_days || [])
			.filter(row => row.is_weekend_off && row.day)
			.map(row => row.day)
			.join(', ');
		summary = `
			<table style="width: 100%; border-collapse: collapse; font-size: 13px;">
				<tr><td style="padding: 4px 8px; font-weight: bold; width: 40%;">Weekend Type</td><td style="padding: 4px 8px;">Fixed</td></tr>
				<tr style="background: #f9f9f9;"><td style="padding: 4px 8px; font-weight: bold;">Weekly Off</td><td style="padding: 4px 8px;">${days || '<span style="color: #999;">Not configured</span>'}</td></tr>
				<tr><td style="padding: 4px 8px; font-weight: bold;">Effective From</td><td style="padding: 4px 8px;">${frappe.datetime.str_to_user(frm.doc.effective_from) || '-'}</td></tr>
				<tr style="background: #f9f9f9;"><td style="padding: 4px 8px; font-weight: bold;">Status</td><td style="padding: 4px 8px;">${frm.doc.is_active ? 'Active' : 'Inactive'}</td></tr>
			</table>
		`;
	} else {
		const schedule = (frm.doc.rotation_cycle || [])
			.filter(row => row.is_weekend_off && row.weekend_day)
			.sort((a, b) => a.week_number - b.week_number)
			.map(row => `Week ${row.week_number} &rarr; ${row.weekend_day}`)
			.join('<br>');
		summary = `
			<table style="width: 100%; border-collapse: collapse; font-size: 13px;">
				<tr><td style="padding: 4px 8px; font-weight: bold; width: 40%;">Weekend Type</td><td style="padding: 4px 8px;">Rotational</td></tr>
				<tr style="background: #f9f9f9;"><td style="padding: 4px 8px; font-weight: bold;">Cycle Start</td><td style="padding: 4px 8px;">${frappe.datetime.str_to_user(frm.doc.cycle_start_date) || '-'}</td></tr>
				<tr><td style="padding: 4px 8px; font-weight: bold;">Rotation</td><td style="padding: 4px 8px;">${frm.doc.rotation_weeks || 0} Weeks</td></tr>
				<tr style="background: #f9f9f9;"><td style="padding: 4px 8px; font-weight: bold;">Schedule</td><td style="padding: 4px 8px;">${schedule || '<span style="color: #999;">Not configured</span>'}</td></tr>
			</table>
		`;
	}
	frm.set_df_property('custom_policy_summary', 'options', summary);
}

function refresh_status_info(frm) {
	if (!frm.doc.name) {
		return;
	}
	const status = frm.doc.is_active ? 'Active' : 'Inactive';
	const color = frm.doc.is_active ? '#28a745' : '#dc3545';
	const message = frm.doc.is_active
		? 'This policy is active and will be used for weekend calculation.'
		: 'This policy is inactive and will not be used for weekend calculation.';
	const html = `
		<div style="display: flex; align-items: center; gap: 8px; margin-bottom: 6px;">
			<span style="display: inline-block; width: 10px; height: 10px; border-radius: 50%; background: ${color};"></span>
			<span style="font-weight: bold; font-size: 14px; color: ${color};">${status}</span>
		</div>
		<p style="font-size: 13px; color: #666; margin: 0;">${message}</p>
	`;
	frm.set_df_property('custom_status_info', 'options', html);
}

function refresh_effective_info(frm) {
	if (!frm.doc.name || !frm.doc.effective_from) {
		return;
	}
	const html = `
		<p style="font-size: 13px; color: #666; margin: 0;">
			<strong>Effective From:</strong> ${frappe.datetime.str_to_user(frm.doc.effective_from)}<br>
			This policy applies from the effective date onward.
		</p>
	`;
	frm.set_df_property('custom_effective_info', 'options', html);
}
