# church/church/report/birthday_celebration_calendar/birthday_celebration_calendar.py

import frappe
from frappe import _
from frappe.utils import nowdate, getdate, add_to_date
from datetime import datetime, timedelta
import json

def execute(filters=None):
    filters = filters or {}
    columns = get_columns()
    data = get_data(filters)
    chart = get_chart(data)
    summary = get_summary(data)
    
    return columns, data, None, chart, summary

def get_columns():
    return [
        {"fieldname": "full_name", "label": _("Member"), "fieldtype": "Data", "width": 200},
        {"fieldname": "date_of_birth", "label": _("Birth Date"), "fieldtype": "Date", "width": 110},
        {"fieldname": "birthday_this_year", "label": _("Celebration Date"), "fieldtype": "Date", "width": 130},
        {"fieldname": "age_turning", "label": _("Age"), "fieldtype": "Int", "width": 100},
        {"fieldname": "days_away", "label": _("Days Until"), "fieldtype": "Int", "width": 120},
        {"fieldname": "celebration_type", "label": _("Type"), "fieldtype": "Data", "width": 120},
        {"fieldname": "branch", "label": _("Branch"), "fieldtype": "Link", "options": "Branch", "width": 150},
        {"fieldname": "mobile_phone", "label": _("Phone"), "fieldtype": "Data", "width": 130},
        {"fieldname": "email", "label": _("Email"), "fieldtype": "Data", "width": 180},
        {"fieldname": "gender", "label": _("Gender"), "fieldtype": "Data", "width": 80},
        {"fieldname": "is_milestone", "label": _("Milestone"), "fieldtype": "Check", "width": 90}
    ]

def get_data(filters):
    today = getdate(nowdate())
    view_type = filters.get("view_type", "Calendar View")
    branch = filters.get("branch", "")
    
    # Get members
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
    milestones = [1, 5, 10, 13, 16, 18, 21, 25, 30, 40, 50, 60, 70, 80, 90, 100]
    
    for member in members:
        dob = getdate(member.date_of_birth)
        
        # Calculate next birthday
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
        age_turning = today.year - dob.year if bday.year == today.year else today.year + 1 - dob.year
        is_milestone = age_turning in milestones
        
        # Apply filters
        if view_type == "Calendar View":
            filter_month = filters.get("month")
            filter_year = filters.get("year")
            
            # Handle month filter
            if filter_month and filter_month != "":
                try:
                    month_num = datetime.strptime(filter_month, "%B").month
                    if bday.month != month_num:
                        continue
                except:
                    pass
            
            # Handle year filter
            if filter_year and filter_year != "":
                try:
                    year_num = int(filter_year)
                    if bday.year != year_num:
                        continue
                except:
                    pass
        else:  # List View
            days_ahead = int(filters.get("days_ahead", 30))
            if days_away > days_ahead:
                continue
            # Milestone only filter
            if filters.get("milestone_only") == "1" and not is_milestone:
                continue
        
        member.birthday_this_year = bday
        member.age_turning = age_turning
        member.days_away = days_away
        member.celebration_type = "Milestone" if is_milestone else "Birthday"
        member.is_milestone = 1 if is_milestone else 0
        result.append(member)
    
    # Sort by days away
    result.sort(key=lambda x: x.days_away)
    return result

def get_chart(data):
    if not data:
        return None
    
    # Group by day of month for calendar view
    day_counts = {}
    for d in data:
        if d.birthday_this_year:
            day = d.birthday_this_year.day
            day_counts[day] = day_counts.get(day, 0) + 1
    
    days = list(day_counts.keys())
    counts = list(day_counts.values())
    
    if not days:
        return None
    
    return {
        "data": {
            "labels": [f"Day {day}" for day in days],
            "datasets": [{
                "name": _("Birthdays"),
                "values": counts,
                "chartType": "bar",
                "colors": ["#48bb78"]
            }]
        },
        "type": "bar",
        "title": _("Birthday Distribution by Day"),
        "height": 300
    }

def get_summary(data):
    today = getdate(nowdate())
    today_birthdays = [d for d in data if d.days_away == 0]
    this_week = [d for d in data if 0 <= d.days_away <= 7]
    milestones = [d for d in data if d.is_milestone]
    
    return [
        {
            "value": len(data),
            "label": _("Total Birthdays"),
            "datatype": "Int",
            "indicator": "blue",
            "color": "#4299e1"
        },
        {
            "value": len(today_birthdays),
            "label": _("Celebrating Today"),
            "datatype": "Int",
            "indicator": "green",
            "color": "#48bb78"
        },
        {
            "value": len(this_week),
            "label": _("This Week"),
            "datatype": "Int",
            "indicator": "orange",
            "color": "#ed8936"
        },
        {
            "value": len(milestones),
            "label": _("Milestones"),
            "datatype": "Int",
            "indicator": "purple",
            "color": "#9f7aea"
        }
    ]

@frappe.whitelist()
def send_reminders(filters):
    """Send email reminders for upcoming birthdays"""
    try:
        # Parse filters if they come as string
        if isinstance(filters, str):
            filters = json.loads(filters)
        
        # Get data with filters
        data = get_data(filters)
        
        # Get birthdays in next 7 days
        upcoming = [d for d in data if 0 <= d.days_away <= 7]
        
        sent_count = 0
        for member in upcoming:
            try:
                if not member.email:
                    continue
                    
                subject = f"🎂 Birthday Reminder: {member.full_name}"
                message = f"""
                <div style="font-family: Arial, sans-serif; padding: 20px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 10px;">
                    <div style="background: white; padding: 30px; border-radius: 10px;">
                        <h2 style="color: #4a5568;">🎉 Happy Birthday {member.full_name}! 🎉</h2>
                        <p style="color: #718096; font-size: 16px;">You're turning <strong>{member.age_turning} years old</strong> in {member.days_away} days!</p>
                        {f'<p style="color: #ed8936; font-weight: bold; font-size: 14px;">✨ This is a MILESTONE birthday! ✨</p>' if member.is_milestone else ''}
                        <hr style="margin: 20px 0;">
                        <p style="color: #718096;">We're excited to celebrate with you at your branch: <strong>{member.branch}</strong></p>
                        <p style="color: #a0aec0; font-size: 12px; margin-top: 20px;">Warm regards,<br>Church Family</p>
                    </div>
                </div>
                """
                
                frappe.sendmail(
                    recipients=[member.email],
                    subject=subject,
                    message=message,
                    delayed=False
                )
                sent_count += 1
                
            except Exception as e:
                frappe.log_error(f"Failed to send birthday reminder to {member.email}: {str(e)}", "Birthday Reminder Error")
                continue
        
        return {"sent": sent_count, "total": len(upcoming)}
        
    except Exception as e:
        frappe.log_error(f"Error in send_reminders: {str(e)}", "Birthday Reminder Error")
        return {"sent": 0, "total": 0, "error": str(e)}