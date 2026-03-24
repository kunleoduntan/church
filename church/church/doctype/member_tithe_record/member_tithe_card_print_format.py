# Copyright (c) 2026, Kunle and contributors
# For license information, please see license.txt

# Copyright (c) 2026, Kunle and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.utils import flt, formatdate, fmt_money


@frappe.whitelist()
def get_tithe_card_data(member_tithe_record_name):
    """
    Fetch all data needed for the tithe card.
    Called from JavaScript to populate the print card.
    """
    try:
        # Get the Member Tithe Record document
        doc = frappe.get_doc("Member Tithe Record", member_tithe_record_name)
        
        # Get member details (email and phone)
        member = frappe.db.get_value(
            "Member",
            doc.member_id,
            ["email", "mobile_phone"],
            as_dict=True
        ) or {}
        
        # Get payments from child table
        payments = doc.tithe_payment_schedule or []
        total_payments = len(payments)
        
        # Calculate statistics
        avg_payment = 0
        last_payment_date = None
        
        if total_payments > 0:
            avg_payment = flt(doc.amount_paid / total_payments, 2)
            # Get the most recent payment date
            sorted_payments = sorted(payments, key=lambda x: x.date, reverse=True)
            last_payment_date = sorted_payments[0].date if sorted_payments else None
        
        # Build recent payments list (last 10)
        recent_payments = []
        sorted_payments = sorted(payments, key=lambda x: x.date, reverse=True)
        
        for payment in sorted_payments[:10]:
            recent_payments.append({
                "date": formatdate(payment.date, "dd MMM yyyy"),
                "receipt_no": payment.receipt_no or "N/A",
                "currency": payment.currency or "NGN",
                "amount": fmt_money(payment.amount_in_lc or 0, currency="NGN")
            })
        
        # Get company/church name
        company = frappe.defaults.get_defaults().get("company")
        company_name = company or "Ecclesia Church"
        
        # Build and return data dictionary
        return {
            "member_id": doc.member_id or "",
            "full_name": doc.full_name or "",
            "salutation": doc.salutation or "",
            "branch": doc.branch or "Main Branch",
            "total_amount": fmt_money(doc.amount_paid or 0, currency="NGN"),
            "total_amount_raw": flt(doc.amount_paid or 0, 2),
            "currency": doc.currency or "NGN",
            "total_payments": total_payments,
            "avg_payment": fmt_money(avg_payment, currency="NGN"),
            "last_payment_date": formatdate(last_payment_date, "MMM yyyy") if last_payment_date else "N/A",
            "record_date": formatdate(frappe.utils.today(), "MMMM dd, yyyy"),
            "recent_payments": recent_payments,
            "company_name": company_name,
            "member_email": member.get("email") or "",
            "member_phone": member.get("mobile_phone") or ""
        }
    
    except Exception as e:
        frappe.log_error(f"Error in get_tithe_card_data: {str(e)}", "Tithe Card Data Error")
        frappe.throw(_("Error fetching tithe card data: {0}").format(str(e)))


@frappe.whitelist()
def generate_tithe_statement_pdf(member_tithe_record_name):
    """
    Generate PDF statement for member tithe record.
    Returns the file URL of the generated PDF.
    """
    try:
        from frappe.utils.pdf import get_pdf
        
        # Get card data
        data = get_tithe_card_data(member_tithe_record_name)
        
        # Generate HTML
        html = generate_print_html(data)
        
        # Generate PDF
        pdf = get_pdf(html)
        
        # Create file name
        file_name = f"Tithe_Statement_{data['member_id']}_{frappe.utils.today()}.pdf"
        
        # Save PDF as file
        file_doc = frappe.get_doc({
            "doctype": "File",
            "file_name": file_name,
            "attached_to_doctype": "Member Tithe Record",
            "attached_to_name": member_tithe_record_name,
            "content": pdf,
            "is_private": 1
        })
        
        file_doc.save(ignore_permissions=True)
        frappe.db.commit()
        
        return file_doc.file_url
    
    except Exception as e:
        frappe.log_error(f"Error generating PDF: {str(e)}", "PDF Generation Error")
        frappe.throw(_("Error generating PDF: {0}").format(str(e)))


