# church/church/report/birthday_calendar/birthday_calendar.py

import frappe
from frappe import _
from frappe.utils import nowdate, getdate, add_to_date

def execute(filters=None):
    filters = filters or {}
    columns = get_columns()
    data    = get_data(filters)
    summary = get_summary(data)
    chart   = get_chart(data)
    return columns, data, None, chart, summary

def get_columns():
    return [
        {"fieldname": "name",          "label": _("Member ID"),    "fieldtype": "Link", "options": "Member", "width": 130},
        {"fieldname": "full_name",     "label": _("Full Name"),    "fieldtype": "Data", "width": 180},
        {"fieldname": "date_of_birth", "label": _("Date of Birth"),"fieldtype": "Date", "width": 120},
        {"fieldname": "birthday_this_year","label": _("Birthday"), "fieldtype": "Date", "width": 120},
        {"fieldname": "age_turning",   "label": _("Turning Age"),  "fieldtype": "Int",  "width": 100},
        {"fieldname": "days_away",     "label": _("Days Away"),    "fieldtype": "Int",  "width": 100},
        {"fieldname": "mobile_phone",  "label": _("Mobile"),       "fieldtype": "Data", "width": 130},
        {"fieldname": "email",         "label": _("Email"),        "fieldtype": "Data", "width": 170},
        {"fieldname": "branch",        "label": _("Branch"),       "fieldtype": "Link", "options": "Branch", "width": 120},
        {"fieldname": "gender",        "label": _("Gender"),       "fieldtype": "Data", "width": 80},
    ]

def get_data(filters):
    today = getdate(nowdate())
    
    # FIX: Handle empty month filter properly
    month = filters.get("month")
    if month == "" or month is None:
        month = None
    else:
        try:
            month = int(month)
        except (ValueError, TypeError):
            month = None
    
    branch = filters.get("branch", "")
    days_ahead = int(filters.get("days_ahead", 30))
    
    branch_cond = "AND branch = %(branch)s" if branch else ""

    members = frappe.db.sql(f"""
        SELECT name, full_name, date_of_birth, mobile_phone, email, branch, gender, age
        FROM `tabMember`
        WHERE date_of_birth IS NOT NULL
          AND member_status = 'Active'
          {branch_cond}
        ORDER BY MONTH(date_of_birth), DAY(date_of_birth)
    """, {"branch": branch}, as_dict=True)

    result = []
    for m in members:
        dob = getdate(m.date_of_birth)
        
        # Birthday this year
        try:
            bday = dob.replace(year=today.year)
        except ValueError:  # Feb 29
            bday = dob.replace(year=today.year, day=28)

        if bday < today:
            try:
                bday = dob.replace(year=today.year + 1)
            except ValueError:
                bday = dob.replace(year=today.year + 1, day=28)

        days_away = (bday - today).days

        # FIX: Better filter logic
        if month:  # Month filter is active
            if bday.month != month:
                continue
        else:  # No month filter, use days_ahead
            if days_away > days_ahead:
                continue

        m.birthday_this_year = bday
        m.age_turning = today.year - dob.year if bday.year == today.year else today.year + 1 - dob.year
        m.days_away = days_away
        result.append(m)

    result.sort(key=lambda x: x.days_away)
    return result

def get_summary(data):
    today_bdays = [d for d in data if d.days_away == 0]
    this_week   = [d for d in data if 0 <= d.days_away <= 7]
    return [
        {"value": len(data),        "label": _("Upcoming Birthdays"), "datatype": "Int", "indicator": "blue"},
        {"value": len(today_bdays), "label": _("Today"),              "datatype": "Int", "indicator": "green"},
        {"value": len(this_week),   "label": _("This Week"),          "datatype": "Int", "indicator": "orange"},
    ]

def get_chart(data):
    month_names = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
    counts = [0] * 12
    for d in data:
        counts[d.birthday_this_year.month - 1] += 1
    return {
        "data": {
            "labels":   month_names,
            "datasets": [{"name": _("Birthdays"), "values": counts}]
        },
        "type": "bar",
        "title": _("Birthdays by Month"),
        "colors": ["#f39c12"]
    }