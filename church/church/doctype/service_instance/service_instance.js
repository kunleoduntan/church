// Service Instance form controller
// Updated with venue QR generation, display screen launch, and auto-refresh

frappe.ui.form.on("Service Instance", {

    onload: function(frm) {
        frm.set_query("service", function() {
            return { filters: { "status": "Active" } };
        });
        frm.set_query("minister", function() {
            return { filters: { "is_a_pastor": 1, "member_status": "Active" } };
        });
        frm.set_query("worship_leader", function() {
            return { filters: { "member_status": "Active" } };
        });
        frm.set_query("preacher", function() {
            return { filters: { "is_a_pastor": 1, "member_status": "Active" } };
        });
        frm.set_query("member", "ministry_team", function() {
            return { filters: { "member_status": "Active" } };
        });
        frm.set_query("visitor", "service_visitors", function() {
            return { filters: { "conversion_status": ["!=", "Lost Contact"] } };
        });
    },

    refresh: function(frm) {
        // ── QR CODE BUTTONS ────────────────────────────────────────────────
        if (!frm.is_new()) {
            add_qr_buttons(frm);
        }

        // ── COMMUNICATIONS ─────────────────────────────────────────────────
        if (!frm.is_new() && frm.doc.ministry_team && frm.doc.ministry_team.length > 0) {
            frm.add_custom_button(__('Send Notifications'), function() {
                show_notification_dialog(frm);
            }, __("Communications"));

            frm.add_custom_button(__('Send Service Reminder'), function() {
                send_service_reminder(frm);
            }, __("Communications"));

            frm.add_custom_button(__('Send Thank You Message'), function() {
                send_thank_you_message(frm);
            }, __("Communications"));
        }

        if (!frm.is_new() && frm.doc.service_visitors && frm.doc.service_visitors.length > 0) {
            frm.add_custom_button(__('Send Coordinator Assignments'), function() {
                send_coordinator_assignments(frm);
            }, __("Communications"));
        }

        // ── TOOLS ──────────────────────────────────────────────────────────
        if (frm.doc.service && (!frm.doc.ministry_team || frm.doc.ministry_team.length === 0)) {
            frm.add_custom_button(__('Copy Ministry Team from Template'), function() {
                copy_ministry_team_from_service(frm);
            }, __("Tools"));
        }

        if (frm.doc.service && !frm.doc.service_order) {
            frm.add_custom_button(__('Copy Service Order from Template'), function() {
                copy_service_order_from_service(frm);
            }, __("Tools"));
        }

        // ── ACTIONS ────────────────────────────────────────────────────────
        if (frm.doc.status === 'Ongoing' || frm.doc.status === 'Scheduled') {
            frm.add_custom_button(__('Mark as Completed'), function() {
                mark_service_completed(frm);
            }, __("Actions"));
        }

        // ── REPORTS ────────────────────────────────────────────────────────
        if (frm.doc.status === 'Completed') {
            frm.add_custom_button(__('Generate Service Report'), function() {
                generate_service_report(frm);
            }, __("Reports"));

            frm.add_custom_button(__('📄 Beautiful HTML Report'), function() {
                generate_html_report(frm);
            }, __("Reports"));

            frm.add_custom_button(__('📧 Email Report'), function() {
                email_report_dialog(frm);
            }, __("Reports"));
        }

        if (frm.doc.service_visitors && frm.doc.service_visitors.length > 0) {
            frm.add_custom_button(__('Visitor Follow-up Dashboard'), function() {
                show_visitor_followup_dashboard(frm);
            }, __("Reports"));
        }

        apply_table_styling(frm);
    },

    service: function(frm) {
        if (frm.doc.service) {
            frappe.db.get_doc('Church Service', frm.doc.service)
                .then(service => {
                    if (!frm.doc.minister) frm.set_value('minister', service.default_minister);
                    if (!frm.doc.worship_leader) frm.set_value('worship_leader', service.default_worship_leader);
                    if (!frm.doc.choir) frm.set_value('choir', service.default_choir);
                    if (!frm.doc.ushering_team) frm.set_value('ushering_team', service.default_ushering_team);
                    if (!frm.doc.service_order) frm.set_value('service_order', service.service_order_template);

                    if (!frm.doc.ministry_team || frm.doc.ministry_team.length === 0) {
                        frappe.show_alert({
                            message: __('Click "Copy Ministry Team from Template" to populate ministry team'),
                            indicator: 'blue'
                        });
                    }
                });
        }
    },

    service_date: function(frm) {
        if (frm.doc.service_date) {
            let service_date = new Date(frm.doc.service_date);
            let today = new Date();
            today.setHours(0, 0, 0, 0);
            if (service_date > today && frm.doc.status !== 'Completed') {
                frm.set_value('status', 'Scheduled');
            }
        }
    },

    before_save: function(frm) {
        let total = (frm.doc.men_count || 0) + (frm.doc.women_count || 0) + (frm.doc.children_count || 0);
        frm.set_value('total_attendance', total);

        if (!frm.doc.actual_start_time && frm.doc.service_time) {
            frm.set_value('actual_start_time', frm.doc.service_time);
        }

        if (!frm.doc.actual_end_time && frm.doc.actual_start_time) {
            let start_time = frappe.datetime.str_to_obj(frm.doc.actual_start_time);
            start_time.setMinutes(start_time.getMinutes() + 120);
            frm.set_value('actual_end_time', frappe.datetime.obj_to_str(start_time).split(' ')[1]);
        }
    },

    setup: function(frm) {
        if (frm.is_new()) {
            frm.set_value('status', 'Scheduled');
            frm.set_value('service_date', frappe.datetime.now_date());
        }
    },

    men_count: function(frm) { calculate_total_attendance(frm); },
    women_count: function(frm) { calculate_total_attendance(frm); },
    children_count: function(frm) { calculate_total_attendance(frm); }
});


