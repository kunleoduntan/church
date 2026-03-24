// AI-Powered Service Instance - World's Best Attendance System
frappe.ui.form.on("Service Instance", {
    onload: function(frm) {
        // Set query filters
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
        // AI-Powered Attendance Buttons
        if (!frm.is_new()) {
            // Auto-update attendance button
            frm.add_custom_button(__('🤖 AI Update Attendance'), function() {
                update_attendance_from_ai(frm);
            }, __("Attendance"));
            
            // Generate analytics report button
            frm.add_custom_button(__('📊 Analytics Report'), function() {
                generate_smart_analytics(frm);
            }, __("Attendance"));
            
            // Quick attendance entry
            if (frm.doc.status === 'Ongoing' || frm.doc.status === 'Scheduled') {
                frm.add_custom_button(__('✏️ Quick Attendance Entry'), function() {
                    quick_attendance_entry(frm);
                }, __("Attendance"));
            }
        }
        
        // Ministry team communications
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
        
        // Coordinator assignments
        if (!frm.is_new() && frm.doc.service_visitors && frm.doc.service_visitors.length > 0) {
            frm.add_custom_button(__('Send Coordinator Assignments'), function() {
                send_coordinator_assignments(frm);
            }, __("Communications"));
        }
        
        // Tools
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
        
        // Actions
        if (frm.doc.status === 'Ongoing' || frm.doc.status === 'Scheduled') {
            frm.add_custom_button(__('Mark as Completed'), function() {
                mark_service_completed(frm);
            }, __("Actions"));
        }
        
        // Reports
        if (frm.doc.status === 'Completed') {
            frm.add_custom_button(__('Generate Service Report'), function() {
                generate_service_report(frm);
            }, __("Reports"));
        }
        
        if (frm.doc.service_visitors && frm.doc.service_visitors.length > 0) {
            frm.add_custom_button(__('Visitor Follow-up Dashboard'), function() {
                show_visitor_followup_dashboard(frm);
            }, __("Reports"));
        }
        
        // Apply styling
        apply_table_styling(frm);
        
        // Show attendance indicator
        show_attendance_indicator(frm);
    },
    
    before_save: function(frm) {
        // Calculate total attendance
        calculate_total_attendance(frm);
        
        // Set actual times
        if (!frm.doc.actual_start_time && frm.doc.service_time) {
            frm.set_value('actual_start_time', frm.doc.service_time);
        }
    },
    
    men_count: function(frm) { calculate_total_attendance(frm); },
    women_count: function(frm) { calculate_total_attendance(frm); },
    children_count: function(frm) { calculate_total_attendance(frm); }
});

// AI-Powered Attendance Update
function update_attendance_from_ai(frm) {
    frappe.confirm(
        `<div style="font-family: Arial; padding: 10px;">
            <h4 style="color: #2c3e50; margin-bottom: 10px;">🤖 AI-Powered Attendance Update</h4>
            <p style="margin-bottom: 10px;">The AI system will:</p>
            <ul style="margin-left: 20px; color: #34495e;">
                <li>Analyze visitor records</li>
                <li>Count members & guests intelligently</li>
                <li>Prevent duplicate counting</li>
                <li>Calculate demographics (men/women/children)</li>
                <li>Track first-timers & converts</li>
            </ul>
            <p style="margin-top: 15px; color: #7f8c8d; font-size: 13px;">
                <strong>Note:</strong> This will overwrite current attendance numbers
            </p>
        </div>`,
        function() {
            frappe.show_alert({
                message: __('🤖 AI is analyzing attendance data...'),
                indicator: 'blue'
            });
            
            frappe.call({
                method: 'church.church.doctype.service_instance.service_instance_ai_attendance.auto_update_attendance_from_visitors',
                args: {
                    service_instance: frm.doc.name
                },
                callback: function(r) {
                    if (r.message && r.message.success.length > 0) {
                        let result = r.message.success[0];
                        
                        frappe.msgprint({
                            title: __('✅ Attendance Updated Successfully'),
                            message: `
                                <div style="font-family: Arial; padding: 10px;">
                                    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 8px; margin-bottom: 15px; text-align: center;">
                                        <div style="font-size: 48px; font-weight: bold;">${result.attendance}</div>
                                        <div style="font-size: 16px; opacity: 0.9;">Total Attendance</div>
                                    </div>
                                    <p style="color: #27ae60; font-size: 14px;">
                                        ✓ AI successfully analyzed and updated attendance numbers
                                    </p>
                                    <p style="color: #7f8c8d; font-size: 13px; margin-top: 10px;">
                                        The system used intelligent deduplication and demographic analysis
                                    </p>
                                </div>
                            `,
                            indicator: 'green',
                            wide: true
                        });
                        
                        frm.reload_doc();
                    } else {
                        frappe.msgprint({
                            title: __('Error'),
                            message: __('Failed to update attendance. Please try again.'),
                            indicator: 'red'
                        });
                    }
                }
            });
        }
    );
}

// Generate Smart Analytics Report
function generate_smart_analytics(frm) {
    frappe.show_alert(__('📊 Generating AI-powered analytics...'));
    
    frappe.call({
        method: 'church.church.doctype.service_instance.service_instance_ai_attendance.generate_attendance_analytics_report',
        args: {
            service_instance: frm.doc.name
        },
        callback: function(r) {
            if (r.message && r.message.success) {
                let d = new frappe.ui.Dialog({
                    title: __('📊 AI-Powered Attendance Analytics'),
                    fields: [
                        {
                            fieldtype: 'HTML',
                            options: r.message.report_html
                        }
                    ],
                    size: 'extra-large',
                    primary_action_label: __('Download Report'),
                    primary_action: function() {
                        // Download as PDF or print
                        let printWindow = window.open('', '_blank');
                        printWindow.document.write(r.message.report_html);
                        printWindow.document.close();
                        printWindow.print();
                    },
                    secondary_action_label: __('Email Report'),
                    secondary_action: function() {
                        email_analytics_report(frm, r.message.report_html);
                    }
                });
                
                d.show();
            }
        }
    });
}

