# Copyright (c) 2026, kunle and contributors
# For license information, please see license.txt



from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe import _


class CommunicationSettings(Document):
    def validate(self):
        """Validation before saving"""
        self.validate_sms_configuration()
        self.validate_whatsapp_configuration()
    
    def validate_sms_configuration(self):
        """Validate SMS provider configuration"""
        if not self.enable_sms:
            self.sms_enabled = 0
            return
        
        if not self.sms_provider:
            self.sms_enabled = 0
            return
        
        is_valid = False
        
        if self.sms_provider == "Twilio":
            is_valid = self.twilio_account_sid and self.twilio_auth_token and self.twilio_from_number
            if not is_valid:
                frappe.msgprint(_("Please configure all Twilio SMS fields"), indicator='orange')
        
        elif self.sms_provider == "Nexmo/Vonage":
            is_valid = self.nexmo_api_key and self.nexmo_api_secret and self.nexmo_from_number
            if not is_valid:
                frappe.msgprint(_("Please configure all Nexmo/Vonage SMS fields"), indicator='orange')
        
        elif self.sms_provider == "Custom API":
            is_valid = self.custom_sms_api_endpoint and self.custom_sms_body_template
            if not is_valid:
                frappe.msgprint(_("Please configure Custom SMS API endpoint and body template"), indicator='orange')
        
        self.sms_enabled = 1 if is_valid else 0
    
    def validate_whatsapp_configuration(self):
        """Validate WhatsApp provider configuration"""
        if not self.enable_whatsapp:
            self.whatsapp_enabled = 0
            return
        
        if not self.whatsapp_provider:
            self.whatsapp_enabled = 0
            return
        
        is_valid = False
        
        if self.whatsapp_provider == "Twilio":
            is_valid = self.twilio_whatsapp_sid and self.twilio_whatsapp_token and self.twilio_whatsapp_number
            if not is_valid:
                frappe.msgprint(_("Please configure all Twilio WhatsApp fields"), indicator='orange')
        
        elif self.whatsapp_provider == "WATI":
            is_valid = self.wati_access_token and self.wati_number
            if not is_valid:
                frappe.msgprint(_("Please configure all WATI fields"), indicator='orange')
        
        elif self.whatsapp_provider == "Custom API":
            is_valid = self.custom_whatsapp_api_endpoint and self.custom_whatsapp_body_template
            if not is_valid:
                frappe.msgprint(_("Please configure Custom WhatsApp API endpoint and body template"), indicator='orange')
        
        self.whatsapp_enabled = 1 if is_valid else 0


@frappe.whitelist()
def test_sms_configuration(phone_number, message):
    """Test SMS configuration"""
    try:
        settings = frappe.get_single("Communication Settings")
        
        if not settings.enable_sms or not settings.sms_enabled:
            return {
                'success': False,
                'error': 'SMS is not enabled or properly configured'
            }
        
        provider = settings.sms_provider
        
        if provider == "Twilio":
            result = test_sms_twilio(phone_number, message, settings)
        elif provider == "Nexmo/Vonage":
            result = test_sms_nexmo(phone_number, message, settings)
        elif provider == "Custom API":
            result = test_sms_custom(phone_number, message, settings)
        else:
            return {
                'success': False,
                'error': 'Invalid SMS provider'
            }
        
        return {
            'success': True,
            'message_id': result
        }
        
    except Exception as e:
        frappe.log_error(f"SMS Test Error: {str(e)}", "SMS Test Error")
        return {
            'success': False,
            'error': str(e)
        }


def test_sms_twilio(phone_number, message, settings):
    """Test Twilio SMS"""
    from twilio.rest import Client
    
    client = Client(settings.twilio_account_sid, settings.get_password('twilio_auth_token'))
    
    message_obj = client.messages.create(
        body=message,
        from_=settings.twilio_from_number,
        to=phone_number
    )
    
    return message_obj.sid


def test_sms_nexmo(phone_number, message, settings):
    """Test Nexmo/Vonage SMS"""
    import vonage
    
    client = vonage.Client(
        key=settings.nexmo_api_key,
        secret=settings.get_password('nexmo_api_secret')
    )
    
    sms = vonage.Sms(client)
    
    response = sms.send_message({
        "from": settings.nexmo_from_number,
        "to": phone_number,
        "text": message
    })
    
    if response["messages"][0]["status"] == "0":
        return response["messages"][0]["message-id"]
    else:
        raise Exception(f"Nexmo Error: {response['messages'][0]['error-text']}")


