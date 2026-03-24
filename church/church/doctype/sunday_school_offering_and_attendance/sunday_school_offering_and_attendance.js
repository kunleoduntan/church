// Copyright (c) 2025, kunle and contributors
// For license information, please see license.txt



frappe.ui.form.on("Sunday School Offering and Attendance", {
    // ========================================================================
    // FORM REFRESH - Setup UI and buttons
    // ========================================================================
    refresh: function(frm) {
        // Set read-only for calculated fields
        set_calculated_fields_readonly(frm);
        
        // Apply zebra striping
        apply_zebra_striping(frm);
        
        // Style the Get Class Members button
        style_get_members_button(frm);
        
        // Add custom action buttons
        add_custom_buttons(frm);
        
        // Auto-link Service Instance
        if (frm.doc.service_date && frm.doc.branch && !frm.doc.service_instance) {
            link_service_instance(frm);
        }
    },
    
    // ========================================================================
    // BEFORE SAVE - Calculate totals
    // ========================================================================
    before_save: function(frm) {
        calculate_totals(frm);
        set_calculated_fields_readonly(frm);
    },
    
    // ========================================================================
    // SERVICE DATE/BRANCH CHANGE - Auto-link Service Instance
    // ========================================================================
    service_date: function(frm) {
        if (frm.doc.service_date && frm.doc.branch) {
            link_service_instance(frm);
        }
    },
    
    branch: function(frm) {
        if (frm.doc.service_date && frm.doc.branch) {
            link_service_instance(frm);
        }
    },
    
    // ========================================================================
    // GET CLASS MEMBERS BUTTON
    // ========================================================================
    get_class_members: function(frm) {
        get_class_members(frm);
    },
    
    // ========================================================================
    // CLASS NAME CHANGE - Update all rows
    // ========================================================================
    class_name: function(frm) {
        if (frm.doc.sunday_school_attendance && frm.doc.sunday_school_attendance.length > 0) {
            update_class_name_in_rows(frm);
        }
    }
});


// ============================================================================
// CHILD TABLE EVENTS - Recalculate on changes
// ============================================================================