// ============================================================================
// QR CODE BUTTONS
// ============================================================================

function add_qr_buttons(frm) {
    /**
     * Adds three QR-related buttons to the QR Code group:
     *
     * 1. 📺 Display on Screen  — opens the full-screen TV/projector page
     * 2. 🖨️ Print QR Code      — opens printable version for notice board
     * 3. 🔄 Regenerate QR      — manually force a new QR code
     */

    // 1. DISPLAY ON SCREEN — opens the dedicated display page
    frm.add_custom_button(__('📺 Display on Screen'), function() {
        let display_url = `/service-display?service=${frm.doc.name}`;
        window.open(display_url, '_blank');
    }, __("QR Check-In"));

    // 2. VIEW / PRINT QR — show current QR in dialog with print option
    frm.add_custom_button(__('🔲 View QR Code'), function() {
        show_qr_dialog(frm);
    }, __("QR Check-In"));

    // 3. REGENERATE — force a fresh QR right now
    frm.add_custom_button(__('🔄 Regenerate QR'), function() {
        frappe.confirm(
            __('Regenerate the venue QR code? The current code will become invalid.'),
            function() {
                frappe.call({
                    method: 'church.church.doctype.service_instance.service_instance.regenerate_venue_qr',
                    args: { service_instance: frm.doc.name },
                    freeze: true,
                    freeze_message: __('Regenerating QR code...'),
                    callback: function(r) {
                        if (r.message && r.message.success) {
                            frappe.show_alert({
                                message: __('✅ QR code regenerated successfully'),
                                indicator: 'green'
                            }, 5);
                            frm.reload_doc();
                        } else {
                            frappe.msgprint({
                                title: __('Failed'),
                                indicator: 'red',
                                message: r.message ? r.message.message : __('QR generation failed')
                            });
                        }
                    }
                });
            }
        );
    }, __("QR Check-In"));
}


