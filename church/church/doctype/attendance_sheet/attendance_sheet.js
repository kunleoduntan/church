// Updated Attendance Sheet Client Script
// Optimized for unified Church Attendance system

frappe.ui.form.on('Attendance Sheet', {
    refresh: function(frm) {
        // Add custom buttons
        add_custom_buttons(frm);
        
        // Apply zebra striping to child table
        apply_zebra_striping(frm);
        
        // Set field properties
        set_field_properties(frm);
    },
    
    reporting_date: function(frm) {
        if (frm.doc.reporting_date) {
            // Auto-set month
            const reportingDate = new Date(frm.doc.reporting_date);
            const monthName = reportingDate.toLocaleString('default', { month: 'long' });
            frm.set_value('month', monthName);
            
            // Update child table dates and branches
            update_child_table_defaults(frm);
        }
    },
    
    branch: function(frm) {
        // Update branch in all child rows
        update_child_table_defaults(frm);
    },
    
    before_save: function(frm) {
        // Calculate all totals
        calculate_grand_totals(frm);
        
        // Ensure all child rows have correct date and branch
        update_child_table_defaults(frm);
        
        // Set all total fields as read-only
        set_totals_readonly(frm);
    },
    
    onload: function(frm) {
        // Auto-populate programmes if empty
        if (frm.is_new() && (!frm.doc.church_attendance_analysis || frm.doc.church_attendance_analysis.length === 0)) {
            populate_default_programmes(frm);
        }
    }
});

// Child Table: Church Attendance Analysis
frappe.ui.form.on('Church Attendance Analysis', {
    date: function(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        
        if (row.date) {
            const reportingDate = new Date(row.date);
            const dayName = reportingDate.toLocaleString('default', { weekday: 'short' });
            frappe.model.set_value(cdt, cdn, 'day', dayName);
        }
    },
    
    men: function(frm, cdt, cdn) {
        update_row_totals(frm, cdt, cdn);
    },
    
    women: function(frm, cdt, cdn) {
        update_row_totals(frm, cdt, cdn);
    },
    
    children: function(frm, cdt, cdn) {
        update_row_totals(frm, cdt, cdn);
    },
    
    new_men: function(frm, cdt, cdn) {
        update_row_totals(frm, cdt, cdn);
    },
    
    new_women: function(frm, cdt, cdn) {
        update_row_totals(frm, cdt, cdn);
    },
    
    new_children: function(frm, cdt, cdn) {
        update_row_totals(frm, cdt, cdn);
    }
});

// Helper Functions

function add_custom_buttons(frm) {
    if (!frm.is_new()) {
        // Recalculate attendance from Church Attendance records
        frm.add_custom_button(__('Recalculate from Attendance'), function() {
            frappe.call({
                method: 'church.church.doctype.attendance_sheet.attendance_sheet.recalculate_attendance',
                args: {
                    attendance_sheet: frm.doc.name
                },
                callback: function(r) {
                    if (r.message && r.message.success) {
                        frappe.msgprint(__('Attendance recalculated successfully'));
                        frm.reload_doc();
                    }
                }
            });
        }, __('Actions'));
        
        // View Church Attendance records
        frm.add_custom_button(__('View Attendance Records'), function() {
            frappe.set_route('List', 'Church Attendance', {
                'service_date': frm.doc.reporting_date,
                'branch': frm.doc.branch
            });
        }, __('Actions'));
        
        // Preview Report
        frm.add_custom_button(__('Preview Report'), function() {
            preview_attendance_report(frm);
        }, __('Reports'));
        
        // Email Report
        frm.add_custom_button(__('Email Report'), function() {
            show_email_dialog(frm);
        }, __('Reports'));
        
        // Download PDF (Print)
        frm.add_custom_button(__('Download PDF'), function() {
            download_report_pdf(frm);
        }, __('Reports'));
        
        // Export to Excel
        frm.add_custom_button(__('Export to Excel'), function() {
            export_to_excel(frm);
        }, __('Reports'));
    }
}

function preview_attendance_report(frm) {
    frappe.call({
        method: 'church.church.doctype.attendance_sheet.attendance_report.preview_report',
        args: {
            attendance_sheet_name: frm.doc.name
        },
        callback: function(r) {
            if (r.message) {
                // Open report in new window
                const report_window = window.open('', '_blank');
                report_window.document.write(r.message);
                report_window.document.close();
            }
        }
    });
}

