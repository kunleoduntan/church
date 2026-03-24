# Copyright (c) 2026, kunle and contributors
# For license information, please see license.txt

# church/church/report/absenteeism_report/absenteeism_report.py
# Absenteeism with period comparison and full attendance history per member

import frappe
from frappe import _
from frappe.utils import nowdate, add_to_date, getdate, date_diff

def execute(filters=None):
    filters = filters or {}
    _set_defaults(filters)
    columns = get_columns(filters)
    data    = get_data(filters)
    summary = get_summary(data, filters)
    chart   = get_chart(data)
    return columns, data, None, chart, summary

def _set_defaults(filters):
    today = nowdate()
    if not filters.get("from_date"):
        filters["from_date"] = add_to_date(today, months=-3)
    if not filters.get("to_date"):
        filters["to_date"] = today
    if not filters.get("min_absent_services"):
        filters["min_absent_services"] = 2

def get_columns(filters):
    return [
        {"fieldname": "member_id",        "label": _("Member ID"),         "fieldtype": "Link", "options": "Member", "width": 130},
        {"fieldname": "full_name",        "label": _("Full Name"),          "fieldtype": "Data", "width": 180},
        {"fieldname": "branch",           "label": _("Branch"),             "fieldtype": "Data", "width": 120},
        {"fieldname": "demographic_group","label": _("Group"),              "fieldtype": "Data", "width": 120},
        {"fieldname": "mobile_phone",     "label": _("Mobile"),             "fieldtype": "Data", "width": 130},
        {"fieldname": "total_services",   "label": _("Services Held"),      "fieldtype": "Int",  "width": 110},
        {"fieldname": "attended",         "label": _("Attended"),           "fieldtype": "Int",  "width": 90},
        {"fieldname": "absent",           "label": _("Absent"),             "fieldtype": "Int",  "width": 80},
        {"fieldname": "attendance_pct",   "label": _("Attendance %"),       "fieldtype": "Percent","width": 110},
        {"fieldname": "last_seen",        "label": _("Last Seen"),          "fieldtype": "Date", "width": 110},
        {"fieldname": "days_absent",      "label": _("Days Since Last Seen"),"fieldtype": "Int", "width": 150},
        {"fieldname": "consecutive_absent","label": _("Consecutive Absent"),"fieldtype": "Int",  "width": 140},
        {"fieldname": "prev_period_pct",  "label": _("Prev Period %"),      "fieldtype": "Percent","width": 110},
        {"fieldname": "trend",            "label": _("Trend"),              "fieldtype": "Data", "width": 90},
        {"fieldname": "risk_level",       "label": _("Risk Level"),         "fieldtype": "Data", "width": 100},
    ]

