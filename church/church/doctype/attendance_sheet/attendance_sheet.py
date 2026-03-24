# -*- coding: utf-8 -*-
# Copyright (c) 2026, Church Management and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, nowdate, get_time, nowtime, formatdate


class AttendanceSheet(Document):
    """Attendance Sheet Controller"""
    
    def validate(self):
        """Validation before save"""
        self.set_month()
        self.set_title()
        self.update_child_table_defaults()
        self.calculate_totals()
    
    def before_save(self):
        """Actions before save"""
        self.calculate_totals()
    
    def on_submit(self):
        """Actions after submit"""
        self.send_notification()
    
    def set_month(self):
        """Auto-set month from reporting date"""
        if self.reporting_date:
            reporting_date = getdate(self.reporting_date)
            self.month = reporting_date.strftime('%B')
    
    def set_title(self):
        """Auto-generate title"""
        if self.reporting_date and self.branch:
            self.title = f"{self.branch} - {formatdate(self.reporting_date, 'dd MMM yyyy')}"
    
    def update_child_table_defaults(self):
        """Update child table with default values"""
        for row in self.church_attendance_analysis:
            if not row.branch:
                row.branch = self.branch
            if not row.date:
                row.date = self.reporting_date
    
    def calculate_totals(self):
        """Calculate all totals"""
        total_men = 0
        total_women = 0
        total_children = 0
        total_new_men = 0
        total_new_women = 0
        total_new_children = 0
        
        for row in self.church_attendance_analysis:
            # Calculate row totals first
            row.total = (row.men or 0) + (row.women or 0) + (row.children or 0)
            row.new_total = (row.new_men or 0) + (row.new_women or 0) + (row.new_children or 0)
            row.existing_men = (row.men or 0) - (row.new_men or 0)
            row.existing_women = (row.women or 0) - (row.new_women or 0)
            row.existing_children = (row.children or 0) - (row.new_children or 0)
            row.existing_total = row.existing_men + row.existing_women + row.existing_children
            
            # Add to grand totals
            total_men += row.men or 0
            total_women += row.women or 0
            total_children += row.children or 0
            total_new_men += row.new_men or 0
            total_new_women += row.new_women or 0
            total_new_children += row.new_children or 0
        
        # Set grand totals
        self.total_men = total_men
        self.total_women = total_women
        self.total_children = total_children
        self.total_new_men = total_new_men
        self.total_new_women = total_new_women
        self.total_new_children = total_new_children
        
        # Calculate combined totals
        self.total_first = total_men + total_women + total_children
        self.total_second = total_new_men + total_new_women + total_new_children
        self.total_existing_men = total_men - total_new_men
        self.total_existing_women = total_women - total_new_women
        self.total_existing_children = total_children - total_new_children
        self.total_third = self.total_existing_men + self.total_existing_women + self.total_existing_children
    
    def send_notification(self):
        """Send email notification after submission"""
        send_attendance_sheet_notification(self)


# API Methods and Helper Functions

@frappe.whitelist()
def recalculate_attendance(attendance_sheet):
    """
    API method to recalculate attendance sheet
    Can be called from client-side or enqueued
    """
    doc = frappe.get_doc("Attendance Sheet", attendance_sheet)
    update_attendance_analysis(doc)
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    
    return {
        'success': True,
        'message': _('Attendance sheet recalculated successfully')
    }


def update_attendance_analysis(doc, method=None):
    """
    Automatically update Church Attendance Analysis child table
    Called on save/submit of Attendance Sheet
    """
    if not doc.church_attendance_analysis:
        return
    
    reporting_date = getdate(doc.reporting_date)
    branch = doc.branch
    
    for row in doc.church_attendance_analysis:
        if row.date != reporting_date or row.branch != branch:
            continue
        
        # Update based on programme type
        update_programme_attendance(row, reporting_date, branch)
    
    # Recalculate totals
    doc.calculate_totals()


