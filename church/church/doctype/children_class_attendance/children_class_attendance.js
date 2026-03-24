// Copyright (c) 2026, kunle and contributors
// For license information, please see license.txt



frappe.ui.form.on("Children Class Attendance", {
    // Form refresh event - Setup UI and buttons
    refresh: function(frm) {
        // Set read-only properties for total fields
        set_total_fields_readonly(frm);
        
        // Apply zebra striping to child table
        apply_zebra_striping(frm);
        
        // Style the Get Class Members button
        style_get_members_button(frm);
        
        // Add custom action buttons
        add_custom_buttons(frm);
    },
    
    // Before save event - Calculate totals
    before_save: function(frm) {
        calculate_totals(frm);
        set_total_fields_readonly(frm);
    },
    
    // Get Class Members button click
    get_class_members: function(frm) {
        get_class_members(frm);
    },
    
    // When class_name changes, update child table
    class_name: function(frm) {
        if (frm.doc.children_attendance && frm.doc.children_attendance.length > 0) {
            update_class_name_in_children(frm);
        }
    }
});


// Child table events - Recalculate on changes
frappe.ui.form.on('Children Attendance', {
    children_attendance_add: function(frm) {
        calculate_totals(frm);
    },
    
    children_attendance_remove: function(frm) {
        calculate_totals(frm);
    },
    
    amount: function(frm, cdt, cdn) {
        calculate_totals(frm);
    },
    
    gender: function(frm, cdt, cdn) {
        calculate_totals(frm);
    }
});


// ============================================================================
// HELPER FUNCTIONS
// ============================================================================

function set_total_fields_readonly(frm) {
    /**
     * Set total fields as read-only to prevent manual editing
     */
    frm.set_df_property('total_female', 'read_only', 1);
    frm.set_df_property('total_male', 'read_only', 1);
    frm.set_df_property('total_count', 'read_only', 1);
    frm.set_df_property('total_offering_amount', 'read_only', 1);
}


function calculate_totals(frm) {
    /**
     * Calculate totals for male, female, count and offering amount
     */
    if (!frm.doc.children_attendance) return;
    
    let total_female = 0;
    let total_male = 0;
    let total_offering = 0;
    
    frm.doc.children_attendance.forEach(row => {
        // Count by gender
        if (row.gender === "Female") {
            total_female += 1;
        } else if (row.gender === "Male") {
            total_male += 1;
        }
        
        // Sum offering amounts
        if (row.amount) {
            total_offering += flt(row.amount);
        }
    });
    
    // Update form values
    frm.set_value('total_female', total_female);
    frm.set_value('total_male', total_male);
    frm.set_value('total_count', total_female + total_male);
    frm.set_value('total_offering_amount', total_offering);
}


function apply_zebra_striping(frm) {
    /**
     * Apply alternating row colors to children attendance table
     */
    setTimeout(() => {
        frm.fields_dict.children_attendance.grid.wrapper.find('.grid-row').each(function(i, row) {
            if (i % 2 === 0) {
                $(row).css('background-color', '#ffffff');
            } else {
                $(row).css('background-color', '#ffffe0');
            }
        });
    }, 300);
}


function style_get_members_button(frm) {
    /**
     * Style the Get Class Members button with orange color
     */
    setTimeout(() => {
        frm.get_field('get_class_members').$input.css({
            'background-color': 'orange',
            'color': 'white',
            'font-weight': 'bold'
        });
    }, 100);
}


function update_class_name_in_children(frm) {
    /**
     * Update class_name field in all child table rows when parent class_name changes
     */
    let class_name = frm.doc.class_name;
    
    frm.doc.children_attendance.forEach(row => {
        frappe.model.set_value(row.doctype, row.name, "class_name", class_name);
    });
}