def get_data(filters):
    branch_cond = "AND m.branch = %(branch)s" if filters.get("branch") else ""
    group_cond  = "AND m.demographic_group = %(demographic_group)s" if filters.get("demographic_group") else ""
    from_date   = filters["from_date"]
    to_date     = filters["to_date"]
    today       = getdate(nowdate())

    # Total services in the period (per branch)
    service_counts = frappe.db.sql("""
        SELECT branch, COUNT(name) AS total
        FROM `tabService Instance`
        WHERE service_date BETWEEN %(from_date)s AND %(to_date)s
          AND status IN ('Completed', 'Ongoing')
        GROUP BY branch
    """, {"from_date": from_date, "to_date": to_date}, as_dict=True)
    svc_map = {r.branch: r.total for r in service_counts}
    overall_total = max(svc_map.values()) if svc_map else 1

    # Previous period (same length, immediately before)
    period_days = date_diff(to_date, from_date)
    prev_from   = add_to_date(from_date, days=-period_days)
    prev_to     = add_to_date(from_date, days=-1)

    members = frappe.db.sql(f"""
        SELECT m.name AS member_id, m.full_name, m.branch,
               m.demographic_group, m.mobile_phone
        FROM `tabMember` m
        WHERE m.member_status = 'Active'
          {branch_cond}
          {group_cond}
        ORDER BY m.full_name
    """, filters, as_dict=True)

    if not members:
        return []

    member_ids = [m.member_id for m in members]

    # Current period attendance
    curr_att = frappe.db.sql("""
        SELECT member_id, COUNT(name) AS cnt, MAX(service_date) AS last_seen
        FROM `tabChurch Attendance`
        WHERE present = 1
          AND service_date BETWEEN %(from_date)s AND %(to_date)s
          AND member_id IN %(ids)s
        GROUP BY member_id
    """, {"from_date": from_date, "to_date": to_date, "ids": member_ids}, as_dict=True)
    curr_map = {r.member_id: r for r in curr_att}

    # Previous period attendance
    prev_att = frappe.db.sql("""
        SELECT member_id, COUNT(name) AS cnt
        FROM `tabChurch Attendance`
        WHERE present = 1
          AND service_date BETWEEN %(prev_from)s AND %(prev_to)s
          AND member_id IN %(ids)s
        GROUP BY member_id
    """, {"prev_from": prev_from, "prev_to": prev_to, "ids": member_ids}, as_dict=True)
    prev_map = {r.member_id: r.cnt for r in prev_att}

    # Consecutive absences — get last N service dates per branch and check
    recent_services = frappe.db.sql("""
        SELECT name, service_date, branch
        FROM `tabService Instance`
        WHERE service_date <= %(today)s
          AND status = 'Completed'
        ORDER BY service_date DESC
        LIMIT 20
    """, {"today": str(today)}, as_dict=True)

    # Build attendance lookup for consecutive calc
    all_checkins = frappe.db.sql("""
        SELECT member_id, service_instance
        FROM `tabChurch Attendance`
        WHERE present = 1
          AND member_id IN %(ids)s
    """, {"ids": member_ids}, as_dict=True)
    checkin_set = set((r.member_id, r.service_instance) for r in all_checkins)

    result = []
    min_absent = int(filters.get("min_absent_services", 2))

    for m in members:
        total_svcs = svc_map.get(m.branch, overall_total) or 1
        curr       = curr_map.get(m.member_id)
        attended   = curr.cnt if curr else 0
        absent     = total_svcs - attended
        att_pct    = round(attended / total_svcs * 100, 1)
        last_seen  = getdate(curr.last_seen) if curr and curr.last_seen else None
        days_absent= (today - last_seen).days if last_seen else 999

        # Previous period attendance %
        prev_attended = prev_map.get(m.member_id, 0)
        prev_pct = round(prev_attended / total_svcs * 100, 1)

        # Trend
        pct_diff = att_pct - prev_pct
        trend = "⬆️ Improving" if pct_diff > 5 else ("⬇️ Declining" if pct_diff < -5 else "➡️ Stable")

        # Consecutive absences
        branch_recent = [s for s in recent_services if s.branch == m.branch][:10]
        consecutive = 0
        for svc in branch_recent:
            if (m.member_id, svc.name) not in checkin_set:
                consecutive += 1
            else:
                break

        # Risk level
        if consecutive >= 4 or days_absent > 60:
            risk = "🔴 High"
        elif consecutive >= 2 or days_absent > 30:
            risk = "🟡 Medium"
        else:
            risk = "🟢 Low"

        if absent < min_absent:
            continue

        result.append({
            "member_id":         m.member_id,
            "full_name":         m.full_name,
            "branch":            m.branch,
            "demographic_group": m.demographic_group,
            "mobile_phone":      m.mobile_phone,
            "total_services":    total_svcs,
            "attended":          attended,
            "absent":            absent,
            "attendance_pct":    att_pct,
            "last_seen":         last_seen,
            "days_absent":       days_absent,
            "consecutive_absent":consecutive,
            "prev_period_pct":   prev_pct,
            "trend":             trend,
            "risk_level":        risk,
        })

    result.sort(key=lambda x: x["consecutive_absent"], reverse=True)
    return result

def get_summary(data, filters):
    high_risk   = sum(1 for d in data if "High"   in d["risk_level"])
    medium_risk = sum(1 for d in data if "Medium" in d["risk_level"])
    declining   = sum(1 for d in data if "Declining" in d["trend"])
    never_seen  = sum(1 for d in data if d["days_absent"] == 999)
    return [
        {"value": len(data),     "label": _("Members with Absences"),  "datatype": "Int", "indicator": "orange"},
        {"value": high_risk,     "label": _("High Risk"),              "datatype": "Int", "indicator": "red"},
        {"value": medium_risk,   "label": _("Medium Risk"),            "datatype": "Int", "indicator": "orange"},
        {"value": declining,     "label": _("Declining Trend"),        "datatype": "Int", "indicator": "red"},
        {"value": never_seen,    "label": _("Never Seen in Period"),   "datatype": "Int", "indicator": "grey"},
    ]

def get_chart(data):
    if not data:
        return {}
    # Distribution by consecutive absences
    buckets = {"1": 0, "2": 0, "3": 0, "4": 0, "5+": 0}
    for d in data:
        c = d["consecutive_absent"]
        if c <= 1:   buckets["1"] += 1
        elif c == 2: buckets["2"] += 1
        elif c == 3: buckets["3"] += 1
        elif c == 4: buckets["4"] += 1
        else:        buckets["5+"] += 1
    return {
        "data": {
            "labels":   list(buckets.keys()),
            "datasets": [{"name": _("Members"), "values": list(buckets.values())}]
        },
        "type": "bar",
        "title": _("Members by Consecutive Absences"),
        "colors": ["#e74c3c"],
        "axisOptions": {"xIsSeries": 1}
    }
