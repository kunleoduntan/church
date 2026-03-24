# Copyright (c) 2026, kunle and contributors
# For license information, please see license.txt

# -*- coding: utf-8 -*-
# Copyright (c) 2026, Church Management
# License: MIT
#
# church/church/report/attendance_analysis_report/attendance_analysis_report.py
# ─────────────────────────────────────────────────────────────────────────────

import frappe
from frappe import _
from frappe.utils import (
    getdate, add_days, add_months, flt, cint,
    formatdate, today, now_datetime
)
from frappe.model.document import Document
import json
from datetime import datetime, timedelta
from collections import defaultdict

def execute(filters=None):
    """
    Main entry point for ERPNext reports.
    Returns columns and data.
    """
    if not filters:
        filters = {}
    
    # Set default filters if not provided
    set_default_filters(filters)
    
    # Validate dates
    validate_filters(filters)
    
    # Get columns based on selected view type
    columns = get_columns(filters)
    
    # Get data based on filters
    data = get_data(filters)
    
    # Get chart data if enabled
    chart = get_chart_data(data, filters) if filters.get("show_chart") else None
    
    # Get summary report data
    summary = get_report_summary(data, filters)
    
    return columns, data, None, chart, summary


def set_default_filters(filters):
    """Set default values for missing filters."""
    if not filters.get("from_date"):
        filters["from_date"] = add_months(today(), -1)  # Default: last month
    
    if not filters.get("to_date"):
        filters["to_date"] = today()
    
    if not filters.get("view_type"):
        filters["view_type"] = "Detailed"
    
    if not filters.get("chart_type"):
        filters["chart_type"] = "Bar"


def validate_filters(filters):
    """Ensure date range is valid."""
    from_date = getdate(filters.get("from_date"))
    to_date = getdate(filters.get("to_date"))
    
    if from_date > to_date:
        frappe.throw(_("From Date cannot be greater than To Date"))
    
    # Limit date range for performance
    date_diff = (to_date - from_date).days
    if date_diff > 365:
        frappe.msgprint(
            _("Date range limited to 1 year. Showing last 365 days."),
            alert=True
        )
        filters["from_date"] = add_days(to_date, -365)


def get_columns(filters):
    """
    Return columns based on view type.
    Supports multiple view modes: Detailed, Summary, Weekly, Monthly, Demographics.
    """
    view_type = filters.get("view_type")
    
    # Common columns for all views
    common_columns = []
    
    if view_type == "Detailed":
        return get_detailed_columns()
    elif view_type == "Summary":
        return get_summary_columns()
    elif view_type == "Weekly":
        return get_weekly_columns()
    elif view_type == "Monthly":
        return get_monthly_columns()
    elif view_type == "Demographics":
        return get_demographics_columns()
    elif view_type == "Service Type Analysis":
        return get_service_type_columns()
    elif view_type == "Leader Dashboard":
        return get_leader_dashboard_columns()
    else:
        return get_detailed_columns()


def get_detailed_columns():
    """Detailed attendance records with all fields."""
    return [
        {
            "fieldname": "service_date",
            "label": _("Service Date"),
            "fieldtype": "Date",
            "width": 110
        },
        {
            "fieldname": "service_type",
            "label": _("Service Type"),
            "fieldtype": "Data",
            "width": 140
        },
        {
            "fieldname": "branch",
            "label": _("Branch"),
            "fieldtype": "Link",
            "options": "Branch",
            "width": 120
        },
        {
            "fieldname": "member_id",
            "label": _("Member ID"),
            "fieldtype": "Link",
            "options": "Member",
            "width": 100
        },
        {
            "fieldname": "full_name",
            "label": _("Full Name"),
            "fieldtype": "Data",
            "width": 150
        },
        {
            "fieldname": "demographic_group",
            "label": _("Demographic Group"),
            "fieldtype": "Data",
            "width": 120
        },
        {
            "fieldname": "present",
            "label": _("Present"),
            "fieldtype": "Check",
            "width": 70
        },
        {
            "fieldname": "time_in",
            "label": _("Time In"),
            "fieldtype": "Time",
            "width": 90
        },
        {
            "fieldname": "sunday_school_class",
            "label": _("Sunday School Class"),
            "fieldtype": "Data",
            "width": 120
        },
        {
            "fieldname": "is_visitor",
            "label": _("Is Visitor"),
            "fieldtype": "Check",
            "width": 70
        },
        {
            "fieldname": "visitor_source",
            "label": _("Visitor Source"),
            "fieldtype": "Data",
            "width": 120
        },
        {
            "fieldname": "checkin_method",
            "label": _("Check-in Method"),
            "fieldtype": "Data",
            "width": 100
        },
        {
            "fieldname": "marked_by",
            "label": _("Marked By"),
            "fieldtype": "Data",
            "width": 120
        },
        {
            "fieldname": "creation",
            "label": _("Created On"),
            "fieldtype": "Datetime",
            "width": 140
        }
    ]


def get_summary_columns():
    """Summary view - daily totals by service type."""
    return [
        {
            "fieldname": "service_date",
            "label": _("Service Date"),
            "fieldtype": "Date",
            "width": 110
        },
        {
            "fieldname": "day_of_week",
            "label": _("Day"),
            "fieldtype": "Data",
            "width": 100
        },
        {
            "fieldname": "branch",
            "label": _("Branch"),
            "fieldtype": "Link",
            "options": "Branch",
            "width": 120
        },
        {
            "fieldname": "sunday_service_count",
            "label": _("Sunday Service"),
            "fieldtype": "Int",
            "width": 110
        },
        {
            "fieldname": "sunday_school_count",
            "label": _("Sunday School"),
            "fieldtype": "Int",
            "width": 110
        },
        {
            "fieldname": "wednesday_service_count",
            "label": _("Wednesday Service"),
            "fieldtype": "Int",
            "width": 120
        },
        {
            "fieldname": "bible_study_count",
            "label": _("Bible Study"),
            "fieldtype": "Int",
            "width": 100
        },
        {
            "fieldname": "prayer_meeting_count",
            "label": _("Prayer Meeting"),
            "fieldtype": "Int",
            "width": 110
        },
        {
            "fieldname": "other_count",
            "label": _("Other Services"),
            "fieldtype": "Int",
            "width": 110
        },
        {
            "fieldname": "total_attendance",
            "label": _("Total"),
            "fieldtype": "Int",
            "width": 90
        },
        {
            "fieldname": "visitor_count",
            "label": _("Visitors"),
            "fieldtype": "Int",
            "width": 80
        }
    ]


