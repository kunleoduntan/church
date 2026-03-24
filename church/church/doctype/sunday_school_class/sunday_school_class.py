# Copyright (c) 2024, kunle and contributors
# For license information, please see license.txt


"""
Sunday School Class - Complete System

Features:
✅ Smart member fetching by demographic_group + branch
✅ Multi-channel messaging (SMS/WhatsApp/Email)
✅ Beautiful HTML message containerization
✅ Member synchronization
✅ Optimized queries
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import nowdate, now, getdate, format_date, fmt_money
import json


class SundaySchoolClass(Document):
    """Sunday School Class Document"""
    
    def validate(self):
        """Validate and calculate"""
        self.calculate_member_count()
        self.set_full_name()
    
    def calculate_member_count(self):
        """Calculate total members"""
        self.member_count = len(self.sunday_school_group_member or [])
    
    def set_full_name(self):
        """Set display name for linking"""
        if self.class_name and self.sunday_school_class_category:
            self.class_desc = f"{self.class_name} - {self.sunday_school_class_category}"


@frappe.whitelist()
def fetch_members_by_demographic(class_doc_name):
    """
    Fetch members based on demographic_group and branch
    Smart filtering with optimization
    
    Returns members matching:
    - demographic_group from Sunday School Class
    - branch from Sunday School Class
    - Active members only
    """
    try:
        # Get the class document
        doc = frappe.get_doc('Sunday School Class', class_doc_name)
        
        if not doc.demographic_group:
            return {
                'success': False,
                'message': _('Please select a Demographic Group first')
            }
        
        if not doc.branch:
            return {
                'success': False,
                'message': _('Please select a Branch first')
            }
        
        # Build filters
        filters = {
            'demographic_group': doc.demographic_group,
            'branch': doc.branch,
            'member_status': 'Active'
        }
        
        # Fetch members - OPTIMIZED: Only required fields
        members = frappe.get_all('Member',
            filters=filters,
            fields=[
                'name as member_id',
                'full_name',
                'email',
                'mobile_phone as phone_no',
                'gender',
                'age',
                'date_of_birth',
                'date_of_joining',
                'sunday_school_class',
                'sunday_school_class_category'
            ],
            order_by='full_name asc'
        )
        
        if not members:
            return {
                'success': False,
                'message': _(f'No active members found for {doc.demographic_group} in {doc.branch}')
            }
        
        # Clear existing members
        doc.sunday_school_group_member = []
        
        # Add fetched members
        added_count = 0
        for member in members:
            row = doc.append('sunday_school_group_member', {
                'member_id': member.member_id,
                'full_name': member.full_name,
                'email': member.email,
                'phone_no': member.phone_no,
                'gender': member.gender,
                'age': member.age,
                'date_of_birth': member.date_of_birth,
                'date_of_joining': member.date_of_joining,
                'branch': doc.branch,
                'class_name': doc.class_name,
                'sunday_school_class_category': doc.sunday_school_class_category,
                'teacher_name': doc.teacher_name,
                'salutation': doc.salutation
            })
            added_count += 1
        
        # Save the document
        doc.save()
        frappe.db.commit()
        
        return {
            'success': True,
            'message': _(f'✅ Successfully added {added_count} members from {doc.demographic_group} group'),
            'count': added_count,
            'members': members
        }
        
    except Exception as e:
        frappe.log_error(
            message=frappe.get_traceback(),
            title="Fetch Members by Demographic Error"
        )
        return {
            'success': False,
            'message': _('Error fetching members: {0}').format(str(e))
        }


@frappe.whitelist()
def send_class_message(class_doc_name, message_text, channels=None):
    """
    Send message to all class members via selected channels
    
    Args:
        class_doc_name: Sunday School Class name
        message_text: Plain text message
        channels: JSON string of selected channels ['email', 'sms', 'whatsapp']
    
    Returns:
        Success/failure report with delivery statistics
    """
    try:
        doc = frappe.get_doc('Sunday School Class', class_doc_name)
        
        if not doc.sunday_school_group_member:
            frappe.throw(_("No members in this class"))
        
        if not message_text:
            frappe.throw(_("Message content is required"))
        
        # Parse channels
        if isinstance(channels, str):
            channels = json.loads(channels)
        
        if not channels:
            channels = ['email']  # Default to email
        
        # Get Church Settings
        church_settings = frappe.get_single('Church Settings')
        
        # Initialize counters
        results = {
            'email': {'sent': 0, 'failed': 0, 'no_address': 0},
            'sms': {'sent': 0, 'failed': 0, 'no_phone': 0},
            'whatsapp': {'sent': 0, 'failed': 0, 'no_phone': 0}
        }
        
        # Process each member
        for member in doc.sunday_school_group_member:
            
            # Send Email
            if 'email' in channels:
                if member.email:
                    try:
                        html_message = generate_beautiful_html_message(
                            doc=doc,
                            member=member,
                            message_text=message_text,
                            church_settings=church_settings
                        )
                        
                        frappe.sendmail(
                            recipients=[member.email],
                            subject=f"Message from {doc.class_name} - {church_settings.church_name or 'Church'}",
                            message=html_message,
                            delayed=False,
                            reference_doctype='Sunday School Class',
                            reference_name=doc.name
                        )
                        results['email']['sent'] += 1
                        
                    except Exception as e:
                        results['email']['failed'] += 1
                        frappe.log_error(
                            message=f"Email failed for {member.full_name}: {str(e)}",
                            title="Sunday School Email Error"
                        )
                else:
                    results['email']['no_address'] += 1
            
            # Send SMS
            if 'sms' in channels:
                if member.phone_no:
                    try:
                        sms_result = send_sms_message(
                            phone=member.phone_no,
                            message=message_text,
                            church_settings=church_settings
                        )
                        
                        if sms_result['success']:
                            results['sms']['sent'] += 1
                        else:
                            results['sms']['failed'] += 1
                            
                    except Exception as e:
                        results['sms']['failed'] += 1
                        frappe.log_error(
                            message=f"SMS failed for {member.full_name}: {str(e)}",
                            title="Sunday School SMS Error"
                        )
                else:
                    results['sms']['no_phone'] += 1
            
            # Send WhatsApp
            if 'whatsapp' in channels:
                if member.phone_no:
                    try:
                        wa_result = send_whatsapp_message(
                            phone=member.phone_no,
                            message=message_text,
                            church_settings=church_settings
                        )
                        
                        if wa_result['success']:
                            results['whatsapp']['sent'] += 1
                        else:
                            results['whatsapp']['failed'] += 1
                            
                    except Exception as e:
                        results['whatsapp']['failed'] += 1
                        frappe.log_error(
                            message=f"WhatsApp failed for {member.full_name}: {str(e)}",
                            title="Sunday School WhatsApp Error"
                        )
                else:
                    results['whatsapp']['no_phone'] += 1
        
        # Commit all
        frappe.db.commit()
        
        # Build response message
        response_message = build_messaging_report(results, channels)
        
        frappe.msgprint(
            response_message,
            indicator='green' if sum(r['failed'] for r in results.values()) == 0 else 'orange',
            title='Messages Sent'
        )
        
        return {
            'success': True,
            'message': response_message,
            'results': results
        }
        
    except Exception as e:
        frappe.log_error(
            message=frappe.get_traceback(),
            title="Sunday School Messaging Error"
        )
        frappe.throw(_("Failed to send messages: {0}").format(str(e)))


def generate_beautiful_html_message(doc, member, message_text, church_settings):
    """
    Generate beautiful containerized HTML message
    Converts plain text to elegant HTML email
    """
    church_name = church_settings.church_name if church_settings else 'Church'
    church_logo = church_settings.church_logo if church_settings else ''
    
    # Convert line breaks to paragraphs
    paragraphs = message_text.split('\n\n')
    formatted_message = ''.join([f'<p style="font-size: 15px; color: #34495e; line-height: 1.8; margin: 15px 0;">{p.replace(chr(10), "<br>")}</p>' for p in paragraphs if p.strip()])
    
    html = f"""
        <div style="font-family: 'Segoe UI', Arial, sans-serif; max-width: 650px; margin: 0 auto; background: #f5f5f5;">
            <!-- Header -->
            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 40px 20px; text-align: center; position: relative; overflow: hidden;">
                <div style="position: absolute; top: -50px; right: -50px; width: 200px; height: 200px; background: rgba(255,255,255,0.1); border-radius: 50%;"></div>
                <div style="position: absolute; bottom: -50px; left: -50px; width: 150px; height: 150px; background: rgba(255,255,255,0.1); border-radius: 50%;"></div>
                {f'<img src="{church_logo}" style="height: 60px; margin-bottom: 15px; position: relative; z-index: 1;" alt="Church Logo">' if church_logo else ''}
                <h1 style="color: white; margin: 0; font-size: 28px; text-shadow: 2px 2px 4px rgba(0,0,0,0.2); position: relative; z-index: 1;">
                    📚 {doc.class_name}
                </h1>
                <p style="color: rgba(255,255,255,0.9); margin: 8px 0 0 0; font-size: 14px; position: relative; z-index: 1;">
                    {doc.sunday_school_class_category or 'Sunday School'}
                </p>
            </div>
            
            <!-- Main Content -->
            <div style="background: white; padding: 40px 30px; border-radius: 0 0 20px 20px; box-shadow: 0 10px 30px rgba(0,0,0,0.1);">
                <p style="font-size: 18px; color: #2c3e50; margin-bottom: 10px;">Dear {member.full_name},</p>
                
                <div style="background: linear-gradient(135deg, #f8f9fa 0%, #ffffff 100%); padding: 25px; border-radius: 12px; margin: 25px 0; border-left: 4px solid #667eea;">
                    {formatted_message}
                </div>
                
                <!-- Class Info -->
                <div style="background: #f0f7ff; padding: 20px; border-radius: 8px; margin: 25px 0;">
                    <table style="width: 100%; font-size: 14px; color: #2c3e50;">
                        <tr>
                            <td style="padding: 8px 0;"><strong>📚 Class:</strong></td>
                            <td style="padding: 8px 0; text-align: right;">{doc.class_name}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px 0;"><strong>👨‍🏫 Teacher:</strong></td>
                            <td style="padding: 8px 0; text-align: right;">{doc.teacher_name or 'N/A'}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px 0;"><strong>🏢 Branch:</strong></td>
                            <td style="padding: 8px 0; text-align: right;">{doc.branch}</td>
                        </tr>
                    </table>
                </div>
                
                <!-- Bible Verse -->
                <div style="background: linear-gradient(135deg, #e8f5e9 0%, #fff8e1 100%); padding: 20px; border-radius: 12px; margin: 25px 0; text-align: center;">
                    <p style="color: #2e7d32; font-size: 16px; font-style: italic; margin: 0;">
                        "Your word is a lamp for my feet, a light on my path."
                    </p>
                    <p style="color: #558b2f; font-weight: bold; margin: 10px 0 0 0; font-size: 14px;">
                        — Psalm 119:105
                    </p>
                </div>
                
                <div style="margin-top: 35px; padding-top: 25px; border-top: 1px solid #e0e0e0;">
                    <p style="font-size: 15px; color: #2c3e50; margin: 0;">
                        <strong>Blessings,</strong><br>
                        <span style="color: #667eea; font-size: 17px; font-weight: bold;">{doc.teacher_name or 'Your Teacher'}</span><br>
                        <em style="color: #7f8c8d;">{doc.class_name}</em><br>
                        <em style="color: #7f8c8d;">{church_name}</em>
                    </p>
                </div>
            </div>
            
            <!-- Footer -->
            <div style="text-align: center; padding: 25px; background: #f5f5f5;">
                <p style="color: #95a5a6; font-size: 12px; margin: 5px 0;">
                    📧 Automated message from {church_name}
                </p>
                <p style="color: #95a5a6; font-size: 12px; margin: 5px 0;">
                    ⛪ Building faith, one class at a time
                </p>
            </div>
        </div>
    """
    
    return html


def send_sms_message(phone, message, church_settings):
    """Send SMS via configured provider"""
    try:
        # Check if SMS enabled
        if not church_settings.sms_notifications_enabled:
            return {'success': False, 'error': 'SMS notifications disabled'}
        
        provider = church_settings.sms_provider
        
        if not provider:
            return {'success': False, 'error': 'No SMS provider configured'}
        
        # Format phone number
        formatted_phone = format_phone_number(phone)
        
        # Truncate message if needed
        message = message[:1000]  # Most providers limit
        
        # Send via provider
        if provider == 'Termii':
            return send_sms_via_termii(formatted_phone, message, church_settings)
        elif provider == 'Twilio':
            return send_sms_via_twilio(formatted_phone, message, church_settings)
        elif provider == "Africa's Talking":
            return send_sms_via_africastalking(formatted_phone, message, church_settings)
        else:
            return {'success': False, 'error': f'Unknown SMS provider: {provider}'}
            
    except Exception as e:
        frappe.log_error(f"SMS Error: {str(e)}", "Send SMS Error")
        return {'success': False, 'error': str(e)}


def send_whatsapp_message(phone, message, church_settings):
    """Send WhatsApp via configured provider"""
    try:
        # Check if WhatsApp enabled
        if not church_settings.whatsapp_notifications_enabled:
            return {'success': False, 'error': 'WhatsApp notifications disabled'}
        
        provider = church_settings.whatsapp_provider
        
        if not provider:
            return {'success': False, 'error': 'No WhatsApp provider configured'}
        
        # Format phone number
        formatted_phone = format_phone_number(phone)
        
        # Send via provider
        if provider == '360Dialog':
            return send_whatsapp_via_360dialog(formatted_phone, message, church_settings)
        elif provider == 'Twilio':
            return send_whatsapp_via_twilio(formatted_phone, message, church_settings)
        elif provider == 'Wati':
            return send_whatsapp_via_wati(formatted_phone, message, church_settings)
        else:
            return {'success': False, 'error': f'Unknown WhatsApp provider: {provider}'}
            
    except Exception as e:
        frappe.log_error(f"WhatsApp Error: {str(e)}", "Send WhatsApp Error")
        return {'success': False, 'error': str(e)}


def send_sms_via_termii(phone, message, settings):
    """Send SMS via Termii"""
    import requests
    
    try:
        if not settings.termii_api_key or not settings.termii_sender_id:
            return {'success': False, 'error': 'Termii credentials incomplete'}
        
        url = "https://api.ng.termii.com/api/sms/send"
        
        payload = {
            "to": phone,
            "from": settings.termii_sender_id,
            "sms": message,
            "type": "plain",
            "channel": settings.termii_channel or "generic",
            "api_key": settings.get_password('termii_api_key')
        }
        
        response = requests.post(url, json=payload, timeout=30)
        
        if response.status_code == 200:
            return {'success': True, 'message_id': response.json().get('message_id')}
        else:
            return {'success': False, 'error': f'Termii error: {response.status_code}'}
            
    except Exception as e:
        return {'success': False, 'error': str(e)}


def send_sms_via_twilio(phone, message, settings):
    """Send SMS via Twilio"""
    # Implementation similar to visitor_messaging_robust.py
    return {'success': False, 'error': 'Twilio SMS not configured'}


def send_sms_via_africastalking(phone, message, settings):
    """Send SMS via Africa's Talking"""
    # Implementation similar to visitor_messaging_robust.py
    return {'success': False, 'error': "Africa's Talking SMS not configured"}


