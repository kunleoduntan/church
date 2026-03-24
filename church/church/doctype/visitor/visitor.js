// Copyright (c) 2026, kunle and contributors
// For license information, please see license.txt

// Visitor form controller with automated features
frappe.ui.form.on('Visitor', {
    onload: function(frm) {
        // Set query filters
        frm.set_query("service", function() {
            return {
                filters: {
                    "status": "Active"
                }
            };
        });
        
        frm.set_query("referrer_name", function() {
            return {
                filters: {
                    "member_status": "Active"
                }
            };
        });
        
        frm.set_query("follow_up_coordinator", function() {
            return {
                filters: [
                    ["Member", "member_status", "=", "Active"],
                    ["Member", "is_counsellor", "=", 1],
                    ["Member", "is_follow_up_coordinator", "=", 1]
                ]
            };
        });
        
        frm.set_query("branch", function() {
            return {
                filters: {
                    "disabled": 0
                }
            };
        });
    },
    
    refresh: function(frm) {
        // Apply alternating row colors to follow-up history
        apply_table_styling(frm);
        
        // Add custom buttons
        if (!frm.is_new()) {
            // Button to send welcome message
            if (frm.doc.conversion_status === 'New Visitor') {
                frm.add_custom_button(__('Send Welcome Message'), function() {
                    send_welcome_message(frm);
                }, __("Communications"));
            }
            
            // Button to schedule follow-up
            if (frm.doc.conversion_status !== 'Converted to Member' && 
                frm.doc.conversion_status !== 'Lost Contact') {
                frm.add_custom_button(__('Schedule Follow-up'), function() {
                    schedule_followup(frm);
                }, __("Actions"));
            }
            
            // Button to convert to member
            if (frm.doc.conversion_status === 'In Follow-up' && !frm.doc.date_converted) {
                frm.add_custom_button(__('Convert to Member'), function() {
                    convert_to_member(frm);
                }, __("Actions"));
            }
            
            // Button to view follow-up dashboard
            if (frm.doc.follow_up_history && frm.doc.follow_up_history.length > 0) {
                frm.add_custom_button(__('Follow-up Dashboard'), function() {
                    show_followup_dashboard(frm);
                }, __("Reports"));
            }
        }
    },
    
    first_name: function(frm) {
        update_full_name(frm);
    },
    
    middle_name: function(frm) {
        update_full_name(frm);
    },
    
    last_name: function(frm) {
        update_full_name(frm);
    },
    
    date_of_birth: function(frm) {
        calculate_age_and_category(frm);
    },
    
    branch: function(frm) {
        // Update branch for all follow-up history records
        if (frm.doc.follow_up_history) {
            frm.doc.follow_up_history.forEach(function(row) {
                frappe.model.set_value(row.doctype, row.name, 'branch', frm.doc.branch);
            });
            frm.refresh_field('follow_up_history');
        }
    },
    
    conversion_status: function(frm) {
        if (frm.doc.conversion_status === 'Converted to Member' && !frm.doc.date_converted) {
            frm.set_value('date_converted', frappe.datetime.now_date());
        }
    },
    
    before_save: function(frm) {
        // Update full name
        update_full_name(frm);
        
        // Calculate age and category
        if (frm.doc.date_of_birth) {
            calculate_age_and_category(frm);
        }
        
        // Update follow-up count
        if (frm.doc.follow_up_history) {
            frm.set_value('follow_up_count', frm.doc.follow_up_history.length);
            
            // Update last follow-up date
            if (frm.doc.follow_up_history.length > 0) {
                let latest_date = frm.doc.follow_up_history[0].date;
                frm.doc.follow_up_history.forEach(function(row) {
                    if (row.date && row.date > latest_date) {
                        latest_date = row.date;
                    }
                });
                frm.set_value('last_follow_up_date', latest_date);
            }
        }
        
        // Auto-assign follow-up coordinator if not set
        if (!frm.doc.follow_up_coordinator && frm.is_new()) {
            // This will be handled by server-side method
            frm.set_value('_assign_coordinator', 1);
        }
    },
    
    after_save: function(frm) {
        // Refresh to show updated data
        frm.reload_doc();
    }
});

