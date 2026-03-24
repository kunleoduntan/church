# Copyright (c) 2026, kunle and contributors
# For license information, please see license.txt


# Copyright (c) 2026, Kunle and contributors
# For license information, please see license.txt

"""
Children Birthday Report
Track and manage children's birthdays across all classes
File: church/church/report/children_birthday_report/children_birthday_report.py
"""

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.utils import getdate, nowdate, add_days, date_diff, formatdate, add_months


def execute(filters=None):
    """Main report execution"""
    columns = get_columns(filters)
    data = get_data(filters)
    chart = get_chart_data(data, filters)
    
    return columns, data, None, chart


def get_columns(filters):
    """Define report columns"""
    return [
        {
            "fieldname": "full_name",
            "label": _("Child Name"),
            "fieldtype": "Data",
            "width": 180
        },
        {
            "fieldname": "child_id",
            "label": _("Member ID"),
            "fieldtype": "Link",
            "options": "Member",
            "width": 120
        },
        {
            "fieldname": "age",
            "label": _("Age"),
            "fieldtype": "Int",
            "width": 60
        },
        {
            "fieldname": "gender",
            "label": _("Gender"),
            "fieldtype": "Data",
            "width": 80
        },
        {
            "fieldname": "date_of_birth",
            "label": _("Date of Birth"),
            "fieldtype": "Date",
            "width": 120
        },
        {
            "fieldname": "birthday_this_year",
            "label": _("Birthday This Year"),
            "fieldtype": "Date",
            "width": 130
        },
        {
            "fieldname": "days_until",
            "label": _("Days Until Birthday"),
            "fieldtype": "Int",
            "width": 140
        },
        {
            "fieldname": "status",
            "label": _("Status"),
            "fieldtype": "Data",
            "width": 120
        },
        {
            "fieldname": "class_name",
            "label": _("Class"),
            "fieldtype": "Link",
            "options": "Children Class",
            "width": 150
        },
        {
            "fieldname": "branch",
            "label": _("Branch"),
            "fieldtype": "Link",
            "options": "Branch",
            "width": 130
        },
        {
            "fieldname": "teacher_name",
            "label": _("Teacher"),
            "fieldtype": "Data",
            "width": 150
        },
        {
            "fieldname": "parent_phone",
            "label": _("Parent Phone"),
            "fieldtype": "Data",
            "width": 130
        },
        {
            "fieldname": "parent_email",
            "label": _("Parent Email"),
            "fieldtype": "Data",
            "width": 180
        }
    ]


