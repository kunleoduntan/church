// Copyright (c) 2026, kunle and contributors
// For license information, please see license.txt

// ============================================
// Tithe Batch Update - Optimized Client Script
// ============================================

frappe.ui.form.on('Tithe Batch Update', {
    onload: function(frm) {
        // Set default currency from company if not set
        if (!frm.doc.currency) {
            frappe.db.get_value('Company', frappe.defaults.get_user_default('Company'), 'default_currency', (r) => {
                if (r && r.default_currency) {
                    frm.set_value('currency', r.default_currency);
                }
            });
        }
    },

    refresh: function(frm) {
        // Apply zebra striping for better readability
        apply_zebra_striping(frm);
        
        // Add custom buttons
        add_custom_buttons(frm);
        
        // Set read-only for calculated fields
        set_readonly_fields(frm);
        
        // Show receipt generation status indicator
        show_receipt_status_indicator(frm);
    },

    reporting_date: function(frm) {
        if (frm.doc.reporting_date) {
            // Auto-populate month
            const reportingDate = new Date(frm.doc.reporting_date);
            const monthName = reportingDate.toLocaleString('default', { month: 'long', year: 'numeric' });
            frm.set_value('month', monthName);
        }
    },

    validate: function(frm) {
        // Validate date ranges
        if (!validate_date_range(frm)) {
            frappe.validated = false;
            return;
        }
        
        // Validate at least one transaction exists
        if (!frm.doc.tithe_transaction_entry || frm.doc.tithe_transaction_entry.length === 0) {
            frappe.msgprint(__('Please add at least one tithe transaction.'));
            frappe.validated = false;
            return;
        }
        
        // Validate all transactions
        if (!validate_transactions(frm)) {
            frappe.validated = false;
            return;
        }
    },

    before_save: function(frm) {
        // Update branch and bank account for all child rows
        update_child_table_fields(frm);
        
        // Calculate totals
        calculate_totals(frm);
    },

    branch: function(frm) {
        if (frm.doc.branch) {
            update_child_table_fields(frm);
        }
    },

    designated_bank_acct: function(frm) {
        if (frm.doc.designated_bank_acct) {
            update_child_table_fields(frm);
        }
    },

    currency: function(frm) {
        if (frm.doc.currency) {
            // Update currency for all child rows
            $.each(frm.doc.tithe_transaction_entry || [], function(i, row) {
                frappe.model.set_value(row.doctype, row.name, 'currency', frm.doc.currency);
            });
            frm.refresh_field('tithe_transaction_entry');
        }
    },

    default_exchange_rate: function(frm) {
        if (frm.doc.default_exchange_rate) {
            // Update exchange rate for all rows that have rate = 1
            $.each(frm.doc.tithe_transaction_entry || [], function(i, row) {
                if (flt(row.exchange_rate) === 1.0) {
                    frappe.model.set_value(row.doctype, row.name, 'exchange_rate', frm.doc.default_exchange_rate);
                }
            });
            frm.refresh_field('tithe_transaction_entry');
        }
    },

    import_template_button: function(frm) {
        download_import_template(frm);
    },

    import_excel_button: function(frm) {
        import_from_excel(frm);
    }
});

// ============================================
// Child Table Events
// ============================================

frappe.ui.form.on('Tithe Transaction Entry', {
    tithe_transaction_entry_add: function(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        
        // Set defaults from parent
        frappe.model.set_value(cdt, cdn, 'branch', frm.doc.branch);
        frappe.model.set_value(cdt, cdn, 'designated_bank_acct', frm.doc.designated_bank_acct);
        frappe.model.set_value(cdt, cdn, 'currency', frm.doc.currency);
        frappe.model.set_value(cdt, cdn, 'date', frm.doc.reporting_date);
        frappe.model.set_value(cdt, cdn, 'exchange_rate', frm.doc.default_exchange_rate || 1.0);
    },

    member_id: function(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        
        if (row.member_id) {
            // Fetch member details
            frappe.db.get_value('Member', row.member_id, ['full_name', 'parish'], (r) => {
                if (r) {
                    frappe.model.set_value(cdt, cdn, 'full_name', r.full_name);
                    
                    // Set branch if not already set
                    if (!row.branch && r.parish) {
                        frappe.model.set_value(cdt, cdn, 'branch', r.parish);
                    }
                }
            });
        }
    },

    type: function(frm, cdt, cdn) {
        calculate_tithe_amounts(frm, cdt, cdn);
    },

    amount_paid: function(frm, cdt, cdn) {
        calculate_tithe_amounts(frm, cdt, cdn);
    },

    exchange_rate: function(frm, cdt, cdn) {
        calculate_tithe_amounts(frm, cdt, cdn);
    },

    tithe_transaction_entry_remove: function(frm) {
        calculate_totals(frm);
    }
});

// ============================================
// Utility Functions
// ============================================