// Child table event handler for Follow Up
frappe.ui.form.on('Follow Up', {
    date: function(frm, cdt, cdn) {
        let row = frappe.get_doc(cdt, cdn);
        
        if (row.date) {
            const date = new Date(row.date);
            const dayName = date.toLocaleString('default', { weekday: 'short' });
            frappe.model.set_value(cdt, cdn, 'day', dayName);
        }
    },
    
    member_id: function(frm, cdt, cdn) {
        let row = frappe.get_doc(cdt, cdn);
        
        if (row.member_id) {
            frappe.db.get_value('Member', row.member_id, 'full_name')
                .then(r => {
                    if (r.message) {
                        frappe.model.set_value(cdt, cdn, 'full_name', r.message.full_name);
                    }
                });
        }
    }
});

// Update full name function
function update_full_name(frm) {
    let parts = [
        frm.doc.salutation,
        frm.doc.first_name,
        frm.doc.middle_name,
        frm.doc.last_name
    ].filter(Boolean);
    
    let fullName = parts.join(' ').trim();
    frm.set_value('full_name', fullName);
}

// Calculate age and category
function calculate_age_and_category(frm) {
    if (!frm.doc.date_of_birth) return;
    
    let today = new Date();
    let birthDate = new Date(frm.doc.date_of_birth);
    let age = today.getFullYear() - birthDate.getFullYear();
    let monthDiff = today.getMonth() - birthDate.getMonth();
    
    if (monthDiff < 0 || (monthDiff === 0 && today.getDate() < birthDate.getDate())) {
        age--;
    }
    
    frm.set_value('age', age);
    
    // Set age category
    let category;
    if (age < 13) {
        category = 'Child';
    } else if (age < 18) {
        category = 'Teenager';
    } else if (age < 36) {
        category = 'Youth';
    } else if (age < 60) {
        category = 'Adult';
    } else {
        category = 'Senior';
    }
    
    frm.set_value('age_category', category);
}

// Send welcome message
function send_welcome_message(frm) {
    frappe.confirm(
        __('Send welcome message to {0}?', [frm.doc.full_name]),
        function() {
            frappe.call({
                method: 'church.church.doctype.visitor.visitor.send_welcome_message',
                args: {
                    visitor: frm.doc.name
                },
                callback: function(r) {
                    if (r.message) {
                        frappe.msgprint({
                            title: __('Message Sent'),
                            message: r.message.message,
                            indicator: 'green'
                        });
                    }
                }
            });
        }
    );
}

// Schedule follow-up
function schedule_followup(frm) {
    let d = new frappe.ui.Dialog({
        title: __('Schedule Follow-up'),
        fields: [
            {
                fieldname: 'follow_up_date',
                fieldtype: 'Date',
                label: 'Follow-up Date',
                reqd: 1,
                default: frappe.datetime.add_days(frappe.datetime.now_date(), 3)
            },
            {
                fieldname: 'follow_up_coordinator',
                fieldtype: 'Link',
                label: 'Assign To',
                options: 'Member',
                get_query: function() {
                    return {
                        filters: [
                            ["Member", "member_status", "=", "Active"],
                            ["Member", "is_counsellor", "=", 1],
                            ["Member", "is_follow_up_coordinator", "=", 1]
                        ]
                    };
                }
            },
            {
                fieldname: 'method',
                fieldtype: 'Link',
                label: 'Follow-up Method',
                options: 'Follow Up Method'
            },
            {
                fieldname: 'notes',
                fieldtype: 'Small Text',
                label: 'Notes'
            }
        ],
        primary_action_label: __('Schedule'),
        primary_action: function(values) {
            frm.set_value('next_follow_up_date', values.follow_up_date);
            if (values.follow_up_coordinator) {
                frm.set_value('follow_up_coordinator', values.follow_up_coordinator);
            }
            frm.save();
            d.hide();
            
            frappe.show_alert({
                message: __('Follow-up scheduled for {0}', [values.follow_up_date]),
                indicator: 'green'
            });
        }
    });
    
    // Pre-fill coordinator if available
    if (frm.doc.follow_up_coordinator) {
        d.set_value('follow_up_coordinator', frm.doc.follow_up_coordinator);
    }
    
    d.show();
}

// Convert to member
function convert_to_member(frm) {
    frappe.confirm(
        __('Convert {0} to church member?', [frm.doc.full_name]),
        function() {
            frappe.call({
                method: 'church.church.doctype.visitor.visitor.convert_to_member',
                args: {
                    visitor: frm.doc.name
                },
                callback: function(r) {
                    if (r.message) {
                        frappe.msgprint({
                            title: __('Success'),
                            message: __('Visitor converted to member successfully!'),
                            indicator: 'green'
                        });
                        
                        frm.set_value('conversion_status', 'Converted to Member');
                        frm.set_value('date_converted', frappe.datetime.now_date());
                        frm.save();
                        
                        // Open the member record
                        setTimeout(() => {
                            frappe.set_route('Form', 'Member', r.message.member);
                        }, 1000);
                    }
                }
            });
        }
    );
}

