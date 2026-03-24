// Copyright (c) 2024, kunle and contributors
// For license information, please see license.txt

// ============================================================================
// Church Department - Complete Client Script
// Features: Member fetching, Messaging, Birthday wishes, Reports
// ============================================================================

frappe.ui.form.on("Church Department", {
   
    refresh: function(frm) {
        // Set total as read-only
        frm.set_df_property('total', 'read_only', 1);
        
        // Apply zebra striping
        apply_zebra_striping(frm);
        
        // Add custom buttons
        add_custom_buttons(frm);
        
        // Show birthday celebrants alert
        show_birthday_alert(frm);
    },
    
    // ========================================================================
    // BEFORE SAVE
    // ========================================================================
    before_save: function(frm) {
        calculate_member_count(frm);
    }
});

// ============================================================================
// CHILD TABLE EVENTS
// ============================================================================

frappe.ui.form.on('Departmental Member', {
    members_add: function(frm) {
        calculate_member_count(frm);
    },
    
    members_remove: function(frm) {
        calculate_member_count(frm);
    }
});

// ============================================================================
// HELPER FUNCTIONS
// ============================================================================

function calculate_member_count(frm) {
    /**
     * Calculate total member count
     */
    if (frm.doc.members) {
        frm.set_value('total', frm.doc.members.length);
    } else {
        frm.set_value('total', 0);
    }
}

function apply_zebra_striping(frm) {
    /**
     * Apply alternating row colors
     */
    setTimeout(() => {
        frm.fields_dict.members.grid.wrapper.find('.grid-row').each(function(i, row) {
            if (i % 2 === 0) {
                $(row).css('background-color', '#ffffff');
            } else {
                $(row).css('background-color', '#e3f2fd');
            }
        });
    }, 300);
}

function show_birthday_alert(frm) {
    /**
     * Show alert if there are birthday celebrants today
     */
    if (!frm.doc.members) return;
    
    let today = frappe.datetime.nowdate();
    let today_date = frappe.datetime.str_to_obj(today);
    
    let celebrants = frm.doc.members.filter(m => {
        if (!m.date_of_birth) return false;
        let dob = frappe.datetime.str_to_obj(m.date_of_birth);
        return dob.getMonth() === today_date.getMonth() && dob.getDate() === today_date.getDate();
    });
    
    if (celebrants.length > 0) {
        let names = celebrants.map(c => c.full_name).join(', ');
        frappe.show_alert({
            message: __('🎉 Birthday Today: {0}', [names]),
            indicator: 'blue'
        }, 10);
    }
}

function add_custom_buttons(frm) {
    /**
     * Add all custom action buttons
     */
    
    if (frm.doc.__islocal) return;
    
    // Fetch Members Button
    frm.add_custom_button(__('👥 Fetch Members'), function() {
        show_fetch_members_dialog(frm);
    }).addClass("btn-primary");
    
    // Send Message Button
    if (frm.doc.members && frm.doc.members.length > 0) {
        frm.add_custom_button(__('📧 Send Message'), function() {
            show_messaging_dialog(frm);
        }).addClass("btn-success");
    }
    
    // Birthday Wishes Button
    frm.add_custom_button(__('🎂 Birthday Wishes'), function() {
        send_birthday_wishes(frm);
    }, __("Actions")).addClass("btn-info");
    
    // Reports Menu
    frm.add_custom_button(__('📊 HTML Report'), function() {
        generate_html_report(frm);
    }, __("Reports"));
    
    frm.add_custom_button(__('📑 Excel Export'), function() {
        generate_excel_report(frm);
    }, __("Reports"));
}

