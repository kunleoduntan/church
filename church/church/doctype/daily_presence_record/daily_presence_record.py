# Copyright (c) 2025, kunle and contributors
# For license information, please see license.txt

# File: attendance_management/attendance_management/doctype/daily_presence_record/daily_presence_record.py

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now, today, get_datetime, add_days, date_diff, getdate
from datetime import datetime, time, timedelta
import json

class DailyPresenceRecord(Document):
    def autoname(self):
        """Auto-generate attendance record ID"""
        # Format: ATT-PR00001-20241209
        date_str = str(self.attendance_date).replace('-', '')
        self.name = f"ATT-{self.person_registry}-{date_str}"
    
    def validate(self):
        """Validate attendance record"""
        # Fetch person name if not set
        if self.person_registry and not self.person_name:
            person_data = frappe.db.get_value('Person Registry', self.person_registry,
                ['full_name', 'organization_unit', 'registry_type'], as_dict=True)
            if person_data:
                self.person_name = person_data.full_name
                self.organization_unit = person_data.organization_unit
                self.registry_type = person_data.registry_type
        
        # Calculate duration if both check-in and check-out exist
        if self.check_in_time and self.check_out_time:
            self.total_duration_minutes = self.calculate_duration()
            
            # Check for overtime
            if self.total_duration_minutes > 480:  # More than 8 hours
                self.is_overtime = 1
        
        # Validate status
        if self.check_in_time and not self.presence_status:
            self.presence_status = 'Present'
        
        # Check for late arrival
        if self.check_in_time and self.shift_assignment:
            self.check_late_arrival()
        
        # Check for early departure
        if self.check_out_time and self.shift_assignment:
            self.check_early_departure()
    
    def before_save(self):
        """Calculate analytics before saving"""
        if self.is_new():
            self.calculate_consecutive_days()
        
        if self.attendance_date:
            self.calculate_monthly_rate()
    
    def calculate_duration(self):
        """Calculate total duration in minutes"""
        if not self.check_in_time or not self.check_out_time:
            return 0
        
        # Convert to datetime objects
        today_date = getdate(self.attendance_date)
        
        check_in_dt = datetime.combine(today_date, self.check_in_time)
        check_out_dt = datetime.combine(today_date, self.check_out_time)
        
        # Handle overnight shifts
        if check_out_dt < check_in_dt:
            check_out_dt += timedelta(days=1)
        
        duration = check_out_dt - check_in_dt
        return int(duration.total_seconds() / 60)
    
    def check_late_arrival(self):
        """Check if arrival was late based on shift"""
        if not self.shift_assignment:
            return
        
        shift = frappe.get_doc('Shift Type', self.shift_assignment)
        
        if shift.start_time and self.check_in_time:
            grace_period = frappe.db.get_single_value('Attendance System Settings', 
                                                       'attendance_grace_period_minutes') or 15
            
            shift_start = datetime.combine(getdate(self.attendance_date), shift.start_time)
            actual_checkin = datetime.combine(getdate(self.attendance_date), self.check_in_time)
            
            # Add grace period
            allowed_time = shift_start + timedelta(minutes=grace_period)
            
            if actual_checkin > allowed_time:
                self.late_arrival = 1
    
    def check_early_departure(self):
        """Check if departure was early based on shift"""
        if not self.shift_assignment or not self.check_out_time:
            return
        
        shift = frappe.get_doc('Shift Type', self.shift_assignment)
        
        if shift.end_time:
            shift_end = datetime.combine(getdate(self.attendance_date), shift.end_time)
            actual_checkout = datetime.combine(getdate(self.attendance_date), self.check_out_time)
            
            if actual_checkout < shift_end:
                self.early_departure = 1
    
    def calculate_consecutive_days(self):
        """Calculate consecutive days present"""
        if self.presence_status != 'Present':
            self.consecutive_days_present = 0
            return
        
        # Get previous day's record
        previous_date = add_days(self.attendance_date, -1)
        previous_record = frappe.db.get_value('Daily Presence Record', {
            'person_registry': self.person_registry,
            'attendance_date': previous_date,
            'presence_status': 'Present'
        }, 'consecutive_days_present')
        
        if previous_record is not None:
            self.consecutive_days_present = previous_record + 1
        else:
            self.consecutive_days_present = 1
    
    def calculate_monthly_rate(self):
        """Calculate monthly attendance rate"""
        if not self.attendance_date:
            return
        
        # Get first and last day of month
        attendance_date = getdate(self.attendance_date)
        first_day = attendance_date.replace(day=1)
        
        # Calculate last day of month
        if attendance_date.month == 12:
            last_day = attendance_date.replace(year=attendance_date.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            last_day = attendance_date.replace(month=attendance_date.month + 1, day=1) - timedelta(days=1)
        
        # Count working days (exclude weekends if needed)
        total_days = (last_day - first_day).days + 1
        
        # Count present days
        present_days = frappe.db.count('Daily Presence Record', {
            'person_registry': self.person_registry,
            'attendance_date': ['between', [first_day, last_day]],
            'presence_status': 'Present'
        })
        
        if total_days > 0:
            self.monthly_attendance_rate = (present_days / total_days) * 100
        else:
            self.monthly_attendance_rate = 0


# ==================== WHITELISTED API METHODS ====================

@frappe.whitelist()
def mark_check_out(registry_id, attendance_date=None, check_out_time=None, checkpoint_location=None):
    """
    Mark check-out time for a person
    
    Args:
        registry_id: Person Registry ID
        attendance_date: Date (default: today)
        check_out_time: Check-out time (default: now)
        checkpoint_location: Optional location
    
    Returns:
        dict: Check-out status and duration
    """
    attendance_date = attendance_date or today()
    
    # Get attendance record
    record_id = f"ATT-{registry_id}-{str(attendance_date).replace('-', '')}"
    
    if not frappe.db.exists('Daily Presence Record', record_id):
        return {
            'success': False,
            'message': _('No check-in record found for this date')
        }
    
    record = frappe.get_doc('Daily Presence Record', record_id)
    
    # Check if already checked out
    if record.check_out_time:
        return {
            'success': False,
            'message': _('Already checked out at {0}').format(record.check_out_time),
            'check_out_time': str(record.check_out_time),
            'duration_minutes': record.total_duration_minutes
        }
    
    # Set check-out time
    if check_out_time:
        record.check_out_time = check_out_time
    else:
        record.check_out_time = datetime.now().time()
    
    if checkpoint_location:
        record.attendance_remarks = f"Checked out at {checkpoint_location}"
    
    record.save(ignore_permissions=True)
    frappe.db.commit()
    
    return {
        'success': True,
        'message': _('Check-out recorded successfully'),
        'person_name': record.person_name,
        'check_in_time': str(record.check_in_time),
        'check_out_time': str(record.check_out_time),
        'duration_minutes': record.total_duration_minutes,
        'duration_hours': round(record.total_duration_minutes / 60, 2)
    }


@frappe.whitelist()
def get_attendance_record(registry_id, attendance_date=None):
    """
    Get attendance record for a person on a specific date
    
    Args:
        registry_id: Person Registry ID
        attendance_date: Date (default: today)
    
    Returns:
        dict: Attendance record details
    """
    attendance_date = attendance_date or today()
    
    # Check permissions
    person = frappe.get_doc('Person Registry', registry_id)
    if frappe.session.user != person.email_id and not frappe.has_permission('Daily Presence Record', 'read'):
        frappe.throw(_('Insufficient permissions'))
    
    record_id = f"ATT-{registry_id}-{str(attendance_date).replace('-', '')}"
    
    if not frappe.db.exists('Daily Presence Record', record_id):
        return {
            'success': False,
            'message': _('No attendance record found'),
            'has_record': False
        }
    
    record = frappe.get_doc('Daily Presence Record', record_id)
    
    return {
        'success': True,
        'has_record': True,
        'record': {
            'registry_id': record.person_registry,
            'person_name': record.person_name,
            'attendance_date': str(record.attendance_date),
            'presence_status': record.presence_status,
            'check_in_time': str(record.check_in_time) if record.check_in_time else None,
            'check_out_time': str(record.check_out_time) if record.check_out_time else None,
            'duration_minutes': record.total_duration_minutes,
            'duration_hours': round(record.total_duration_minutes / 60, 2) if record.total_duration_minutes else 0,
            'detection_method': record.primary_detection_method,
            'checkpoint_location': record.checkpoint_location,
            'late_arrival': record.late_arrival,
            'early_departure': record.early_departure,
            'is_overtime': record.is_overtime,
            'remarks': record.attendance_remarks
        }
    }


@frappe.whitelist()
def get_person_attendance_history(registry_id, from_date=None, to_date=None, status_filter=None):
    """
    Get attendance history for a person
    
    Args:
        registry_id: Person Registry ID
        from_date: Start date (default: 30 days ago)
        to_date: End date (default: today)
        status_filter: Filter by status (Present/Absent/etc.)
    
    Returns:
        dict: Attendance history with statistics
    """
    # Check permissions
    person = frappe.get_doc('Person Registry', registry_id)
    if frappe.session.user != person.email_id and not frappe.has_permission('Daily Presence Record', 'read'):
        frappe.throw(_('Insufficient permissions'))
    
    to_date = to_date or today()
    from_date = from_date or add_days(to_date, -30)
    
    conditions = ['person_registry = %(registry_id)s']
    conditions.append('attendance_date BETWEEN %(from_date)s AND %(to_date)s')
    
    values = {
        'registry_id': registry_id,
        'from_date': from_date,
        'to_date': to_date
    }
    
    if status_filter:
        conditions.append('presence_status = %(status)s')
        values['status'] = status_filter
    
    where_clause = " AND ".join(conditions)
    
    records = frappe.db.sql(f"""
        SELECT 
            name as record_id,
            attendance_date,
            presence_status,
            check_in_time,
            check_out_time,
            total_duration_minutes,
            primary_detection_method,
            checkpoint_location,
            late_arrival,
            early_departure,
            is_overtime
        FROM `tabDaily Presence Record`
        WHERE {where_clause}
        ORDER BY attendance_date DESC
    """, values, as_dict=True)
    
    # Calculate statistics
    total_days = date_diff(to_date, from_date) + 1
    present_count = sum(1 for r in records if r.presence_status == 'Present')
    absent_count = sum(1 for r in records if r.presence_status == 'Absent')
    late_count = sum(1 for r in records if r.late_arrival)
    
    total_minutes = sum(r.total_duration_minutes or 0 for r in records)
    avg_hours = round(total_minutes / 60 / present_count, 2) if present_count > 0 else 0
    
    return {
        'success': True,
        'person_name': person.full_name,
        'from_date': from_date,
        'to_date': to_date,
        'statistics': {
            'total_days': total_days,
            'present_days': present_count,
            'absent_days': absent_count,
            'attendance_rate': round((present_count / total_days) * 100, 2) if total_days > 0 else 0,
            'late_arrivals': late_count,
            'average_hours_per_day': avg_hours
        },
        'records': records
    }


@frappe.whitelist()
def get_daily_attendance_report(attendance_date=None, filters=None):
    """
    Get comprehensive daily attendance report
    
    Args:
        attendance_date: Date (default: today)
        filters: Additional filters (organization_unit, registry_type, etc.)
    
    Returns:
        dict: Daily attendance report with summary
    """
    if not frappe.has_permission('Daily Presence Record', 'read'):
        frappe.throw(_('Insufficient permissions'))
    
    attendance_date = attendance_date or today()
    
    conditions = ['attendance_date = %(date)s']
    values = {'date': attendance_date}
    
    # Apply filters
    if filters:
        if isinstance(filters, str):
            filters = json.loads(filters)
        
        for key, value in filters.items():
            if key in ['organization_unit', 'registry_type', 'presence_status']:
                conditions.append(f"{key} = %({key})s")
                values[key] = value
    
    where_clause = " AND ".join(conditions)
    
    records = frappe.db.sql(f"""
        SELECT 
            person_registry,
            person_name,
            organization_unit,
            registry_type,
            presence_status,
            check_in_time,
            check_out_time,
            total_duration_minutes,
            primary_detection_method,
            checkpoint_location,
            late_arrival,
            early_departure
        FROM `tabDaily Presence Record`
        WHERE {where_clause}
        ORDER BY organization_unit, person_name
    """, values, as_dict=True)
    
    # Calculate summary
    total_records = len(records)
    present = sum(1 for r in records if r.presence_status == 'Present')
    absent = sum(1 for r in records if r.presence_status == 'Absent')
    late = sum(1 for r in records if r.late_arrival)
    
    # Group by organization unit
    by_unit = {}
    for record in records:
        unit = record.organization_unit or 'Unassigned'
        if unit not in by_unit:
            by_unit[unit] = {'total': 0, 'present': 0, 'absent': 0}
        by_unit[unit]['total'] += 1
        if record.presence_status == 'Present':
            by_unit[unit]['present'] += 1
        else:
            by_unit[unit]['absent'] += 1
    
    return {
        'success': True,
        'date': attendance_date,
        'summary': {
            'total_records': total_records,
            'present': present,
            'absent': absent,
            'late_arrivals': late,
            'attendance_rate': round((present / total_records) * 100, 2) if total_records > 0 else 0
        },
        'by_organization_unit': by_unit,
        'records': records
    }


@frappe.whitelist()
def mark_bulk_absent(registry_ids, attendance_date=None, remarks=None):
    """
    Mark multiple persons as absent for a date
    Useful for marking absences in bulk
    
    Args:
        registry_ids: List of Person Registry IDs (JSON array or comma-separated)
        attendance_date: Date (default: today)
        remarks: Optional remarks
    
    Returns:
        dict: Bulk marking summary
    """
    if not frappe.has_permission('Daily Presence Record', 'create'):
        frappe.throw(_('Insufficient permissions'))
    
    attendance_date = attendance_date or today()
    
    # Parse registry_ids
    if isinstance(registry_ids, str):
        if registry_ids.startswith('['):
            registry_ids = json.loads(registry_ids)
        else:
            registry_ids = [r.strip() for r in registry_ids.split(',')]
    
    marked_count = 0
    skipped = []
    errors = []
    
    for registry_id in registry_ids:
        try:
            # Check if record already exists
            record_id = f"ATT-{registry_id}-{str(attendance_date).replace('-', '')}"
            
            if frappe.db.exists('Daily Presence Record', record_id):
                skipped.append({
                    'registry_id': registry_id,
                    'reason': 'Record already exists'
                })
                continue
            
            # Get person details
            person = frappe.get_doc('Person Registry', registry_id)
            
            # Create absent record
            record = frappe.get_doc({
                'doctype': 'Daily Presence Record',
                'person_registry': registry_id,
                'person_name': person.full_name,
                'organization_unit': person.organization_unit,
                'registry_type': person.registry_type,
                'attendance_date': attendance_date,
                'presence_status': 'Absent',
                'primary_detection_method': 'Manual Entry',
                'attendance_remarks': remarks or 'Marked absent in bulk',
                'approval_status': 'Approved'
            })
            record.insert(ignore_permissions=True)
            marked_count += 1
            
        except Exception as e:
            errors.append({
                'registry_id': registry_id,
                'error': str(e)
            })
    
    frappe.db.commit()
    
    return {
        'success': True,
        'date': attendance_date,
        'marked_count': marked_count,
        'skipped_count': len(skipped),
        'error_count': len(errors),
        'skipped': skipped,
        'errors': errors
    }


@frappe.whitelist()
def update_attendance_status(record_id, new_status, remarks=None):
    """
    Update attendance status (for corrections)
    
    Args:
        record_id: Daily Presence Record ID
        new_status: New status (Present/Absent/Half Day/etc.)
        remarks: Reason for change
    
    Returns:
        dict: Update status
    """
    if not frappe.has_permission('Daily Presence Record', 'write'):
        frappe.throw(_('Insufficient permissions'))
    
    record = frappe.get_doc('Daily Presence Record', record_id)
    old_status = record.presence_status
    
    record.presence_status = new_status
    
    # Add to remarks
    change_note = f"Status changed from {old_status} to {new_status} by {frappe.session.user}"
    if remarks:
        change_note += f". Reason: {remarks}"
    
    if record.attendance_remarks:
        record.attendance_remarks += f"\n{change_note}"
    else:
        record.attendance_remarks = change_note
    
    record.save(ignore_permissions=True)
    frappe.db.commit()
    
    return {
        'success': True,
        'message': _('Attendance status updated'),
        'old_status': old_status,
        'new_status': new_status,
        'person_name': record.person_name
    }


@frappe.whitelist()
def get_monthly_summary(registry_id, year, month):
    """
    Get monthly attendance summary for a person
    
    Args:
        registry_id: Person Registry ID
        year: Year (e.g., 2024)
        month: Month (1-12)
    
    Returns:
        dict: Monthly summary with calendar view
    """
    # Check permissions
    person = frappe.get_doc('Person Registry', registry_id)
    if frappe.session.user != person.email_id and not frappe.has_permission('Daily Presence Record', 'read'):
        frappe.throw(_('Insufficient permissions'))
    
    # Calculate date range
    first_day = datetime(int(year), int(month), 1).date()
    if int(month) == 12:
        last_day = datetime(int(year) + 1, 1, 1).date() - timedelta(days=1)
    else:
        last_day = datetime(int(year), int(month) + 1, 1).date() - timedelta(days=1)
    
    # Get all records for the month
    records = frappe.get_all('Daily Presence Record',
        filters={
            'person_registry': registry_id,
            'attendance_date': ['between', [first_day, last_day]]
        },
        fields=['attendance_date', 'presence_status', 'check_in_time', 'check_out_time', 
                'total_duration_minutes', 'late_arrival', 'early_departure']
    )
    
    # Create calendar dict
    calendar = {}
    for record in records:
        day = record.attendance_date.day
        calendar[day] = {
            'status': record.presence_status,
            'check_in': str(record.check_in_time) if record.check_in_time else None,
            'check_out': str(record.check_out_time) if record.check_out_time else None,
            'duration_hours': round(record.total_duration_minutes / 60, 2) if record.total_duration_minutes else 0,
            'late': record.late_arrival,
            'early_departure': record.early_departure
        }
    
    # Calculate statistics
    total_days = (last_day - first_day).days + 1
    present_days = sum(1 for r in records if r.presence_status == 'Present')
    absent_days = sum(1 for r in records if r.presence_status == 'Absent')
    late_days = sum(1 for r in records if r.late_arrival)
    
    total_hours = sum(r.total_duration_minutes or 0 for r in records) / 60
    
    return {
        'success': True,
        'person_name': person.full_name,
        'year': year,
        'month': month,
        'month_name': datetime(int(year), int(month), 1).strftime('%B'),
        'statistics': {
            'total_days': total_days,
            'present_days': present_days,
            'absent_days': absent_days,
            'not_marked': total_days - present_days - absent_days,
            'late_days': late_days,
            'total_hours': round(total_hours, 2),
            'average_hours_per_day': round(total_hours / present_days, 2) if present_days > 0 else 0,
            'attendance_rate': round((present_days / total_days) * 100, 2) if total_days > 0 else 0
        },
        'calendar': calendar
    }


@frappe.whitelist()
def export_attendance_report(from_date, to_date, filters=None, format='excel'):
    """
    Export attendance report in Excel or PDF format
    
    Args:
        from_date: Start date
        to_date: End date
        filters: Additional filters (JSON string)
        format: 'excel' or 'pdf'
    
    Returns:
        File download
    """
    if not frappe.has_permission('Daily Presence Record', 'read'):
        frappe.throw(_('Insufficient permissions'))
    
    conditions = ['attendance_date BETWEEN %(from_date)s AND %(to_date)s']
    values = {'from_date': from_date, 'to_date': to_date}
    
    # Apply filters
    if filters:
        if isinstance(filters, str):
            filters = json.loads(filters)
        for key, value in filters.items():
            if key in ['organization_unit', 'registry_type']:
                conditions.append(f"{key} = %({key})s")
                values[key] = value
    
    where_clause = " AND ".join(conditions)
    
    data = frappe.db.sql(f"""
        SELECT 
            person_registry as 'Registry ID',
            person_name as 'Name',
            organization_unit as 'Unit',
            registry_type as 'Type',
            attendance_date as 'Date',
            presence_status as 'Status',
            check_in_time as 'Check In',
            check_out_time as 'Check Out',
            total_duration_minutes as 'Duration (Min)',
            primary_detection_method as 'Method',
            CASE WHEN late_arrival = 1 THEN 'Yes' ELSE 'No' END as 'Late',
            CASE WHEN early_departure = 1 THEN 'Yes' ELSE 'No' END as 'Early Departure'
        FROM `tabDaily Presence Record`
        WHERE {where_clause}
        ORDER BY attendance_date, organization_unit, person_name
    """, values, as_dict=True)
    
    if format == 'excel':
        # Export to Excel
        from frappe.utils.xlsxutils import make_xlsx
        xlsx_file = make_xlsx(data, "Attendance Report")
        
        frappe.response['filename'] = f'attendance_report_{from_date}_to_{to_date}.xlsx'
        frappe.response['filecontent'] = xlsx_file.getvalue()
        frappe.response['type'] = 'binary'
    
    return {
        'success': True,
        'record_count': len(data)
    }


# ==================== SCHEDULED JOBS ====================

def auto_mark_absent():
    """
    Scheduled job to automatically mark absent for persons with no attendance
    Run daily at end of day
    
    Usage in hooks.py:
        scheduler_events = {
            "daily": [
                "attendance_management.doctype.daily_presence_record.daily_presence_record.auto_mark_absent"
            ]
        }
    """
    settings = frappe.get_single('Attendance System Settings')
    days_threshold = settings.mark_absent_after_days or 1
    
    target_date = add_days(today(), -days_threshold)
    
    # Get all active persons
    active_persons = frappe.get_all('Person Registry',
        filters={'status': 'Active', 'allow_auto_attendance': 1},
        fields=['name', 'full_name', 'organization_unit', 'registry_type']
    )
    
    marked_count = 0
    
    for person in active_persons:
        # Check if attendance record exists
        record_id = f"ATT-{person.name}-{str(target_date).replace('-', '')}"
        
        if not frappe.db.exists('Daily Presence Record', record_id):
            try:
                # Create absent record
                record = frappe.get_doc({
                    'doctype': 'Daily Presence Record',
                    'person_registry': person.name,
                    'person_name': person.full_name,
                    'organization_unit': person.organization_unit,
                    'registry_type': person.registry_type,
                    'attendance_date': target_date,
                    'presence_status': 'Absent',
                    'primary_detection_method': 'Auto Mark',
                    'attendance_remarks': 'Auto-marked absent - no attendance log',
                    'approval_status': 'Approved'
                })
                record.insert(ignore_permissions=True)
                marked_count += 1
            except Exception as e:
                frappe.log_error(f"Failed to auto-mark absent for {person.name}: {str(e)}",
                               "Auto Mark Absent Error")
    
    frappe.db.commit()
    
    frappe.log_error(
        f"Auto-marked {marked_count} persons as absent for {target_date}",
        "Auto Mark Absent Summary"
    )