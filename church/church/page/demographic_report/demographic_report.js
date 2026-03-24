// ============================================================================
// Demographic Attendance Report Page - OPTIMIZED
// Fixed data loading and added visitor tracking
// ============================================================================

frappe.pages['demographic-report'].on_page_load = function(wrapper) {
    let page = frappe.ui.make_app_page({
        parent: wrapper,
        title: '📊 Demographic Attendance Report',
        single_column: true
    });
    
    // Store page reference
    frappe.demographic_report_page = page;
    
    
    
    // Add date filters with better defaults
    page.add_field({
        fieldname: 'from_date',
        label: __('From Date'),
        fieldtype: 'Date',
        default: frappe.datetime.month_start(),
        reqd: 1,
        change: function() {
            update_date_range_info(page);
        }
    });
    
    page.add_field({
        fieldname: 'to_date',
        label: __('To Date'),
        fieldtype: 'Date',
        default: frappe.datetime.month_end(),
        reqd: 1,
        change: function() {
            update_date_range_info(page);
        }
    });
    
    page.add_field({
        fieldname: 'branch',
        label: __('Branch'),
        fieldtype: 'Link',
        options: 'Branch',
        change: function() {
            update_branch_info(page);
        }
    });
    
    // Add "Include Visitors" toggle
    page.add_field({
        fieldname: 'include_visitors',
        label: __('Include Visitor Analysis'),
        fieldtype: 'Check',
        default: 1,
        description: __('Show visitor statistics and conversion tracking')
    });
    
    // Add primary actions
    page.set_primary_action(__('🔍 Generate HTML Report'), function() {
        generate_html_report(page);
    }, 'octicon octicon-graph');
    
    // Add secondary action for refresh
    page.set_secondary_action(__('🔄 Refresh'), function() {
        refresh_page(page);
    }, 'octicon octicon-sync');
    
    // Add action icons
    page.add_action_icon('fa fa-file-excel-o', function() {
        generate_excel_report(page);
    }, __('Download Excel Report'));
    
    page.add_action_icon('fa fa-refresh', function() {
        regenerate_last_report(page);
    }, __('Regenerate Last Report'));
    
    // Add menu items
    page.add_menu_item(__('📄 Print Report'), function() {
        print_current_report();
    });
    
    page.add_menu_item(__('📧 Email Report'), function() {
        email_report_dialog(page);
    });
    
    page.add_menu_item(__('🔄 Reset Filters'), function() {
        reset_filters(page);
    });
    
    page.add_menu_item(__('📊 View Summary'), function() {
        show_report_summary(page);
    });
    
    // Show initial info
    update_date_range_info(page);
    
    // Store last report params for refresh
    page.last_report_params = null;
};


// ============================================================================
// HELPER FUNCTIONS
// ============================================================================

function update_date_range_info(page) {
    /**
     * Show date range info
     */
    let values = page.get_form_values();
    if (values.from_date && values.to_date) {
        let from = frappe.datetime.str_to_obj(values.from_date);
        let to = frappe.datetime.str_to_obj(values.to_date);
        let days = frappe.datetime.get_diff(to, from) + 1;
        
        frappe.show_alert({
            message: __('Selected period: {0} days', [days]),
            indicator: 'blue'
        }, 3);
    }
}


function update_branch_info(page) {
    /**
     * Show branch selection info
     */
    let values = page.get_form_values();
    if (values.branch) {
        frappe.show_alert({
            message: __('Branch: {0}', [values.branch]),
            indicator: 'green'
        }, 3);
    }
}


function refresh_page(page) {
    /**
     * Refresh the entire page and reset data
     */
    frappe.show_alert({
        message: __('🔄 Refreshing page...'),
        indicator: 'blue'
    }, 2);
    
    // Clear last report HTML
    window.last_report_html = null;
    
    // Reset to default values
    page.fields_dict.from_date.set_value(frappe.datetime.month_start());
    page.fields_dict.to_date.set_value(frappe.datetime.month_end());
    page.fields_dict.branch.set_value('');
    page.fields_dict.include_visitors.set_value(1);
    
    // Clear last params
    page.last_report_params = null;
    
    frappe.show_alert({
        message: __('✅ Page refreshed'),
        indicator: 'green'
    }, 3);
}


