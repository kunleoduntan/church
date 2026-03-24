# Copyright (c) 2026, kunle and contributors
# For license information, please see license.txt

# church/church/report/department_strength/department_strength.py

import frappe
from frappe import _

def execute(filters=None):
    filters = filters or {}
    columns = get_columns(filters)
    data    = get_data(filters)
    summary = get_summary(data)
    chart   = get_chart(data)
    return columns, data, None, chart, summary

def get_columns(filters):
    cols = [
        {"fieldname": "department",      "label": _("Department"),      "fieldtype": "Link", "options": "Church Department", "width": 180},
        {"fieldname": "total_members",   "label": _("Total Members"),   "fieldtype": "Int",  "width": 120},
        {"fieldname": "active_members",  "label": _("Active"),          "fieldtype": "Int",  "width": 90},
        {"fieldname": "inactive_members","label": _("Inactive"),        "fieldtype": "Int",  "width": 90},
        {"fieldname": "primary_count",   "label": _("Primary Dept of"), "fieldtype": "Int",  "width": 130},
        {"fieldname": "male_count",      "label": _("Male"),            "fieldtype": "Int",  "width": 70},
        {"fieldname": "female_count",    "label": _("Female"),          "fieldtype": "Int",  "width": 80},
        {"fieldname": "avg_age",         "label": _("Avg Age"),         "fieldtype": "Float","width": 90},
    ]
    if filters.get("show_members"):
        cols += [
            {"fieldname": "member_id",  "label": _("Member ID"),   "fieldtype": "Link", "options": "Member", "width": 130},
            {"fieldname": "full_name",  "label": _("Full Name"),   "fieldtype": "Data", "width": 180},
            {"fieldname": "role",       "label": _("Role"),        "fieldtype": "Data", "width": 140},
            {"fieldname": "is_primary", "label": _("Is Primary"),  "fieldtype": "Check","width": 100},
            {"fieldname": "from_date",  "label": _("Since"),       "fieldtype": "Date", "width": 100},
        ]
    return cols

def get_data(filters):
    dept_filter = "AND md.department = %(department)s" if filters.get("department") else ""

    # Department-level summary
    dept_rows = frappe.db.sql(f"""
        SELECT
            md.department,
            COUNT(md.name)                                        AS total_members,
            SUM(CASE WHEN md.is_active = 1 THEN 1 ELSE 0 END)    AS active_members,
            SUM(CASE WHEN md.is_active = 0 THEN 1 ELSE 0 END)    AS inactive_members,
            SUM(CASE WHEN md.is_primary = 1 THEN 1 ELSE 0 END)   AS primary_count,
            SUM(CASE WHEN m.gender = 'Male'   THEN 1 ELSE 0 END) AS male_count,
            SUM(CASE WHEN m.gender = 'Female' THEN 1 ELSE 0 END) AS female_count,
            ROUND(AVG(m.age), 1)                                  AS avg_age
        FROM `tabMember Department` md
        JOIN `tabMember` m ON m.name = md.parent
        WHERE m.member_status = 'Active'
          {dept_filter}
        GROUP BY md.department
        ORDER BY active_members DESC
    """, {"department": filters.get("department", "")}, as_dict=True)

    if not filters.get("show_members"):
        return dept_rows

    # Detailed member rows
    result = []
    for dept in dept_rows:
        result.append(dept)  # Department summary row
        members = frappe.db.sql("""
            SELECT
                md.parent    AS member_id,
                m.full_name,
                md.role,
                md.is_primary,
                md.from_date
            FROM `tabMember Department` md
            JOIN `tabMember` m ON m.name = md.parent
            WHERE md.department = %(dept)s
              AND m.member_status = 'Active'
              AND md.is_active = 1
            ORDER BY m.full_name
        """, {"dept": dept.department}, as_dict=True)
        for mem in members:
            result.append({
                "department": "",
                "member_id":  mem.member_id,
                "full_name":  mem.full_name,
                "role":       mem.role,
                "is_primary": mem.is_primary,
                "from_date":  mem.from_date,
            })
    return result

def get_summary(data):
    dept_rows  = [d for d in data if d.get("total_members")]
    total_dept = len(dept_rows)
    total_mem  = sum(d.active_members for d in dept_rows)
    largest    = max(dept_rows, key=lambda d: d.active_members) if dept_rows else None
    multi_dept = frappe.db.sql("""
        SELECT COUNT(DISTINCT parent) AS cnt
        FROM `tabMember Department`
        WHERE is_active = 1
        GROUP BY parent
        HAVING COUNT(name) > 1
    """, as_dict=True)
    multi_count = len(multi_dept)
    return [
        {"value": total_dept,  "label": _("Active Departments"),       "datatype": "Int",  "indicator": "blue"},
        {"value": total_mem,   "label": _("Total Dept Assignments"),   "datatype": "Int",  "indicator": "green"},
        {"value": multi_count, "label": _("Members in 2+ Depts"),      "datatype": "Int",  "indicator": "orange"},
        {"value": largest.department if largest else "—",
                               "label": _("Largest Department"),       "datatype": "Data", "indicator": "blue"},
    ]

def get_chart(data):
    dept_rows = [d for d in data if d.get("total_members")][:12]
    return {
        "data": {
            "labels": [d.department for d in dept_rows],
            "datasets": [
                {"name": _("Active"),   "values": [d.active_members   for d in dept_rows], "chartType": "bar"},
                {"name": _("Inactive"), "values": [d.inactive_members for d in dept_rows], "chartType": "bar"},
            ]
        },
        "type": "bar",
        "title": _("Department Strength"),
        "colors": ["#2ecc71","#e74c3c"],
        "barOptions": {"stacked": 1},
        "axisOptions": {"xIsSeries": 1}
    }
