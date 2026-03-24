# Copyright (c) 2026, Your Organization
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.utils import flt, getdate, formatdate, cstr
from frappe.model.document import Document

def execute(filters=None):
    """
    Main function to execute the Member Tithe Record Report.
    Returns data formatted for both screen view and print format.
    """
    columns = get_columns()
    data = get_data(filters)
    
    # Add summary for each member
    if data:
        data = add_member_summary(data, filters)
    
    # Get member details for print header
    member_details = get_member_details(filters)
    
    # Prepare chart data for visual summary
    chart = get_chart_data(data, filters)
    
    return columns, data, None, chart, None, member_details

def get_columns():
    """
    Define columns with shortened names for better table fit.
    """
    return [
        {
            "fieldname": "date",
            "label": _("📅 Date"),
            "fieldtype": "Date",
            "width": 100,
            "align": "center"
        },
        {
            "fieldname": "receipt_no",
            "label": _("🧾 Receipt"),
            "fieldtype": "Link",
            "options": "Receipts",
            "width": 110,
            "align": "center"
        },
        {
            "fieldname": "currency",
            "label": _("💵 Curr"),
            "fieldtype": "Data",
            "width": 70,
            "align": "center"
        },
        {
            "fieldname": "exchange_rate",
            "label": _("🔄 Rate"),
            "fieldtype": "Float",
            "precision": 4,
            "width": 80,
            "align": "right"
        },
        {
            "fieldname": "amount_paid",
            "label": _("💰 Paid"),
            "fieldtype": "Currency",
            "width": 120,
            "align": "right"
        },
        {
            "fieldname": "amount_in_lc",
            "label": _("🏦 LCY"),
            "fieldtype": "Currency",
            "width": 120,
            "align": "right",
            "bold": 1
        },
        {
            "fieldname": "branch",
            "label": _("🏢 Branch"),
            "fieldtype": "Data",
            "width": 120,
            "align": "left"
        },
        {
            "fieldname": "other_details",
            "label": _("📝 Notes"),
            "fieldtype": "Small Text",
            "width": 200,
            "align": "left"
        }
    ]

def get_conditions(filters):
    """
    Build SQL WHERE conditions based on user filters.
    """
    conditions = ""
    
    if filters.get("member_id"):
        conditions += f" AND parent = '{filters.get('member_id')}'"
    
    if filters.get("from_date"):
        conditions += f" AND date >= '{filters.get('from_date')}'"
    
    if filters.get("to_date"):
        conditions += f" AND date <= '{filters.get('to_date')}'"
    
    if filters.get("branch"):
        conditions += f" AND branch = '{filters.get('branch')}'"
    
    if filters.get("currency"):
        conditions += f" AND currency = '{filters.get('currency')}'"
    
    return conditions

def get_data(filters):
    """
    Fetch tithe payment schedule data for the member.
    """
    conditions = get_conditions(filters)
    
    # Get the child table data
    query = f"""
        SELECT
            date,
            receipt_no,
            currency,
            exchange_rate,
            amount_paid,
            amount_in_lc,
            branch,
            other_details,
            full_name
        FROM
            `tabTithe Payment Schedule`
        WHERE
            1=1
            {conditions}
        ORDER BY
            date DESC
    """
    
    data = frappe.db.sql(query, as_dict=1)
    
    if not data:
        return []
    
    return data

def get_member_details(filters):
    """
    Get member details for print header and summary.
    """
    if not filters.get("member_id"):
        return {}
    
    member = frappe.get_doc("Member Tithe Record", filters.get("member_id"))
    
    # Get member info from Member doctype - only fields that exist
    member_info = {}
    if member.member_id:
        # Fetch only fields that exist in your Member doctype
        fields = ["full_name", "salutation"]
        # Only include fields that exist in the Member doctype
        member_data = frappe.db.get_value("Member", member.member_id, fields, as_dict=1)
        if member_data:
            member_info = member_data
    
    return {
        "member_id": member.member_id,
        "full_name": member.full_name,
        "salutation": member.salutation,
        "branch": member.branch,
        "currency": member.currency,
        "total_amount": member.amount_paid,
        "last_synced": member.last_synced,
        "description": member.description,
        "member_info": member_info
    }

def add_member_summary(data, filters):
    """
    Add summary statistics at the beginning of the data.
    """
    if not data:
        return data
    
    total_paid = sum(flt(d.get("amount_paid", 0)) for d in data)
    total_lcy = sum(flt(d.get("amount_in_lc", 0)) for d in data)
    transaction_count = len(data)
    unique_currencies = list(set(d.get("currency") for d in data if d.get("currency")))
    
    # Create summary row that will be displayed above the table
    summary_row = {
        "is_summary": 1,
        "date": "",
        "receipt_no": "",
        "currency": "",
        "exchange_rate": "",
        "amount_paid": total_paid,
        "amount_in_lc": total_lcy,
        "branch": "",
        "other_details": f"📊 {transaction_count} transactions | Currencies: {', '.join(unique_currencies)}"
    }
    
    # Insert summary at the beginning
    data.insert(0, summary_row)
    
    return data

def get_chart_data(data, filters):
    """
    Create chart data for visual representation of tithe history.
    """
    if not data:
        return None
    
    # Remove summary row if present
    chart_data = [d for d in data if not d.get("is_summary")]
    
    if not chart_data:
        return None
    
    # Group by month for trend
    monthly_data = {}
    for row in chart_data:
        if row.get("date"):
            month_key = getdate(row.get("date")).strftime("%b %Y")
            monthly_data[month_key] = monthly_data.get(month_key, 0) + flt(row.get("amount_in_lc", 0))
    
    # Prepare chart
    chart = {
        "data": {
            "labels": list(monthly_data.keys()),
            "datasets": [
                {
                    "name": _("Tithe Amount (LCY)"),
                    "values": list(monthly_data.values()),
                    "chartType": "bar",
                    "color": "#4F46E5"
                }
            ]
        },
        "type": "bar",
        "height": 300,
        "colors": ["#4F46E5", "#10B981"],
        "title": _("Monthly Tithe Contribution Trend")
    }
    
    return chart