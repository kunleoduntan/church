# -*- coding: utf-8 -*-
# Copyright (c) 2026, Church Management
# For license information, please see license.txt

"""
WhatsApp Webhook Handler
Receives incoming WhatsApp messages for attendance check-in
"""

import frappe
from frappe import _
import json
from ecclesia.attendance.smart_attendance import (
    mark_attendance,
    verify_location,
    get_current_service,
    is_within_checkin_window
)

# ============================================================================
# WHATSAPP WEBHOOK
# ============================================================================

@frappe.whitelist(allow_guest=True)
def whatsapp_webhook():
    """
    Handle incoming WhatsApp messages
    Endpoint: /api/method/ecclesia.attendance.whatsapp_handler.whatsapp_webhook
    """
    
    try:
        # Get request data
        data = frappe.request.get_json() if frappe.request.is_json else frappe.local.form_dict
        
        # Log incoming webhook
        frappe.log_error(json.dumps(data, indent=2), "WhatsApp Webhook Received")
        
        # Verify webhook (for setup)
        if frappe.request.method == 'GET':
            return verify_webhook()
        
        # Process incoming message
        if 'messages' in data or 'message' in data:
            process_whatsapp_message(data)
            return {'status': 'success'}
        
        return {'status': 'ignored'}
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "WhatsApp Webhook Error")
        return {'status': 'error', 'message': str(e)}


def verify_webhook():
    """Verify webhook for WhatsApp Business API setup"""
    
    mode = frappe.local.form_dict.get('hub.mode')
    token = frappe.local.form_dict.get('hub.verify_token')
    challenge = frappe.local.form_dict.get('hub.challenge')
    
    settings = frappe.get_single('Church Settings')
    verify_token = settings.get_password('whatsapp_api_token')
    
    if mode == 'subscribe' and token == verify_token:
        return challenge
    
    frappe.throw(_("Verification failed"))


def process_whatsapp_message(data):
    """Process incoming WhatsApp message for attendance"""
    
    try:
        settings = frappe.get_single('Church Settings')
        
        if not settings.enable_whatsapp_attendance:
            return
        
        # Extract message details (format varies by provider)
        message_data = extract_message_data(data)
        
        if not message_data:
            return
        
        phone_number = message_data['phone']
        message_text = message_data['text'].strip()
        message_type = message_data.get('type', 'text')
        
        # Find member by phone number
        member = find_member_by_phone(phone_number)
        
        if not member:
            send_whatsapp_reply(phone_number, 
                "❌ Phone number not registered. Please contact church admin.", 
                settings)
            return
        
        # Check if member has WhatsApp check-in enabled
        if not member.enable_whatsapp_check_in:
            send_whatsapp_reply(phone_number,
                "WhatsApp check-in is not enabled for your account. Please enable it in your member profile.",
                settings)
            return
        
        # Get current service
        service = get_current_service()
        
        if not service:
            send_whatsapp_reply(phone_number,
                "❌ No active service at this time. Check-in is only available during service hours.",
                settings)
            return
        
        # Check service window
        if not is_within_checkin_window(service, settings):
            send_whatsapp_reply(phone_number,
                "❌ Check-in window has closed for this service.",
                settings)
            return
        
        # Process based on verification method
        verification_method = settings.whatsapp_verification_method
        
        if verification_method == "Daily Code Required":
            process_code_checkin(member, message_text, service, phone_number, settings)
            
        elif verification_method == "Location Share Required":
            if message_type == 'location':
                process_location_checkin(member, message_data, service, phone_number, settings)
            else:
                # Request location
                request_location_share(phone_number, settings)
                
        elif verification_method == "Time Window Only":
            # Just check in without additional verification
            result = mark_attendance(
                member_id=member.name,
                service_instance=service,
                checkin_method='WhatsApp',
                device_info=f"WhatsApp {phone_number}"
            )
            
            if result['success']:
                send_whatsapp_reply(phone_number,
                    f"✅ {result['message']}",
                    settings)
            else:
                send_whatsapp_reply(phone_number,
                    f"❌ {result['message']}",
                    settings)
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "WhatsApp Message Processing Error")


