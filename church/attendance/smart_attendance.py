# Copyright (c) 2026, kunle and contributors
# For license information, please see license.txt

"""
Smart Attendance Module
Supports: WiFi Check-In, QR Code Scanning, Location Verification

Features:
- Auto-detect members on church WiFi
- Generate dynamic QR codes for venue scanning (points to /checkin landing page)
- Verify member GPS location
- Fraud detection and prevention
- WhatsApp/SMS confirmations
"""

import frappe
from urllib.parse import quote as _url_quote
from frappe import _
from frappe.utils import now_datetime, getdate, get_time, add_to_date, now
import hashlib
import qrcode
import io
import base64
import json
from math import radians, cos, sin, asin, sqrt
import requests


# ============================================================================
# QR CODE GENERATION
# ============================================================================

@frappe.whitelist(allow_guest=True)
def generate_venue_qr_code(service_instance=None):
    """
    Generate dynamic QR code for venue scanning.
    QR code changes based on refresh interval setting.
    Scanning the code opens the /checkin landing page on the member's phone.
    """
    try:
        settings = frappe.get_single('Church Settings')

        if not settings.enable_qr_checkin:
            frappe.throw(_("QR Code check-in is not enabled"))

        if not service_instance:
            service_instance = get_current_service()

        if not service_instance:
            frappe.throw(_("No active service found"))

        qr_data = generate_qr_data(service_instance, settings)

        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            box_size=10,
            border=4,
        )
        qr.add_data(qr_data['url'])
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")

        buffered = io.BytesIO()
        img.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode()

        return {
            'success': True,
            'qr_image': f'data:image/png;base64,{img_str}',
            'qr_code': qr_data['hash'],
            'service': service_instance,
            'valid_until': qr_data['valid_until'],
            'scan_url': qr_data['url']
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "QR Code Generation Error")
        return {'success': False, 'message': str(e)}


def generate_qr_data(service_instance, settings):
    """
    Generate QR code data with expiration.

    UPDATED: scan_url now points to the /checkin landing page instead of
    the raw API endpoint. The landing page handles both members and visitors:
      - Member found by phone → mark Church Attendance
      - Member not found     → show Visitor form → create Visitor record
    """
    interval_map = {
        '5 Minutes': 5,
        '10 Minutes': 10,
        '15 Minutes': 15,
        '30 Minutes': 30,
        '1 Hour': 60,
        'Once Per Service': 999
    }

    interval = interval_map.get(settings.qr_refresh_interval, 15)

    current_time = now_datetime()
    time_block = int(current_time.timestamp() / (interval * 60))

    hash_input = f"{service_instance}{time_block}{settings.church_name}"
    code_hash = hashlib.sha256(hash_input.encode()).hexdigest()[:12].upper()
    code = f"CHK-{code_hash}"

    site_url = frappe.utils.get_url()

    # ── UPDATED: opens the friendly landing page, not the raw API ──────────
    # /checkin is served from church/www/checkin.html
    # The page handles member lookup and visitor form automatically.
    scan_url = f"{site_url}/checkin?code={code}&service={_url_quote(service_instance)}"
    # ────────────────────────────────────────────────────────────────────────

    valid_until = add_to_date(current_time, minutes=interval)

    return {
        'code': scan_url,   # full URL encoded in the QR image
        'hash': code,       # just the CHK-XXXX token
        'valid_until': valid_until,
        'url': scan_url
    }


