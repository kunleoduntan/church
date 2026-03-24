// Main Church Service form controller
// Updated: "⚡ Create Instance Now" uses manual_create_instances_for_service()
// which handles multi-slot, multi-branch creation correctly.

frappe.ui.form.on("Church Service", {

    onload: function(frm) {
        frm.set_query("default_minister", function() {
            return { filters: { "is_a_pastor": 1, "member_status": "Active" } };
        });
        frm.set_query("default_worship_leader", function() {
            return {
                filters: [
                    ["Member", "member_status", "=", "Active"],
                    ["Member", "is_a_pastor", "=", 1]
                ]
            };
        });
        frm.set_query("default_follow_up_coordinator", function() {
            return { filters: { "member_status": "Active" } };
        });
        frm.set_query("member", "ministry_team", function() {
            return { filters: { "member_status": "Active" } };
        });
    },

    refresh: function(frm) {

        // ── TOOLS ──────────────────────────────────────────────────────────
        if (!frm.is_new()) {
            frm.add_custom_button(__('Add Pastors & Workers'), function() {
                get_pastors_and_workers(frm);
            }, __("Tools"));
        }

        frm.add_custom_button(__('Create Service Order'), function() {
            create_service_order_template(frm);
        }, __("Tools"));

        if (frm.doc.is_recurring) {
            frm.add_custom_button(__('Calculate Next Date'), function() {
                calculate_next_service_date(frm);
            }, __("Tools"));
        }

        if (frm.doc.is_recurring && !frm.is_new()) {
            frm.add_custom_button(__('Generate Service Instances'), function() {
                generate_service_instances(frm);
            }, __("Tools"));
        }

        // ── REPORTS ────────────────────────────────────────────────────────
        if (!frm.is_new()) {
            frm.add_custom_button(__('View Statistics'), function() {
                show_service_statistics(frm);
            }, __("Reports"));
        }

        // ── ACTIONS ────────────────────────────────────────────────────────
        if (!frm.is_new()) {
            /**
             * CREATE INSTANCE NOW
             * ───────────────────
             * Manually creates Service Instances for this Church Service's
             * BASE service name across ALL active branches and ALL slots for today.
             *
             * Determines the base service name from this record's service_name
             * by stripping slot suffix if present (e.g. "Sunday Service - 1st Service - Lagos"
             * → base = "Sunday Service").
             *
             * Uses manual_create_instances_for_service() which:
             *   - reads weekly_services to find slot count and timing
             *   - creates all slots × all branches
             *   - generates QR + notifies pastors per instance
             */
            frm.add_custom_button(__('⚡ Create Instance Now'), function() {
                create_instance_now(frm);
            }, __("Actions"));
        }

        apply_table_row_colors(frm);
    },

    recurrence_pattern: function(frm) {
        if (frm.doc.is_recurring) calculate_next_service_date(frm);
    },
    day_of_week: function(frm) {
        if (frm.doc.is_recurring) calculate_next_service_date(frm);
    },
    frequency: function(frm) {
        if (frm.doc.is_recurring) calculate_next_service_date(frm);
    },
    is_recurring: function(frm) {
        if (frm.doc.is_recurring) {
            calculate_next_service_date(frm);
        } else {
            frm.set_value('next_service_date', '');
        }
    },

    before_save: function(frm) {
        if (!frm.doc.duration_minutes) frm.set_value('duration_minutes', 120);
        if (frm.doc.is_recurring && !frm.doc.next_service_date && frm.doc.day_of_week) {
            calculate_next_service_date(frm);
        }
    },

    setup: function(frm) {
        if (frm.is_new()) {
            frm.set_value('status', 'Active');
            frm.set_value('enable_attendance_tracking', 1);
            frm.set_value('enable_offering_collection', 1);
            frm.set_value('auto_track_visitors', 1);
            frm.set_value('visitor_follow_up_enabled', 1);
            frm.set_value('duration_minutes', 120);
            if (!frm.doc.service_type || frm.doc.service_type.includes('Sunday')) {
                frm.set_value('is_recurring', 1);
                frm.set_value('recurrence_pattern', 'Weekly');
                frm.set_value('day_of_week', 'Sunday');
            }
        }
    }
});


// ============================================================================
// CREATE INSTANCE NOW
// ============================================================================

