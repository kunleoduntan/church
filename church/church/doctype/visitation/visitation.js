frappe.ui.form.on('Visitation', {
    refresh: function(frm) {
        // Add custom buttons
        add_custom_buttons(frm);
        
        // Apply zebra striping to team table
        apply_team_table_styling(frm);
        
        // Add status indicator
        add_status_indicator(frm);
    },
    
    date_of_visitation: function(frm) {
        if (frm.doc.date_of_visitation) {
            // Set day name
            const reportingDate = new Date(frm.doc.date_of_visitation);
            const dayName = reportingDate.toLocaleString('default', { weekday: 'long' });
            frm.set_value('day', dayName);
            
            // Auto-generate report title if not set
            if (!frm.doc.visitation_report && frm.doc.visitee_full_name) {
                frm.set_value('visitation_report', 
                    `<h3>Visitation Report: ${frm.doc.visitee_full_name}</h3>
                     <p><strong>Date:</strong> ${frappe.datetime.str_to_user(frm.doc.date_of_visitation)}</p>
                     <p><strong>Type:</strong> ${frm.doc.type}</p>
                     <hr>
                     <h4>Report Details:</h4>
                     <p>[Enter visitation details here...]</p>`
                );
            }
        }
    },
    
    member_id: function(frm) {
        // Fetch member details
        if (frm.doc.member_id) {
            frappe.call({
                method: 'frappe.client.get',
                args: {
                    doctype: 'Member',
                    name: frm.doc.member_id
                },
                callback: function(r) {
                    if (r.message) {
                        const member = r.message;
                        
                        // Update contact fields - using correct Member field names
                        if (!frm.doc.email) frm.set_value('email', member.email);
                        if (!frm.doc.phone) frm.set_value('phone', member.mobile_phone);
                        if (!frm.doc.alternative_phone) frm.set_value('alternative_phone', member.alternative_phone);
                        if (!frm.doc.address) frm.set_value('address', member.address);
                        if (!frm.doc.location) frm.set_value('location', member.city || member.state);
                        
                        // Auto-set branch if not already set
                        if (!frm.doc.branch && member.branch) {
                            frm.set_value('branch', member.branch);
                        }
                    }
                }
            });
        }
    },
    
    team_leader: function(frm) {
        // Fetch team leader details and auto-set branch
        if (frm.doc.team_leader) {
            frappe.call({
                method: 'frappe.client.get',
                args: {
                    doctype: 'Member',
                    name: frm.doc.team_leader
                },
                callback: function(r) {
                    if (r.message) {
                        const team_leader = r.message;
                        
                        // Auto-set branch from team leader if not set
                        if (!frm.doc.branch && team_leader.branch) {
                            frm.set_value('branch', team_leader.branch);
                        }
                        
                        // Check if team leader is authorized
                        if (!team_leader.is_cancellor && !team_leader.is_follow_up_cordinator) {
                            frappe.msgprint({
                                title: __('Authorization Warning'),
                                message: __(`${team_leader.full_name} is not set as a Counsellor or Follow-up Coordinator. Please ensure proper authorization.`),
                                indicator: 'orange'
                            });
                        }
                    }
                }
            });
        }
    },
    
    status: function(frm) {
        // Update completed date when status changes to Completed
        if (frm.doc.status === 'Completed' && !frm.doc.completed_date) {
            frm.set_value('completed_date', frappe.datetime.now_datetime());
        }
    }
});

// Child table event for Visitation Team
frappe.ui.form.on('Visitation Team', {
    member_id: function(frm, cdt, cdn) {
        // Auto-fetch member details when team member is added
        let row = locals[cdt][cdn];
        
        if (row.member_id) {
            frappe.call({
                method: 'frappe.client.get',
                args: {
                    doctype: 'Member',
                    name: row.member_id
                },
                callback: function(r) {
                    if (r.message) {
                        const member = r.message;
                        
                        // Set fetched fields
                        frappe.model.set_value(cdt, cdn, 'full_name', member.full_name);
                        frappe.model.set_value(cdt, cdn, 'email', member.email);
                        frappe.model.set_value(cdt, cdn, 'phone_no', member.mobile_phone);
                    }
                }
            });
        }
    }
});

// Helper functions
function add_custom_buttons(frm) {
    if (frm.doc.docstatus === 1) {
        // Export to Excel button
        frm.add_custom_button(__('Export to Excel'), function() {
            export_visitation_to_excel(frm);
        }, __('Actions'));
        
        // Send Email button
        frm.add_custom_button(__('Send Report via Email'), function() {
            send_visitation_email(frm);
        }, __('Actions'));
        
        // Print button
        frm.add_custom_button(__('Print Report'), function() {
            frappe.set_route('print', frm.doctype, frm.doc.name, 'Visitation Report');
        }, __('Actions'));
    }
    
    // Add team member button
    if (frm.doc.docstatus === 0) {
        frm.add_custom_button(__('Add Team Member'), function() {
            add_team_member_dialog(frm);
        });
    }
}

function apply_team_table_styling(frm) {
    // Apply zebra striping with slight delay to ensure grid is rendered
    setTimeout(function() {
        frm.fields_dict.visitation_team.grid.wrapper.find('.grid-row').each(function(i, row) {
            if (i % 2 === 0) {
                $(row).css('background-color', '#ffffff');
            } else {
                $(row).css('background-color', '#f0f8ff');
            }
        });
    }, 500);
}

function add_status_indicator(frm) {
    const status_colors = {
        'Assigned': 'blue',
        'In Progress': 'orange',
        'Completed': 'green',
        'Cancelled': 'red',
        'Rescheduled': 'yellow'
    };
    
    if (frm.doc.status) {
        frm.dashboard.add_indicator(
            __(frm.doc.status), 
            status_colors[frm.doc.status] || 'gray'
        );
    }
}

