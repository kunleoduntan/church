# -*- coding: utf-8 -*-
"""
Children Class Attendance - Complete System
Features:
- Service Instance linking for accurate timing
- Receipt creation with duplicate prevention
- Beautiful HTML reports
- Excel export with formatting
"""


import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import nowdate, now, getdate, format_date, fmt_money, get_datetime, add_days
import json


class ChildrenClassAttendance(Document):
    def validate(self):
        """Validate before saving"""
        self.calculate_totals()
        self.validate_dates()
        self.link_service_instance()
        
    def before_submit(self):
        """Before submission validations"""
        if not self.children_attendance:
            frappe.throw(_("Cannot submit without any children attendance records"))
    
    def calculate_totals(self):
        """Calculate total counts and offering amount"""
        total_male = 0
        total_female = 0
        total_offering = 0
        
        for row in self.children_attendance:
            if row.gender == "Male":
                total_male += 1
            elif row.gender == "Female":
                total_female += 1
            
            if row.amount:
                total_offering += row.amount
        
        self.total_male = total_male
        self.total_female = total_female
        self.total_count = total_male + total_female
        self.total_offering_amount = total_offering
    
    def validate_dates(self):
        """Validate service date"""
        if self.service_date and getdate(self.service_date) > getdate():
            frappe.throw(_("Service date cannot be in the future"))
    
    def link_service_instance(self):
        """Auto-link to Service Instance if available"""
        if not self.service_instance and self.service_date and self.branch:
            # Try to find matching Service Instance
            service_instance = frappe.db.get_value('Service Instance', {
                'service_date': self.service_date,
                'branch': self.branch,
                'docstatus': ['!=', 2]  # Not cancelled
            }, 'name')
            
            if service_instance:
                self.service_instance = service_instance


@frappe.whitelist()
def create_cc_attendance(ss_attendance, cs_attendance):
    """
    Create Church Attendance records linked to Service Instance
    Gets timing from Service Instance for accuracy
    """
    try:
        doc = frappe.get_doc("Children Class Attendance", ss_attendance)
        
        if not doc.children_attendance:
            frappe.throw(_("No children attendance records found"))
        
        created_count = 0
        skipped_count = 0
        error_count = 0
        error_messages = []
        
        # Get Service Instance for timing
        service_instance = None
        if doc.service_instance:
            service_instance = frappe.get_doc('Service Instance', doc.service_instance)
        
        # Process Sunday School Attendance
        if doc.mark_ss_attendance:
            # Get time from Service Instance or use manual entry
            ss_time = service_instance.actual_start_time if service_instance else doc.ss_time
            
            created, skipped, errors, err_msgs = mark_attendance(
                doc=doc,
                service_type="Sunday School",
                time_value=ss_time,
                service_instance=doc.service_instance
            )
            created_count += created
            skipped_count += skipped
            error_count += errors
            error_messages.extend(err_msgs)
        
        # Process Church Service Attendance
        if doc.mark_cs_attendance:
            # Get time from Service Instance or use manual entry
            cs_time = service_instance.actual_start_time if service_instance else doc.cs_time
            
            created, skipped, errors, err_msgs = mark_attendance(
                doc=doc,
                service_type="Church Service",
                time_value=cs_time,
                service_instance=doc.service_instance
            )
            created_count += created
            skipped_count += skipped
            error_count += errors
            error_messages.extend(err_msgs)
        
        # Check if any attendance was marked
        if not doc.mark_ss_attendance and not doc.mark_cs_attendance:
            frappe.msgprint(
                _("Please check 'Mark SS Attendance' or 'Mark CS Attendance' before processing"),
                indicator='orange',
                title='No Attendance Marked'
            )
            return {
                'success': False,
                'message': 'No attendance type selected'
            }
        
        # Commit all changes
        frappe.db.commit()
        
        # Build response message
        message = build_attendance_message(created_count, skipped_count, error_count, error_messages)
        
        frappe.msgprint(
            message,
            indicator='green' if error_count == 0 else 'orange',
            title='Attendance Processing Complete'
        )
        
        return {
            'success': True,
            'message': message,
            'created': created_count,
            'skipped': skipped_count,
            'errors': error_count
        }
        
    except Exception as e:
        frappe.log_error(
            message=frappe.get_traceback(),
            title="Children Class Attendance Creation Error"
        )
        frappe.throw(_("Failed to create attendance: {0}").format(str(e)))


