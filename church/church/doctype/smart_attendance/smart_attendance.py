# -*- coding: utf-8 -*-
# Copyright (c) 2026, Church Management and contributors
# For license information, please see license.txt

"""
Smart Attendance DocType Controller
Handles QR code generation, scanning, and intelligent attendance tracking
"""

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import (
    now_datetime, nowdate, getdate, get_datetime, 
    formatdate, date_diff, cint, flt, add_days
)
import json
from collections import defaultdict

# QR Code imports - optional, will handle gracefully if not installed
try:
    import qrcode
    from qrcode.image.pure import PyPNGImage
    import io
    import base64
    HAS_QRCODE = True
except ImportError:
    HAS_QRCODE = False


class SmartAttendance(Document):
    """
    Smart Attendance Controller
    Manages attendance tracking with QR codes and analytics
    """
    
    def validate(self):
        """Validate before saving"""
        self.validate_dates()
        self.calculate_statistics()
    
    def validate_dates(self):
        """Ensure date ranges are valid"""
        if self.from_date and self.to_date:
            if getdate(self.from_date) > getdate(self.to_date):
                frappe.throw(_("From Date cannot be after To Date"))
    
    def calculate_statistics(self):
        """Calculate attendance statistics"""
        if not self.attendance_records:
            self.total_attendance = 0
            self.unique_members = 0
            return
        
        # Count total and unique
        member_ids = set()
        for record in self.attendance_records:
            member_ids.add(record.member_id)
        
        self.total_attendance = len(self.attendance_records)
        self.unique_members = len(member_ids)


# ============================================================================
# QR CODE GENERATION FUNCTIONS
# ============================================================================

@frappe.whitelist()
def generate_personal_qr_code(member_name):
    """
    Generate personal QR code for a member
    Creates a scannable QR code that links to quick check-in
    
    Args:
        member_name: Member ID
    
    Returns:
        dict: Success status and QR code data
    """
    
    if not HAS_QRCODE:
        return {
            'success': False,
            'error': _('QR code library not installed. Run: bench pip install qrcode[pil]')
        }
    
    try:
        # Validate member exists
        if not frappe.db.exists("Member", member_name):
            frappe.throw(_("Member {0} not found").format(member_name))
        
        member = frappe.get_doc("Member", member_name)
        
        # Generate QR code URL with correct path
        site_url = frappe.utils.get_url()
        qr_url = f"{site_url}/api/method/church.church.doctype.smart_attendance.smart_attendance.process_qr_checkin?member_id={member.name}"
        
        # Create QR code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_H,  # High error correction
            box_size=10,
            border=4,
        )
        qr.add_data(qr_url)
        qr.make(fit=True)
        
        # Generate image with church branding colors
        img = qr.make_image(fill_color="#667EEA", back_color="white")
        
        # Convert to base64 for storage
        buffered = io.BytesIO()
        img.save(buffered, format="PNG")
        img_base64 = base64.b64encode(buffered.getvalue()).decode()
        
        qr_data_url = f"data:image/png;base64,{img_base64}"
        
        # Save to member record if field exists
        if hasattr(member, 'personal_qr_code'):
            member.personal_qr_code = qr_data_url
            member.qr_generated_on = now_datetime()
            member.save(ignore_permissions=True)
            frappe.db.commit()
        
        return {
            'success': True,
            'qr_code': qr_data_url,
            'qr_url': qr_url,
            'message': _('QR code generated successfully for {0}').format(member.full_name)
        }
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "QR Code Generation Error")
        return {
            'success': False,
            'error': str(e)
        }


@frappe.whitelist()
def generate_personal_qr_if_needed(member_name):
    """
    Generate QR code only if it doesn't exist
    Used by automated systems to ensure all members have QR codes
    
    Args:
        member_name: Member ID
    
    Returns:
        dict: Result with status
    """
    try:
        member = frappe.get_doc("Member", member_name)
        
        # Check if QR already exists
        if hasattr(member, 'personal_qr_code') and member.personal_qr_code:
            return {
                'success': True,
                'message': _('QR code already exists'),
                'generated': False
            }
        
        # Generate new QR code
        result = generate_personal_qr_code(member_name)
        result['generated'] = True
        return result
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Auto QR Generation Error")
        return {
            'success': False,
            'error': str(e)
        }


