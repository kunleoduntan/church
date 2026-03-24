# Copyright (c) 2026, kunle and contributors
# For license information, please see license.txt

# church/church/report/member_attendance_comparison/member_attendance_comparison.py
# Compares each member's attendance across two periods side by side

import frappe
from frappe import _
from frappe.utils import add_to_date, nowdate

def execute(filters=None):
    filters = filters or {}
    _set_default_periods(filters)
    columns = get_columns(filters)
    data    = get_data(filters)
    summary = get_summary(data, filters)
    chart   = get_chart(data)
    return columns, data, None, chart, summary

def _set_default_periods(filters):
    today = nowdate()
    if not filters.get("period1_from"):
        filters["period1_from"] = add_to_date(today, months=-2)
    if not filters.get("period1_to"):
        filters["period1_to"]   = add_to_date(today, months=-1)
    if not filters.get("period2_from"):
        filters["period2_from"] = add_to_date(today, months=-1)
    if not filters.get("period2_to"):
        filters["period2_to"]   = today

def get_columns(filters):
    p1 = f"{filters.get('period1_from')} → {filters.get('period1_to')}"
    p2 = f"{filters.get('period2_from')} → {filters.get('period2_to')}"
    return [
        {"fieldname": "member_id",   "label": _("Member ID"),       "fieldtype": "Link", "options": "Member", "width": 130},
        {"fieldname": "full_name",   "label": _("Full Name"),        "fieldtype": "Data", "width": 180},
        {"fieldname": "branch",      "label": _("Branch"),           "fieldtype": "Data", "width": 130},
        {"fieldname": "demographic_group","label": _("Group"),       "fieldtype": "Data", "width": 120},
        {"fieldname": "period1",     "label": _(f"Period 1 ({p1})"), "fieldtype": "Int",  "width": 160},
        {"fieldname": "period2",     "label": _(f"Period 2 ({p2})"), "fieldtype": "Int",  "width": 160},
        {"fieldname": "change",      "label": _("Change"),           "fieldtype": "Int",  "width": 80},
        {"fieldname": "change_pct",  "label": _("Change %"),         "fieldtype": "Percent","width": 100},
        {"fieldname": "trend",       "label": _("Trend"),            "fieldtype": "Data", "width": 80},
    ]

def get_data(filters):
    branch_cond = "AND m.branch = %(branch)s" if filters.get("branch") else ""
    group_cond  = "AND m.demographic_group = %(demographic_group)s" if filters.get("demographic_group") else ""

    members = frappe.db.sql(f"""
        SELECT m.name AS member_id, m.full_name, m.branch, m.demographic_group
        FROM `tabMember` m
        WHERE m.member_status = 'Active'
          {branch_cond}
          {group_cond}
        ORDER BY m.full_name
    """, filters, as_dict=True)

    member_ids = [m.member_id for m in members]
    if not member_ids:
        return []

    # Period 1 counts
    p1_rows = frappe.db.sql("""
        SELECT member_id, COUNT(name) AS cnt
        FROM `tabChurch Attendance`
        WHERE present = 1
          AND service_date BETWEEN %(period1_from)s AND %(period1_to)s
          AND member_id IN %(ids)s
        GROUP BY member_id
    """, {"period1_from": filters["period1_from"], "period1_to": filters["period1_to"],
          "ids": member_ids}, as_dict=True)

    # Period 2 counts
    p2_rows = frappe.db.sql("""
        SELECT member_id, COUNT(name) AS cnt
        FROM `tabChurch Attendance`
        WHERE present = 1
          AND service_date BETWEEN %(period2_from)s AND %(period2_to)s
          AND member_id IN %(ids)s
        GROUP BY member_id
    """, {"period2_from": filters["period2_from"], "period2_to": filters["period2_to"],
          "ids": member_ids}, as_dict=True)

    p1_map = {r.member_id: r.cnt for r in p1_rows}
    p2_map = {r.member_id: r.cnt for r in p2_rows}

    result = []
    for m in members:
        p1 = p1_map.get(m.member_id, 0)
        p2 = p2_map.get(m.member_id, 0)
        change = p2 - p1
        change_pct = round(change / p1 * 100, 1) if p1 else (100.0 if p2 else 0.0)
        trend = "⬆️ Up" if change > 0 else ("⬇️ Down" if change < 0 else "➡️ Same")

        # Apply filter
        min_att = int(filters.get("min_attendance", 0))
        if p1 < min_att and p2 < min_att:
            continue

        result.append({
            "member_id":        m.member_id,
            "full_name":        m.full_name,
            "branch":           m.branch,
            "demographic_group":m.demographic_group,
            "period1":          p1,
            "period2":          p2,
            "change":           change,
            "change_pct":       change_pct,
            "trend":            trend,
        })

    # Sort by change descending
    result.sort(key=lambda x: x["change"], reverse=True)
    return result

def get_summary(data, filters):
    improved  = sum(1 for d in data if d["change"] > 0)
    declined  = sum(1 for d in data if d["change"] < 0)
    same      = sum(1 for d in data if d["change"] == 0)
    zero_both = sum(1 for d in data if d["period1"] == 0 and d["period2"] == 0)
    return [
        {"value": len(data),  "label": _("Members Compared"),  "datatype": "Int", "indicator": "blue"},
        {"value": improved,   "label": _("Attendance Up"),     "datatype": "Int", "indicator": "green"},
        {"value": declined,   "label": _("Attendance Down"),   "datatype": "Int", "indicator": "red"},
        {"value": same,       "label": _("No Change"),         "datatype": "Int", "indicator": "grey"},
        {"value": zero_both,  "label": _("Zero in Both Periods"),"datatype": "Int","indicator": "orange"},
    ]

def get_chart(data):
    if not data:
        return {}
    # Top 10 most improved and most declined
    top10 = sorted(data, key=lambda x: x["change"], reverse=True)[:10]
    names   = [d["full_name"][:20] for d in top10]
    p1_vals = [d["period1"] for d in top10]
    p2_vals = [d["period2"] for d in top10]
    return {
        "data": {
            "labels": names,
            "datasets": [
                {"name": _("Period 1"), "values": p1_vals, "chartType": "bar"},
                {"name": _("Period 2"), "values": p2_vals, "chartType": "bar"},
            ]
        },
        "type": "bar",
        "title": _("Top 10 Attendance Change (Period 1 vs Period 2)"),
        "colors": ["#95a5a6","#2ecc71"],
        "axisOptions": {"xIsSeries": 1}
    }
