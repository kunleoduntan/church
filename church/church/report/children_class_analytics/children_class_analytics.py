# Copyright (c) 2026, kunle and contributors
# For license information, please see license.txt




# Copyright (c) 2026, Kunle and contributors
# For license information, please see license.txt

"""
Children Class Analytics Report
Comprehensive analytics for children's ministry management
File: church/church/report/children_class_analytics/children_class_analytics.py
"""

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.utils import getdate, nowdate, add_days, date_diff, flt


def execute(filters=None):
    """Main report execution function"""
    columns = get_columns(filters)
    data = get_data(filters)
    chart = get_chart_data(data, filters)
    summary = get_report_summary(data, filters)
    
    return columns, data, None, chart, summary


def get_columns(filters):
    """Define report columns"""
    columns = [
        {
            "fieldname": "class_name",
            "label": _("Class Name"),
            "fieldtype": "Link",
            "options": "Children Class",
            "width": 180
        },
        {
            "fieldname": "branch",
            "label": _("Branch"),
            "fieldtype": "Link",
            "options": "Branch",
            "width": 140
        },
        {
            "fieldname": "age_group",
            "label": _("Age Group"),
            "fieldtype": "Data",
            "width": 120
        },
        {
            "fieldname": "teacher_name",
            "label": _("Teacher"),
            "fieldtype": "Data",
            "width": 150
        },
        {
            "fieldname": "total_members",
            "label": _("Total Members"),
            "fieldtype": "Int",
            "width": 120
        },
        {
            "fieldname": "male_count",
            "label": _("Male"),
            "fieldtype": "Int",
            "width": 80
        },
        {
            "fieldname": "female_count",
            "label": _("Female"),
            "fieldtype": "Int",
            "width": 80
        },
        {
            "fieldname": "avg_age",
            "label": _("Avg Age"),
            "fieldtype": "Float",
            "width": 90,
            "precision": 1
        },
        {
            "fieldname": "promotion_age",
            "label": _("Promotion Age"),
            "fieldtype": "Int",
            "width": 120
        },
        {
            "fieldname": "ready_for_promotion",
            "label": _("Ready for Promotion"),
            "fieldtype": "Int",
            "width": 140
        },
        {
            "fieldname": "assets_count",
            "label": _("Assets"),
            "fieldtype": "Int",
            "width": 80
        },
        {
            "fieldname": "asset_value",
            "label": _("Asset Value"),
            "fieldtype": "Currency",
            "width": 130
        },
        {
            "fieldname": "birthdays_this_month",
            "label": _("Birthdays This Month"),
            "fieldtype": "Int",
            "width": 150
        },
        {
            "fieldname": "birthdays_next_month",
            "label": _("Birthdays Next Month"),
            "fieldtype": "Int",
            "width": 150
        }
    ]
    
    return columns


def get_data(filters):
    """Fetch and process report data"""
    conditions = get_conditions(filters)
    
    # Get all classes with member details
    classes = frappe.db.sql(f"""
        SELECT 
            cc.name as class_name,
            cc.branch,
            cc.age_group,
            cc.teacher_name,
            cc.promotion_age,
            cc.member_count as total_members,
            cc.value_of_asset as asset_value
        FROM `tabChildren Class` cc
        WHERE 1=1 {conditions}
        ORDER BY cc.branch, cc.class_name
    """, filters, as_dict=1)
    
    today = getdate(nowdate())
    current_month = today.month
    current_year = today.year
    next_month = current_month + 1 if current_month < 12 else 1
    next_month_year = current_year if current_month < 12 else current_year + 1
    
    data = []
    
    for class_doc in classes:
        # Get member statistics
        members = frappe.db.sql("""
            SELECT 
                child_id,
                gender,
                age,
                date_of_birth
            FROM `tabChildren Class Member`
            WHERE parent = %s
        """, class_doc.class_name, as_dict=1)
        
        male_count = len([m for m in members if m.gender == 'Male'])
        female_count = len([m for m in members if m.gender == 'Female'])
        
        # Calculate average age
        ages = [m.age for m in members if m.age]
        avg_age = sum(ages) / len(ages) if ages else 0
        
        # Count ready for promotion
        ready_for_promotion = 0
        if class_doc.promotion_age:
            ready_for_promotion = len([
                m for m in members 
                if m.age and m.age >= class_doc.promotion_age
            ])
        
        # Count birthdays this month
        birthdays_this_month = len([
            m for m in members 
            if m.date_of_birth and m.date_of_birth.month == current_month
        ])
        
        # Count birthdays next month
        birthdays_next_month = len([
            m for m in members 
            if m.date_of_birth and m.date_of_birth.month == next_month
        ])
        
        # Count assets
        assets_count = frappe.db.count('Children Class Assets', {
            'parent': class_doc.class_name
        })
        
        data.append({
            'class_name': class_doc.class_name,
            'branch': class_doc.branch,
            'age_group': class_doc.age_group,
            'teacher_name': class_doc.teacher_name,
            'total_members': class_doc.total_members or 0,
            'male_count': male_count,
            'female_count': female_count,
            'avg_age': round(avg_age, 1),
            'promotion_age': class_doc.promotion_age,
            'ready_for_promotion': ready_for_promotion,
            'assets_count': assets_count,
            'asset_value': class_doc.asset_value or 0,
            'birthdays_this_month': birthdays_this_month,
            'birthdays_next_month': birthdays_next_month
        })
    
    return data