def test_sms_custom(phone_number, message, settings):
    """Test Custom SMS API"""
    import requests
    import json
    
    headers = {}
    if settings.custom_sms_headers:
        headers = json.loads(settings.custom_sms_headers)
        headers = {k: v.replace('{api_key}', settings.get_password('custom_sms_api_key')) 
                  for k, v in headers.items()}
    
    body = {}
    if settings.custom_sms_body_template:
        body_template = settings.custom_sms_body_template
        body_str = body_template.replace('{phone_number}', phone_number)
        body_str = body_str.replace('{message}', message)
        body_str = body_str.replace('{api_key}', settings.get_password('custom_sms_api_key'))
        body = json.loads(body_str)
    
    if settings.custom_sms_method == "POST":
        response = requests.post(settings.custom_sms_api_endpoint, headers=headers, json=body)
    else:
        response = requests.get(settings.custom_sms_api_endpoint, headers=headers, params=body)
    
    if response.status_code in [200, 201]:
        return response.text
    else:
        raise Exception(f"API Error: {response.status_code} - {response.text}")


@frappe.whitelist()
def test_whatsapp_configuration(phone_number, message, image_url=None):
    """Test WhatsApp configuration"""
    try:
        settings = frappe.get_single("Communication Settings")
        
        if not settings.enable_whatsapp or not settings.whatsapp_enabled:
            return {
                'success': False,
                'error': 'WhatsApp is not enabled or properly configured'
            }
        
        provider = settings.whatsapp_provider
        
        if provider == "Twilio":
            result = test_whatsapp_twilio(phone_number, message, image_url, settings)
        elif provider == "WATI":
            result = test_whatsapp_wati(phone_number, message, image_url, settings)
        elif provider == "Custom API":
            result = test_whatsapp_custom(phone_number, message, image_url, settings)
        else:
            return {
                'success': False,
                'error': 'Invalid WhatsApp provider'
            }
        
        return {
            'success': True,
            'message_id': result
        }
        
    except Exception as e:
        frappe.log_error(f"WhatsApp Test Error: {str(e)}", "WhatsApp Test Error")
        return {
            'success': False,
            'error': str(e)
        }


def test_whatsapp_twilio(phone_number, message, image_url, settings):
    """Test Twilio WhatsApp"""
    from twilio.rest import Client
    
    client = Client(settings.twilio_whatsapp_sid, settings.get_password('twilio_whatsapp_token'))
    
    msg_params = {
        'body': message,
        'from_': f'whatsapp:{settings.twilio_whatsapp_number}',
        'to': f'whatsapp:{phone_number}'
    }
    
    if image_url:
        msg_params['media_url'] = [image_url]
    
    message_obj = client.messages.create(**msg_params)
    
    return message_obj.sid


def test_whatsapp_wati(phone_number, message, image_url, settings):
    """Test WATI WhatsApp"""
    import requests
    
    url = f"{settings.wati_api_endpoint}/api/v1/sendSessionMessage/{phone_number}"
    
    headers = {
        'Authorization': f'Bearer {settings.get_password("wati_access_token")}',
        'Content-Type': 'application/json'
    }
    
    payload = {
        'messageText': message
    }
    
    if image_url:
        payload['media'] = {
            'url': image_url
        }
    
    response = requests.post(url, headers=headers, json=payload)
    
    if response.status_code == 200:
        return response.json().get('messageId', 'success')
    else:
        raise Exception(f"WATI Error: {response.status_code} - {response.text}")


def test_whatsapp_custom(phone_number, message, image_url, settings):
    """Test Custom WhatsApp API"""
    import requests
    import json
    
    headers = {}
    if settings.custom_whatsapp_headers:
        headers = json.loads(settings.custom_whatsapp_headers)
        headers = {k: v.replace('{api_key}', settings.get_password('custom_whatsapp_api_key')) 
                  for k, v in headers.items()}
    
    body = {}
    if settings.custom_whatsapp_body_template:
        body_template = settings.custom_whatsapp_body_template
        body_str = body_template.replace('{phone_number}', phone_number)
        body_str = body_str.replace('{message}', message)
        body_str = body_str.replace('{image_url}', image_url or '')
        body_str = body_str.replace('{api_key}', settings.get_password('custom_whatsapp_api_key'))
        body = json.loads(body_str)
    
    if settings.custom_whatsapp_method == "POST":
        response = requests.post(settings.custom_whatsapp_api_endpoint, headers=headers, json=body)
    else:
        response = requests.get(settings.custom_whatsapp_api_endpoint, headers=headers, params=body)
    
    if response.status_code in [200, 201]:
        return response.text
    else:
        raise Exception(f"API Error: {response.status_code} - {response.text}")


@frappe.whitelist()
def test_email_configuration(email, subject, message):
    """Test Email configuration"""
    try:
        settings = frappe.get_single("Communication Settings")
        
        if not settings.enable_email:
            return {
                'success': False,
                'error': 'Email is not enabled'
            }
        
        frappe.sendmail(
            recipients=[email],
            subject=subject,
            message=message,
            reference_doctype="Communication Settings",
            reference_name="Communication Settings"
        )
        
        return {
            'success': True
        }
        
    except Exception as e:
        frappe.log_error(f"Email Test Error: {str(e)}", "Email Test Error")
        return {
            'success': False,
            'error': str(e)
        }