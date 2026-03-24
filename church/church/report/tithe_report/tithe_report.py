# Copyright (c) 2026, Your Organization
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.utils import flt, getdate, formatdate

def execute(filters=None):
    """
    Main function to execute the Tithe Transaction Report.
    Queries through the parent doctype Tithe Batch Update.
    """
    # Define the columns for the report
    columns = get_columns()
    
    # Fetch data based on filters
    data = get_data(filters)
    
    # Add subtotals for each member and grand total
    data_with_totals = add_subtotals_and_grand_totals(data, filters)
    
    # Prepare summary statistics for the report footer
    summary = get_summary(data_with_totals, filters)
    
    # Add a cute, friendly message if no data found
    if not data:
        frappe.msgprint(_("🎉 Hooray! No tithe transactions found for the selected criteria. Keep shining! ✨"))
        return columns, [], None, None, summary
    
    return columns, data_with_totals, None, None, summary

def get_columns():
    """
    Define the columns for the report.
    """
    return [
        {
            "fieldname": "member_id",
            "label": _("👤 Member ID"),
            "fieldtype": "Link",
            "options": "Member",
            "width": 120
        },
        {
            "fieldname": "full_name",
            "label": _("✨ Full Name"),
            "fieldtype": "Data",
            "width": 200
        },
        {
            "fieldname": "member_status",
            "label": _("⭐ Status"),
            "fieldtype": "Data",
            "width": 100
        },
        {
            "fieldname": "batch_name",
            "label": _("📦 Batch"),
            "fieldtype": "Link",
            "options": "Tithe Batch Update",
            "width": 150
        },
        {
            "fieldname": "branch",
            "label": _("🏢 Branch"),
            "fieldtype": "Link",
            "options": "Branch",
            "width": 150
        },
        {
            "fieldname": "type",
            "label": _("🌟 Source"),
            "fieldtype": "Data",
            "width": 100
        },
        {
            "fieldname": "date",
            "label": _("📅 Date"),
            "fieldtype": "Date",
            "width": 120
        },
        {
            "fieldname": "currency",
            "label": _("💵 Currency"),
            "fieldtype": "Link",
            "options": "Currency",
            "width": 100
        },
        {
            "fieldname": "amount_paid",
            "label": _("💰 Amount Paid"),
            "fieldtype": "Currency",
            "options": "currency",
            "width": 130
        },
        {
            "fieldname": "exchange_rate",
            "label": _("🔄 Exchange Rate"),
            "fieldtype": "Float",
            "precision": 6,
            "width": 110
        },
        {
            "fieldname": "worker_tithe",
            "label": _("🙏 Worker Tithe"),
            "fieldtype": "Currency",
            "options": "currency",
            "width": 130
        },
        {
            "fieldname": "member_tithe",
            "label": _("🏡 Member Tithe"),
            "fieldtype": "Currency",
            "options": "currency",
            "width": 130
        },
        {
            "fieldname": "total_base_currency",
            "label": _("🏦 Total (Base)"),
            "fieldtype": "Currency",
            "width": 150
        },
        {
            "fieldname": "receipt_reference",
            "label": _("🧾 Receipt Ref"),
            "fieldtype": "Data",
            "width": 150
        },
        {
            "fieldname": "other_details",
            "label": _("📝 Details"),
            "fieldtype": "Small Text",
            "width": 250
        }
    ]

