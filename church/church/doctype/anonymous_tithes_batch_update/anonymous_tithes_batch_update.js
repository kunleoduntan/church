// Copyright (c) 2026, kunle and contributors
// For license information, please see license.txt



frappe.ui.form.on('Anonymous Tithes Batch Update', {
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
            
            if (!frm.doc.description) {
                frm.set_value('description', 'Anonymous tithes received from various members');
            }
        }
    },
    
    branch: function(frm) {
        update_branch_in_tithes(frm);
        get_default_bank_account(frm);
    },
    
    designated_bank_acct: function(frm) {
        update_bank_in_tithes(frm);
    },
    
    currency: function(frm) {
        update_currency_in_tithes(frm);
    },
    
    description: function(frm) {
        update_description_in_tithes(frm);
    },
    
    before_save: function(frm) {
        validate_dates(frm);
        calculate_totals(frm);
        set_readonly_fields(frm);
    }
});

frappe.ui.form.on("Tithe Transaction Entry for Anonymous", {
    amount_paid: function(frm, cdt, cdn) {
        calculate_amount_in_lc(frm, cdt, cdn);
    },
    
    exchange_rate: function(frm, cdt, cdn) {
        calculate_amount_in_lc(frm, cdt, cdn);
    },
    
    currency: function(frm, cdt, cdn) {
        const row = frappe.get_doc(cdt, cdn);
        
        if (row.currency === 'NGN') {
            frappe.model.set_value(cdt, cdn, 'exchange_rate', 1.00);
        } else if (row.currency) {
            get_exchange_rate(frm, cdt, cdn, row.currency);
        }
    }
});

// Helper Functions

function setup_custom_buttons(frm) {
    if (frm.doc.docstatus === 0) {
        frm.add_custom_button(__('Get Import Template'), function() {
            download_import_template();
        }, __('Tools'));
        
        frm.add_custom_button(__('Import from Excel'), function() {
            import_from_excel(frm);
        }, __('Tools'));
    }
    
    if (frm.doc.docstatus === 1) {
        frm.add_custom_button(__('Export to Excel'), function() {
            export_to_excel(frm);
        }, __('Tools'));
        
        frm.add_custom_button(__('View HTML Report'), function() {
            view_html_report(frm);
        }, __('Reports'));
        
        frm.add_custom_button(__('Email Report'), function() {
            show_email_dialog(frm);
        }, __('Actions'));
        
        frm.add_custom_button(__('Quick Email'), function() {
            quick_email_report(frm);
        }, __('Actions'));
    }
}

function apply_alternating_row_colors(frm) {
    setTimeout(() => {
        frm.fields_dict.tithe_transaction_entry_for_anonymous.grid.wrapper.find('.grid-row').each(function(i, row) {
            if (i % 2 === 0) {
                $(row).css('background-color', '#ffffff');
            } else {
                $(row).css('background-color', '#e0f7fa');
            }
        });
    }, 100);
}

function set_field_properties(frm) {
    frm.set_df_property('amount_paid', 'read_only', 1);
    frm.set_df_property('month', 'read_only', 1);
    
    if (frm.doc.designated_bank_acct && !frm.doc.currency) {
        frappe.db.get_value('Bank Account', frm.doc.designated_bank_acct, 'account_currency')
            .then(r => {
                if (r.message && r.message.account_currency) {
                    frm.set_value('currency', r.message.account_currency);
                }
            });
    }
}

function validate_dates(frm) {
    if (frm.doc.reporting_date && frm.doc.start_date && frm.doc.end_date) {
        if (frm.doc.reporting_date < frm.doc.start_date || frm.doc.reporting_date < frm.doc.end_date) {
            frappe.msgprint(__('The reporting date cannot be earlier than the start date or end date.'));
            frappe.validated = false;
        }
    }
}

function update_branch_in_tithes(frm) {
    if (frm.doc.branch && frm.doc.tithe_transaction_entry_for_anonymous) {
        frm.doc.tithe_transaction_entry_for_anonymous.forEach(row => {
            frappe.model.set_value(row.doctype, row.name, 'branch', frm.doc.branch);
        });
        frm.refresh_field('tithe_transaction_entry_for_anonymous');
    }
}