def get_weekly_columns():
    """Weekly aggregated view."""
    return [
        {
            "fieldname": "week_start",
            "label": _("Week Starting"),
            "fieldtype": "Date",
            "width": 110
        },
        {
            "fieldname": "week_end",
            "label": _("Week Ending"),
            "fieldtype": "Date",
            "width": 110
        },
        {
            "fieldname": "branch",
            "label": _("Branch"),
            "fieldtype": "Link",
            "options": "Branch",
            "width": 120
        },
        {
            "fieldname": "week_number",
            "label": _("Week #"),
            "fieldtype": "Int",
            "width": 70
        },
        {
            "fieldname": "year",
            "label": _("Year"),
            "fieldtype": "Int",
            "width": 70
        },
        {
            "fieldname": "sunday_services",
            "label": _("Sunday Services"),
            "fieldtype": "Int",
            "width": 120
        },
        {
            "fieldname": "weekday_services",
            "label": _("Weekday Services"),
            "fieldtype": "Int",
            "width": 120
        },
        {
            "fieldname": "total_attendance",
            "label": _("Total Attendance"),
            "fieldtype": "Int",
            "width": 120
        },
        {
            "fieldname": "avg_per_service",
            "label": _("Avg/Service"),
            "fieldtype": "Float",
            "precision": 1,
            "width": 100
        },
        {
            "fieldname": "unique_members",
            "label": _("Unique Members"),
            "fieldtype": "Int",
            "width": 110
        },
        {
            "fieldname": "new_visitors",
            "label": _("New Visitors"),
            "fieldtype": "Int",
            "width": 100
        },
        {
            "fieldname": "growth_rate",
            "label": _("Growth %"),
            "fieldtype": "Float",
            "precision": 1,
            "width": 90
        }
    ]


def get_monthly_columns():
    """Monthly aggregated view."""
    return [
        {
            "fieldname": "month",
            "label": _("Month"),
            "fieldtype": "Data",
            "width": 100
        },
        {
            "fieldname": "year",
            "label": _("Year"),
            "fieldtype": "Int",
            "width": 70
        },
        {
            "fieldname": "month_start",
            "label": _("Month Start"),
            "fieldtype": "Date",
            "width": 110
        },
        {
            "fieldname": "branch",
            "label": _("Branch"),
            "fieldtype": "Link",
            "options": "Branch",
            "width": 120
        },
        {
            "fieldname": "total_services",
            "label": _("Total Services"),
            "fieldtype": "Int",
            "width": 110
        },
        {
            "fieldname": "total_attendance",
            "label": _("Total Attendance"),
            "fieldtype": "Int",
            "width": 120
        },
        {
            "fieldname": "avg_attendance",
            "label": _("Avg Attendance"),
            "fieldtype": "Float",
            "precision": 1,
            "width": 110
        },
        {
            "fieldname": "peak_attendance",
            "label": _("Peak Attendance"),
            "fieldtype": "Int",
            "width": 120
        },
        {
            "fieldname": "peak_date",
            "label": _("Peak Date"),
            "fieldtype": "Date",
            "width": 110
        },
        {
            "fieldname": "unique_members",
            "label": _("Unique Members"),
            "fieldtype": "Int",
            "width": 110
        },
        {
            "fieldname": "retention_rate",
            "label": _("Retention %"),
            "fieldtype": "Float",
            "precision": 1,
            "width": 100
        }
    ]


def get_demographics_columns():
    """Demographic breakdown view."""
    return [
        {
            "fieldname": "branch",
            "label": _("Branch"),
            "fieldtype": "Link",
            "options": "Branch",
            "width": 120
        },
        {
            "fieldname": "demographic_group",
            "label": _("Demographic Group"),
            "fieldtype": "Data",
            "width": 140
        },
        {
            "fieldname": "total_members",
            "label": _("Total Members"),
            "fieldtype": "Int",
            "width": 110
        },
        {
            "fieldname": "active_members",
            "label": _("Active Members"),
            "fieldtype": "Int",
            "width": 110
        },
        {
            "fieldname": "attended_count",
            "label": _("Attended (Period)"),
            "fieldtype": "Int",
            "width": 120
        },
        {
            "fieldname": "attendance_rate",
            "label": _("Attendance Rate %"),
            "fieldtype": "Float",
            "precision": 1,
            "width": 120
        },
        {
            "fieldname": "avg_attendance",
            "label": _("Avg Per Service"),
            "fieldtype": "Float",
            "precision": 1,
            "width": 120
        },
        {
            "fieldname": "visitor_count",
            "label": _("Visitors"),
            "fieldtype": "Int",
            "width": 90
        },
        {
            "fieldname": "first_timers",
            "label": _("First Timers"),
            "fieldtype": "Int",
            "width": 100
        }
    ]


def get_service_type_columns():
    """Service type analysis view."""
    return [
        {
            "fieldname": "service_type",
            "label": _("Service Type"),
            "fieldtype": "Data",
            "width": 160
        },
        {
            "fieldname": "total_occurrences",
            "label": _("Total Services"),
            "fieldtype": "Int",
            "width": 110
        },
        {
            "fieldname": "total_attendance",
            "label": _("Total Attendance"),
            "fieldtype": "Int",
            "width": 120
        },
        {
            "fieldname": "avg_attendance",
            "label": _("Average"),
            "fieldtype": "Float",
            "precision": 1,
            "width": 100
        },
        {
            "fieldname": "peak_attendance",
            "label": _("Peak"),
            "fieldtype": "Int",
            "width": 90
        },
        {
            "fieldname": "lowest_attendance",
            "label": _("Lowest"),
            "fieldtype": "Int",
            "width": 90
        },
        {
            "fieldname": "trend_direction",
            "label": _("Trend"),
            "fieldtype": "Data",
            "width": 80
        },
        {
            "fieldname": "visitor_percentage",
            "label": _("Visitors %"),
            "fieldtype": "Float",
            "precision": 1,
            "width": 100
        },
        {
            "fieldname": "member_retention",
            "label": _("Member Retention %"),
            "fieldtype": "Float",
            "precision": 1,
            "width": 130
        }
    ]


