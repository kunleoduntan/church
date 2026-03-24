# Copyright (c) 2026, kunle and contributors
# For license information, please see license.txt

# church/church/report/visitor_conversion/visitor_conversion.py

import frappe
from frappe import _
from frappe.utils import nowdate, add_to_date

def execute(filters=None):
    filters = filters or {}
    columns = get_columns()
    data    = get_data(filters)
    summary = get_summary(data)
    chart   = get_chart(data)
    return columns, data, None, chart, summary

def get_columns():
    return [
        {"fieldname": "period",           "label": _("Period"),             "fieldtype": "Data", "width": 120},
        {"fieldname": "total_visitors",   "label": _("Total Visitors"),     "fieldtype": "Int",  "width": 120},
        {"fieldname": "first_timers",     "label": _("First Timers"),       "fieldtype": "Int",  "width": 110},
        {"fieldname": "return_visitors",  "label": _("Return Visitors"),    "fieldtype": "Int",  "width": 120},
        {"fieldname": "in_followup",      "label": _("In Follow-Up"),       "fieldtype": "Int",  "width": 110},
        {"fieldname": "converted",        "label": _("Converted"),          "fieldtype": "Int",  "width": 100},
        {"fieldname": "lost_contact",     "label": _("Lost Contact"),       "fieldtype": "Int",  "width": 110},
        {"fieldname": "conversion_rate",  "label": _("Conversion Rate %"),  "fieldtype": "Percent","width": 130},
        {"fieldname": "branch",           "label": _("Branch"),             "fieldtype": "Data", "width": 130},
    ]

def get_data(filters):
    branch_cond = "AND branch = %(branch)s" if filters.get("branch") else ""
    from_date   = filters.get("from_date", add_to_date(nowdate(), months=-12))
    to_date     = filters.get("to_date", nowdate())
    period      = filters.get("period", "Monthly")

    if period == "Monthly":
        group_expr = "DATE_FORMAT(date_of_visit, '%%Y-%%m')"
    elif period == "Quarterly":
        group_expr = "CONCAT(YEAR(date_of_visit), '-Q', QUARTER(date_of_visit))"
    else:
        group_expr = "YEAR(date_of_visit)"

    rows = frappe.db.sql(f"""
        SELECT
            {group_expr} AS period,
            COUNT(name)  AS total_visitors,
            SUM(CASE WHEN visit_type = 'First Time Visitor' THEN 1 ELSE 0 END)  AS first_timers,
            SUM(CASE WHEN visit_type = 'Return Visitor'     THEN 1 ELSE 0 END)  AS return_visitors,
            SUM(CASE WHEN conversion_status = 'In Follow-up' THEN 1 ELSE 0 END) AS in_followup,
            SUM(CASE WHEN conversion_status = 'Converted to Member' THEN 1 ELSE 0 END) AS converted,
            SUM(CASE WHEN conversion_status = 'Lost Contact' THEN 1 ELSE 0 END) AS lost_contact,
            branch
        FROM `tabVisitor`
        WHERE date_of_visit BETWEEN %(from_date)s AND %(to_date)s
          {branch_cond}
        GROUP BY {group_expr}, branch
        ORDER BY period
    """, {"from_date": from_date, "to_date": to_date,
          "branch": filters.get("branch","")}, as_dict=True)

    for r in rows:
        r.conversion_rate = round(r.converted / r.total_visitors * 100, 1) if r.total_visitors else 0
    return rows

def get_summary(data):
    total     = sum(d.total_visitors for d in data)
    converted = sum(d.converted for d in data)
    rate      = round(converted / total * 100, 1) if total else 0
    lost      = sum(d.lost_contact for d in data)
    return [
        {"value": total,     "label": _("Total Visitors"),      "datatype": "Int",   "indicator": "blue"},
        {"value": converted, "label": _("Converted to Member"), "datatype": "Int",   "indicator": "green"},
        {"value": rate,      "label": _("Overall Conversion %"),"datatype": "Float", "indicator": "green"},
        {"value": lost,      "label": _("Lost Contact"),        "datatype": "Int",   "indicator": "red"},
    ]

def get_chart(data):
    if not data:
        return {}
    labels    = [d.period for d in data]
    visitors  = [d.total_visitors for d in data]
    converted = [d.converted for d in data]
    return {
        "data": {
            "labels": labels,
            "datasets": [
                {"name": _("Visitors"),  "values": visitors,  "chartType": "bar"},
                {"name": _("Converted"), "values": converted, "chartType": "line"},
            ]
        },
        "type": "axis-mixed",
        "title": _("Visitor Conversion Trend"),
        "colors": ["#3498db","#27ae60"],
        "axisOptions": {"xIsSeries": 1}
    }
