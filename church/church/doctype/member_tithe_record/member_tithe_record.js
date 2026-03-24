// Copyright (c) 2026, Kunle and contributors
// For license information, please see license.txt

// Copyright (c) 2026, Kunle and contributors
// For license information, please see license.txt

frappe.ui.form.on("Member Tithe Record", {
    refresh: function(frm) {
        // Setup all buttons and features
        setup_custom_buttons(frm);
        setup_print_buttons(frm);
        apply_table_styling(frm);
        set_field_properties(frm);
        
        // REMOVED: Auto-sync on refresh (causes infinite loop)
        // Only sync manually via button or on specific events
    },
    
    onload: function(frm) {
        // Auto-sync only ONCE when form first loads
        if (!frm.is_new() && !frm.__synced) {
            frm.__synced = true;  // Flag to prevent repeated syncs
            auto_sync_tithe_payments(frm);
        }
    },
    
    member_id: function(frm) {
        // Auto-fetch member details when member is selected
        if (frm.doc.member_id) {
            fetch_member_details(frm);
        }
    },
    
    before_save: function(frm) {
        // Recalculate totals before saving
        calculate_totals(frm);
    },
    
    branch: function(frm) {
        // Update branch for all child table entries
        if (frm.doc.branch && frm.doc.tithe_payment_schedule) {
            frm.doc.tithe_payment_schedule.forEach(row => {
                frappe.model.set_value(row.doctype, row.name, "branch", frm.doc.branch);
            });
            frm.refresh_field('tithe_payment_schedule');
        }
    }
});


// ========================================
// CHILD TABLE: Tithe Payment Schedule
// ========================================

frappe.ui.form.on("Tithe Payment Schedule", {
    exchange_rate: function(frm, cdt, cdn) {
        calculate_amount_in_lc(frm, cdt, cdn);
    },
    
    amount_paid: function(frm, cdt, cdn) {
        calculate_amount_in_lc(frm, cdt, cdn);
    },
    
    currency: function(frm, cdt, cdn) {
        // When currency changes, update exchange rate
        let row = frappe.get_doc(cdt, cdn);
        
        if (row.currency === "NGN") {
            frappe.model.set_value(cdt, cdn, 'exchange_rate', 1.0);
        }
    },
    
    receipt_no: function(frm, cdt, cdn) {
        // When receipt number is entered, fetch receipt details
        let row = frappe.get_doc(cdt, cdn);
        
        if (row.receipt_no) {
            fetch_receipt_details(frm, cdt, cdn, row.receipt_no);
        }
    },
    
    tithe_payment_schedule_remove: function(frm) {
        // Recalculate totals when a row is removed
        calculate_totals(frm);
    }
});


// ========================================
// BUTTON SETUP FUNCTIONS
// ========================================

function setup_custom_buttons(frm) {
    /**
     * Setup action buttons for tithe record management
     */
    if (!frm.is_new()) {
        // Sync button
        frm.add_custom_button(__('Sync Tithe Payments'), function() {
            sync_tithe_payments(frm);
        }, __('Actions'));
        
        // View Member button
        frm.add_custom_button(__('View Member'), function() {
            frappe.set_route('Form', 'Member', frm.doc.member_id);
        }, __('Actions'));
    }
    
    // Make amount_paid read-only (auto-calculated)
    frm.set_df_property('amount_paid', 'read_only', 1);
}


function setup_print_buttons(frm) {
    /**
     * Setup print-related buttons
     */
    if (!frm.is_new()) {
        frm.add_custom_button(__('Print Tithe Card'), function() {
            print_tithe_card(frm);
        }, __('Print'));
        
        frm.add_custom_button(__('Email Statement'), function() {
            email_tithe_statement(frm);
        }, __('Print'));
        
        frm.add_custom_button(__('Download PDF'), function() {
            download_tithe_pdf(frm);
        }, __('Print'));
        
        frm.add_custom_button(__('Preview Card'), function() {
            preview_tithe_card(frm);
        }, __('Print'));
    }
}


// ========================================
// SYNC FUNCTIONS
// ========================================