function show_qr_dialog(frm) {
    /**
     * Show the current venue QR code in a dialog.
     * Includes live check-in count and expiry info.
     */
    const qr_url  = frm.doc.venue_qr_code;
    const expires = frm.doc.venue_qr_expires_at;
    const checkin_url = frm.doc.venue_qr_checkin_url || '';
    const display_url = `/service-display?service=${frm.doc.name}`;

    if (!qr_url) {
        frappe.msgprint({
            title: __('No QR Code'),
            indicator: 'orange',
            message: __('QR code has not been generated yet. Save the record to auto-generate it, or use "Regenerate QR".')
        });
        return;
    }

    const site_url  = window.location.origin;
    const full_url  = site_url + qr_url;
    const expires_str = expires ? frappe.datetime.str_to_user(expires) : 'N/A';

    let d = new frappe.ui.Dialog({
        title: __('Venue QR Code — {0}', [frm.doc.service_name || frm.doc.name]),
        size: 'large',
        fields: [{ fieldtype: 'HTML', fieldname: 'qr_html' }],
        primary_action_label: __('📺 Open Display Screen'),
        primary_action: function() {
            window.open(display_url, '_blank');
            d.hide();
        },
        secondary_action_label: __('🖨️ Print'),
        secondary_action: function() {
            print_qr(full_url, frm.doc.service_name, frm.doc.service_date, frm.doc.service_time);
        }
    });

    d.fields_dict.qr_html.$wrapper.html(`
        <div style="text-align:center;padding:24px 16px;">
            <img src="${full_url}"
                 style="width:220px;height:220px;border:2px solid #e0e0e0;border-radius:10px;"
                 alt="Venue QR Code">

            <div style="margin-top:18px;background:#f8f6ff;border-radius:10px;padding:14px 18px;text-align:left;">
                <p style="margin:4px 0;font-size:13px;color:#555;">
                    <strong>Service:</strong> ${frappe.utils.escape_html(frm.doc.service_name || frm.doc.name)}
                </p>
                <p style="margin:4px 0;font-size:13px;color:#555;">
                    <strong>Expires:</strong> ${frappe.utils.escape_html(expires_str)}
                </p>
                <p style="margin:4px 0;font-size:13px;color:#555;">
                    <strong>Refreshes:</strong> Every 10 minutes automatically on display screen
                </p>
            </div>

            <div style="margin-top:14px;background:#e8f5e9;border-radius:8px;padding:12px;font-size:12px;color:#2d6a4f;">
                📺 For best experience, open the <strong>Display Screen</strong> on your TV or projector.
                The QR auto-refreshes there every 10 minutes.
            </div>
        </div>
    `);

    d.show();
}


function print_qr(qr_image_url, service_name, service_date, service_time) {
    /**
     * Open a print-friendly page with just the QR code.
     * Suitable for printing on notice board.
     */
    const win = window.open('', '_blank', 'width=600,height=700');
    const date_str = service_date ? frappe.datetime.str_to_user(service_date) : '';
    const time_str = service_time || '';

    win.document.write(`
        <!DOCTYPE html>
        <html>
        <head>
            <title>Church Check-In QR — ${frappe.utils.escape_html(service_name || '')}</title>
            <style>
                body { font-family: Arial, sans-serif; text-align: center; padding: 30px; }
                h1   { font-size: 22px; color: #2c3e50; margin-bottom: 4px; }
                p    { color: #555; font-size: 15px; margin: 4px 0; }
                img  { width: 280px; height: 280px; border: 2px solid #ccc; border-radius: 8px; margin: 20px 0; }
                .footer { margin-top: 20px; font-size: 12px; color: #aaa; }
            </style>
        </head>
        <body>
            <h1>⛪ ${frappe.utils.escape_html(service_name || 'Church Service')}</h1>
            <p>${date_str} &nbsp;•&nbsp; ${time_str}</p>
            <img src="${qr_image_url}" alt="Check-In QR Code">
            <p style="font-size:16px;font-weight:bold;color:#667eea;">Scan to Check In</p>
            <p style="font-size:13px;color:#888;">Members: enter your phone number &nbsp;|&nbsp; Visitors: fill the form</p>
            <div class="footer">Church Management System</div>
            <script>window.onload = function() { window.print(); }</script>
        </body>
        </html>
    `);
    win.document.close();
}