// Show follow-up dashboard
function show_followup_dashboard(frm) {
    let total_followups = frm.doc.follow_up_count || 0;
    let last_followup = frm.doc.last_follow_up_date || 'Never';
    let next_followup = frm.doc.next_follow_up_date || 'Not scheduled';
    let coordinator = frm.doc.follow_up_coordinator || 'Not assigned';
    
    // Get coordinator name
    let coordinator_display = coordinator;
    if (coordinator !== 'Not assigned') {
        frappe.db.get_value('Member', coordinator, 'full_name')
            .then(r => {
                if (r.message) {
                    coordinator_display = r.message.full_name;
                    show_dashboard_dialog();
                }
            });
    } else {
        show_dashboard_dialog();
    }
    
    function show_dashboard_dialog() {
        let dashboard_html = `
        <div style="font-family: Arial, sans-serif;">
            <h3 style="color: #2c3e50; margin-bottom: 20px;">Follow-up Dashboard - ${frm.doc.full_name}</h3>
            
            <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 15px; margin-bottom: 20px;">
                <div style="background: #3498db; color: white; padding: 20px; border-radius: 8px; text-align: center;">
                    <div style="font-size: 36px; font-weight: bold;">${total_followups}</div>
                    <div style="font-size: 14px;">Total Follow-ups</div>
                </div>
                <div style="background: #27ae60; color: white; padding: 20px; border-radius: 8px; text-align: center;">
                    <div style="font-size: 18px; font-weight: bold;">${frm.doc.conversion_status}</div>
                    <div style="font-size: 14px;">Current Status</div>
                </div>
            </div>
            
            <div style="background: #f8f9fa; padding: 15px; border-radius: 8px; margin-bottom: 15px;">
                <p style="margin: 5px 0;"><strong>Last Follow-up:</strong> ${last_followup}</p>
                <p style="margin: 5px 0;"><strong>Next Follow-up:</strong> ${next_followup}</p>
                <p style="margin: 5px 0;"><strong>Coordinator:</strong> ${coordinator_display}</p>
            </div>
            
            ${frm.doc.follow_up_history && frm.doc.follow_up_history.length > 0 ? `
            <h4 style="color: #34495e; margin-top: 20px;">Recent Follow-ups</h4>
            <table style="width: 100%; border-collapse: collapse; font-size: 13px;">
                <thead>
                    <tr style="background: #f8f9fa;">
                        <th style="padding: 8px; border: 1px solid #dee2e6; text-align: left;">Date</th>
                        <th style="padding: 8px; border: 1px solid #dee2e6; text-align: left;">By</th>
                        <th style="padding: 8px; border: 1px solid #dee2e6; text-align: left;">Method</th>
                        <th style="padding: 8px; border: 1px solid #dee2e6; text-align: left;">Response</th>
                    </tr>
                </thead>
                <tbody>
                    ${frm.doc.follow_up_history.slice(0, 5).map(f => `
                    <tr>
                        <td style="padding: 8px; border: 1px solid #dee2e6;">${f.date || '-'}</td>
                        <td style="padding: 8px; border: 1px solid #dee2e6;">${f.full_name || '-'}</td>
                        <td style="padding: 8px; border: 1px solid #dee2e6;">${f.method || '-'}</td>
                        <td style="padding: 8px; border: 1px solid #dee2e6;">${f.response || '-'}</td>
                    </tr>
                    `).join('')}
                </tbody>
            </table>
            ` : '<p style="color: #7f8c8d;">No follow-up history yet</p>'}
        </div>
        `;
        
        frappe.msgprint({
            title: __('Follow-up Dashboard'),
            message: dashboard_html,
            wide: true
        });
    }
}

// Apply table styling
function apply_table_styling(frm) {
    setTimeout(() => {
        if (frm.fields_dict.follow_up_history && frm.fields_dict.follow_up_history.grid) {
            frm.fields_dict.follow_up_history.grid.wrapper.find('.grid-row').each(function(i, row) {
                if (i % 2 === 0) {
                    $(row).css('background-color', '#ffffff');
                } else {
                    $(row).css('background-color', '#ffefd5');
                }
            });
        }
    }, 100);
}