# Copyright (c) 2026, kunle and contributors
# For license information, please see license.txt

# church/church/report/branch_attendance_comparison/branch_attendance_comparison.py

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
        {"fieldname": "period",         "label": _("Period"),           "fieldtype": "Data",    "width": 120},
        {"fieldname": "branch",         "label": _("Branch"),           "fieldtype": "Data",    "width": 160},
        {"fieldname": "services_held",  "label": _("Services Held"),    "fieldtype": "Int",     "width": 120},
        {"fieldname": "total_att",      "label": _("Total Attendance"), "fieldtype": "Int",     "width": 130},
        {"fieldname": "avg_att",        "label": _("Avg per Service"),  "fieldtype": "Float",   "width": 130},
        {"fieldname": "qr_checkins",    "label": _("QR Check-Ins"),     "fieldtype": "Int",     "width": 120},
        {"fieldname": "qr_pct",         "label": _("QR %"),             "fieldtype": "Percent", "width": 90},
        {"fieldname": "first_timers",   "label": _("First Timers"),     "fieldtype": "Int",     "width": 110},
        {"fieldname": "new_converts",   "label": _("New Converts"),     "fieldtype": "Int",     "width": 120},
        {"fieldname": "peak_service",   "label": _("Peak Service"),     "fieldtype": "Data",    "width": 150},
        {"fieldname": "peak_att",       "label": _("Peak Attendance"),  "fieldtype": "Int",     "width": 130},
    ]

def get_data(filters):
    from_date = filters.get("from_date", add_to_date(nowdate(), months=-3))
    to_date   = filters.get("to_date",   nowdate())
    period    = filters.get("period",    "Monthly")
    branch    = filters.get("branch",    "")

    if period == "Monthly":
        group_expr = "DATE_FORMAT(si.service_date, '%%Y-%%m')"
    elif period == "Quarterly":
        group_expr = "CONCAT(YEAR(si.service_date), '-Q', QUARTER(si.service_date))"
    else:
        group_expr = "YEAR(si.service_date)"

    branch_cond = "AND si.branch = %(branch)s" if branch else ""

    rows = frappe.db.sql(f"""
        SELECT
            {group_expr}                            AS period,
            si.branch,
            COUNT(si.name)                          AS services_held,
            SUM(COALESCE(si.total_attendance, 0))   AS total_att,
            ROUND(AVG(COALESCE(si.total_attendance,0)),1) AS avg_att,
            SUM(COALESCE(si.first_timers, 0))       AS first_timers,
            SUM(COALESCE(si.new_converts, 0))       AS new_converts
        FROM `tabService Instance` si
        WHERE si.service_date BETWEEN %(from_date)s AND %(to_date)s
          AND si.status = 'Completed'
          {branch_cond}
        GROUP BY {group_expr}, si.branch
        ORDER BY period, si.branch
    """, {"from_date": from_date, "to_date": to_date, "branch": branch}, as_dict=True)

    # QR checkins per branch per period
    qr_rows = frappe.db.sql(f"""
        SELECT
            {group_expr.replace('si.', 'si2.')} AS period,
            si2.branch,
            COUNT(ca.name) AS qr_count
        FROM `tabChurch Attendance` ca
        JOIN `tabService Instance` si2 ON si2.name = ca.service_instance
        WHERE si2.service_date BETWEEN %(from_date)s AND %(to_date)s
          AND ca.present = 1
          AND ca.checkin_method LIKE 'QR%%'
          {branch_cond.replace('si.', 'si2.')}
        GROUP BY {group_expr.replace('si.', 'si2.')}, si2.branch
    """, {"from_date": from_date, "to_date": to_date, "branch": branch}, as_dict=True)
    qr_map = {(r.period, r.branch): r.qr_count for r in qr_rows}

    # Peak service per branch per period
    peak_rows = frappe.db.sql(f"""
        SELECT branch, service_name, service_date, total_attendance
        FROM `tabService Instance`
        WHERE service_date BETWEEN %(from_date)s AND %(to_date)s
          AND status = 'Completed'
          {branch_cond}
        ORDER BY total_attendance DESC
    """, {"from_date": from_date, "to_date": to_date, "branch": branch}, as_dict=True)
    peak_map = {}
    for p in peak_rows:
        key = p.branch
        if key not in peak_map:
            peak_map[key] = p

    for r in rows:
        qr = qr_map.get((r.period, r.branch), 0)
        r.qr_checkins = qr
        r.qr_pct      = round(qr / r.total_att * 100, 1) if r.total_att else 0
        pk = peak_map.get(r.branch)
        r.peak_service = f"{pk.service_name} ({pk.service_date})" if pk else "—"
        r.peak_att     = pk.total_attendance if pk else 0
    return rows

def get_summary(data):
    branches     = list(set(d.branch for d in data))
    total_att    = sum(d.total_att for d in data)
    total_svc    = sum(d.services_held for d in data)
    best_branch  = max(data, key=lambda d: d.total_att) if data else None
    return [
        {"value": len(branches),  "label": _("Branches"),           "datatype": "Int",   "indicator": "blue"},
        {"value": total_svc,      "label": _("Total Services"),      "datatype": "Int",   "indicator": "green"},
        {"value": total_att,      "label": _("Total Attendance"),    "datatype": "Int",   "indicator": "blue"},
        {"value": best_branch.branch if best_branch else "—",
                                  "label": _("Top Branch (Period)"), "datatype": "Data",  "indicator": "green"},
    ]

def get_chart(data):
    if not data:
        return {}
    branches = list(set(d.branch for d in data))
    periods  = sorted(set(d.period for d in data))
    att_map  = {(d.period, d.branch): d.total_att for d in data}
    datasets = []
    colors   = ["#3498db","#2ecc71","#e74c3c","#f39c12","#9b59b6","#1abc9c"]
    for i, branch in enumerate(branches):
        datasets.append({
            "name":   branch,
            "values": [att_map.get((p, branch), 0) for p in periods],
            "chartType": "line"
        })
    return {
        "data": {"labels": periods, "datasets": datasets},
        "type": "line",
        "title": _("Branch Attendance Comparison Over Time"),
        "colors": colors[:len(branches)],
        "axisOptions": {"xIsSeries": 1}
    }