// ============================================================================
// EXISTING FUNCTIONS — UNCHANGED
// ============================================================================

function calculate_total_attendance(frm) {
    let total = (frm.doc.men_count || 0) + (frm.doc.women_count || 0) + (frm.doc.children_count || 0);
    frm.set_value('total_attendance', total);
}


function send_coordinator_assignments(frm) {
    let coordinator_groups = {};
    let unassigned_visitors = [];

    if (!frm.doc.service_visitors || frm.doc.service_visitors.length === 0) {
        frappe.msgprint(__('No visitors found in this service'));
        return;
    }

    frm.doc.service_visitors.forEach(function(visitor) {
        if (visitor.follow_up_required) {
            if (visitor.follow_up_assigned_to) {
                if (!coordinator_groups[visitor.follow_up_assigned_to]) {
                    coordinator_groups[visitor.follow_up_assigned_to] = {
                        coordinator: visitor.follow_up_assigned_to,
                        coordinator_name: visitor.follow_up_coordinator_name || '',
                        visitors: []
                    };
                }
                coordinator_groups[visitor.follow_up_assigned_to].visitors.push(visitor);
            } else {
                unassigned_visitors.push(visitor);
            }
        }
    });

    let coordinator_count = Object.keys(coordinator_groups).length;
    let total_assigned = Object.values(coordinator_groups).reduce((sum, g) => sum + g.visitors.length, 0);

    if (coordinator_count === 0) {
        frappe.msgprint(__('No visitors have been assigned to coordinators'));
        return;
    }

    let summary_html = `
        <div style="font-family:Arial,sans-serif;margin-bottom:15px;">
            <h4 style="color:#2c3e50;margin-bottom:10px;">Assignment Summary</h4>
            <table style="width:100%;border-collapse:collapse;font-size:14px;">
                <tr style="background:#f8f9fa;">
                    <td style="padding:8px;border:1px solid #dee2e6;"><strong>Total Coordinators:</strong></td>
                    <td style="padding:8px;border:1px solid #dee2e6;">${coordinator_count}</td>
                </tr>
                <tr>
                    <td style="padding:8px;border:1px solid #dee2e6;"><strong>Total Assigned Visitors:</strong></td>
                    <td style="padding:8px;border:1px solid #dee2e6;">${total_assigned}</td>
                </tr>
                ${unassigned_visitors.length > 0 ? `
                <tr style="background:#fff3cd;">
                    <td style="padding:8px;border:1px solid #dee2e6;"><strong>Unassigned Visitors:</strong></td>
                    <td style="padding:8px;border:1px solid #dee2e6;color:#856404;">${unassigned_visitors.length}</td>
                </tr>` : ''}
            </table>
            <div style="margin-top:15px;">
                <h5 style="color:#34495e;margin-bottom:8px;">Coordinators & Assignments:</h5>
                <ul style="margin:0;padding-left:20px;font-size:13px;">
                    ${Object.values(coordinator_groups).map(g =>
                        `<li style="margin-bottom:5px;"><strong>${g.coordinator_name || g.coordinator}</strong>: ${g.visitors.length} visitor${g.visitors.length > 1 ? 's' : ''}</li>`
                    ).join('')}
                </ul>
            </div>
        </div>
    `;

    frappe.confirm(
        summary_html + '<p style="margin-top:15px;"><strong>Send assignment emails to all coordinators?</strong></p>',
        function() {
            frappe.call({
                method: 'church.church.doctype.service_instance.service_instance.send_coordinator_assignment_emails',
                args: { service_instance: frm.doc.name },
                callback: function(r) {
                    if (r.message && r.message.success) {
                        frappe.msgprint({ title: __('Emails Sent'), message: r.message.message, indicator: 'green' });
                        frm.doc.service_visitors.forEach(function(visitor) {
                            if (visitor.follow_up_assigned_to) visitor.follow_up_status = 'Scheduled';
                        });
                        frm.refresh_field('service_visitors');
                        frm.save();
                    }
                }
            });
        }
    );
}