frappe.ui.form.on('Sunday School Attendance', {
    sunday_school_attendance_add: function(frm) {
        calculate_totals(frm);
    },
    
    sunday_school_attendance_remove: function(frm) {
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

function set_calculated_fields_readonly(frm) {
    /**
     * Set calculated fields as read-only
     * BEST PRACTICE: Prevent manual editing of calculated values
     */
    frm.set_df_property('total_female', 'read_only', 1);
    frm.set_df_property('total_male', 'read_only', 1);
    frm.set_df_property('total_count', 'read_only', 1);
    frm.set_df_property('total_offering_amount', 'read_only', 1);
}


function calculate_totals(frm) {
    /**
     * Calculate totals for gender and offering
     * OPTIMIZED: Single loop for all calculations
     */
    if (!frm.doc.sunday_school_attendance) return;
    
    let total_female = 0;
    let total_male = 0;
    let total_offering = 0;
    
    frm.doc.sunday_school_attendance.forEach(row => {
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
     * Apply alternating row colors to attendance table
     * BEST PRACTICE: Visual clarity
     */
    setTimeout(() => {
        frm.fields_dict.sunday_school_attendance.grid.wrapper.find('.grid-row').each(function(i, row) {
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
     * Style the Get Class Members button
     */
    setTimeout(() => {
        frm.get_field('get_class_members').$input.css({
            'background-color': 'orange',
            'color': 'white',
            'font-weight': 'bold'
        });
    }, 100);
}


function update_class_name_in_rows(frm) {
    /**
     * Update class_name in all child table rows
     */
    let class_name = frm.doc.class_name;
    
    frm.doc.sunday_school_attendance.forEach(row => {
        frappe.model.set_value(row.doctype, row.name, "class_name", class_name);
    });
}


function link_service_instance(frm) {
    /**
     * Auto-link to Service Instance based on date and branch
     * BEST PRACTICE: Automatic data linking
     */
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


function get_class_members(frm) {
    /**
     * Fetch and populate class members from Sunday School Class
     * OPTIMIZED: Single API call, batch updates
     */
    if (!frm.doc.class_name) {
        frappe.msgprint({
            title: __('Class Required'),
            indicator: 'red',
            message: __('Please select a Sunday School Class first.')
        });
        return;
    }
    
    frappe.call({
        method: 'frappe.client.get',
        args: {
            doctype: 'Sunday School Class',
            name: frm.doc.class_name
        },
        callback: function(r) {
            if (r.message && r.message.sunday_school_group_member && r.message.sunday_school_group_member.length > 0) {
                let sunday_school_class = r.message;
                
                // Clear existing table
                frm.clear_table("sunday_school_attendance");
                
                // Populate with class members
                sunday_school_class.sunday_school_group_member.forEach(member => {
                    let row = frm.add_child("sunday_school_attendance");
                    row.member_id = member.member_id;
                    row.full_name = member.full_name;
                    row.email = member.email;
                    row.phone_no = member.phone_no;
                    row.teacher_name = member.teacher_name;
                    row.gender = member.gender;
                    row.age = member.age;
                    row.class_name = frm.doc.class_name;
                    row.branch = frm.doc.branch;
                    row.sunday_school_class_category = frm.doc.sunday_school_class_category;
                    row.demographic_group = member.demographic_group;
                });
                
                // Refresh and recalculate
                frm.refresh_field("sunday_school_attendance");
                calculate_totals(frm);
                apply_zebra_striping(frm);
                
                frappe.show_alert({
                    message: __('✅ {0} class members loaded successfully', [sunday_school_class.sunday_school_group_member.length]),
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
     * Add custom action buttons
     * BEST PRACTICE: Clear, organized button placement
     */
    
    // Only show buttons if document is saved
    if (frm.doc.__islocal) return;
    
    // Mark SS & CS Attendance Button
    frm.add_custom_button(__('Mark SS & CS Attendance'), function() {
        mark_attendance(frm);
    }).addClass("btn-primary");
    
    // Create Receipts Button
    frm.add_custom_button(__('Create Receipts'), function() {
        create_receipts(frm);
    }).addClass("btn-success");
    
    // Send Email Button
    frm.add_custom_button(__('Send Email Notifications'), function() {
        send_email_notifications(frm);
    }).addClass("btn-info");
    
    // Generate Reports (if submitted)
    if (frm.doc.docstatus == 1) {
        frm.add_custom_button(__('📊 Generate Reports'), function() {
            show_reports_menu(frm);
        }, __("Reports"));
    }
}


function mark_attendance(frm) {
    /**
     * Mark Sunday School and Church Service attendance
     * OPTIMIZED: Clear validation, beautiful feedback
     */
    
    // Validation
    if (!frm.doc.sunday_school_attendance || frm.doc.sunday_school_attendance.length === 0) {
        frappe.msgprint({
            title: __('No Attendance Records'),
            indicator: 'red',
            message: __('Please add attendance records first.')
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
    
    // Show loading
    frappe.show_alert({
        message: __('Processing attendance records...'),
        indicator: 'blue'
    }, 3);
    
    // Call backend method
    frappe.call({
        method: 'church.church.doctype.sunday_school_offering_and_attendance.sunday_school_offering_and_attendance.create_ss_cs_attendance',
        args: {
            ss_attendance: frm.doc.name,
            cs_attendance: frm.doc.name
        },
        freeze: true,
        freeze_message: __('Creating Attendance Records...'),
        callback: function(r) {
            if (r.message && r.message.success) {
                frappe.msgprint({
                    title: __('Attendance Processing Complete'),
                    indicator: 'green',
                    message: r.message.message
                });
                frm.reload_doc();
            } else if (r.message && !r.message.success) {
                frappe.msgprint({
                    title: __('Attendance Processing Failed'),
                    indicator: 'red',
                    message: r.message.message || __('An error occurred.')
                });
            }
        },
        error: function(r) {
            frappe.msgprint({
                title: __('Error'),
                indicator: 'red',
                message: __('Failed to process attendance. Check error log.')
            });
        }
    });
}


function create_receipts(frm) {
    /**
     * Create offering receipts
     * OPTIMIZED: Validates before processing, clear feedback
     */
    
    // Validation
    if (!frm.doc.sunday_school_attendance || frm.doc.sunday_school_attendance.length === 0) {
        frappe.msgprint({
            title: __('No Attendance Records'),
            indicator: 'red',
            message: __('Please add attendance records first.')
        });
        return;
    }
    
    // Check if offering amount or individual amounts exist
    let has_offering = frm.doc.offering_amount && frm.doc.offering_amount > 0;
    let has_individual = frm.doc.sunday_school_attendance.some(row => row.amount && row.amount > 0);
    
    if (!has_offering && !has_individual) {
        frappe.msgprint({
            title: __('No Offering Amount'),
            indicator: 'orange',
            message: __('Please enter either Class Offering Amount or individual amounts.')
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
        method: 'church.church.doctype.sunday_school_offering_and_attendance.sunday_school_offering_and_attendance.create_ss_offering_receipt',
        args: {
            create_receipt: frm.doc.name
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
                    title: __('Receipt Creation Info'),
                    indicator: 'orange',
                    message: r.message.message
                });
            }
        },
        error: function(r) {
            frappe.msgprint({
                title: __('Error'),
                indicator: 'red',
                message: __('Failed to create receipts. Check error log.')
            });
        }
    });
}


function send_email_notifications(frm) {
    /**
     * Send email notifications to parents
     */
    
    // Validation
    if (!frm.doc.sunday_school_attendance || frm.doc.sunday_school_attendance.length === 0) {
        frappe.msgprint({
            title: __('No Attendance Records'),
            indicator: 'red',
            message: __('Please add attendance records first.')
        });
        return;
    }
    
    // Count records with emails
    let email_count = frm.doc.sunday_school_attendance.filter(row => row.email).length;
    
    if (email_count === 0) {
        frappe.msgprint({
            title: __('No Email Addresses'),
            indicator: 'orange',
            message: __('None of the records have email addresses.')
        });
        return;
    }
    
    // Confirm before sending
    frappe.confirm(
        __('Send exotic email notifications to {0} recipient(s)?', [email_count]),
        function() {
            frappe.show_alert({
                message: __('Sending email notifications...'),
                indicator: 'blue'
            }, 3);
            
            frappe.call({
                method: 'church.church.doctype.sunday_school_offering_and_attendance.sunday_school_offering_and_attendance.send_exotic_email',
                args: {
                    syou_receipt: frm.doc.name
                },
                freeze: true,
                freeze_message: __('Sending Exotic Email Notifications...'),
                callback: function(r) {
                    if (r.message && r.message.success) {
                        frappe.msgprint({
                            title: __('Emails Sent'),
                            indicator: 'green',
                            message: `✅ ${r.message.sent} sent, ⊘ ${r.message.no_email} without email${r.message.failed > 0 ? `, ✗ ${r.message.failed} failed` : ''}`
                        });
                        frm.reload_doc();
                    }
                },
                error: function(r) {
                    frappe.msgprint({
                        title: __('Error'),
                        indicator: 'red',
                        message: __('Failed to send emails. Check error log.')
                    });
                }
            });
        }
    );
}


function show_reports_menu(frm) {
    /**
     * Show reports menu
     * FUTURE: Will generate HTML and Excel reports
     */
    frappe.msgprint({
        title: __('Reports Coming Soon'),
        indicator: 'blue',
        message: __('Beautiful HTML and Excel reports with demographic breakdown will be available soon!')
    });
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