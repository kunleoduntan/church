# Copyright (c) 2026, kunle and contributors
# For license information, please see license.txt

"""
Guest Check-In Module

Flow:
    Member scans venue QR code displayed on screen in church
        ↓
    Page loads → asks for phone number to identify them
        ↓
    FOUND as Member  →  mark Church Attendance  →  success
    NOT FOUND        →  show Visitor form        →  create Visitor + success

No error screens for "invalid QR" — scanning the venue QR always
leads somewhere useful. Worst case the person fills the visitor form.
"""

import frappe
from frappe import _
from frappe.utils import nowdate, now_datetime, getdate
import hashlib


# ============================================================================
# GET SERVICE INFO
# Called on page load — returns service details to display in the header.
# Never throws an error. If service is not found, returns a safe fallback.
# ============================================================================

@frappe.whitelist(allow_guest=True)
def get_service_info(service=None, code=None):
    """
    Returns service details for the check-in page header.
    Always returns something useful — never an error screen.
    """
    try:
        settings = frappe.get_single('Church Settings')
        church_name = settings.church_name or 'Church'

        # Try to resolve service from param or from active service
        if not service:
            service = _get_active_service()

        if not service:
            # No active service — still show the form as visitor intake
            return {
                'success': True,
                'church_name': church_name,
                'service': None,
                'service_type': 'Visitor Check-In',
                'service_date': frappe.utils.format_date(nowdate()),
                'service_time': '',
                'branch': '',
                'show_visitor_form_only': True
            }

        service_doc = frappe.db.get_value(
            'Service Instance',
            service,
            ['service_type', 'service_date', 'service_time', 'branch'],
            as_dict=True
        )

        if not service_doc:
            return {
                'success': True,
                'church_name': church_name,
                'service': service,
                'service_type': 'Service Check-In',
                'service_date': frappe.utils.format_date(nowdate()),
                'service_time': '',
                'branch': '',
                'show_visitor_form_only': False
            }

        return {
            'success': True,
            'church_name': church_name,
            'service': service,
            'service_type': service_doc.service_type or 'Service',
            'service_date': frappe.utils.format_date(service_doc.service_date),
            'service_time': str(service_doc.service_time or ''),
            'branch': service_doc.branch or '',
            'show_visitor_form_only': False
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Get Service Info Error")
        return {
            'success': True,
            'church_name': 'Church',
            'service': service,
            'service_type': 'Check-In',
            'service_date': frappe.utils.format_date(nowdate()),
            'service_time': '',
            'branch': '',
            'show_visitor_form_only': False
        }


# ============================================================================
# LOOKUP MEMBER BY PHONE OR EMAIL
# ============================================================================

@frappe.whitelist(allow_guest=True)
def lookup_member(phone=None, email=None):
    """
    Check if person exists as an active Member by phone or email.
    Returns found=True/False and minimal safe info.
    """
    if not phone and not email:
        return {'found': False}

    try:
        member = None

        if phone:
            clean = _clean_phone(phone)
            member = frappe.db.get_value(
                'Member',
                {
                    'mobile_phone': ['like', f'%{clean[-9:]}'],
                    'member_status': 'Active'
                },
                ['name', 'full_name', 'first_name'],
                as_dict=True
            )

        if not member and email:
            member = frappe.db.get_value(
                'Member',
                {
                    'email': email.strip().lower(),
                    'member_status': 'Active'
                },
                ['name', 'full_name', 'first_name'],
                as_dict=True
            )

        if member:
            return {
                'found': True,
                'member_id': member.name,
                'first_name': member.first_name or '',
                'full_name': member.full_name or ''
            }

        return {'found': False}

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Member Lookup Error")
        return {'found': False}


# ============================================================================
# CHECKIN — EXISTING MEMBER
# ============================================================================

@frappe.whitelist(allow_guest=True)
def checkin_member(member_id, service=None):
    """
    Mark Church Attendance for an identified Member.
    """
    try:
        if not service:
            service = _get_active_service()

        member_name = frappe.db.get_value('Member', member_id, 'full_name') or 'Member'

        # Handle no active service gracefully
        if not service:
            return {
                'success': True,
                'message': f'✅ Welcome {member_name}! Your visit has been noted.',
                'already_checked_in': False,
                'member': member_name
            }

        # Duplicate check
        existing = frappe.db.exists('Church Attendance', {
            'member_id': member_id,
            'service_instance': service,
            'present': 1
        })

        if existing:
            return {
                'success': True,
                'already_checked_in': True,
                'message': f'✅ {member_name}, you are already checked in!',
                'member': member_name
            }

        # Get service details
        service_doc = frappe.get_doc('Service Instance', service)

        # Create attendance
        attendance = frappe.new_doc('Church Attendance')
        attendance.member_id = member_id
        attendance.service_instance = service
        attendance.service_date = service_doc.service_date
        attendance.branch = service_doc.branch
        attendance.service_type = service_doc.service_type
        attendance.present = 1
        attendance.checkin_method = 'QR Code - Venue'
        attendance.checkin_timestamp = now_datetime()
        attendance.auto_marked = 1
        attendance.save(ignore_permissions=True)

        # Update member stats without triggering validation
        current = frappe.db.get_value('Member', member_id, 'total_checkins') or 0
        frappe.db.set_value('Member', member_id, {
            'last_checkin_date': now_datetime(),
            'last_checkin_method': 'QR Code - Venue',
            'total_checkins': current + 1
        }, update_modified=False)
        frappe.db.commit()

        return {
            'success': True,
            'already_checked_in': False,
            'member': member_name,
            'service': service_doc.service_type,
            'message': f'🎉 Welcome {member_name}! Attendance recorded.'
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Member Check-In Error")
        return {
            'success': False,
            'message': 'Check-in failed. Please see the attendance desk.'
        }


# ============================================================================
# CHECKIN — VISITOR (not found in Member list)
# ============================================================================

@frappe.whitelist(allow_guest=True)
def checkin_visitor(
    first_name,
    last_name,
    mobile_phone,
    gender,
    service=None,
    email=None,
    marital_status=None
):
    """
    Handle check-in for someone not found as a Member.
    Creates a Visitor record and Church Attendance.
    """
    try:
        if not first_name or not last_name:
            return {'success': False, 'message': 'First name and last name are required.'}
        if not mobile_phone:
            return {'success': False, 'message': 'Mobile number is required.'}
        if not gender:
            return {'success': False, 'message': 'Please select your gender.'}

        if not service:
            service = _get_active_service()

        full_name = f"{first_name.strip()} {last_name.strip()}"
        formatted_phone = _format_phone(mobile_phone)

        # Resolve service details
        service_doc = None
        service_date = nowdate()
        branch = None
        service_type = None

        if service:
            try:
                service_doc = frappe.get_doc('Service Instance', service)
                service_date = service_doc.service_date
                branch = service_doc.branch
                service_type = service_doc.service_type
            except Exception:
                pass

        # Check if Visitor already exists by phone
        existing_visitor = None
        clean = _clean_phone(mobile_phone)

        existing_visitor = frappe.db.get_value(
            'Visitor',
            {'mobile_phone': ['like', f'%{clean[-9:]}']},
            ['name', 'full_name'],
            as_dict=True
        )

        if not existing_visitor and email:
            existing_visitor = frappe.db.get_value(
                'Visitor',
                {'email': email.strip().lower()},
                ['name', 'full_name'],
                as_dict=True
            )

        # Create new Visitor if not found
        if existing_visitor:
            visitor_id = existing_visitor.name
            display_name = existing_visitor.full_name or full_name
            is_new = False
        else:
            visitor = frappe.new_doc('Visitor')
            visitor.first_name = first_name.strip()
            visitor.last_name = last_name.strip()
            visitor.full_name = full_name
            visitor.gender = gender
            visitor.mobile_phone = formatted_phone
            visitor.email = email.strip().lower() if email else None
            visitor.marital_status = marital_status or None
            visitor.date_of_visit = service_date
            visitor.branch = branch
            visitor.visit_type = 'First Time Visitor'
            visitor.conversion_status = 'New Visitor'
            visitor.insert(ignore_permissions=True)
            frappe.db.commit()

            visitor_id = visitor.name
            display_name = full_name
            is_new = True

        # Duplicate attendance check
        att_filters = {'visitor_id': visitor_id, 'present': 1}
        if service:
            att_filters['service_instance'] = service

        if frappe.db.exists('Church Attendance', att_filters):
            return {
                'success': True,
                'already_checked_in': True,
                'message': f'✅ {display_name}, your attendance is already recorded!'
            }

        # Create attendance
        attendance = frappe.new_doc('Church Attendance')
        attendance.visitor_id = visitor_id
        attendance.visitor_name = display_name
        attendance.service_date = service_date
        attendance.present = 1
        attendance.checkin_method = 'QR Code - Venue (Visitor)'
        attendance.checkin_timestamp = now_datetime()
        attendance.auto_marked = 1

        if service and service_doc:
            attendance.service_instance = service
            attendance.branch = branch
            attendance.service_type = service_type

        attendance.save(ignore_permissions=True)
        frappe.db.commit()

        return {
            'success': True,
            'already_checked_in': False,
            'visitor': visitor_id,
            'is_new_visitor': is_new,
            'message': f'🎉 Welcome {display_name}! We are glad you are here.'
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Visitor Check-In Error")
        return {
            'success': False,
            'message': 'Check-in failed. Please see the welcome desk.'
        }


# ============================================================================
# HELPERS
# ============================================================================

def _get_active_service():
    """Find a service instance active right now"""
    try:
        from frappe.utils import add_to_date
        settings = frappe.get_single('Church Settings')
        window = settings.attendance_check_in_window or 30
        now_time = now_datetime()

        services = frappe.get_all(
            'Service Instance',
            filters={'service_date': getdate(), 'docstatus': ['!=', 2]},
            fields=['name', 'service_time']
        )

        for svc in services:
            svc_dt = frappe.utils.get_datetime(f"{getdate()} {svc.service_time}")
            if (add_to_date(svc_dt, minutes=-window)
                    <= now_time <=
                    add_to_date(svc_dt, minutes=window)):
                return svc.name
    except Exception:
        pass
    return None


def _clean_phone(phone):
    if not phone:
        return ''
    return ''.join(c for c in phone if c.isdigit() or c == '+')


def _format_phone(phone):
    if not phone:
        return None
    phone = _clean_phone(phone)
    if not phone.startswith('+'):
        if len(phone) in (10, 11):
            phone = '+234' + phone.lstrip('0')
        else:
            phone = '+' + phone
    return phone