def get_data(filters):
    """Fetch birthday data"""
    today = getdate(nowdate())
    
    # Build conditions
    conditions = "WHERE ccm.date_of_birth IS NOT NULL"
    
    if filters.get("branch"):
        conditions += " AND ccm.branch = %(branch)s"
    
    if filters.get("class_name"):
        conditions += " AND ccm.parent = %(class_name)s"
    
    if filters.get("age_group"):
        conditions += " AND cc.age_group = %(age_group)s"
    
    # Date range filters
    if filters.get("view_type") == "This Month":
        conditions += f" AND MONTH(ccm.date_of_birth) = {today.month}"
    elif filters.get("view_type") == "Next Month":
        next_month = add_months(today, 1)
        conditions += f" AND MONTH(ccm.date_of_birth) = {next_month.month}"
    elif filters.get("view_type") == "This Quarter":
        quarter_start = ((today.month - 1) // 3) * 3 + 1
        quarter_end = quarter_start + 2
        conditions += f" AND MONTH(ccm.date_of_birth) BETWEEN {quarter_start} AND {quarter_end}"
    elif filters.get("view_type") == "Upcoming 30 Days":
        # Will be filtered in Python
        pass
    
    # Get all children with birthdays
    # Using ONLY fields from Children Class Member child table
    children = frappe.db.sql(f"""
        SELECT 
            ccm.child_id,
            ccm.full_name,
            ccm.date_of_birth,
            ccm.age,
            ccm.gender,
            ccm.phone_no,
            ccm.email,
            ccm.parent as class_name,
            ccm.branch,
            ccm.class_name as class_display_name,
            ccm.teacher_name
        FROM `tabChildren Class Member` ccm
        INNER JOIN `tabChildren Class` cc ON cc.name = ccm.parent
        {conditions}
        ORDER BY MONTH(ccm.date_of_birth), DAY(ccm.date_of_birth)
    """, filters, as_dict=1)
    
    data = []
    
    for child in children:
        # Calculate birthday this year
        birth_day = child.date_of_birth.day
        birth_month = child.date_of_birth.month
        
        birthday_this_year = getdate(f"{today.year}-{birth_month:02d}-{birth_day:02d}")
        
        # If birthday has passed this year, show next year's
        if birthday_this_year < today:
            birthday_this_year = getdate(f"{today.year + 1}-{birth_month:02d}-{birth_day:02d}")
        
        days_until = date_diff(birthday_this_year, today)
        
        # Apply "Upcoming 30 Days" filter
        if filters.get("view_type") == "Upcoming 30 Days" and days_until > 30:
            continue
        
        # Determine status
        if days_until == 0:
            status = "🎂 TODAY!"
        elif days_until == 1:
            status = "🎈 Tomorrow"
        elif days_until <= 7:
            status = "⏰ This Week"
        elif days_until <= 30:
            status = "📅 This Month"
        else:
            status = "📆 Upcoming"
        
        # Get contact info from Children Class Member fields
        parent_phone = child.phone_no or ""
        parent_email = child.email or ""
        
        data.append({
            'full_name': child.full_name,
            'child_id': child.child_id,
            'age': child.age,
            'gender': child.gender,
            'date_of_birth': child.date_of_birth,
            'birthday_this_year': birthday_this_year,
            'days_until': days_until,
            'status': status,
            'class_name': child.class_name,
            'branch': child.branch,
            'teacher_name': child.teacher_name,
            'parent_phone': parent_phone,
            'parent_email': parent_email
        })
    
    # Sort by days until birthday
    data.sort(key=lambda x: x['days_until'])
    
    return data


def get_chart_data(data, filters):
    """Generate birthday distribution chart"""
    if not data:
        return None
    
    # Count birthdays by month
    month_counts = {}
    month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 
                   'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    
    for child in data:
        month = child['date_of_birth'].month
        month_name = month_names[month - 1]
        month_counts[month_name] = month_counts.get(month_name, 0) + 1
    
    # Ensure all months are represented
    labels = []
    values = []
    for month_name in month_names:
        labels.append(month_name)
        values.append(month_counts.get(month_name, 0))
    
    chart = {
        'data': {
            'labels': labels,
            'datasets': [
                {
                    'name': 'Birthdays',
                    'values': values
                }
            ]
        },
        'type': 'bar',
        'colors': ['#F59E0B'],
        'height': 300,
        'axisOptions': {
            'xIsSeries': 1
        }
    }
    
    return chart


# ==================== REPORT ACTION METHODS ====================

@frappe.whitelist()
def send_batch_birthday_wishes(children):
    """Send birthday wishes to multiple children"""
    import json
    from church.church.doctype.children_class.children_class import send_birthday_wishes_multi_channel, log_birthday_wish
    
    children_list = json.loads(children) if isinstance(children, str) else children
    settings = frappe.get_single("Church Settings")
    
    if not settings.enable_birthday_notifications:
        frappe.throw(_("Birthday notifications are disabled in Church Settings"))
    
    sent_count = 0
    today = getdate(nowdate())
    
    for child_id in children_list:
        try:
            # Get child details using ONLY Children Class Member fields
            child_data = frappe.db.sql("""
                SELECT 
                    ccm.child_id,
                    ccm.full_name,
                    ccm.date_of_birth,
                    ccm.gender,
                    ccm.phone_no,
                    ccm.email,
                    ccm.age,
                    ccm.branch,
                    ccm.class_name,
                    ccm.teacher_name,
                    ccm.parent as children_class_name
                FROM `tabChildren Class Member` ccm
                WHERE ccm.child_id = %s
                LIMIT 1
            """, (child_id,), as_dict=1)
            
            if not child_data:
                continue
            
            child = child_data[0]
            age = date_diff(today, child.date_of_birth) // 365
            
            # Send birthday wishes
            send_birthday_wishes_multi_channel(child, age, settings)
            log_birthday_wish(child, age)
            
            sent_count += 1
            
        except Exception as e:
            frappe.log_error(f"Batch birthday wish failed for {child_id}: {str(e)}")
    
    frappe.db.commit()
    
    return {
        'sent_count': sent_count,
        'message': f'Sent {sent_count} birthday wishes'
    }


@frappe.whitelist()
def export_birthday_calendar(filters=None):
    """Export birthday calendar to Excel"""
    import pandas as pd
    from io import BytesIO
    from frappe.utils import format_date
    
    filters = frappe._dict(filters) if isinstance(filters, dict) else frappe._dict()
    data = get_data(filters)
    
    if not data:
        frappe.throw(_("No birthday data found for export"))
    
    output = BytesIO()
    writer = pd.ExcelWriter(output, engine='xlsxwriter')
    workbook = writer.book
    
    # Formats
    header_format = workbook.add_format({
        'bold': True,
        'bg_color': '#F59E0B',
        'font_color': 'white',
        'border': 1,
        'align': 'center',
        'valign': 'vcenter'
    })
    
    title_format = workbook.add_format({
        'bold': True,
        'font_size': 20,
        'bg_color': '#FFF9E6',
        'align': 'center',
        'valign': 'vcenter'
    })
    
    today_format = workbook.add_format({
        'bg_color': '#D1FAE5',
        'border': 1,
        'bold': True
    })
    
    thisweek_format = workbook.add_format({
        'bg_color': '#FEF3C7',
        'border': 1
    })
    
    # Main birthday list
    birthday_data = []
    for row in data:
        birthday_data.append({
            'Child Name': row['full_name'],
            'Age': row['age'],
            'Gender': row['gender'],
            'Date of Birth': format_date(row['date_of_birth'], 'dd MMM yyyy'),
            'Birthday This Year': format_date(row['birthday_this_year'], 'dd MMM yyyy'),
            'Days Until': row['days_until'],
            'Status': row['status'],
            'Class': row['class_name'],
            'Branch': row['branch'],
            'Teacher': row['teacher_name'],
            'Parent Phone': row['parent_phone'],
            'Parent Email': row['parent_email']
        })
    
    df = pd.DataFrame(birthday_data)
    df.to_excel(writer, sheet_name='Birthday Calendar', startrow=2, index=False)
    
    ws = writer.sheets['Birthday Calendar']
    ws.merge_range('A1:L1', '🎂 CHILDREN BIRTHDAY CALENDAR', title_format)
    ws.set_row(0, 40)
    
    # Apply header format
    for col_num, value in enumerate(df.columns.values):
        ws.write(2, col_num, value, header_format)
    
    # Apply conditional formatting
    for row_num, row_data in enumerate(data, 3):
        if row_data['days_until'] == 0:
            for col in range(12):
                ws.write(row_num, col, df.iloc[row_num - 3, col], today_format)
        elif row_data['days_until'] <= 7:
            for col in range(12):
                ws.write(row_num, col, df.iloc[row_num - 3, col], thisweek_format)
    
    # Set column widths
    ws.set_column('A:A', 25)  # Name
    ws.set_column('B:B', 8)   # Age
    ws.set_column('C:C', 10)  # Gender
    ws.set_column('D:E', 18)  # Dates
    ws.set_column('F:F', 12)  # Days Until
    ws.set_column('G:G', 15)  # Status
    ws.set_column('H:J', 20)  # Class, Branch, Teacher
    ws.set_column('K:L', 25)  # Contact
    
    # Month-by-month breakdown
    months = ['January', 'February', 'March', 'April', 'May', 'June',
              'July', 'August', 'September', 'October', 'November', 'December']
    
    for month_num, month_name in enumerate(months, 1):
        month_data = [row for row in data if row['date_of_birth'].month == month_num]
        
        if month_data:
            month_df_data = [{
                'Name': row['full_name'],
                'Day': row['date_of_birth'].day,
                'Age': row['age'],
                'Class': row['class_name'],
                'Parent Phone': row['parent_phone']
            } for row in month_data]
            
            month_df = pd.DataFrame(month_df_data)
            month_df.to_excel(writer, sheet_name=month_name[:10], startrow=1, index=False)
            
            ws_month = writer.sheets[month_name[:10]]
            ws_month.merge_range('A1:E1', f'🎂 {month_name} Birthdays', title_format)
            
            for col_num, value in enumerate(month_df.columns.values):
                ws_month.write(1, col_num, value, header_format)
            
            ws_month.set_column('A:A', 25)
            ws_month.set_column('B:E', 15)
    
    writer.close()
    output.seek(0)
    
    # Save file
    from frappe.utils import now_datetime
    file_name = f"Birthday_Calendar_{now_datetime().strftime('%Y%m%d_%H%M%S')}.xlsx"
    
    file_doc = frappe.get_doc({
        'doctype': 'File',
        'file_name': file_name,
        'content': output.read(),
        'is_private': 0
    })
    file_doc.save(ignore_permissions=True)
    
    return {
        'file_url': file_doc.file_url,
        'file_name': file_name
    }


@frappe.whitelist()
def send_teacher_birthday_reminders(filters=None):
    """Send birthday reminders to teachers for upcoming birthdays"""
    from frappe.utils import formatdate
    
    filters = frappe._dict(filters) if isinstance(filters, dict) else frappe._dict()
    data = get_data(filters)
    settings = frappe.get_single("Church Settings")
    
    # Group by teacher
    teacher_birthdays = {}
    
    for row in data:
        if row['days_until'] <= 7 and row['days_until'] >= 0:  # Next 7 days
            teacher = row['teacher_name']
            if teacher not in teacher_birthdays:
                teacher_birthdays[teacher] = {
                    'email': None,
                    'class_name': row['class_name'],
                    'children': []
                }
            
            teacher_birthdays[teacher]['children'].append(row)
    
    sent_count = 0
    
    for teacher_name, info in teacher_birthdays.items():
        # Get teacher email
        teacher_email = frappe.db.get_value('Children Class', info['class_name'], 'email')
        
        if not teacher_email:
            continue
        
        # Build birthday list
        birthday_rows = ""
        for child in info['children']:
            birthday_rows += f"""
                <tr style="border-bottom: 1px solid #eee;">
                    <td style="padding: 12px;">{child['full_name']}</td>
                    <td style="padding: 12px; text-align: center;">{child['age']}</td>
                    <td style="padding: 12px; text-align: center;">{formatdate(child['birthday_this_year'], 'dd MMM')}</td>
                    <td style="padding: 12px; text-align: center; color: #f59e0b; font-weight: bold;">
                        {'TODAY!' if child['days_until'] == 0 else f"{child['days_until']} days"}
                    </td>
                </tr>
            """
        
        subject = f"🎂 Birthday Reminder - {info['class_name']}"
        
        message = f"""
        <div style="font-family: Arial, sans-serif; max-width: 650px; margin: 0 auto;">
            <div style="background: linear-gradient(135deg, #F59E0B, #F97316); padding: 30px; text-align: center; border-radius: 15px 15px 0 0;">
                <h1 style="color: white; margin: 0;">🎂 Birthday Reminder</h1>
                <p style="color: rgba(255,255,255,0.9); margin: 10px 0 0 0;">{info['class_name']}</p>
            </div>
            
            <div style="background: white; padding: 30px; border-radius: 0 0 15px 15px; box-shadow: 0 4px 15px rgba(0,0,0,0.1);">
                <p>Dear <strong>{teacher_name}</strong>,</p>
                
                <p>The following children have birthdays coming up this week:</p>
                
                <table style="width: 100%; border-collapse: collapse; margin: 20px 0;">
                    <thead>
                        <tr style="background: linear-gradient(135deg, #F59E0B, #F97316); color: white;">
                            <th style="padding: 15px; text-align: left;">Child</th>
                            <th style="padding: 15px; text-align: center;">Age</th>
                            <th style="padding: 15px; text-align: center;">Birthday</th>
                            <th style="padding: 15px; text-align: center;">When</th>
                        </tr>
                    </thead>
                    <tbody>{birthday_rows}</tbody>
                </table>
                
                <div style="background: #FFF9E6; padding: 20px; border-left: 4px solid #F59E0B; border-radius: 5px;">
                    <p style="margin: 0;">💡 Consider preparing a special birthday greeting for these children!</p>
                </div>
                
                <p style="font-size: 14px; color: #999; margin-top: 30px; padding-top: 20px; border-top: 2px solid #f0f0f0;">
                    {settings.church_name or 'Your Church'}<br>
                    Automated from Ecclesia Church Management System
                </p>
            </div>
        </div>
        """
        
        try:
            frappe.sendmail(
                recipients=[teacher_email],
                subject=subject,
                message=message,
                delayed=False
            )
            sent_count += 1
        except Exception as e:
            frappe.log_error(f"Teacher reminder failed: {str(e)}")
    
    return {
        'sent_count': sent_count,
        'message': f'Sent {sent_count} reminder emails'
    }