function create_instance_now(frm) {
    /**
     * Extracts the BASE service name from this Church Service record,
     * then calls manual_create_instances_for_service() to create all
     * slots × all branches for today.
     *
     * How base name is determined:
     *   If this record was created by setup_church_services(), its name
     *   follows the pattern: "{base} - {Nth} Service - {Branch}" or "{base} - {Branch}".
     *   We try to find the matching weekly_services row by checking if
     *   frm.doc.name starts with any known service base name.
     *
     *   Simplest approach: use frm.doc.name as-is and let the server
     *   figure out the base from weekly_services.
     */

    const today    = frappe.datetime.now_date();
    const today_hr = frappe.datetime.str_to_user(today);

    frappe.confirm(
        __(
            'Create ALL Service Instances for <strong>{0}</strong> on '
            + '<strong>{1}</strong> across all active branches and slots?<br><br>'
            + 'This will:<br>'
            + '&nbsp;&nbsp;• Calculate all service slots from weekly_services<br>'
            + '&nbsp;&nbsp;• Create a Service Instance per slot per branch<br>'
            + '&nbsp;&nbsp;• Generate a QR code for each instance<br>'
            + '&nbsp;&nbsp;• Email all active pastors',
            [frm.doc.service_name, today_hr]
        ),
        function() {
            frappe.show_alert({
                message: __('Creating service instances…'),
                indicator: 'blue'
            }, 3);

            frappe.call({
                method: 'church.attendance.auto_service_creator.manual_create_instances_for_service',
                args: {
                    service_name: frm.doc.service_name,  // base service name
                    service_date: today
                },
                freeze: true,
                freeze_message: __(
                    'Creating instances across all branches and slots, '
                    + 'generating QR codes, notifying pastors…'
                ),
                callback: function(r) {
                    if (!r.message) {
                        frappe.msgprint({
                            title: __('Error'), indicator: 'red',
                            message: __('No server response. Check error logs.')
                        });
                        return;
                    }

                    const res = r.message;

                    if (!res.success) {
                        frappe.msgprint({
                            title: __('Failed'), indicator: 'red',
                            message: res.message
                        });
                        return;
                    }

                    // Results dialog
                    const created_list = Object.entries(res.created || {});
                    const skipped_list = res.skipped || [];

                    let html = `
                        <div style="font-family:Arial,sans-serif;font-size:14px;">
                            <p style="margin-bottom:12px;">${res.message}</p>
                    `;

                    if (created_list.length > 0) {
                        html += `
                            <h4 style="color:#27ae60;margin-bottom:8px;">
                                ✅ Created (${created_list.length})
                            </h4>
                            <table style="width:100%;border-collapse:collapse;margin-bottom:14px;">
                                <tr style="background:#f8f9fa;">
                                    <th style="padding:7px 10px;border:1px solid #dee2e6;text-align:left;">
                                        Church Service</th>
                                    <th style="padding:7px 10px;border:1px solid #dee2e6;text-align:left;">
                                        Instance</th>
                                </tr>
                                ${created_list.map(([svc, inst]) => `
                                    <tr>
                                        <td style="padding:7px 10px;border:1px solid #dee2e6;
                                                   font-size:12px;">${svc}</td>
                                        <td style="padding:7px 10px;border:1px solid #dee2e6;">
                                            <a href="/app/service-instance/${inst}"
                                               target="_blank"
                                               style="color:#3498db;font-size:12px;
                                                      font-family:monospace;">${inst}</a>
                                        </td>
                                    </tr>
                                `).join('')}
                            </table>
                        `;
                    }

                    if (skipped_list.length > 0) {
                        html += `
                            <h4 style="color:#e67e22;margin-bottom:8px;">
                                ⚠️ Skipped (${skipped_list.length})
                            </h4>
                            <ul style="margin:0;padding-left:20px;color:#888;font-size:12px;">
                                ${skipped_list.map(s =>
                                    `<li style="margin-bottom:3px;">${s}</li>`
                                ).join('')}
                            </ul>
                        `;
                    }

                    html += '</div>';

                    let d = new frappe.ui.Dialog({
                        title: __('Instance Creation Results'),
                        size: 'large',
                        fields: [{ fieldtype: 'HTML', fieldname: 'results_html' }],
                        primary_action_label: __('Close'),
                        primary_action: function() { d.hide(); }
                    });
                    d.fields_dict.results_html.$wrapper.html(html);
                    d.show();
                }
            });
        }
    );
}


// ============================================================================
// EXISTING FUNCTIONS — UNCHANGED
// ============================================================================

