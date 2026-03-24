# -*- coding: utf-8 -*-
# Copyright (c) 2026, Church Management and contributors
# For license information, please see license.txt

"""
Visitor DocType Controller
Comprehensive visitor management with multi-channel messaging, follow-up tracking, and conversion analytics
"""

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import (
    now_datetime, nowdate, getdate, formatdate, get_datetime,
    date_diff, add_days, cint, flt
)
import json
import requests
from collections import defaultdict


class Visitor(Document):
    """
    Visitor Controller
    Manages new visitors with automated follow-up, multi-channel messaging, and conversion tracking
    """
    
    def validate(self):
        """Validate before saving"""
        self.set_full_name()
        self.validate_contact_info()
        self.calculate_age()
        self.assign_demographic_group()
        self.validate_dates()
        self.set_defaults()
    
    def before_save(self):
        """Before save operations"""
        self.track_status_changes()
    
    def on_update(self):
        """After save operations"""
        self.check_auto_welcome_message()
        self.update_conversion_metrics()
    
    def set_full_name(self):
        """Set full name from first and last names"""
        if self.first_name:
            parts = [self.first_name, self.last_name] if self.last_name else [self.first_name]
            self.full_name = " ".join(parts)
    
    def validate_contact_info(self):
        """Validate contact information"""
        if not self.mobile_phone and not self.email:
            frappe.msgprint(
                _("Warning: Visitor has no contact information. Follow-up will be difficult."),
                indicator='orange',
                alert=True
            )
        
        # Validate email format
        if self.email:
            import re
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_pattern, self.email):
                frappe.throw(_("Invalid email format"))
        
        # Format phone number
        if self.mobile_phone:
            self.mobile_phone = format_phone_number(self.mobile_phone)
    
    def calculate_age(self):
        """Calculate age from date of birth"""
        if not self.date_of_birth:
            self.age = None
            return
        
        dob = getdate(self.date_of_birth)
        today = getdate()
        
        age = today.year - dob.year
        if (today.month, today.day) < (dob.month, dob.day):
            age -= 1
        
        self.age = max(0, age)
    
    def assign_demographic_group(self):
        """Assign demographic group based on Church Settings rules"""
        if not self.age or not self.gender:
            return
        
        # Get demographic rules from Church Settings
        rules = frappe.get_all(
            "Demographic Group Rule",
            filters={
                "parenttype": "Church Settings",
                "parent": "Church Settings"
            },
            fields=["member_group", "gender", "min_age", "max_age", "priority"],
            order_by="priority desc"
        )
        
        for rule in rules:
            min_age = cint(rule.min_age) if rule.min_age else 0
            max_age = cint(rule.max_age) if rule.max_age else 999
            
            if min_age <= self.age <= max_age:
                if rule.gender == "Both" or rule.gender == self.gender:
                    self.demographic_group = rule.member_group
                    return
    
    def validate_dates(self):
        """Validate date fields"""
        if self.date_of_visit and getdate(self.date_of_visit) > getdate(nowdate()):
            frappe.throw(_("Date of Visit cannot be in the future"))
        
        if self.date_of_birth and getdate(self.date_of_birth) > getdate(nowdate()):
            frappe.throw(_("Date of Birth cannot be in the future"))
        
        if self.follow_up_date and self.date_of_visit:
            if getdate(self.follow_up_date) < getdate(self.date_of_visit):
                frappe.throw(_("Follow-up Date cannot be before Date of Visit"))
    
    def set_defaults(self):
        """Set default values"""
        if not self.date_of_visit:
            self.date_of_visit = nowdate()
        
        if not self.conversion_status:
            self.conversion_status = 'New Visitor'
        
        if not self.branch:
            settings = frappe.get_single('Church Settings')
            if settings.default_branch:
                self.branch = settings.default_branch
        
        # Set default follow-up date (7 days from visit)
        if not self.follow_up_date and self.date_of_visit:
            self.follow_up_date = add_days(self.date_of_visit, 7)
    
    def track_status_changes(self):
        """Track conversion status changes"""
        if self.is_new():
            return
        
        old_doc = self.get_doc_before_save()
        if not old_doc:
            return
        
        if old_doc.conversion_status != self.conversion_status:
            # Log status change
            self.append('status_history', {
                'from_status': old_doc.conversion_status,
                'to_status': self.conversion_status,
                'change_date': nowdate(),
                'changed_by': frappe.session.user,
                'remarks': f'Status changed from {old_doc.conversion_status} to {self.conversion_status}'
            })
            
            # Log significant status changes
            frappe.logger().info(
                f"Visitor {self.full_name} status: {old_doc.conversion_status} → {self.conversion_status}"
            )
    
    def check_auto_welcome_message(self):
        """Check if automatic welcome message should be sent"""
        if self.is_new():
            settings = frappe.get_single('Church Settings')
            
            # Send welcome message if enabled and visitor is new
            if settings.get('auto_send_visitor_welcome') and self.conversion_status == 'New Visitor':
                # Queue for background sending
                frappe.enqueue(
                    'church.church.doctype.visitor.visitor.send_welcome_message',
                    visitor=self.name,
                    queue='short',
                    timeout=300
                )
    
    def update_conversion_metrics(self):
        """Update conversion tracking metrics"""
        # Calculate days since visit
        if self.date_of_visit:
            self.days_since_visit = date_diff(nowdate(), self.date_of_visit)
        
        # Set converted date if status changed to Converted
        if self.conversion_status == 'Converted to Member' and not self.converted_date:
            self.converted_date = nowdate()
            
            # Calculate conversion time
            if self.date_of_visit:
                self.days_to_conversion = date_diff(self.converted_date, self.date_of_visit)