def send_whatsapp_via_360dialog(phone, message, settings):
    """Send WhatsApp via 360Dialog"""
    # Implementation similar to visitor_messaging_robust.py
    return {'success': False, 'error': '360Dialog not configured'}


def send_whatsapp_via_twilio(phone, message, settings):
    """Send WhatsApp via Twilio"""
    # Implementation similar to visitor_messaging_robust.py
    return {'success': False, 'error': 'Twilio WhatsApp not configured'}


def send_whatsapp_via_wati(phone, message, settings):
    """Send WhatsApp via Wati"""
    # Implementation similar to visitor_messaging_robust.py
    return {'success': False, 'error': 'Wati not configured'}


def format_phone_number(phone):
    """Format phone number to international format"""
    if not phone:
        return None
    
    # Remove all non-digit characters except +
    phone = ''.join(c for c in phone if c.isdigit() or c == '+')
    
    # Add + if not present
    if not phone.startswith('+'):
        # Assume Nigerian number if no country code
        if len(phone) == 10 or len(phone) == 11:
            phone = '+234' + phone.lstrip('0')
        else:
            phone = '+' + phone
    
    return phone


def build_messaging_report(results, channels):
    """Build beautiful messaging report"""
    
    total_sent = sum(r['sent'] for r in results.values())
    total_failed = sum(r['failed'] for r in results.values())
    
    if total_failed > 0:
        status_color = "#ff9800"
        status_icon = "⚠️"
    else:
        status_color = "#4caf50"
        status_icon = "✅"
    
    message = f"""
        <div style="padding: 20px; border-radius: 8px; background: #f8f9fa; border-left: 4px solid {status_color};">
            <h4 style="color: {status_color}; margin-top: 0; font-size: 18px;">
                {status_icon} Messaging Complete
            </h4>
            <div style="background: white; padding: 15px; border-radius: 6px; margin: 15px 0;">
                <table style="width: 100%; border-collapse: collapse;">
    """
    
    for channel in channels:
        if channel in results:
            r = results[channel]
            message += f"""
                    <tr>
                        <td style="padding: 8px; border-bottom: 1px solid #e0e0e0;">
                            <strong>{channel.upper()}:</strong>
                        </td>
                        <td style="padding: 8px; border-bottom: 1px solid #e0e0e0; text-align: right;">
                            <span style="color: #4caf50;">✓ {r['sent']}</span>
                            {f'<span style="color: #f44336;"> ✗ {r["failed"]}</span>' if r['failed'] > 0 else ''}
                            {f'<span style="color: #9e9e9e;"> ⊘ {r.get("no_address", r.get("no_phone", 0))}</span>' if r.get('no_address') or r.get('no_phone') else ''}
                        </td>
                    </tr>
            """
    
    message += f"""
                    <tr>
                        <td style="padding: 8px;"><strong>TOTAL:</strong></td>
                        <td style="padding: 8px; text-align: right;">
                            <span style="color: #4caf50; font-weight: bold;">{total_sent} sent</span>
                            {f'<span style="color: #f44336; font-weight: bold;"> {total_failed} failed</span>' if total_failed > 0 else ''}
                        </td>
                    </tr>
                </table>
            </div>
        </div>
    """
    
    return message