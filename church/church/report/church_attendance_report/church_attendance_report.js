// Copyright (c) 2026, kunle and contributors
// For license information, please see license.txt
/* eslint-disable */


// Attendance Analysis Report - Client Script
// Adds custom buttons for HTML preview, Excel export, PDF, and email
// Supports single sheet and date range analysis

frappe.query_reports["Church Attendance Report"] = {
    "filters": [
        {
            "fieldname": "mode",
            "label": __("Report Mode"),
            "fieldtype": "Select",
            "options": ["Single Sheet", "Date Range", "Branch Analysis"],
            "default": "Single Sheet",
            "reqd": 1,
            "on_change": function() {
                // Refresh to show/hide filters based on mode
                frappe.query_report.refresh();
            }
        },
        {
            "fieldname": "attendance_sheet",
            "label": __("Attendance Sheet"),
            "fieldtype": "Link",
            "options": "Attendance Sheet",
            "depends_on": "eval:doc.mode=='Single Sheet'",
            "mandatory_depends_on": "eval:doc.mode=='Single Sheet'",
            "get_query": function() {
                return {
                    "filters": {
                        "docstatus": ["in", [0, 1]]
                    }
                };
            }
        },
        {
            "fieldname": "from_date",
            "label": __("From Date"),
            "fieldtype": "Date",
            "depends_on": "eval:doc.mode=='Date Range'",
            "mandatory_depends_on": "eval:doc.mode=='Date Range'",
            "default": frappe.datetime.month_start()
        },
        {
            "fieldname": "to_date",
            "label": __("To Date"),
            "fieldtype": "Date",
            "depends_on": "eval:doc.mode=='Date Range'",
            "mandatory_depends_on": "eval:doc.mode=='Date Range'",
            "default": frappe.datetime.month_end()
        },
        {
            "fieldname": "branch",
            "label": __("Branch"),
            "fieldtype": "Link",
            "options": "Branch",
            "depends_on": "eval:doc.mode=='Date Range' || doc.mode=='Branch Analysis'",
            "mandatory_depends_on": "eval:doc.mode=='Branch Analysis'"
        },
        {
            "fieldname": "limit",
            "label": __("Limit"),
            "fieldtype": "Int",
            "default": 20,
            "depends_on": "eval:doc.mode=='Branch Analysis'",
            "description": __("Number of recent sheets to analyze")
        }
    ],
    
    "onload": function(report) {
        // Add custom buttons
        add_custom_report_buttons(report);
    },
    
    "formatter": function(value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);
        
        // Highlight visitor percentage
        if (column.fieldname == "visitor_percent" && data && data.visitor_percent > 30) {
            value = `<span style="color: red; font-weight: bold;">${value}</span>`;
        }
        
        // Highlight total column
        if (column.fieldname == "total" && data && data.total > 0) {
            value = `<span style="color: #667eea; font-weight: bold;">${value}</span>`;
        }
        
        // Make sheet clickable
        if (column.fieldname == "attendance_sheet" && data && data.attendance_sheet) {
            value = `<a href="/app/attendance-sheet/${data.attendance_sheet}" target="_blank">${value}</a>`;
        }
        
        return value;
    }
};

function add_custom_report_buttons(report) {
    // Export Period to Excel Button
    report.page.add_inner_button(__('Export Period to Excel'), function() {
        const filters = report.get_values();
        export_period_to_excel(filters);
    }, __('Actions'));
    
    // For Single Sheet Mode - Add all buttons
    report.page.add_inner_button(__('Preview HTML Report'), function() {
        const filters = report.get_values();
        
        if (filters.mode === 'Single Sheet' && filters.attendance_sheet) {
            preview_html_report(filters.attendance_sheet);
        } else {
            frappe.msgprint(__('HTML preview only available in Single Sheet mode'));
        }
    }, __('Actions'));
    
    report.page.add_inner_button(__('Export to Beautiful Excel'), function() {
        const filters = report.get_values();
        
        if (filters.mode === 'Single Sheet' && filters.attendance_sheet) {
            export_to_excel(filters.attendance_sheet);
        } else {
            frappe.msgprint(__('Beautiful Excel only available in Single Sheet mode. Use "Export Period to Excel" for date ranges.'));
        }
    }, __('Actions'));
    
    report.page.add_inner_button(__('Download PDF'), function() {
        const filters = report.get_values();
        
        if (filters.mode === 'Single Sheet' && filters.attendance_sheet) {
            download_pdf_report(filters.attendance_sheet);
        } else {
            frappe.msgprint(__('PDF download only available in Single Sheet mode'));
        }
    }, __('Actions'));
    
    report.page.add_inner_button(__('Email Report'), function() {
        const filters = report.get_values();
        
        if (filters.mode === 'Single Sheet' && filters.attendance_sheet) {
            show_email_dialog(filters.attendance_sheet);
        } else {
            frappe.msgprint(__('Email feature only available in Single Sheet mode'));
        }
    }, __('Actions'));
    
    // View Attendance Sheet Button
    report.page.add_inner_button(__('View Attendance Sheet'), function() {
        const filters = report.get_values();
        
        if (filters.mode === 'Single Sheet' && filters.attendance_sheet) {
            frappe.set_route('Form', 'Attendance Sheet', filters.attendance_sheet);
        } else {
            frappe.msgprint(__('Select a single Attendance Sheet to view'));
        }
    }, __('Navigate'));
}