def mark_attendance(doc, service_type, time_value, service_instance=None):
    """
    Create Church Attendance records for children
    Links to Service Instance when available
    """
    created_count = 0
    skipped_count = 0
    error_count = 0
    error_messages = []
    
    # Get Programme link for service_type
    programme = get_or_create_programme(service_type)
    
    for row in doc.children_attendance:
        try:
            # Validate member exists
            if not frappe.db.exists('Member', row.child_id):
                error_messages.append(f"{row.full_name}: Member ID {row.child_id} not found")
                error_count += 1
                continue
            
            # Check if attendance already exists
            existing = frappe.db.exists('Church Attendance', {
                'member_id': row.child_id,
                'service_date': doc.service_date,
                'service_type': programme,
            })
            
            if existing:
                skipped_count += 1
                frappe.logger().info(
                    f"Attendance already exists for {row.full_name} on {doc.service_date} - {service_type}"
                )
                continue
            
            # Get available fields in Church Attendance DocType
            meta = frappe.get_meta('Church Attendance')
            available_fields = [df.fieldname for df in meta.fields]
            
            # Build attendance data with only existing fields
            attendance_data = {
                'doctype': 'Church Attendance',
                'member_id': row.child_id,
                'full_name': row.full_name,
                'service_date': doc.service_date,
                'time_in': time_value or now(),
                'service_type': programme,
                'branch': doc.branch,
                'present': 1,
                'notes': f'Auto-created from {doc.doctype} {doc.name}'
            }
            
            # Add Service Instance link if available
            if 'service_instance' in available_fields and service_instance:
                attendance_data['service_instance'] = service_instance
            
            # Add optional fields only if they exist in the DocType
            if 'email' in available_fields:
                attendance_data['email'] = row.email or ''
            
            if 'phone' in available_fields:
                attendance_data['phone'] = row.phone_no or ''
            
            if 'age' in available_fields:
                attendance_data['age'] = row.age or 0
            
            if 'gender' in available_fields:
                attendance_data['gender'] = row.gender
            
            if 'sunday_school_class' in available_fields and service_type == "Sunday School":
                attendance_data['sunday_school_class'] = doc.class_name
            
            if 'sunday_school_category' in available_fields and service_type == "Sunday School":
                attendance_data['sunday_school_category'] = doc.class_group
            
            if 'marked_by' in available_fields:
                attendance_data['marked_by'] = frappe.session.user
            
            if 'marked_at' in available_fields:
                attendance_data['marked_at'] = now()
            
            # Create Church Attendance record
            attendance = frappe.get_doc(attendance_data)
            attendance.insert(ignore_permissions=True)
            created_count += 1
            
            frappe.logger().info(
                f"Church Attendance created: {row.full_name} - {service_type} - {doc.service_date}"
            )
            
        except frappe.exceptions.ValidationError as ve:
            error_count += 1
            error_messages.append(f"{row.full_name}: {str(ve)}")
            frappe.log_error(
                message=f"Validation error for {row.full_name}: {str(ve)}",
                title=f"Church Attendance Validation Error - {service_type}"
            )
            
        except Exception as e:
            error_count += 1
            error_messages.append(f"{row.full_name}: {str(e)}")
            frappe.log_error(
                message=f"Failed to create attendance for {row.full_name}: {str(e)}\n{frappe.get_traceback()}",
                title=f"Church Attendance Creation Error - {service_type}"
            )
    
    return created_count, skipped_count, error_count, error_messages