@frappe.whitelist()
def generate_personal_qr_code(member_id):
    """
    Generate personal QR code for a member.

    FIXED: Uses frappe.db.set_value() instead of member.save() to avoid
    triggering required-field validation (Member Status, Gender, Parish).
    """
    try:
        member_data = frappe.db.get_value(
            'Member',
            member_id,
            ['name', 'full_name', 'whatsapp_number', 'member_qr_code'],
            as_dict=True
        )

        if not member_data:
            return {'success': False, 'message': _('Member not found')}

        if member_data.member_qr_code:
            qr_code = member_data.member_qr_code
        else:
            hash_input = f"{member_data.name}{member_data.full_name}{member_data.whatsapp_number or ''}"
            qr_code = f"MEM-{hashlib.sha256(hash_input.encode()).hexdigest()[:12].upper()}"

            frappe.db.set_value(
                'Member',
                member_id,
                'member_qr_code',
                qr_code,
                update_modified=False
            )
            frappe.db.commit()

        site_url = frappe.utils.get_url()
        scan_url = f"{site_url}/api/method/church.attendance.smart_attendance.process_personal_qr?code={qr_code}"

        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            box_size=10,
            border=4
        )
        qr.add_data(scan_url)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")
        buffered = io.BytesIO()
        img.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode()

        return {
            'success': True,
            'qr_image': f'data:image/png;base64,{img_str}',
            'qr_code': qr_code,
            'member': member_id,
            'full_name': member_data.full_name
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Personal QR Generation Error")
        return {'success': False, 'message': str(e)}


@frappe.whitelist(allow_guest=True)
def process_qr_checkin(code, service=None, latitude=None, longitude=None):
    """
    Process venue QR code check-in via direct API call.
    NOTE: This endpoint is kept for backward compatibility and WiFi/GPS flows.
    The primary path for phone scans is now the /checkin landing page.
    """
    try:
        settings = frappe.get_single('Church Settings')

        if not service:
            service = get_current_service()

        if not service:
            return {'success': False, 'message': 'No active service at this time'}

        if not is_within_checkin_window(service, settings):
            return {'success': False, 'message': 'Check-in window has closed'}

        member_id = frappe.session.user

        if member_id == 'Guest':
            # Redirect guest to the landing page instead of showing an error
            site_url = frappe.utils.get_url()
            return {
                'success': False,
                'require_auth': True,
                'redirect': f"{site_url}/checkin?code={code}&service={_url_quote(service)}",
                'message': 'Please use the check-in page to check in.',
                'code': code,
                'service': service
            }

        if settings.enable_location_checkin and latitude and longitude:
            location_valid = verify_location(float(latitude), float(longitude), settings)
            if not location_valid['valid']:
                return {
                    'success': False,
                    'message': f'You are {location_valid["distance"]:.0f}m from church. Please come closer to check in.'
                }

        result = mark_attendance(
            member_id=member_id,
            service_instance=service,
            checkin_method='QR Code - Venue',
            latitude=latitude,
            longitude=longitude,
            device_info=frappe.request.headers.get('User-Agent', 'Unknown')
        )

        return result

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "QR Check-In Error")
        return {'success': False, 'message': str(e)}


@frappe.whitelist(allow_guest=True)
def process_personal_qr(code):
    """Process personal member QR code scan"""
    try:
        member = frappe.db.get_value('Member', {'member_qr_code': code}, 'name')

        if not member:
            return {'success': False, 'message': 'Invalid QR code'}

        service = get_current_service()

        if not service:
            return {'success': False, 'message': 'No active service at this time'}

        result = mark_attendance(
            member_id=member,
            service_instance=service,
            checkin_method='QR Code - Personal',
            device_info=frappe.request.headers.get('User-Agent', 'Unknown')
        )

        return result

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Personal QR Check-In Error")
        return {'success': False, 'message': str(e)}


# ============================================================================
# WIFI AUTO CHECK-IN
# ============================================================================

@frappe.whitelist()
def check_wifi_connections():
    """
    Poll WiFi controller for connected devices.
    Auto-mark attendance for registered members.
    """
    try:
        settings = frappe.get_single('Church Settings')

        if not settings.enable_wifi_checkin:
            return {'success': False, 'message': 'WiFi check-in not enabled'}

        service = get_current_service()
        if not service:
            return {'success': False, 'message': 'No active service'}

        connected_devices = get_wifi_connected_devices(settings)

        if not connected_devices:
            return {'success': False, 'message': 'No devices found'}

        checked_in = 0

        for device in connected_devices:
            mac_address = device.get('mac_address')

            member_device = frappe.db.get_value(
                'Member Device',
                {'mac_address': mac_address, 'is_active': 1},
                ['parent'],
                as_dict=True
            )

            if member_device:
                member_id = member_device.parent

                existing = frappe.db.exists('Church Attendance', {
                    'member_id': member_id,
                    'service_instance': service,
                    'present': 1
                })

                if not existing:
                    if settings.wifi_verification_method == 'Auto-mark on Connection':
                        mark_attendance(
                            member_id=member_id,
                            service_instance=service,
                            checkin_method='WiFi Auto Check-In',
                            device_info=mac_address,
                            ip_address=device.get('ip_address')
                        )
                        checked_in += 1

                    elif settings.wifi_verification_method == 'Send WhatsApp Confirmation Link':
                        send_wifi_confirmation_link(member_id, service, mac_address)

                    elif settings.wifi_verification_method == 'Send SMS Confirmation Code':
                        send_sms_confirmation(member_id, service)

        return {
            'success': True,
            'checked_in': checked_in,
            'devices_found': len(connected_devices)
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "WiFi Check-In Error")
        return {'success': False, 'message': str(e)}