def get_leader_dashboard_columns():
    """Leadership dashboard view."""
    return [
        {
            "fieldname": "branch",
            "label": _("Branch"),
            "fieldtype": "Link",
            "options": "Branch",
            "width": 120
        },
        {
            "fieldname": "leader_name",
            "label": _("Branch Leader"),
            "fieldtype": "Data",
            "width": 150
        },
        {
            "fieldname": "total_members",
            "label": _("Total Members"),
            "fieldtype": "Int",
            "width": 110
        },
        {
            "fieldname": "active_members",
            "label": _("Active"),
            "fieldtype": "Int",
            "width": 80
        },
        {
            "fieldname": "inactive_members",
            "label": _("Inactive"),
            "fieldtype": "Int",
            "width": 80
        },
        {
            "fieldname": "attendance_rate",
            "label": _("Attendance Rate"),
            "fieldtype": "Percent",
            "width": 110
        },
        {
            "fieldname": "missed_2_weeks",
            "label": _("Missed 2+ Weeks"),
            "fieldtype": "Int",
            "width": 120
        },
        {
            "fieldname": "missed_4_weeks",
            "label": _("Missed 4+ Weeks"),
            "fieldtype": "Int",
            "width": 120
        },
        {
            "fieldname": "need_followup",
            "label": _("Need Follow-up"),
            "fieldtype": "Int",
            "width": 110
        },
        {
            "fieldname": "followup_todos",
            "label": _("Open ToDos"),
            "fieldtype": "Int",
            "width": 100
        },
        {
            "fieldname": "new_members",
            "label": _("New Members"),
            "fieldtype": "Int",
            "width": 100
        }
    ]


def get_data(filters):
    """
    Main data retrieval function.
    Routes to appropriate data method based on view type.
    """
    view_type = filters.get("view_type", "Detailed")
    
    if view_type == "Detailed":
        return get_detailed_data(filters)
    elif view_type == "Summary":
        return get_summary_data(filters)
    elif view_type == "Weekly":
        return get_weekly_data(filters)
    elif view_type == "Monthly":
        return get_monthly_data(filters)
    elif view_type == "Demographics":
        return get_demographics_data(filters)
    elif view_type == "Service Type Analysis":
        return get_service_type_data(filters)
    elif view_type == "Leader Dashboard":
        return get_leader_dashboard_data(filters)
    else:
        return get_detailed_data(filters)


def build_attendance_query(filters):
    """
    Build the base SQL query with dynamic filters.
    Returns SQL string and parameters.
    """
    conditions = ["ca.docstatus = 1"]  # Only submitted records
    params = {}
    
    # Date range filter
    if filters.get("from_date"):
        conditions.append("ca.service_date >= %(from_date)s")
        params["from_date"] = filters.get("from_date")
    
    if filters.get("to_date"):
        conditions.append("ca.service_date <= %(to_date)s")
        params["to_date"] = filters.get("to_date")
    
    # Branch filter
    if filters.get("branch"):
        if isinstance(filters.get("branch"), list):
            conditions.append("ca.branch IN %(branch)s")
            params["branch"] = tuple(filters.get("branch"))
        else:
            conditions.append("ca.branch = %(branch)s")
            params["branch"] = filters.get("branch")
    
    # Service type filter
    if filters.get("service_type"):
        if isinstance(filters.get("service_type"), list):
            conditions.append("ca.service_type IN %(service_type)s")
            params["service_type"] = tuple(filters.get("service_type"))
        else:
            conditions.append("ca.service_type = %(service_type)s")
            params["service_type"] = filters.get("service_type")
    
    # Demographic group filter
    if filters.get("demographic_group"):
        conditions.append("m.demographic_group = %(demographic_group)s")
        params["demographic_group"] = filters.get("demographic_group")
    
    # Present/absent filter
    if filters.get("present") is not None:
        conditions.append("ca.present = %(present)s")
        params["present"] = cint(filters.get("present"))
    
    # Visitor filter
    if filters.get("is_visitor") is not None:
        conditions.append("ca.is_visitor = %(is_visitor)s")
        params["is_visitor"] = cint(filters.get("is_visitor"))
    
    # Sunday School Class filter
    if filters.get("sunday_school_class"):
        conditions.append("ca.sunday_school_class = %(sunday_school_class)s")
        params["sunday_school_class"] = filters.get("sunday_school_class")
    
    # Member filter
    if filters.get("member_id"):
        conditions.append("ca.member_id = %(member_id)s")
        params["member_id"] = filters.get("member_id")
    
    # Check-in method filter
    if filters.get("checkin_method"):
        conditions.append("ca.checkin_method = %(checkin_method)s")
        params["checkin_method"] = filters.get("checkin_method")
    
    # Minimum attendance count filter
    if filters.get("min_attendance") and cint(filters.get("min_attendance")) > 0:
        conditions.append("""
            ca.member_id IN (
                SELECT member_id 
                FROM `tabChurch Attendance` 
                WHERE docstatus = 1 
                AND service_date BETWEEN %(from_date)s AND %(to_date)s
                GROUP BY member_id 
                HAVING COUNT(*) >= %(min_attendance)s
            )
        """)
        params["min_attendance"] = cint(filters.get("min_attendance"))
    
    # Build the query
    query = f"""
        SELECT 
            ca.name,
            ca.service_date,
            ca.service_type,
            ca.branch,
            ca.member_id,
            ca.full_name,
            ca.present,
            ca.time_in,
            ca.sunday_school_class,
            ca.is_visitor,
            ca.visitor_source,
            ca.checkin_method,
            ca.checkin_gate,
            ca.checkin_device,
            ca.demography,
            ca.marked_by,
            ca.creation,
            ca.modified,
            m.demographic_group,
            m.member_status,
            m.mobile_phone,
            m.email
        FROM `tabChurch Attendance` ca
        LEFT JOIN `tabMember` m ON ca.member_id = m.name
        WHERE {' AND '.join(conditions)}
        ORDER BY ca.service_date DESC, ca.service_type, ca.branch
    """
    
    return query, params


def get_detailed_data(filters):
    """Get detailed attendance records."""
    query, params = build_attendance_query(filters)
    return frappe.db.sql(query, params, as_dict=True)