function auto_sync_tithe_payments(frm) {
    /**
     * Automatically sync tithe payments when form is FIRST loaded.
     * Silent operation - no reload to prevent infinite loop.
     */
    if (!frm.doc.member_id) return;
    
    // Silent sync without reload
    frappe.call({
        method: "church.church.doctype.member_tithe_record.member_tithe_record.sync_tithe_payments",
        args: {
            member_tithe_record_name: frm.doc.name
        },
        callback: function(r) {
            if (r.message && r.message.success) {
                // Just refresh fields, don't reload entire document
                frm.refresh_fields();
            }
        }
    });
}


function sync_tithe_payments(frm) {
    /**
     * Manually sync tithe payments with user feedback.
     * Called from the "Sync Tithe Payments" button.
     */
    frappe.show_alert({
        message: __('Syncing tithe payments...'),
        indicator: 'blue'
    });
    
    frappe.call({
        method: "church.church.doctype.member_tithe_record.member_tithe_record.sync_tithe_payments",
        args: {
            member_tithe_record_name: frm.doc.name
        },
        freeze: true,
        freeze_message: __('Updating tithe record...'),
        callback: function(r) {
            if (r.message && r.message.success) {
                frappe.show_alert({
                    message: r.message.message,
                    indicator: 'green'
                }, 5);
                // Reload document to show updates
                frm.reload_doc();
            }
        },
        error: function(r) {
            frappe.show_alert({
                message: __('Error syncing tithe payments'),
                indicator: 'red'
            }, 5);
        }
    });
}


// ========================================
// DATA FETCHING FUNCTIONS
// ========================================

function fetch_member_details(frm) {
    /**
     * Fetch and populate member details from Member doctype.
     */
    frappe.db.get_value('Member', frm.doc.member_id, 
        ['full_name', 'salutation', 'branch'],
        (r) => {
            if (r) {
                frm.set_value('full_name', r.full_name);
                frm.set_value('salutation', r.salutation);
                if (!frm.doc.branch) {
                    frm.set_value('branch', r.branch);
                }
            }
        }
    );
}


function fetch_receipt_details(frm, cdt, cdn, receipt_no) {
    /**
     * Fetch and populate details from Receipt.
     */
    frappe.db.get_value('Receipts', receipt_no,
        [
            'transaction_date', 'member_full_name', 'remittance_bank',
            'branch', 'receipt_currency', 'exchange_rate', 
            'amount_paid', 'amount_paid_in_fc'
        ],
        (r) => {
            if (r) {
                let currency = r.receipt_currency || 'NGN';
                let is_local = currency === 'NGN';
                let amount = is_local ? r.amount_paid : r.amount_paid_in_fc;
                let rate = is_local ? 1.0 : (r.exchange_rate || 1.0);
                
                frappe.model.set_value(cdt, cdn, 'date', r.transaction_date);
                frappe.model.set_value(cdt, cdn, 'full_name', r.member_full_name);
                frappe.model.set_value(cdt, cdn, 'designated_bank_acct', r.remittance_bank);
                frappe.model.set_value(cdt, cdn, 'branch', r.branch);
                frappe.model.set_value(cdt, cdn, 'currency', currency);
                frappe.model.set_value(cdt, cdn, 'exchange_rate', rate);
                frappe.model.set_value(cdt, cdn, 'amount_paid', amount);
                frappe.model.set_value(cdt, cdn, 'amount_in_lc', flt(amount * rate, 2));
            }
        }
    );
}


// ========================================
// CALCULATION FUNCTIONS
// ========================================

function calculate_amount_in_lc(frm, cdt, cdn) {
    /**
     * Calculate amount in local currency for a child table row.
     */
    let row = frappe.get_doc(cdt, cdn);
    
    let amount_paid = flt(row.amount_paid || 0);
    let exchange_rate = flt(row.exchange_rate || 1);
    let amount_in_lc = flt(amount_paid * exchange_rate, 2);
    
    frappe.model.set_value(cdt, cdn, 'amount_in_lc', amount_in_lc);
    
    // Recalculate parent total
    calculate_totals(frm);
}