def get_conditions(filters):
    """Build SQL conditions from filters"""
    conditions = ""
    
    if filters.get("branch"):
        conditions += " AND cc.branch = %(branch)s"
    
    if filters.get("age_group"):
        conditions += " AND cc.age_group = %(age_group)s"
    
    if filters.get("teacher"):
        conditions += " AND cc.teacher = %(teacher)s"
    
    if filters.get("class_name"):
        conditions += " AND cc.name = %(class_name)s"
    
    return conditions


def get_chart_data(data, filters):
    """Generate chart data for visualization"""
    if not data:
        return None
    
    # Chart 1: Members by Class
    labels = [d['class_name'] for d in data]
    values = [d['total_members'] for d in data]
    
    chart = {
        'data': {
            'labels': labels[:10],  # Limit to top 10 for readability
            'datasets': [
                {
                    'name': 'Total Members',
                    'values': values[:10]
                }
            ]
        },
        'type': 'bar',
        'colors': ['#667EEA'],
        'height': 300,
        'axisOptions': {
            'xIsSeries': 1
        },
        'barOptions': {
            'stacked': 0
        }
    }
    
    return chart


def get_report_summary(data, filters):
    """Generate report summary cards"""
    if not data:
        return []
    
    total_members = sum([d['total_members'] for d in data])
    total_males = sum([d['male_count'] for d in data])
    total_females = sum([d['female_count'] for d in data])
    total_ready_promotion = sum([d['ready_for_promotion'] for d in data])
    total_assets = sum([d['assets_count'] for d in data])
    total_asset_value = sum([d['asset_value'] for d in data])
    total_birthdays_this_month = sum([d['birthdays_this_month'] for d in data])
    total_birthdays_next_month = sum([d['birthdays_next_month'] for d in data])
    
    summary = [
        {
            'value': len(data),
            'label': 'Total Classes',
            'datatype': 'Int',
            'indicator': 'Blue'
        },
        {
            'value': total_members,
            'label': 'Total Children',
            'datatype': 'Int',
            'indicator': 'Green'
        },
        {
            'value': total_males,
            'label': 'Male Children',
            'datatype': 'Int',
            'indicator': 'Blue'
        },
        {
            'value': total_females,
            'label': 'Female Children',
            'datatype': 'Int',
            'indicator': 'Pink'
        },
        {
            'value': total_ready_promotion,
            'label': 'Ready for Promotion',
            'datatype': 'Int',
            'indicator': 'Orange'
        },
        {
            'value': total_assets,
            'label': 'Total Assets',
            'datatype': 'Int',
            'indicator': 'Purple'
        },
        {
            'value': total_asset_value,
            'label': 'Asset Value',
            'datatype': 'Currency',
            'indicator': 'Green'
        },
        {
            'value': total_birthdays_this_month,
            'label': 'Birthdays This Month',
            'datatype': 'Int',
            'indicator': 'Yellow'
        },
        {
            'value': total_birthdays_next_month,
            'label': 'Birthdays Next Month',
            'datatype': 'Int',
            'indicator': 'Orange'
        }
    ]
    
    return summary


# ==================== REPORT ACTION METHODS ====================