def get_summary_data(filters):
    """Get daily summary by service type."""
    conditions = ["docstatus = 1"]
    params = {}
    
    if filters.get("from_date"):
        conditions.append("service_date >= %(from_date)s")
        params["from_date"] = filters.get("from_date")
    
    if filters.get("to_date"):
        conditions.append("service_date <= %(to_date)s")
        params["to_date"] = filters.get("to_date")
    
    if filters.get("branch"):
        if isinstance(filters.get("branch"), list):
            conditions.append("branch IN %(branch)s")
            params["branch"] = tuple(filters.get("branch"))
        else:
            conditions.append("branch = %(branch)s")
            params["branch"] = filters.get("branch")
    
    query = f"""
        SELECT 
            service_date,
            DAYNAME(service_date) as day_of_week,
            branch,
            SUM(CASE WHEN service_type = 'Sunday Service' AND present = 1 THEN 1 ELSE 0 END) as sunday_service_count,
            SUM(CASE WHEN service_type = 'Sunday School' AND present = 1 THEN 1 ELSE 0 END) as sunday_school_count,
            SUM(CASE WHEN service_type = 'Wednesday Service' AND present = 1 THEN 1 ELSE 0 END) as wednesday_service_count,
            SUM(CASE WHEN service_type = 'Bible Study' AND present = 1 THEN 1 ELSE 0 END) as bible_study_count,
            SUM(CASE WHEN service_type = 'Prayer Meeting' AND present = 1 THEN 1 ELSE 0 END) as prayer_meeting_count,
            SUM(CASE WHEN service_type NOT IN ('Sunday Service', 'Sunday School', 'Wednesday Service', 'Bible Study', 'Prayer Meeting') AND present = 1 THEN 1 ELSE 0 END) as other_count,
            SUM(CASE WHEN present = 1 THEN 1 ELSE 0 END) as total_attendance,
            SUM(CASE WHEN is_visitor = 1 THEN 1 ELSE 0 END) as visitor_count
        FROM `tabChurch Attendance`
        WHERE {' AND '.join(conditions)}
        GROUP BY service_date, branch
        ORDER BY service_date DESC, branch
    """
    
    return frappe.db.sql(query, params, as_dict=True)


def get_weekly_data(filters):
    """Get weekly aggregated data with growth metrics."""
    conditions = ["ca.docstatus = 1"]
    params = {}
    
    if filters.get("from_date"):
        conditions.append("ca.service_date >= %(from_date)s")
        params["from_date"] = filters.get("from_date")
    
    if filters.get("to_date"):
        conditions.append("ca.service_date <= %(to_date)s")
        params["to_date"] = filters.get("to_date")
    
    if filters.get("branch"):
        if isinstance(filters.get("branch"), list):
            conditions.append("ca.branch IN %(branch)s")
            params["branch"] = tuple(filters.get("branch"))
        else:
            conditions.append("ca.branch = %(branch)s")
            params["branch"] = filters.get("branch")
    
    # Complex query with week grouping
    query = f"""
        SELECT 
            DATE_SUB(ca.service_date, INTERVAL WEEKDAY(ca.service_date) DAY) as week_start,
            DATE_ADD(DATE_SUB(ca.service_date, INTERVAL WEEKDAY(ca.service_date) DAY), INTERVAL 6 DAY) as week_end,
            ca.branch,
            WEEK(ca.service_date) as week_number,
            YEAR(ca.service_date) as year,
            COUNT(DISTINCT CASE WHEN ca.service_type IN ('Sunday Service', 'Sunday School') THEN ca.service_date END) as sunday_services,
            COUNT(DISTINCT CASE WHEN ca.service_type NOT IN ('Sunday Service', 'Sunday School') THEN ca.service_date END) as weekday_services,
            SUM(CASE WHEN ca.present = 1 THEN 1 ELSE 0 END) as total_attendance,
            ROUND(SUM(CASE WHEN ca.present = 1 THEN 1 ELSE 0 END) / 
                  NULLIF(COUNT(DISTINCT ca.service_date), 0), 1) as avg_per_service,
            COUNT(DISTINCT ca.member_id) as unique_members,
            SUM(CASE WHEN ca.is_visitor = 1 THEN 1 ELSE 0 END) as new_visitors,
            0 as growth_rate  -- Will calculate in Python
        FROM `tabChurch Attendance` ca
        WHERE {' AND '.join(conditions)}
        GROUP BY week_start, ca.branch
        ORDER BY week_start DESC, ca.branch
    """
    
    data = frappe.db.sql(query, params, as_dict=True)
    
    # Calculate growth rates
    for i, row in enumerate(data):
        if i < len(data) - 1:
            current = row["total_attendance"]
            previous = data[i + 1]["total_attendance"]
            if previous and previous > 0:
                row["growth_rate"] = round(((current - previous) / previous) * 100, 1)
            else:
                row["growth_rate"] = 0
    
    return data


def get_monthly_data(filters):
    """Get monthly aggregated data."""
    conditions = ["ca.docstatus = 1"]
    params = {}
    
    if filters.get("from_date"):
        conditions.append("ca.service_date >= %(from_date)s")
        params["from_date"] = filters.get("from_date")
    
    if filters.get("to_date"):
        conditions.append("ca.service_date <= %(to_date)s")
        params["to_date"] = filters.get("to_date")
    
    if filters.get("branch"):
        if isinstance(filters.get("branch"), list):
            conditions.append("ca.branch IN %(branch)s")
            params["branch"] = tuple(filters.get("branch"))
        else:
            conditions.append("ca.branch = %(branch)s")
            params["branch"] = filters.get("branch")
    
    query = f"""
        SELECT 
            DATE_FORMAT(ca.service_date, '%M') as month,
            MONTH(ca.service_date) as month_num,
            YEAR(ca.service_date) as year,
            DATE_FORMAT(ca.service_date, '%Y-%m-01') as month_start,
            ca.branch,
            COUNT(DISTINCT ca.service_date) as total_services,
            SUM(CASE WHEN ca.present = 1 THEN 1 ELSE 0 END) as total_attendance,
            ROUND(AVG(CASE WHEN ca.present = 1 THEN 1 ELSE 0 END), 1) as avg_attendance,
            MAX(CASE WHEN ca.present = 1 THEN 
                (SELECT COUNT(*) FROM `tabChurch Attendance` ca2 
                 WHERE ca2.service_date = ca.service_date AND ca2.present = 1) 
            ELSE 0 END) as peak_attendance,
            (SELECT ca3.service_date 
             FROM `tabChurch Attendance` ca3 
             WHERE ca3.service_date = ca.service_date 
               AND ca3.present = 1 
             GROUP BY ca3.service_date 
             ORDER BY COUNT(*) DESC 
             LIMIT 1) as peak_date,
            COUNT(DISTINCT ca.member_id) as unique_members,
            0 as retention_rate
        FROM `tabChurch Attendance` ca
        WHERE {' AND '.join(conditions)}
        GROUP BY year, month_num, ca.branch
        ORDER BY year DESC, month_num DESC, ca.branch
    """
    
    data = frappe.db.sql(query, params, as_dict=True)
    
    # Calculate retention rates (members who attended at least twice)
    for row in data:
        month_start = row["month_start"]
        month_end = add_months(month_start, 1)
        
        # Count members who attended at least twice in the month
        repeat_members = frappe.db.sql("""
            SELECT COUNT(DISTINCT member_id) 
            FROM `tabChurch Attendance` 
            WHERE docstatus = 1 
                AND service_date BETWEEN %s AND %s
                AND present = 1
            GROUP BY member_id
            HAVING COUNT(*) >= 2
        """, (month_start, month_end))
        
        if repeat_members and row["unique_members"] > 0:
            row["retention_rate"] = round((len(repeat_members) / row["unique_members"]) * 100, 1)
    
    return data


