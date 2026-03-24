# Copyright (c) 2026, kunle and contributors
# For license information, please see license.txt

# church/church/report/service_attendance_summary/service_attendance_summary.py

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
        {"fieldname": "service_date",    "label": _("Date"),           "fieldtype": "Date", "width": 110},
        {"fieldname": "service_name",    "label": _("Service"),        "fieldtype": "Data", "width": 200},
        {"fieldname": "service_type",    "label": _("Type"),           "fieldtype": "Data", "width": 130},
        {"fieldname": "branch",          "label": _("Branch"),         "fieldtype": "Link", "options": "Branch", "width": 130},
        {"fieldname": "status",          "label": _("Status"),         "fieldtype": "Data", "width": 100},
        {"fieldname": "men_count",       "label": _("Men"),            "fieldtype": "Int",  "width": 70},
        {"fieldname": "women_count",     "label": _("Women"),          "fieldtype": "Int",  "width": 80},
        {"fieldname": "children_count",  "label": _("Children"),       "fieldtype": "Int",  "width": 90},
        {"fieldname": "total_attendance","label": _("Total"),          "fieldtype": "Int",  "width": 80},
        {"fieldname": "qr_checkins",     "label": _("QR Check-Ins"),   "fieldtype": "Int",  "width": 110},
        {"fieldname": "first_timers",    "label": _("First Timers"),   "fieldtype": "Int",  "width": 110},
        {"fieldname": "new_converts",    "label": _("New Converts"),   "fieldtype": "Int",  "width": 110},
        {"fieldname": "capacity",        "label": _("Capacity"),       "fieldtype": "Int",  "width": 90},
        {"fieldname": "capacity_pct",    "label": _("Capacity %"),     "fieldtype": "Percent","width": 100},
    ]

def get_data(filters):
    conds = ["1=1"]
    if filters.get("branch"):       conds.append("si.branch = %(branch)s")
    if filters.get("service_type"): conds.append("si.service_type = %(service_type)s")
    if filters.get("from_date"):    conds.append("si.service_date >= %(from_date)s")
    if filters.get("to_date"):      conds.append("si.service_date <= %(to_date)s")
    if filters.get("status"):       conds.append("si.status = %(status)s")

    rows = frappe.db.sql(f"""
        SELECT
            si.service_date,
            si.service_name,
            si.service_type,
            si.branch,
            si.status,
            COALESCE(si.men_count, 0)        AS men_count,
            COALESCE(si.women_count, 0)      AS women_count,
            COALESCE(si.children_count, 0)   AS children_count,
            COALESCE(si.total_attendance, 0) AS total_attendance,
            COALESCE(si.first_timers, 0)     AS first_timers,
            COALESCE(si.new_converts, 0)     AS new_converts,
            COALESCE(si.capacity, 0)         AS capacity,
            (SELECT COUNT(ca.name)
             FROM `tabChurch Attendance` ca
             WHERE ca.service_instance = si.name
               AND ca.present = 1
               AND ca.checkin_method LIKE 'QR%%')  AS qr_checkins
        FROM `tabService Instance` si
        WHERE {" AND ".join(conds)}
        ORDER BY si.service_date DESC, si.branch
    """, filters, as_dict=True)

    for r in rows:
        if r.capacity and r.total_attendance:
            r.capacity_pct = round(r.total_attendance / r.capacity * 100, 1)
        else:
            r.capacity_pct = 0
    return rows

def get_summary(data):
    total_services  = len(data)
    total_att       = sum(d.total_attendance for d in data)
    avg_att         = round(total_att / total_services, 0) if total_services else 0
    total_qr        = sum(d.qr_checkins or 0 for d in data)
    total_ft        = sum(d.first_timers or 0 for d in data)
    return [
        {"value": total_services, "label": _("Total Services"),    "datatype": "Int",   "indicator": "blue"},
        {"value": total_att,      "label": _("Total Attendance"),  "datatype": "Int",   "indicator": "green"},
        {"value": avg_att,        "label": _("Avg Attendance"),    "datatype": "Float", "indicator": "blue"},
        {"value": total_qr,       "label": _("QR Check-Ins"),      "datatype": "Int",   "indicator": "purple"},
        {"value": total_ft,       "label": _("First Timers"),      "datatype": "Int",   "indicator": "orange"},
    ]

def get_chart(data):
    if not data:
        return {}
    # Show last 12 services
    recent = sorted(data, key=lambda d: d.service_date)[-12:]
    labels = [f"{d.service_date} {d.branch or ''}" for d in recent]
    return {
        "data": {
            "labels": labels,
            "datasets": [
                {"name": _("Men"),      "values": [d.men_count     for d in recent], "chartType": "bar"},
                {"name": _("Women"),    "values": [d.women_count   for d in recent], "chartType": "bar"},
                {"name": _("Children"), "values": [d.children_count for d in recent],"chartType": "bar"},
            ]
        },
        "type": "bar",
        "title": _("Attendance Breakdown (Last 12 Services)"),
        "colors": ["#3498db","#e91e8c","#f39c12"],
        "barOptions": {"stacked": 1},
        "axisOptions": {"xIsSeries": 1}
    }
