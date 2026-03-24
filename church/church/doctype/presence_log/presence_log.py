# Copyright (c) 2025, kunle and contributors
# For license information, please see license.txt

# File: attendance_management/attendance_management/doctype/presence_log/presence_log.py

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now, today, get_datetime, time_diff_in_seconds, add_to_date
import json
from church.utils.mac_encryption_utils import MACAddressSecurityManager

class PresenceLog(Document):
    def autoname(self):
        """Auto-generate log ID with year and sequence"""
        from datetime import datetime
        year = datetime.now().year
        self.name = frappe.model.naming.make_autoname(f'LOG-{year}-.#######')
    
    def validate(self):
        """Validate log data before save"""
        # Set log_date from log_timestamp
        if self.log_timestamp and not self.log_date:
            self.log_date = get_datetime(self.log_timestamp).date()
        
        # Fetch person name if not set
        if self.person_registry and not self.person_name:
            self.person_name = frappe.db.get_value('Person Registry', self.person_registry, 'full_name')
        
        # Fetch organization unit and registry type
        if self.person_registry and not self.organization_unit:
            person_data = frappe.db.get_value('Person Registry', self.person_registry, 
                ['organization_unit', 'registry_type'], as_dict=True)
            if person_data:
                self.organization_unit = person_data.organization_unit
                self.registry_type = person_data.registry_type
    
    def after_insert(self):
        """Process attendance after log creation"""
        if not self.processed_to_attendance and self.is_verified:
            try:
                self.process_to_attendance()
            except Exception as e:
                frappe.log_error(f"Failed to process attendance for {self.name}: {str(e)}", 
                               "Attendance Processing Error")
    
    def process_to_attendance(self):
        """
        Process presence log to create/update Daily Presence Record
        Creates or updates attendance record based on this log
        """
        # Check if attendance record exists for this person and date
        existing = frappe.db.get_value('Daily Presence Record', {
            'person_registry': self.person_registry,
            'attendance_date': self.log_date
        }, 'name')
        
        if existing:
            # Update existing record
            attendance = frappe.get_doc('Daily Presence Record', existing)
            
            # Update check-in time if this log is earlier
            log_time = get_datetime(self.log_timestamp).time()
            
            if not attendance.check_in_time or log_time < attendance.check_in_time:
                attendance.check_in_time = log_time
                attendance.primary_detection_method = self.detection_method
                attendance.checkpoint_location = self.checkpoint_location
            
            # Calculate duration if check_out_time exists
            if attendance.check_out_time:
                attendance.total_duration_minutes = calculate_duration_minutes(
                    attendance.check_in_time, 
                    attendance.check_out_time
                )
            
            attendance.save(ignore_permissions=True)
        else:
            # Create new attendance record
            attendance = frappe.get_doc({
                'doctype': 'Daily Presence Record',
                'person_registry': self.person_registry,
                'person_name': self.person_name,
                'registry_type': self.registry_type,
                'organization_unit': self.organization_unit,
                'attendance_date': self.log_date,
                'presence_status': 'Present',
                'check_in_time': get_datetime(self.log_timestamp).time(),
                'primary_detection_method': self.detection_method,
                'checkpoint_location': self.checkpoint_location,
                'approval_status': 'Approved'
            })
            attendance.insert(ignore_permissions=True)
        
        # Mark log as processed
        self.db_set('processed_to_attendance', 1)
        self.db_set('attendance_record_reference', attendance.name)
        
        frappe.db.commit()
        
        return attendance.name


# ==================== WHITELISTED API METHODS ====================