function get_class_members(frm) {
    /**
     * Fetch and populate class members from Children Class
     */
    if (!frm.doc.class_name) {
        frappe.msgprint({
            title: __('Class Required'),
            indicator: 'red',
            message: __('Please select a Children Class first.')
        });
        return;
    }
    
    frappe.call({
        method: 'frappe.client.get',
        args: {
            doctype: 'Children Class',
            name: frm.doc.class_name
        },
        callback: function(r) {
            if (r.message && r.message.children_class_member && r.message.children_class_member.length > 0) {
                let children_class = r.message;
                
                // Clear existing children attendance table
                frm.clear_table("children_attendance");
                
                // Populate with class members
                children_class.children_class_member.forEach(member => {
                    let row = frm.add_child("children_attendance");
                    row.child_id = member.child_id;
                    row.full_name = member.full_name;
                    row.email = member.email;
                    row.phone_no = member.phone_no;
                    row.teacher_name = member.teacher_name;
                    row.gender = member.gender;
                    row.age = member.age;
                    row.class_name = frm.doc.class_name;
                    row.branch = frm.doc.branch;
                });
                
                // Refresh and recalculate
                frm.refresh_field("children_attendance");
                calculate_totals(frm);
                apply_zebra_striping(frm);
                
                frappe.show_alert({
                    message: __('✅ {0} class members loaded successfully', [children_class.children_class_member.length]),
                    indicator: 'green'
                }, 5);
                
            } else {
                frappe.msgprint({
                    title: __('No Members Found'),
                    indicator: 'orange',
                    message: __('No members found in the selected class.')
                });
            }
        },
        error: function(r) {
            frappe.msgprint({
                title: __('Error'),
                indicator: 'red',
                message: __('Failed to load class members. Please try again.')
            });
        }
    });
}


function add_custom_buttons(frm) {
    /**
     * Add custom action buttons to the form
     */
    
    // Only show buttons if document is saved
    if (frm.doc.__islocal) return;
    
    // Mark SS & CS Attendance Button
    frm.add_custom_button(__('Mark SS & CS Attendance'), function() {
        mark_attendance(frm);
    }).addClass("btn-primary");
    
    // Create Receipt Button
    frm.add_custom_button(__('Create Receipts'), function() {
        create_receipts(frm);
    }).addClass("btn-success");
    
    // Send Email Button
    frm.add_custom_button(__('Send Email Notifications'), function() {
        send_email_notifications(frm);
    }).addClass("btn-info");
}


function mark_attendance(frm) {
    /**
     * Mark Sunday School and Church Service attendance
     */
    
    // Validation
    if (!frm.doc.children_attendance || frm.doc.children_attendance.length === 0) {
        frappe.msgprint({
            title: __('No Attendance Records'),
            indicator: 'red',
            message: __('Please add children attendance records first.')
        });
        return;
    }
    
    if (!frm.doc.mark_ss_attendance && !frm.doc.mark_cs_attendance) {
        frappe.msgprint({
            title: __('Select Attendance Type'),
            indicator: 'orange',
            message: __('Please check "Mark SS Attendance" or "Mark CS Attendance" before processing.')
        });
        return;
    }
    
    // Show loading indicator
    frappe.show_alert({
        message: __('Processing attendance records...'),
        indicator: 'blue'
    }, 3);
    
    // Call backend method
    frappe.call({
        method: 'church.church.doctype.children_class_attendance.children_class_attendance.create_cc_attendance',
        args: {
            ss_attendance: frm.doc.name,
            cs_attendance: frm.doc.name
        },
        freeze: true,
        freeze_message: __('Creating Church Attendance Records...'),
        callback: function(r) {
            if (r.message && r.message.success) {
                // Show beautiful success message
                frappe.msgprint({
                    title: __('Attendance Processing Complete'),
                    indicator: 'green',
                    message: r.message.message
                });
                
                // Reload form
                frm.reload_doc();
            } else if (r.message && !r.message.success) {
                frappe.msgprint({
                    title: __('Attendance Processing Failed'),
                    indicator: 'red',
                    message: r.message.message || __('An error occurred while processing attendance.')
                });
            }
        },
        error: function(r) {
            frappe.msgprint({
                title: __('Error'),
                indicator: 'red',
                message: __('Failed to process attendance. Please check the error log.')
            });
        }
    });
}