def extract_message_data(data):
    """Extract message data from webhook payload (varies by provider)"""
    
    try:
        # WhatsApp Business API format
        if 'entry' in data:
            entry = data['entry'][0]
            changes = entry['changes'][0]
            value = changes['value']
            
            if 'messages' in value:
                message = value['messages'][0]
                
                return {
                    'phone': message['from'],
                    'text': message.get('text', {}).get('body', ''),
                    'type': message.get('type', 'text'),
                    'location': message.get('location', {})
                }
        
        # Twilio format
        elif 'From' in data:
            return {
                'phone': data['From'].replace('whatsapp:', ''),
                'text': data.get('Body', ''),
                'type': 'text',
                'location': {}
            }
        
        # 360Dialog format
        elif 'messages' in data:
            message = data['messages'][0]
            return {
                'phone': message['from'],
                'text': message.get('text', {}).get('body', ''),
                'type': message.get('type', 'text'),
                'location': message.get('location', {})
            }
        
        return None
        
    except Exception as e:
        frappe.log_error(f"Message extraction error: {str(e)}", "WhatsApp Data Extraction")
        return None


def process_code_checkin(member, message_text, service, phone_number, settings):
    """Process check-in with daily code verification"""
    
    # Get today's code
    daily_code = generate_daily_code(service)
    
    # Extract code from message
    # Expected format: "CODE123 Present" or just "CODE123"
    message_parts = message_text.upper().split()
    
    keyword = settings.whatsapp_check_in_keyword.upper()
    code_in_message = None
    
    # Check if message contains the keyword
    has_keyword = keyword in message_text.upper()
    
    # Find code in message
    for part in message_parts:
        if len(part) >= 6 and part != keyword:
            code_in_message = part
            break
    
    if not code_in_message:
        send_whatsapp_reply(phone_number,
            f"❌ Invalid format. Please send:\n\n*{daily_code} {keyword}*\n\nCheck the code on church screen.",
            settings)
        return
    
    # Verify code
    if code_in_message != daily_code:
        send_whatsapp_reply(phone_number,
            f"❌ Incorrect code. Today's code is:\n\n*{daily_code}*\n\nPlease try again.",
            settings)
        return
    
    # Mark attendance
    result = mark_attendance(
        member_id=member.name,
        service_instance=service,
        checkin_method='WhatsApp + Daily Code',
        device_info=f"WhatsApp {phone_number}"
    )
    
    if result['success']:
        send_whatsapp_reply(phone_number,
            f"✅ {result['message']}",
            settings)
    else:
        send_whatsapp_reply(phone_number,
            f"❌ {result['message']}",
            settings)


def process_location_checkin(member, message_data, service, phone_number, settings):
    """Process check-in with location verification"""
    
    location = message_data.get('location', {})
    
    if not location:
        request_location_share(phone_number, settings)
        return
    
    latitude = location.get('latitude')
    longitude = location.get('longitude')
    
    if not latitude or not longitude:
        send_whatsapp_reply(phone_number,
            "❌ Invalid location. Please share your live location.",
            settings)
        return
    
    # Verify location
    location_check = verify_location(float(latitude), float(longitude), settings)
    
    if not location_check['valid']:
        send_whatsapp_reply(phone_number,
            f"❌ You are {location_check['distance']:.0f}m from church. Please come closer to check in.",
            settings)
        return
    
    # Mark attendance
    result = mark_attendance(
        member_id=member.name,
        service_instance=service,
        checkin_method='WhatsApp + Location',
        latitude=latitude,
        longitude=longitude,
        device_info=f"WhatsApp {phone_number}"
    )
    
    if result['success']:
        send_whatsapp_reply(phone_number,
            f"✅ {result['message']}",
            settings)
    else:
        send_whatsapp_reply(phone_number,
            f"❌ {result['message']}",
            settings)