@frappe.whitelist()
def bulk_generate_qr_codes(filters=None):
    """
    Generate QR codes for multiple members in bulk
    
    Args:
        filters: JSON string or dict with member filters
    
    Returns:
        dict: Generation statistics
    """
    try:
        # Parse filters
        if filters and isinstance(filters, str):
            filters = json.loads(filters)
        
        if not filters:
            filters = {'member_status': 'Active'}
        
        # Get members
        members = frappe.get_all(
            'Member',
            filters=filters,
            fields=['name', 'full_name']
        )
        
        success_count = 0
        failed_count = 0
        skipped_count = 0
        
        for member in members:
            try:
                result = generate_personal_qr_if_needed(member.name)
                
                if result.get('success'):
                    if result.get('generated'):
                        success_count += 1
                    else:
                        skipped_count += 1
                else:
                    failed_count += 1
                    
            except Exception as e:
                failed_count += 1
                frappe.log_error(f"Failed to generate QR for {member.name}: {str(e)}")
        
        frappe.db.commit()
        
        return {
            'success': True,
            'generated': success_count,
            'skipped': skipped_count,
            'failed': failed_count,
            'total': len(members),
            'message': _('Generated {0} QR codes, skipped {1}, failed {2}').format(
                success_count, skipped_count, failed_count
            )
        }
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Bulk QR Generation Error")
        return {
            'success': False,
            'error': str(e)
        }


# ============================================================================
# QR CODE SCANNING & CHECK-IN PROCESSING
# ============================================================================

@frappe.whitelist(allow_guest=True)
def process_qr_checkin(member_id):
    """
    Process member check-in via QR code scan
    This is the endpoint that QR codes point to
    Allows guest access so members don't need to log in
    
    Args:
        member_id: Member ID from scanned QR code
    
    Returns:
        Web page with check-in result
    """
    try:
        # Validate member exists
        if not frappe.db.exists("Member", member_id):
            frappe.respond_as_web_page(
                _("Member Not Found"),
                _("The scanned QR code is invalid or the member does not exist."),
                indicator_color='red',
                http_status_code=404
            )
            return
        
        member = frappe.get_doc("Member", member_id)
        
        # Check if member is active
        if member.member_status != 'Active':
            frappe.respond_as_web_page(
                _("Member Inactive"),
                _("""
                <div style='text-align: center; padding: 30px;'>
                    <h2>{0}</h2>
                    <p>Member status: <strong>{1}</strong></p>
                    <p>Please contact church administration.</p>
                </div>
                """).format(member.full_name, member.member_status),
                indicator_color='orange'
            )
            return
        
        # Record attendance
        attendance_result = record_member_attendance(
            member_id=member.name,
            check_in_method='QR Code'
        )
        
        if attendance_result.get('success'):
            # Success response
            check_in_time = get_datetime(attendance_result.get('check_in_time'))
            time_str = check_in_time.strftime('%I:%M %p')
            
            frappe.respond_as_web_page(
                _("✓ Check-in Successful"),
                _("""
                <div style='text-align: center; padding: 40px; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;'>
                    <div style='font-size: 96px; color: #2ecc71; margin-bottom: 20px; animation: scaleIn 0.5s ease-out;'>
                        ✓
                    </div>
                    <h1 style='color: #2c3e50; margin: 20px 0; font-size: 36px;'>
                        Welcome {0}!
                    </h1>
                    <p style='font-size: 18px; color: #7f8c8d; margin: 15px 0;'>
                        {1}
                    </p>
                    <div style='background: #f8f9fa; padding: 20px; border-radius: 12px; margin: 25px auto; max-width: 400px;'>
                        <p style='margin: 8px 0; color: #495057;'>
                            <strong>Time:</strong> {2}
                        </p>
                        <p style='margin: 8px 0; color: #495057;'>
                            <strong>Date:</strong> {3}
                        </p>
                        <p style='margin: 8px 0; color: #495057;'>
                            <strong>Branch:</strong> {4}
                        </p>
                    </div>
                    <p style='font-size: 14px; color: #95a5a6; margin-top: 30px;'>
                        God bless you! 🙏
                    </p>
                </div>
                <style>
                    @keyframes scaleIn {{
                        from {{ transform: scale(0); }}
                        to {{ transform: scale(1); }}
                    }}
                </style>
                """).format(
                    member.first_name or member.full_name,
                    attendance_result.get('message', 'Check-in successful'),
                    time_str,
                    formatdate(nowdate(), "dd MMMM yyyy"),
                    member.branch or 'Church'
                ),
                indicator_color='green'
            )
        else:
            # Error response
            frappe.respond_as_web_page(
                _("Check-in Failed"),
                _("""
                <div style='text-align: center; padding: 30px;'>
                    <div style='font-size: 72px; color: #e74c3c; margin-bottom: 20px;'>✗</div>
                    <h2>Check-in Failed</h2>
                    <p style='color: #7f8c8d;'>{0}</p>
                    <p style='margin-top: 20px;'>Please contact church staff for assistance.</p>
                </div>
                """).format(attendance_result.get('error', 'Unknown error')),
                indicator_color='red'
            )
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "QR Check-in Error")
        frappe.respond_as_web_page(
            _("System Error"),
            _("""
            <div style='text-align: center; padding: 30px;'>
                <h2>An error occurred</h2>
                <p>Please try again or contact church administration.</p>
            </div>
            """),
            indicator_color='red',
            http_status_code=500
        )


