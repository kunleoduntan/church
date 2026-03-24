// -*- coding: utf-8 -*-
// Copyright (c) 2025, Value Impacts Consulting and contributors
// For license information, please see license.txt

frappe.ui.form.on('Offering Sheet', {
    refresh: function(frm) {
        setup_custom_buttons(frm);
        apply_alternating_row_colors(frm);
        set_field_properties(frm);
    },
    
    reporting_date: function(frm) {
        if (frm.doc.reporting_date) {
            const reportingDate = new Date(frm.doc.reporting_date);
            const monthName = reportingDate.toLocaleString('default', { month: 'long', year: 'numeric' });
            frm.set_value('month', monthName);
            
            // Auto-set date range (Sunday to Sunday)
            const dayOfWeek = reportingDate.getDay();
            const daysToSubtract = dayOfWeek === 0 ? 6 : dayOfWeek + 6;
            const dateFrom = new Date(reportingDate);
            dateFrom.setDate(dateFrom.getDate() - daysToSubtract);
            
            frm.set_value('date_from', frappe.datetime.obj_to_str(dateFrom));
            frm.set_value('date_to', frappe.datetime.obj_to_str(reportingDate));
        }
    },
    
    branch: function(frm) {
        update_branch_in_offerings(frm);
        get_default_bank_account(frm);
    },
    
    before_save: function(frm) {
        calculate_totals(frm);
        set_readonly_fields(frm);
    }
});

frappe.ui.form.on("Offerings", {
    date: function(frm, cdt, cdn) {
        const row = frappe.get_doc(cdt, cdn);
        
        if (row.date) {
            const date = new Date(row.date);
            const dayName = date.toLocaleString('default', { weekday: 'short' });
            frappe.model.set_value(cdt, cdn, 'day', dayName);
        }
    },
    
    amount_paid: function(frm, cdt, cdn) {
        calculate_amount_in_lc(frm, cdt, cdn);
    },
    
    exchange_rate: function(frm, cdt, cdn) {
        calculate_amount_in_lc(frm, cdt, cdn);
    },
    
    currency: function(frm, cdt, cdn) {
        const row = frappe.get_doc(cdt, cdn);
        
        // Set exchange rate to 1 for NGN, otherwise prompt for rate
        if (row.currency === 'NGN') {
            frappe.model.set_value(cdt, cdn, 'exchange_rate', 1.00);
        } else if (row.currency) {
            get_exchange_rate(frm, cdt, cdn, row.currency);
        }
    },
    
    offering_type: function(frm, cdt, cdn) {
        const row = frappe.get_doc(cdt, cdn);
        
        if (row.offering_type) {
            frappe.db.get_value('Offering Type', row.offering_type, 'income_account')
                .then(r => {
                    if (r.message && r.message.income_account) {
                        frappe.model.set_value(cdt, cdn, 'income_account', r.message.income_account);
                    }
                });
        }
    }
});

// Helper Functions

function setup_custom_buttons(frm) {
    if (frm.doc.docstatus === 0) {
        // Add custom buttons for draft state
        frm.add_custom_button(__('Get Import Template'), function() {
            download_import_template();
        }, __('Tools'));
        
        frm.add_custom_button(__('Import from Excel'), function() {
            import_from_excel(frm);
        }, __('Tools'));
    }
    
    if (frm.doc.docstatus === 1) {
        // Add export button for submitted documents
        frm.add_custom_button(__('Export to Excel'), function() {
            export_to_excel(frm);
        }, __('Tools'));
        
     //   frm.add_custom_button(__('View HTML Report'), function() {
     //       view_html_report(frm);
     //  }, __('Reports'));
        
        // Add email button
        frm.add_custom_button(__('Email Report'), function() {
            show_email_dialog(frm);
        }, __('Actions'));
        
        // Quick email to default recipients
        frm.add_custom_button(__('Quick Email'), function() {
            quick_email_report(frm);
        }, __('Actions'));
    }
}