def get_wifi_connected_devices(settings):
    """Get list of connected devices from WiFi controller"""

    controller_type = settings.wifi_controller_type
    api_endpoint = settings.wifi_api_endpoint
    api_key = settings.get_password('wifi_api_key')

    if not all([controller_type, api_endpoint, api_key]):
        frappe.throw(_("WiFi controller not properly configured"))

    try:
        if controller_type == 'UniFi':
            return get_unifi_clients(api_endpoint, api_key)
        elif controller_type == 'MikroTik':
            return get_mikrotik_clients(api_endpoint, api_key)
        elif controller_type == 'Cisco Meraki':
            return get_meraki_clients(api_endpoint, api_key)
        elif controller_type == 'TP-Link Omada':
            return get_omada_clients(api_endpoint, api_key)
        elif controller_type == 'Custom API':
            return get_custom_api_clients(api_endpoint, api_key)
        return []

    except Exception as e:
        frappe.log_error(f"WiFi Controller Error: {str(e)}", "WiFi Connection Check")
        return []


def get_unifi_clients(api_endpoint, api_key):
    """Get clients from UniFi controller"""
    headers = {'Authorization': f'Bearer {api_key}'}
    response = requests.get(f"{api_endpoint}/api/s/default/stat/sta", headers=headers)
    if response.status_code == 200:
        data = response.json()
        return [
            {'mac_address': client['mac'], 'ip_address': client.get('ip')}
            for client in data.get('data', [])
        ]
    return []


def get_mikrotik_clients(api_endpoint, api_key):
    """Get clients from MikroTik (RouterOS API)"""
    return []


def get_meraki_clients(api_endpoint, api_key):
    """Get clients from Cisco Meraki"""
    headers = {'X-Cisco-Meraki-API-Key': api_key}
    response = requests.get(f"{api_endpoint}/clients", headers=headers)
    if response.status_code == 200:
        clients = response.json()
        return [
            {'mac_address': client['mac'], 'ip_address': client.get('ip')}
            for client in clients
        ]
    return []


def get_omada_clients(api_endpoint, api_key):
    """Get clients from TP-Link Omada"""
    return []


def get_custom_api_clients(api_endpoint, api_key):
    """Get clients from custom API"""
    headers = {'Authorization': f'Bearer {api_key}'}
    response = requests.get(api_endpoint, headers=headers)
    if response.status_code == 200:
        return response.json().get('devices', [])
    return []


@frappe.whitelist()
def register_device(member_id, device_name, mac_address, device_type='Smartphone'):
    """
    Register member device for WiFi check-in.

    Uses member.save() intentionally — modifies child table (registered_devices)
    which cannot use frappe.db.set_value(). Safe here because device registration
    only happens on a fully saved member with all required fields filled.
    """
    try:
        member = frappe.get_doc('Member', member_id)

        existing = False
        for device in member.registered_devices:
            if device.mac_address == mac_address:
                existing = True
                device.last_seen = now_datetime()
                break

        if not existing:
            member.append('registered_devices', {
                'device_name': device_name,
                'device_type': device_type,
                'mac_address': mac_address,
                'registered_date': getdate(),
                'is_active': 1
            })

        member.save(ignore_permissions=True)
        return {'success': True, 'message': 'Device registered successfully'}

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Device Registration Error")
        return {'success': False, 'message': str(e)}


def send_wifi_confirmation_link(member_id, service, mac_address):
    """Send WhatsApp link to confirm attendance"""

    member_data = frappe.db.get_value(
        'Member', member_id,
        ['full_name', 'whatsapp_number'],
        as_dict=True
    )
    settings = frappe.get_single('Church Settings')

    token = hashlib.sha256(f"{member_id}{service}{now()}".encode()).hexdigest()[:16]

    frappe.cache().set(f"wifi_confirm_{token}", {
        'member': member_id,
        'service': service,
        'mac': mac_address
    }, expires_in_sec=1800)

    site_url = frappe.utils.get_url()
    confirm_url = f"{site_url}/api/method/church.attendance.smart_attendance.confirm_wifi_checkin?token={token}"

    message = (
        f"👋 Hello {member_data.full_name}!\n\n"
        f"We detected you're at church. Click to confirm your attendance:\n\n"
        f"{confirm_url}\n\nGod bless you!"
    )

    send_whatsapp_message(member_data.whatsapp_number, message, settings)


