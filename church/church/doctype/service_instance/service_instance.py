# Copyright (c) 2026, kunle and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime, get_datetime, formatdate, get_time, add_to_date, nowdate
import json
import hashlib
import qrcode
import io
import base64
from frappe.utils.file_manager import save_file
from urllib.parse import quote as _url_quote


class ServiceInstance(Document):

    def validate(self):
        """Validate Service Instance"""
        self.calculate_total_attendance()

    def after_insert(self):
        """After new record is created — generate QR and notify pastors"""
        self.generate_venue_qr()
        self.notify_pastors_new_service()

    def on_update(self):
        """On every save — regenerate QR if service details changed"""
        self.generate_venue_qr()

    def calculate_total_attendance(self):
        """Calculate total attendance from men, women, and children counts"""
        self.total_attendance = (
            (self.men_count or 0) +
            (self.women_count or 0) +
            (self.children_count or 0)
        )

    # =========================================================================
    # QR CODE GENERATION
    # =========================================================================

    def generate_venue_qr(self):
        """
        Generate and store a venue QR code for this service instance.

        The QR encodes the /checkin landing page URL with code + service params.
        The code is time-based (changes every 10 min) so the stored QR is the
        CURRENT snapshot. The display page regenerates it live via JS.

        Uses frappe.db.set_value() so this never re-triggers validate/on_update.
        """
        try:
            settings = frappe.get_single('Church Settings')

            site_url = frappe.utils.get_url()
            interval = 10  # minutes — matches QR refresh interval

            current_time = now_datetime()
            time_block = int(current_time.timestamp() / (interval * 60))

            church_name = settings.church_name or ''
            hash_input = f"{self.name}{time_block}{church_name}"
            code_hash = hashlib.sha256(hash_input.encode()).hexdigest()[:12].upper()
            code = f"CHK-{code_hash}"

            # URL that the QR encodes — opens /checkin landing page on phone
            checkin_url = f"{site_url}/checkin?code={code}&service={_url_quote(self.name)}"

            # Build QR image
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_H,
                box_size=10,
                border=4
            )
            qr.add_data(checkin_url)
            qr.make(fit=True)

            img = qr.make_image(fill_color="black", back_color="white")
            buffer = io.BytesIO()
            img.save(buffer, format="PNG")
            buffer.seek(0)

            # Save file attached to this Service Instance
            file_doc = save_file(
                fname=f"{self.name}_venue_qr.png",
                content=buffer.getvalue(),
                dt="Service Instance",
                dn=self.name,
                is_private=0
            )

            # Calculate expiry — 40 minutes after service time
            service_dt = None
            if self.service_date and self.service_time:
                try:
                    service_dt = get_datetime(f"{self.service_date} {self.service_time}")
                except Exception:
                    pass

            expiry = add_to_date(service_dt or now_datetime(), minutes=40)

            # Write directly to DB — skips validate / on_update entirely
            frappe.db.set_value(
                'Service Instance',
                self.name,
                {
                    'venue_qr_code': file_doc.file_url,
                    'venue_qr_checkin_url': checkin_url,
                    'venue_qr_expires_at': expiry,
                    'venue_qr_code_hash': code
                },
                update_modified=False
            )
            frappe.db.commit()

        except Exception:
            frappe.log_error(frappe.get_traceback(), "Venue QR Generation Error")

    # =========================================================================
    # PASTOR NOTIFICATION
    # =========================================================================

    def notify_pastors_new_service(self):
        """
        Send email to all active pastors when a new Service Instance is created.
        Includes service details and the venue QR code image.
        """
        try:
            pastors = frappe.get_all(
                'Member',
                filters={'is_a_pastor': 1, 'member_status': 'Active'},
                fields=['name', 'full_name', 'email']
            )

            if not pastors:
                return

            settings = frappe.get_single('Church Settings')
            church_name = settings.church_name or 'Church'

            service_date_fmt = formatdate(self.service_date, "dddd, dd MMMM yyyy") if self.service_date else 'N/A'
            service_time_fmt = str(self.service_time or '')
            service_name = self.service_name or self.service or 'Service'

            # Get QR URL if already generated
            qr_url = frappe.db.get_value('Service Instance', self.name, 'venue_qr_code') or ''
            site_url = frappe.utils.get_url()
            display_url = f"{site_url}/service-display?service={_url_quote(self.name)}"

            for pastor in pastors:
                if not pastor.email:
                    continue

                try:
                    subject = f"📅 New Service Scheduled: {service_name} — {service_date_fmt}"

                    message = f"""
                    <div style="font-family:'Segoe UI',Arial,sans-serif;max-width:600px;margin:0 auto;">

                        <div style="background:linear-gradient(135deg,#667eea,#764ba2);padding:30px;border-radius:12px 12px 0 0;text-align:center;color:white;">
                            <div style="font-size:36px;margin-bottom:8px;">⛪</div>
                            <h1 style="margin:0;font-size:22px;">New Service Instance Created</h1>
                            <p style="margin:8px 0 0;opacity:0.85;">{church_name}</p>
                        </div>

                        <div style="background:#fff;padding:30px;border-radius:0 0 12px 12px;border:1px solid #e8e8e8;">
                            <p style="font-size:16px;color:#2c3e50;">Dear <strong>{pastor.full_name}</strong>,</p>
                            <p style="color:#555;line-height:1.7;">A new service has been scheduled. Here are the details:</p>

                            <div style="background:#f8f6ff;border-left:4px solid #667eea;padding:18px;border-radius:8px;margin:20px 0;">
                                <table style="width:100%;font-size:15px;color:#2c3e50;border-collapse:collapse;">
                                    <tr><td style="padding:6px 0;width:140px;"><strong>Service:</strong></td><td>{service_name}</td></tr>
                                    <tr><td style="padding:6px 0;"><strong>Date:</strong></td><td>{service_date_fmt}</td></tr>
                                    <tr><td style="padding:6px 0;"><strong>Time:</strong></td><td>{service_time_fmt}</td></tr>
                                    <tr><td style="padding:6px 0;"><strong>Branch:</strong></td><td>{self.branch or 'N/A'}</td></tr>
                                    <tr><td style="padding:6px 0;"><strong>Service ID:</strong></td><td style="font-family:monospace;font-size:13px;">{self.name}</td></tr>
                                </table>
                            </div>

                            <div style="background:#e8f5e9;border-left:4px solid #27ae60;padding:16px;border-radius:8px;margin:20px 0;">
                                <p style="margin:0 0 8px;font-weight:700;color:#1a6b35;">📺 Display QR Code for Check-In</p>
                                <p style="margin:0;font-size:13px;color:#2d7a46;line-height:1.6;">
                                    Open the link below on the church display screen or TV.<br>
                                    The QR code refreshes automatically every 10 minutes.
                                </p>
                                <a href="{display_url}" style="display:inline-block;margin-top:12px;background:#27ae60;color:white;padding:10px 20px;border-radius:8px;text-decoration:none;font-weight:600;font-size:14px;">
                                    📺 Open Display Screen →
                                </a>
                            </div>

                            {"<div style='text-align:center;margin:20px 0;'><img src='" + site_url + qr_url + "' style='width:180px;height:180px;border:2px solid #e0e0e0;border-radius:8px;' alt='Venue QR Code'><p style='font-size:12px;color:#aaa;margin-top:6px;'>Current QR Code (refreshes every 10 min)</p></div>" if qr_url else ""}

                            <p style="font-size:13px;color:#888;margin-top:24px;border-top:1px solid #f0f0f0;padding-top:16px;">
                                ⏰ The venue QR code expires <strong>40 minutes after service time</strong>.<br>
                                After expiry, members will still be directed to the check-in page as visitors.
                            </p>

                            <p style="font-size:15px;color:#555;margin-top:20px;">
                                God bless,<br>
                                <strong>{church_name} Management System</strong>
                            </p>
                        </div>
                    </div>
                    """

                    frappe.sendmail(
                        recipients=[pastor.email],
                        subject=subject,
                        message=message,
                        delayed=False,
                        now=True
                    )

                except Exception:
                    frappe.log_error(frappe.get_traceback(), f"Pastor Notification Failed: {pastor.name}")

        except Exception:
            frappe.log_error(frappe.get_traceback(), "Notify Pastors Error")