function show_email_dialog(frm) {
    // Get default recipients
    frappe.call({
        method: 'frappe.client.get_list',
        args: {
            doctype: 'Member',
            filters: { 'is_a_pastor': 1 },
            fields: ['email', 'full_name']
        },
        callback: function(r) {
            const default_recipients = r.message || [];
            const email_addresses = default_recipients
                .filter(m => m.email)
                .map(m => m.email)
                .join(', ');
            
            // Create email dialog
            const d = new frappe.ui.Dialog({
                title: __('Email Attendance Report'),
                fields: [
                    {
                        label: __('Recipients'),
                        fieldname: 'recipients',
                        fieldtype: 'Small Text',
                        reqd: 1,
                        default: email_addresses,
                        description: __('Enter email addresses separated by commas')
                    },
                    {
                        fieldtype: 'Section Break'
                    },
                    {
                        fieldtype: 'HTML',
                        fieldname: 'preview',
                        options: `
                            <div style="padding: 15px; background: #f8f9fa; border-radius: 8px; margin-top: 10px;">
                                <h4 style="margin-bottom: 10px; color: #667eea;">📧 Email Preview</h4>
                                <p><strong>Subject:</strong> Attendance Report - ${frm.doc.branch} (${frappe.format(frm.doc.reporting_date, {fieldtype: 'Date'})})</p>
                                <p><strong>Report includes:</strong></p>
                                <ul style="margin-left: 20px;">
                                    <li>Summary statistics with visual cards</li>
                                    <li>Detailed breakdown by programme</li>
                                    <li>Visual analytics with progress bars</li>
                                    <li>Beautiful, professional HTML design</li>
                                </ul>
                            </div>
                        `
                    }
                ],
                primary_action_label: __('Send Email'),
                primary_action(values) {
                    const recipients_list = values.recipients
                        .split(',')
                        .map(email => email.trim())
                        .filter(email => email);
                    
                    if (recipients_list.length === 0) {
                        frappe.msgprint(__('Please enter at least one email address'));
                        return;
                    }
                    
                    d.hide();
                    
                    frappe.call({
                        method: 'church.church.doctype.attendance_sheet.attendance_report.email_report',
                        args: {
                            attendance_sheet_name: frm.doc.name,
                            recipients: recipients_list
                        },
                        freeze: true,
                        freeze_message: __('Sending email...'),
                        callback: function(r) {
                            if (r.message && r.message.success) {
                                frappe.show_alert({
                                    message: r.message.message,
                                    indicator: 'green'
                                }, 5);
                            }
                        }
                    });
                }
            });
            
            d.show();
        }
    });
}

function download_report_pdf(frm) {
    frappe.call({
        method: 'church.church.doctype.attendance_sheet.attendance_report.preview_report',
        args: {
            attendance_sheet_name: frm.doc.name
        },
        callback: function(r) {
            if (r.message) {
                // Open in new window and trigger print
                const report_window = window.open('', '_blank');
                report_window.document.write(r.message);
                report_window.document.close();
                
                // Wait for content to load then print
                setTimeout(function() {
                    report_window.print();
                }, 500);
            }
        }
    });
}

function export_to_excel(frm) {
    frappe.show_alert({
        message: __('Generating Excel file...'),
        indicator: 'blue'
    });
    
    frappe.call({
        method: 'church.church.doctype.attendance_sheet.attendance_excel_export.export_attendance_to_excel',
        args: {
            attendance_sheet_name: frm.doc.name
        },
        callback: function(r) {
            if (r.message && r.message.success) {
                // Create download link
                const link = document.createElement('a');
                link.href = 'data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,' + r.message.file_content;
                link.download = r.message.filename;
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);
                
                frappe.show_alert({
                    message: __('Excel file downloaded successfully'),
                    indicator: 'green'
                }, 5);
            } else {
                frappe.msgprint({
                    title: __('Export Failed'),
                    message: r.message.error || __('Failed to generate Excel file'),
                    indicator: 'red'
                });
            }
        }
    });
}

function apply_zebra_striping(frm) {
    setTimeout(function() {
        frm.fields_dict.church_attendance_analysis.grid.wrapper.find('.grid-row').each(function(i, row) {
            if (i % 2 === 0) {
                $(row).css('background-color', '#ffffff');
            } else {
                $(row).css('background-color', '#e9ffdb');
            }
        });
    }, 300);
}

function set_field_properties(frm) {
    // Set total fields as read-only
    const total_fields = [
        'total_men', 'total_women', 'total_children',
        'total_new_men', 'total_new_women', 'total_new_children',
        'total_first', 'total_second', 'total_third',
        'total_existing_men', 'total_existing_women', 'total_existing_children'
    ];
    
    total_fields.forEach(function(field) {
        frm.set_df_property(field, 'read_only', 1);
    });
    
    // Hide title field (auto-generated)
    frm.set_df_property('title', 'hidden', 1);
}

function update_child_table_defaults(frm) {
    if (!frm.doc.church_attendance_analysis) {
        return;
    }
    
    $.each(frm.doc.church_attendance_analysis || [], function(index, row) {
        // Set branch
        if (frm.doc.branch && !row.branch) {
            frappe.model.set_value(row.doctype, row.name, 'branch', frm.doc.branch);
        }
        
        // Set date
        if (frm.doc.reporting_date && !row.date) {
            frappe.model.set_value(row.doctype, row.name, 'date', frm.doc.reporting_date);
        }
    });
}

