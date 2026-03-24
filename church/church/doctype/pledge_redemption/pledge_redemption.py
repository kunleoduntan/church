# Copyright (c) 2026, kunle and contributors
# For license information, please see license.txt

# Copyright (c) 2026, kunle and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate, today


class PledgeRedemption(Document):
    """
    Pledge Redemption — records a single payment against a Pledge Card (Pledges).
    On submit  → validates balance, creates Receipt, updates Pledge totals, sends email.
    On cancel  → updates Pledge totals, sends cancellation note.
    """

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    def validate(self):
        self.validate_pledge_submitted()
        self.load_outstanding()
        self.validate_amount()
        self.validate_payment_date()

    def on_submit(self):
        self.create_receipt()
        self._update_pledge_totals()
        self.send_payment_email()

    def on_cancel(self):
        self._update_pledge_totals()

    # ── Validation ─────────────────────────────────────────────────────────────

    def validate_pledge_submitted(self):
        status = frappe.db.get_value("Pledges", self.pledge_id, "docstatus")
        if status != 1:
            frappe.throw(_("You can only redeem against a submitted Pledge. {0} is not submitted.").format(self.pledge_id))

    def load_outstanding(self):
        """Set current_outstanding from the authoritative server-side calculation."""
        self.current_outstanding = flt(get_outstanding_balance(self.pledge_id))

    def validate_amount(self):
        if flt(self.amount_paid) <= 0:
            frappe.throw(_("Amount Paying must be greater than zero"))

        if flt(self.amount_paid) > flt(self.current_outstanding):
            frappe.throw(
                _("Payment amount ({0}) cannot exceed the outstanding balance ({1}) on pledge {2}.").format(
                    frappe.format_value(self.amount_paid,          {'fieldtype': 'Currency'}),
                    frappe.format_value(self.current_outstanding,  {'fieldtype': 'Currency'}),
                    self.pledge_id
                )
            )

    def validate_payment_date(self):
        if self.payment_date and getdate(self.payment_date) > getdate(today()):
            frappe.throw(_("Payment Date cannot be in the future"))

    # ── Receipt Creation ───────────────────────────────────────────────────────

    def create_receipt(self):
        """Create a Receipt document linked to this redemption."""
        if frappe.db.exists("Receipts", {"referenced_document_no": self.name}):
            frappe.msgprint(_("Receipt for {0} already exists").format(self.name))
            return

        try:
            receipt = frappe.new_doc("Receipts")
            receipt.naming_series          = 'REC #-'
            receipt.received_from          = self.pledger_name or ''
            receipt.transaction_date       = self.payment_date
            receipt.transaction_type       = 'Revenue'
            receipt.branch                 = self.branch
            receipt.create_accounting_entries = 1
            receipt.transaction_purposes   = (
                self.notes or
                f"Pledge redemption — {self.pledge_id}"
            )
            receipt.receipt_currency       = self.currency
            receipt.exchange_rate          = flt(self.exchange_rate) if self.currency != "NGN" else 1.0

            if self.currency == 'NGN':
                receipt.amount_paid        = flt(self.amount_paid)
                receipt.amount_paid_in_fc  = 0
            else:
                receipt.amount_paid        = 0
                receipt.amount_paid_in_fc  = flt(self.amount_paid)

            receipt.mode_of_payment        = self.mode_of_payment or "Wire Transfer"
            receipt.reference_no           = self.reference_no or self.name.upper()
            receipt.referenced_document_no = self.name.upper()
            receipt.remittance_bank        = self.designated_bank_acct

            receipt.flags.ignore_permissions = True
            receipt.flags.ignore_mandatory   = True
            receipt.insert()

            frappe.msgprint(
                _("Receipt {0} created successfully for {1}").format(
                    frappe.bold(receipt.name),
                    frappe.bold(self.name)
                ),
                indicator='green'
            )

        except Exception as e:
            frappe.log_error(
                message=frappe.get_traceback(),
                title=f"Pledge Redemption Receipt Error — {self.name}"
            )
            frappe.throw(_("Error creating receipt: {0}").format(str(e)))

    # ── Update parent pledge ───────────────────────────────────────────────────

    def _update_pledge_totals(self):
        pledge = frappe.get_doc("Pledges", self.pledge_id)
        pledge.update_redemption_totals()

    # ── Emails ─────────────────────────────────────────────────────────────────

    def send_payment_email(self):
        pledge     = frappe.get_doc("Pledges", self.pledge_id)
        recipient  = pledge.email
        if not recipient:
            return

        full_name   = pledge._get_full_name()
        outstanding = flt(pledge.outstanding_balance)
        status      = pledge.redemption_status

        if status == "Fully Redeemed":
            self._send_full_redemption_email(recipient, full_name, pledge)
        else:
            self._send_partial_redemption_email(recipient, full_name, pledge, outstanding)

    def _send_partial_redemption_email(self, recipient, full_name, pledge, outstanding):
        subject = f"Payment Received — Pledge {self.pledge_id}"

        message = f"""
        <div style="font-family:'Segoe UI',sans-serif;max-width:600px;margin:auto;padding:32px;background:#f9fafb;border-radius:12px;">
            <div style="background:#1e3a5f;border-radius:8px 8px 0 0;padding:24px 28px;">
                <h2 style="color:#fff;margin:0;font-size:22px;">Payment Received</h2>
                <p style="color:#bfdbfe;margin:6px 0 0;font-size:14px;">Reference: {self.name}</p>
            </div>
            <div style="background:#fff;border-radius:0 0 8px 8px;padding:28px 28px 24px;border:1px solid #e5e7eb;border-top:none;">
                <p style="font-size:15px;color:#374151;">Dear <strong>{full_name}</strong>,</p>
                <p style="font-size:15px;color:#374151;">
                    We have received your pledge payment. Thank you for your continued faithfulness.
                </p>
                <div style="background:#f0f9ff;border:1px solid #bae6fd;border-radius:8px;padding:16px 20px;margin:20px 0;">
                    <table style="width:100%;font-size:14px;color:#374151;border-collapse:collapse;">
                        <tr><td style="padding:6px 0;color:#6b7280;">Redemption Ref</td><td style="text-align:right;font-weight:700;">{self.name}</td></tr>
                        <tr><td style="padding:6px 0;color:#6b7280;">Pledge Reference</td><td style="text-align:right;font-weight:700;">{self.pledge_id}</td></tr>
                        <tr><td style="padding:6px 0;color:#6b7280;">Programme</td><td style="text-align:right;font-weight:700;">{pledge.programme}</td></tr>
                        <tr><td style="padding:6px 0;color:#6b7280;">Amount Paid</td><td style="text-align:right;font-weight:700;color:#16a34a;">{frappe.format_value(self.amount_paid, {'fieldtype':'Currency'})}</td></tr>
                        <tr><td style="padding:6px 0;color:#6b7280;">Payment Date</td><td style="text-align:right;font-weight:700;">{self.payment_date}</td></tr>
                        <tr style="border-top:1px solid #e5e7eb;">
                            <td style="padding:10px 0 4px;color:#6b7280;font-weight:700;">Outstanding Balance</td>
                            <td style="text-align:right;font-weight:700;color:#dc2626;font-size:16px;">{frappe.format_value(outstanding, {'fieldtype':'Currency'})}</td>
                        </tr>
                    </table>
                </div>
                <div style="background:#fff8e1;border-left:4px solid #f59e0b;padding:12px 16px;border-radius:0 6px 6px 0;margin-bottom:20px;">
                    <p style="margin:0;font-size:13px;color:#92400e;">
                        You have an outstanding balance of <strong>{frappe.format_value(outstanding, {'fieldtype':'Currency'})}</strong>
                        on your pledge. Please ensure this is completed by <strong>{pledge.closing_date}</strong>.
                    </p>
                </div>
                <p style="font-size:14px;color:#374151;margin-top:24px;">God bless you.<br><strong>{pledge.branch}</strong></p>
            </div>
        </div>
        """

        _send_email(recipient, subject, message)

    def _send_full_redemption_email(self, recipient, full_name, pledge):
        subject = f"Pledge Fully Redeemed — {self.pledge_id} 🎉"

        message = f"""
        <div style="font-family:'Segoe UI',sans-serif;max-width:600px;margin:auto;padding:32px;background:#f9fafb;border-radius:12px;">
            <div style="background:linear-gradient(135deg,#14532d,#16a34a);border-radius:8px 8px 0 0;padding:24px 28px;">
                <h2 style="color:#fff;margin:0;font-size:22px;">🎉 Pledge Fully Redeemed!</h2>
                <p style="color:#bbf7d0;margin:6px 0 0;font-size:14px;">Congratulations on completing your pledge</p>
            </div>
            <div style="background:#fff;border-radius:0 0 8px 8px;padding:28px 28px 24px;border:1px solid #e5e7eb;border-top:none;">
                <p style="font-size:15px;color:#374151;">Dear <strong>{full_name}</strong>,</p>
                <p style="font-size:16px;color:#374151;line-height:1.6;">
                    We are delighted to inform you that your pledge has been <strong style="color:#16a34a;">fully redeemed</strong>.
                    Your faithfulness and generosity towards <strong>{pledge.programme}</strong> is a blessing to this church and community.
                </p>
                <div style="background:#dcfce7;border:1px solid #86efac;border-radius:8px;padding:16px 20px;margin:20px 0;text-align:center;">
                    <div style="font-size:13px;color:#166534;margin-bottom:8px;text-transform:uppercase;font-weight:600;letter-spacing:0.05em;">Total Pledge Fulfilled</div>
                    <div style="font-size:32px;font-weight:800;color:#14532d;">{frappe.format_value(pledge.amount, {'fieldtype':'Currency'})}</div>
                    <div style="font-size:12px;color:#16a34a;margin-top:4px;">Pledge Ref: {self.pledge_id}</div>
                </div>
                <p style="font-size:14px;color:#6b7280;text-align:center;font-style:italic;">
                    "Each of you should give what you have decided in your heart to give, not reluctantly or under compulsion,
                    for God loves a cheerful giver." — 2 Corinthians 9:7
                </p>
                <p style="font-size:14px;color:#374151;margin-top:24px;">
                    With gratitude,<br><strong>{pledge.branch}</strong>
                </p>
            </div>
        </div>
        """

        _send_email(recipient, subject, message)


# ── Whitelisted API ────────────────────────────────────────────────────────────

@frappe.whitelist()
def get_outstanding_balance(pledge_id):
    """
    Return the current outstanding balance for a pledge.
    = pledge.amount  minus  SUM of all submitted Pledge Redemptions for that pledge.
    """
    pledge_amount = flt(frappe.db.get_value("Pledges", pledge_id, "amount"))

    total_redeemed = frappe.db.sql("""
        SELECT COALESCE(SUM(amount_paid), 0)
        FROM `tabPledge Redemption`
        WHERE pledge_id = %s AND docstatus = 1
    """, pledge_id)[0][0]

    outstanding = pledge_amount - flt(total_redeemed)
    return max(outstanding, 0)


# ── Shared utility (imported by pledges.py too) ────────────────────────────────

def _send_email(recipient, subject, message):
    try:
        frappe.sendmail(
            recipients=[recipient],
            subject=subject,
            message=message,
            now=True
        )
    except Exception:
        frappe.log_error(
            message=frappe.get_traceback(),
            title=f"Pledge Redemption Email Error — {subject[:60]}"
        )