function calculate_totals(frm) {
    /**
     * Calculate total amount paid from all payment schedules.
     */
    let total = 0;
    
    if (frm.doc.tithe_payment_schedule) {
        frm.doc.tithe_payment_schedule.forEach(row => {
            // Ensure amount_in_lc is calculated
            if (row.amount_paid && row.exchange_rate) {
                row.amount_in_lc = flt(row.amount_paid * row.exchange_rate, 2);
            }
            total += flt(row.amount_in_lc || 0);
        });
    }
    
    frm.set_value('amount_paid', flt(total, 2));
    frm.refresh_field('tithe_payment_schedule');
}


// ========================================
// UI ENHANCEMENT FUNCTIONS
// ========================================

function apply_table_styling(frm) {
    /**
     * Apply alternating row colors for better readability.
     */
    setTimeout(() => {
        frm.fields_dict.tithe_payment_schedule.grid.wrapper
            .find('.grid-row')
            .each(function(i, row) {
                if (i % 2 === 0) {
                    $(row).css('background-color', '#ffffff');
                } else {
                    $(row).css('background-color', '#f8f9fa');
                }
            });
    }, 500);
}


function set_field_properties(frm) {
    /**
     * Set field properties for better UX.
     */
    // Make calculated fields read-only
    frm.set_df_property('amount_paid', 'read_only', 1);
    
    // Make fetched fields read-only
    frm.set_df_property('full_name', 'read_only', 1);
    frm.set_df_property('salutation', 'read_only', 1);
}


// ========================================
// PRINT FUNCTIONS
// ========================================

function print_tithe_card(frm) {
    /**
     * Print the tithe card using browser print
     */
    frappe.show_alert({
        message: __('Preparing tithe card for printing...'),
        indicator: 'blue'
    });
    
    frappe.call({
        method: 'church.church.doctype.member_tithe_record.member_tithe_card_print_format.get_tithe_card_data',
        args: {
            member_tithe_record_name: frm.doc.name
        },
        callback: function(r) {
            if (r.message) {
                open_print_window(r.message);
            }
        }
    });
}


function open_print_window(data) {
    /**
     * Open a new window with the tithe card and trigger print
     */
    const print_window = window.open('', '_blank');
    
    const html = generate_print_html(data);
    
    print_window.document.write(html);
    print_window.document.close();
    
    // Wait for content to load, then print
    print_window.onload = function() {
        setTimeout(() => {
            print_window.print();
        }, 500);
    };
}