# ============================================================================
# MULTI-CHANNEL MESSAGING SYSTEM
# ============================================================================

@frappe.whitelist()
def send_welcome_message(visitor):
    """
    Send welcome message to new visitor with robust error handling
    Multi-channel delivery: Email, SMS, WhatsApp
    """
    try:
        doc = frappe.get_doc('Visitor', visitor)
        settings = frappe.get_single('Church Settings')
        
        # Validate contact information
        if not doc.mobile_phone and not doc.email:
            return {
                'success': False,
                'message': _('No contact information available for {0}').format(doc.full_name)
            }
        
        # Generate messages
        message_html, message_plain = generate_welcome_message(doc, settings)
        
        # Track results
        sent_channels = []
        failed_channels = []
        
        # Send via Email
        if doc.email:
            email_result = send_email_safely(doc, message_html, settings)
            if email_result['success']:
                sent_channels.append('Email')
            else:
                failed_channels.append(f"Email: {email_result.get('error', 'Unknown error')}")
        
        # Send via SMS
        if doc.mobile_phone:
            sms_result = send_sms_safely(doc, message_plain, settings)
            if sms_result['success']:
                sent_channels.append('SMS')
            else:
                failed_channels.append(f"SMS: {sms_result.get('error', 'Not configured or failed')}")
        
        # Send via WhatsApp
        if doc.mobile_phone:
            whatsapp_result = send_whatsapp_safely(doc, message_plain, settings)
            if whatsapp_result['success']:
                sent_channels.append('WhatsApp')
            else:
                failed_channels.append(f"WhatsApp: {whatsapp_result.get('error', 'Not configured or failed')}")
        
        # Update visitor status if any message sent
        if sent_channels:
            if doc.conversion_status == 'New Visitor':
                doc.db_set('conversion_status', 'In Follow-up', update_modified=False)
            
            # Mark welcome message as sent
            doc.db_set('welcome_message_sent', 1, update_modified=False)
            doc.db_set('welcome_message_date', now_datetime(), update_modified=False)
            
            # Log communication
            log_visitor_communication(doc, sent_channels)
            
            message = _('Welcome message sent via: {0}').format(', '.join(sent_channels))
            if failed_channels:
                message += _('\n\nFailed: {0}').format('; '.join(failed_channels))
            
            return {'success': True, 'message': message, 'channels': sent_channels}
        else:
            error_msg = _('Failed to send via all channels:\n{0}').format('\n'.join(failed_channels))
            frappe.log_error(
                message=f"All channels failed for visitor {doc.full_name}:\n{error_msg}",
                title="Welcome Message Complete Failure"
            )
            return {'success': False, 'message': error_msg}
            
    except Exception as e:
        frappe.log_error(
            message=frappe.get_traceback(),
            title=f"Welcome Message Error - {visitor}"
        )
        return {
            'success': False,
            'message': _('System error: {0}').format(str(e))
        }


def send_email_safely(visitor_doc, message_html, settings):
    """Send email with comprehensive error handling"""
    try:
        # Check if email is enabled
        if not settings.get('email_notifications_enabled'):
            return {'success': False, 'error': 'Email notifications disabled in settings'}
        
        # Validate email configuration
        if not frappe.get_value('Email Account', {'enable_outgoing': 1}, 'name'):
            return {'success': False, 'error': 'No outgoing email account configured'}
        
        church_name = settings.church_name or "Our Church"
        subject = f"Welcome to {church_name}!"
        
        frappe.sendmail(
            recipients=[visitor_doc.email],
            subject=subject,
            message=message_html,
            delayed=False,
            now=True,
            reference_doctype='Visitor',
            reference_name=visitor_doc.name
        )
        
        return {'success': True}
        
    except Exception as e:
        error_msg = str(e)
        frappe.log_error(
            message=f"Email to {visitor_doc.email} failed: {error_msg}\n{frappe.get_traceback()}",
            title="Visitor Email Error"
        )
        return {'success': False, 'error': error_msg}