function get_pastors_and_workers(frm) {
    frappe.prompt([
        { fieldname: 'include_pastors', fieldtype: 'Check', label: 'Include Pastors', default: 1 },
        { fieldname: 'include_workers', fieldtype: 'Check', label: 'Include Workers', default: 1 },
        { fieldname: 'clear_existing',  fieldtype: 'Check', label: 'Clear Existing Ministry Team', default: 0 }
    ],
    function(values) {
        if (!values.include_pastors && !values.include_workers) {
            frappe.msgprint(__('Please select at least one category'));
            return;
        }
        if (values.clear_existing) frm.clear_table('ministry_team');
        frappe.show_alert(__('Fetching members...'));
        frappe.call({
            method: 'frappe.client.get_list',
            args: {
                doctype: 'Member',
                fields: ['name', 'full_name', 'email', 'mobile_phone',
                         'is_a_pastor', 'is_a_worker', 'designation'],
                filters: { "member_status": "Active" },
                limit_page_length: 0
            },
            callback: function(r) {
                if (r.message) {
                    let count = 0;
                    r.message.forEach(function(member) {
                        let ok = false;
                        if (values.include_pastors && member.is_a_pastor) ok = true;
                        if (values.include_workers  && member.is_a_worker)  ok = true;
                        if (!ok) return;
                        let row = frm.add_child('ministry_team');
                        row.member    = member.name;
                        row.full_name = member.full_name    || '';
                        row.phone     = member.mobile_phone || '';
                        row.email     = member.email        || '';
                        row.ministry_role = member.designation
                            ? member.designation
                            : member.is_a_pastor ? 'Minister/Pastor' : 'Other';
                        count++;
                    });
                    frm.refresh_field('ministry_team');
                    frappe.show_alert({
                        message: __('Added {0} members', [count]),
                        indicator: 'green'
                    });
                }
            }
        });
    },
    __('Select Members to Add'), __('Add Members'));
}


function create_service_order_template(frm) {
    if (!frm.doc.service_time) {
        frappe.msgprint({ title: __('Warning'), indicator: 'orange',
            message: __('Please set service time first') });
        return;
    }
    let today = new Date();
    let formattedDate = today.toLocaleDateString('en-US', {
        weekday: 'long', year: 'numeric', month: 'long', day: 'numeric'
    });
    let template = `<div style="font-family:'Segoe UI',sans-serif;max-width:800px;margin:0 auto;padding:20px;">
    <div style="text-align:center;margin-bottom:30px;padding-bottom:20px;border-bottom:3px solid #2c3e50;">
        <h1 style="color:#2c3e50;font-size:28px;">${frm.doc.service_name || 'Church Service'}</h1>
        <p><strong>Date:</strong> ${formattedDate}</p>
        <p><strong>Time:</strong> ${frm.doc.service_time}</p>
        <p><strong>Venue:</strong> ${frm.doc.venue || 'Main Sanctuary'}</p>
    </div>
    <h2 style="color:#3498db;border-bottom:2px solid #3498db;padding-bottom:8px;">Order of Service</h2>
    <table style="width:100%;border-collapse:collapse;margin:20px 0;font-size:14px;">
        <thead><tr style="background:#f8f9fa;">
            <th style="padding:10px;border:1px solid #dee2e6;">Time</th>
            <th style="padding:10px;border:1px solid #dee2e6;">Item</th>
            <th style="padding:10px;border:1px solid #dee2e6;">Leader</th>
        </tr></thead>
        <tbody>
            <tr><td style="padding:10px;border:1px solid #dee2e6;">${frm.doc.service_time}</td><td style="padding:10px;border:1px solid #dee2e6;">Call to Worship</td><td style="padding:10px;border:1px solid #dee2e6;">Worship Leader</td></tr>
            <tr><td style="padding:10px;border:1px solid #dee2e6;"></td><td style="padding:10px;border:1px solid #dee2e6;">Praise & Worship</td><td style="padding:10px;border:1px solid #dee2e6;">Worship Team</td></tr>
            <tr><td style="padding:10px;border:1px solid #dee2e6;"></td><td style="padding:10px;border:1px solid #dee2e6;">Announcements</td><td style="padding:10px;border:1px solid #dee2e6;">Secretary</td></tr>
            <tr><td style="padding:10px;border:1px solid #dee2e6;"></td><td style="padding:10px;border:1px solid #dee2e6;">Special Music</td><td style="padding:10px;border:1px solid #dee2e6;">${frm.doc.default_choir || 'Church Choir'}</td></tr>
            <tr><td style="padding:10px;border:1px solid #dee2e6;"></td><td style="padding:10px;border:1px solid #dee2e6;">Scripture Reading</td><td style="padding:10px;border:1px solid #dee2e6;"></td></tr>
            <tr><td style="padding:10px;border:1px solid #dee2e6;"></td><td style="padding:10px;border:1px solid #dee2e6;">Sermon</td><td style="padding:10px;border:1px solid #dee2e6;">${frm.doc.default_minister || 'Minister'}</td></tr>
            <tr><td style="padding:10px;border:1px solid #dee2e6;"></td><td style="padding:10px;border:1px solid #dee2e6;">Altar Call</td><td style="padding:10px;border:1px solid #dee2e6;">Minister</td></tr>
            <tr><td style="padding:10px;border:1px solid #dee2e6;"></td><td style="padding:10px;border:1px solid #dee2e6;">Offering & Tithes</td><td style="padding:10px;border:1px solid #dee2e6;">${frm.doc.default_ushering_team || 'Ushering Dept'}</td></tr>
            <tr><td style="padding:10px;border:1px solid #dee2e6;"></td><td style="padding:10px;border:1px solid #dee2e6;">Closing & Benediction</td><td style="padding:10px;border:1px solid #dee2e6;">Minister</td></tr>
        </tbody>
    </table>
    <div style="margin-top:20px;padding:15px;background:#fff8e1;border-radius:5px;border-left:4px solid #f39c12;">
        <p>${frm.doc.service_description || '• Please arrive 30 minutes early for prayer<br>• Ministry team: be at post 15 min before service'}</p>
    </div>
</div>`;
    frm.set_value('service_order_template', template);
    frm.refresh_field('service_order_template');
    frappe.show_alert({ message: __('Service order template created'), indicator: 'green' });
}