def get_demographics_data(filters):
    """Get demographic breakdown."""
    conditions = ["ca.docstatus = 1"]
    params = {}
    
    if filters.get("from_date"):
        conditions.append("ca.service_date >= %(from_date)s")
        params["from_date"] = filters.get("from_date")
    
    if filters.get("to_date"):
        conditions.append("ca.service_date <= %(to_date)s")
        params["to_date"] = filters.get("to_date")
    
    if filters.get("branch"):
        if isinstance(filters.get("branch"), list):
            conditions.append("ca.branch IN %(branch)s")
            params["branch"] = tuple(filters.get("branch"))
        else:
            conditions.append("ca.branch = %(branch)s")
            params["branch"] = filters.get("branch")
    
    # Get member counts by demographic group
    member_stats = frappe.db.sql("""
        SELECT 
            m.demographic_group,
            m.branch,
            COUNT(DISTINCT m.name) as total_members,
            SUM(CASE WHEN m.member_status = 'Active' THEN 1 ELSE 0 END) as active_members
        FROM `tabMember` m
        WHERE m.status != 'Disabled'
        GROUP BY m.demographic_group, m.branch
    """, as_dict=True)
    
    member_dict = {}
    for stat in member_stats:
        key = (stat["demographic_group"] or "Unspecified", stat["branch"] or "")
        member_dict[key] = stat
    
    # Get attendance stats by demographic group
    query = f"""
        SELECT 
            COALESCE(m.demographic_group, 'Unspecified') as demographic_group,
            ca.branch,
            COUNT(DISTINCT ca.member_id) as attended_count,
            SUM(CASE WHEN ca.present = 1 THEN 1 ELSE 0 END) as total_attendance,
            COUNT(DISTINCT ca.service_date) as service_days,
            SUM(CASE WHEN ca.is_visitor = 1 THEN 1 ELSE 0 END) as visitor_count,
            SUM(CASE WHEN ca.is_visitor = 1 AND ca.visitor_source = 'First Time' THEN 1 ELSE 0 END) as first_timers
        FROM `tabChurch Attendance` ca
        LEFT JOIN `tabMember` m ON ca.member_id = m.name
        WHERE {' AND '.join(conditions)}
        GROUP BY demographic_group, ca.branch
        ORDER BY demographic_group, ca.branch
    """
    
    attendance_stats = frappe.db.sql(query, params, as_dict=True)
    
    # Combine the data
    result = []
    for stat in attendance_stats:
        key = (stat["demographic_group"], stat["branch"] or "")
        member_stat = member_dict.get(key, {})
        
        row = {
            "branch": stat["branch"] or "",
            "demographic_group": stat["demographic_group"],
            "total_members": member_stat.get("total_members", 0),
            "active_members": member_stat.get("active_members", 0),
            "attended_count": stat["attended_count"],
            "visitor_count": stat["visitor_count"],
            "first_timers": stat["first_timers"],
            "attendance_rate": 0,
            "avg_attendance": 0
        }
        
        if member_stat.get("active_members", 0) > 0:
            row["attendance_rate"] = round(
                (stat["attended_count"] / member_stat["active_members"]) * 100, 1
            )
        
        if stat["service_days"] > 0:
            row["avg_attendance"] = round(stat["total_attendance"] / stat["service_days"], 1)
        
        result.append(row)
    
    return result