def get_conditions(filters):
    """
    Build SQL WHERE conditions based on user filters.
    """
    conditions = ""
    
    if filters.get("from_date"):
        conditions += f" AND tbu.reporting_date >= '{filters.get('from_date')}'"
    
    if filters.get("to_date"):
        conditions += f" AND tbu.reporting_date <= '{filters.get('to_date')}'"
    
    if filters.get("batch_id"):
        conditions += f" AND tbu.name = '{filters.get('batch_id')}'"
    
    if filters.get("member_id"):
        conditions += f" AND tte.member_id = '{filters.get('member_id')}'"
    
    if filters.get("type"):
        conditions += f" AND tte.type = '{filters.get('type')}'"
    
    if filters.get("branch"):
        conditions += f" AND tbu.branch = '{filters.get('branch')}'"
    
    if filters.get("currency"):
        conditions += f" AND tbu.currency = '{filters.get('currency')}'"
    
    if filters.get("member_status"):
        if filters.get("member_status") != "All":
            conditions += f" AND m.member_status = '{filters.get('member_status')}'"
    
    # Only get submitted documents
    conditions += " AND tbu.docstatus = 1"
    
    return conditions

def get_data(filters):
    """
    Fetch tithe transaction data from the parent doctype Tithe Batch Update.
    """
    conditions = get_conditions(filters)
    
    query = f"""
        SELECT
            tte.member_id,
            tte.full_name,
            m.member_status,
            tbu.branch,
            tbu.name as batch_name,
            tbu.reporting_date as date,
            tbu.currency,
            tte.type,
            tte.amount_paid,
            tte.exchange_rate,
            tte.worker_tithe,
            tte.member_tithe,
            tte.total_base_currency,
            tte.receipt_reference,
            tte.other_details
        FROM
            `tabTithe Batch Update` tbu
        INNER JOIN
            `tabTithe Transaction Entry` tte ON tte.parent = tbu.name
        LEFT JOIN
            `tabMember` m ON tte.member_id = m.name
        WHERE
            1=1
            {conditions}
        ORDER BY
            tte.member_id ASC,
            tbu.reporting_date DESC
    """
    
    data = frappe.db.sql(query, as_dict=1)
    
    if not data:
        return []
    
    return data

def add_subtotals_and_grand_totals(data, filters):
    """
    Add subtotal rows for each member and a grand total row at the end.
    """
    if not data:
        return []
    
    result = []
    current_member = None
    member_subtotal = {
        "total_base_currency": 0,
        "worker_tithe": 0,
        "member_tithe": 0,
        "amount_paid": 0,
        "transaction_count": 0
    }
    
    grand_total = {
        "total_base_currency": 0,
        "worker_tithe": 0,
        "member_tithe": 0,
        "amount_paid": 0,
        "transaction_count": 0,
        "member_count": 0
    }
    
    for row in data:
        if current_member != row.get("member_id"):
            if current_member is not None and member_subtotal["transaction_count"] > 0:
                result.append(get_subtotal_row(current_member, member_subtotal, data))
                grand_total["member_count"] += 1
            
            current_member = row.get("member_id")
            member_subtotal = {
                "total_base_currency": 0,
                "worker_tithe": 0,
                "member_tithe": 0,
                "amount_paid": 0,
                "transaction_count": 0
            }
        
        result.append(row)
        
        member_subtotal["total_base_currency"] += flt(row.get("total_base_currency", 0))
        member_subtotal["worker_tithe"] += flt(row.get("worker_tithe", 0))
        member_subtotal["member_tithe"] += flt(row.get("member_tithe", 0))
        member_subtotal["amount_paid"] += flt(row.get("amount_paid", 0))
        member_subtotal["transaction_count"] += 1
        
        grand_total["total_base_currency"] += flt(row.get("total_base_currency", 0))
        grand_total["worker_tithe"] += flt(row.get("worker_tithe", 0))
        grand_total["member_tithe"] += flt(row.get("member_tithe", 0))
        grand_total["amount_paid"] += flt(row.get("amount_paid", 0))
        grand_total["transaction_count"] += 1
    
    if current_member is not None and member_subtotal["transaction_count"] > 0:
        result.append(get_subtotal_row(current_member, member_subtotal, data))
        grand_total["member_count"] += 1
    
    if grand_total["transaction_count"] > 0:
        result.append(get_grand_total_row(grand_total))
    
    return result