function regenerate_last_report(page) {
    /**
     * Regenerate the last report with same parameters
     */
    if (!page.last_report_params) {
        frappe.msgprint({
            title: __('No Previous Report'),
            indicator: 'orange',
            message: __('Please generate a report first.')
        });
        return;
    }
    
    frappe.show_alert({
        message: __('🔄 Regenerating last report...'),
        indicator: 'blue'
    }, 3);
    
    // Set the last parameters
    page.fields_dict.from_date.set_value(page.last_report_params.from_date);
    page.fields_dict.to_date.set_value(page.last_report_params.to_date);
    if (page.last_report_params.branch) {
        page.fields_dict.branch.set_value(page.last_report_params.branch);
    }
    
    // Generate report
    setTimeout(function() {
        generate_html_report(page);
    }, 500);
}


function reset_filters(page) {
    /**
     * Reset all filters to default
     */
    frappe.confirm(
        __('Reset all filters to default values?'),
        function() {
            refresh_page(page);
        }
    );
}


function show_report_summary(page) {
    /**
     * Show quick summary of current selections
     */
    let values = page.get_form_values();
    
    let from = values.from_date ? frappe.datetime.str_to_obj(values.from_date) : null;
    let to = values.to_date ? frappe.datetime.str_to_obj(values.to_date) : null;
    let days = from && to ? frappe.datetime.get_diff(to, from) + 1 : 0;
    
    let summary_html = `
        <div style="padding: 20px;">
            <h3 style="margin-top: 0;">📊 Report Configuration Summary</h3>
            <table class="table table-bordered" style="margin-top: 15px;">
                <tr>
                    <td style="width: 40%;"><strong>From Date:</strong></td>
                    <td>${values.from_date || 'Not set'}</td>
                </tr>
                <tr>
                    <td><strong>To Date:</strong></td>
                    <td>${values.to_date || 'Not set'}</td>
                </tr>
                <tr>
                    <td><strong>Period:</strong></td>
                    <td>${days} days</td>
                </tr>
                <tr>
                    <td><strong>Branch:</strong></td>
                    <td>${values.branch || 'All Branches'}</td>
                </tr>
                <tr>
                    <td><strong>Include Visitors:</strong></td>
                    <td>${values.include_visitors ? '✅ Yes' : '❌ No'}</td>
                </tr>
            </table>
            
            ${page.last_report_params ? `
                <div style="margin-top: 20px; padding: 15px; background: #e3f2fd; border-radius: 8px;">
                    <h4 style="margin-top: 0; color: #1976d2;">Last Generated Report</h4>
                    <p style="margin: 5px 0;">
                        <strong>Period:</strong> ${page.last_report_params.from_date} to ${page.last_report_params.to_date}
                    </p>
                    <p style="margin: 5px 0;">
                        <strong>Branch:</strong> ${page.last_report_params.branch || 'All Branches'}
                    </p>
                </div>
            ` : ''}
            
            <div style="margin-top: 20px; padding: 15px; background: #fff3cd; border-radius: 8px;">
                <h4 style="margin-top: 0; color: #856404;">⌨️ Keyboard Shortcuts</h4>
                <ul style="margin: 0; padding-left: 20px;">
                    <li><code>Ctrl + Enter</code> - Generate HTML Report</li>
                    <li><code>Ctrl + E</code> - Generate Excel Report</li>
                    <li><code>Ctrl + P</code> - Print Current Report</li>
                    <li><code>Ctrl + R</code> - Refresh Page</li>
                </ul>
            </div>
        </div>
    `;
    
    let d = new frappe.ui.Dialog({
        title: __('Report Summary'),
        fields: [
            {
                fieldtype: 'HTML',
                fieldname: 'summary_html'
            }
        ],
        size: 'large'
    });
    
    d.fields_dict.summary_html.$wrapper.html(summary_html);
    d.show();
}