function generate_print_html(data) {
    /**
     * Generate HTML for printing
     */
    const payments_html = data.recent_payments.map(payment => `
        <tr>
            <td>${payment.date}</td>
            <td><span class="receipt-badge">${payment.receipt_no}</span></td>
            <td>${payment.currency}</td>
            <td style="font-weight: 700; color: #667eea;">${payment.amount}</td>
        </tr>
    `).join('');
    
    return `
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Tithe Card - ${data.full_name}</title>
        <link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;600;700&family=Lato:wght@300;400;700&display=swap" rel="stylesheet">
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { font-family: 'Lato', sans-serif; padding: 20px; }
            .card-container { max-width: 900px; margin: 0 auto; border: 2px solid #e0e0e0; border-radius: 16px; overflow: hidden; }
            .card-header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 40px; position: relative; overflow: hidden; }
            .card-header::before { content: ''; position: absolute; top: -50%; right: -10%; width: 400px; height: 400px; background: rgba(255,255,255,0.1); border-radius: 50%; }
            .church-logo { width: 80px; height: 80px; background: white; border-radius: 50%; display: flex; align-items: center; justify-content: center; margin: 0 auto 20px; position: relative; z-index: 1; }
            .church-logo svg { width: 50px; height: 50px; fill: #667eea; }
            .header-title { text-align: center; color: white; position: relative; z-index: 1; }
            .header-title h1 { font-family: 'Playfair Display', serif; font-size: 32px; font-weight: 700; margin-bottom: 8px; }
            .header-title p { font-size: 16px; opacity: 0.95; letter-spacing: 1px; }
            .card-body { padding: 40px; }
            .member-info { display: grid; grid-template-columns: 1fr 1fr; gap: 25px; margin-bottom: 35px; padding-bottom: 35px; border-bottom: 2px solid #f0f0f0; }
            .info-label { font-size: 11px; text-transform: uppercase; letter-spacing: 1.5px; color: #999; margin-bottom: 6px; font-weight: 600; }
            .info-value { font-size: 18px; color: #333; font-weight: 600; }
            .stats-row { display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; margin-bottom: 30px; }
            .stat-card { background: #f8f9ff; padding: 20px; border-radius: 12px; border: 2px solid #e8ebff; text-align: center; }
            .stat-number { font-size: 24px; font-weight: 700; color: #667eea; margin-bottom: 5px; }
            .stat-label { font-size: 10px; text-transform: uppercase; letter-spacing: 1px; color: #999; font-weight: 600; }
            .total-section { background: linear-gradient(135deg, #f8f9ff 0%, #f0f2ff 100%); padding: 30px; border-radius: 16px; margin-bottom: 30px; border: 2px solid #e8ebff; text-align: center; }
            .total-label { font-size: 13px; color: #667eea; text-transform: uppercase; letter-spacing: 2px; margin-bottom: 10px; font-weight: 700; }
            .total-amount { font-size: 42px; font-weight: 700; color: #667eea; font-family: 'Playfair Display', serif; }
            .history-header { font-size: 16px; font-weight: 700; color: #333; margin-bottom: 15px; padding-left: 15px; border-left: 4px solid #667eea; }
            .history-table { width: 100%; border-collapse: collapse; }
            .history-table thead th { text-align: left; font-size: 10px; text-transform: uppercase; letter-spacing: 1.5px; color: #999; font-weight: 700; padding: 12px 10px; border-bottom: 2px solid #e0e0e0; }
            .history-table tbody td { padding: 14px 10px; color: #333; font-size: 13px; border-bottom: 1px solid #f0f0f0; }
            .history-table tbody tr:nth-child(even) { background: #f8f9fa; }
            .receipt-badge { display: inline-block; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 3px 10px; border-radius: 15px; font-size: 10px; font-weight: 600; }
            .card-footer { background: #f8f9fa; padding: 30px; text-align: center; border-top: 2px solid #e0e0e0; }
            .footer-text { color: #666; font-size: 12px; line-height: 1.8; margin-bottom: 12px; }
            .footer-verse { font-style: italic; color: #667eea; font-size: 13px; font-weight: 600; font-family: 'Playfair Display', serif; }
            @media print { body { padding: 0; } .card-container { border: none; } }
        </style>
    </head>
    <body>
        <div class="card-container">
            <div class="card-header">
                <div class="church-logo">
                    <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                        <path d="M12 2L4 7v6.5C4 19 8 22 12 22s8-3 8-8.5V7l-8-5zm0 2.18l6 3.75v5.57c0 3.9-3.13 6.5-6 6.5s-6-2.6-6-6.5V7.93l6-3.75zM11 8v3H8v2h3v3h2v-3h3v-2h-3V8h-2z"/>
                    </svg>
                </div>
                <div class="header-title">
                    <h1>${data.company_name}</h1>
                    <p>Member Tithe Record Certificate</p>
                </div>
            </div>
            <div class="card-body">
                <div class="member-info">
                    <div><div class="info-label">Member ID</div><div class="info-value">${data.member_id}</div></div>
                    <div><div class="info-label">Full Name</div><div class="info-value">${data.salutation} ${data.full_name}</div></div>
                    <div><div class="info-label">Branch</div><div class="info-value">${data.branch}</div></div>
                    <div><div class="info-label">Record Date</div><div class="info-value">${data.record_date}</div></div>
                </div>
                <div class="stats-row">
                    <div class="stat-card"><div class="stat-number">${data.total_payments}</div><div class="stat-label">Total Payments</div></div>
                    <div class="stat-card"><div class="stat-number">${data.avg_payment}</div><div class="stat-label">Average Payment</div></div>
                    <div class="stat-card"><div class="stat-number">${data.last_payment_date}</div><div class="stat-label">Last Payment</div></div>
                </div>
                <div class="total-section">
                    <div class="total-label">Total Tithe Contributed</div>
                    <div class="total-amount">${data.total_amount}</div>
                </div>
                <div class="payment-history">
                    <div class="history-header">Recent Payment History</div>
                    <table class="history-table">
                        <thead><tr><th>Date</th><th>Receipt No</th><th>Currency</th><th>Amount</th></tr></thead>
                        <tbody>${payments_html}</tbody>
                    </table>
                </div>
            </div>
            <div class="card-footer">
                <div class="footer-text">
                    Thank you for your faithful giving and commitment to the work of God's kingdom.<br>
                    Your contributions support our mission and ministry initiatives.
                </div>
                <div class="footer-verse">"Each of you should give what you have decided in your heart to give" - 2 Corinthians 9:7</div>
            </div>
        </div>
    </body>
    </html>`;
}