function show_notification_dialog(frm) {
    let d = new frappe.ui.Dialog({
        title: __('Send Service Notifications'),
        fields: [
            { fieldname: 'notification_type', fieldtype: 'Select', label: 'Notification Type',
              options: ['Service Reminder', 'Service Schedule', 'Thank You Message', 'Custom Message'], reqd: 1, default: 'Service Reminder' },
            { fieldname: 'section_break_1', fieldtype: 'Section Break' },
            { fieldname: 'send_via_email', fieldtype: 'Check', label: 'Send via Email', default: 1 },
            { fieldname: 'send_via_sms', fieldtype: 'Check', label: 'Send via SMS', default: 0 },
            { fieldname: 'send_via_whatsapp', fieldtype: 'Check', label: 'Send via WhatsApp', default: 0 },
            { fieldname: 'section_break_2', fieldtype: 'Section Break' },
            {
                fieldname: 'recipients', fieldtype: 'MultiSelectList', label: 'Select Recipients',
                get_data: function() {
                    return frm.doc.ministry_team.map(member => ({
                        value: member.member,
                        description: `${member.full_name} - ${member.ministry_role}`
                    }));
                },
                reqd: 1
            },
            { fieldname: 'section_break_3', fieldtype: 'Section Break', depends_on: 'eval:doc.notification_type=="Custom Message"' },
            { fieldname: 'custom_subject', fieldtype: 'Data', label: 'Subject', depends_on: 'eval:doc.notification_type=="Custom Message"' },
            { fieldname: 'custom_message', fieldtype: 'Text Editor', label: 'Custom Message', depends_on: 'eval:doc.notification_type=="Custom Message"' }
        ],
        primary_action_label: __('Send Notifications'),
        primary_action: function(values) {
            if (!values.send_via_email && !values.send_via_sms && !values.send_via_whatsapp) {
                frappe.msgprint(__('Please select at least one channel'));
                return;
            }
            if (!values.recipients || values.recipients.length === 0) {
                frappe.msgprint(__('Please select at least one recipient'));
                return;
            }
            frappe.show_alert(__('Sending notifications...'));
            d.hide();
            frappe.call({
                method: 'church.church.doctype.service_instance.service_instance.send_ministry_team_notifications',
                args: {
                    service_instance: frm.doc.name,
                    notification_type: values.notification_type,
                    recipients: values.recipients,
                    send_via_email: values.send_via_email,
                    send_via_sms: values.send_via_sms,
                    send_via_whatsapp: values.send_via_whatsapp,
                    custom_subject: values.custom_subject,
                    custom_message: values.custom_message
                },
                callback: function(r) {
                    if (r.message) frappe.msgprint({ title: __('Sent'), message: r.message.message, indicator: 'green' });
                }
            });
        }
    });
    d.show();
}


function send_service_reminder(frm) {
    frappe.confirm(__('Send service reminder to all ministry team members?'), function() {
        frappe.call({
            method: 'church.church.doctype.service_instance.service_instance.send_service_reminder',
            args: { service_instance: frm.doc.name },
            callback: function(r) {
                if (r.message) frappe.msgprint({ title: __('Reminder Sent'), message: r.message.message, indicator: 'green' });
            }
        });
    });
}


function send_thank_you_message(frm) {
    if (frm.doc.status !== 'Completed') { frappe.msgprint(__('Please mark the service as completed first')); return; }
    frappe.confirm(__('Send thank you message to all present ministry team members?'), function() {
        frappe.call({
            method: 'church.church.doctype.service_instance.service_instance.send_thank_you_message',
            args: { service_instance: frm.doc.name },
            callback: function(r) {
                if (r.message) frappe.msgprint({ title: __('Thank You Sent'), message: r.message.message, indicator: 'green' });
            }
        });
    });
}