def send_sms_safely(visitor_doc, message_plain, settings):
    """Send SMS with error handling and provider validation"""
    try:
        # Check if SMS is enabled
        if not settings.get('sms_notifications_enabled'):
            return {'success': False, 'error': 'SMS notifications disabled'}
        
        # Get SMS provider
        sms_provider = settings.get('sms_provider')
        
        if not sms_provider:
            return {'success': False, 'error': 'No SMS provider configured in Church Settings'}
        
        # Validate phone number format
        phone = format_phone_number(visitor_doc.mobile_phone)
        if not phone:
            return {'success': False, 'error': 'Invalid phone number format'}
        
        # Send via configured provider
        if sms_provider == 'Twilio':
            return send_sms_via_twilio(phone, message_plain, settings)
        elif sms_provider == 'Termii':
            return send_sms_via_termii(phone, message_plain, settings)
        elif sms_provider == "Africa's Talking":
            return send_sms_via_africastalking(phone, message_plain, settings)
        else:
            return {'success': False, 'error': f'Unknown SMS provider: {sms_provider}'}
            
    except Exception as e:
        frappe.log_error(
            message=f"SMS system error: {str(e)}\n{frappe.get_traceback()}",
            title="Visitor SMS Error"
        )
        return {'success': False, 'error': str(e)}


def send_whatsapp_safely(visitor_doc, message_plain, settings):
    """Send WhatsApp with error handling and provider validation"""
    try:
        # Check if WhatsApp is enabled
        if not settings.get('whatsapp_notifications_enabled'):
            return {'success': False, 'error': 'WhatsApp notifications disabled'}
        
        # Get WhatsApp provider
        whatsapp_provider = settings.get('whatsapp_provider')
        
        if not whatsapp_provider:
            return {'success': False, 'error': 'No WhatsApp provider configured in Church Settings'}
        
        # Validate phone number format
        phone = format_phone_number(visitor_doc.mobile_phone)
        if not phone:
            return {'success': False, 'error': 'Invalid phone number format'}
        
        # Send via configured provider
        if whatsapp_provider == 'Twilio':
            return send_whatsapp_via_twilio(phone, message_plain, settings)
        elif whatsapp_provider == '360Dialog':
            return send_whatsapp_via_360dialog(phone, message_plain, settings)
        elif whatsapp_provider == 'Wati':
            return send_whatsapp_via_wati(phone, message_plain, settings)
        else:
            return {'success': False, 'error': f'Unknown WhatsApp provider: {whatsapp_provider}'}
            
    except Exception as e:
        frappe.log_error(
            message=f"WhatsApp system error: {str(e)}\n{frappe.get_traceback()}",
            title="Visitor WhatsApp Error"
        )
        return {'success': False, 'error': str(e)}


# ============================================================================
# SMS PROVIDERS - Robust implementations
# ============================================================================

def send_sms_via_twilio(phone, message, settings):
    """Send SMS via Twilio with validation"""
    try:
        # Validate credentials
        account_sid = settings.get('twilio_account_sid')
        auth_token = settings.get_password('twilio_auth_token')
        from_number = settings.get('twilio_phone_number')
        
        if not all([account_sid, auth_token, from_number]):
            return {
                'success': False,
                'error': 'Twilio credentials incomplete. Check Church Settings: Account SID, Auth Token, Phone Number'
            }
        
        # Send via Twilio
        from twilio.rest import Client
        client = Client(account_sid, auth_token)
        
        result = client.messages.create(
            from_=from_number,
            body=message[:1600],  # Twilio limit
            to=phone
        )
        
        if result.sid:
            return {'success': True, 'message_id': result.sid}
        else:
            return {'success': False, 'error': 'No SID returned from Twilio'}
            
    except Exception as e:
        error_msg = str(e)
        frappe.log_error(
            message=f"Twilio SMS failed: {error_msg}\nPhone: {phone}\n{frappe.get_traceback()}",
            title="Twilio SMS Error"
        )
        return {'success': False, 'error': f'Twilio error: {error_msg}'}