function create_receipts(frm) {
    /**
     * Create offering receipts for children
     */
    
    // Validation
    if (!frm.doc.children_attendance || frm.doc.children_attendance.length === 0) {
        frappe.msgprint({
            title: __('No Attendance Records'),
            indicator: 'red',
            message: __('Please add children attendance records first.')
        });
        return;
    }
    
    // Check if create_receipts is checked
    if (!frm.doc.create_receipts) {
        frappe.confirm(
            __('The "Create Receipts" option is not checked. Do you want to enable it and continue?'),
            function() {
                frm.set_value('create_receipts', 1);
                frm.save().then(() => {
                    process_receipts(frm);
                });
            }
        );
        return;
    }
    
    process_receipts(frm);
}


function process_receipts(frm) {
    /**
     * Process receipt creation
     */
    frappe.show_alert({
        message: __('Creating offering receipts...'),
        indicator: 'blue'
    }, 3);
    
    frappe.call({
        method: 'church.church.doctype.children_class_attendance.children_class_attendance.create_receipts',
        args: {
            sso_receipt: frm.doc.name
        },
        freeze: true,
        freeze_message: __('Creating Offering Receipts...'),
        callback: function(r) {
            if (r.message && r.message.success) {
                frappe.msgprint({
                    title: __('Receipts Created'),
                    indicator: 'green',
                    message: r.message.message
                });
                
                frm.reload_doc();
            } else if (r.message && !r.message.success) {
                frappe.msgprint({
                    title: __('Receipt Creation Failed'),
                    indicator: 'red',
                    message: r.message.message || __('An error occurred while creating receipts.')
                });
            }
        },
        error: function(r) {
            frappe.msgprint({
                title: __('Error'),
                indicator: 'red',
                message: __('Failed to create receipts. Please check the error log.')
            });
        }
    });
}


function send_email_notifications(frm) {
    /**
     * Send email notifications to parents
     */
    
    // Validation
    if (!frm.doc.children_attendance || frm.doc.children_attendance.length === 0) {
        frappe.msgprint({
            title: __('No Attendance Records'),
            indicator: 'red',
            message: __('Please add children attendance records first.')
        });
        return;
    }
    
    // Count records with emails
    let email_count = frm.doc.children_attendance.filter(row => row.email).length;
    
    if (email_count === 0) {
        frappe.msgprint({
            title: __('No Email Addresses'),
            indicator: 'orange',
            message: __('None of the children have email addresses. Please add email addresses before sending notifications.')
        });
        return;
    }
    
    // Confirm before sending
    frappe.confirm(
        __('Send email notifications to {0} parent(s)?', [email_count]),
        function() {
            // Show loading
            frappe.show_alert({
                message: __('Sending email notifications...'),
                indicator: 'blue'
            }, 3);
            
            frappe.call({
                method: 'church.church.doctype.children_class_attendance.children_class_attendance.send_mail_from_Children_class',
                args: {
                    syou_receipt: frm.doc.name
                },
                freeze: true,
                freeze_message: __('Sending Email Notifications...'),
                callback: function(r) {
                    if (r.message) {
                        frappe.msgprint({
                            title: __('Email Notifications'),
                            indicator: 'green',
                            message: r.message
                        });
                        
                        frm.reload_doc();
                    }
                },
                error: function(r) {
                    frappe.msgprint({
                        title: __('Error'),
                        indicator: 'red',
                        message: __('Failed to send email notifications. Please check the error log.')
                    });
                }
            });
        }
    );
}


// ============================================================================
// UTILITY FUNCTIONS
// ============================================================================

function flt(value) {
    /**
     * Convert to float, handling null/undefined
     */
    return parseFloat(value) || 0;
}