def update_programme_attendance(row, reporting_date, branch):
    """Update attendance for a specific programme row"""
    
    programme = row.programme
    
    # Get all Church Attendance records for this programme
    attendance_filters = {
        "service_date": reporting_date,
        "service_type": programme,
        "branch": branch,
        "docstatus": 1,
        "present": 1
    }
    
    # Get members (non-visitors)
    members = frappe.get_all(
        "Church Attendance",
        filters={**attendance_filters, "is_visitor": 0},
        fields=["gender", "age"]
    )
    
    # Get visitors
    visitors = frappe.get_all(
        "Church Attendance",
        filters={**attendance_filters, "is_visitor": 1},
        fields=["gender", "age"]
    )
    
    # Calculate member attendance
    row.children = sum(1 for p in members if p.age < 13)
    row.men = sum(1 for p in members if p.age >= 13 and p.gender == "Male")
    row.women = sum(1 for p in members if p.age >= 13 and p.gender == "Female")
    
    # Calculate visitor attendance
    row.new_children = sum(1 for p in visitors if p.age < 13)
    row.new_men = sum(1 for p in visitors if p.age >= 13 and p.gender == "Male")
    row.new_women = sum(1 for p in visitors if p.age >= 13 and p.gender == "Female")
    
    # Calculate totals
    row.total = row.men + row.women + row.children
    row.new_total = row.new_men + row.new_women + row.new_children
    row.existing_men = row.men - row.new_men
    row.existing_women = row.women - row.new_women
    row.existing_children = row.children - row.new_children
    row.existing_total = row.existing_men + row.existing_women + row.existing_children


def send_attendance_sheet_notification(doc, method=None):
    """Send notification after attendance sheet is created"""
    
    # Get pastors and administrators
    recipients = frappe.get_all(
        "Member",
        filters={"is_a_pastor": 1},
        fields=["email"]
    )
    
    recipient_emails = [r.email for r in recipients if r.email]
    
    if not recipient_emails:
        return
    
    try:
        frappe.sendmail(
            recipients=recipient_emails,
            subject=_("Attendance Sheet Created - {0} ({1})").format(
                doc.branch,
                formatdate(doc.reporting_date, "dd MMM yyyy")
            ),
            message=_("""
                <p>Dear Pastor,</p>
                <p>An attendance sheet has been created for <strong>{0}</strong> on <strong>{1}</strong>.</p>
                <p>Please review and update as necessary.</p>
                <p><a href="{2}">View Attendance Sheet</a></p>
            """).format(
                doc.branch,
                formatdate(doc.reporting_date, "dd MMM yyyy"),
                frappe.utils.get_url_to_form("Attendance Sheet", doc.name)
            )
        )
    except Exception as e:
        frappe.log_error(
            f"Error sending attendance sheet notification: {str(e)}",
            "Attendance Sheet Notification"
        )


def auto_create_attendance_sheets():
    """
    Scheduled function to auto-create attendance sheets
    Run daily at configured time
    """
    today = getdate(nowdate())
    
    # Get all active branches
    branches = frappe.get_all("Branch", filters={"disabled": 0}, fields=["name"])
    
    created_count = 0
    
    for branch_doc in branches:
        branch = branch_doc.name
        
        # Check if attendance sheet already exists
        if frappe.db.exists("Attendance Sheet", {
            "reporting_date": today,
            "branch": branch
        }):
            continue
        
        # Create new attendance sheet
        try:
            attendance_sheet = frappe.get_doc({
                "doctype": "Attendance Sheet",
                "reporting_date": today,
                "branch": branch
            })
            
            # Add default programme rows
            add_default_programmes(attendance_sheet)
            
            attendance_sheet.insert(ignore_permissions=True)
            created_count += 1
            
        except Exception as e:
            frappe.log_error(
                f"Error creating attendance sheet for {branch}: {str(e)}",
                "Auto Create Attendance Sheet"
            )
    
    if created_count > 0:
        frappe.db.commit()
        frappe.logger().info(f"Created {created_count} attendance sheets")


