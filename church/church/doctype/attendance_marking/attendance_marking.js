// Copyright (c) 2026, kunle and contributors
// For license information, please see license.txt

// ─────────────────────────────────────────────────────────────────────────────
// Attendance Marking — Client Script
// ─────────────────────────────────────────────────────────────────────────────

frappe.ui.form.on('Attendance Marking', {

	// ── Form load / refresh ───────────────────────────────────────────────
	refresh(frm) {
		_update_summary(frm);
		_render_buttons(frm);
	},

	// ── Fetch Member List button ──────────────────────────────────────────
	fetch_members_btn(frm) {
		if (!frm.doc.branch) {
			frappe.msgprint(__('Please select a Branch first.'));
			return;
		}

		frappe.show_progress(__('Fetching Members'), 30, 100, __('Querying member list...'));

		frappe.call({
			method: 'church.church.doctype.attendance_marking.attendance_marking.fetch_member_list',
			args: {
				branch: frm.doc.branch,
				demography: frm.doc.gender || 'All',
			},
			callback(r) {
				frappe.hide_progress();
				if (!r.message || !r.message.length) {
					frappe.msgprint(__('No active members found for the selected criteria.'));
					return;
				}

				// Preserve existing present/absent markings
				const existing = {};
				(frm.doc.attendance || []).forEach(row => {
					existing[row.member_id] = cint(row.present);
				});

				frm.clear_table('attendance');

				r.message.forEach(member => {
					const row = frm.add_child('attendance');
					row.member_id         = member.member_id;
					row.full_name         = member.full_name;
					row.salutation        = member.salutation;
					row.mobile_phone      = member.mobile_phone;
					row.email             = member.email;
					row.whatsapp_number   = member.whatsapp_number;
					row.gender            = member.gender;
					row.demographic_group = member.demographic_group;
					row.present = existing.hasOwnProperty(member.member_id)
						? existing[member.member_id] : 0;
				});

				frm.refresh_field('attendance');
				_update_summary(frm);

				frappe.show_alert({
					message: __('{0} members loaded.', [r.message.length]),
					indicator: 'green',
				});
			},
		});
	},

	// ── Send Notifications button ─────────────────────────────────────────
	send_notifications_btn(frm) {
		if (!frm.doc.message_type) {
			frappe.msgprint(__('Please set a Message Type.'));
			return;
		}
		frappe.confirm(
			__('Send {0} notifications to members now?', [frm.doc.message_type]),
			() => {
				frappe.show_progress(__('Sending Notifications'), 50, 100);
				frappe.call({
					method: 'church.church.doctype.attendance_marking.attendance_marking.send_notifications',
					args: { docname: frm.doc.name },
					callback(r) {
						frappe.hide_progress();
						if (r.message) {
							frappe.show_alert({
								message: r.message.message,
								indicator: 'green',
							});
							frm.reload_doc();
						}
					},
				});
			}
		);
	},

	// ── Live recalc triggers ──────────────────────────────────────────────
	attendance_add:    (frm) => _update_summary(frm),
	attendance_remove: (frm) => _update_summary(frm),
});

// Recalculate when present checkbox is toggled in the child table
frappe.ui.form.on('Attendance Marking Item', {
	present(frm) {
		_update_summary(frm);
	},
});


// ─────────────────────────────────────────────────────────────────────────────
// Button rendering — single place, no duplicates
// ─────────────────────────────────────────────────────────────────────────────