@frappe.whitelist(allow_guest=True)
def mark_attendance_qr(qr_data, checkpoint_location=None):
    """
    Mark attendance by scanning QR code
    
    Args:
        qr_data: JSON string from QR code containing registry_id and token
        checkpoint_location: Optional checkpoint location name
    
    Returns:
        dict: {
            'success': bool,
            'message': str,
            'person_data': dict (if successful)
        }
    
    Example QR Data:
        {
            "type": "attendance",
            "registry_id": "PR-00001",
            "token": "abc123...",
            "name": "John Doe",
            "expires": "2025-03-09"
        }
    """
    try:
        # Parse QR data
        if isinstance(qr_data, str):
            qr_data = json.loads(qr_data)
        
        registry_id = qr_data.get('registry_id')
        token = qr_data.get('token')
        
        if not registry_id or not token:
            return {
                'success': False,
                'message': _('Invalid QR code format. Please request a new QR code.')
            }
        
        # Verify person exists
        if not frappe.db.exists('Person Registry', registry_id):
            return {
                'success': False,
                'message': _('Person not found in system. Please contact administrator.')
            }
        
        person = frappe.get_doc('Person Registry', registry_id)
        
        # Verify token
        if person.qr_security_token != token:
            return {
                'success': False,
                'message': _('Invalid or expired QR code. Please request a new one from administrator.'),
                'error_code': 'INVALID_TOKEN'
            }
        
        # Check token expiry
        if person.token_expiry_date:
            expiry_date = get_datetime(person.token_expiry_date)
            if expiry_date < get_datetime(today()):
                return {
                    'success': False,
                    'message': _('QR code has expired on {0}. Please request a new one.').format(
                        frappe.format(person.token_expiry_date, {'fieldtype': 'Date'})
                    ),
                    'error_code': 'TOKEN_EXPIRED',
                    'expired_date': str(person.token_expiry_date)
                }
        
        # Check if person is active
        if person.status != 'Active':
            return {
                'success': False,
                'message': _('Your account status is {0}. Please contact administrator.').format(person.status),
                'error_code': 'ACCOUNT_INACTIVE',
                'person_data': {
                    'name': person.full_name,
                    'status': person.status
                }
            }
        
        # Check if auto attendance is allowed
        if not person.allow_auto_attendance:
            return {
                'success': False,
                'message': _('Automatic attendance is disabled for your account. Please contact administrator.'),
                'error_code': 'AUTO_ATTENDANCE_DISABLED'
            }
        
        # Check if already logged today
        existing_log = frappe.db.exists('Presence Log', {
            'person_registry': registry_id,
            'log_date': today(),
            'detection_method': 'QR Code Scan'
        })
        
        if existing_log:
            existing = frappe.get_doc('Presence Log', existing_log)
            return {
                'success': False,
                'message': _('Attendance already marked at {0}').format(
                    frappe.format(existing.log_timestamp, {'fieldtype': 'Datetime'})
                ),
                'error_code': 'ALREADY_MARKED',
                'person_data': {
                    'registry_id': person.name,
                    'name': person.full_name,
                    'photo': person.profile_picture,
                    'organization_unit': person.organization_unit,
                    'designation': person.designation,
                    'check_in_time': str(existing.log_timestamp)
                }
            }
        
        # Get IP address and user agent
        ip_address = None
        user_agent = None
        
        if hasattr(frappe.local, 'request_ip'):
            ip_address = frappe.local.request_ip
        
        if hasattr(frappe, 'request') and frappe.request:
            user_agent = frappe.request.headers.get('User-Agent')
        
        # Create presence log
        log = frappe.get_doc({
            'doctype': 'Presence Log',
            'person_registry': registry_id,
            'person_name': person.full_name,
            'registry_type': person.registry_type,
            'organization_unit': person.organization_unit,
            'log_timestamp': now(),
            'log_date': today(),
            'detection_method': 'QR Code Scan',
            'checkpoint_location': checkpoint_location,
            'ip_address_recorded': ip_address,
            'user_agent_string': user_agent,
            'is_verified': 1,
            'verification_status': 'Verified'
        })
        log.insert(ignore_permissions=True)
        frappe.db.commit()
        
        # Return success with person details
        return {
            'success': True,
            'message': _('Welcome {0}! Attendance marked successfully at {1}.').format(
                person.full_name,
                frappe.format(log.log_timestamp, {'fieldtype': 'Time'})
            ),
            'log_id': log.name,
            'person_data': {
                'registry_id': person.name,
                'name': person.full_name,
                'photo': person.profile_picture,
                'organization_unit': person.organization_unit,
                'designation': person.designation,
                'registry_type': person.registry_type,
                'check_in_time': str(log.log_timestamp),
                'checkpoint_location': checkpoint_location
            }
        }
    
    except json.JSONDecodeError:
        return {
            'success': False,
            'message': _('Invalid QR code data format'),
            'error_code': 'JSON_DECODE_ERROR'
        }
    except Exception as e:
        frappe.log_error(message=str(e), title='QR Attendance Error')
        return {
            'success': False,
            'message': _('Error processing attendance. Please try again or contact administrator.'),
            'error_code': 'SYSTEM_ERROR',
            'error_detail': str(e) if frappe.conf.developer_mode else None
        }