frappe.ui.form.on("Children Class Attendance", {
    refresh: function(frm) {
        // ... existing code ...
        
        // Add Report Buttons (only for completed docs)
        if (!frm.is_new() && frm.doc.docstatus == 0) {
            
            // HTML Report
            frm.add_custom_button(__('📄 HTML Report'), function() {
                generate_html_report(frm);
            }, __("Reports"));
            
            // Excel Export
            frm.add_custom_button(__('📊 Excel Export'), function() {
                export_to_excel(frm);
            }, __("Reports"));
            
            // Email Report
            frm.add_custom_button(__('📧 Email Report'), function() {
                email_report_dialog(frm);
            }, __("Reports"));
        }
    },
    
    // Auto-link Service Instance on date/branch change
    service_date: function(frm) {
        link_service_instance(frm);
    },
    
    branch: function(frm) {
        link_service_instance(frm);
    }
});

// Auto-link Service Instance
function link_service_instance(frm) {
    if (frm.doc.service_date && frm.doc.branch && !frm.doc.service_instance) {
        frappe.call({
            method: 'frappe.client.get_value',
            args: {
                doctype: 'Service Instance',
                filters: {
                    service_date: frm.doc.service_date,
                    branch: frm.doc.branch,
                    docstatus: ['!=', 2]
                },
                fieldname: 'name'
            },
            callback: function(r) {
                if (r.message && r.message.name) {
                    frm.set_value('service_instance', r.message.name);
                    frappe.show_alert({
                        message: __('✅ Linked to Service Instance: {0}', [r.message.name]),
                        indicator: 'green'
                    }, 3);
                }
            }
        });
    }
}

// Generate HTML Report
function generate_html_report(frm) {
    frappe.show_alert(__('📄 Generating report...'));
    
    frappe.call({
        method: 'church.church.doctype.children_class_attendance.children_class_reports.generate_html_report',
        args: {
            attendance_name: frm.doc.name
        },
        callback: function(r) {
            if (r.message && r.message.success) {
                // Open in new window
                let win = window.open('', '_blank');
                win.document.write(r.message.html);
                win.document.close();
                
                frappe.show_alert({
                    message: __('✅ Report generated'),
                    indicator: 'green'
                });
            }
        }
    });
}

// Export to Excel
function export_to_excel(frm) {
    frappe.show_alert(__('📊 Preparing Excel...'));
    
    frappe.call({
        method: 'church.church.doctype.children_class_attendance.children_class_reports.export_to_excel',
        args: {
            attendance_name: frm.doc.name
        },
        callback: function(r) {
            if (r.message && r.message.success) {
                // Trigger download
                let link = document.createElement('a');
                link.href = 'data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,' + r.message.file_content;
                link.download = r.message.filename;
                link.click();
                
                frappe.show_alert({
                    message: __('✅ Excel downloaded'),
                    indicator: 'green'
                });
            }
        }
    });
}

// Email Report Dialog
function email_report_dialog(frm) {
    let d = new frappe.ui.Dialog({
        title: __('📧 Email Report'),
        fields: [
            {
                fieldname: 'report_type',
                fieldtype: 'Select',
                label: 'Report Type',
                options: 'HTML (Beautiful)\\nPDF (Printable)\\nExcel Spreadsheet',
                default: 'HTML (Beautiful)',
                reqd: 1
            },
            {
                fieldname: 'recipients',
                fieldtype: 'Small Text',
                label: 'Recipients (comma-separated)',
                description: 'Enter email addresses separated by commas'
            }
        ],
        primary_action_label: __('Send'),
        primary_action: function(values) {
            d.hide();
            
            frappe.call({
                method: 'church.church.doctype.children_class_attendance.children_class_reports.email_report',
                args: {
                    attendance_name: frm.doc.name,
                    recipients: values.recipients,
                    report_type: values.report_type
                },
                callback: function(r) {
                    if (r.message && r.message.success) {
                        frappe.msgprint({
                            title: __('✅ Email Sent'),
                            message: r.message.message,
                            indicator: 'green'
                        });
                    }
                }
            });
        }
    });
    
    d.show();
}