function _render_buttons(frm) {

	// Always clear custom buttons first to avoid duplicates on re-render
	frm.clear_custom_buttons();

	// ── Create Attendance Records ─────────────────────────────────────────
	// Show only when: submitted + not yet created
	if (frm.doc.docstatus === 1 && !frm.doc.attendance_created) {

		frm.add_custom_button(__('Create Attendance Records'), () => {

			frappe.confirm(
				__('Create individual Church Attendance records for all {0} members?', [
					(frm.doc.attendance || []).length
				]),
				() => {
					frappe.show_progress(__('Creating Records'), 50, 100);
					frappe.call({
						method: 'church.church.doctype.attendance_marking.attendance_marking.create_attendance_records',
						args: { docname: frm.doc.name },
						callback(r) {
							frappe.hide_progress();
							if (r.message) {
								frappe.show_alert({
									message: r.message.message,
									indicator: r.message.errors && r.message.errors.length
										? 'orange' : 'green',
								});
								frm.reload_doc();
							}
						},
					});
				}
			);

		}, __('Actions'));
	}

	// ── Send Notifications ────────────────────────────────────────────────
	// Show only when: submitted
	if (frm.doc.docstatus === 1) {

		frm.add_custom_button(__('Send Notifications'), () => {

			if (!frm.doc.message_type) {
				frappe.msgprint(__('Please set a Message Type first.'));
				return;
			}

			frappe.confirm(
				__('Send {0} notifications to members now?', [frm.doc.message_type]),
				() => {
					frappe.show_progress(__('Sending Notifications'), 50, 100);
					frappe.call({
						method: 'church.church.doctype.attendance_marking.attendance_marking.send_notifications',
						args: { docname: frm.doc.name },
						callback(r) {
							frappe.hide_progress();
							if (r.message) {
								frappe.show_alert({
									message: r.message.message,
									indicator: 'green',
								});
								frm.reload_doc();
							}
						},
					});
				}
			);

		}, __('Actions'));
	}
}


// ─────────────────────────────────────────────────────────────────────────────
// Summary helpers
// ─────────────────────────────────────────────────────────────────────────────

function _pct(numerator, denominator) {
	if (!denominator) return 0;
	return parseFloat(((numerator / denominator) * 100).toFixed(1));
}

function _update_summary(frm) {
	const rows    = frm.doc.attendance || [];
	const total   = rows.length;
	const present = rows.filter(r => cint(r.present)).length;
	const absent  = total - present;

	// ── Overall ───────────────────────────────────────────────────────────
	frm.set_value('total_subscribers', total);
	frm.set_value('total_present',     present);
	frm.set_value('total_absent',      absent);
	frm.set_value('attendance_pct',    _pct(present, total));

	// ── Demography buckets ────────────────────────────────────────────────
	const groups = {
		Men:           { total: 0, present: 0 },
		Women:         { total: 0, present: 0 },
		Youth:         { total: 0, present: 0 },
		Teens:         { total: 0, present: 0 },
		Children:      { total: 0, present: 0 },
		_unclassified: { total: 0, present: 0 },
	};

	rows.forEach(r => {
		const key = groups[r.demographic_group] ? r.demographic_group : '_unclassified';
		groups[key].total++;
		if (cint(r.present)) groups[key].present++;
	});

	// ── Count fields ──────────────────────────────────────────────────────
	frm.set_value('total_men',                  groups.Men.total);
	frm.set_value('total_men_present',          groups.Men.present);
	frm.set_value('total_women',                groups.Women.total);
	frm.set_value('total_women_present',        groups.Women.present);
	frm.set_value('total_youth',                groups.Youth.total);
	frm.set_value('total_youth_present',        groups.Youth.present);
	frm.set_value('total_teens',                groups.Teens.total);
	frm.set_value('total_teens_present',        groups.Teens.present);
	frm.set_value('total_children',             groups.Children.total);
	frm.set_value('total_children_present',     groups.Children.present);
	frm.set_value('total_unclassified',         groups._unclassified.total);
	frm.set_value('total_unclassified_present', groups._unclassified.present);

	// ── % of total members (composition) ─────────────────────────────────
	frm.set_value('pct_men',          _pct(groups.Men.total,           total));
	frm.set_value('pct_women',        _pct(groups.Women.total,         total));
	frm.set_value('pct_youth',        _pct(groups.Youth.total,         total));
	frm.set_value('pct_teens',        _pct(groups.Teens.total,         total));
	frm.set_value('pct_children',     _pct(groups.Children.total,      total));
	frm.set_value('pct_unclassified', _pct(groups._unclassified.total, total));

	// ── % attendance within each group ────────────────────────────────────
	frm.set_value('pct_men_present',          _pct(groups.Men.present,           groups.Men.total));
	frm.set_value('pct_women_present',        _pct(groups.Women.present,         groups.Women.total));
	frm.set_value('pct_youth_present',        _pct(groups.Youth.present,         groups.Youth.total));
	frm.set_value('pct_teens_present',        _pct(groups.Teens.present,         groups.Teens.total));
	frm.set_value('pct_children_present',     _pct(groups.Children.present,      groups.Children.total));
	frm.set_value('pct_unclassified_present', _pct(groups._unclassified.present, groups._unclassified.total));
}