def get_service_type_data(filters):
    """Get service type analysis."""
    conditions = ["docstatus = 1"]
    params = {}
    
    if filters.get("from_date"):
        conditions.append("service_date >= %(from_date)s")
        params["from_date"] = filters.get("from_date")
    
    if filters.get("to_date"):
        conditions.append("service_date <= %(to_date)s")
        params["to_date"] = filters.get("to_date")
    
    if filters.get("branch"):
        if isinstance(filters.get("branch"), list):
            conditions.append("branch IN %(branch)s")
            params["branch"] = tuple(filters.get("branch"))
        else:
            conditions.append("branch = %(branch)s")
            params["branch"] = filters.get("branch")
    
    query = f"""
        SELECT 
            service_type,
            COUNT(DISTINCT service_date) as total_occurrences,
            SUM(CASE WHEN present = 1 THEN 1 ELSE 0 END) as total_attendance,
            ROUND(AVG(CASE WHEN present = 1 THEN 1 ELSE 0 END), 1) as avg_attendance,
            MAX(CASE WHEN present = 1 THEN 
                (SELECT COUNT(*) FROM `tabChurch Attendance` ca2 
                 WHERE ca2.service_date = ca.service_date 
                   AND ca2.service_type = ca.service_type
                   AND ca2.present = 1) 
            ELSE 0 END) as peak_attendance,
            MIN(CASE WHEN present = 1 THEN 
                (SELECT COUNT(*) FROM `tabChurch Attendance` ca2 
                 WHERE ca2.service_date = ca.service_date 
                   AND ca2.service_type = ca.service_type
                   AND ca2.present = 1) 
            ELSE 999999 END) as lowest_attendance,
            ROUND(SUM(CASE WHEN is_visitor = 1 THEN 1 ELSE 0 END) / 
                  NULLIF(SUM(CASE WHEN present = 1 THEN 1 ELSE 0 END), 0) * 100, 1) as visitor_percentage,
            0 as trend_direction,
            0 as member_retention
        FROM `tabChurch Attendance` ca
        WHERE {' AND '.join(conditions)}
        GROUP BY service_type
        ORDER BY total_attendance DESC
    """
    
    data = frappe.db.sql(query, params, as_dict=True)
    
    # Calculate trends and retention
    for row in data:
        # Simple trend based on first half vs second half
        if filters.get("from_date") and filters.get("to_date"):
            mid_date = add_days(
                getdate(filters.get("from_date")), 
                (getdate(filters.get("to_date")) - getdate(filters.get("from_date"))).days // 2
            )
            
            first_half = frappe.db.sql("""
                SELECT AVG(cnt) as avg_attendance
                FROM (
                    SELECT service_date, COUNT(*) as cnt
                    FROM `tabChurch Attendance`
                    WHERE docstatus = 1
                        AND service_type = %s
                        AND service_date BETWEEN %s AND %s
                        AND present = 1
                    GROUP BY service_date
                ) t
            """, (row["service_type"], filters.get("from_date"), mid_date))[0][0] or 0
            
            second_half = frappe.db.sql("""
                SELECT AVG(cnt) as avg_attendance
                FROM (
                    SELECT service_date, COUNT(*) as cnt
                    FROM `tabChurch Attendance`
                    WHERE docstatus = 1
                        AND service_type = %s
                        AND service_date BETWEEN %s AND %s
                        AND present = 1
                    GROUP BY service_date
                ) t
            """, (row["service_type"], add_days(mid_date, 1), filters.get("to_date")))[0][0] or 0
            
            if first_half > 0 and second_half > 0:
                if second_half > first_half * 1.1:
                    row["trend_direction"] = "↑ Rising"
                elif second_half < first_half * 0.9:
                    row["trend_direction"] = "↓ Declining"
                else:
                    row["trend_direction"] = "→ Stable"
            
            # Member retention (members who attend regularly)
            regular_members = frappe.db.sql("""
                SELECT COUNT(DISTINCT member_id)
                FROM `tabChurch Attendance`
                WHERE docstatus = 1
                    AND service_type = %s
                    AND service_date BETWEEN %s AND %s
                    AND present = 1
                GROUP BY member_id
                HAVING COUNT(DISTINCT service_date) >= 2
            """, (row["service_type"], filters.get("from_date"), filters.get("to_date")))
            
            total_members = frappe.db.sql("""
                SELECT COUNT(DISTINCT member_id)
                FROM `tabChurch Attendance`
                WHERE docstatus = 1
                    AND service_type = %s
                    AND service_date BETWEEN %s AND %s
                    AND present = 1
            """, (row["service_type"], filters.get("from_date"), filters.get("to_date")))[0][0] or 0
            
            if total_members > 0:
                row["member_retention"] = round((regular_members[0][0] / total_members) * 100, 1)
    
    return data


def get_leader_dashboard_data(filters):
    """Get leadership dashboard with follow-up metrics."""
    conditions = ["ca.docstatus = 1"]
    params = {}
    
    if filters.get("from_date"):
        conditions.append("ca.service_date >= %(from_date)s")
        params["from_date"] = filters.get("from_date")
    
    if filters.get("to_date"):
        conditions.append("ca.service_date <= %(to_date)s")
        params["to_date"] = filters.get("to_date")
    
    if filters.get("branch"):
        if isinstance(filters.get("branch"), list):
            conditions.append("ca.branch IN %(branch)s")
            params["branch"] = tuple(filters.get("branch"))
        else:
            conditions.append("ca.branch = %(branch)s")
            params["branch"] = filters.get("branch")
    
    # Get all branches and their leaders
    branches = frappe.db.sql("""
        SELECT DISTINCT branch 
        FROM `tabMember` 
        WHERE branch IS NOT NULL AND branch != ''
        ORDER BY branch
    """, as_dict=True)
    
    result = []
    
    for branch_row in branches:
        branch = branch_row["branch"]
        
        # Find branch leader(s)
        leaders = frappe.db.sql("""
            SELECT full_name, email
            FROM `tabMember`
            WHERE branch = %s
                AND member_status = 'Active'
                AND (is_a_pastor = 1 OR is_hod = 1 OR is_cancellor = 1)
            LIMIT 1
        """, branch)
        
        leader_name = leaders[0][0] if leaders else "No Leader Assigned"
        
        # Get member counts
        member_counts = frappe.db.sql("""
            SELECT 
                COUNT(*) as total_members,
                SUM(CASE WHEN member_status = 'Active' THEN 1 ELSE 0 END) as active_members,
                SUM(CASE WHEN member_status != 'Active' THEN 1 ELSE 0 END) as inactive_members
            FROM `tabMember`
            WHERE branch = %s
        """, branch, as_dict=True)
        
        member_count = member_counts[0] if member_counts else {"total_members": 0, "active_members": 0, "inactive_members": 0}
        
        # Get attendance rate for period
        attendance_rate_data = frappe.db.sql("""
            SELECT 
                COUNT(DISTINCT ca.member_id) as attended_members,
                COUNT(DISTINCT ca.service_date) as service_days
            FROM `tabChurch Attendance` ca
            WHERE ca.branch = %s
                AND ca.docstatus = 1
                AND ca.present = 1
                AND ca.service_date BETWEEN %s AND %s
        """, (branch, params.get("from_date"), params.get("to_date")), as_dict=True)
        
        attended_members = attendance_rate_data[0]["attended_members"] if attendance_rate_data else 0
        service_days = attendance_rate_data[0]["service_days"] if attendance_rate_data else 0
        
        attendance_rate = 0
        if member_count["active_members"] > 0 and service_days > 0:
            attendance_rate = round((attended_members / member_count["active_members"]) * 100, 1)
        
        # Get members who missed services
        two_weeks_ago = add_days(getdate(params.get("to_date")), -14)
        four_weeks_ago = add_days(getdate(params.get("to_date")), -28)
        
        missed_2_weeks = frappe.db.sql("""
            SELECT COUNT(DISTINCT m.name)
            FROM `tabMember` m
            WHERE m.branch = %s
                AND m.member_status = 'Active'
                AND NOT EXISTS (
                    SELECT 1 FROM `tabChurch Attendance` ca
                    WHERE ca.member_id = m.name
                        AND ca.docstatus = 1
                        AND ca.present = 1
                        AND ca.service_date >= %s
                )
        """, (branch, two_weeks_ago))[0][0] or 0
        
        missed_4_weeks = frappe.db.sql("""
            SELECT COUNT(DISTINCT m.name)
            FROM `tabMember` m
            WHERE m.branch = %s
                AND m.member_status = 'Active'
                AND NOT EXISTS (
                    SELECT 1 FROM `tabChurch Attendance` ca
                    WHERE ca.member_id = m.name
                        AND ca.docstatus = 1
                        AND ca.present = 1
                        AND ca.service_date >= %s
                )
        """, (branch, four_weeks_ago))[0][0] or 0
        
        # Get open ToDos for branch members
        open_todos = frappe.db.sql("""
            SELECT COUNT(*)
            FROM `tabToDo`
            WHERE status = 'Open'
                AND (
                    description LIKE %s
                    OR description LIKE %s
                    OR allocated_to IN (
                        SELECT name FROM `tabMember` WHERE branch = %s
                    )
                )
        """, (f"%{branch}%", f"%Branch: {branch}%", branch))[0][0] or 0
        
        # Get new members in period
        new_members = frappe.db.sql("""
            SELECT COUNT(*)
            FROM `tabMember`
            WHERE branch = %s
                AND creation >= %s
                AND creation <= %s
        """, (branch, params.get("from_date"), params.get("to_date")))[0][0] or 0
        
        result.append({
            "branch": branch,
            "leader_name": leader_name,
            "total_members": member_count["total_members"],
            "active_members": member_count["active_members"],
            "inactive_members": member_count["inactive_members"],
            "attendance_rate": attendance_rate,
            "missed_2_weeks": missed_2_weeks,
            "missed_4_weeks": missed_4_weeks,
            "need_followup": missed_2_weeks + missed_4_weeks,
            "followup_todos": open_todos,
            "new_members": new_members
        })
    
    return result