@frappe.whitelist(allow_guest=True)
def mark_attendance_mac(mac_address, checkpoint_location=None, ip_address=None):
    """
    Mark attendance by MAC address detection
    This is typically called by background services monitoring network
    
    Args:
        mac_address: Device MAC address
        checkpoint_location: Optional checkpoint location
        ip_address: Optional IP address of device
    
    Returns:
        dict: Attendance status and person details
    """
    try:
        # Find person by MAC address using encryption manager
        mac_manager = MACAddressSecurityManager()
        person_data = mac_manager.find_person_by_mac(mac_address)
        
        if not person_data:
            return {
                'success': False,
                'message': _('Device not registered in system'),
                'error_code': 'DEVICE_NOT_REGISTERED',
                'mac_hint': mac_address[:8] + '...'  # Show partial MAC for debugging
            }
        
        registry_id = person_data['person_id']
        
        # Check if person is active
        if person_data['status'] != 'Active':
            return {
                'success': False,
                'message': _('Person account is {0}').format(person_data['status']),
                'error_code': 'ACCOUNT_INACTIVE'
            }
        
        # Check if MAC detection is enabled
        if not person_data['enable_mac_detection']:
            return {
                'success': False,
                'message': _('MAC detection is disabled for {0}').format(person_data['full_name']),
                'error_code': 'MAC_DETECTION_DISABLED'
            }
        
        # Check if auto attendance is allowed
        if not person_data['allow_auto_attendance']:
            return {
                'success': False,
                'message': _('Auto attendance is disabled for {0}').format(person_data['full_name']),
                'error_code': 'AUTO_ATTENDANCE_DISABLED'
            }
        
        # Check if already logged today
        existing_log = frappe.db.exists('Presence Log', {
            'person_registry': registry_id,
            'log_date': today(),
            'detection_method': 'MAC Detection'
        })
        
        if existing_log:
            # Update device last seen time
            mac_manager.update_device_last_seen(
                person_data['device_alias'],
                ip_address
            )
            
            existing = frappe.get_doc('Presence Log', existing_log)
            return {
                'success': False,
                'message': _('Attendance already marked for {0} at {1}').format(
                    person_data['full_name'],
                    frappe.format(existing.log_timestamp, {'fieldtype': 'Time'})
                ),
                'error_code': 'ALREADY_MARKED',
                'already_marked': True,
                'person_data': {
                    'registry_id': registry_id,
                    'name': person_data['full_name'],
                    'check_in_time': str(existing.log_timestamp)
                }
            }
        
        # Get device identifier hash for logging
        normalized_mac = mac_manager._normalize_mac_address(mac_address)
        device_hash = mac_manager._generate_mac_hash(normalized_mac) if normalized_mac else None
        
        # Create presence log
        log = frappe.get_doc({
            'doctype': 'Presence Log',
            'person_registry': registry_id,
            'person_name': person_data['full_name'],
            'registry_type': person_data.get('registry_type'),
            'organization_unit': person_data.get('organization_unit'),
            'log_timestamp': now(),
            'log_date': today(),
            'detection_method': 'MAC Detection',
            'checkpoint_location': checkpoint_location,
            'device_alias': person_data['device_alias'],
            'device_identifier_hash': device_hash,
            'ip_address_recorded': ip_address,
            'is_verified': 1,
            'verification_status': 'Verified',
            'system_notes': f"Auto-detected via device: {person_data['device_label']}"
        })
        log.insert(ignore_permissions=True)
        
        # Update device last seen
        mac_manager.update_device_last_seen(
            person_data['device_alias'],
            ip_address or log.ip_address_recorded
        )
        
        frappe.db.commit()
        
        return {
            'success': True,
            'message': _('Attendance marked automatically for {0}').format(person_data['full_name']),
            'log_id': log.name,
            'person_data': {
                'registry_id': registry_id,
                'name': person_data['full_name'],
                'organization_unit': person_data.get('organization_unit'),
                'device_alias': person_data['device_alias'],
                'device_label': person_data['device_label'],
                'check_in_time': str(log.log_timestamp)
            }
        }
    
    except Exception as e:
        frappe.log_error(message=str(e), title='MAC Attendance Error')
        return {
            'success': False,
            'message': _('Error processing MAC attendance'),
            'error_code': 'SYSTEM_ERROR',
            'error_detail': str(e) if frappe.conf.developer_mode else None
        }


