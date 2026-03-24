// Copyright (c) 2026, kunle and contributors
// For license information, please see license.txt

// Copyright (c) 2026, kunle and contributors
// For license information, please see license.txt

frappe.ui.form.on('Pledge Redemption', {

    // ── On load & refresh ────────────────────────────────────────────────────

    onload: function(frm) {
        if (frm.doc.pledge_id && !frm.doc.__islocal) {
            load_outstanding(frm);
        }
    },

    refresh: function(frm) {
        if (frm.doc.pledge_id) {
            load_outstanding(frm);
        }

        // Show a clear status banner on submitted docs
        if (frm.doc.docstatus === 1) {
            frm.dashboard.set_headline_alert(
                `<span style="color:#16a34a;font-weight:600;">✔ Payment Submitted — Receipt Created</span>`
            );
        }
    },

    // ── Pledge selected ──────────────────────────────────────────────────────

    pledge_id: function(frm) {
        if (!frm.doc.pledge_id) {
            frm.set_value('current_outstanding', 0);
            frm.set_value('pledge_amount', 0);
            return;
        }

        // Small delay to allow fetch_from fields to populate
        setTimeout(() => load_outstanding(frm), 600);
    },

    // ── Live over-payment guard ───────────────────────────────────────────────

    amount_paid: function(frm) {
        const outstanding = flt(frm.doc.current_outstanding);
        const paying      = flt(frm.doc.amount_paid);

        if (outstanding > 0 && paying > outstanding) {
            frappe.msgprint({
                title: __('Amount Exceeds Balance'),
                indicator: 'red',
                message: __(
                    'The amount you are paying ({0}) exceeds the outstanding balance ({1}). Please correct the amount.',
                    [
                        format_currency(paying,      frm.doc.currency),
                        format_currency(outstanding, frm.doc.currency)
                    ]
                )
            });
            frm.set_value('amount_paid', outstanding);
        }
    }
});

// ── Helpers ───────────────────────────────────────────────────────────────────

/**
 * Fetch the current outstanding balance from the server
 * (server is authoritative — avoids stale client-side values)
 */
function load_outstanding(frm) {
    if (!frm.doc.pledge_id) return;

    frappe.call({
        method: 'church.church.doctype.pledge_redemption.pledge_redemption.get_outstanding_balance',
        args: { pledge_id: frm.doc.pledge_id },
        callback: function(r) {
            if (r.message !== undefined) {
                frm.set_value('current_outstanding', flt(r.message));
            }
        }
    });
}

function format_currency(value, currency) {
    return frappe.format(value, { fieldtype: 'Currency', currency: currency });
}