def send_sms_via_termii(phone, message, settings):
    """Send SMS via Termii with validation"""
    try:
        # Validate credentials
        api_key = settings.get_password('termii_api_key')
        sender_id = settings.get('termii_sender_id')
        channel = settings.get('termii_channel') or 'generic'
        
        if not all([api_key, sender_id]):
            return {
                'success': False,
                'error': 'Termii credentials incomplete. Check Church Settings: API Key, Sender ID'
            }
        
        # Prepare request
        url = "https://api.ng.termii.com/api/sms/send"
        
        payload = {
            "to": phone,
            "from": sender_id,
            "sms": message[:1000],  # Termii recommended limit
            "type": "plain",
            "channel": channel,
            "api_key": api_key
        }
        
        headers = {
            "Content-Type": "application/json"
        }
        
        # Send request
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        
        # Handle response
        if response.status_code == 200:
            result = response.json()
            if result.get('message_id'):
                return {'success': True, 'message_id': result.get('message_id')}
            else:
                return {'success': False, 'error': f"Termii returned no message ID: {result}"}
        
        elif response.status_code == 401:
            return {
                'success': False,
                'error': 'Termii authentication failed. Check API Key in Church Settings'
            }
        
        elif response.status_code == 400:
            error_data = response.json()
            return {
                'success': False,
                'error': f"Termii validation error: {error_data.get('message', 'Invalid request')}"
            }
        
        else:
            return {
                'success': False,
                'error': f'Termii returned status {response.status_code}: {response.text[:200]}'
            }
            
    except requests.Timeout:
        return {'success': False, 'error': 'Termii request timed out'}
    
    except requests.ConnectionError:
        return {'success': False, 'error': 'Could not connect to Termii API'}
    
    except Exception as e:
        error_msg = str(e)
        frappe.log_error(
            message=f"Termii SMS failed: {error_msg}\nPhone: {phone}\n{frappe.get_traceback()}",
            title="Termii SMS Error"
        )
        return {'success': False, 'error': f'Termii error: {error_msg}'}


def send_sms_via_africastalking(phone, message, settings):
    """Send SMS via Africa's Talking with validation"""
    try:
        # Validate credentials
        username = settings.get('africastalking_username')
        api_key = settings.get_password('africastalking_api_key')
        sender_id = settings.get('africastalking_sender_id')
        
        if not all([username, api_key]):
            return {
                'success': False,
                'error': "Africa's Talking credentials incomplete. Check Church Settings: Username, API Key"
            }
        
        # Prepare request
        url = "https://api.africastalking.com/version1/messaging"
        
        headers = {
            "apiKey": api_key,
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json"
        }
        
        data = {
            "username": username,
            "to": phone,
            "message": message[:800],  # AT recommended limit
        }
        
        if sender_id:
            data['from'] = sender_id
        
        # Send request
        response = requests.post(url, headers=headers, data=data, timeout=10)
        
        # Handle response
        if response.status_code == 201:
            result = response.json()
            recipients = result.get('SMSMessageData', {}).get('Recipients', [])
            if recipients and recipients[0].get('status') == 'Success':
                return {'success': True, 'message_id': recipients[0].get('messageId')}
            else:
                return {'success': False, 'error': f"Africa's Talking failed: {recipients}"}
        
        elif response.status_code == 401:
            return {
                'success': False,
                'error': "Africa's Talking authentication failed. Check API Key"
            }
        
        else:
            return {
                'success': False,
                'error': f"Africa's Talking returned status {response.status_code}: {response.text[:200]}"
            }
            
    except Exception as e:
        error_msg = str(e)
        frappe.log_error(
            message=f"Africa's Talking SMS failed: {error_msg}\nPhone: {phone}\n{frappe.get_traceback()}",
            title="Africa's Talking SMS Error"
        )
        return {'success': False, 'error': f"Africa's Talking error: {error_msg}"}


# ============================================================================
# WHATSAPP PROVIDERS - Robust implementations
# ============================================================================