def record_member_attendance(member_id, check_in_method='QR Code'):
    """
    Record or update member attendance
    
    Args:
        member_id: Member ID
        check_in_method: Method of check-in (QR Code, Manual, etc.)
    
    Returns:
        dict: Recording result with success status
    """
    try:
        member = frappe.get_doc('Member', member_id)
        current_date = nowdate()
        current_time = now_datetime()
        
        # Check if attendance record already exists for today
        existing = frappe.db.exists(
            'Member Attendance',
            {
                'member_id': member_id,
                'attendance_date': current_date
            }
        )
        
        if existing:
            # Update existing attendance record
            attendance = frappe.get_doc('Member Attendance', existing)
            attendance.check_in_time = current_time
            attendance.attendance_method = check_in_method
            attendance.attendance_status = 'Present'
            attendance.save(ignore_permissions=True)
            
            message = _('Attendance updated - Welcome back!')
            
        else:
            # Create new attendance record
            attendance = frappe.get_doc({
                'doctype': 'Member Attendance',
                'member_id': member_id,
                'member_name': member.full_name,
                'attendance_date': current_date,
                'check_in_time': current_time,
                'attendance_status': 'Present',
                'attendance_method': check_in_method,
                'branch': member.branch,
                'demographic_group': member.demographic_group,
                'gender': member.gender
            })
            attendance.insert(ignore_permissions=True)
            
            message = _('Check-in successful!')
        
        frappe.db.commit()
        
        # Log successful check-in
        frappe.logger().info(f"QR Check-in: {member.full_name} ({member_id}) at {current_time}")
        
        return {
            'success': True,
            'check_in_time': current_time,
            'message': message,
            'attendance_id': attendance.name,
            'is_new': not existing
        }
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Record Attendance Error")
        return {
            'success': False,
            'error': str(e)
        }


# ============================================================================
# ANALYTICS & REPORTING
# ============================================================================

@frappe.whitelist()
def get_qr_checkin_stats(date=None, branch=None):
    """
    Get QR check-in statistics for analysis
    
    Args:
        date: Date to check (default: today)
        branch: Branch filter (optional)
    
    Returns:
        dict: Comprehensive check-in statistics
    """
    try:
        if not date:
            date = nowdate()
        
        filters = {
            'attendance_date': date,
            'attendance_method': 'QR Code'
        }
        
        if branch:
            filters['branch'] = branch
        
        # Get all QR check-ins for the date
        checkins = frappe.get_all(
            'Member Attendance',
            filters=filters,
            fields=[
                'name', 'member_id', 'member_name', 'check_in_time',
                'demographic_group', 'gender', 'branch'
            ],
            order_by='check_in_time asc'
        )
        
        # Calculate statistics
        stats = {
            'total_checkins': len(checkins),
            'by_demographic': defaultdict(int),
            'by_gender': defaultdict(int),
            'by_hour': defaultdict(int),
            'by_branch': defaultdict(int),
            'peak_hour': None,
            'first_checkin': None,
            'last_checkin': None,
            'recent_checkins': []
        }
        
        if checkins:
            stats['first_checkin'] = checkins[0]
            stats['last_checkin'] = checkins[-1]
            stats['recent_checkins'] = checkins[-10:] if len(checkins) > 10 else checkins
            
            hour_counts = defaultdict(int)
            
            for checkin in checkins:
                # By demographic
                group = checkin.demographic_group or 'Unknown'
                stats['by_demographic'][group] += 1
                
                # By gender
                gender = checkin.gender or 'Unknown'
                stats['by_gender'][gender] += 1
                
                # By branch
                branch_name = checkin.branch or 'Unknown'
                stats['by_branch'][branch_name] += 1
                
                # By hour
                if checkin.check_in_time:
                    hour = get_datetime(checkin.check_in_time).hour
                    hour_counts[hour] += 1
                    stats['by_hour'][f"{hour:02d}:00"] = hour_counts[hour]
            
            # Find peak hour
            if hour_counts:
                peak_hour = max(hour_counts.items(), key=lambda x: x[1])
                stats['peak_hour'] = {
                    'hour': f"{peak_hour[0]:02d}:00",
                    'count': peak_hour[1]
                }
        
        # Convert defaultdicts to regular dicts for JSON
        stats['by_demographic'] = dict(stats['by_demographic'])
        stats['by_gender'] = dict(stats['by_gender'])
        stats['by_hour'] = dict(stats['by_hour'])
        stats['by_branch'] = dict(stats['by_branch'])
        
        return {
            'success': True,
            'date': date,
            'branch': branch,
            'statistics': stats
        }
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "QR Stats Error")
        return {
            'success': False,
            'error': str(e)
        }