function validate_date_range(frm) {
    if (frm.doc.reporting_date && frm.doc.start_date && frm.doc.end_date) {
        const reportingDate = new Date(frm.doc.reporting_date);
        const startDate = new Date(frm.doc.start_date);
        const endDate = new Date(frm.doc.end_date);
        
        if (reportingDate < startDate) {
            frappe.msgprint(__('Reporting date cannot be earlier than start date.'));
            return false;
        }
        
        if (startDate > endDate) {
            frappe.msgprint(__('Start date cannot be later than end date.'));
            return false;
        }
    }
    return true;
}

function validate_transactions(frm) {
    let valid = true;
    let errors = [];
    
    $.each(frm.doc.tithe_transaction_entry || [], function(i, row) {
        let row_errors = [];
        
        if (!row.member_id) {
            row_errors.push('Member ID is required');
        }
        
        if (!row.date) {
            row_errors.push('Date is required');
        }
        
        if (!row.type) {
            row_errors.push('Source is required');
        }
        
        if (flt(row.amount_paid) <= 0) {
            row_errors.push('Amount must be greater than zero');
        }
        
        if (row_errors.length > 0) {
            errors.push(`Row ${i + 1}: ${row_errors.join(', ')}`);
            valid = false;
        }
    });
    
    if (!valid) {
        frappe.msgprint({
            title: __('Validation Errors'),
            message: errors.join('<br>'),
            indicator: 'red'
        });
    }
    
    return valid;
}

function update_child_table_fields(frm) {
    if (!frm.doc.tithe_transaction_entry) return;
    
    $.each(frm.doc.tithe_transaction_entry, function(i, row) {
        if (frm.doc.branch) {
            frappe.model.set_value(row.doctype, row.name, 'branch', frm.doc.branch);
        }
        
        if (frm.doc.designated_bank_acct) {
            frappe.model.set_value(row.doctype, row.name, 'designated_bank_acct', frm.doc.designated_bank_acct);
        }
    });
}

function calculate_tithe_amounts(frm, cdt, cdn) {
    let row = locals[cdt][cdn];
    
    let amountPaid = flt(row.amount_paid || 0);
    let exchangeRate = flt(row.exchange_rate || 1);
    let totalBaseCurrency = amountPaid * exchangeRate;
    
    // Set total in base currency
    frappe.model.set_value(cdt, cdn, 'total_base_currency', totalBaseCurrency);
    
    // Calculate worker/member tithe based on type
    if (row.type === 'Worker') {
        frappe.model.set_value(cdt, cdn, 'worker_tithe', totalBaseCurrency);
        frappe.model.set_value(cdt, cdn, 'member_tithe', 0);
    } else if (row.type === 'Member') {
        frappe.model.set_value(cdt, cdn, 'worker_tithe', 0);
        frappe.model.set_value(cdt, cdn, 'member_tithe', totalBaseCurrency);
    } else {
        frappe.model.set_value(cdt, cdn, 'worker_tithe', 0);
        frappe.model.set_value(cdt, cdn, 'member_tithe', 0);
    }
    
    // Recalculate totals
    setTimeout(() => calculate_totals(frm), 100);
}

function calculate_totals(frm) {
    if (!frm.doc.tithe_transaction_entry) return;
    
    let totalAmount = 0;
    let totalWorkers = 0;
    let totalMembers = 0;
    let totalTransactions = frm.doc.tithe_transaction_entry.length;
    
    $.each(frm.doc.tithe_transaction_entry, function(i, row) {
        totalAmount += flt(row.total_base_currency || 0);
        totalWorkers += flt(row.worker_tithe || 0);
        totalMembers += flt(row.member_tithe || 0);
    });
    
    frm.set_value('total_transactions', totalTransactions);
    frm.set_value('amount_paid', totalAmount);
    frm.set_value('total_for_workers', totalWorkers);
    frm.set_value('total_for_members', totalMembers);
    
    frm.refresh_field('total_transactions');
    frm.refresh_field('amount_paid');
    frm.refresh_field('total_for_workers');
    frm.refresh_field('total_for_members');
}

function set_readonly_fields(frm) {
    frm.set_df_property('month', 'read_only', 1);
    frm.set_df_property('amount_paid', 'read_only', 1);
    frm.set_df_property('total_for_workers', 'read_only', 1);
    frm.set_df_property('total_for_members', 'read_only', 1);
    frm.set_df_property('total_transactions', 'read_only', 1);
}

function apply_zebra_striping(frm) {
    setTimeout(() => {
        frm.fields_dict.tithe_transaction_entry.grid.wrapper.find('.grid-row').each(function(i, row) {
            if (i % 2 === 0) {
                $(row).css('background-color', '#ffffff');
            } else {
                $(row).css('background-color', '#e9ffdb');
            }
        });
    }, 300);
}

