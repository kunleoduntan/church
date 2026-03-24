# Copyright (c) 2026, kunle and contributors
# For license information, please see license.txt

# Copyright (c) 2026, kunle and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate, today, add_days, nowdate


class Pledges(Document):
    """Pledge DocType Controller — acts as the Pledge Card (commitment record)."""

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    def validate(self):
        self.validate_dates()
        self.validate_amounts()
        self.validate_member_details()
        self.update_description()

    def on_submit(self):
        self.update_redemption_totals()
        self.send_pledge_confirmation_email()

    def on_cancel(self):
        self.update_redemption_totals()

    # ── Validation ─────────────────────────────────────────────────────────────

    def validate_dates(self):
        if self.redemption_date and self.closing_date:
            if getdate(self.closing_date) < getdate(self.redemption_date):
                frappe.throw(_("Expected Completion Date cannot be before Redemption Start Date"))

        if self.pledge_date and getdate(self.pledge_date) > getdate(today()):
            frappe.throw(_("Pledge Date cannot be in the future"))

    def validate_amounts(self):
        if flt(self.amount) <= 0:
            frappe.throw(_("Pledge Amount must be greater than zero"))

    def validate_member_details(self):
        if self.is_a_member == "Yes" and not self.member_id:
            frappe.throw(_("Member ID is required when 'Is a Member' is set to Yes"))

        if self.is_a_member == "No":
            for field in ['first_name', 'last_name', 'phone_no', 'email']:
                if not self.get(field):
                    label = frappe.get_meta("Pledges").get_label(field)
                    frappe.throw(_("{0} is required for non-members").format(label))

    def update_description(self):
        parts = [self.salutation or '', self.first_name or '', self.last_name or '']
        full_name = ' '.join(p for p in parts if p).strip()
        self.description = f"Pledge redemption by {full_name}".strip()

    # ── Totals (called by Pledge Redemption on submit/cancel) ──────────────────

    def update_redemption_totals(self):
        """Recalculate total_redeemed, outstanding_balance, and redemption_status."""
        total_redeemed = frappe.db.sql("""
            SELECT COALESCE(SUM(amount_paid), 0)
            FROM `tabPledge Redemption`
            WHERE pledge_id = %s AND docstatus = 1
        """, self.name)[0][0]

        total_redeemed  = flt(total_redeemed)
        pledge_amount   = flt(self.amount)
        outstanding     = pledge_amount - total_redeemed

        if total_redeemed <= 0:
            status = "Pending"
        elif outstanding <= 0:
            status = "Fully Redeemed"
        else:
            status = "Partially Redeemed"

        frappe.db.set_value("Pledges", self.name, {
            "total_redeemed":    total_redeemed,
            "outstanding_balance": max(outstanding, 0),
            "redemption_status": status
        }, update_modified=False)

        # Reload so the calling context has fresh values
        self.reload()

    # ── Email ──────────────────────────────────────────────────────────────────

    def send_pledge_confirmation_email(self):
        """Send pledge commitment confirmation to pledger."""
        recipient = self.email
        if not recipient:
            return

        full_name = self._get_full_name()
        subject   = f"Your Pledge Commitment — {self.name}"

        message = f"""
        <div style="font-family:'Segoe UI',sans-serif;max-width:600px;margin:auto;padding:32px;background:#f9fafb;border-radius:12px;">
            <div style="background:#1e3a5f;border-radius:8px 8px 0 0;padding:24px 28px;">
                <h2 style="color:#fff;margin:0;font-size:22px;">Pledge Commitment Confirmed</h2>
            </div>
            <div style="background:#fff;border-radius:0 0 8px 8px;padding:28px 28px 24px;border:1px solid #e5e7eb;border-top:none;">
                <p style="font-size:15px;color:#374151;">Dear <strong>{full_name}</strong>,</p>
                <p style="font-size:15px;color:#374151;">
                    Thank you for your generous pledge commitment. We are grateful for your faithfulness and support.
                </p>
                <div style="background:#f0f9ff;border:1px solid #bae6fd;border-radius:8px;padding:16px 20px;margin:20px 0;">
                    <table style="width:100%;font-size:14px;color:#374151;border-collapse:collapse;">
                        <tr><td style="padding:6px 0;color:#6b7280;">Pledge Reference</td><td style="text-align:right;font-weight:700;">{self.name}</td></tr>
                        <tr><td style="padding:6px 0;color:#6b7280;">Programme</td><td style="text-align:right;font-weight:700;">{self.programme}</td></tr>
                        <tr><td style="padding:6px 0;color:#6b7280;">Pledge Amount</td><td style="text-align:right;font-weight:700;">{frappe.format_value(self.amount, {'fieldtype':'Currency'})}</td></tr>
                        <tr><td style="padding:6px 0;color:#6b7280;">Pledge Date</td><td style="text-align:right;font-weight:700;">{self.pledge_date}</td></tr>
                        <tr><td style="padding:6px 0;color:#6b7280;">Expected Completion</td><td style="text-align:right;font-weight:700;">{self.closing_date}</td></tr>
                    </table>
                </div>
                <p style="font-size:14px;color:#6b7280;">
                    Your pledge will be tracked and you will receive confirmation each time a payment is recorded.
                    If you have any questions, please do not hesitate to reach out.
                </p>
                <p style="font-size:14px;color:#374151;margin-top:24px;">God bless you.<br><strong>{self.branch}</strong></p>
            </div>
        </div>
        """

        _send_email(recipient, subject, message)

    def _get_full_name(self):
        parts = [self.salutation or '', self.first_name or '', self.last_name or '']
        return ' '.join(p for p in parts if p).strip()