def get_or_create_programme(service_type):
    """Get or create Programme record for service type"""
    if not frappe.db.exists('Programme', service_type):
        try:
            programme = frappe.get_doc({
                'doctype': 'Programme',
                'programme_name': service_type,
                'programme_type': 'Regular Service',
                'is_active': 1
            })
            programme.insert(ignore_permissions=True)
            frappe.db.commit()
            frappe.logger().info(f"Created new Programme: {service_type}")
        except Exception as e:
            frappe.log_error(
                message=f"Failed to create Programme {service_type}: {str(e)}",
                title="Programme Creation Error"
            )
            return service_type
    
    return service_type


def build_attendance_message(created, skipped, errors, error_messages):
    """Build HTML message for attendance processing results"""
    
    if errors > 0:
        status_color = "#ff9800"
        status_icon = "⚠️"
        status_text = "Completed with Errors"
    else:
        status_color = "#4caf50"
        status_icon = "✅"
        status_text = "Successfully Completed"
    
    message = f"""
        <div style="padding: 20px; border-radius: 8px; background: #f8f9fa; border-left: 4px solid {status_color};">
            <h4 style="color: {status_color}; margin-top: 0; font-size: 18px;">
                {status_icon} Attendance Processing {status_text}
            </h4>
            <div style="background: white; padding: 15px; border-radius: 6px; margin: 15px 0;">
                <table style="width: 100%; border-collapse: collapse;">
                    <tr>
                        <td style="padding: 8px; border-bottom: 1px solid #e0e0e0;">
                            <strong>✓ Created:</strong>
                        </td>
                        <td style="padding: 8px; border-bottom: 1px solid #e0e0e0; text-align: right;">
                            <span style="color: #4caf50; font-weight: bold; font-size: 16px;">{created}</span>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; border-bottom: 1px solid #e0e0e0;">
                            <strong>⊘ Skipped (Already Exist):</strong>
                        </td>
                        <td style="padding: 8px; border-bottom: 1px solid #e0e0e0; text-align: right;">
                            <span style="color: #2196f3; font-weight: bold; font-size: 16px;">{skipped}</span>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 8px;">
                            <strong>✗ Errors:</strong>
                        </td>
                        <td style="padding: 8px; text-align: right;">
                            <span style="color: #f44336; font-weight: bold; font-size: 16px;">{errors}</span>
                        </td>
                    </tr>
                </table>
            </div>
    """
    
    if errors > 0 and error_messages:
        message += """
            <div style="background: #fff3cd; padding: 15px; border-radius: 6px; margin-top: 15px; border-left: 3px solid #ff9800;">
                <h5 style="color: #856404; margin-top: 0;">Error Details:</h5>
                <ul style="margin: 5px 0; padding-left: 20px; color: #856404; font-size: 13px;">
        """
        for error_msg in error_messages[:10]:
            message += f"<li>{error_msg}</li>"
        
        if len(error_messages) > 10:
            message += f"<li><em>...and {len(error_messages) - 10} more errors</em></li>"
        
        message += """
                </ul>
                <p style="margin: 10px 0 0 0; font-size: 12px; color: #856404;">
                    <em>Check Error Log for complete details</em>
                </p>
            </div>
        """
    
    message += "</div>"
    
    return message