def send_whatsapp_via_twilio(phone, message, settings):
    """Send WhatsApp via Twilio with validation"""
    try:
        # Validate credentials
        account_sid = settings.get('twilio_whatsapp_account_sid') or settings.get('twilio_account_sid')
        auth_token = settings.get_password('twilio_whatsapp_auth_token') or settings.get_password('twilio_auth_token')
        from_number = settings.get('twilio_whatsapp_number')
        
        if not all([account_sid, auth_token, from_number]):
            return {
                'success': False,
                'error': 'Twilio WhatsApp credentials incomplete. Check Church Settings'
            }
        
        # Format numbers for WhatsApp
        from_whatsapp = f"whatsapp:{from_number}"
        to_whatsapp = f"whatsapp:{phone}"
        
        # Send via Twilio
        from twilio.rest import Client
        client = Client(account_sid, auth_token)
        
        result = client.messages.create(
            from_=from_whatsapp,
            body=message[:1600],
            to=to_whatsapp
        )
        
        if result.sid:
            return {'success': True, 'message_id': result.sid}
        else:
            return {'success': False, 'error': 'No SID returned from Twilio WhatsApp'}
            
    except Exception as e:
        error_msg = str(e)
        frappe.log_error(
            message=f"Twilio WhatsApp failed: {error_msg}\nPhone: {phone}\n{frappe.get_traceback()}",
            title="Twilio WhatsApp Error"
        )
        return {'success': False, 'error': f'Twilio WhatsApp error: {error_msg}'}


def send_whatsapp_via_360dialog(phone, message, settings):
    """Send WhatsApp via 360Dialog with validation"""
    try:
        # Validate credentials
        api_key = settings.get_password('dialog_360_api_key')
        
        if not api_key:
            return {
                'success': False,
                'error': '360Dialog API Key missing. Check Church Settings'
            }
        
        # Prepare request
        url = "https://waba.360dialog.io/v1/messages"
        
        headers = {
            "D360-API-KEY": api_key,
            "Content-Type": "application/json"
        }
        
        payload = {
            "to": phone.replace('+', ''),  # 360Dialog needs no +
            "type": "text",
            "text": {
                "body": message[:4096]  # WhatsApp limit
            }
        }
        
        # Send request
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        
        # Handle response
        if response.status_code == 201:
            result = response.json()
            return {'success': True, 'message_id': result.get('messages', [{}])[0].get('id')}
        
        elif response.status_code == 401:
            return {
                'success': False,
                'error': '360Dialog authentication failed. Check API Key'
            }
        
        else:
            return {
                'success': False,
                'error': f'360Dialog returned status {response.status_code}: {response.text[:200]}'
            }
            
    except Exception as e:
        error_msg = str(e)
        frappe.log_error(
            message=f"360Dialog WhatsApp failed: {error_msg}\nPhone: {phone}\n{frappe.get_traceback()}",
            title="360Dialog WhatsApp Error"
        )
        return {'success': False, 'error': f'360Dialog error: {error_msg}'}


def send_whatsapp_via_wati(phone, message, settings):
    """Send WhatsApp via Wati with validation"""
    try:
        # Validate credentials
        api_key = settings.get_password('wati_api_key')
        api_endpoint = settings.get('wati_api_endpoint')
        
        if not all([api_key, api_endpoint]):
            return {
                'success': False,
                'error': 'Wati credentials incomplete. Check Church Settings: API Key, Endpoint'
            }
        
        # Format phone (Wati needs clean number)
        clean_phone = phone.replace('+', '').replace(' ', '').replace('-', '')
        
        # Prepare request
        url = f"{api_endpoint}/api/v1/sendSessionMessage/{clean_phone}"
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "messageText": message[:4096]
        }
        
        # Send request
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        
        # Handle response
        if response.status_code == 200:
            result = response.json()
            if result.get('result'):
                return {'success': True, 'message_id': result.get('info', {}).get('messageId')}
            else:
                return {'success': False, 'error': f"Wati failed: {result.get('info')}"}
        
        elif response.status_code == 401:
            return {
                'success': False,
                'error': 'Wati authentication failed. Check API Key'
            }
        
        else:
            return {
                'success': False,
                'error': f'Wati returned status {response.status_code}: {response.text[:200]}'
            }
            
    except Exception as e:
        error_msg = str(e)
        frappe.log_error(
            message=f"Wati WhatsApp failed: {error_msg}\nPhone: {phone}\n{frappe.get_traceback()}",
            title="Wati WhatsApp Error"
        )
        return {'success': False, 'error': f'Wati error: {error_msg}'}


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def format_phone_number(phone):
    """Format phone number to international format"""
    if not phone:
        return None
    
    # Remove all non-digit characters except +
    phone = ''.join(c for c in phone if c.isdigit() or c == '+')
    
    # Ensure starts with +
    if not phone.startswith('+'):
        # Assume Nigerian number if no country code
        if len(phone) == 11 and phone.startswith('0'):
            phone = '+234' + phone[1:]
        elif len(phone) == 10:
            phone = '+234' + phone
        else:
            phone = '+' + phone
    
    # Validate length (should be 10-15 digits)
    digits = ''.join(c for c in phone if c.isdigit())
    if len(digits) < 10 or len(digits) > 15:
        return None
    
    return phone