function apply_alternating_row_colors(frm) {
    setTimeout(() => {
        frm.fields_dict.offering.grid.wrapper.find('.grid-row').each(function(i, row) {
            if (i % 2 === 0) {
                $(row).css('background-color', '#f8f9fa');
            } else {
                $(row).css('background-color', '#e3f2fd');
            }
        });
    }, 100);
}

function set_field_properties(frm) {
    frm.set_df_property('total', 'read_only', 1);
    frm.set_df_property('month', 'read_only', 1);
    
    // Set currency field based on bank account
    if (frm.doc.bank_account && !frm.doc.currency) {
        frappe.db.get_value('Bank Account', frm.doc.bank_account, 'account_currency')
            .then(r => {
                if (r.message && r.message.account_currency) {
                    frm.set_value('currency', r.message.account_currency);
                }
            });
    }
}

function update_branch_in_offerings(frm) {
    if (frm.doc.branch && frm.doc.offering) {
        frm.doc.offering.forEach(row => {
            frappe.model.set_value(row.doctype, row.name, 'branch', frm.doc.branch);
        });
        frm.refresh_field('offering');
    }
}

function get_default_bank_account(frm) {
    if (frm.doc.branch) {
        frappe.db.get_value('Branch', frm.doc.branch, 'default_bank_account')
            .then(r => {
                if (r.message && r.message.default_bank_account) {
                    frm.set_value('bank_account', r.message.default_bank_account);
                }
            });
    }
}

function calculate_amount_in_lc(frm, cdt, cdn) {
    const row = frappe.get_doc(cdt, cdn);
    
    const amountPaid = flt(row.amount_paid || 0);
    const exchangeRate = flt(row.exchange_rate || 1);
    const amountInLC = amountPaid * exchangeRate;
    
    frappe.model.set_value(cdt, cdn, 'amount_in_lc', amountInLC);
    
    // Recalculate totals
    calculate_totals(frm);
}

function calculate_totals(frm) {
    let total = 0;
    
    if (frm.doc.offering) {
        frm.doc.offering.forEach(row => {
            total += flt(row.amount_in_lc || 0);
        });
    }
    
    frm.set_value('total', total);
}

function get_exchange_rate(frm, cdt, cdn, currency) {
    const company = frm.doc.company || frappe.defaults.get_user_default("Company");
    
    frappe.call({
        method: "erpnext.setup.utils.get_exchange_rate",
        args: {
            from_currency: currency,
            to_currency: frm.doc.currency || "NGN",
            transaction_date: frm.doc.reporting_date || frappe.datetime.get_today()
        },
        callback: function(r) {
            if (r.message) {
                frappe.model.set_value(cdt, cdn, 'exchange_rate', flt(r.message, 2));
            }
        }
    });
}

function set_readonly_fields(frm) {
    frm.set_df_property('total', 'read_only', 1);
    frm.set_df_property('month', 'read_only', 1);
    frm.set_df_property('currency', 'read_only', frm.doc.bank_account ? 1 : 0);
}

function download_import_template() {
    frappe.call({
        method: 'church.church.doctype.offering_sheet.offering_sheet.get_offering_template',
        callback: function(r) {
            if (!r.exc) {
                frappe.msgprint(__('Template downloaded successfully'));
            }
        }
    });
}

function import_from_excel(frm) {
    frappe.prompt([{
        fieldname: 'file',
        fieldtype: 'Attach',
        label: __('Upload Excel File'),
        reqd: 1
    }], function(values) {
        frappe.call({
            method: 'frappe.utils.file_manager.get_file',
            args: {
                file_url: values.file
            },
            callback: function(r) {
                if (r.message) {
                    process_excel_import(frm, r.message);
                }
            }
        });
    }, __('Import Offerings from Excel'));
}