@frappe.whitelist(allow_guest=True)
def confirm_wifi_checkin(token):
    """Confirm WiFi-detected attendance via link"""
    try:
        token_data = frappe.cache().get(f"wifi_confirm_{token}")

        if not token_data:
            return {'success': False, 'message': 'Invalid or expired link'}

        result = mark_attendance(
            member_id=token_data['member'],
            service_instance=token_data['service'],
            checkin_method='WiFi Auto Check-In',
            device_info=token_data['mac']
        )

        frappe.cache().delete(f"wifi_confirm_{token}")
        return result

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "WiFi Confirmation Error")
        return {'success': False, 'message': str(e)}


# ============================================================================
# LOCATION VERIFICATION
# ============================================================================

@frappe.whitelist()
def verify_checkin_location(member_id, latitude, longitude, service_instance=None):
    """Verify member location for check-in"""
    try:
        settings = frappe.get_single('Church Settings')

        if not settings.enable_location_checkin:
            return {'success': False, 'message': 'Location verification not enabled'}

        location_check = verify_location(float(latitude), float(longitude), settings)

        if not location_check['valid']:
            return {
                'success': False,
                'message': f'You are {location_check["distance"]:.0f}m from church',
                'distance': location_check['distance']
            }

        if not service_instance:
            service_instance = get_current_service()

        if not service_instance:
            return {'success': False, 'message': 'No active service'}

        result = mark_attendance(
            member_id=member_id,
            service_instance=service_instance,
            checkin_method='Mobile App GPS',
            latitude=latitude,
            longitude=longitude,
            device_info=frappe.request.headers.get('User-Agent', 'Unknown')
        )

        return result

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Location Verification Error")
        return {'success': False, 'message': str(e)}


def verify_location(latitude, longitude, settings):
    """Check if coordinates are within church radius"""
    church_lat = settings.church_latitude
    church_lon = settings.church_longitude
    max_radius = settings.location_radius or 100
    distance = calculate_distance(church_lat, church_lon, latitude, longitude)
    return {'valid': distance <= max_radius, 'distance': distance}


def calculate_distance(lat1, lon1, lat2, lon2):
    """
    Calculate distance between two GPS coordinates in metres.
    Uses the Haversine formula.
    """
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * asin(sqrt(a))
    return c * 6371000


# ============================================================================
# ATTENDANCE MARKING
# ============================================================================

