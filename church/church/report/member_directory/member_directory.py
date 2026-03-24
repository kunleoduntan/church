# Copyright (c) 2026, kunle and contributors
# For license information, please see license.txt

# church/church/report/member_directory/member_directory.py

import frappe
from frappe import _
from frappe.utils import formatdate

def execute(filters=None):
    filters = filters or {}
    columns = get_columns()
    data    = get_data(filters)
    summary = get_summary(data)
    chart   = get_chart(data)
    return columns, data, None, chart, summary

def get_columns():
    return [
        {"fieldname": "name",             "label": _("Member ID"),        "fieldtype": "Link",   "options": "Member", "width": 130},
        {"fieldname": "full_name",        "label": _("Full Name"),         "fieldtype": "Data",   "width": 180},
        {"fieldname": "gender",           "label": _("Gender"),            "fieldtype": "Data",   "width": 80},
        {"fieldname": "age",              "label": _("Age"),               "fieldtype": "Int",    "width": 60},
        {"fieldname": "category",         "label": _("Age Category"),      "fieldtype": "Data",   "width": 100},
        {"fieldname": "demographic_group","label": _("Demographic Group"), "fieldtype": "Data",   "width": 130},
        {"fieldname": "mobile_phone",     "label": _("Mobile"),            "fieldtype": "Data",   "width": 130},
        {"fieldname": "email",            "label": _("Email"),             "fieldtype": "Data",   "width": 180},
        {"fieldname": "branch",           "label": _("Branch"),            "fieldtype": "Link",   "options": "Branch", "width": 130},
        {"fieldname": "member_status",    "label": _("Status"),            "fieldtype": "Data",   "width": 90},
        {"fieldname": "date_of_joining",  "label": _("Date Joined"),       "fieldtype": "Date",   "width": 110},
        {"fieldname": "department_count", "label": _("Departments"),       "fieldtype": "Int",    "width": 100},
    ]

def get_data(filters):
    conditions = build_conditions(filters)
    return frappe.db.sql(f"""
        SELECT
            name, full_name, gender, age, category,
            demographic_group, mobile_phone, email,
            branch, member_status, date_of_joining, department_count
        FROM `tabMember`
        WHERE {conditions}
        ORDER BY full_name ASC
    """, filters, as_dict=True)

def build_conditions(filters):
    conds = ["1=1"]
    if filters.get("branch"):        conds.append("branch = %(branch)s")
    if filters.get("member_status"): conds.append("member_status = %(member_status)s")
    if filters.get("gender"):        conds.append("gender = %(gender)s")
    if filters.get("demographic_group"): conds.append("demographic_group = %(demographic_group)s")
    if filters.get("category"):      conds.append("category = %(category)s")
    if filters.get("from_date"):     conds.append("date_of_joining >= %(from_date)s")
    if filters.get("to_date"):       conds.append("date_of_joining <= %(to_date)s")
    return " AND ".join(conds)

def get_summary(data):
    total   = len(data)
    active  = sum(1 for d in data if d.member_status == "Active")
    male    = sum(1 for d in data if d.gender == "Male")
    female  = sum(1 for d in data if d.gender == "Female")
    no_contact = sum(1 for d in data if not d.mobile_phone and not d.email)
    return [
        {"value": total,      "label": _("Total Members"),      "datatype": "Int", "indicator": "blue"},
        {"value": active,     "label": _("Active"),             "datatype": "Int", "indicator": "green"},
        {"value": male,       "label": _("Male"),               "datatype": "Int", "indicator": "blue"},
        {"value": female,     "label": _("Female"),             "datatype": "Int", "indicator": "pink"},
        {"value": no_contact, "label": _("No Contact Info"),    "datatype": "Int", "indicator": "orange"},
    ]

def get_chart(data):
    status_counts = {}
    for d in data:
        status_counts[d.member_status or "Unknown"] = status_counts.get(d.member_status or "Unknown", 0) + 1
    return {
        "data": {
            "labels": list(status_counts.keys()),
            "datasets": [{"name": _("Members"), "values": list(status_counts.values())}]
        },
        "type": "donut",
        "title": _("Members by Status"),
        "colors": ["#2ecc71","#e67e22","#3498db","#e74c3c","#95a5a6"]
    }