// Quick Attendance Entry Dialog
function quick_attendance_entry(frm) {
    let d = new frappe.ui.Dialog({
        title: __('✏️ Quick Attendance Entry'),
        fields: [
            {
                fieldname: 'attendance_section',
                fieldtype: 'Section Break',
                label: '👥 Enter Attendance Numbers'
            },
            {
                fieldname: 'men_count',
                fieldtype: 'Int',
                label: '🧔 Men',
                default: frm.doc.men_count || 0
            },
            {
                fieldname: 'women_count',
                fieldtype: 'Int',
                label: '👩 Women',
                default: frm.doc.women_count || 0
            },
            {
                fieldname: 'children_count',
                fieldtype: 'Int',
                label: '👶 Children',
                default: frm.doc.children_count || 0
            },
            {
                fieldname: 'column_break',
                fieldtype: 'Column Break'
            },
            {
                fieldname: 'first_timers',
                fieldtype: 'Int',
                label: '⭐ First-Timers',
                default: frm.doc.first_timers || 0
            },
            {
                fieldname: 'new_converts',
                fieldtype: 'Int',
                label: '🙏 New Converts',
                default: frm.doc.new_converts || 0
            },
            {
                fieldname: 'total_display',
                fieldtype: 'HTML',
                options: '<div id="total_attendance_display" style="margin-top: 20px;"></div>'
            }
        ],
        primary_action_label: __('Save Attendance'),
        primary_action: function(values) {
            frm.set_value('men_count', values.men_count);
            frm.set_value('women_count', values.women_count);
            frm.set_value('children_count', values.children_count);
            frm.set_value('first_timers', values.first_timers);
            frm.set_value('new_converts', values.new_converts);
            
            frm.save();
            d.hide();
            
            frappe.show_alert({
                message: __('✅ Attendance saved successfully'),
                indicator: 'green'
            });
        }
    });
    
    // Update total display on field changes
    d.fields_dict.men_count.$input.on('input', function() {
        update_total_display(d);
    });
    d.fields_dict.women_count.$input.on('input', function() {
        update_total_display(d);
    });
    d.fields_dict.children_count.$input.on('input', function() {
        update_total_display(d);
    });
    
    d.show();
    update_total_display(d);
}

function update_total_display(dialog) {
    let men = parseInt(dialog.get_value('men_count')) || 0;
    let women = parseInt(dialog.get_value('women_count')) || 0;
    let children = parseInt(dialog.get_value('children_count')) || 0;
    let total = men + women + children;
    
    $('#total_attendance_display').html(`
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 8px; text-align: center;">
            <div style="font-size: 48px; font-weight: bold;">${total}</div>
            <div style="font-size: 16px; opacity: 0.9;">Total Attendance</div>
        </div>
    `);
}

// Email Analytics Report
function email_analytics_report(frm, report_html) {
    frappe.prompt([
        {
            fieldname: 'recipients',
            fieldtype: 'MultiSelect',
            label: 'Send To',
            options: 'Leadership Team\nMinistry Team\nCustom',
            reqd: 1
        },
        {
            fieldname: 'custom_email',
            fieldtype: 'Data',
            label: 'Custom Email',
            depends_on: 'eval:doc.recipients.includes("Custom")'
        }
    ],
    function(values) {
        frappe.call({
            method: 'frappe.sendmail',
            args: {
                recipients: values.custom_email || 'admin@church.com',
                subject: `Attendance Analytics - ${frm.doc.service_name} (${frm.doc.service_date})`,
                message: report_html
            },
            callback: function(r) {
                frappe.show_alert({
                    message: __('📧 Report emailed successfully'),
                    indicator: 'green'
                });
            }
        });
    },
    __('Email Report'),
    __('Send')
    );
}

// Calculate Total Attendance
function calculate_total_attendance(frm) {
    let total = (frm.doc.men_count || 0) + (frm.doc.women_count || 0) + (frm.doc.children_count || 0);
    frm.set_value('total_attendance', total);
}

// Show Attendance Indicator
function show_attendance_indicator(frm) {
    if (frm.doc.total_attendance) {
        setTimeout(() => {
            let indicator_html = `
                <div style="position: fixed; bottom: 20px; right: 20px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 15px 25px; border-radius: 50px; box-shadow: 0 4px 15px rgba(0,0,0,0.2); z-index: 1000; font-family: Arial;">
                    <div style="font-size: 12px; opacity: 0.9;">Total Attendance</div>
                    <div style="font-size: 28px; font-weight: bold; text-align: center;">${frm.doc.total_attendance}</div>
                </div>
            `;
            
            if ($('#attendance-indicator').length === 0) {
                $('body').append(`<div id="attendance-indicator">${indicator_html}</div>`);
            } else {
                $('#attendance-indicator').html(indicator_html);
            }
        }, 500);
    }
}

// [Include all other functions from previous service_instance.js here]
// send_coordinator_assignments, show_notification_dialog, etc.

// Apply table styling
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

// Mark service as completed
function mark_service_completed(frm) {
    frappe.confirm(
        __('Mark this service as completed?'),
        function() {
            frm.set_value('status', 'Completed');
            if (!frm.doc.actual_end_time) {
                frm.set_value('actual_end_time', frappe.datetime.now_time());
            }
            frm.save();
        }
    );
}

// [Include remaining functions: send_coordinator_assignments, copy_ministry_team_from_service, etc.]