def mark_attendance(member_id, service_instance, checkin_method, latitude=None,
                    longitude=None, device_info=None, ip_address=None):
    """
    Core function to mark attendance.
    Includes fraud detection and verification.

    FIXED: Member stats updated via frappe.db.set_value() — never triggers
    required-field validation (Member Status, Gender, Parish).
    """
    try:
        settings = frappe.get_single('Church Settings')
        service = frappe.get_doc('Service Instance', service_instance)

        member_data = frappe.db.get_value(
            'Member', member_id,
            ['full_name', 'total_checkins', 'suspicious_checkins_count'],
            as_dict=True
        )

        if not member_data:
            return {'success': False, 'message': 'Member not found'}

        # Duplicate check
        existing = frappe.db.get_value('Church Attendance', {
            'member_id': member_id,
            'service_instance': service_instance,
            'present': 1
        }, 'name')

        if existing and not settings.allow_duplicate_qr_scan:
            return {
                'success': False,
                'message': f'{member_data.full_name} is already checked in for this service'
            }

        # Fraud detection
        is_suspicious, suspicious_reason = detect_fraud(
            member_id, service_instance, checkin_method,
            latitude, longitude, settings
        )

        # Create or update attendance record
        if existing:
            attendance = frappe.get_doc('Church Attendance', existing)
        else:
            attendance = frappe.new_doc('Church Attendance')
            attendance.member_id = member_id
            attendance.service_instance = service_instance
            attendance.service_date = service.service_date
            attendance.branch = service.branch
            attendance.service_type = service.service_type

        attendance.present = 1
        attendance.checkin_method = checkin_method
        attendance.checkin_timestamp = now_datetime()
        attendance.device_info = device_info
        attendance.ip_address = ip_address
        attendance.latitude = latitude
        attendance.longitude = longitude
        attendance.auto_marked = 1 if checkin_method != 'Manual Entry' else 0

        if latitude and longitude and settings.church_latitude:
            distance = calculate_distance(
                settings.church_latitude, settings.church_longitude,
                float(latitude), float(longitude)
            )
            attendance.distance_from_church = distance
            attendance.location_verified = distance <= (settings.location_radius or 100)

        attendance.is_suspicious = is_suspicious
        attendance.suspicious_reason = suspicious_reason if is_suspicious else None
        attendance.save(ignore_permissions=True)

        # Update member stats without triggering validation
        new_total = (member_data.total_checkins or 0) + 1
        new_suspicious = (member_data.suspicious_checkins_count or 0) + (1 if is_suspicious else 0)

        frappe.db.set_value(
            'Member',
            member_id,
            {
                'last_checkin_date': now_datetime(),
                'last_checkin_method': checkin_method,
                'total_checkins': new_total,
                'suspicious_checkins_count': new_suspicious
            },
            update_modified=False
        )
        frappe.db.commit()

        if settings.send_checkin_confirmation:
            send_checkin_confirmation(member_data, service, settings)

        return {
            'success': True,
            'message': f'Welcome {member_data.full_name}! Attendance marked successfully',
            'member': member_data.full_name,
            'service': service.service_type,
            'time': str(attendance.checkin_timestamp),
            'flagged': is_suspicious
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Mark Attendance Error")
        return {'success': False, 'message': str(e)}


def detect_fraud(member_id, service_instance, checkin_method, latitude, longitude, settings):
    """Detect suspicious check-in patterns"""

    suspicious = False
    reasons = []

    # Check 1: Location
    if settings.prevent_remote_checkin and settings.enable_location_checkin:
        if latitude and longitude:
            location_check = verify_location(float(latitude), float(longitude), settings)
            if not location_check['valid']:
                suspicious = True
                reasons.append(f"Outside church premises ({location_check['distance']:.0f}m away)")

    # Check 2: Multiple check-ins in 5 minutes
    recent_checkins = frappe.db.count('Church Attendance', {
        'member_id': member_id,
        'checkin_timestamp': ['>=', add_to_date(now_datetime(), minutes=-5)],
        'present': 1
    })
    if recent_checkins >= 3:
        suspicious = True
        reasons.append("Multiple check-ins in 5 minutes")

    # Check 3: Outside service window
    if not is_within_checkin_window(service_instance, settings):
        suspicious = True
        reasons.append("Check-in outside service window")

    # Check 4: Impossible travel
    last_checkin = frappe.db.get_value(
        'Church Attendance',
        {'member_id': member_id, 'checkin_timestamp': ['<', now_datetime()]},
        ['latitude', 'longitude', 'checkin_timestamp'],
        order_by='checkin_timestamp desc'
    )

    if last_checkin and latitude and longitude:
        time_diff = (now_datetime() - last_checkin[2]).total_seconds() / 60
        if time_diff < 10:
            distance = calculate_distance(
                last_checkin[0], last_checkin[1],
                float(latitude), float(longitude)
            )
            if distance > 1000:
                suspicious = True
                reasons.append("Impossible travel distance")

    return suspicious, "; ".join(reasons) if reasons else None


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_current_service():
    """Get active service instance based on current time"""
    try:
        settings = frappe.get_single('Church Settings')
        window = settings.attendance_check_in_window or 30
        now_time = now_datetime()

        services = frappe.get_all(
            'Service Instance',
            filters={'service_date': getdate(), 'docstatus': ['!=', 2]},
            fields=['name', 'service_time', 'service_type']
        )

        for service in services:
            service_datetime = frappe.utils.get_datetime(f"{getdate()} {service.service_time}")
            start_window = add_to_date(service_datetime, minutes=-window)
            end_window = add_to_date(service_datetime, minutes=window)

            if start_window <= now_time <= end_window:
                return service.name

    except Exception:
        pass

    return None


def is_within_checkin_window(service_instance, settings):
    """Check if current time is within the check-in window for a service"""
    service = frappe.get_doc('Service Instance', service_instance)
    window = settings.attendance_check_in_window or 30
    service_datetime = frappe.utils.get_datetime(f"{service.service_date} {service.service_time}")
    start_window = add_to_date(service_datetime, minutes=-window)
    end_window = add_to_date(service_datetime, minutes=window)
    return start_window <= now_datetime() <= end_window


def send_checkin_confirmation(member_data, service, settings):
    """
    Send check-in confirmation message.
    Accepts member_data as a dict — never loads full Member doc.
    """
    method = settings.confirmation_method
    template = (
        settings.confirmation_message
        or "✅ Welcome {member_name}! Your attendance has been recorded for {service_name} on {date}. God bless you!"
    )

    full_name = (
        member_data.full_name
        if hasattr(member_data, 'full_name')
        else member_data.get('full_name', '')
    )

    message = template.format(
        member_name=full_name,
        service_name=service.service_type,
        date=frappe.utils.format_date(service.service_date)
    )

    member_name_or_id = member_data.get('name') if isinstance(member_data, dict) else None

    if method == 'WhatsApp':
        whatsapp = (
            member_data.whatsapp_number
            if hasattr(member_data, 'whatsapp_number')
            else frappe.db.get_value('Member', member_name_or_id, 'whatsapp_number')
        )
        send_whatsapp_message(whatsapp, message, settings)

    elif method == 'SMS':
        phone = (
            member_data.phone
            if hasattr(member_data, 'phone')
            else frappe.db.get_value('Member', member_name_or_id, 'mobile_phone')
        )
        send_sms_message(phone, message, settings)

    elif method == 'Email':
        email = (
            member_data.email
            if hasattr(member_data, 'email')
            else frappe.db.get_value('Member', member_name_or_id, 'email')
        )
        if email:
            frappe.sendmail(
                recipients=[email],
                subject='Attendance Confirmation',
                message=message
            )


def send_whatsapp_message(phone_number, message, settings):
    """Send WhatsApp message via configured API provider"""
    provider = settings.whatsapp_api_provider
    api_key = settings.get_password('whatsapp_api_key')

    if not all([provider, api_key, phone_number]):
        return

    try:
        if provider == 'Twilio':
            pass  # Twilio implementation placeholder
        elif provider == '360Dialog':
            pass  # 360Dialog implementation placeholder
    except Exception as e:
        frappe.log_error(f"WhatsApp Error: {str(e)}", "WhatsApp Notification")


def send_sms_message(phone_number, message, settings):
    """Send SMS message via configured provider"""
    pass


# ============================================================================
# SCHEDULED JOBS
# ============================================================================

def auto_check_wifi_connections():
    """
    Scheduled job: poll WiFi connections every 5 minutes during service times.
    Wired in hooks.py under scheduler_events cron or 'all'.
    """
    settings = frappe.get_single('Church Settings')
    if settings.enable_wifi_checkin:
        check_wifi_connections()


def cleanup_expired_qr_tokens():
    """Cleanup expired QR codes and tokens from cache"""
    pass


def cleanup_old_attendance_data():
    """
    Cleanup old attendance data and temporary tokens.
    Run daily to maintain system performance.
    """
    try:
        ninety_days_ago = add_to_date(getdate(), days=-90)

        old_suspicious = frappe.get_all(
            'Church Attendance',
            filters={
                'is_suspicious': 1,
                'verified_by_admin': ['is', 'set'],
                'service_date': ['<', ninety_days_ago]
            },
            pluck='name'
        )

        for record in old_suspicious:
            frappe.db.set_value(
                'Church Attendance',
                record,
                'is_suspicious',
                0,
                update_modified=False
            )

        frappe.db.commit()

        # Clean up expired WiFi confirmation tokens from cache
        cache_keys = frappe.cache().get_keys('wifi_confirm_*')
        for key in cache_keys:
            token_data = frappe.cache().get(key)
            if not token_data:
                frappe.cache().delete(key)

        frappe.logger().info(
            f"Attendance cleanup completed. Processed {len(old_suspicious)} old suspicious records."
        )

        return {
            'success': True,
            'message': 'Cleanup completed successfully',
            'old_suspicious_cleared': len(old_suspicious)
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Attendance Cleanup Error")
        return {'success': False, 'message': str(e)}