def get_chart_data(data, filters):
    """
    Generate chart data based on view type.
    Supports multiple chart types: Line, Bar, Pie, Heatmap.
    """
    if not data:
        return None
    
    view_type = filters.get("view_type")
    chart_type = filters.get("chart_type", "Bar")
    
    if view_type == "Summary":
        return get_summary_chart(data, filters)
    elif view_type == "Weekly":
        return get_weekly_chart(data, filters)
    elif view_type == "Monthly":
        return get_monthly_chart(data, filters)
    elif view_type == "Demographics":
        return get_demographics_chart(data, filters)
    elif view_type == "Service Type Analysis":
        return get_service_type_chart(data, filters)
    elif view_type == "Leader Dashboard":
        return get_leader_chart(data, filters)
    else:
        return get_detailed_chart(data, filters)


def get_summary_chart(data, filters):
    """Chart for summary view."""
    dates = [d["service_date"] for d in data[:30]]  # Limit to 30 days
    totals = [d["total_attendance"] for d in data[:30]]
    visitors = [d["visitor_count"] for d in data[:30]]
    
    chart = {
        "data": {
            "labels": [formatdate(d) for d in dates],
            "datasets": [
                {
                    "name": "Total Attendance",
                    "values": totals
                },
                {
                    "name": "Visitors",
                    "values": visitors
                }
            ]
        },
        "type": filters.get("chart_type", "Bar"),
        "colors": ["#1a3f90", "#2563eb"],
        "fieldtype": "Int"
    }
    
    return chart


def get_weekly_chart(data, filters):
    """Chart for weekly view."""
    labels = [f"Week {d['week_number']} ({formatdate(d['week_start'])})" for d in data[:12]]
    attendance = [d["total_attendance"] for d in data[:12]]
    unique = [d["unique_members"] for d in data[:12]]
    
    chart = {
        "data": {
            "labels": labels,
            "datasets": [
                {
                    "name": "Total Attendance",
                    "values": attendance
                },
                {
                    "name": "Unique Members",
                    "values": unique
                }
            ]
        },
        "type": filters.get("chart_type", "Line"),
        "colors": ["#1a3f90", "#10b981"],
        "fieldtype": "Int"
    }
    
    return chart


def get_monthly_chart(data, filters):
    """Chart for monthly view."""
    labels = [f"{d['month']} {d['year']}" for d in data[:12]]
    totals = [d["total_attendance"] for d in data[:12]]
    avg = [d["avg_attendance"] for d in data[:12]]
    
    chart = {
        "data": {
            "labels": labels,
            "datasets": [
                {
                    "name": "Total Attendance",
                    "values": totals
                },
                {
                    "name": "Average Attendance",
                    "values": avg
                }
            ]
        },
        "type": filters.get("chart_type", "Bar"),
        "colors": ["#1a3f90", "#f59e0b"],
        "fieldtype": "Int"
    }
    
    return chart


def get_demographics_chart(data, filters):
    """Pie chart for demographics."""
    groups = [d["demographic_group"] for d in data]
    attendees = [d["attended_count"] for d in data]
    
    chart = {
        "data": {
            "labels": groups,
            "datasets": [
                {
                    "name": "Attendance by Group",
                    "values": attendees
                }
            ]
        },
        "type": "Pie",
        "colors": ["#1a3f90", "#2563eb", "#3b82f6", "#60a5fa", "#93c5fd"],
        "fieldtype": "Int"
    }
    
    return chart


def get_service_type_chart(data, filters):
    """Chart for service type analysis."""
    types = [d["service_type"] for d in data]
    attendance = [d["total_attendance"] for d in data]
    avg = [d["avg_attendance"] for d in data]
    
    chart = {
        "data": {
            "labels": types,
            "datasets": [
                {
                    "name": "Total Attendance",
                    "values": attendance
                },
                {
                    "name": "Average",
                    "values": avg
                }
            ]
        },
        "type": filters.get("chart_type", "Bar"),
        "colors": ["#1a3f90", "#10b981"],
        "fieldtype": "Int"
    }
    
    return chart


def get_leader_chart(data, filters):
    """Chart for leader dashboard."""
    branches = [d["branch"] for d in data[:10]]
    attendance_rates = [d["attendance_rate"] for d in data[:10]]
    followup = [d["need_followup"] for d in data[:10]]
    
    chart = {
        "data": {
            "labels": branches,
            "datasets": [
                {
                    "name": "Attendance Rate %",
                    "values": attendance_rates
                },
                {
                    "name": "Needs Follow-up",
                    "values": followup
                }
            ]
        },
        "type": "Bar",
        "colors": ["#1a3f90", "#ef4444"],
        "fieldtype": "Float"
    }
    
    return chart