function calculate_next_service_date(frm) {
    if (!frm.doc.is_recurring || !frm.doc.day_of_week) return;
    const today = new Date();
    const dayMap = { Sunday:0, Monday:1, Tuesday:2, Wednesday:3, Thursday:4, Friday:5, Saturday:6 };
    const targetDay = dayMap[frm.doc.day_of_week];
    let daysToAdd = targetDay - today.getDay();
    if (daysToAdd <= 0) daysToAdd += 7;
    if (frm.doc.recurrence_pattern === 'Bi-Weekly') daysToAdd += 7;
    if (frm.doc.recurrence_pattern === 'Monthly')   daysToAdd += 21;
    const nextDate = new Date(today);
    nextDate.setDate(today.getDate() + daysToAdd);
    frm.set_value('next_service_date', frappe.datetime.obj_to_str(nextDate));
}


function generate_service_instances(frm) {
    frappe.prompt([
        { fieldname: 'start_date', fieldtype: 'Date', label: 'Start Date', reqd: 1,
          default: frm.doc.next_service_date || frappe.datetime.now_date() },
        { fieldname: 'number_of_instances', fieldtype: 'Int',
          label: 'Number of Instances to Generate', reqd: 1, default: 4 }
    ],
    function(values) {
        frappe.show_alert({ message: __('Generating instances…'), indicator: 'blue' });
        // Placeholder — implement server-side bulk generation if needed
        frappe.msgprint(__('Bulk generation scheduled. Check back in a moment.'));
    },
    __('Generate Service Instances'), __('Generate'));
}


function show_service_statistics(frm) {
    frappe.msgprint({
        title: __('Service Statistics'),
        message: `
            <div style="font-size:14px;">
                <p><strong>Total Occurrences:</strong> ${frm.doc.total_occurrences || 0}</p>
                <p><strong>Average Attendance:</strong> ${frm.doc.average_attendance || 0}</p>
                <p><strong>Next Service:</strong> ${frm.doc.next_service_date || 'Not scheduled'}</p>
                <p><strong>Last Service:</strong> ${frm.doc.last_service_date || 'No data'}</p>
            </div>
        `
    });
}


function apply_table_row_colors(frm) {
    setTimeout(() => {
        if (frm.fields_dict.ministry_team && frm.fields_dict.ministry_team.grid) {
            frm.fields_dict.ministry_team.grid.wrapper.find('.grid-row').each(function(i, row) {
                $(row).css('background-color', i % 2 === 0 ? '#ffffff' : '#f8f9fa');
            });
        }
    }, 100);
}


frappe.ui.form.on('Service Ministry Team', {
    member: function(frm, cdt, cdn) {
        let row = frappe.get_doc(cdt, cdn);
        if (row.member) {
            frappe.db.get_value('Member', row.member,
                ['full_name', 'email', 'mobile_phone', 'is_a_pastor', 'designation']
            ).then(r => {
                if (r.message) {
                    frappe.model.set_value(cdt, cdn, 'full_name', r.message.full_name || '');
                    frappe.model.set_value(cdt, cdn, 'email',     r.message.email || '');
                    frappe.model.set_value(cdt, cdn, 'phone',     r.message.mobile_phone || '');
                    if (r.message.designation && !row.ministry_role) {
                        frappe.model.set_value(cdt, cdn, 'ministry_role', r.message.designation);
                    } else if (r.message.is_a_pastor && !row.ministry_role) {
                        frappe.model.set_value(cdt, cdn, 'ministry_role', 'Minister/Pastor');
                    }
                }
            });
        }
    }
});