function show_fetch_members_dialog(frm) {
    /**
     * Show dialog to fetch members from Member Department table
     */
    
    let d = new frappe.ui.Dialog({
        title: __('Fetch Department Members'),
        fields: [
            {
                fieldname: 'info',
                fieldtype: 'HTML',
                options: `
                    <div style="background: #e3f2fd; padding: 15px; border-radius: 8px; margin-bottom: 15px;">
                        <p style="margin: 0; color: #1976d2;">
                            <strong>ℹ️ How it works:</strong><br>
                            This will fetch all members who have <strong>${frm.doc.department_name}</strong> 
                            in their "Member Department" table.
                        </p>
                    </div>
                `
            },
            {
                fieldname: 'fetch_mode',
                fieldtype: 'Select',
                label: __('Fetch Mode'),
                options: 'All Active Members\nPrimary Department Only',
                default: 'All Active Members',
                reqd: 1,
                description: __('Choose which members to fetch')
            },
            {
                fieldname: 'replace_existing',
                fieldtype: 'Check',
                label: __('Replace Existing Members'),
                default: 1,
                description: __('Uncheck to append to existing list')
            }
        ],
        primary_action_label: __('Fetch Members'),
        primary_action: function(values) {
            if (values.replace_existing === 0 && frm.doc.members && frm.doc.members.length > 0) {
                frappe.confirm(
                    __('This will add members to existing {0} members. Continue?', [frm.doc.members.length]),
                    function() {
                        d.hide();
                        process_fetch_members(frm, values.fetch_mode);
                    }
                );
            } else {
                d.hide();
                process_fetch_members(frm, values.fetch_mode);
            }
        }
    });
    
    d.show();
}

function process_fetch_members(frm, fetch_mode) {
    /**
     * Process member fetching from backend
     */
    
    let mode = fetch_mode === 'Primary Department Only' ? 'primary_only' : 'active_only';
    
    frappe.show_alert({
        message: __('🔍 Searching for department members...'),
        indicator: 'blue'
    }, 3);
    
    frappe.call({
        method: 'church.church.doctype.church_department.church_department.fetch_department_members',
        args: {
            department_name: frm.doc.name,
            fetch_mode: mode
        },
        freeze: true,
        freeze_message: __('Fetching Members...'),
        callback: function(r) {
            if (r.message && r.message.success) {
                frappe.show_alert({
                    message: r.message.message,
                    indicator: 'green'
                }, 5);
                
                frm.reload_doc();
            } else if (r.message && !r.message.success) {
                frappe.msgprint({
                    title: __('No Members Found'),
                    indicator: 'orange',
                    message: r.message.message
                });
            }
        },
        error: function(r) {
            frappe.msgprint({
                title: __('Error'),
                indicator: 'red',
                message: __('Failed to fetch members. Check error log.')
            });
        }
    });
}

function show_messaging_dialog(frm) {
    /**
     * Show messaging dialog with HTML editor and channel selection
     */
    
    let d = new frappe.ui.Dialog({
        title: __('📧 Send Message to Department'),
        fields: [
            {
                fieldname: 'message_section',
                fieldtype: 'Section Break',
                label: __('Message Content')
            },
            {
                fieldname: 'message_html',
                fieldtype: 'HTML Editor',
                label: __('Message'),
                reqd: 1,
                description: __('This will be containerized in beautiful HTML for email')
            },
            {
                fieldname: 'channels_section',
                fieldtype: 'Section Break',
                label: __('Delivery Channels')
            },
            {
                fieldname: 'send_email',
                fieldtype: 'Check',
                label: __('📧 Send via Email'),
                default: 1
            },
            {
                fieldname: 'column_break_1',
                fieldtype: 'Column Break'
            },
            {
                fieldname: 'send_sms',
                fieldtype: 'Check',
                label: __('📱 Send via SMS')
            },
            {
                fieldname: 'column_break_2',
                fieldtype: 'Column Break'
            },
            {
                fieldname: 'send_whatsapp',
                fieldtype: 'Check',
                label: __('💬 Send via WhatsApp')
            },
            {
                fieldname: 'stats_section',
                fieldtype: 'Section Break',
                label: __('Recipients')
            },
            {
                fieldname: 'recipient_info',
                fieldtype: 'HTML',
                options: get_recipient_stats_html(frm)
            }
        ],
        primary_action_label: __('Send Messages'),
        primary_action: function(values) {
            // Validate
            if (!values.send_email && !values.send_sms && !values.send_whatsapp) {
                frappe.msgprint({
                    title: __('No Channel Selected'),
                    indicator: 'red',
                    message: __('Please select at least one delivery channel.')
                });
                return;
            }
            
            // Build channels
            let channels = [];
            if (values.send_email) channels.push('email');
            if (values.send_sms) channels.push('sms');
            if (values.send_whatsapp) channels.push('whatsapp');
            
            d.hide();
            send_department_messages(frm, values.message_html, channels);
        }
    });
    
    d.show();
    d.$wrapper.find('.modal-dialog').css('max-width', '750px');
}