@frappe.whitelist()
def mark_attendance_manual(registry_id, attendance_date=None, checkpoint_location=None, 
                          remarks=None, check_in_time=None):
    """
    Manually mark attendance for a person
    Requires appropriate permissions
    
    Args:
        registry_id: Person Registry ID
        attendance_date: Date of attendance (default: today)
        checkpoint_location: Location name
        remarks: Optional remarks
        check_in_time: Optional specific check-in time
    
    Returns:
        dict: Attendance status
    """
    if not frappe.has_permission('Presence Log', 'create'):
        frappe.throw(_('Insufficient permissions to mark manual attendance'))
    
    attendance_date = attendance_date or today()
    
    # Verify person exists
    if not frappe.db.exists('Person Registry', registry_id):
        return {
            'success': False,
            'message': _('Person not found')
        }
    
    person = frappe.get_doc('Person Registry', registry_id)
    
    # Check if already logged for this date
    existing_log = frappe.db.exists('Presence Log', {
        'person_registry': registry_id,
        'log_date': attendance_date,
        'detection_method': 'Manual Entry'
    })
    
    if existing_log:
        return {
            'success': False,
            'message': _('Manual attendance already marked for {0} on {1}').format(
                person.full_name,
                frappe.format(attendance_date, {'fieldtype': 'Date'})
            )
        }
    
    # Prepare timestamp
    if check_in_time:
        timestamp = f"{attendance_date} {check_in_time}"
    else:
        timestamp = now()
    
    # Create presence log
    log = frappe.get_doc({
        'doctype': 'Presence Log',
        'person_registry': registry_id,
        'person_name': person.full_name,
        'registry_type': person.registry_type,
        'organization_unit': person.organization_unit,
        'log_timestamp': timestamp,
        'log_date': attendance_date,
        'detection_method': 'Manual Entry',
        'checkpoint_location': checkpoint_location,
        'system_notes': remarks or f"Manually entered by {frappe.session.user}",
        'is_verified': 1,
        'verification_status': 'Verified'
    })
    log.insert(ignore_permissions=True)
    frappe.db.commit()
    
    return {
        'success': True,
        'message': _('Attendance marked manually for {0}').format(person.full_name),
        'log_id': log.name,
        'person_data': {
            'registry_id': registry_id,
            'name': person.full_name,
            'check_in_time': str(log.log_timestamp)
        }
    }


@frappe.whitelist()
def get_daily_logs(date=None, filters=None, limit=100):
    """
    Get all presence logs for a specific date with optional filters
    
    Args:
        date: Date to fetch logs (default: today)
        filters: Additional filters as JSON string
        limit: Maximum number of records (default: 100)
    
    Returns:
        list: Presence logs with person details
    """
    if not frappe.has_permission('Presence Log', 'read'):
        frappe.throw(_('Insufficient permissions to view logs'))
    
    date = date or today()
    
    conditions = ['log_date = %(date)s']
    values = {'date': date}
    
    # Apply additional filters
    if filters:
        if isinstance(filters, str):
            filters = json.loads(filters)
        
        for key, value in filters.items():
            if key in ['detection_method', 'checkpoint_location', 'organization_unit', 
                      'verification_status', 'registry_type']:
                conditions.append(f"{key} = %({key})s")
                values[key] = value
    
    where_clause = " AND ".join(conditions)
    
    logs = frappe.db.sql(f"""
        SELECT 
            name as log_id,
            person_registry,
            person_name,
            registry_type,
            organization_unit,
            log_timestamp,
            log_date,
            detection_method,
            checkpoint_location,
            device_alias,
            verification_status,
            processed_to_attendance,
            attendance_record_reference,
            ip_address_recorded
        FROM `tabPresence Log`
        WHERE {where_clause}
        ORDER BY log_timestamp DESC
        LIMIT {int(limit)}
    """, values, as_dict=True)
    
    return {
        'success': True,
        'count': len(logs),
        'date': date,
        'logs': logs
    }