def add_default_programmes(attendance_sheet):
    """Add default programme rows to attendance sheet"""
    
    reporting_date = getdate(attendance_sheet.reporting_date)
    day_of_week = reporting_date.weekday()  # Monday = 0, Sunday = 6
    
    # Get active programmes
    programmes = frappe.get_all(
        "Programme",
        filters={"disabled": 0},
        fields=["name", "programme_name"]
    )
    
    for prog in programmes:
        # Add appropriate programmes based on day of week
        should_add = False
        
        if day_of_week == 6:  # Sunday
            if prog.programme_name in ["Sunday Service", "Sunday School"]:
                should_add = True
        elif day_of_week in [2, 3]:  # Wednesday or Thursday (common midweek days)
            if "Midweek" in prog.programme_name or "Bible Study" in prog.programme_name:
                should_add = True
        
        if should_add:
            attendance_sheet.append("church_attendance_analysis", {
                "date": reporting_date,
                "programme": prog.name,
                "branch": attendance_sheet.branch,
                "men": 0,
                "women": 0,
                "children": 0,
                "new_men": 0,
                "new_women": 0,
                "new_children": 0
            })


def auto_submit_attendance_by_service():
    """
    Auto-submit attendance records based on service-specific times
    More granular than single auto-submit time
    """
    from frappe.utils import get_time, nowtime, nowdate, getdate
    
    today = getdate(nowdate())
    current_time = get_time(nowtime())
    
    # Get Church Settings
    church_settings = frappe.get_single("Church Settings")
    
    # Service-specific auto-submit times
    service_times = {
        "Sunday School": getattr(church_settings, "time_to_mark_sunday_school_attendance", None),
        "Sunday Service": getattr(church_settings, "time_to_mark_sunday_service_attendance", None),
        "Midweek Service": getattr(church_settings, "time_to_mark_midweek_attendance", None)
    }
    
    for service_type, submit_time in service_times.items():
        if not submit_time:
            continue
        
        submit_time_obj = get_time(submit_time)
        
        # Check if current time matches submit time (within the same hour and past the minute)
        if current_time.hour == submit_time_obj.hour and current_time.minute >= submit_time_obj.minute:
            auto_submit_service_attendance(today, service_type)


def auto_submit_service_attendance(service_date, service_type):
    """Auto-submit attendance for specific service type"""
    
    records = frappe.get_all(
        "Church Attendance",
        filters={
            "docstatus": 0,
            "service_date": service_date,
            "service_type": service_type
        },
        fields=["name"]
    )
    
    submitted_count = 0
    
    for record in records:
        try:
            doc = frappe.get_doc("Church Attendance", record.name)
            doc.submit()
            submitted_count += 1
        except Exception as e:
            frappe.log_error(
                f"Error auto-submitting {record.name}: {str(e)}",
                "Auto Submit Attendance"
            )
    
    if submitted_count > 0:
        frappe.db.commit()
        frappe.logger().info(
            f"Auto-submitted {submitted_count} {service_type} attendance records"
        )


@frappe.whitelist()
def get_attendance_trends(branch, start_date, end_date, service_type=None):
    """Get attendance trends for reporting"""
    
    filters = {
        "branch": branch,
        "service_date": ["between", [start_date, end_date]],
        "docstatus": 1,
        "present": 1
    }
    
    if service_type:
        filters["service_type"] = service_type
    
    # Get attendance records grouped by date
    attendance_by_date = frappe.db.sql("""
        SELECT 
            service_date,
            service_type,
            COUNT(*) as total_attendance,
            SUM(CASE WHEN is_visitor = 1 THEN 1 ELSE 0 END) as visitors,
            SUM(CASE WHEN gender = 'Male' AND age >= 13 THEN 1 ELSE 0 END) as men,
            SUM(CASE WHEN gender = 'Female' AND age >= 13 THEN 1 ELSE 0 END) as women,
            SUM(CASE WHEN age < 13 THEN 1 ELSE 0 END) as children
        FROM `tabChurch Attendance`
        WHERE branch = %(branch)s
            AND service_date BETWEEN %(start_date)s AND %(end_date)s
            AND docstatus = 1
            AND present = 1
            {service_filter}
        GROUP BY service_date, service_type
        ORDER BY service_date
    """.format(
        service_filter="AND service_type = %(service_type)s" if service_type else ""
    ), {
        "branch": branch,
        "start_date": start_date,
        "end_date": end_date,
        "service_type": service_type
    }, as_dict=1)
    
    return attendance_by_date