function validate_inputs(page) {
    /**
     * Validate form inputs before generating report
     */
    let values = page.get_form_values();
    
    if (!values.from_date || !values.to_date) {
        frappe.msgprint({
            title: __('Missing Dates'),
            indicator: 'red',
            message: __('Please select both From Date and To Date')
        });
        return false;
    }
    
    let from = frappe.datetime.str_to_obj(values.from_date);
    let to = frappe.datetime.str_to_obj(values.to_date);
    
    if (from > to) {
        frappe.msgprint({
            title: __('Invalid Date Range'),
            indicator: 'red',
            message: __('From Date cannot be after To Date')
        });
        return false;
    }
    
    // Warn if date range is too large
    let days = frappe.datetime.get_diff(to, from);
    if (days > 365) {
        frappe.confirm(
            __('You selected a date range of {0} days (over 1 year). This may take longer to process. Continue?', [days]),
            function() {
                return true;
            },
            function() {
                return false;
            }
        );
    }
    
    return true;
}


// ============================================================================
// REPORT GENERATION FUNCTIONS
// ============================================================================

function generate_html_report(page) {
    /**
     * Generate and display HTML report
     */
    
    if (!validate_inputs(page)) {
        return;
    }
    
    let values = page.get_form_values();
    
    // Store last report params for refresh
    page.last_report_params = {
        from_date: values.from_date,
        to_date: values.to_date,
        branch: values.branch
    };
    
    frappe.show_alert({
        message: __('Generating report...'),
        indicator: 'blue'
    }, 3);
    
    frappe.call({
        method: 'church.church.page.demographic_report.demographic_attendance_report.generate_demographic_html_report',
        args: {
            from_date: values.from_date,
            to_date: values.to_date,
            branch: values.branch || null
        },
        freeze: true,
        freeze_message: __('Generating Demographic Report...'),
        callback: function(r) {
            console.log('HTML Report Response:', r);
            
            if (r.message) {
                if (r.message.success && r.message.html) {
                    // Open in new window
                    let report_window = window.open('', '_blank');
                    report_window.document.write(r.message.html);
                    report_window.document.close();
                    
                    // Store for printing
                    window.last_report_html = r.message.html;
                    
                    frappe.show_alert({
                        message: __('✅ Report generated successfully!'),
                        indicator: 'green'
                    }, 5);
                } else {
                    // Show error
                    frappe.msgprint({
                        title: __('Report Generation Failed'),
                        indicator: 'red',
                        message: r.message.error || __('Unknown error occurred')
                    });
                }
            } else {
                frappe.msgprint({
                    title: __('No Response'),
                    indicator: 'orange',
                    message: __('No response received from server. Please check your connection and try again.')
                });
            }
        },
        error: function(r) {
            console.error('HTML Report Error:', r);
            frappe.msgprint({
                title: __('Error'),
                indicator: 'red',
                message: __('Failed to generate report. Please check error log.')
            });
        }
    });
}


function generate_excel_report(page) {
    /**
     * Generate and download Excel report
     */
    
    if (!validate_inputs(page)) {
        return;
    }
    
    let values = page.get_form_values();
    
    frappe.show_alert({
        message: __('Generating Excel file...'),
        indicator: 'blue'
    }, 3);
    
    frappe.call({
        method: 'church.church.page.demographic_report.demographic_attendance_report.generate_demographic_excel_report',
        args: {
            from_date: values.from_date,
            to_date: values.to_date,
            branch: values.branch || null
        },
        freeze: true,
        freeze_message: __('Generating Excel Report...'),
        callback: function(r) {
            console.log('Excel Report Response:', r);
            
            if (r.message && r.message.success) {
                // Download file
                let link = document.createElement('a');
                link.href = 'data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,' + r.message.file_content;
                link.download = r.message.filename;
                link.click();
                
                frappe.show_alert({
                    message: __('✅ Excel downloaded: {0}', [r.message.filename]),
                    indicator: 'green'
                }, 5);
            } else {
                frappe.msgprint({
                    title: __('Excel Generation Failed'),
                    indicator: 'red',
                    message: r.message ? r.message.error : __('Unknown error occurred')
                });
            }
        },
        error: function(r) {
            console.error('Excel Report Error:', r);
            frappe.msgprint({
                title: __('Error'),
                indicator: 'red',
                message: __('Failed to generate Excel. Please check error log.')
            });
        }
    });
}


