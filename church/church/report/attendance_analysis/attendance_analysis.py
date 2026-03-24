# Copyright (c) 2026, kunle and contributors
# For license information, please see license.txt

# -*- coding: utf-8 -*-
# Copyright (c) 2026, Church Management and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.utils import getdate, formatdate, format_date, format_datetime, now_datetime, flt
import json


def execute(filters=None):
    """
    Main execution function for Script Report
    Returns columns and data
    """
    if not filters:
        filters = {}
    
    # Validate required filters
    if not filters.get("attendance_sheet"):
        frappe.msgprint(_("Please select an Attendance Sheet"))
        return [], []
    
    # Get data
    columns = get_columns()
    data = get_data(filters)
    
    # Add charts
    chart = get_chart_data(filters)
    
    # Add summary
    report_summary = get_report_summary(filters)
    
    return columns, data, None, chart, report_summary


def get_columns():
    """Define report columns"""
    return [
        {
            "fieldname": "date",
            "label": _("Date"),
            "fieldtype": "Date",
            "width": 100
        },
        {
            "fieldname": "day",
            "label": _("Day"),
            "fieldtype": "Data",
            "width": 80
        },
        {
            "fieldname": "programme",
            "label": _("Programme"),
            "fieldtype": "Data",
            "width": 200
        },
        {
            "fieldname": "men",
            "label": _("Men"),
            "fieldtype": "Int",
            "width": 80
        },
        {
            "fieldname": "women",
            "label": _("Women"),
            "fieldtype": "Int",
            "width": 80
        },
        {
            "fieldname": "children",
            "label": _("Children"),
            "fieldtype": "Int",
            "width": 90
        },
        {
            "fieldname": "total",
            "label": _("Total"),
            "fieldtype": "Int",
            "width": 80
        },
        {
            "fieldname": "new_men",
            "label": _("New Men"),
            "fieldtype": "Int",
            "width": 90
        },
        {
            "fieldname": "new_women",
            "label": _("New Women"),
            "fieldtype": "Int",
            "width": 100
        },
        {
            "fieldname": "new_children",
            "label": _("New Children"),
            "fieldtype": "Int",
            "width": 110
        },
        {
            "fieldname": "visitors",
            "label": _("Visitors"),
            "fieldtype": "Int",
            "width": 90
        },
        {
            "fieldname": "visitor_percent",
            "label": _("Visitor %"),
            "fieldtype": "Percent",
            "width": 90
        }
    ]


def get_data(filters):
    """Get report data"""
    
    attendance_sheet = filters.get("attendance_sheet")
    
    # Get the attendance sheet document
    doc = frappe.get_doc("Attendance Sheet", attendance_sheet)
    
    data = []
    
    for row in doc.church_attendance_analysis:
        visitor_percent = calculate_percentage(row.new_total or 0, row.total or 0)
        
        data.append({
            "date": row.date,
            "day": row.day,
            "programme": row.programme,
            "men": row.men or 0,
            "women": row.women or 0,
            "children": row.children or 0,
            "total": row.total or 0,
            "new_men": row.new_men or 0,
            "new_women": row.new_women or 0,
            "new_children": row.new_children or 0,
            "visitors": row.new_total or 0,
            "visitor_percent": visitor_percent
        })
    
    return data


def get_chart_data(filters):
    """Generate chart data for visualization"""
    
    attendance_sheet = filters.get("attendance_sheet")
    doc = frappe.get_doc("Attendance Sheet", attendance_sheet)
    
    # Pie chart for attendance distribution
    chart = {
        "data": {
            "labels": ["Men", "Women", "Children"],
            "datasets": [
                {
                    "name": "Attendance Distribution",
                    "values": [
                        doc.total_men or 0,
                        doc.total_women or 0,
                        doc.total_children or 0
                    ]
                }
            ]
        },
        "type": "pie",
        "colors": ["#4facfe", "#fa709a", "#a8edea"]
    }
    
    return chart


def get_report_summary(filters):
    """Generate report summary cards"""
    
    attendance_sheet = filters.get("attendance_sheet")
    doc = frappe.get_doc("Attendance Sheet", attendance_sheet)
    
    total_attendance = doc.total_first or 0
    total_visitors = doc.total_second or 0
    
    summary = [
        {
            "value": total_attendance,
            "label": _("Total Attendance"),
            "datatype": "Int",
            "indicator": "blue"
        },
        {
            "value": doc.total_men or 0,
            "label": _("Men"),
            "datatype": "Int",
            "indicator": "green"
        },
        {
            "value": doc.total_women or 0,
            "label": _("Women"),
            "datatype": "Int",
            "indicator": "orange"
        },
        {
            "value": doc.total_children or 0,
            "label": _("Children"),
            "datatype": "Int",
            "indicator": "purple"
        },
        {
            "value": total_visitors,
            "label": _("Visitors"),
            "datatype": "Int",
            "indicator": "red"
        },
        {
            "value": calculate_percentage(total_visitors, total_attendance),
            "label": _("Visitor %"),
            "datatype": "Percent",
            "indicator": "yellow"
        }
    ]
    
    return summary


def calculate_percentage(value, total):
    """Calculate percentage"""
    if not total or total == 0:
        return 0
    return round((value / total) * 100, 1)


# =============================================================================
# CUSTOM EXPORT FUNCTIONS
# =============================================================================

@frappe.whitelist()
def export_to_beautiful_excel(attendance_sheet):
    """Export to beautifully formatted Excel"""
    from church.church.doctype.attendance_sheet.attendance_excel_export import export_attendance_to_excel
    
    result = export_attendance_to_excel(attendance_sheet)
    return result


@frappe.whitelist()
def generate_html_report(attendance_sheet):
    """Generate beautiful HTML report"""
    from church.church.doctype.attendance_sheet.attendance_report import preview_report
    
    html = preview_report(attendance_sheet)
    return html


@frappe.whitelist()
def email_report(attendance_sheet, recipients):
    """Email the report"""
    from church.church.doctype.attendance_sheet.attendance_report import email_report as send_email
    
    result = send_email(attendance_sheet, recipients)
    return result


@frappe.whitelist()
def get_attendance_sheet_list():
    """Get list of attendance sheets for filter"""
    
    sheets = frappe.get_all(
        "Attendance Sheet",
        fields=["name", "branch", "reporting_date"],
        order_by="reporting_date desc",
        limit=100
    )
    
    return [
        {
            "value": sheet.name,
            "label": f"{sheet.branch} - {format_date(sheet.reporting_date, 'dd MMM yyyy')}"
        }
        for sheet in sheets
    ]