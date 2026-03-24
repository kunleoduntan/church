# Copyright (c) 2026, kunle and contributors
# For license information, please see license.txt

# church/church/report/member_growth/member_growth.py

import frappe
from frappe import _
from frappe.utils import getdate, add_to_date, nowdate

def execute(filters=None):
    filters = filters or {}
    columns = get_columns(filters)
    data    = get_data(filters)
    summary = get_summary(data)
    chart   = get_chart(data, filters)
    return columns, data, None, chart, summary

def get_columns(filters):
    period = filters.get("period", "Monthly")
    return [
        {"fieldname": "period",      "label": _(period + " Period"), "fieldtype": "Data", "width": 130},
        {"fieldname": "new_members", "label": _("New Members"),      "fieldtype": "Int",  "width": 120},
        {"fieldname": "cumulative",  "label": _("Cumulative Total"),  "fieldtype": "Int",  "width": 140},
        {"fieldname": "male",        "label": _("Male"),              "fieldtype": "Int",  "width": 80},
        {"fieldname": "female",      "label": _("Female"),            "fieldtype": "Int",  "width": 80},
        {"fieldname": "active",      "label": _("Active"),            "fieldtype": "Int",  "width": 80},
        {"fieldname": "branch",      "label": _("Branch"),            "fieldtype": "Data", "width": 130},
    ]

def get_data(filters):
    period    = filters.get("period", "Monthly")
    from_date = filters.get("from_date", add_to_date(nowdate(), years=-1))
    to_date   = filters.get("to_date",   nowdate())
    branch    = filters.get("branch", "")

    if period == "Monthly":
        date_format = "%Y-%m"
        group_expr  = "DATE_FORMAT(date_of_joining, '%%Y-%%m')"
    elif period == "Quarterly":
        date_format = "%Y-Q"
        group_expr  = "CONCAT(YEAR(date_of_joining), '-Q', QUARTER(date_of_joining))"
    else:  # Yearly
        group_expr  = "YEAR(date_of_joining)"

    branch_cond = "AND branch = %(branch)s" if branch else ""

    rows = frappe.db.sql(f"""
        SELECT
            {group_expr}                                      AS period,
            COUNT(name)                                       AS new_members,
            SUM(CASE WHEN gender='Male'   THEN 1 ELSE 0 END) AS male,
            SUM(CASE WHEN gender='Female' THEN 1 ELSE 0 END) AS female,
            SUM(CASE WHEN member_status='Active' THEN 1 ELSE 0 END) AS active,
            branch
        FROM `tabMember`
        WHERE date_of_joining BETWEEN %(from_date)s AND %(to_date)s
          {branch_cond}
        GROUP BY {group_expr}, branch
        ORDER BY period ASC
    """, {"from_date": from_date, "to_date": to_date, "branch": branch}, as_dict=True)

    # Add cumulative column
    cumulative = 0
    for row in rows:
        cumulative += row.new_members
        row.cumulative = cumulative
    return rows

def get_summary(data):
    total_new  = sum(d.new_members for d in data)
    peak_row   = max(data, key=lambda d: d.new_members) if data else None
    avg        = round(total_new / len(data), 1) if data else 0
    return [
        {"value": total_new,              "label": _("Total New Members"),   "datatype": "Int",   "indicator": "blue"},
        {"value": avg,                    "label": _("Avg per Period"),       "datatype": "Float", "indicator": "green"},
        {"value": peak_row.new_members if peak_row else 0,
                                          "label": _("Peak Period Count"),    "datatype": "Int",   "indicator": "orange"},
        {"value": peak_row.period if peak_row else "—",
                                          "label": _("Peak Period"),          "datatype": "Data",  "indicator": "orange"},
    ]

def get_chart(data, filters):
    if not data:
        return {}
    labels   = [d.period for d in data]
    new_vals = [d.new_members for d in data]
    cum_vals = [d.cumulative  for d in data]
    return {
        "data": {
            "labels": labels,
            "datasets": [
                {"name": _("New Members"),      "values": new_vals, "chartType": "bar"},
                {"name": _("Cumulative Total"), "values": cum_vals, "chartType": "line"},
            ]
        },
        "type": "axis-mixed",
        "title": _("Member Growth Trend"),
        "colors": ["#3498db","#2ecc71"],
        "axisOptions": {"xIsSeries": 1}
    }