function copy_ministry_team_from_service(frm) {
    if (!frm.doc.service) { frappe.msgprint(__('Please select a service first')); return; }
    frappe.call({
        method: 'frappe.client.get',
        args: { doctype: 'Church Service', name: frm.doc.service },
        callback: function(r) {
            if (r.message && r.message.ministry_team) {
                frm.clear_table('ministry_team');
                r.message.ministry_team.forEach(function(tm) {
                    let row = frm.add_child('ministry_team');
                    row.member = tm.member; row.full_name = tm.full_name;
                    row.phone = tm.phone; row.email = tm.email;
                    row.ministry_role = tm.ministry_role; row.responsibility = tm.responsibility;
                    row.present = 1;
                });
                frm.refresh_field('ministry_team');
                frappe.show_alert({ message: __('Ministry team copied'), indicator: 'green' });
            } else {
                frappe.msgprint(__('No ministry team found in service template'));
            }
        }
    });
}


function copy_service_order_from_service(frm) {
    if (!frm.doc.service) { frappe.msgprint(__('Please select a service first')); return; }
    frappe.db.get_value('Church Service', frm.doc.service, 'service_order_template').then(r => {
        if (r.message && r.message.service_order_template) {
            frm.set_value('service_order', r.message.service_order_template);
            frappe.show_alert({ message: __('Service order copied'), indicator: 'green' });
        }
    });
}


function mark_service_completed(frm) {
    frappe.confirm(__('Mark this service as completed?'), function() {
        frm.set_value('status', 'Completed');
        if (!frm.doc.actual_end_time) frm.set_value('actual_end_time', frappe.datetime.now_time());
        frm.save();
    });
}


function generate_service_report(frm) {
    let report_html = `
    <div style="font-family:Arial,sans-serif;max-width:800px;">
        <h2 style="color:#2c3e50;border-bottom:2px solid #3498db;padding-bottom:10px;">
            Service Report — ${frm.doc.service_name}
        </h2>
        <p><strong>Date:</strong> ${frappe.datetime.str_to_user(frm.doc.service_date)}</p>
        <p><strong>Time:</strong> ${frm.doc.actual_start_time} — ${frm.doc.actual_end_time || 'N/A'}</p>
        <p><strong>Status:</strong> ${frm.doc.status}</p>

        <h3 style="color:#34495e;margin-top:24px;">Attendance Summary</h3>
        <table style="width:100%;border-collapse:collapse;margin:10px 0;">
            <tr style="background:#f8f9fa;"><td style="padding:8px;border:1px solid #dee2e6;"><strong>Men</strong></td><td style="padding:8px;border:1px solid #dee2e6;">${frm.doc.men_count || 0}</td></tr>
            <tr><td style="padding:8px;border:1px solid #dee2e6;"><strong>Women</strong></td><td style="padding:8px;border:1px solid #dee2e6;">${frm.doc.women_count || 0}</td></tr>
            <tr style="background:#f8f9fa;"><td style="padding:8px;border:1px solid #dee2e6;"><strong>Children</strong></td><td style="padding:8px;border:1px solid #dee2e6;">${frm.doc.children_count || 0}</td></tr>
            <tr style="background:#e8f4fd;"><td style="padding:8px;border:1px solid #dee2e6;"><strong>Total</strong></td><td style="padding:8px;border:1px solid #dee2e6;"><strong>${frm.doc.total_attendance || 0}</strong></td></tr>
            <tr><td style="padding:8px;border:1px solid #dee2e6;"><strong>First Timers</strong></td><td style="padding:8px;border:1px solid #dee2e6;">${frm.doc.first_timers || 0}</td></tr>
            <tr style="background:#f8f9fa;"><td style="padding:8px;border:1px solid #dee2e6;"><strong>New Converts</strong></td><td style="padding:8px;border:1px solid #dee2e6;">${frm.doc.new_converts || 0}</td></tr>
        </table>

        ${frm.doc.sermon_title ? `<h3 style="color:#34495e;margin-top:24px;">Sermon Details</h3>
        <p><strong>Title:</strong> ${frm.doc.sermon_title}</p>
        <p><strong>Text:</strong> ${frm.doc.sermon_text || 'N/A'}</p>
        <p><strong>Preacher:</strong> ${frm.doc.preacher || 'N/A'}</p>` : ''}
    </div>`;

    let d = new frappe.ui.Dialog({
        title: __('Service Report'),
        fields: [{ fieldtype: 'HTML', options: report_html }],
        primary_action_label: __('Print'),
        primary_action: function() {
            window.open('/printview?doctype=Service Instance&name=' + frm.doc.name);
        }
    });
    d.show();
}