@frappe.whitelist()
def get_person_logs(registry_id, from_date=None, to_date=None, limit=50):
    """
    Get presence logs for a specific person
    
    Args:
        registry_id: Person Registry ID
        from_date: Start date (optional)
        to_date: End date (optional)
        limit: Maximum records
    
    Returns:
        list: Presence logs for the person
    """
    # Check permissions - users can view their own logs
    person = frappe.get_doc('Person Registry', registry_id)
    
    if frappe.session.user != person.email_id and not frappe.has_permission('Presence Log', 'read'):
        frappe.throw(_('Insufficient permissions'))
    
    conditions = ['person_registry = %(registry_id)s']
    values = {'registry_id': registry_id}
    
    if from_date:
        conditions.append('log_date >= %(from_date)s')
        values['from_date'] = from_date
    
    if to_date:
        conditions.append('log_date <= %(to_date)s')
        values['to_date'] = to_date
    
    where_clause = " AND ".join(conditions)
    
    logs = frappe.db.sql(f"""
        SELECT 
            name as log_id,
            log_timestamp,
            log_date,
            detection_method,
            checkpoint_location,
            device_alias,
            verification_status,
            processed_to_attendance,
            attendance_record_reference
        FROM `tabPresence Log`
        WHERE {where_clause}
        ORDER BY log_timestamp DESC
        LIMIT {int(limit)}
    """, values, as_dict=True)
    
    return {
        'success': True,
        'registry_id': registry_id,
        'person_name': person.full_name,
        'count': len(logs),
        'logs': logs
    }


@frappe.whitelist()
def bulk_process_logs(date=None):
    """
    Bulk process unprocessed logs to attendance records
    Useful for batch processing at end of day
    
    Args:
        date: Date to process (default: today)
    
    Returns:
        dict: Processing summary with counts and errors
    """
    if not frappe.has_permission('Presence Log', 'write'):
        frappe.throw(_('Insufficient permissions to process logs'))
    
    date = date or today()
    
    # Get unprocessed logs
    logs = frappe.get_all('Presence Log', 
        filters={
            'log_date': date,
            'processed_to_attendance': 0,
            'is_verified': 1
        },
        fields=['name', 'person_name']
    )
    
    processed_count = 0
    errors = []
    
    for log_data in logs:
        try:
            log = frappe.get_doc('Presence Log', log_data.name)
            attendance_id = log.process_to_attendance()
            processed_count += 1
        except Exception as e:
            frappe.log_error(f"Processing error for {log_data.name}: {str(e)}", 
                           "Bulk Log Processing")
            errors.append({
                'log_id': log_data.name,
                'person_name': log_data.person_name,
                'error': str(e)
            })
    
    return {
        'success': True,
        'date': date,
        'total_logs': len(logs),
        'processed_count': processed_count,
        'error_count': len(errors),
        'errors': errors
    }