function update_bank_in_tithes(frm) {
    if (frm.doc.designated_bank_acct && frm.doc.tithe_transaction_entry_for_anonymous) {
        frm.doc.tithe_transaction_entry_for_anonymous.forEach(row => {
            frappe.model.set_value(row.doctype, row.name, 'designated_bank_acct', frm.doc.designated_bank_acct);
        });
        frm.refresh_field('tithe_transaction_entry_for_anonymous');
    }
}

function update_currency_in_tithes(frm) {
    if (frm.doc.currency && frm.doc.tithe_transaction_entry_for_anonymous) {
        frm.doc.tithe_transaction_entry_for_anonymous.forEach(row => {
            if (!row.currency) {
                frappe.model.set_value(row.doctype, row.name, 'currency', frm.doc.currency);
            }
        });
        frm.refresh_field('tithe_transaction_entry_for_anonymous');
    }
}

function update_description_in_tithes(frm) {
    if (frm.doc.description && frm.doc.tithe_transaction_entry_for_anonymous) {
        frm.doc.tithe_transaction_entry_for_anonymous.forEach(row => {
            if (!row.other_details) {
                frappe.model.set_value(row.doctype, row.name, 'other_details', frm.doc.description);
            }
        });
        frm.refresh_field('tithe_transaction_entry_for_anonymous');
    }
}

function get_default_bank_account(frm) {
    if (frm.doc.branch) {
        frappe.db.get_value('Branch', frm.doc.branch, 'default_bank_account')
            .then(r => {
                if (r.message && r.message.default_bank_account) {
                    frm.set_value('designated_bank_acct', r.message.default_bank_account);
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
    
    calculate_totals(frm);
}

function calculate_totals(frm) {
    let total = 0;
    
    if (frm.doc.tithe_transaction_entry_for_anonymous) {
        frm.doc.tithe_transaction_entry_for_anonymous.forEach(row => {
            total += flt(row.amount_in_lc || 0);
        });
    }
    
    frm.set_value('amount_paid', total);
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
    frm.set_df_property('amount_paid', 'read_only', 1);
    frm.set_df_property('month', 'read_only', 1);
}

function download_import_template() {
    frappe.call({
        method: 'church.church.doctype.anonymous_tithes_batch_update.anonymous_tithes_batch_update.get_anonymous_tithes_template',
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
        frappe.msgprint(__('Excel import functionality to be implemented'));
    }, __('Import Anonymous Tithes from Excel'));
}

function export_to_excel(frm) {
    const url = frappe.urllib.get_full_url(
        '/api/method/church.church.doctype.anonymous_tithes_batch_update.anonymous_tithes_batch_update.export_anonymous_tithes'
        + '?anonymous_tithes_name=' + encodeURIComponent(frm.doc.name)
    );
    
    const link = document.createElement('a');
    link.href = url;
    link.download = `anonymous_tithes_${frm.doc.name}.xlsx`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    
    frappe.show_alert({
        message: __('Downloading Excel file...'),
        indicator: 'green'
    }, 3);
}

function view_html_report(frm) {
    const print_url = frappe.urllib.get_full_url(
        '/printview?'
        + 'doctype=' + encodeURIComponent('Anonymous Tithes Batch Update')
        + '&name=' + encodeURIComponent(frm.doc.name)
        + '&format=' + encodeURIComponent('Anonymous Tithes Report')
        + '&no_letterhead=0'
        + '&letterhead=' + encodeURIComponent('No Letterhead')
        + '&settings={}'
        + '&_lang=en'
    );
    
    window.open(print_url, '_blank');
}

function show_email_dialog(frm) {
    const d = new frappe.ui.Dialog({
        title: __('Email Anonymous Tithes Report'),
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
                default: `Anonymous Tithes Batch - ${frm.doc.branch} (${frm.doc.start_date} to ${frm.doc.end_date})`
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
        method: 'church.church.doctype.anonymous_tithes_batch_update.anonymous_tithes_batch_update.email_anonymous_tithes',
        args: {
            anonymous_tithes_name: frm.doc.name,
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
        __('Send anonymous tithes report to default recipients?<br><br>This will email the report with a beautiful template and Excel attachment.'),
        function() {
            frappe.call({
                method: 'church.church.doctype.anonymous_tithes_batch_update.anonymous_tithes_batch_update.email_anonymous_tithes',
                args: {
                    anonymous_tithes_name: frm.doc.name,
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