function show_visitor_followup_dashboard(frm) {
    let pending = 0, completed = 0;
    let total = frm.doc.service_visitors ? frm.doc.service_visitors.length : 0;
    if (frm.doc.service_visitors) {
        frm.doc.service_visitors.forEach(v => {
            if (v.follow_up_status === 'Completed') completed++;
            else if (v.follow_up_required) pending++;
        });
    }
    frappe.msgprint({
        title: __('Follow-up Dashboard'),
        message: `
        <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:15px;margin:20px 0;font-family:Arial,sans-serif;">
            <div style="background:#3498db;color:white;padding:20px;border-radius:8px;text-align:center;">
                <div style="font-size:36px;font-weight:bold;">${total}</div><div>Total Visitors</div>
            </div>
            <div style="background:#e74c3c;color:white;padding:20px;border-radius:8px;text-align:center;">
                <div style="font-size:36px;font-weight:bold;">${pending}</div><div>Pending</div>
            </div>
            <div style="background:#27ae60;color:white;padding:20px;border-radius:8px;text-align:center;">
                <div style="font-size:36px;font-weight:bold;">${completed}</div><div>Completed</div>
            </div>
        </div>`,
        wide: true
    });
}


function apply_table_styling(frm) {
    setTimeout(() => {
        if (frm.fields_dict.ministry_team && frm.fields_dict.ministry_team.grid) {
            frm.fields_dict.ministry_team.grid.wrapper.find('.grid-row').each(function(i, row) {
                $(row).css('background-color', i % 2 === 0 ? '#ffffff' : '#f8f9fa');
            });
        }
        if (frm.fields_dict.service_visitors && frm.fields_dict.service_visitors.grid) {
            frm.fields_dict.service_visitors.grid.wrapper.find('.grid-row').each(function(i, row) {
                $(row).css('background-color', i % 2 === 0 ? '#ffffff' : '#fff8e1');
            });
        }
    }, 100);
}


function generate_html_report(frm) {
    frappe.show_alert(__('📄 Generating report...'));
    frappe.call({
        method: 'church.church.doctype.service_instance.service_instance_html_report.preview_report',
        args: { service_instance_name: frm.doc.name },
        callback: function(r) {
            if (r.message) {
                let win = window.open('', '_blank');
                win.document.write(r.message);
                win.document.close();
            }
        }
    });
}


function email_report_dialog(frm) {
    let d = new frappe.ui.Dialog({
        title: __('📧 Email Service Report'),
        fields: [
            { fieldname: 'recipient_type', fieldtype: 'Select', label: 'Send To',
              options: 'Leadership Team\nMinistry Team\nAll Members\nCustom', reqd: 1, default: 'Leadership Team' },
            { fieldname: 'custom_recipients', fieldtype: 'Small Text', label: 'Email Addresses (comma-separated)',
              depends_on: 'eval:doc.recipient_type=="Custom"' }
        ],
        primary_action_label: __('Send Report'),
        primary_action: function(values) {
            d.hide();
            if (values.recipient_type === 'Custom') {
                let recipients = values.custom_recipients.split(',').map(e => e.trim());
                send_email_report(frm, recipients);
            } else {
                get_recipients_by_type(frm, values.recipient_type, function(r) {
                    send_email_report(frm, r);
                });
            }
        }
    });
    d.show();
}