@frappe.whitelist()
def create_receipts(sso_receipt):
    """
    Create offering receipts for children's class offerings
    Prevents duplicate receipt creation
    """
    try:
        doc = frappe.get_doc("Children Class Attendance", sso_receipt)
        
        if not doc.create_receipts:
            frappe.throw(_("Please check 'Create Receipts' option first"))
        
        if not doc.children_attendance:
            frappe.throw(_("No children attendance records found"))
        
        # Check if receipts already created for this document
        existing_receipts = frappe.db.count('Receipts', {
            'source': doc.name,
            'docstatus': ['!=', 2]
        })
        
        if existing_receipts > 0:
            frappe.msgprint(
                _(f"Receipts already created for this document. Found {existing_receipts} existing receipt(s)."),
                indicator='orange',
                title='Receipts Already Exist'
            )
            return {
                'success': False,
                'message': f'Found {existing_receipts} existing receipts. Delete them first if you want to recreate.'
            }
        
        created_count = 0
        skipped_count = 0
        error_count = 0
        total_amount = 0
        receipt_numbers = []
        
        for row in doc.children_attendance:
            # Skip if no offering amount
            if not row.amount or row.amount <= 0:
                continue
            
            try:
                # Create Receipt document (not Offering Receipt)
                receipt = frappe.get_doc({
                    'doctype': 'Receipts',
                    'transaction_date': doc.service_date,
                    'transaction_type': 'Sunday School Offering',
                    'member_id': row.child_id,
                    'member_full_name': row.full_name,
                    'branch': doc.branch,
                    'receipt_currency': frappe.db.get_single_value('Church Settings', 'default_currency') or 'NGN',
                    'amount_paid': doc.offering_amount,
                    'mode_of_payment': 'Cash',
                    'transaction_purposes': f'Children Class Offering - {doc.class_name}',
                    'reference_no': f'CCA-{doc.name}-{row.idx}',
                    'source': doc.name,  # Link back to Children Class Attendance
                    'company': frappe.db.get_single_value('Global Defaults', 'default_company'),
                    'remittance_bank': frappe.db.get_value('Bank Account', {'is_default': 1}, 'name'),
                })
                
                receipt.insert(ignore_permissions=True)
                created_count += 1
                total_amount += row.amount
                receipt_numbers.append(receipt.name)
                
            except Exception as e:
                error_count += 1
                frappe.log_error(
                    message=f"Failed to create receipt for {row.full_name}: {str(e)}\n{frappe.get_traceback()}",
                    title="Children Receipt Creation Error"
                )
        
        frappe.db.commit()
        
        # Get currency
        currency = frappe.db.get_single_value('Church Settings', 'default_currency') or 'NGN'
        formatted_total = fmt_money(total_amount, currency=currency)
        
        message = f"""
            <div style="padding: 20px; border-radius: 8px; background: #e3f2fd; border-left: 4px solid #2196f3;">
                <h4 style="color: #1976d2; margin-top: 0; font-size: 18px;">
                    💰 Offering Receipts Created
                </h4>
                <div style="background: white; padding: 15px; border-radius: 6px; margin: 15px 0;">
                    <table style="width: 100%; border-collapse: collapse;">
                        <tr>
                            <td style="padding: 8px; border-bottom: 1px solid #e0e0e0;">
                                <strong>Receipts Created:</strong>
                            </td>
                            <td style="padding: 8px; border-bottom: 1px solid #e0e0e0; text-align: right;">
                                <span style="color: #4caf50; font-weight: bold;">{created_count}</span>
                            </td>
                        </tr>
                        {f'<tr><td style="padding: 8px; border-bottom: 1px solid #e0e0e0;"><strong>Errors:</strong></td><td style="padding: 8px; border-bottom: 1px solid #e0e0e0; text-align: right;"><span style="color: #f44336; font-weight: bold;">{error_count}</span></td></tr>' if error_count > 0 else ''}
                        <tr>
                            <td style="padding: 8px;">
                                <strong>Total Amount:</strong>
                            </td>
                            <td style="padding: 8px; text-align: right;">
                                <span style="color: #1976d2; font-weight: bold; font-size: 16px;">
                                    {formatted_total}
                                </span>
                            </td>
                        </tr>
                    </table>
                </div>
                {f'<div style="background: #fff8e1; padding: 10px; border-radius: 6px; margin-top: 10px;"><p style="margin: 0; font-size: 13px; color: #856404;"><strong>Receipt Numbers:</strong> {", ".join(receipt_numbers[:5])}{" ..." if len(receipt_numbers) > 5 else ""}</p></div>' if receipt_numbers else ''}
            </div>
        """
        
        frappe.msgprint(
            message,
            indicator='green',
            title='Offering Receipts Created'
        )
        
        return {
            'success': True,
            'message': message,
            'created': created_count,
            'errors': error_count,
            'total_amount': total_amount,
            'receipt_numbers': receipt_numbers
        }
        
    except Exception as e:
        frappe.log_error(
            message=frappe.get_traceback(),
            title="Children Receipt Creation Error"
        )
        frappe.throw(_("Failed to create receipts: {0}").format(str(e)))