def get_subtotal_row(member_id, subtotal, data):
    """
    Create a subtotal row for a member with styling indicators.
    """
    member_info = next((row for row in data if row.get("member_id") == member_id), {})
    
    return {
        "member_id": member_id,
        "full_name": member_info.get("full_name", ""),
        "member_status": member_info.get("member_status", ""),
        "batch_name": "",
        "branch": member_info.get("branch", ""),
        "type": "✨ SUBTOTAL ✨",
        "date": "",
        "currency": "",
        "amount_paid": subtotal["amount_paid"],
        "exchange_rate": "",
        "worker_tithe": subtotal["worker_tithe"],
        "member_tithe": subtotal["member_tithe"],
        "total_base_currency": subtotal["total_base_currency"],
        "receipt_reference": f"📊 {subtotal['transaction_count']} transactions",
        "other_details": "",
        "is_subtotal": 1,
        "indent": 1,
        "row_type": "subtotal"
    }

def get_grand_total_row(grand_total):
    """
    Create a grand total row with celebration styling.
    """
    return {
        "member_id": "🎯 GRAND TOTAL 🎯",
        "full_name": "",
        "member_status": "",
        "batch_name": "",
        "branch": "",
        "type": "🏆 GRAND TOTAL 🏆",
        "date": "",
        "currency": "",
        "amount_paid": grand_total["amount_paid"],
        "exchange_rate": "",
        "worker_tithe": grand_total["worker_tithe"],
        "member_tithe": grand_total["member_tithe"],
        "total_base_currency": grand_total["total_base_currency"],
        "receipt_reference": f"✨ {grand_total['member_count']} members • {grand_total['transaction_count']} transactions ✨",
        "other_details": "",
        "is_grand_total": 1,
        "indent": 0,
        "bold": 1,
        "row_type": "grand_total"
    }

def get_summary(data, filters):
    """
    Generate a cute summary for the report footer.
    """
    if not data:
        return []
    
    transaction_data = [row for row in data if not row.get("is_subtotal") and not row.get("is_grand_total")]
    
    if not transaction_data:
        return []
    
    total_base_currency = 0
    total_worker_tithe = 0
    total_member_tithe = 0
    total_amount_paid = 0
    unique_members = set()
    
    for row in transaction_data:
        total_base_currency += flt(row.get("total_base_currency", 0))
        total_worker_tithe += flt(row.get("worker_tithe", 0))
        total_member_tithe += flt(row.get("member_tithe", 0))
        total_amount_paid += flt(row.get("amount_paid", 0))
        unique_members.add(row.get("member_id"))
    
    summary = [
        {
            "value": len(unique_members),
            "label": _("👥 Members Contributed"),
            "datatype": "Int",
            "fieldname": "member_count",
            "currency": None
        },
        {
            "value": len(transaction_data),
            "label": _("📋 Total Transactions"),
            "datatype": "Int",
            "fieldname": "transaction_count",
            "currency": None
        },
        {
            "value": total_amount_paid,
            "label": _("💰 Total Amount Paid"),
            "datatype": "Currency",
            "fieldname": "total_amount_paid",
            "currency": filters.get("base_currency", "USD")
        },
        {
            "value": total_base_currency,
            "label": _("🏦 Total Tithe (Base)"),
            "datatype": "Currency",
            "fieldname": "total_base_currency",
            "currency": filters.get("base_currency", "USD")
        },
        {
            "value": total_worker_tithe,
            "label": _("🙏 Worker Tithe"),
            "datatype": "Currency",
            "fieldname": "total_worker_tithe",
            "currency": filters.get("base_currency", "USD")
        },
        {
            "value": total_member_tithe,
            "label": _("🏡 Member Tithe"),
            "datatype": "Currency",
            "fieldname": "total_member_tithe",
            "currency": filters.get("base_currency", "USD")
        }
    ]
    
    return summary