def request_location_share(phone_number, settings):
    """Ask member to share their location"""
    
    keyword = settings.whatsapp_check_in_keyword
    
    message = f"""
📍 Please share your live location to check in.

*How to share location:*
1. Tap the + icon
2. Select Location
3. Choose "Live Location"
4. Send

Or send: *CODE {keyword}*
(Get code from church screen)
    """
    
    send_whatsapp_reply(phone_number, message.strip(), settings)


def generate_daily_code(service):
    """Generate daily code for service"""
    
    import hashlib
    from frappe.utils import getdate, format_date
    
    service_doc = frappe.get_doc('Service Instance', service)
    
    # Create code based on service and date
    date_str = format_date(service_doc.service_date, "ddMM")
    service_name = service_doc.service_type.upper()[:5]
    
    # Generate hash
    hash_input = f"{service}{service_doc.service_date}"
    hash_code = hashlib.md5(hash_input.encode()).hexdigest()[:4].upper()
    
    return f"{service_name}{date_str}"


def find_member_by_phone(phone_number):
    """Find member by WhatsApp or phone number"""
    
    # Clean phone number
    clean_number = phone_number.replace('+', '').replace('-', '').replace(' ', '')
    
    # Try WhatsApp number first
    member = frappe.db.get_value('Member', 
        {'whatsapp_number': ['like', f'%{clean_number[-10:]}%']}, 
        '*', as_dict=True)
    
    if member:
        return frappe.get_doc('Member', member.name)
    
    # Try phone number
    member = frappe.db.get_value('Member',
        {'phone': ['like', f'%{clean_number[-10:]}%']},
        '*', as_dict=True)
    
    if member:
        return frappe.get_doc('Member', member.name)
    
    return None


def send_whatsapp_reply(phone_number, message, settings):
    """Send WhatsApp reply message"""
    
    from ecclesia.attendance.smart_attendance import send_whatsapp_message
    send_whatsapp_message(phone_number, message, settings)


# ============================================================================
# HELPER FUNCTIONS FOR DAILY CODE DISPLAY
# ============================================================================

@frappe.whitelist()
def get_daily_code(service_instance=None):
    """Get daily code for display on screen"""
    
    if not service_instance:
        service_instance = get_current_service()
    
    if not service_instance:
        return {'code': 'NO-SERVICE', 'message': 'No active service'}
    
    code = generate_daily_code(service_instance)
    
    service_doc = frappe.get_doc('Service Instance', service_instance)
    
    return {
        'code': code,
        'service': service_doc.service_type,
        'date': frappe.utils.format_date(service_doc.service_date),
        'message': f"Send via WhatsApp: {code} Present"
    }


@frappe.whitelist()
def get_whatsapp_checkin_instructions():
    """Get instructions for WhatsApp check-in"""
    
    settings = frappe.get_single('Church Settings')
    
    if not settings.enable_whatsapp_attendance:
        return {'enabled': False}
    
    daily_code = get_daily_code()
    
    instructions = {
        'enabled': True,
        'business_number': settings.whatsapp_business_number,
        'keyword': settings.whatsapp_check_in_keyword,
        'verification_method': settings.whatsapp_verification_method,
        'daily_code': daily_code.get('code'),
        'require_location': settings.whatsapp_require_location
    }
    
    if settings.whatsapp_verification_method == "Daily Code Required":
        instructions['message'] = f"Send to {settings.whatsapp_business_number}:\n{daily_code.get('code')} {settings.whatsapp_check_in_keyword}"
    elif settings.whatsapp_verification_method == "Location Share Required":
        instructions['message'] = f"Send '{settings.whatsapp_check_in_keyword}' then share your location"
    else:
        instructions['message'] = f"Send '{settings.whatsapp_check_in_keyword}' to check in"
    
    return instructions