# =============================================================================
# WHITELISTED API FUNCTIONS
# =============================================================================

@frappe.whitelist()
def regenerate_venue_qr(service_instance):
    """
    Manually regenerate the venue QR code for a service instance.
    Called from the JS button on the form.
    """
    try:
        doc = frappe.get_doc('Service Instance', service_instance)
        doc.generate_venue_qr()

        new_url = frappe.db.get_value('Service Instance', service_instance, 'venue_qr_checkin_url')
        qr_file = frappe.db.get_value('Service Instance', service_instance, 'venue_qr_code')

        return {
            'success': True,
            'message': 'QR code regenerated successfully',
            'qr_file': qr_file,
            'checkin_url': new_url
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Manual QR Regeneration Error")
        return {'success': False, 'message': str(e)}


@frappe.whitelist(allow_guest=True)
def get_live_venue_qr(service_instance):
    """
    Generate a fresh QR code image for the display screen.
    Called every 10 minutes by the service-display page JS.
    Returns base64 image + metadata.
    """
    try:
        settings = frappe.get_single('Church Settings')
        site_url = frappe.utils.get_url()
        interval = 10

        current_time = now_datetime()
        time_block = int(current_time.timestamp() / (interval * 60))

        church_name = settings.church_name or ''
        hash_input = f"{service_instance}{time_block}{church_name}"
        code_hash = hashlib.sha256(hash_input.encode()).hexdigest()[:12].upper()
        code = f"CHK-{code_hash}"

        checkin_url = f"{site_url}/checkin?code={code}&service={_url_quote(service_instance)}"

        # Generate fresh QR image
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            box_size=12,
            border=4
        )
        qr.add_data(checkin_url)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        img_str = base64.b64encode(buffer.getvalue()).decode()

        # Get service details for display
        svc = frappe.db.get_value(
            'Service Instance',
            service_instance,
            ['service_name', 'service_date', 'service_time', 'branch',
             'total_attendance', 'venue_qr_expires_at'],
            as_dict=True
        )

        # Check if expired (40 min after service)
        is_expired = False
        expires_at = svc.venue_qr_expires_at if svc else None
        if expires_at and get_datetime(expires_at) < now_datetime():
            is_expired = True

        # Count live check-ins
        checkin_count = frappe.db.count('Church Attendance', {
            'service_instance': service_instance,
            'present': 1
        })

        # Next refresh in seconds
        seconds_in_block = interval * 60
        elapsed = int(current_time.timestamp()) % seconds_in_block
        next_refresh = seconds_in_block - elapsed

        return {
            'success': True,
            'qr_image': f'data:image/png;base64,{img_str}',
            'checkin_url': checkin_url,
            'code': code,
            'is_expired': is_expired,
            'service_name': svc.service_name if svc else '',
            'service_date': formatdate(svc.service_date) if svc and svc.service_date else '',
            'service_time': str(svc.service_time or '') if svc else '',
            'branch': svc.branch if svc else '',
            'church_name': church_name or 'Church',
            'checkin_count': checkin_count,
            'next_refresh_seconds': next_refresh
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Live QR Generation Error")
        return {'success': False, 'message': str(e)}


@frappe.whitelist()
def send_coordinator_assignment_emails(service_instance):
    """Send coordinator assignment emails"""
    doc = frappe.get_doc('Service Instance', service_instance)

    coordinator_groups = {}
    for visitor in (doc.service_visitors or []):
        if visitor.follow_up_required and visitor.follow_up_assigned_to:
            coord = visitor.follow_up_assigned_to
            if coord not in coordinator_groups:
                coordinator_groups[coord] = {
                    'coordinator': coord,
                    'coordinator_name': visitor.follow_up_coordinator_name or coord,
                    'visitors': []
                }
            coordinator_groups[coord]['visitors'].append(visitor)

    if not coordinator_groups:
        return {'success': False, 'message': _('No coordinator assignments found')}

    sent = 0
    for coord_id, group in coordinator_groups.items():
        coord_email = frappe.db.get_value('Member', coord_id, 'email')
        if not coord_email:
            continue

        visitor_list = ''.join([
            f"<li style='padding:4px 0;'>{v.full_name} — {v.phone or 'No phone'}</li>"
            for v in group['visitors']
        ])

        frappe.sendmail(
            recipients=[coord_email],
            subject=f"Visitor Follow-up Assignment — {doc.service_name or doc.name}",
            message=f"""
            <div style="font-family:Arial,sans-serif;max-width:600px;">
                <h2 style="color:#2c3e50;">Visitor Follow-up Assignment</h2>
                <p>Dear <strong>{group['coordinator_name']}</strong>,</p>
                <p>You have been assigned to follow up with the following visitor(s) from <strong>{doc.service_name or doc.name}</strong>:</p>
                <ul style="font-size:15px;line-height:1.8;">{visitor_list}</ul>
                <p>Please reach out within 48 hours. God bless your ministry!</p>
                <p>— Church Administration</p>
            </div>
            """,
            delayed=False,
            now=True
        )
        sent += 1

    return {
        'success': True,
        'message': _(f'Assignment emails sent to {sent} coordinator(s)')
    }


@frappe.whitelist()
def send_ministry_team_notifications(service_instance, notification_type, recipients,
                                      send_via_email=1, send_via_sms=0, send_via_whatsapp=0,
                                      custom_subject=None, custom_message=None):
    """Send notifications to ministry team members"""
    doc = frappe.get_doc("Service Instance", service_instance)

    if isinstance(recipients, str):
        recipients = json.loads(recipients)

    service_name = doc.service_name or "Church Service"
    service_date = formatdate(doc.service_date, "dd MMM yyyy")
    service_time = str(doc.service_time or "")
    venue = doc.get("venue") or "Church"

    if notification_type == "Custom Message":
        subject = custom_subject or "Church Service Notification"
        message_html = custom_message or ""
        message_plain = frappe.utils.html2text(message_html)
    else:
        subject, message_html, message_plain = generate_notification_content(
            doc, notification_type, service_name, service_date, service_time, venue
        )

    sent_count = 0
    failed_count = 0

    for member_name in recipients:
        member = frappe.get_doc("Member", member_name)

        team_member = next((tm for tm in doc.ministry_team if tm.member == member_name), None)
        if not team_member:
            continue

        personalized_html = message_html.replace("{member_name}", member.full_name or "")
        personalized_html = personalized_html.replace("{ministry_role}", team_member.ministry_role or "Team Member")
        personalized_plain = message_plain.replace("{member_name}", member.full_name or "")
        personalized_plain = personalized_plain.replace("{ministry_role}", team_member.ministry_role or "Team Member")

        try:
            if int(send_via_email) and member.email:
                send_email_notification(member.email, subject, personalized_html, member.full_name)
            if int(send_via_sms) and member.mobile_phone:
                send_sms_notification(member.mobile_phone, personalized_plain, member.full_name)
            if int(send_via_whatsapp) and member.mobile_phone:
                send_whatsapp_notification(member.mobile_phone, personalized_plain, member.full_name)
            sent_count += 1
        except Exception as e:
            frappe.log_error(f"Failed to notify {member.full_name}: {str(e)}", "Notification Error")
            failed_count += 1

    return {
        "success": True,
        "message": _(f"Notifications sent to {sent_count} members. {failed_count} failed.")
    }


@frappe.whitelist()
def send_service_reminder(service_instance):
    doc = frappe.get_doc("Service Instance", service_instance)
    recipients = [tm.member for tm in doc.ministry_team if tm.member]
    if not recipients:
        return {"success": False, "message": _("No ministry team members found")}
    return send_ministry_team_notifications(
        service_instance=service_instance,
        notification_type="Service Reminder",
        recipients=recipients,
        send_via_email=1,
        send_via_sms=1
    )


@frappe.whitelist()
def send_thank_you_message(service_instance):
    doc = frappe.get_doc("Service Instance", service_instance)
    recipients = [tm.member for tm in doc.ministry_team if tm.member and tm.present]
    if not recipients:
        return {"success": False, "message": _("No present ministry team members found")}
    return send_ministry_team_notifications(
        service_instance=service_instance,
        notification_type="Thank You Message",
        recipients=recipients,
        send_via_email=1,
        send_via_whatsapp=1
    )


# =============================================================================
# NOTIFICATION CONTENT GENERATOR
# =============================================================================

def generate_notification_content(doc, notification_type, service_name, service_date, service_time, venue):
    """Generate email/SMS content for each notification type"""

    if notification_type == "Service Reminder":
        subject = f"Reminder: {service_name} — {service_date}"
        message_html = f"""
        <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;background:#f8f9fa;border-radius:10px;overflow:hidden;">
            <div style="background:linear-gradient(135deg,#667eea,#764ba2);padding:30px;text-align:center;color:white;">
                <h1 style="margin:0;font-size:26px;">⏰ Service Reminder</h1>
            </div>
            <div style="background:white;padding:30px;">
                <p style="font-size:17px;color:#2c3e50;">Dear <strong>{{member_name}}</strong>,</p>
                <p style="color:#555;line-height:1.7;">You are scheduled to serve in the upcoming service.</p>
                <div style="background:#e8f4fd;padding:18px;border-radius:8px;border-left:4px solid #3498db;margin:20px 0;">
                    <p style="margin:4px 0;"><strong>Service:</strong> {service_name}</p>
                    <p style="margin:4px 0;"><strong>Date:</strong> {service_date}</p>
                    <p style="margin:4px 0;"><strong>Time:</strong> {service_time}</p>
                    <p style="margin:4px 0;"><strong>Venue:</strong> {venue}</p>
                    <p style="margin:4px 0;"><strong>Your Role:</strong> <span style="background:#3498db;color:white;padding:3px 10px;border-radius:12px;">{{ministry_role}}</span></p>
                </div>
                <div style="background:#fff8e1;padding:12px;border-radius:8px;border-left:4px solid #f39c12;">
                    <p style="margin:0;color:#8b6914;font-size:14px;">⏰ Please arrive 30 minutes early for prayer and preparation.</p>
                </div>
                <p style="color:#555;margin-top:20px;">God bless you,<br><strong>Church Leadership</strong></p>
            </div>
        </div>"""
        message_plain = f"Dear {{member_name}},\n\nReminder: {service_name} on {service_date} at {service_time}.\nYour Role: {{ministry_role}}\nVenue: {venue}\n\nPlease arrive 30 minutes early.\n\nGod bless,\nChurch Leadership"

    elif notification_type == "Thank You Message":
        subject = f"Thank You for Serving — {service_name}"
        message_html = f"""
        <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;">
            <div style="background:linear-gradient(135deg,#56ab2f,#a8e063);padding:30px;text-align:center;color:white;border-radius:10px 10px 0 0;">
                <h1 style="margin:0;">🙏 Thank You!</h1>
            </div>
            <div style="background:white;padding:30px;border-radius:0 0 10px 10px;border:1px solid #e8e8e8;">
                <p style="font-size:17px;color:#2c3e50;">Dear <strong>{{member_name}}</strong>,</p>
                <p style="color:#555;line-height:1.7;">Thank you for your faithful service in today's worship service.</p>
                <div style="background:#e8f8f5;padding:16px;border-radius:8px;border-left:4px solid #27ae60;margin:20px 0;">
                    <p style="margin:4px 0;"><strong>Service:</strong> {service_name}</p>
                    <p style="margin:4px 0;"><strong>Date:</strong> {service_date}</p>
                    <p style="margin:4px 0;"><strong>Your Role:</strong> {{ministry_role}}</p>
                </div>
                <div style="background:#fff3cd;padding:14px;border-radius:8px;text-align:center;font-style:italic;color:#856404;">
                    "Whatever you do, work at it with all your heart, as working for the Lord." — Col 3:23
                </div>
                <p style="color:#555;margin-top:20px;">With gratitude,<br><strong>Church Leadership</strong></p>
            </div>
        </div>"""
        message_plain = f"Dear {{member_name}},\n\nThank you for serving in {service_name} on {service_date} as {{ministry_role}}.\n\nYour dedication is a blessing!\n\nWith gratitude,\nChurch Leadership"

    elif notification_type == "Service Schedule":
        subject = f"Service Schedule: {service_name} — {service_date}"
        message_html = f"""
        <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px;background:white;">
            <h2 style="color:#2c3e50;">Service Schedule</h2>
            <p>Dear <strong>{{member_name}}</strong>,</p>
            <p>You are scheduled for:</p>
            <div style="background:#f8f9fa;padding:15px;border-radius:6px;margin:15px 0;">
                <p><strong>Service:</strong> {service_name}</p>
                <p><strong>Date:</strong> {service_date}</p>
                <p><strong>Time:</strong> {service_time}</p>
                <p><strong>Role:</strong> {{ministry_role}}</p>
            </div>
            <p>Thank you for serving!<br><strong>Church Administration</strong></p>
        </div>"""
        message_plain = f"Dear {{member_name}},\n\nScheduled: {service_name} on {service_date} at {service_time}.\nRole: {{ministry_role}}\n\nThank you!\nChurch Administration"

    else:
        subject = "Church Service Notification"
        message_html = "<p>Church service notification.</p>"
        message_plain = "Church service notification."

    return subject, message_html, message_plain


# =============================================================================
# SEND HELPERS
# =============================================================================

def send_email_notification(recipient, subject, message, member_name):
    frappe.sendmail(recipients=[recipient], subject=subject, message=message, delayed=False, now=True)
    frappe.logger().info(f"Email sent to {member_name} ({recipient})")


def send_sms_notification(phone, message, member_name):
    try:
        from frappe.core.doctype.sms_settings.sms_settings import send_sms
        send_sms([phone], message)
        frappe.logger().info(f"SMS sent to {member_name} ({phone})")
    except Exception as e:
        frappe.log_error(f"SMS failed for {member_name}: {str(e)}", "SMS Error")
        raise


def send_whatsapp_notification(phone, message, member_name):
    try:
        frappe.logger().info(f"WhatsApp queued for {member_name} ({phone})")
        frappe.get_doc({
            "doctype": "Communication",
            "communication_type": "Communication",
            "communication_medium": "WhatsApp",
            "sent_or_received": "Sent",
            "phone_no": phone,
            "content": message,
            "status": "Sent"
        }).insert(ignore_permissions=True)
    except Exception as e:
        frappe.log_error(f"WhatsApp failed for {member_name}: {str(e)}", "WhatsApp Error")
        raise