function print_current_report() {
    /**
     * Print last generated report
     */
    if (window.last_report_html) {
        let print_window = window.open('', '_blank');
        print_window.document.write(window.last_report_html);
        print_window.document.close();
        print_window.print();
    } else {
        frappe.msgprint({
            title: __('No Report'),
            indicator: 'orange',
            message: __('Please generate a report first before printing.')
        });
    }
}


function email_report_dialog(page) {
    /**
     * Show dialog to email report
     */
    
    let d = new frappe.ui.Dialog({
        title: __('Email Report'),
        fields: [
            {
                fieldname: 'recipients',
                label: __('Recipients'),
                fieldtype: 'Small Text',
                reqd: 1,
                description: __('Email addresses separated by commas')
            },
            {
                fieldname: 'subject',
                label: __('Subject'),
                fieldtype: 'Data',
                default: __('Demographic Attendance Report')
            },
            {
                fieldname: 'message',
                label: __('Message'),
                fieldtype: 'Text Editor',
                default: __('Please find attached the demographic attendance report.')
            },
            {
                fieldname: 'format',
                label: __('Format'),
                fieldtype: 'Select',
                options: 'HTML\nExcel\nBoth',
                default: 'HTML'
            }
        ],
        primary_action_label: __('Send'),
        primary_action: function(values) {
            d.hide();
            send_report_email(page, values);
        }
    });
    
    d.show();
}


function send_report_email(page, email_data) {
    /**
     * Send report via email
     */
    
    let page_values = page.get_form_values();
    
    frappe.call({
        method: 'church.church.page.demographic_report.demographic_attendance_report.email_demographic_report',
        args: {
            from_date: page_values.from_date,
            to_date: page_values.to_date,
            branch: page_values.branch || null,
            recipients: email_data.recipients,
            subject: email_data.subject,
            message: email_data.message,
            format: email_data.format
        },
        freeze: true,
        freeze_message: __('Sending email...'),
        callback: function(r) {
            if (r.message && r.message.success) {
                frappe.msgprint({
                    title: __('Email Sent'),
                    indicator: 'green',
                    message: __('Report emailed successfully to {0}', [email_data.recipients])
                });
            } else {
                frappe.msgprint({
                    title: __('Failed'),
                    indicator: 'red',
                    message: r.message ? r.message.error : __('Failed to send email')
                });
            }
        }
    });
}


// ============================================================================
// AUTO-REFRESH ON PAGE SHOW
// ============================================================================

frappe.pages['demographic-report'].on_page_show = function() {
    /**
     * Refresh data when page is shown
     */
    console.log('Demographic Report page shown');
};


// ============================================================================
// KEYBOARD SHORTCUTS
// ============================================================================

$(document).on('keydown', function(e) {
    // Check if we're on the demographic report page
    if (!frappe.demographic_report_page) {
        return;
    }
    
    // Ctrl+Enter to generate report
    if (e.ctrlKey && e.key === 'Enter') {
        e.preventDefault();
        generate_html_report(frappe.demographic_report_page);
    }
    
    // Ctrl+E to generate Excel
    if (e.ctrlKey && e.key === 'e') {
        e.preventDefault();
        generate_excel_report(frappe.demographic_report_page);
    }
    
    // Ctrl+P to print
    if (e.ctrlKey && e.key === 'p') {
        e.preventDefault();
        print_current_report();
    }
    
    // Ctrl+R to refresh
    if (e.ctrlKey && e.key === 'r') {
        e.preventDefault();
        refresh_page(frappe.demographic_report_page);
    }
});