function export_period_to_excel(filters) {
    frappe.show_alert({
        message: __('Generating Excel file for selected period...'),
        indicator: 'blue'
    });
    
    frappe.call({
        method: 'church.church.report.attendance_analysis.attendance_analysis.export_period_to_excel',
        args: {
            filters: filters
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
                    message: r.message ? r.message.error : __('Failed to generate Excel file'),
                    indicator: 'red'
                });
            }
        }
    });
}

function preview_html_report(attendance_sheet) {
    frappe.show_alert({
        message: __('Generating HTML report...'),
        indicator: 'blue'
    });
    
    frappe.call({
        method: 'church.church.report.attendance_analysis.attendance_analysis.generate_html_report',
        args: {
            attendance_sheet: attendance_sheet
        },
        callback: function(r) {
            if (r.message) {
                // Open in new window
                const report_window = window.open('', '_blank');
                report_window.document.write(r.message);
                report_window.document.close();
            }
        }
    });
}

function export_to_excel(attendance_sheet) {
    frappe.show_alert({
        message: __('Generating Excel file...'),
        indicator: 'blue'
    });
    
    frappe.call({
        method: 'church.church.report.attendance_analysis.attendance_analysis.export_to_beautiful_excel',
        args: {
            attendance_sheet: attendance_sheet
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

function download_pdf_report(attendance_sheet) {
    frappe.call({
        method: 'church.church.report.attendance_analysis.attendance_analysis.generate_html_report',
        args: {
            attendance_sheet: attendance_sheet
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

function show_email_dialog(attendance_sheet) {
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
                                <p><strong>Includes:</strong></p>
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
                        method: 'church.church.report.attendance_analysis.attendance_analysis.email_report',
                        args: {
                            attendance_sheet: attendance_sheet,
                            recipients: recipients_list
                        },
                        freeze: true,
                        freeze_message: __('Sending email...'),
                        callback: function(r) {
                            if (r.message && r.message.success) {
                                frappe.show_alert({
                                    message: __('Email sent successfully'),
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

function add_custom_report_buttons(report) {
    // Preview HTML Report Button
    report.page.add_inner_button(__('Preview HTML Report'), function() {
        const filters = report.get_values();
        
        if (!filters.attendance_sheet) {
            frappe.msgprint(__('Please select an Attendance Sheet'));
            return;
        }
        
        preview_html_report(filters.attendance_sheet);
    }, __('Actions'));
    
    // Export to Beautiful Excel Button
    report.page.add_inner_button(__('Export to Beautiful Excel'), function() {
        const filters = report.get_values();
        
        if (!filters.attendance_sheet) {
            frappe.msgprint(__('Please select an Attendance Sheet'));
            return;
        }
        
        export_to_excel(filters.attendance_sheet);
    }, __('Actions'));
    
    // Download PDF Button
    report.page.add_inner_button(__('Download PDF'), function() {
        const filters = report.get_values();
        
        if (!filters.attendance_sheet) {
            frappe.msgprint(__('Please select an Attendance Sheet'));
            return;
        }
        
        download_pdf_report(filters.attendance_sheet);
    }, __('Actions'));
    
    // Email Report Button
    report.page.add_inner_button(__('Email Report'), function() {
        const filters = report.get_values();
        
        if (!filters.attendance_sheet) {
            frappe.msgprint(__('Please select an Attendance Sheet'));
            return;
        }
        
        show_email_dialog(filters.attendance_sheet);
    }, __('Actions'));
    
    // View Attendance Sheet Button
    report.page.add_inner_button(__('View Attendance Sheet'), function() {
        const filters = report.get_values();
        
        if (!filters.attendance_sheet) {
            frappe.msgprint(__('Please select an Attendance Sheet'));
            return;
        }
        
        frappe.set_route('Form', 'Attendance Sheet', filters.attendance_sheet);
    }, __('Navigate'));
}

function preview_html_report(attendance_sheet) {
    frappe.show_alert({
        message: __('Generating HTML report...'),
        indicator: 'blue'
    });
    
    frappe.call({
        method: 'church.church.report.attendance_analysis.attendance_analysis.generate_html_report',
        args: {
            attendance_sheet: attendance_sheet
        },
        callback: function(r) {
            if (r.message) {
                // Open in new window
                const report_window = window.open('', '_blank');
                report_window.document.write(r.message);
                report_window.document.close();
            }
        }
    });
}

function export_to_excel(attendance_sheet) {
    frappe.show_alert({
        message: __('Generating Excel file...'),
        indicator: 'blue'
    });
    
    frappe.call({
        method: 'church.church.report.attendance_analysis.attendance_analysis.export_to_beautiful_excel',
        args: {
            attendance_sheet: attendance_sheet
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

function download_pdf_report(attendance_sheet) {
    frappe.call({
        method: 'church.church.report.attendance_analysis.attendance_analysis.generate_html_report',
        args: {
            attendance_sheet: attendance_sheet
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

function show_email_dialog(attendance_sheet) {
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
                                <p><strong>Includes:</strong></p>
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
                        method: 'church.church.report.attendance_analysis.attendance_analysis.email_report',
                        args: {
                            attendance_sheet: attendance_sheet,
                            recipients: recipients_list
                        },
                        freeze: true,
                        freeze_message: __('Sending email...'),
                        callback: function(r) {
                            if (r.message && r.message.success) {
                                frappe.show_alert({
                                    message: __('Email sent successfully'),
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