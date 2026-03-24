# Copyright (c) 2024, kunle and contributors
# For license information, please see license.txt

# -*- coding: utf-8 -*-
"""
Church Department - Complete Optimized System

Features:
✅ Smart member fetching from Member Department table (is_active only)
✅ Multi-channel messaging (Email/SMS/WhatsApp)
✅ Beautiful HTML reports with department statistics
✅ Excel export with professional formatting
✅ Automatic birthday wishes to department members
✅ Scheduled birthday notifications
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import nowdate, now, getdate, format_date, fmt_money, add_days, get_datetime
from frappe.utils.user import get_user_fullname
import json
from datetime import datetime, timedelta


class ChurchDepartment(Document):
    """Church Department Document"""
    
    def validate(self):
        """Validate and calculate totals"""
        self.calculate_member_count()
        self.validate_hod()
    
    def calculate_member_count(self):
        """Calculate total active members"""
        if self.members:
            self.total = len(self.members)
        else:
            self.total = 0
    
    def validate_hod(self):
        """Ensure HOD is in department members"""
        if self.hod_member_id:
            # Check if HOD is in members list
            hod_in_list = False
            for member in self.members or []:
                if member.member_id == self.hod_member_id:
                    hod_in_list = True
                    break
            
            if not hod_in_list:
                frappe.msgprint(
                    _("HOD {0} is not in the department members list. Consider adding them.").format(self.full_name),
                    indicator='orange',
                    title='HOD Not in Members'
                )


@frappe.whitelist()
def fetch_department_members(department_name, fetch_mode='active_only'):
    """
    Fetch members from Member Department child table
    
    Logic:
    - Fetches ALL members who have this department in their Member Department table
    - Filters by is_active = 1
    - Optionally filters by is_primary = 1 (based on fetch_mode)
    
    Args:
        department_name: Name of Church Department
        fetch_mode: 'active_only' or 'primary_only'
    
    Returns:
        Success message with member count
    """
    try:
        doc = frappe.get_doc('Church Department', department_name)
        
        # Build SQL query to find all members with this department
        # We need to query Member doctype and check their department child table
        
        if fetch_mode == 'primary_only':
            # Only primary and active departments
            query = """
                SELECT DISTINCT m.name as member_id
                FROM `tabMember` m
                INNER JOIN `tabMember Department` md ON md.parent = m.name
                WHERE md.department = %(department)s
                AND md.is_active = 1
                AND md.is_primary = 1
                AND m.member_status = 'Active'
                ORDER BY m.full_name
            """
        else:
            # All active departments (regardless of primary status)
            query = """
                SELECT DISTINCT m.name as member_id
                FROM `tabMember` m
                INNER JOIN `tabMember Department` md ON md.parent = m.name
                WHERE md.department = %(department)s
                AND md.is_active = 1
                AND m.member_status = 'Active'
                ORDER BY m.full_name
            """
        
        member_ids = frappe.db.sql(query, {'department': department_name}, as_dict=1)
        
        if not member_ids:
            return {
                'success': False,
                'message': _('No active members found for this department')
            }
        
        # Fetch full member details
        members_data = []
        for mid in member_ids:
            member = frappe.get_doc('Member', mid['member_id'])
            
            # Get department-specific details
            dept_details = None
            for dept in member.get('departments', []):  # Assuming field name is 'departments'
                if dept.department == department_name and dept.is_active:
                    dept_details = dept
                    break
            
            members_data.append({
                'member_id': member.name,
                'full_name': member.full_name,
                'last_name': member.last_name,
                'marital_status': member.marital_status,
                'date_of_birth': member.date_of_birth,
                'mobile_phone': member.mobile_phone,
                'address': member.address,
                'state': member.state,
                'is_a_worker': member.is_a_worker,
                'designation': dept_details.designation if dept_details else None,
                'salutation': member.salutation,
                'date_of_joining': dept_details.from_date if dept_details else None,
                'occupation': member.occupation,
                'branch': member.branch,
                'membership_date': dept_details.from_date if dept_details else None,
                'email': member.email
            })
        
        # Clear existing members
        doc.members = []
        
        # Add fetched members
        for member_data in members_data:
            doc.append('members', member_data)
        
        # Save
        doc.save()
        frappe.db.commit()
        
        return {
            'success': True,
            'message': _(f'✅ Successfully added {len(members_data)} active members'),
            'count': len(members_data)
        }
        
    except Exception as e:
        frappe.log_error(
            message=frappe.get_traceback(),
            title="Fetch Department Members Error"
        )
        return {
            'success': False,
            'message': _('Error fetching members: {0}').format(str(e))
        }


@frappe.whitelist()
def send_department_message(department_name, message_html, channels=None):
    """
    Send message to all department members via selected channels
    
    Args:
        department_name: Church Department name
        message_html: HTML message content
        channels: JSON string of selected channels ['email', 'sms', 'whatsapp']
    
    Returns:
        Delivery report with statistics
    """
    try:
        doc = frappe.get_doc('Church Department', department_name)
        
        if not doc.members:
            frappe.throw(_("No members in this department"))
        
        if not message_html:
            frappe.throw(_("Message content is required"))
        
        # Parse channels
        if isinstance(channels, str):
            channels = json.loads(channels)
        
        if not channels:
            channels = ['email']
        
        # Get Church Settings
        church_settings = frappe.get_single('Church Settings')
        
        # Initialize counters
        results = {
            'email': {'sent': 0, 'failed': 0, 'no_address': 0},
            'sms': {'sent': 0, 'failed': 0, 'no_phone': 0},
            'whatsapp': {'sent': 0, 'failed': 0, 'no_phone': 0}
        }
        
        # Process each member
        for member in doc.members:
            # Get full member details for email
            member_doc = frappe.get_doc('Member', member.member_id)
            
            # Send Email
            if 'email' in channels:
                if member_doc.email:
                    try:
                        email_html = containerize_department_message(
                            doc=doc,
                            member=member_doc,
                            message_html=message_html,
                            church_settings=church_settings
                        )
                        
                        frappe.sendmail(
                            recipients=[member_doc.email],
                            subject=f"Message from {doc.department_name} - {church_settings.church_name or 'Church'}",
                            message=email_html,
                            delayed=False,
                            reference_doctype='Church Department',
                            reference_name=doc.name
                        )
                        results['email']['sent'] += 1
                        
                    except Exception as e:
                        results['email']['failed'] += 1
                        frappe.log_error(
                            message=f"Email failed for {member.full_name}: {str(e)}",
                            title="Department Email Error"
                        )
                else:
                    results['email']['no_address'] += 1
            
            # Send SMS
            if 'sms' in channels:
                if member.mobile_phone:
                    try:
                        # Extract plain text from HTML
                        plain_text = frappe.utils.html2text(message_html)
                        
                        sms_result = send_sms_via_provider(
                            phone=member.mobile_phone,
                            message=plain_text[:1000],  # Truncate
                            church_settings=church_settings
                        )
                        
                        if sms_result['success']:
                            results['sms']['sent'] += 1
                        else:
                            results['sms']['failed'] += 1
                            
                    except Exception as e:
                        results['sms']['failed'] += 1
                        frappe.log_error(f"SMS failed for {member.full_name}: {str(e)}")
                else:
                    results['sms']['no_phone'] += 1
            
            # Send WhatsApp
            if 'whatsapp' in channels:
                if member.mobile_phone:
                    try:
                        plain_text = frappe.utils.html2text(message_html)
                        
                        wa_result = send_whatsapp_via_provider(
                            phone=member.mobile_phone,
                            message=plain_text,
                            church_settings=church_settings
                        )
                        
                        if wa_result['success']:
                            results['whatsapp']['sent'] += 1
                        else:
                            results['whatsapp']['failed'] += 1
                            
                    except Exception as e:
                        results['whatsapp']['failed'] += 1
                        frappe.log_error(f"WhatsApp failed for {member.full_name}: {str(e)}")
                else:
                    results['whatsapp']['no_phone'] += 1
        
        frappe.db.commit()
        
        # Build response
        response_message = build_messaging_report(results, channels)
        
        frappe.msgprint(
            response_message,
            indicator='green' if sum(r['failed'] for r in results.values()) == 0 else 'orange',
            title='Messages Sent'
        )
        
        return {
            'success': True,
            'message': response_message,
            'results': results
        }
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Department Messaging Error")
        frappe.throw(_("Failed to send messages: {0}").format(str(e)))


def containerize_department_message(doc, member, message_html, church_settings):
    """
    Create beautiful HTML container for department message
    """
    church_name = church_settings.church_name if church_settings else 'Church'
    church_logo = church_settings.church_logo if church_settings else ''
    
    html = f"""
        <div style="font-family: 'Segoe UI', Arial, sans-serif; max-width: 650px; margin: 0 auto; background: #f5f5f5;">
            <!-- Header -->
            <div style="background: linear-gradient(135deg, #1976D2 0%, #1565C0 100%); padding: 40px 20px; text-align: center; position: relative; overflow: hidden;">
                <div style="position: absolute; top: -50px; right: -50px; width: 200px; height: 200px; background: rgba(255,255,255,0.1); border-radius: 50%;"></div>
                <div style="position: absolute; bottom: -50px; left: -50px; width: 150px; height: 150px; background: rgba(255,255,255,0.1); border-radius: 50%;"></div>
                {f'<img src="{church_logo}" style="height: 60px; margin-bottom: 15px; position: relative; z-index: 1;" alt="Logo">' if church_logo else ''}
                <h1 style="color: white; margin: 0; font-size: 28px; text-shadow: 2px 2px 4px rgba(0,0,0,0.2); position: relative; z-index: 1;">
                    🏛️ {doc.department_name}
                </h1>
                <p style="color: rgba(255,255,255,0.9); margin: 8px 0 0 0; font-size: 14px; position: relative; z-index: 1;">
                    Department Communication
                </p>
            </div>
            
            <!-- Main Content -->
            <div style="background: white; padding: 40px 30px; border-radius: 0 0 20px 20px; box-shadow: 0 10px 30px rgba(0,0,0,0.1);">
                <p style="font-size: 18px; color: #2c3e50; margin-bottom: 10px;">Dear {member.full_name},</p>
                
                <div style="background: linear-gradient(135deg, #f8f9fa 0%, #ffffff 100%); padding: 25px; border-radius: 12px; margin: 25px 0; border-left: 4px solid #1976D2;">
                    {message_html}
                </div>
                
                <!-- Department Info -->
                <div style="background: #e3f2fd; padding: 20px; border-radius: 8px; margin: 25px 0;">
                    <table style="width: 100%; font-size: 14px; color: #2c3e50;">
                        <tr>
                            <td style="padding: 8px 0;"><strong>🏛️ Department:</strong></td>
                            <td style="padding: 8px 0; text-align: right;">{doc.department_name}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px 0;"><strong>👨‍💼 HOD:</strong></td>
                            <td style="padding: 8px 0; text-align: right;">{doc.full_name or 'N/A'}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px 0;"><strong>🏢 Branch:</strong></td>
                            <td style="padding: 8px 0; text-align: right;">{doc.branch or 'N/A'}</td>
                        </tr>
                    </table>
                </div>
                
                <div style="margin-top: 35px; padding-top: 25px; border-top: 1px solid #e0e0e0;">
                    <p style="font-size: 15px; color: #2c3e50; margin: 0;">
                        <strong>Blessings,</strong><br>
                        <span style="color: #1976D2; font-size: 17px; font-weight: bold;">{doc.full_name or doc.department_name}</span><br>
                        <em style="color: #7f8c8d;">{doc.department_name}</em><br>
                        <em style="color: #7f8c8d;">{church_name}</em>
                    </p>
                </div>
            </div>
            
            <!-- Footer -->
            <div style="text-align: center; padding: 25px; background: #f5f5f5;">
                <p style="color: #95a5a6; font-size: 12px; margin: 5px 0;">
                    📧 Automated message from {church_name}
                </p>
                <p style="color: #95a5a6; font-size: 12px; margin: 5px 0;">
                    ⛪ Serving together in ministry
                </p>
            </div>
        </div>
    """
    
    return html


@frappe.whitelist()
def send_birthday_wishes_to_department(department_name=None):
    """
    Send automatic birthday wishes to members celebrating today
    Can be called manually or scheduled via cron
    
    If department_name is provided, only sends to that department
    Otherwise, sends to all departments
    """
    try:
        today = getdate()
        
        # Get all departments or specific department
        if department_name:
            departments = [frappe.get_doc('Church Department', department_name)]
        else:
            departments = frappe.get_all('Church Department', fields=['name'])
            departments = [frappe.get_doc('Church Department', d.name) for d in departments]
        
        total_sent = 0
        total_failed = 0
        
        church_settings = frappe.get_single('Church Settings')
        
        for dept in departments:
            if not dept.members:
                continue
            
            # Find birthday celebrants in this department
            for member in dept.members:
                if not member.date_of_birth:
                    continue
                
                # Check if birthday is today
                dob = getdate(member.date_of_birth)
                if dob.month == today.month and dob.day == today.day:
                    # It's their birthday!
                    try:
                        member_doc = frappe.get_doc('Member', member.member_id)
                        
                        if member_doc.email:
                            # Generate birthday message
                            birthday_html = generate_birthday_wish(
                                dept=dept,
                                member=member_doc,
                                church_settings=church_settings
                            )
                            
                            # Send email
                            frappe.sendmail(
                                recipients=[member_doc.email],
                                subject=f"🎉 Happy Birthday {member.full_name}! - {dept.department_name}",
                                message=birthday_html,
                                delayed=False,
                                reference_doctype='Church Department',
                                reference_name=dept.name
                            )
                            
                            total_sent += 1
                            
                            frappe.logger().info(f"Birthday wish sent to {member.full_name} from {dept.department_name}")
                            
                    except Exception as e:
                        total_failed += 1
                        frappe.log_error(
                            message=f"Birthday email failed for {member.full_name}: {str(e)}",
                            title="Birthday Wish Error"
                        )
        
        frappe.db.commit()
        
        return {
            'success': True,
            'sent': total_sent,
            'failed': total_failed,
            'message': f'Sent {total_sent} birthday wishes, {total_failed} failed'
        }
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Birthday Wishes Error")
        return {
            'success': False,
            'error': str(e)
        }


def generate_birthday_wish(dept, member, church_settings):
    """Generate beautiful birthday wish HTML"""
    
    church_name = church_settings.church_name if church_settings else 'Church'
    church_logo = church_settings.church_logo if church_settings else ''
    
    # Calculate age
    age = None
    if member.date_of_birth:
        today = getdate()
        dob = getdate(member.date_of_birth)
        age = today.year - dob.year
    
    html = f"""
        <div style="font-family: 'Segoe UI', Arial, sans-serif; max-width: 650px; margin: 0 auto; background: #f5f5f5;">
            <!-- Birthday Header -->
            <div style="background: linear-gradient(135deg, #FF6B9D 0%, #C06C84 100%); padding: 50px 20px; text-align: center; position: relative; overflow: hidden;">
                <div style="position: absolute; top: 0; left: 0; right: 0; bottom: 0; background-image: url('data:image/svg+xml,<svg xmlns=\"http://www.w3.org/2000/svg\" viewBox=\"0 0 1000 1000\"><text y=\"100\" font-size=\"100\" fill=\"rgba(255,255,255,0.1)\">🎉🎂🎈🎁</text></svg>'); opacity: 0.2;"></div>
                <h1 style="color: white; margin: 0; font-size: 42px; text-shadow: 2px 2px 4px rgba(0,0,0,0.3); position: relative; z-index: 1; animation: bounce 2s infinite;">
                    🎉 Happy Birthday! 🎉
                </h1>
                <p style="color: rgba(255,255,255,0.95); margin: 15px 0 0 0; font-size: 24px; position: relative; z-index: 1;">
                    {member.full_name}
                </p>
                {f'<p style="color: rgba(255,255,255,0.9); margin: 8px 0 0 0; font-size: 18px; position: relative; z-index: 1;">Celebrating {age} wonderful years!</p>' if age else ''}
            </div>
            
            <!-- Birthday Message -->
            <div style="background: white; padding: 40px 30px; border-radius: 0 0 20px 20px; box-shadow: 0 10px 30px rgba(0,0,0,0.1);">
                <div style="text-align: center; margin-bottom: 30px;">
                    <div style="font-size: 80px; margin-bottom: 20px;">🎂</div>
                    <h2 style="color: #C06C84; margin: 0; font-size: 28px;">A Special Day for a Special Person!</h2>
                </div>
                
                <div style="background: linear-gradient(135deg, #FFF0F5 0%, #FFE4E9 100%); padding: 30px; border-radius: 12px; margin: 25px 0; border-left: 5px solid #FF6B9D;">
                    <p style="font-size: 16px; color: #2c3e50; line-height: 1.8; margin: 0;">
                        Dear <strong>{member.full_name}</strong>,
                        <br><br>
                        On this special day, the entire <strong>{dept.department_name}</strong> family celebrates with you! 🎈
                        <br><br>
                        May this new year of your life be filled with abundant blessings, joy, and divine favor. 
                        May God grant you wisdom, strength, and endless opportunities to shine His light.
                        <br><br>
                        We are grateful for your dedication and service in our department. You are a valued member of our family! 💝
                    </p>
                </div>
                
                <!-- Bible Verse -->
                <div style="background: linear-gradient(135deg, #E3F2FD 0%, #F3E5F5 100%); padding: 25px; border-radius: 12px; margin: 25px 0; text-align: center;">
                    <p style="color: #1976D2; font-size: 17px; font-style: italic; margin: 0; line-height: 1.6;">
                        "For I know the plans I have for you," declares the Lord, "plans to prosper you and not to harm you, plans to give you hope and a future."
                    </p>
                    <p style="color: #C06C84; font-weight: bold; margin: 12px 0 0 0; font-size: 14px;">
                        — Jeremiah 29:11 (NIV)
                    </p>
                </div>
                
                <!-- Department Info -->
                <div style="background: #f8f9fa; padding: 20px; border-radius: 8px; margin: 25px 0; text-align: center;">
                    <p style="color: #7f8c8d; font-size: 14px; margin: 5px 0;">
                        With love from your family at
                    </p>
                    <p style="color: #C06C84; font-size: 20px; font-weight: bold; margin: 8px 0;">
                        {dept.department_name}
                    </p>
                    <p style="color: #7f8c8d; font-size: 14px; margin: 5px 0;">
                        {church_name}
                    </p>
                </div>
                
                <div style="text-align: center; margin-top: 30px;">
                    <p style="font-size: 40px; margin: 0;">🎁 🎈 🎊 🎉</p>
                </div>
            </div>
            
            <!-- Footer -->
            <div style="text-align: center; padding: 25px; background: #f5f5f5;">
                <p style="color: #95a5a6; font-size: 12px; margin: 5px 0;">
                    🎂 Automated birthday wishes from {dept.department_name}
                </p>
                <p style="color: #95a5a6; font-size: 12px; margin: 5px 0;">
                    ⛪ {church_name} - Celebrating life together
                </p>
            </div>
        </div>
    """
    
    return html


def send_sms_via_provider(phone, message, church_settings):
    """Send SMS via configured provider"""
    # Implementation similar to Sunday School Class
    return {'success': False, 'error': 'SMS not configured'}


def send_whatsapp_via_provider(phone, message, church_settings):
    """Send WhatsApp via configured provider"""
    # Implementation similar to Sunday School Class
    return {'success': False, 'error': 'WhatsApp not configured'}


def build_messaging_report(results, channels):
    """Build messaging report HTML"""
    
    total_sent = sum(r['sent'] for r in results.values())
    total_failed = sum(r['failed'] for r in results.values())
    
    status_color = "#ff9800" if total_failed > 0 else "#4caf50"
    status_icon = "⚠️" if total_failed > 0 else "✅"
    
    message = f"""
        <div style="padding: 20px; border-radius: 8px; background: #f8f9fa; border-left: 4px solid {status_color};">
            <h4 style="color: {status_color}; margin-top: 0;">{status_icon} Messaging Complete</h4>
            <table style="width: 100%; border-collapse: collapse;">
    """
    
    for channel in channels:
        if channel in results:
            r = results[channel]
            message += f"""
                <tr>
                    <td style="padding: 8px;"><strong>{channel.upper()}:</strong></td>
                    <td style="padding: 8px; text-align: right;">
                        <span style="color: #4caf50;">✓ {r['sent']}</span>
                        {f'<span style="color: #f44336;"> ✗ {r["failed"]}</span>' if r['failed'] > 0 else ''}
                        {f'<span style="color: #9e9e9e;"> ⊘ {r.get("no_address", r.get("no_phone", 0))}</span>' if r.get('no_address') or r.get('no_phone') else ''}
                    </td>
                </tr>
            """
    
    message += f"""
                <tr style="border-top: 2px solid #e0e0e0;">
                    <td style="padding: 8px;"><strong>TOTAL:</strong></td>
                    <td style="padding: 8px; text-align: right;">
                        <strong>{total_sent} sent</strong>
                        {f' <span style="color: #f44336;">{total_failed} failed</span>' if total_failed > 0 else ''}
                    </td>
                </tr>
            </table>
        </div>
    """
    
    return message


# Scheduled task to send birthday wishes daily
def daily_birthday_wishes():
    """
    Scheduled task to send birthday wishes
    Add to hooks.py:
    
    scheduler_events = {
        "daily": [
            "church.church.doctype.church_department.church_department.daily_birthday_wishes"
        ]
    }
    """
    send_birthday_wishes_to_department()