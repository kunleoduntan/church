// Copyright (c) 2024, kunle and contributors
// For license information, please see license.txt


frappe.ui.form.on("Sunday School Class", {
    // ========================================================================
    // FORM REFRESH
    // ========================================================================
    refresh: function(frm) {
        // Set member count as read-only
        frm.set_df_property('member_count', 'read_only', 1);
        
        // Apply zebra striping to member table
        apply_zebra_striping(frm);
        
        // Add custom buttons
        add_custom_buttons(frm);
    },
    
    // ========================================================================
    // BEFORE SAVE - Calculate member count
    // ========================================================================
    before_save: function(frm) {
        calculate_member_count(frm);
    },
    
    // ========================================================================
    // DEMOGRAPHIC GROUP OR BRANCH CHANGE - Show fetch button
    // ========================================================================
    demographic_group: function(frm) {
        if (frm.doc.demographic_group && frm.doc.branch) {
            show_fetch_members_alert(frm);
        }
    },
    
    branch: function(frm) {
        if (frm.doc.demographic_group && frm.doc.branch) {
            show_fetch_members_alert(frm);
        }
    }
});


// ============================================================================
// CHILD TABLE EVENTS
// ============================================================================

frappe.ui.form.on('Sunday School Group Member', {
    sunday_school_group_member_add: function(frm) {
        calculate_member_count(frm);
    },
    
    sunday_school_group_member_remove: function(frm) {
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
    if (frm.doc.sunday_school_group_member) {
        frm.set_value('member_count', frm.doc.sunday_school_group_member.length);
    } else {
        frm.set_value('member_count', 0);
    }
}


function apply_zebra_striping(frm) {
    /**
     * Apply alternating row colors
     */
    setTimeout(() => {
        frm.fields_dict.sunday_school_group_member.grid.wrapper.find('.grid-row').each(function(i, row) {
            if (i % 2 === 0) {
                $(row).css('background-color', '#ffffff');
            } else {
                $(row).css('background-color', '#f0f7ff');
            }
        });
    }, 300);
}


function show_fetch_members_alert(frm) {
    /**
     * Show alert to fetch members
     */
    frappe.show_alert({
        message: __('💡 Ready to fetch {0} members from {1}', 
            [frm.doc.demographic_group, frm.doc.branch]),
        indicator: 'blue'
    }, 5);
}


function add_custom_buttons(frm) {
    /**
     * Add custom action buttons
     */
    
    // Only show buttons if document is saved
    if (frm.doc.__islocal) return;
    
    // Fetch Members Button
    if (frm.doc.demographic_group && frm.doc.branch) {
        frm.add_custom_button(__('👥 Fetch Members'), function() {
            fetch_members_by_demographic(frm);
        }).addClass("btn-primary");
    }
    
    // Send Message Button (only if has members)
    if (frm.doc.sunday_school_group_member && frm.doc.sunday_school_group_member.length > 0) {
        frm.add_custom_button(__('📧 Send Message'), function() {
            show_messaging_dialog(frm);
        }).addClass("btn-success");
    }
    
    // Reports Button (if submitted)
    if (frm.doc.docstatus == 1) {
        frm.add_custom_button(__('📊 Generate Report'), function() {
            generate_class_report(frm);
        }, __("Reports")).addClass("btn-info");
    }
}


function fetch_members_by_demographic(frm) {
    /**
     * Fetch members based on demographic_group and branch
     * SMART: Auto-populates based on filters
     */
    
    if (!frm.doc.demographic_group) {
        frappe.msgprint({
            title: __('Demographic Group Required'),
            indicator: 'red',
            message: __('Please select a Demographic Group first.')
        });
        return;
    }
    
    if (!frm.doc.branch) {
        frappe.msgprint({
            title: __('Branch Required'),
            indicator: 'red',
            message: __('Please select a Branch first.')
        });
        return;
    }
    
    // Confirm if members already exist
    if (frm.doc.sunday_school_group_member && frm.doc.sunday_school_group_member.length > 0) {
        frappe.confirm(
            __('This will replace existing {0} members. Continue?', [frm.doc.sunday_school_group_member.length]),
            function() {
                process_fetch_members(frm);
            }
        );
    } else {
        process_fetch_members(frm);
    }
}


function process_fetch_members(frm) {
    /**
     * Process member fetching
     */
    frappe.show_alert({
        message: __('🔍 Searching for {0} members in {1}...', 
            [frm.doc.demographic_group, frm.doc.branch]),
        indicator: 'blue'
    }, 3);
    
    frappe.call({
        method: 'church.church.doctype.sunday_school_class.sunday_school_class.fetch_members_by_demographic',
        args: {
            class_doc_name: frm.doc.name
        },
        freeze: true,
        freeze_message: __('Fetching Members...'),
        callback: function(r) {
            if (r.message && r.message.success) {
                frappe.show_alert({
                    message: r.message.message,
                    indicator: 'green'
                }, 5);
                
                // Reload the form
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
                message: __('Failed to fetch members. Please try again.')
            });
        }
    });
}


function show_messaging_dialog(frm) {
    /**
     * Show beautiful messaging dialog
     * Multi-channel selection with message preview
     */
    
    let d = new frappe.ui.Dialog({
        title: __('📧 Send Message to Class'),
        fields: [
            {
                fieldname: 'message_section',
                fieldtype: 'Section Break',
                label: __('Message Content')
            },
            {
                fieldname: 'message_text',
                fieldtype: 'Text Editor',
                label: __('Message'),
                reqd: 1,
                description: __('This will be converted to beautiful HTML for email')
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
            // Validate at least one channel selected
            if (!values.send_email && !values.send_sms && !values.send_whatsapp) {
                frappe.msgprint({
                    title: __('No Channel Selected'),
                    indicator: 'red',
                    message: __('Please select at least one delivery channel.')
                });
                return;
            }
            
            // Build channels array
            let channels = [];
            if (values.send_email) channels.push('email');
            if (values.send_sms) channels.push('sms');
            if (values.send_whatsapp) channels.push('whatsapp');
            
            // Close dialog
            d.hide();
            
            // Send messages
            send_class_messages(frm, values.message_text, channels);
        }
    });
    
    d.show();
    
    // Add custom styling
    d.$wrapper.find('.modal-dialog').css('max-width', '700px');
}


function get_recipient_stats_html(frm) {
    /**
     * Generate recipient statistics HTML
     */
    let total = frm.doc.sunday_school_group_member.length;
    let with_email = frm.doc.sunday_school_group_member.filter(m => m.email).length;
    let with_phone = frm.doc.sunday_school_group_member.filter(m => m.phone_no).length;
    
    return `
        <div style="background: linear-gradient(135deg, #e3f2fd 0%, #f3e5f5 100%); 
                    padding: 20px; border-radius: 8px; margin: 10px 0;">
            <table style="width: 100%; font-size: 14px;">
                <tr>
                    <td style="padding: 8px;">
                        <strong>👥 Total Members:</strong>
                    </td>
                    <td style="padding: 8px; text-align: right;">
                        <span style="color: #1976d2; font-weight: bold; font-size: 16px;">${total}</span>
                    </td>
                </tr>
                <tr>
                    <td style="padding: 8px;">
                        <strong>📧 With Email:</strong>
                    </td>
                    <td style="padding: 8px; text-align: right;">
                        <span style="color: #4caf50; font-weight: bold;">${with_email}</span>
                        <span style="color: #9e9e9e;"> (${((with_email/total)*100).toFixed(0)}%)</span>
                    </td>
                </tr>
                <tr>
                    <td style="padding: 8px;">
                        <strong>📱 With Phone:</strong>
                    </td>
                    <td style="padding: 8px; text-align: right;">
                        <span style="color: #ff9800; font-weight: bold;">${with_phone}</span>
                        <span style="color: #9e9e9e;"> (${((with_phone/total)*100).toFixed(0)}%)</span>
                    </td>
                </tr>
            </table>
        </div>
    `;
}


function send_class_messages(frm, message_text, channels) {
    /**
     * Send messages to all class members
     */
    
    frappe.show_alert({
        message: __('📨 Sending messages via {0}...', [channels.join(', ')]),
        indicator: 'blue'
    }, 3);
    
    frappe.call({
        method: 'church.church.doctype.sunday_school_class.sunday_school_class.send_class_message',
        args: {
            class_doc_name: frm.doc.name,
            message_text: message_text,
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
            } else if (r.message && !r.message.success) {
                frappe.msgprint({
                    title: __('Messaging Failed'),
                    indicator: 'red',
                    message: r.message.message || __('Failed to send messages.')
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


function generate_class_report(frm) {
    /**
     * Generate beautiful class report
     * HTML and Excel options
     */
    
    let d = new frappe.ui.Dialog({
        title: __('📊 Generate Class Report'),
        fields: [
            {
                fieldname: 'report_type',
                fieldtype: 'Select',
                label: __('Report Type'),
                options: 'HTML (Beautiful)\nExcel (Spreadsheet)',
                default: 'HTML (Beautiful)',
                reqd: 1
            },
            {
                fieldname: 'include_section',
                fieldtype: 'Section Break',
                label: __('Include in Report')
            },
            {
                fieldname: 'include_demographics',
                fieldtype: 'Check',
                label: __('Demographic Breakdown'),
                default: 1
            },
            {
                fieldname: 'column_break_1',
                fieldtype: 'Column Break'
            },
            {
                fieldname: 'include_contact_info',
                fieldtype: 'Check',
                label: __('Contact Information'),
                default: 1
            },
            {
                fieldname: 'column_break_2',
                fieldtype: 'Column Break'
            },
            {
                fieldname: 'include_charts',
                fieldtype: 'Check',
                label: __('Charts & Analytics'),
                default: 1
            }
        ],
        primary_action_label: __('Generate'),
        primary_action: function(values) {
            d.hide();
            
            frappe.msgprint({
                title: __('Coming Soon'),
                indicator: 'blue',
                message: __('Beautiful HTML and Excel reports with demographic breakdown will be available soon!')
            });
            
            // TODO: Implement report generation
            // Call backend method to generate report
        }
    });
    
    d.show();
}


// ============================================================================
// UTILITY FUNCTIONS
// ============================================================================

function flt(value) {
    /**
     * Convert to float
     */
    return parseFloat(value) || 0;
}