function email_tithe_statement(frm) {
    /**
     * Email the tithe statement to member
     */
    const d = new frappe.ui.Dialog({
        title: __('Email Tithe Statement'),
        fields: [
            {
                label: __('Recipient Email'),
                fieldname: 'email',
                fieldtype: 'Data',
                reqd: 1,
                description: __('Leave blank to use member\'s email address')
            },
            {
                label: __('Send Copy to Me'),
                fieldname: 'send_copy',
                fieldtype: 'Check',
                default: 0
            }
        ],
        primary_action_label: __('Send Email'),
        primary_action: function(values) {
            frappe.call({
                method: 'church.church.doctype.member_tithe_record.member_tithe_card_print_format.email_tithe_statement',
                args: {
                    member_tithe_record_name: frm.doc.name,
                    recipient_email: values.email || null
                },
                freeze: true,
                freeze_message: __('Sending email...'),
                callback: function(r) {
                    if (!r.exc) {
                        frappe.show_alert({
                            message: __('Email sent successfully!'),
                            indicator: 'green'
                        }, 5);
                        d.hide();
                    }
                }
            });
        }
    });
    
    d.show();
}


function download_tithe_pdf(frm) {
    /**
     * Download tithe card as PDF
     */
    frappe.show_alert({
        message: __('Generating PDF...'),
        indicator: 'blue'
    });
    
    frappe.call({
        method: 'church.church.doctype.member_tithe_record.member_tithe_card_print_format.generate_tithe_statement_pdf',
        args: {
            member_tithe_record_name: frm.doc.name
        },
        freeze: true,
        freeze_message: __('Generating PDF...'),
        callback: function(r) {
            if (r.message) {
                // Open PDF in new tab
                window.open(r.message, '_blank');
                frappe.show_alert({
                    message: __('PDF generated successfully!'),
                    indicator: 'green'
                }, 5);
            }
        }
    });
}


function preview_tithe_card(frm) {
    /**
     * Preview tithe card in modal dialog
     */
    frappe.call({
        method: 'church.church.doctype.member_tithe_record.member_tithe_card_print_format.get_tithe_card_data',
        args: {
            member_tithe_record_name: frm.doc.name
        },
        callback: function(r) {
            if (r.message) {
                show_preview_dialog(r.message);
            }
        }
    });
}


function show_preview_dialog(data) {
    /**
     * Show preview in a dialog
     */
    const html = generate_print_html(data);
    
    const d = new frappe.ui.Dialog({
        title: __('Tithe Card Preview'),
        size: 'extra-large',
        fields: [
            {
                fieldtype: 'HTML',
                fieldname: 'preview_html'
            }
        ],
        primary_action_label: __('Print'),
        primary_action: function() {
            open_print_window(data);
            d.hide();
        }
    });
    
    d.fields_dict.preview_html.$wrapper.html(`
        <div style="max-height: 70vh; overflow-y: auto;">
            ${html}
        </div>
    `);
    
    d.show();
}