@frappe.whitelist()
def export_combined_report(filters=None):
    """Export combined report for all classes"""
    import pandas as pd
    from io import BytesIO
    
    try:
        filters = frappe._dict(filters) if isinstance(filters, dict) else frappe._dict()
        data = get_data(filters)
        
        if not data:
            frappe.throw(_("No data found for export"))
        
        output = BytesIO()
        writer = pd.ExcelWriter(output, engine='xlsxwriter')
        workbook = writer.book
        
        # Define formats
        header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#667EEA',
            'font_color': 'white',
            'border': 1,
            'align': 'center',
            'valign': 'vcenter'
        })
        
        title_format = workbook.add_format({
            'bold': True,
            'font_size': 18,
            'bg_color': '#E9ECEF',
            'align': 'center',
            'valign': 'vcenter'
        })
        
        data_format = workbook.add_format({
            'border': 1,
            'align': 'left',
            'valign': 'vcenter'
        })
        
        number_format = workbook.add_format({
            'border': 1,
            'align': 'right',
            'num_format': '#,##0'
        })
        
        currency_format = workbook.add_format({
            'border': 1,
            'align': 'right',
            'num_format': '#,##0.00'
        })
        
        # Sheet 1: Class Analytics Summary
        summary_data = []
        for row in data:
            summary_data.append({
                'Class Name': row['class_name'],
                'Branch': row['branch'],
                'Age Group': row['age_group'],
                'Teacher': row['teacher_name'],
                'Total Members': row['total_members'],
                'Male': row['male_count'],
                'Female': row['female_count'],
                'Avg Age': row['avg_age'],
                'Ready for Promotion': row['ready_for_promotion'],
                'Assets': row['assets_count'],
                'Asset Value': row['asset_value'],
                'Birthdays This Month': row['birthdays_this_month'],
                'Birthdays Next Month': row['birthdays_next_month']
            })
        
        df_summary = pd.DataFrame(summary_data)
        df_summary.to_excel(writer, sheet_name='Class Analytics', startrow=2, index=False)
        
        ws = writer.sheets['Class Analytics']
        ws.merge_range('A1:M1', '📊 CHILDREN CLASS ANALYTICS REPORT', title_format)
        ws.merge_range('A2:M2', f"Generated: {frappe.utils.now_datetime().strftime('%d %B %Y, %I:%M %p')}", 
                      workbook.add_format({'align': 'center', 'italic': True, 'font_size': 10}))
        ws.set_row(0, 35)
        ws.set_row(1, 20)
        
        # Apply header format
        for col_num, value in enumerate(df_summary.columns.values):
            ws.write(2, col_num, value, header_format)
        
        # Set column widths
        ws.set_column('A:A', 25)  # Class Name
        ws.set_column('B:B', 18)  # Branch
        ws.set_column('C:C', 15)  # Age Group
        ws.set_column('D:D', 20)  # Teacher
        ws.set_column('E:M', 14)  # Numbers
        
        # Sheet 2: Branch Summary
        branch_summary = {}
        for row in data:
            branch = row['branch']
            if branch not in branch_summary:
                branch_summary[branch] = {
                    'classes': 0,
                    'total_members': 0,
                    'male': 0,
                    'female': 0,
                    'assets': 0,
                    'asset_value': 0
                }
            
            branch_summary[branch]['classes'] += 1
            branch_summary[branch]['total_members'] += row['total_members']
            branch_summary[branch]['male'] += row['male_count']
            branch_summary[branch]['female'] += row['female_count']
            branch_summary[branch]['assets'] += row['assets_count']
            branch_summary[branch]['asset_value'] += row['asset_value']
        
        branch_data = []
        for branch, stats in branch_summary.items():
            branch_data.append({
                'Branch': branch,
                'Classes': stats['classes'],
                'Total Members': stats['total_members'],
                'Male': stats['male'],
                'Female': stats['female'],
                'Assets': stats['assets'],
                'Asset Value': stats['asset_value']
            })
        
        df_branch = pd.DataFrame(branch_data)
        df_branch.to_excel(writer, sheet_name='Branch Summary', startrow=2, index=False)
        
        ws_branch = writer.sheets['Branch Summary']
        ws_branch.merge_range('A1:G1', '🏢 BRANCH SUMMARY', title_format)
        ws_branch.set_row(0, 35)
        
        for col_num, value in enumerate(df_branch.columns.values):
            ws_branch.write(2, col_num, value, header_format)
        
        ws_branch.set_column('A:A', 25)
        ws_branch.set_column('B:G', 18)
        
        # Sheet 3: Birthday Calendar (This Month & Next Month)
        birthday_data = []
        for row in data:
            if row['birthdays_this_month'] > 0 or row['birthdays_next_month'] > 0:
                birthday_data.append({
                    'Class': row['class_name'],
                    'Branch': row['branch'],
                    'Teacher': row['teacher_name'],
                    'Birthdays This Month': row['birthdays_this_month'],
                    'Birthdays Next Month': row['birthdays_next_month']
                })
        
        if birthday_data:
            df_birthdays = pd.DataFrame(birthday_data)
            df_birthdays.to_excel(writer, sheet_name='Birthday Calendar', startrow=2, index=False)
            
            ws_bday = writer.sheets['Birthday Calendar']
            ws_bday.merge_range('A1:E1', '🎂 UPCOMING BIRTHDAYS', title_format)
            ws_bday.set_row(0, 35)
            
            for col_num, value in enumerate(df_birthdays.columns.values):
                ws_bday.write(2, col_num, value, header_format)
            
            ws_bday.set_column('A:C', 25)
            ws_bday.set_column('D:E', 20)
        
        # Sheet 4: Promotions Due
        promotion_data = []
        for row in data:
            if row['ready_for_promotion'] > 0:
                promotion_data.append({
                    'Class': row['class_name'],
                    'Branch': row['branch'],
                    'Teacher': row['teacher_name'],
                    'Ready for Promotion': row['ready_for_promotion'],
                    'Promotion Age': row['promotion_age']
                })
        
        if promotion_data:
            df_promotions = pd.DataFrame(promotion_data)
            df_promotions.to_excel(writer, sheet_name='Promotions Due', startrow=2, index=False)
            
            ws_promo = writer.sheets['Promotions Due']
            ws_promo.merge_range('A1:E1', '📈 CHILDREN READY FOR PROMOTION', title_format)
            ws_promo.set_row(0, 35)
            
            for col_num, value in enumerate(df_promotions.columns.values):
                ws_promo.write(2, col_num, value, header_format)
            
            ws_promo.set_column('A:C', 25)
            ws_promo.set_column('D:E', 20)
        
        # Save workbook
        writer.close()
        output.seek(0)
        
        # Create file
        from frappe.utils import now_datetime
        file_name = f"Children_Class_Analytics_{now_datetime().strftime('%Y%m%d_%H%M%S')}.xlsx"
        
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
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), 'Combined Report Export Error')
        frappe.throw(_('Failed to generate combined report: {0}').format(str(e)))