function update_row_totals(frm, cdt, cdn) {
    const row = locals[cdt][cdn];
    
    // Calculate totals
    const total = (row.men || 0) + (row.women || 0) + (row.children || 0);
    const totalNew = (row.new_men || 0) + (row.new_women || 0) + (row.new_children || 0);
    const existingMen = (row.men || 0) - (row.new_men || 0);
    const existingWomen = (row.women || 0) - (row.new_women || 0);
    const existingChildren = (row.children || 0) - (row.new_children || 0);
    const totalExisting = existingMen + existingWomen + existingChildren;
    
    // Set values
    frappe.model.set_value(cdt, cdn, 'total', total);
    frappe.model.set_value(cdt, cdn, 'new_total', totalNew);
    frappe.model.set_value(cdt, cdn, 'existing_men', existingMen);
    frappe.model.set_value(cdt, cdn, 'existing_women', existingWomen);
    frappe.model.set_value(cdt, cdn, 'existing_children', existingChildren);
    frappe.model.set_value(cdt, cdn, 'existing_total', totalExisting);
    
    // Recalculate grand totals
    calculate_grand_totals(frm);
}

function calculate_grand_totals(frm) {
    let total_men = 0;
    let total_women = 0;
    let total_children = 0;
    let total_new_men = 0;
    let total_new_women = 0;
    let total_new_children = 0;
    
    $.each(frm.doc.church_attendance_analysis || [], function(index, row) {
        total_men += row.men || 0;
        total_women += row.women || 0;
        total_children += row.children || 0;
        total_new_men += row.new_men || 0;
        total_new_women += row.new_women || 0;
        total_new_children += row.new_children || 0;
    });
    
    // Set totals
    frm.set_value('total_men', total_men);
    frm.set_value('total_women', total_women);
    frm.set_value('total_children', total_children);
    frm.set_value('total_new_men', total_new_men);
    frm.set_value('total_new_women', total_new_women);
    frm.set_value('total_new_children', total_new_children);
    
    // Calculate combined totals
    frm.set_value('total_first', total_men + total_women + total_children);
    frm.set_value('total_second', total_new_men + total_new_women + total_new_children);
    frm.set_value('total_existing_men', total_men - total_new_men);
    frm.set_value('total_existing_women', total_women - total_new_women);
    frm.set_value('total_existing_children', total_children - total_new_children);
    frm.set_value('total_third', 
        (total_men - total_new_men) + 
        (total_women - total_new_women) + 
        (total_children - total_new_children)
    );
    
    // Refresh total fields
    frm.refresh_field('total_men');
    frm.refresh_field('total_women');
    frm.refresh_field('total_children');
    frm.refresh_field('total_new_men');
    frm.refresh_field('total_new_women');
    frm.refresh_field('total_new_children');
    frm.refresh_field('total_first');
    frm.refresh_field('total_second');
    frm.refresh_field('total_third');
}

function set_totals_readonly(frm) {
    const total_fields = [
        'total_men', 'total_women', 'total_children',
        'total_new_men', 'total_new_women', 'total_new_children',
        'total_first', 'total_second', 'total_third',
        'total_existing_men', 'total_existing_women', 'total_existing_children'
    ];
    
    total_fields.forEach(function(field) {
        frm.set_df_property(field, 'read_only', 1);
    });
}

function populate_default_programmes(frm) {
    if (!frm.doc.reporting_date) {
        frappe.msgprint(__('Please select a reporting date first'));
        return;
    }
    
    frappe.call({
        method: 'frappe.client.get_list',
        args: {
            doctype: 'Programme',
            filters: { 'disabled': 0 },
            fields: ['name', 'programme_name'],
            limit_page_length: 0
        },
        callback: function(r) {
            if (r.message) {
                const reportingDate = new Date(frm.doc.reporting_date);
                const dayOfWeek = reportingDate.getDay();
                
                r.message.forEach(function(prog) {
                    let shouldAdd = false;
                    
                    // Sunday programmes
                    if (dayOfWeek === 0 && (prog.programme_name.includes('Sunday'))) {
                        shouldAdd = true;
                    }
                    // Midweek programmes
                    else if ([2, 3].includes(dayOfWeek) && 
                             (prog.programme_name.includes('Midweek') || 
                              prog.programme_name.includes('Bible Study'))) {
                        shouldAdd = true;
                    }
                    
                    if (shouldAdd) {
                        const row = frm.add_child('church_attendance_analysis');
                        row.date = frm.doc.reporting_date;
                        row.programme = prog.name;
                        row.branch = frm.doc.branch;
                        row.men = 0;
                        row.women = 0;
                        row.children = 0;
                        row.new_men = 0;
                        row.new_women = 0;
                        row.new_children = 0;
                    }
                });
                
                frm.refresh_field('church_attendance_analysis');
            }
        }
    });
}

// Validation
frappe.ui.form.on('Anonymous Tithes Batch Update', {
    before_save: function(frm) {
        if (frm.doc.reporting_date < frm.doc.from_date || frm.doc.reporting_date < frm.doc.to_date) {
            frappe.msgprint(__('The reporting date cannot be earlier than the start date or end date.'));
            frappe.validated = false;
        }
    }
});