def log_visitor_communication(visitor_doc, channels):
    """Log communication record"""
    try:
        frappe.get_doc({
            'doctype': 'Communication',
            'communication_type': 'Communication',
            'communication_medium': ', '.join(channels),
            'sent_or_received': 'Sent',
            'reference_doctype': 'Visitor',
            'reference_name': visitor_doc.name,
            'subject': f'Welcome Message - {visitor_doc.full_name}',
            'content': f'Welcome message sent via: {", ".join(channels)}',
            'sender': frappe.session.user,
            'status': 'Sent'
        }).insert(ignore_permissions=True)
    except Exception as e:
        # Don't fail the whole process if logging fails
        frappe.log_error(
            message=f"Failed to log communication: {str(e)}",
            title="Communication Log Error"
        )


def generate_welcome_message(visitor, settings):
    """Generate personalized welcome message (HTML and plain text)"""
    church_name = settings.church_name or "Our Church"
    
    # HTML version (for email)
    message_html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; background-color: #f8f9fa; border-radius: 10px;">
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; border-radius: 10px 10px 0 0; text-align: center;">
            <h1 style="color: white; margin: 0; font-size: 28px;">Welcome to {church_name}!</h1>
        </div>
        
        <div style="background: white; padding: 30px; border-radius: 0 0 10px 10px;">
            <p style="font-size: 18px; color: #2c3e50; margin-bottom: 5px;">Dear <strong>{visitor.full_name}</strong>,</p>
            
            <p style="font-size: 16px; color: #34495e; line-height: 1.6;">
                We are absolutely delighted that you visited us on <strong>{formatdate(visitor.date_of_visit, 'dd MMM yyyy')}</strong>! 
                Your presence blessed us, and we hope you felt the warmth of God's love and our church family.
            </p>
            
            <div style="background: #e8f4fd; padding: 20px; border-radius: 8px; margin: 25px 0; border-left: 4px solid #3498db;">
                <h3 style="color: #2980b9; margin-top: 0; margin-bottom: 15px;">What's Next?</h3>
                <ul style="margin: 0; padding-left: 20px; color: #2c3e50; line-height: 1.8;">
                    <li>Join us for our next service - we'd love to see you again!</li>
                    <li>Connect with our community and make new friends</li>
                    <li>Explore opportunities to serve and grow in faith</li>
                    <li>Reach out to us anytime - we're here for you!</li>
                </ul>
            </div>
            
            {f'''<div style="background: #fff8e1; padding: 15px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #f39c12;">
                <p style="margin: 0; color: #8b6914; font-size: 14px;"><strong>🙏 Prayer Request:</strong> {visitor.prayer_requests}</p>
                <p style="margin: 10px 0 0 0; color: #8b6914; font-size: 13px; font-style: italic;">We are praying for you!</p>
            </div>''' if visitor.get('prayer_requests') else ''}
            
            <div style="background: #e8f8f5; padding: 15px; border-radius: 8px; margin: 20px 0; text-align: center;">
                <p style="margin: 0; color: #16a085; font-size: 15px; font-style: italic;">
                    "For where two or three gather in my name, there am I with them."
                    <br><strong>- Matthew 18:20</strong>
                </p>
            </div>
            
            <p style="font-size: 15px; color: #34495e; line-height: 1.6; margin-top: 25px;">
                If you have any questions or would like to know more about our church, please don't hesitate to reach out. 
                We're excited to journey with you in faith!
            </p>
            
            <p style="font-size: 15px; color: #34495e; margin-top: 25px;">
                God bless you abundantly,<br>
                <strong>{church_name} Family</strong>
            </p>
        </div>
        
        <div style="text-align: center; padding: 20px; color: #7f8c8d; font-size: 12px;">
            <p style="margin: 5px 0;">You're receiving this because you visited {church_name}</p>
            <p style="margin: 5px 0;">We respect your privacy and will never share your information</p>
        </div>
    </div>
    """
    
    # Plain text version (for SMS/WhatsApp)
    prayer_text = f"\n\nPRAYER REQUEST: {visitor.prayer_requests}\nWe are praying for you!" if visitor.get('prayer_requests') else ''
    
    message_plain = f"""Dear {visitor.full_name},

Welcome to {church_name}!

We are delighted that you visited us on {formatdate(visitor.date_of_visit, 'dd MMM yyyy')}! Your presence blessed us.

WHAT'S NEXT?
• Join us for our next service
• Connect with our community
• Explore opportunities to serve
• Reach out anytime - we're here for you!{prayer_text}