@frappe.whitelist()
def send_mail_from_Children_class(syou_receipt):
    """Send email notifications to parents"""
    try:
        doc = frappe.get_doc("Children Class Attendance", syou_receipt)
        
        if not doc.children_attendance:
            frappe.throw(_("No children attendance records found"))
        
        sent_count = 0
        failed_count = 0
        no_email_count = 0
        
        for row in doc.children_attendance:
            if not row.email:
                no_email_count += 1
                continue
            
            try:
                subject = f"Attendance Confirmation - {row.full_name} - {format_date(doc.service_date)}"
                message = generate_attendance_email(doc, row)
                
                frappe.sendmail(
                    recipients=[row.email],
                    subject=subject,
                    message=message,
                    delayed=False,
                    reference_doctype='Children Class Attendance',
                    reference_name=doc.name
                )
                
                sent_count += 1
                
            except Exception as e:
                failed_count += 1
                frappe.log_error(
                    message=f"Failed to send email to {row.email}: {str(e)}\n{frappe.get_traceback()}",
                    title="Children Class Email Error"
                )
        
        frappe.db.commit()
        
        message = f"""
            <div style="padding: 15px; border-radius: 8px; background: #e8f5e9; border-left: 4px solid #4caf50;">
                <h4 style="color: #2e7d32; margin-top: 0;">📧 Email Notification Results</h4>
                <ul style="margin: 10px 0; padding-left: 20px;">
                    <li>✅ <strong>{sent_count}</strong> emails sent successfully</li>
                    <li>⊘ <strong>{no_email_count}</strong> records without email</li>
                    {f'<li style="color: #d32f2f;">✗ <strong>{failed_count}</strong> failed to send</li>' if failed_count > 0 else ''}
                </ul>
            </div>
        """
        
        frappe.msgprint(
            message,
            indicator='green' if failed_count == 0 else 'orange',
            title='Email Notifications Sent'
        )
        
        return {
            'success': True,
            'message': message,
            'sent': sent_count,
            'no_email': no_email_count,
            'failed': failed_count
        }
        
    except Exception as e:
        frappe.log_error(
            message=frappe.get_traceback(),
            title="Children Class Email Error"
        )
        frappe.throw(_("Failed to send emails: {0}").format(str(e)))