@frappe.whitelist()
def email_tithe_statement(member_tithe_record_name, recipient_email=None):
    """
    Email tithe statement to member with PDF attachment.
    """
    try:
        doc = frappe.get_doc("Member Tithe Record", member_tithe_record_name)
        
        # Get member email if not provided
        if not recipient_email:
            member = frappe.db.get_value("Member", doc.member_id, "email")
            recipient_email = member
        
        if not recipient_email:
            frappe.throw(_("No email address found for this member. Please provide an email address."))
        
        # Generate PDF
        pdf_url = generate_tithe_statement_pdf(member_tithe_record_name)
        
        # Get data for email
        data = get_tithe_card_data(member_tithe_record_name)
        
        # Email subject
        subject = f"Your Tithe Statement - {data['company_name']}"
        
        # Email message
        message = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2 style="color: #667eea;">Dear {data['salutation']} {data['full_name']},</h2>
            
            <p>Thank you for your faithful giving and commitment to the work of God's kingdom.</p>
            
            <div style="background: #f8f9ff; padding: 20px; border-radius: 10px; margin: 20px 0;">
                <h3 style="color: #667eea; margin-top: 0;">Tithe Summary</h3>
                <p><strong>Total Contributions:</strong> {data['total_amount']}</p>
                <p><strong>Number of Payments:</strong> {data['total_payments']}</p>
                <p><strong>Average Payment:</strong> {data['avg_payment']}</p>
            </div>
            
            <p>Your detailed tithe statement is attached to this email.</p>
            
            <p style="font-style: italic; color: #666;">
                "Each of you should give what you have decided in your heart to give, 
                not reluctantly or under compulsion, for God loves a cheerful giver." 
                <br><strong>- 2 Corinthians 9:7</strong>
            </p>
            
            <p>God bless you!</p>
            
            <p style="color: #999; font-size: 12px; margin-top: 30px;">
                {data['company_name']}<br>
                {data['branch']}
            </p>
        </div>
        """
        
        # Get PDF file
        file_doc = frappe.get_doc("File", {"file_url": pdf_url})
        
        # Send email
        frappe.sendmail(
            recipients=[recipient_email],
            subject=subject,
            message=message,
            attachments=[{
                "fname": f"Tithe_Statement_{data['member_id']}.pdf",
                "fcontent": file_doc.get_content()
            }],
            reference_doctype="Member Tithe Record",
            reference_name=member_tithe_record_name
        )
        
        frappe.msgprint(_("Tithe statement sent successfully to {0}").format(recipient_email))
        
        return True
    
    except Exception as e:
        frappe.log_error(f"Error emailing statement: {str(e)}", "Email Statement Error")
        frappe.throw(_("Error sending email: {0}").format(str(e)))


def generate_print_html(data):
    """
    Generate HTML for printing.
    This creates the beautiful tithe card HTML.
    """
    # Build payment history HTML
    payments_html = ""
    for payment in data['recent_payments']:
        payments_html += f"""
        <tr>
            <td>{payment['date']}</td>
            <td><span class="receipt-badge">{payment['receipt_no']}</span></td>
            <td>{payment['currency']}</td>
            <td style="font-weight: 700; color: #667eea;">{payment['amount']}</td>
        </tr>
        """
    
    # Complete HTML with inline styles
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;600;700&family=Lato:wght@300;400;700&display=swap');
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{ font-family: 'Lato', sans-serif; padding: 20px; }}
            .card-container {{ max-width: 900px; margin: 0 auto; border: 2px solid #e0e0e0; border-radius: 16px; overflow: hidden; }}
            .card-header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 40px; position: relative; overflow: hidden; }}
            .card-header::before {{ content: ''; position: absolute; top: -50%; right: -10%; width: 400px; height: 400px; background: rgba(255,255,255,0.1); border-radius: 50%; }}
            .church-logo {{ width: 80px; height: 80px; background: white; border-radius: 50%; display: flex; align-items: center; justify-content: center; margin: 0 auto 20px; position: relative; z-index: 1; }}
            .church-logo svg {{ width: 50px; height: 50px; fill: #667eea; }}
            .header-title {{ text-align: center; color: white; position: relative; z-index: 1; }}
            .header-title h1 {{ font-family: 'Playfair Display', serif; font-size: 32px; font-weight: 700; margin-bottom: 8px; }}
            .header-title p {{ font-size: 16px; opacity: 0.95; letter-spacing: 1px; }}
            .card-body {{ padding: 40px; }}
            .member-info {{ display: grid; grid-template-columns: 1fr 1fr; gap: 25px; margin-bottom: 35px; padding-bottom: 35px; border-bottom: 2px solid #f0f0f0; }}
            .info-label {{ font-size: 11px; text-transform: uppercase; letter-spacing: 1.5px; color: #999; margin-bottom: 6px; font-weight: 600; }}
            .info-value {{ font-size: 18px; color: #333; font-weight: 600; }}
            .stats-row {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; margin-bottom: 30px; }}
            .stat-card {{ background: #f8f9ff; padding: 20px; border-radius: 12px; border: 2px solid #e8ebff; text-align: center; }}
            .stat-number {{ font-size: 24px; font-weight: 700; color: #667eea; margin-bottom: 5px; }}
            .stat-label {{ font-size: 10px; text-transform: uppercase; letter-spacing: 1px; color: #999; font-weight: 600; }}
            .total-section {{ background: linear-gradient(135deg, #f8f9ff 0%, #f0f2ff 100%); padding: 30px; border-radius: 16px; margin-bottom: 30px; border: 2px solid #e8ebff; text-align: center; }}
            .total-label {{ font-size: 13px; color: #667eea; text-transform: uppercase; letter-spacing: 2px; margin-bottom: 10px; font-weight: 700; }}
            .total-amount {{ font-size: 42px; font-weight: 700; color: #667eea; font-family: 'Playfair Display', serif; }}
            .history-header {{ font-size: 16px; font-weight: 700; color: #333; margin-bottom: 15px; padding-left: 15px; border-left: 4px solid #667eea; }}
            .history-table {{ width: 100%; border-collapse: collapse; }}
            .history-table thead th {{ text-align: left; font-size: 10px; text-transform: uppercase; letter-spacing: 1.5px; color: #999; font-weight: 700; padding: 12px 10px; border-bottom: 2px solid #e0e0e0; }}
            .history-table tbody td {{ padding: 14px 10px; color: #333; font-size: 13px; border-bottom: 1px solid #f0f0f0; }}
            .history-table tbody tr:nth-child(even) {{ background: #f8f9fa; }}
            .receipt-badge {{ display: inline-block; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 3px 10px; border-radius: 15px; font-size: 10px; font-weight: 600; }}
            .card-footer {{ background: #f8f9fa; padding: 30px; text-align: center; border-top: 2px solid #e0e0e0; }}
            .footer-text {{ color: #666; font-size: 12px; line-height: 1.8; margin-bottom: 12px; }}
            .footer-verse {{ font-style: italic; color: #667eea; font-size: 13px; font-weight: 600; font-family: 'Playfair Display', serif; }}
            @media print {{ body {{ padding: 0; }} .card-container {{ border: none; }} }}
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
                    <h1>{data['company_name']}</h1>
                    <p>Member Tithe Record Certificate</p>
                </div>
            </div>
            <div class="card-body">
                <div class="member-info">
                    <div><div class="info-label">Member ID</div><div class="info-value">{data['member_id']}</div></div>
                    <div><div class="info-label">Full Name</div><div class="info-value">{data['salutation']} {data['full_name']}</div></div>
                    <div><div class="info-label">Branch</div><div class="info-value">{data['branch']}</div></div>
                    <div><div class="info-label">Record Date</div><div class="info-value">{data['record_date']}</div></div>
                </div>
                <div class="stats-row">
                    <div class="stat-card"><div class="stat-number">{data['total_payments']}</div><div class="stat-label">Total Payments</div></div>
                    <div class="stat-card"><div class="stat-number">{data['avg_payment']}</div><div class="stat-label">Average Payment</div></div>
                    <div class="stat-card"><div class="stat-number">{data['last_payment_date']}</div><div class="stat-label">Last Payment</div></div>
                </div>
                <div class="total-section">
                    <div class="total-label">Total Tithe Contributed</div>
                    <div class="total-amount">{data['total_amount']}</div>
                </div>
                <div class="payment-history">
                    <div class="history-header">Recent Payment History</div>
                    <table class="history-table">
                        <thead><tr><th>Date</th><th>Receipt No</th><th>Currency</th><th>Amount</th></tr></thead>
                        <tbody>{payments_html}</tbody>
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
    </html>
    """
    
    return html