function export_to_excel(frm) {
    // Direct download approach
    const url = frappe.urllib.get_full_url(
        '/api/method/church.church.doctype.offering_sheet.offering_sheet.export_offering_sheet'
        + '?offering_sheet_name=' + encodeURIComponent(frm.doc.name)
    );
    
    // Create temporary link and trigger download
    const link = document.createElement('a');
    link.href = url;
    link.download = `offering_sheet_${frm.doc.name}.xlsx`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    
    frappe.show_alert({
        message: __('Downloading Excel file...'),
        indicator: 'green'
    }, 3);
}

function view_html_report(frm) {
    // Open in new window with custom print format
    const print_url = frappe.urllib.get_full_url(
        '/printview?'
        + 'doctype=' + encodeURIComponent('Offering Sheet')
        + '&name=' + encodeURIComponent(frm.doc.name)
        + '&format=' + encodeURIComponent('Offering Sheet Report')
        + '&no_letterhead=0'
        + '&letterhead=' + encodeURIComponent('No Letterhead')
        + '&settings={}'
        + '&_lang=en'
    );
    
    window.open(print_url, '_blank');
}

function process_excel_import(frm, file_data) {
    // This would require additional server-side processing
    // Placeholder for Excel import functionality
    frappe.msgprint(__('Excel import functionality to be implemented'));
}

function show_email_dialog(frm) {
    const d = new frappe.ui.Dialog({
        title: __('Email Offering Sheet'),
        fields: [
            {
                fieldname: 'recipients',
                fieldtype: 'Small Text',
                label: __('Recipients'),
                description: __('Enter email addresses separated by commas'),
                reqd: 1
            },
            {
                fieldname: 'cc',
                fieldtype: 'Small Text',
                label: __('CC'),
                description: __('Enter CC email addresses separated by commas')
            },
            {
                fieldname: 'subject',
                fieldtype: 'Data',
                label: __('Subject'),
                default: `Offering Sheet - ${frm.doc.branch} (${frm.doc.date_from} to ${frm.doc.date_to})`
            },
            {
                fieldname: 'message',
                fieldtype: 'Small Text',
                label: __('Additional Message'),
                description: __('Optional message to include in the email body')
            },
            {
                fieldname: 'attach_excel',
                fieldtype: 'Check',
                label: __('Attach Excel File'),
                default: 1
            }
        ],
        primary_action_label: __('Send Email'),
        primary_action(values) {
            send_email_with_template(frm, values);
            d.hide();
        }
    });
    
    d.show();
}

function send_email_with_template(frm, values) {
    frappe.call({
        method: 'church.church.doctype.offering_sheet.offering_sheet.email_offering_sheet',
        args: {
            offering_sheet_name: frm.doc.name,
            recipients: values.recipients,
            cc: values.cc,
            subject: values.subject,
            message: values.message,
            attach_excel: values.attach_excel
        },
        freeze: true,
        freeze_message: __('Sending email...'),
        callback: function(r) {
            if (r.message && r.message.status === 'success') {
                frappe.show_alert({
                    message: __('Email sent successfully to {0}', [r.message.recipients.join(', ')]),
                    indicator: 'green'
                }, 5);
                
                frm.reload_doc();
            }
        },
        error: function(r) {
            frappe.msgprint({
                title: __('Email Error'),
                message: __('Failed to send email. Please check the error log.'),
                indicator: 'red'
            });
        }
    });
}

function quick_email_report(frm) {
    frappe.confirm(
        __('Send offering sheet report to default recipients?<br><br>This will email the report with a beautiful template and Excel attachment.'),
        function() {
            frappe.call({
                method: 'church.church.doctype.offering_sheet.offering_sheet.email_offering_sheet',
                args: {
                    offering_sheet_name: frm.doc.name,
                    attach_excel: 1
                },
                freeze: true,
                freeze_message: __('Sending email...'),
                callback: function(r) {
                    if (r.message && r.message.status === 'success') {
                        frappe.show_alert({
                            message: __('Email sent successfully!'),
                            indicator: 'green'
                        }, 5);
                        
                        frm.reload_doc();
                    }
                }
            });
        }
    );
}