@frappe.whitelist()
def get_member_attendance_history(member_id, limit=20):
    """
    Get attendance history for a member
    
    Args:
        member_id: Member ID
        limit: Number of records to return
    
    Returns:
        dict: Attendance history
    """
    try:
        attendance_records = frappe.get_all(
            'Member Attendance',
            filters={'member_id': member_id},
            fields=[
                'name', 'attendance_date', 'check_in_time',
                'attendance_status', 'attendance_method', 'branch'
            ],
            order_by='attendance_date desc',
            limit=limit
        )
        
        # Calculate statistics
        total_present = sum(1 for r in attendance_records if r.attendance_status == 'Present')
        qr_checkins = sum(1 for r in attendance_records if r.attendance_method == 'QR Code')
        
        return {
            'success': True,
            'attendance_records': attendance_records,
            'statistics': {
                'total_records': len(attendance_records),
                'total_present': total_present,
                'qr_checkins': qr_checkins,
                'attendance_rate': (total_present / len(attendance_records) * 100) if attendance_records else 0
            }
        }
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Attendance History Error")
        return {
            'success': False,
            'error': str(e)
        }


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

@frappe.whitelist()
def download_member_qr(member_name):
    """
    Download member's QR code as PNG file
    
    Args:
        member_name: Member ID
    """
    try:
        member = frappe.get_doc("Member", member_name)
        
        # Generate QR if doesn't exist
        if not hasattr(member, 'personal_qr_code') or not member.personal_qr_code:
            result = generate_personal_qr_code(member_name)
            if not result.get('success'):
                frappe.throw(_("Failed to generate QR code: {0}").format(result.get('error')))
            qr_data_url = result.get('qr_code')
        else:
            qr_data_url = member.personal_qr_code
        
        # Extract base64 data
        qr_base64 = qr_data_url.split(',')[1] if ',' in qr_data_url else qr_data_url
        qr_bytes = base64.b64decode(qr_base64)
        
        # Set response for download
        frappe.local.response.filename = f"{member.name}_QR_Code.png"
        frappe.local.response.filecontent = qr_bytes
        frappe.local.response.type = "download"
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "QR Download Error")
        frappe.throw(_("Failed to download QR code: {0}").format(str(e)))


@frappe.whitelist()
def regenerate_member_qr(member_name):
    """
    Regenerate QR code for a member
    Useful if QR format changed or code is compromised
    
    Args:
        member_name: Member ID
    
    Returns:
        dict: New QR code data
    """
    try:
        # Clear old QR code
        member = frappe.get_doc("Member", member_name)
        if hasattr(member, 'personal_qr_code'):
            member.personal_qr_code = None
            member.qr_generated_on = None
            member.save(ignore_permissions=True)
        
        # Generate new QR code
        return generate_personal_qr_code(member_name)
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "QR Regeneration Error")
        return {
            'success': False,
            'error': str(e)
        }


@frappe.whitelist()
def check_qr_library_installed():
    """
    Check if QR code library is installed
    
    Returns:
        dict: Installation status
    """
    return {
        'installed': HAS_QRCODE,
        'message': _('QR code library is installed') if HAS_QRCODE else _(
            'QR code library not installed. Run: bench pip install qrcode[pil]'
        )
    }


# ============================================================================
# SCHEDULED JOBS
# ============================================================================

def cleanup_old_checkins():
    """
    Cleanup old QR check-in records
    Run monthly to keep database clean
    Keeps last 6 months only
    """
    try:
        six_months_ago = add_days(nowdate(), -180)
        
        # Delete old attendance records with QR method
        deleted = frappe.db.sql("""
            DELETE FROM `tabMember Attendance`
            WHERE attendance_method = 'QR Code'
            AND attendance_date < %s
        """, (six_months_ago,))
        
        frappe.db.commit()
        
        frappe.logger().info(f"QR check-in cleanup: Removed records older than {six_months_ago}")
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "QR Cleanup Error")


def auto_generate_missing_qr_codes():
    """
    Automatically generate QR codes for members who don't have them
    Run weekly
    """
    try:
        # Find active members without QR codes
        members_without_qr = frappe.db.sql("""
            SELECT name
            FROM `tabMember`
            WHERE member_status = 'Active'
            AND (personal_qr_code IS NULL OR personal_qr_code = '')
            LIMIT 100
        """, as_dict=True)
        
        generated = 0
        for member in members_without_qr:
            try:
                result = generate_personal_qr_code(member.name)
                if result.get('success'):
                    generated += 1
            except:
                pass
        
        if generated > 0:
            frappe.logger().info(f"Auto-generated {generated} QR codes")
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Auto QR Generation Error")