function add_team_member_dialog(frm) {
    if (!frm.doc.branch) {
        frappe.msgprint(__('Please set Branch first before adding team members'));
        return;
    }
    
    const dialog = new frappe.ui.Dialog({
        title: __('Add Team Member'),
        fields: [
            {
                fieldname: 'member_id',
                fieldtype: 'Link',
                label: __('Member'),
                options: 'Member',
                reqd: 1,
                get_query: function() {
                    return {
                        filters: {
                            'branch': frm.doc.branch,
                            'member_status': 'Active'
                        }
                    };
                },
                onchange: function() {
                    // Preview member details
                    let member_id = dialog.get_value('member_id');
                    if (member_id) {
                        frappe.call({
                            method: 'frappe.client.get',
                            args: {
                                doctype: 'Member',
                                name: member_id
                            },
                            callback: function(r) {
                                if (r.message) {
                                    dialog.set_value('member_name', r.message.full_name);
                                    dialog.set_value('member_email', r.message.email);
                                    dialog.set_value('member_phone', r.message.mobile_phone);
                                }
                            }
                        });
                    }
                }
            },
            {
                fieldname: 'member_name',
                fieldtype: 'Data',
                label: __('Name'),
                read_only: 1
            },
            {
                fieldname: 'col_break_1',
                fieldtype: 'Column Break'
            },
            {
                fieldname: 'member_email',
                fieldtype: 'Data',
                label: __('Email'),
                read_only: 1
            },
            {
                fieldname: 'member_phone',
                fieldtype: 'Data',
                label: __('Phone'),
                read_only: 1
            },
            {
                fieldname: 'section_break_1',
                fieldtype: 'Section Break'
            },
            {
                fieldname: 'role',
                fieldtype: 'Data',
                label: __('Role'),
                default: 'Team Member'
            },
            {
                fieldname: 'note',
                fieldtype: 'Small Text',
                label: __('Note')
            }
        ],
        primary_action_label: __('Add Member'),
        primary_action: function(values) {
            const child = frm.add_child('visitation_team');
            child.member_id = values.member_id;
            child.full_name = values.member_name;
            child.email = values.member_email;
            child.phone_no = values.member_phone;
            child.role = values.role;
            child.note = values.note;
            
            frm.refresh_field('visitation_team');
            dialog.hide();
            
            frappe.show_alert({
                message: __('Team member added successfully'),
                indicator: 'green'
            }, 3);
        }
    });
    
    dialog.show();
}

function export_visitation_to_excel(frm) {
    frappe.show_alert({
        message: __('Generating Excel report...'),
        indicator: 'blue'
    }, 3);
    
    frappe.call({
        method: 'church.church.doctype.visitation.visitation_excel_export.download_excel',
        args: {
            visitation_name: frm.doc.name
        },
        callback: function(r) {
            if (r.message && r.message.success) {
                window.open(r.message.file_url);
                frappe.show_alert({
                    message: __('Excel file generated successfully!'),
                    indicator: 'green'
                }, 5);
            } else {
                frappe.msgprint({
                    title: __('Export Failed'),
                    message: __('Failed to generate Excel file. Please check error logs.'),
                    indicator: 'red'
                });
            }
        },
        error: function(r) {
            frappe.msgprint({
                title: __('Export Error'),
                message: __('An error occurred while generating the Excel file.'),
                indicator: 'red'
            });
        }
    });
}

function send_visitation_email(frm) {
    const dialog = new frappe.ui.Dialog({
        title: __('Send Visitation Report via Email'),
        fields: [
            {
                fieldname: 'recipients',
                fieldtype: 'Small Text',
                label: __('Recipients (comma-separated emails)'),
                reqd: 1,
                default: frm.doc.email || '',
                description: __('Enter multiple email addresses separated by commas')
            },
            {
                fieldname: 'include_excel',
                fieldtype: 'Check',
                label: __('Include Excel Attachment'),
                default: 1
            },
            {
                fieldname: 'message',
                fieldtype: 'Text Editor',
                label: __('Additional Message'),
                description: __('This message will be included at the top of the email')
            }
        ],
        primary_action_label: __('Send Email'),
        primary_action: function(values) {
            // Validate email addresses
            const emails = values.recipients.split(',').map(e => e.trim()).filter(e => e);
            const invalid_emails = emails.filter(email => !frappe.utils.validate_type(email, 'email'));
            
            if (invalid_emails.length > 0) {
                frappe.msgprint({
                    title: __('Invalid Email'),
                    message: __('Please check the following email addresses: ') + invalid_emails.join(', '),
                    indicator: 'red'
                });
                return;
            }
            
            // Show loading message
            frappe.show_alert({
                message: __('Sending email...'),
                indicator: 'blue'
            }, 3);
            
            frappe.call({
                method: 'church.church.doctype.visitation.visitation_excel_export.send_visitation_email',
                args: {
                    visitation_name: frm.doc.name,
                    recipients: values.recipients,
                    include_excel: values.include_excel,
                    additional_message: values.message || ''
                },
                callback: function(r) {
                    if (r.message && r.message.success) {
                        frappe.show_alert({
                            message: __(r.message.message),
                            indicator: 'green'
                        }, 5);
                        dialog.hide();
                    } else {
                        frappe.msgprint({
                            title: __('Email Failed'),
                            message: __('Failed to send email: ') + (r.message.error || 'Unknown error'),
                            indicator: 'red'
                        });
                    }
                },
                error: function(r) {
                    frappe.msgprint({
                        title: __('Email Error'),
                        message: __('An error occurred while sending the email.'),
                        indicator: 'red'
                    });
                }
            });
        }
    });
    
    dialog.show();
}