# Copyright (c) 2026, kunle and contributors
# For license information, please see license.txt

# church/church/report/visitor_register/visitor_register.py

import frappe
from frappe import _

def execute(filters=None):
    filters = filters or {}
    columns = get_columns()
    data    = get_data(filters)
    summary = get_summary(data)
    chart   = get_chart(data)
    return columns, data, None, chart, summary

def get_columns():
    return [
        {"fieldname": "name",              "label": _("Visitor ID"),         "fieldtype": "Link", "options": "Visitor", "width": 130},
        {"fieldname": "full_name",         "label": _("Full Name"),           "fieldtype": "Data", "width": 170},
        {"fieldname": "gender",            "label": _("Gender"),              "fieldtype": "Data", "width": 80},
        {"fieldname": "mobile_phone",      "label": _("Mobile"),              "fieldtype": "Data", "width": 130},
        {"fieldname": "email",             "label": _("Email"),               "fieldtype": "Data", "width": 160},
        {"fieldname": "date_of_visit",     "label": _("Date of Visit"),       "fieldtype": "Date", "width": 110},
        {"fieldname": "branch",            "label": _("Branch"),              "fieldtype": "Data", "width": 120},
        {"fieldname": "visit_type",        "label": _("Visit Type"),          "fieldtype": "Data", "width": 140},
        {"fieldname": "how_did_you_hear",  "label": _("How Did You Hear"),    "fieldtype": "Data", "width": 160},
        {"fieldname": "conversion_status", "label": _("Conversion Status"),   "fieldtype": "Data", "width": 150},
        {"fieldname": "follow_up_count",   "label": _("Follow-Ups Done"),     "fieldtype": "Int",  "width": 120},
        {"fieldname": "last_follow_up_date","label": _("Last Follow-Up"),     "fieldtype": "Date", "width": 120},
        {"fieldname": "next_follow_up_date","label": _("Next Follow-Up"),     "fieldtype": "Date", "width": 120},
        {"fieldname": "follow_up_coordinator","label": _("Coordinator"),      "fieldtype": "Data", "width": 140},
        {"fieldname": "interested_in_membership","label": _("Wants Membership"),"fieldtype":"Check","width": 130},
        {"fieldname": "interested_in_baptism",  "label": _("Wants Baptism"),  "fieldtype": "Check","width": 120},
    ]

def get_data(filters):
    conds = ["1=1"]
    if filters.get("branch"):            conds.append("branch = %(branch)s")
    if filters.get("conversion_status"): conds.append("conversion_status = %(conversion_status)s")
    if filters.get("visit_type"):        conds.append("visit_type = %(visit_type)s")
    if filters.get("from_date"):         conds.append("date_of_visit >= %(from_date)s")
    if filters.get("to_date"):           conds.append("date_of_visit <= %(to_date)s")
    if filters.get("follow_up_coordinator"):
        conds.append("follow_up_coordinator = %(follow_up_coordinator)s")

    return frappe.db.sql(f"""
        SELECT
            v.name, v.full_name, v.gender, v.mobile_phone, v.email,
            v.date_of_visit, v.branch, v.visit_type, v.how_did_you_hear,
            v.conversion_status, v.follow_up_count, v.last_follow_up_date,
            v.next_follow_up_date, v.follow_up_coordinator,
            v.interested_in_membership, v.interested_in_baptism
        FROM `tabVisitor` v
        WHERE {" AND ".join(conds)}
        ORDER BY v.date_of_visit DESC
    """, filters, as_dict=True)

def get_summary(data):
    total      = len(data)
    converted  = sum(1 for d in data if d.conversion_status == "Converted to Member")
    pending    = sum(1 for d in data if d.conversion_status == "In Follow-up")
    new_vis    = sum(1 for d in data if d.conversion_status == "New Visitor")
    lost       = sum(1 for d in data if d.conversion_status == "Lost Contact")
    want_mem   = sum(1 for d in data if d.interested_in_membership)
    return [
        {"value": total,     "label": _("Total Visitors"),         "datatype": "Int", "indicator": "blue"},
        {"value": converted, "label": _("Converted to Member"),    "datatype": "Int", "indicator": "green"},
        {"value": pending,   "label": _("In Follow-up"),           "datatype": "Int", "indicator": "orange"},
        {"value": new_vis,   "label": _("New / Not Followed Up"),  "datatype": "Int", "indicator": "red"},
        {"value": lost,      "label": _("Lost Contact"),           "datatype": "Int", "indicator": "grey"},
        {"value": want_mem,  "label": _("Want Membership"),        "datatype": "Int", "indicator": "purple"},
    ]

def get_chart(data):
    status_counts = {}
    for d in data:
        s = d.conversion_status or "Unknown"
        status_counts[s] = status_counts.get(s, 0) + 1
    return {
        "data": {
            "labels":   list(status_counts.keys()),
            "datasets": [{"name": _("Visitors"), "values": list(status_counts.values())}]
        },
        "type": "donut",
        "title": _("Visitors by Conversion Status"),
        "colors": ["#27ae60","#f39c12","#3498db","#e74c3c","#95a5a6","#9b59b6"]
    }