function add_custom_buttons(frm) {
    if (frm.doc.docstatus === 1) {
        // Generate Receipts button
        if (frm.doc.receipt_status !== 'Completed') {
            frm.add_custom_button(__('Generate Receipts'), function() {
                generate_receipts(frm);
            }, __('Actions'));
        }
        
        // View Receipts button
        if (frm.doc.receipts_created > 0) {
            frm.add_custom_button(__('View Receipts'), function() {
                frappe.set_route('List', 'Receipts', {
                    'tithe_batch_reference': frm.doc.name
                });
            }, __('Actions'));
        }
        
        // Print Tithe Collection button
        frm.add_custom_button(__('Print Collection Report'), function() {
            print_collection_report(frm);
        }, __('Print'));
        
        // Export to Excel button
        frm.add_custom_button(__('Export to Excel'), function() {
            export_to_excel(frm);
        }, __('Export'));
    }
}

function show_receipt_status_indicator(frm) {
    if (frm.doc.docstatus === 1 && frm.doc.receipt_status) {
        let color = 'blue';
        if (frm.doc.receipt_status === 'Completed') color = 'green';
        else if (frm.doc.receipt_status === 'Failed' || frm.doc.receipt_status === 'Partially Failed') color = 'red';
        else if (frm.doc.receipt_status === 'In Progress') color = 'orange';
        
        frm.dashboard.add_indicator(
            __('Receipt Status: {0}', [frm.doc.receipt_status]),
            color
        );
        
        if (frm.doc.receipts_created > 0) {
            frm.dashboard.add_indicator(
                __('Receipts Created: {0}/{1}', [frm.doc.receipts_created, frm.doc.total_transactions]),
                frm.doc.receipts_created === frm.doc.total_transactions ? 'green' : 'orange'
            );
        }
    }
}

function generate_receipts(frm) {
    frappe.confirm(
        __('Generate receipts for all {0} transactions in this batch?', [frm.doc.total_transactions]),
        function() {
            frappe.call({
                method: 'church.church.doctype.tithe_batch_update.tithe_batch_update.generate_receipts',
                args: {
                    docname: frm.doc.name
                },
                freeze: true,
                freeze_message: __('Generating receipts...'),
                callback: function(r) {
                    if (r.message) {
                        frappe.show_alert({
                            message: r.message.message,
                            indicator: r.message.success ? 'green' : 'orange'
                        });
                        frm.reload_doc();
                    }
                }
            });
        }
    );
}

function download_import_template(frm) {
    frappe.call({
        method: 'church.church.doctype.tithe_batch_update.tithe_batch_update.download_import_template',
        args: {
            branch: frm.doc.branch,
            currency: frm.doc.currency
        },
        callback: function(r) {
            if (r.message) {
                const a = document.createElement('a');
                a.href = 'data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,' + r.message.file_content;
                a.download = r.message.filename;
                a.click();
                
                frappe.show_alert({
                    message: __('Template downloaded successfully'),
                    indicator: 'green'
                });
            }
        }
    });
}

function import_from_excel(frm) {
    new frappe.ui.FileUploader({
        doctype: frm.doctype,
        docname: frm.docname,
        frm: frm,
        allow_multiple: false,
        restrictions: {
            allowed_file_types: ['.xlsx', '.xls']
        },
        on_success: function(file_doc) {
            frappe.call({
                method: 'church.church.doctype.tithe_batch_update.tithe_batch_update.import_from_excel',
                args: {
                    docname: frm.doc.name,
                    file_url: file_doc.file_url
                },
                freeze: true,
                freeze_message: __('Importing transactions...'),
                callback: function(r) {
                    if (r.message) {
                        frappe.show_alert({
                            message: __('Imported {0} transactions successfully', [r.message.imported]),
                            indicator: 'green'
                        });
                        
                        if (r.message.errors && r.message.errors.length > 0) {
                            frappe.msgprint({
                                title: __('Import Warnings'),
                                message: r.message.errors.join('<br>'),
                                indicator: 'orange'
                            });
                        }
                        
                        frm.reload_doc();
                    }
                }
            });
        }
    });
}

function print_collection_report(frm) {
    const print_format = 'Tithe Collection Report';
    frappe.ui.get_print_settings(false, function(print_settings) {
        let w = window.open(
            frappe.urllib.get_full_url(`/api/method/frappe.utils.print_format.download_pdf?doctype=${encodeURIComponent(frm.doctype)}&name=${encodeURIComponent(frm.docname)}&format=${encodeURIComponent(print_format)}&no_letterhead=0`)
        );
        if (!w) {
            frappe.msgprint(__('Please enable pop-ups'));
        }
    });
}

function export_to_excel(frm) {
    frappe.call({
        method: 'church.church.doctype.tithe_batch_update.tithe_batch_update.export_to_excel',
        args: {
            docname: frm.doc.name
        },
        callback: function(r) {
            if (r.message) {
                const a = document.createElement('a');
                a.href = 'data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,' + r.message.file_content;
                a.download = r.message.filename;
                a.click();
                
                frappe.show_alert({
                    message: __('Exported successfully'),
                    indicator: 'green'
                });
            }
        }
    });
}