function get_recipient_stats_html(frm) {
    /**
     * Generate recipient statistics HTML
     */
    let total = frm.doc.members.length;
    let with_email = frm.doc.members.filter(m => m.email).length;
    let with_phone = frm.doc.members.filter(m => m.mobile_phone).length;
    
    return `
        <div style="background: linear-gradient(135deg, #e3f2fd 0%, #f3e5f5 100%); 
                    padding: 20px; border-radius: 8px;">
            <table style="width: 100%; font-size: 14px;">
                <tr>
                    <td style="padding: 8px;"><strong>👥 Total Members:</strong></td>
                    <td style="padding: 8px; text-align: right;">
                        <span style="color: #1976d2; font-weight: bold; font-size: 16px;">${total}</span>
                    </td>
                </tr>
                <tr>
                    <td style="padding: 8px;"><strong>📧 With Email:</strong></td>
                    <td style="padding: 8px; text-align: right;">
                        <span style="color: #4caf50; font-weight: bold;">${with_email}</span>
                        <span style="color: #9e9e9e;"> (${((with_email/total)*100).toFixed(0)}%)</span>
                    </td>
                </tr>
                <tr>
                    <td style="padding: 8px;"><strong>📱 With Phone:</strong></td>
                    <td style="padding: 8px; text-align: right;">
                        <span style="color: #ff9800; font-weight: bold;">${with_phone}</span>
                        <span style="color: #9e9e9e;"> (${((with_phone/total)*100).toFixed(0)}%)</span>
                    </td>
                </tr>
            </table>
        </div>
    `;
}

function send_department_messages(frm, message_html, channels) {
    /**
     * Send messages via backend
     */
    
    frappe.show_alert({
        message: __('📨 Sending messages via {0}...', [channels.join(', ')]),
        indicator: 'blue'
    }, 3);
    
    frappe.call({
        method: 'church.church.doctype.church_department.church_department.send_department_message',
        args: {
            department_name: frm.doc.name,
            message_html: message_html,
            channels: JSON.stringify(channels)
        },
        freeze: true,
        freeze_message: __('Sending Messages...'),
        callback: function(r) {
            if (r.message && r.message.success) {
                frappe.msgprint({
                    title: __('Messages Sent'),
                    indicator: 'green',
                    message: r.message.message
                });
            }
        },
        error: function(r) {
            frappe.msgprint({
                title: __('Error'),
                indicator: 'red',
                message: __('Failed to send messages. Check error log.')
            });
        }
    });
}

function send_birthday_wishes(frm) {
    /**
     * Send birthday wishes to today's celebrants
     */
    
    frappe.confirm(
        __('Send birthday wishes to all members celebrating today in {0}?', [frm.doc.department_name]),
        function() {
            frappe.call({
                method: 'church.church.doctype.church_department.church_department.send_birthday_wishes_to_department',
                args: {
                    department_name: frm.doc.name
                },
                freeze: true,
                freeze_message: __('Sending Birthday Wishes...'),
                callback: function(r) {
                    if (r.message && r.message.success) {
                        frappe.msgprint({
                            title: __('🎉 Birthday Wishes Sent'),
                            indicator: 'green',
                            message: __('Sent {0} wishes, {1} failed', [r.message.sent, r.message.failed])
                        });
                    }
                }
            });
        }
    );
}

function generate_html_report(frm) {
    /**
     * Generate beautiful HTML report
     */
    
    frappe.msgprint({
        title: __('Coming Soon'),
        indicator: 'blue',
        message: __('Beautiful HTML department report will be available soon!')
    });
    
    // TODO: Implement HTML report generation
}

function generate_excel_report(frm) {
    /**
     * Generate Excel export
     */
    
    frappe.msgprint({
        title: __('Coming Soon'),
        indicator: 'blue',
        message: __('Excel export with professional formatting will be available soon!')
    });
    
    // TODO: Implement Excel export
}