@frappe.whitelist()
def get_logs_summary(from_date=None, to_date=None, group_by='detection_method'):
    """
    Get summary statistics of presence logs
    
    Args:
        from_date: Start date (default: today)
        to_date: End date (default: today)
        group_by: Field to group by (detection_method, organization_unit, registry_type)
    
    Returns:
        dict: Summary statistics
    """
    if not frappe.has_permission('Presence Log', 'read'):
        frappe.throw(_('Insufficient permissions'))
    
    from_date = from_date or today()
    to_date = to_date or today()
    
    valid_group_fields = ['detection_method', 'organization_unit', 'registry_type', 'checkpoint_location']
    if group_by not in valid_group_fields:
        group_by = 'detection_method'
    
    summary = frappe.db.sql(f"""
        SELECT 
            {group_by} as category,
            COUNT(*) as total_logs,
            COUNT(DISTINCT person_registry) as unique_persons,
            SUM(CASE WHEN processed_to_attendance = 1 THEN 1 ELSE 0 END) as processed_count,
            SUM(CASE WHEN processed_to_attendance = 0 THEN 1 ELSE 0 END) as pending_count
        FROM `tabPresence Log`
        WHERE log_date BETWEEN %(from_date)s AND %(to_date)s
        GROUP BY {group_by}
        ORDER BY total_logs DESC
    """, {'from_date': from_date, 'to_date': to_date}, as_dict=True)
    
    # Get overall totals
    totals = frappe.db.sql("""
        SELECT 
            COUNT(*) as total_logs,
            COUNT(DISTINCT person_registry) as unique_persons,
            COUNT(DISTINCT log_date) as days_covered,
            SUM(CASE WHEN processed_to_attendance = 1 THEN 1 ELSE 0 END) as processed,
            SUM(CASE WHEN processed_to_attendance = 0 THEN 1 ELSE 0 END) as pending
        FROM `tabPresence Log`
        WHERE log_date BETWEEN %(from_date)s AND %(to_date)s
    """, {'from_date': from_date, 'to_date': to_date}, as_dict=True)
    
    return {
        'success': True,
        'from_date': from_date,
        'to_date': to_date,
        'group_by': group_by,
        'summary': summary,
        'totals': totals[0] if totals else {}
    }


@frappe.whitelist()
def delete_log(log_id, reason=None):
    """
    Delete a presence log with reason
    Requires admin permissions
    
    Args:
        log_id: Presence Log ID
        reason: Reason for deletion
    
    Returns:
        dict: Deletion status
    """
    if not frappe.has_permission('Presence Log', 'delete'):
        frappe.throw(_('Insufficient permissions to delete logs'))
    
    log = frappe.get_doc('Presence Log', log_id)
    person_name = log.person_name
    log_date = log.log_date
    
    # Log deletion for audit trail
    frappe.log_error(
        f"Log {log_id} deleted by {frappe.session.user}. "
        f"Person: {person_name}, Date: {log_date}, Reason: {reason or 'Not specified'}",
        "Presence Log Deletion"
    )
    
    log.delete()
    frappe.db.commit()
    
    return {
        'success': True,
        'message': _('Log deleted successfully'),
        'deleted_log_id': log_id,
        'person_name': person_name,
        'log_date': log_date
    }


# ==================== HELPER FUNCTIONS ====================

def calculate_duration_minutes(start_time, end_time):
    """
    Calculate duration in minutes between two times
    
    Args:
        start_time: Start time
        end_time: End time
    
    Returns:
        int: Duration in minutes
    """
    if not start_time or not end_time:
        return 0
    
    from datetime import datetime, timedelta
    
    # Convert to datetime objects if they're time objects
    if isinstance(start_time, str):
        start_time = datetime.strptime(start_time, '%H:%M:%S').time()
    if isinstance(end_time, str):
        end_time = datetime.strptime(end_time, '%H:%M:%S').time()
    
    # Create datetime objects for today
    today_date = datetime.now().date()
    start_dt = datetime.combine(today_date, start_time)
    end_dt = datetime.combine(today_date, end_time)
    
    # Handle overnight shifts
    if end_dt < start_dt:
        end_dt += timedelta(days=1)
    
    duration = end_dt - start_dt
    return int(duration.total_seconds() / 60)


def auto_process_yesterday_logs():
    """
    Scheduled job to auto-process yesterday's logs
    Run this as a daily scheduled job at midnight
    
    Usage in hooks.py:
        scheduler_events = {
            "daily": [
                "church.church.doctype.presence_log.presence_log.auto_process_yesterday_logs"
            ]
        }
    """
    yesterday = add_to_date(today(), days=-1)
    
    try:
        result = bulk_process_logs(date=yesterday)
        frappe.log_error(
            f"Auto-processed {result['processed_count']} logs for {yesterday}. "
            f"Errors: {result['error_count']}",
            "Auto Process Logs"
        )
    except Exception as e:
        frappe.log_error(f"Failed to auto-process logs for {yesterday}: {str(e)}", 
                        "Auto Process Logs Error")