# ── Scheduler Tasks ────────────────────────────────────────────────────────────

def send_pledge_reminders():
    """
    Called daily by the scheduler.
    Sends reminders 30 days and 7 days before closing_date
    for all submitted, not-fully-redeemed pledges.
    """
    today_date = getdate(today())
    thresholds = [30, 7]

    for days in thresholds:
        target_date = add_days(today_date, days)

        pledges = frappe.get_all("Pledges",
            filters={
                "docstatus": 1,
                "closing_date": target_date,
                "redemption_status": ["in", ["Pending", "Partially Redeemed"]]
            },
            fields=["name", "email", "first_name", "last_name", "salutation",
                    "amount", "outstanding_balance", "closing_date",
                    "programme", "branch"]
        )

        for pledge in pledges:
            if not pledge.email:
                continue

            full_name   = ' '.join(filter(None, [pledge.salutation, pledge.first_name, pledge.last_name]))
            outstanding = flt(pledge.outstanding_balance)
            subject     = f"Pledge Reminder — {days} Days to Completion ({pledge.name})"

            message = f"""
            <div style="font-family:'Segoe UI',sans-serif;max-width:600px;margin:auto;padding:32px;background:#f9fafb;border-radius:12px;">
                <div style="background:#92400e;border-radius:8px 8px 0 0;padding:24px 28px;">
                    <h2 style="color:#fff;margin:0;font-size:22px;">Pledge Completion Reminder</h2>
                    <p style="color:#fde68a;margin:6px 0 0;font-size:14px;">{days} days remaining</p>
                </div>
                <div style="background:#fff;border-radius:0 0 8px 8px;padding:28px 28px 24px;border:1px solid #e5e7eb;border-top:none;">
                    <p style="font-size:15px;color:#374151;">Dear <strong>{full_name}</strong>,</p>
                    <p style="font-size:15px;color:#374151;">
                        This is a friendly reminder that your pledge is due for completion in
                        <strong>{days} day{'s' if days > 1 else ''}</strong>.
                    </p>
                    <div style="background:#fff8e1;border:1px solid #f59e0b;border-radius:8px;padding:16px 20px;margin:20px 0;">
                        <table style="width:100%;font-size:14px;color:#374151;border-collapse:collapse;">
                            <tr><td style="padding:6px 0;color:#6b7280;">Pledge Reference</td><td style="text-align:right;font-weight:700;">{pledge.name}</td></tr>
                            <tr><td style="padding:6px 0;color:#6b7280;">Programme</td><td style="text-align:right;font-weight:700;">{pledge.programme}</td></tr>
                            <tr><td style="padding:6px 0;color:#6b7280;">Outstanding Balance</td><td style="text-align:right;font-weight:700;color:#dc2626;">{frappe.format_value(outstanding, {'fieldtype':'Currency'})}</td></tr>
                            <tr><td style="padding:6px 0;color:#6b7280;">Completion Date</td><td style="text-align:right;font-weight:700;">{pledge.closing_date}</td></tr>
                        </table>
                    </div>
                    <p style="font-size:14px;color:#6b7280;">
                        Please make arrangements to fulfil your pledge before the completion date.
                        Your faithfulness makes a difference.
                    </p>
                    <p style="font-size:14px;color:#374151;margin-top:24px;">God bless you.<br><strong>{pledge.branch}</strong></p>
                </div>
            </div>
            """

            _send_email(pledge.email, subject, message)


# ── Shared Utility ─────────────────────────────────────────────────────────────

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
            title=f"Pledge Email Error — {subject[:60]}"
        )


# ── Whitelisted API ────────────────────────────────────────────────────────────

@frappe.whitelist()
def get_pledge_summary(filters=None):
    """Return summary statistics for pledges (used in reports/dashboards)."""
    filters = frappe.parse_json(filters) if filters else {}

    conditions, values = [], {}

    if filters.get('branch'):
        conditions.append('branch = %(branch)s')
        values['branch'] = filters['branch']
    if filters.get('programme'):
        conditions.append('programme = %(programme)s')
        values['programme'] = filters['programme']
    if filters.get('from_date'):
        conditions.append('pledge_date >= %(from_date)s')
        values['from_date'] = filters['from_date']
    if filters.get('to_date'):
        conditions.append('pledge_date <= %(to_date)s')
        values['to_date'] = filters['to_date']

    where_clause = ' AND '.join(conditions) if conditions else '1=1'

    result = frappe.db.sql(f"""
        SELECT
            COUNT(*)                    AS total_pledges,
            SUM(amount)                 AS total_pledged,
            SUM(total_redeemed)         AS total_redeemed,
            SUM(outstanding_balance)    AS total_outstanding,
            AVG(amount)                 AS average_pledge
        FROM `tabPledges`
        WHERE {where_clause} AND docstatus = 1
    """, values=values, as_dict=True)

    return result[0] if result else {}