@frappe.whitelist()
def send_birthday_reminders(filters=None):
    """Send birthday reminder emails to teachers"""
    from frappe.utils import formatdate, add_days
    
    filters = frappe._dict(filters) if isinstance(filters, dict) else frappe._dict()
    settings = frappe.get_single("Church Settings")
    
    today = getdate(nowdate())
    next_7_days = add_days(today, 7)
    
    # Get all classes
    conditions = get_conditions(filters)
    
    classes = frappe.db.sql(f"""
        SELECT 
            cc.name as class_name,
            cc.class_name as display_name,
            cc.teacher_name,
            cc.email as teacher_email,
            cc.branch
        FROM `tabChildren Class` cc
        WHERE cc.email IS NOT NULL {conditions}
    """, filters, as_dict=1)
    
    sent_count = 0
    
    for class_doc in classes:
        # Get children with birthdays in next 7 days
        upcoming_birthdays = frappe.db.sql("""
            SELECT 
                full_name,
                date_of_birth,
                age,
                gender
            FROM `tabChildren Class Member`
            WHERE parent = %s
                AND date_of_birth IS NOT NULL
                AND (
                    (MONTH(date_of_birth) = MONTH(%s) AND DAY(date_of_birth) >= DAY(%s))
                    OR (MONTH(date_of_birth) = MONTH(%s) AND DAY(date_of_birth) <= DAY(%s))
                )
            ORDER BY MONTH(date_of_birth), DAY(date_of_birth)
        """, (class_doc.class_name, today, today, next_7_days, next_7_days), as_dict=1)
        
        if not upcoming_birthdays:
            continue
        
        # Build birthday list HTML
        birthday_rows = ""
        for child in upcoming_birthdays:
            birth_day = child.date_of_birth.day
            birth_month = child.date_of_birth.month
            birthday_this_year = getdate(f"{today.year}-{birth_month:02d}-{birth_day:02d}")
            days_until = date_diff(birthday_this_year, today)
            
            birthday_rows += f"""
                <tr style="border-bottom: 1px solid #eee;">
                    <td style="padding: 12px;">{child.full_name}</td>
                    <td style="padding: 12px; text-align: center;">{child.age}</td>
                    <td style="padding: 12px; text-align: center;">{formatdate(birthday_this_year, 'dd MMM')}</td>
                    <td style="padding: 12px; text-align: center; color: #f59e0b; font-weight: bold;">
                        {days_until} day{'s' if days_until != 1 else ''}
                    </td>
                </tr>
            """
        
        # Send reminder email
        subject = f"🎂 Upcoming Birthdays - {class_doc.display_name}"
        
        message = f"""
        <div style="font-family: Arial, sans-serif; max-width: 650px; margin: 0 auto;">
            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; border-radius: 15px 15px 0 0; text-align: center;">
                <h1 style="color: white; margin: 0; font-size: 28px;">🎂 Birthday Reminder</h1>
                <p style="color: rgba(255,255,255,0.9); margin: 10px 0 0 0;">{class_doc.display_name}</p>
            </div>
            
            <div style="background: white; padding: 30px; border-radius: 0 0 15px 15px; box-shadow: 0 4px 15px rgba(0,0,0,0.1);">
                <p style="font-size: 16px; color: #333;">Dear <strong>{class_doc.teacher_name}</strong>,</p>
                
                <p style="font-size: 16px; color: #333; line-height: 1.6;">
                    The following children in your class have birthdays coming up in the next 7 days:
                </p>
                
                <table style="width: 100%; border-collapse: collapse; margin: 20px 0;">
                    <thead>
                        <tr style="background: linear-gradient(135deg, #667eea, #764ba2); color: white;">
                            <th style="padding: 15px; text-align: left;">Child Name</th>
                            <th style="padding: 15px; text-align: center;">Age</th>
                            <th style="padding: 15px; text-align: center;">Birthday</th>
                            <th style="padding: 15px; text-align: center;">In</th>
                        </tr>
                    </thead>
                    <tbody>
                        {birthday_rows}
                    </tbody>
                </table>
                
                <div style="background: #fff9e6; padding: 20px; border-left: 4px solid #FFD700; border-radius: 5px; margin: 25px 0;">
                    <p style="margin: 0; color: #666; font-size: 14px;">
                        💡 <strong>Tip:</strong> Consider preparing a special birthday greeting or small celebration during your next class!
                    </p>
                </div>
                
                <p style="font-size: 14px; color: #999; margin-top: 30px; padding-top: 20px; border-top: 2px solid #f0f0f0;">
                    Automated reminder from Ecclesia Church Management System<br>
                    {settings.church_name or 'Your Church'}
                </p>
            </div>
        </div>
        """
        
        try:
            frappe.sendmail(
                recipients=[class_doc.teacher_email],
                subject=subject,
                message=message,
                delayed=False
            )
            sent_count += 1
        except Exception as e:
            frappe.log_error(f"Birthday reminder failed for {class_doc.teacher_email}: {str(e)}")
    
    return {
        'sent_count': sent_count,
        'message': f'Sent {sent_count} birthday reminder emails'
    }