function get_recipients_by_type(frm, type, callback) {
    if (type === 'Ministry Team') {
        return callback(frm.doc.ministry_team.map(m => m.email).filter(Boolean));
    }
    let filters = type === 'Leadership Team'
        ? { is_a_pastor: 1, member_status: 'Active' }
        : { member_status: 'Active' };
    frappe.call({
        method: 'frappe.client.get_list',
        args: { doctype: 'Member', filters: filters, fields: ['email'], limit_page_length: 0 },
        callback: function(r) {
            callback(r.message ? r.message.map(m => m.email).filter(Boolean) : []);
        }
    });
}


function send_email_report(frm, recipients) {
    frappe.show_alert(__('📧 Sending report...'));
    frappe.call({
        method: 'church.church.doctype.service_instance.service_instance_html_report.email_report',
        args: { service_instance_name: frm.doc.name, recipients: JSON.stringify(recipients) },
        callback: function(r) {
            if (r.message && r.message.success) {
                frappe.msgprint({ title: __('✅ Emails Sent'), message: r.message.message, indicator: 'green' });
            }
        }
    });
}


// ============================================================================
// CHILD TABLE EVENTS
// ============================================================================

frappe.ui.form.on('Service Instance Team', {
    member: function(frm, cdt, cdn) {
        let row = frappe.get_doc(cdt, cdn);
        if (row.member) {
            frappe.db.get_value('Member', row.member, ['full_name', 'email', 'mobile_phone']).then(r => {
                if (r.message) {
                    frappe.model.set_value(cdt, cdn, 'full_name', r.message.full_name || '');
                    frappe.model.set_value(cdt, cdn, 'email', r.message.email || '');
                    frappe.model.set_value(cdt, cdn, 'phone', r.message.mobile_phone || '');
                }
            });
        }
    }
});

frappe.ui.form.on('Service Visitor', {
    visitor: function(frm, cdt, cdn) {
        let row = frappe.get_doc(cdt, cdn);
        if (row.visitor) {
            frappe.db.get_value('Visitor', row.visitor,
                ['full_name', 'mobile_phone', 'email', 'visit_type', 'is_born_again',
                 'interested_in_membership', 'interested_in_baptism']).then(r => {
                if (r.message) {
                    frappe.model.set_value(cdt, cdn, 'full_name', r.message.full_name || '');
                    frappe.model.set_value(cdt, cdn, 'phone', r.message.mobile_phone || '');
                    frappe.model.set_value(cdt, cdn, 'email', r.message.email || '');
                    frappe.model.set_value(cdt, cdn, 'visit_type', r.message.visit_type || '');
                    frappe.model.set_value(cdt, cdn, 'is_born_again', r.message.is_born_again || 0);
                    frappe.model.set_value(cdt, cdn, 'interested_in_membership', r.message.interested_in_membership || 0);
                    frappe.model.set_value(cdt, cdn, 'interested_in_baptism', r.message.interested_in_baptism || 0);
                    frappe.call({
                        method: 'frappe.client.get_count',
                        args: { doctype: 'Service Visitor', filters: { visitor: row.visitor } },
                        callback: function(r) {
                            if (r.message <= 1) frappe.model.set_value(cdt, cdn, 'is_first_time', 1);
                            frappe.model.set_value(cdt, cdn, 'visit_count', r.message || 1);
                        }
                    });
                }
            });
        }
    },

    follow_up_required: function(frm, cdt, cdn) {
        let row = frappe.get_doc(cdt, cdn);
        if (row.follow_up_required && !row.follow_up_assigned_to && frm.doc.service) {
            frappe.db.get_value('Church Service', frm.doc.service, 'default_follow_up_coordinator').then(r => {
                if (r.message && r.message.default_follow_up_coordinator) {
                    frappe.model.set_value(cdt, cdn, 'follow_up_assigned_to', r.message.default_follow_up_coordinator);
                }
            });
        }
    }
});