def get_detailed_chart(data, filters):
    """Chart for detailed view."""
    # Group by date
    date_groups = {}
    for row in data[:500]:  # Limit for performance
        date = row["service_date"]
        if date not in date_groups:
            date_groups[date] = 0
        if row.get("present"):
            date_groups[date] += 1
    
    sorted_dates = sorted(date_groups.keys())
    labels = [formatdate(d) for d in sorted_dates[-30:]]  # Last 30 days
    values = [date_groups[d] for d in sorted_dates[-30:]]
    
    chart = {
        "data": {
            "labels": labels,
            "datasets": [
                {
                    "name": "Daily Attendance",
                    "values": values
                }
            ]
        },
        "type": filters.get("chart_type", "Line"),
        "colors": ["#1a3f90"],
        "fieldtype": "Int"
    }
    
    return chart


def get_report_summary(data, filters):
    """
    Generate summary statistics for the report header.
    """
    if not data:
        return []
    
    view_type = filters.get("view_type")
    
    if view_type == "Detailed":
        total_present = sum(1 for d in data if d.get("present"))
        total_visitors = sum(1 for d in data if d.get("is_visitor"))
        unique_members = len(set(d.get("member_id") for d in data if d.get("member_id")))
        
        return [
            {
                "value": total_present,
                "label": _("Total Present"),
                "datatype": "Int",
                "color": "blue"
            },
            {
                "value": unique_members,
                "label": _("Unique Members"),
                "datatype": "Int",
                "color": "green"
            },
            {
                "value": total_visitors,
                "label": _("Visitors"),
                "datatype": "Int",
                "color": "orange"
            }
        ]
    
    elif view_type == "Summary":
        total_attendance = sum(d.get("total_attendance", 0) for d in data)
        total_visitors = sum(d.get("visitor_count", 0) for d in data)
        service_days = len(set(d.get("service_date") for d in data))
        
        return [
            {
                "value": total_attendance,
                "label": _("Total Attendance"),
                "datatype": "Int",
                "color": "blue"
            },
            {
                "value": service_days,
                "label": _("Service Days"),
                "datatype": "Int",
                "color": "green"
            },
            {
                "value": round(total_attendance / service_days, 1) if service_days else 0,
                "label": _("Avg Per Day"),
                "datatype": "Float",
                "color": "orange"
            },
            {
                "value": total_visitors,
                "label": _("Total Visitors"),
                "datatype": "Int",
                "color": "red"
            }
        ]
    
    elif view_type == "Weekly":
        total_attendance = sum(d.get("total_attendance", 0) for d in data)
        avg_attendance = round(total_attendance / len(data), 1) if data else 0
        
        return [
            {
                "value": len(data),
                "label": _("Weeks"),
                "datatype": "Int",
                "color": "blue"
            },
            {
                "value": total_attendance,
                "label": _("Total Attendance"),
                "datatype": "Int",
                "color": "green"
            },
            {
                "value": avg_attendance,
                "label": _("Weekly Average"),
                "datatype": "Float",
                "color": "orange"
            }
        ]
    
    elif view_type == "Leader Dashboard":
        total_active = sum(d.get("active_members", 0) for d in data)
        total_followup = sum(d.get("need_followup", 0) for d in data)
        avg_attendance = round(sum(d.get("attendance_rate", 0) for d in data) / len(data), 1) if data else 0
        
        return [
            {
                "value": total_active,
                "label": _("Total Active"),
                "datatype": "Int",
                "color": "blue"
            },
            {
                "value": f"{avg_attendance}%",
                "label": _("Avg Attendance"),
                "datatype": "Data",
                "color": "green"
            },
            {
                "value": total_followup,
                "label": _("Need Follow-up"),
                "datatype": "Int",
                "color": "red"
            }
        ]
    
    return []


@frappe.whitelist()
def get_filter_options():
    """
    Get filter options for dynamic filter UI.
    Returns distinct values for various filter fields.
    """
    options = {
        "branches": frappe.db.sql_list("SELECT DISTINCT branch FROM `tabChurch Attendance` WHERE branch IS NOT NULL AND branch != '' ORDER BY branch"),
        "service_types": frappe.db.sql_list("SELECT DISTINCT service_type FROM `tabChurch Attendance` WHERE service_type IS NOT NULL ORDER BY service_type"),
        "demographic_groups": frappe.db.sql_list("SELECT DISTINCT demographic_group FROM `tabMember` WHERE demographic_group IS NOT NULL AND demographic_group != '' ORDER BY demographic_group"),
        "sunday_school_classes": frappe.db.sql_list("SELECT DISTINCT sunday_school_class FROM `tabChurch Attendance` WHERE sunday_school_class IS NOT NULL AND sunday_school_class != '' ORDER BY sunday_school_class"),
        "checkin_methods": frappe.db.sql_list("SELECT DISTINCT checkin_method FROM `tabChurch Attendance` WHERE checkin_method IS NOT NULL AND checkin_method != '' ORDER BY checkin_method"),
        "visitor_sources": frappe.db.sql_list("SELECT DISTINCT visitor_source FROM `tabChurch Attendance` WHERE visitor_source IS NOT NULL AND visitor_source != '' ORDER BY visitor_source"),
    }
    
    return options


@frappe.whitelist()
def export_to_excel(filters):
    """
    Export report data to Excel.
    """
    if isinstance(filters, str):
        filters = json.loads(filters)
    
    data = get_data(filters)
    columns = get_columns(filters)
    
    # Create Excel file
    from frappe.utils.xlsxutils import make_xlsx
    
    # Prepare data for export
    excel_data = []
    
    # Add headers
    excel_data.append([col.get("label") for col in columns])
    
    # Add rows
    for row in data:
        excel_row = []
        for col in columns:
            fieldname = col.get("fieldname")
            value = row.get(fieldname, "")
            
            # Format based on fieldtype
            if col.get("fieldtype") == "Date" and value:
                value = formatdate(value)
            elif col.get("fieldtype") == "Check":
                value = "Yes" if value else "No"
            elif col.get("fieldtype") == "Percent":
                value = f"{value}%"
            
            excel_row.append(value)
        
        excel_data.append(excel_row)
    
    xlsx_file = make_xlsx(excel_data, "Attendance Report")
    
    frappe.response['filename'] = f"Attendance_Report_{now_datetime().strftime('%Y%m%d_%H%M%S')}.xlsx"
    frappe.response['filecontent'] = xlsx_file.getvalue()
    frappe.response['type'] = 'binary'