@frappe.whitelist()
def process_all_promotions(filters=None):
    """Process promotions for all eligible children"""
    filters = frappe._dict(filters) if isinstance(filters, dict) else frappe._dict()
    conditions = get_conditions(filters)
    
    # Get all classes with promotion settings
    classes = frappe.db.sql(f"""
        SELECT 
            name,
            class_name,
            next_class_group,
            promotion_age
        FROM `tabChildren Class`
        WHERE next_class_group IS NOT NULL
            AND promotion_age IS NOT NULL
            {conditions}
    """, filters, as_dict=1)
    
    total_promoted = 0
    classes_processed = 0
    
    for class_info in classes:
        doc = frappe.get_doc("Children Class", class_info.name)
        next_class = frappe.get_doc("Children Class", class_info.next_class_group)
        
        promoted_in_class = 0
        today = getdate(nowdate())
        
        # Find eligible children
        members_to_remove = []
        for idx, member in enumerate(doc.children_class_member):
            if not member.date_of_birth or not member.age:
                continue
            
            if member.age >= class_info.promotion_age:
                # Add to new class
                next_class.append('children_class_member', {
                    'child_id': member.child_id,
                    'full_name': member.full_name,
                    'date_of_birth': member.date_of_birth,
                    'age': member.age,
                    'gender': member.gender,
                    'phone_no': member.phone_no,
                    'email': member.email,
                    'date_of_joining': nowdate(),
                    'date_of_promotion': nowdate()
                })
                
                # Mark for removal
                members_to_remove.append(member)
                promoted_in_class += 1
        
        # Remove from current class
        for member in members_to_remove:
            doc.remove(member)
        
        if promoted_in_class > 0:
            doc.save(ignore_permissions=True)
            next_class.save(ignore_permissions=True)
            classes_processed += 1
            total_promoted += promoted_in_class
    
    frappe.db.commit()
    
    return {
        'total_promoted': total_promoted,
        'classes_processed': classes_processed
    }