# Copyright (c) 2026, kunle and contributors
# For license information, please see license.txt

# church/church/report/age_demographic_distribution/age_demographic_distribution.py

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
        {"fieldname": "demographic_group", "label": _("Demographic Group"), "fieldtype": "Data", "width": 160},
        {"fieldname": "category",          "label": _("Age Category"),      "fieldtype": "Data", "width": 120},
        {"fieldname": "gender",            "label": _("Gender"),            "fieldtype": "Data", "width": 80},
        {"fieldname": "count",             "label": _("Members"),           "fieldtype": "Int",  "width": 100},
        {"fieldname": "pct",               "label": _("% of Total"),        "fieldtype": "Percent","width": 100},
        {"fieldname": "avg_age",           "label": _("Avg Age"),           "fieldtype": "Float","width": 90},
        {"fieldname": "min_age",           "label": _("Youngest"),          "fieldtype": "Int",  "width": 90},
        {"fieldname": "max_age",           "label": _("Oldest"),            "fieldtype": "Int",  "width": 90},
        {"fieldname": "branch",            "label": _("Branch"),            "fieldtype": "Data", "width": 130},
    ]

def get_data(filters):
    branch_cond = "AND branch = %(branch)s" if filters.get("branch") else ""
    status_cond = "AND member_status = %(member_status)s" if filters.get("member_status") else ""

    rows = frappe.db.sql(f"""
        SELECT
            COALESCE(demographic_group, 'Unassigned') AS demographic_group,
            COALESCE(category, 'Unassigned')          AS category,
            COALESCE(gender, 'Unknown')               AS gender,
            COUNT(name)                               AS count,
            ROUND(AVG(age), 1)                        AS avg_age,
            MIN(age)                                  AS min_age,
            MAX(age)                                  AS max_age,
            branch
        FROM `tabMember`
        WHERE member_status = 'Active'
          {branch_cond}
          {status_cond}
        GROUP BY demographic_group, category, gender, branch
        ORDER BY demographic_group, category, gender
    """, filters, as_dict=True)

    total = sum(r.count for r in rows) or 1
    for r in rows:
        r.pct = round(r.count / total * 100, 1)
    return rows

def get_summary(data):
    total   = sum(d.count for d in data)
    groups  = len(set(d.demographic_group for d in data))
    largest = max(data, key=lambda d: d.count) if data else None
    return [
        {"value": total,  "label": _("Total Active Members"),    "datatype": "Int",  "indicator": "blue"},
        {"value": groups, "label": _("Demographic Groups"),      "datatype": "Int",  "indicator": "green"},
        {"value": largest.demographic_group if largest else "—",
                          "label": _("Largest Group"),           "datatype": "Data", "indicator": "orange"},
        {"value": largest.count if largest else 0,
                          "label": _("Largest Group Count"),     "datatype": "Int",  "indicator": "orange"},
    ]

def get_chart(data):
    group_totals = {}
    for d in data:
        group_totals[d.demographic_group] = group_totals.get(d.demographic_group, 0) + d.count
    sorted_groups = sorted(group_totals.items(), key=lambda x: x[1], reverse=True)
    return {
        "data": {
            "labels":   [g[0] for g in sorted_groups],
            "datasets": [{"name": _("Members"), "values": [g[1] for g in sorted_groups]}]
        },
        "type": "bar",
        "title": _("Members by Demographic Group"),
        "colors": ["#667eea"],
        "barOptions": {"stacked": 0}
    }