def generate_attendance_email(doc, row):
    """Generate beautiful HTML email for attendance confirmation"""
    church_settings = frappe.get_single('Church Settings')
    church_name = church_settings.church_name if church_settings else 'Church'
    
    offering_display = ""
    if row.amount:
        currency = frappe.db.get_single_value('Church Settings', 'default_currency') or 'NGN'
        formatted_amount = fmt_money(row.amount, currency=currency)
        offering_display = f'''
        <div style="background: #fff8e1; padding: 15px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #ffc107;">
            <h4 style="color: #f57c00; margin-top: 0; margin-bottom: 10px;">💰 Offering Contribution</h4>
            <p style="margin: 0; color: #8b6914; font-size: 16px;">
                <strong>{formatted_amount}</strong>
            </p>
            <p style="margin: 10px 0 0 0; color: #8b6914; font-size: 13px; font-style: italic;">
                Thank you for your child's generous contribution!
            </p>
        </div>
        '''
    
    message = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; background-color: #f8f9fa; padding: 20px;">
            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; border-radius: 10px 10px 0 0; text-align: center;">
                <h2 style="color: white; margin: 0; font-size: 24px;">⛪ Children's Class Attendance</h2>
            </div>
            
            <div style="background: white; padding: 30px; border-radius: 0 0 10px 10px;">
                <p style="font-size: 16px; color: #2c3e50;">Dear Parent/Guardian,</p>
                
                <p style="font-size: 15px; color: #34495e; line-height: 1.6;">
                    This is to confirm that <strong style="color: #667eea;">{row.full_name}</strong> attended 
                    <strong>{doc.class_name}</strong> on <strong>{format_date(doc.service_date)}</strong>.
                </p>
                
                <div style="background: #e8f4fd; padding: 20px; border-radius: 8px; margin: 25px 0; border-left: 4px solid #2196f3;">
                    <h3 style="color: #1976d2; margin-top: 0; margin-bottom: 15px;">📋 Class Details</h3>
                    <table style="width: 100%; font-size: 14px; color: #2c3e50;">
                        <tr>
                            <td style="padding: 6px 0;"><strong>Class:</strong></td>
                            <td style="padding: 6px 0;">{doc.class_name}</td>
                        </tr>
                        <tr>
                            <td style="padding: 6px 0;"><strong>Group:</strong></td>
                            <td style="padding: 6px 0;">{doc.class_group or 'N/A'}</td>
                        </tr>
                        <tr>
                            <td style="padding: 6px 0;"><strong>Teacher:</strong></td>
                            <td style="padding: 6px 0;">{doc.teacher_name or 'N/A'}</td>
                        </tr>
                        <tr>
                            <td style="padding: 6px 0;"><strong>Date:</strong></td>
                            <td style="padding: 6px 0;">{format_date(doc.service_date)}</td>
                        </tr>
                    </table>
                </div>
                
                {offering_display}
                
                <div style="background: #e8f8f5; padding: 15px; border-radius: 8px; margin: 20px 0; text-align: center;">
                    <p style="margin: 0; color: #16a085; font-size: 14px; font-style: italic;">
                        "Train up a child in the way he should go; even when he is old he will not depart from it."
                        <br><strong>- Proverbs 22:6</strong>
                    </p>
                </div>
                
                <p style="font-size: 14px; color: #34495e; line-height: 1.6;">
                    Thank you for your continued support and for partnering with us in raising godly children!
                </p>
                
                <p style="font-size: 14px; color: #34495e; margin-top: 25px;">
                    Blessings,<br>
                    <strong>{doc.branch} Children's Ministry</strong><br>
                    <em>{church_name}</em>
                </p>
            </div>
            
            <div style="text-align: center; padding: 20px; color: #7f8c8d; font-size: 12px;">
                <p style="margin: 5px 0;">This is an automated notification from {church_name}</p>
                <p style="margin: 5px 0;">Please do not reply to this email</p>
            </div>
        </div>
    """
    
    return message


@frappe.whitelist()
def get_class_members_data(class_name):
    """Fetch class members for the selected children class"""
    try:
        if not class_name:
            frappe.throw(_("Please select a Children Class first"))
        
        children_class = frappe.get_doc('Children Class', class_name)
        
        if not children_class.children_class_member:
            return {
                'success': False,
                'message': _('No members found in the selected class')
            }
        
        members = []
        for member in children_class.children_class_member:
            members.append({
                'child_id': member.child_id,
                'full_name': member.full_name,
                'email': member.email,
                'phone_no': member.phone_no,
                'teacher_name': member.teacher_name,
                'gender': member.gender,
                'age': member.age
            })
        
        return {
            'success': True,
            'members': members,
            'message': _('{0} members found').format(len(members))
        }
        
    except Exception as e:
        frappe.log_error(
            message=frappe.get_traceback(),
            title="Get Class Members Error"
        )
        return {
            'success': False,
            'message': _('Error fetching class members: {0}').format(str(e))
        }