"For where two or three gather in my name, there am I with them." - Matthew 18:20

God bless you abundantly,
{church_name} Family"""
    
    return message_html, message_plain


# ============================================================================
# VISITOR ANALYTICS & REPORTING
# ============================================================================

@frappe.whitelist()
def get_visitor_statistics(filters=None):
    """
    Get comprehensive visitor statistics
    
    Returns:
        dict: Complete visitor analytics
    """
    try:
        if filters and isinstance(filters, str):
            filters = json.loads(filters)
        
        if not filters:
            filters = {}
        
        visitors = frappe.get_all(
            'Visitor',
            filters=filters,
            fields=[
                'name', 'full_name', 'gender', 'age', 'demographic_group',
                'date_of_visit', 'conversion_status', 'branch',
                'invited_by', 'follow_up_date', 'days_since_visit'
            ]
        )
        
        stats = {
            'total': len(visitors),
            'by_gender': defaultdict(int),
            'by_status': defaultdict(int),
            'by_branch': defaultdict(int),
            'by_demographic': defaultdict(int),
            'by_invite_source': defaultdict(int),
            'age_distribution': {
                '0-12': 0,
                '13-17': 0,
                '18-35': 0,
                '36-59': 0,
                '60+': 0
            },
            'recent_visitors': 0,  # Last 7 days
            'needs_followup': 0,
            'converted': 0,
            'conversion_rate': 0
        }
        
        seven_days_ago = add_days(nowdate(), -7)
        
        for visitor in visitors:
            # Gender
            if visitor.gender:
                stats['by_gender'][visitor.gender] += 1
            
            # Status
            if visitor.conversion_status:
                stats['by_status'][visitor.conversion_status] += 1
            
            # Branch
            if visitor.branch:
                stats['by_branch'][visitor.branch] += 1
            
            # Demographic
            if visitor.demographic_group:
                stats['by_demographic'][visitor.demographic_group] += 1
            
            # Invite source
            if visitor.invited_by:
                stats['by_invite_source'][visitor.invited_by] += 1
            
            # Age distribution
            if visitor.age:
                if visitor.age <= 12:
                    stats['age_distribution']['0-12'] += 1
                elif visitor.age <= 17:
                    stats['age_distribution']['13-17'] += 1
                elif visitor.age <= 35:
                    stats['age_distribution']['18-35'] += 1
                elif visitor.age <= 59:
                    stats['age_distribution']['36-59'] += 1
                else:
                    stats['age_distribution']['60+'] += 1
            
            # Recent visitors
            if visitor.date_of_visit and getdate(visitor.date_of_visit) >= getdate(seven_days_ago):
                stats['recent_visitors'] += 1
            
            # Needs follow-up
            if visitor.follow_up_date and getdate(visitor.follow_up_date) <= getdate(nowdate()):
                if visitor.conversion_status not in ['Converted to Member', 'Not Interested']:
                    stats['needs_followup'] += 1
            
            # Converted
            if visitor.conversion_status == 'Converted to Member':
                stats['converted'] += 1
        
        # Calculate conversion rate
        if stats['total'] > 0:
            stats['conversion_rate'] = round((stats['converted'] / stats['total']) * 100, 1)
        
        # Convert defaultdicts to regular dicts
        stats['by_gender'] = dict(stats['by_gender'])
        stats['by_status'] = dict(stats['by_status'])
        stats['by_branch'] = dict(stats['by_branch'])
        stats['by_demographic'] = dict(stats['by_demographic'])
        stats['by_invite_source'] = dict(stats['by_invite_source'])
        
        return {
            'success': True,
            'statistics': stats
        }
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Visitor Statistics Error")
        return {
            'success': False,
            'error': str(e)
        }


@frappe.whitelist()
def bulk_send_welcome_messages(filters=None):
    """
    Send welcome messages to multiple visitors in bulk
    
    Args:
        filters: Visitor filters (default: New Visitors without welcome message)
    
    Returns:
        dict: Sending statistics
    """
    try:
        if filters and isinstance(filters, str):
            filters = json.loads(filters)
        
        if not filters:
            filters = {
                'conversion_status': 'New Visitor',
                'welcome_message_sent': 0
            }
        
        visitors = frappe.get_all('Visitor', filters=filters, pluck='name')
        
        sent = 0
        failed = 0
        
        for visitor_name in visitors:
            result = send_welcome_message(visitor_name)
            if result.get('success'):
                sent += 1
            else:
                failed += 1
        
        return {
            'success': True,
            'sent': sent,
            'failed': failed,
            'total': len(visitors),
            'message': _(f'Sent welcome messages to {sent} visitors ({failed} failed)')
        }
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Bulk Welcome Message Error")
        return {
            'success': False,
            'error': str(e)
        }


@frappe.whitelist()
def test_messaging_setup():
    """
    Test messaging configuration
    Returns status of all configured providers
    """
    settings = frappe.get_single('Church Settings')
    
    results = {
        'email': test_email_config(settings),
        'sms': test_sms_config(settings),
        'whatsapp': test_whatsapp_config(settings)
    }
    
    return results


def test_email_config(settings):
    """Test email configuration"""
    if not settings.get('email_notifications_enabled'):
        return {'configured': False, 'status': 'Disabled in settings'}
    
    email_account = frappe.get_value('Email Account', {'enable_outgoing': 1}, 'name')
    if email_account:
        return {'configured': True, 'status': f'Using account: {email_account}'}
    else:
        return {'configured': False, 'status': 'No outgoing email account configured'}


def test_sms_config(settings):
    """Test SMS configuration"""
    if not settings.get('sms_notifications_enabled'):
        return {'configured': False, 'status': 'Disabled in settings'}
    
    provider = settings.get('sms_provider')
    if not provider:
        return {'configured': False, 'status': 'No SMS provider selected'}
    
    if provider == 'Twilio':
        if all([settings.get('twilio_account_sid'), settings.get_password('twilio_auth_token'), settings.get('twilio_phone_number')]):
            return {'configured': True, 'status': f'Twilio configured'}
        else:
            return {'configured': False, 'status': 'Twilio credentials incomplete'}
    
    elif provider == 'Termii':
        if all([settings.get_password('termii_api_key'), settings.get('termii_sender_id')]):
            return {'configured': True, 'status': 'Termii configured'}
        else:
            return {'configured': False, 'status': 'Termii credentials incomplete'}
    
    elif provider == "Africa's Talking":
        if all([settings.get('africastalking_username'), settings.get_password('africastalking_api_key')]):
            return {'configured': True, 'status': "Africa's Talking configured"}
        else:
            return {'configured': False, 'status': "Africa's Talking credentials incomplete"}
    
    return {'configured': False, 'status': f'Unknown provider: {provider}'}


def test_whatsapp_config(settings):
    """Test WhatsApp configuration"""
    if not settings.get('whatsapp_notifications_enabled'):
        return {'configured': False, 'status': 'Disabled in settings'}
    
    provider = settings.get('whatsapp_provider')
    if not provider:
        return {'configured': False, 'status': 'No WhatsApp provider selected'}
    
    if provider == 'Twilio':
        if all([settings.get('twilio_whatsapp_number'), settings.get_password('twilio_whatsapp_auth_token')]):
            return {'configured': True, 'status': 'Twilio WhatsApp configured'}
        else:
            return {'configured': False, 'status': 'Twilio WhatsApp credentials incomplete'}
    
    elif provider == '360Dialog':
        if settings.get_password('dialog_360_api_key'):
            return {'configured': True, 'status': '360Dialog configured'}
        else:
            return {'configured': False, 'status': '360Dialog API Key missing'}
    
    elif provider == 'Wati':
        if all([settings.get_password('wati_api_key'), settings.get('wati_api_endpoint')]):
            return {'configured': True, 'status': 'Wati configured'}
        else:
            return {'configured': False, 'status': 'Wati credentials incomplete'}
    
    return {'configured': False, 'status': f'Unknown provider: {provider}'}


# ============================================================================
# SCHEDULED JOBS
# ============================================================================

def send_daily_followup_reminders():
    """
    Send daily reminders for visitors needing follow-up
    Run via scheduler
    """
    try:
        today = nowdate()
        
        # Get visitors with follow-up due today
        visitors_due = frappe.get_all(
            'Visitor',
            filters={
                'follow_up_date': today,
                'conversion_status': ['not in', ['Converted to Member', 'Not Interested']]
            },
            fields=['name', 'full_name', 'assigned_to']
        )
        
        # Send notification to assigned staff
        for visitor in visitors_due:
            if visitor.assigned_to:
                frappe.publish_realtime(
                    event='follow_up_reminder',
                    message={
                        'visitor': visitor.name,
                        'visitor_name': visitor.full_name,
                        'message': f'Follow-up due today for {visitor.full_name}'
                    },
                    user=visitor.assigned_to
                )
        
        frappe.logger().info(f"Sent {len(visitors_due)} follow-up reminders")
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Follow-up Reminder Error")