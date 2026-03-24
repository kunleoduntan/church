# Copyright (c) 2026, kunle and contributors
# For license information, please see license.txt

# -*- coding: utf-8 -*-
# Copyright (c) 2025, Ecclesia and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe.utils import getdate, get_weekday, nowdate, now_datetime, add_days, formatdate
from frappe import _

class Visitation(Document):
    def before_insert(self):
        """Set defaults before insert"""
        if not self.assigned_by:
            self.assigned_by = frappe.session.user
        
        # Set branch from team leader if not set
        if self.team_leader and not self.branch:
            team_leader_doc = frappe.get_doc("Member", self.team_leader)
            self.branch = team_leader_doc.branch
    
    def validate(self):
        """Validate visitation data"""
        self.validate_team_leader()
        self.validate_dates()
        self.set_day_from_date()
        self.fetch_member_details()
        self.validate_team_members()
    
    def validate_team_leader(self):
        """Ensure team leader is qualified"""
        if not self.team_leader:
            frappe.throw(_("Team Leader is required"))
        
        team_leader = frappe.get_doc("Member", self.team_leader)
        
        # Check if team leader is authorized
        if not (team_leader.is_counsellor or team_leader.is_follow_up_cordinator):
            frappe.throw(_(f"{team_leader.full_name} is not authorized as a Counsellor or Follow-up Coordinator"))
    
    def validate_dates(self):
        """Validate visitation dates"""
        if self.date_of_visitation and getdate(self.date_of_visitation) < getdate(nowdate()):
            frappe.msgprint(_("Visitation date is in the past"), alert=True)
    
    def set_day_from_date(self):
        """Auto-set day name from date"""
        if self.date_of_visitation:
            self.day = get_weekday(self.date_of_visitation)
    
    def fetch_member_details(self):
        """Fetch member contact details if not already set"""
        if self.member_id and not self.email:
            member = frappe.get_doc("Member", self.member_id)
            
            if not self.email:
                self.email = member.email
            if not self.phone:
                self.phone = member.mobile_phone
            if not self.alternative_phone:
                self.alternative_phone = member.phone
            if not self.address:
                self.address = member.address
            if not self.location:
                self.location = member.city or member.state
    
    def validate_team_members(self):
        """Ensure no duplicate team members"""
        if self.visitation_team:
            members = [row.member_id for row in self.visitation_team if row.member_id]
            if len(members) != len(set(members)):
                frappe.throw(_("Duplicate team members found"))
    
    def on_submit(self):
        """Actions on submit"""
        self.status = "Completed"
        self.completed_date = now_datetime()
        
        # Create follow-up visitation if required
        if self.follow_up_required and self.follow_up_notes:
            self.create_follow_up_visitation()
    
    def on_cancel(self):
        """Actions on cancel"""
        self.status = "Cancelled"
    
    def create_follow_up_visitation(self):
        """Create follow-up visitation automatically"""
        try:
            follow_up = frappe.get_doc({
                "doctype": "Visitation",
                "type": "Follow-up",
                "member_id": self.member_id,
                "visitee_full_name": self.visitee_full_name,
                "branch": self.branch,
                "team_leader": self.team_leader,
                "date_of_visitation": add_days(self.date_of_visitation, 7),
                "location": self.location,
                "address": self.address,
                "email": self.email,
                "phone": self.phone,
                "visitation_report": f"Follow-up to visitation: {self.name}<br><br>{self.follow_up_notes}",
                "assigned_by": frappe.session.user
            })
            
            follow_up.insert(ignore_permissions=True)
            
            frappe.msgprint(
                _("Follow-up visitation {0} created successfully").format(
                    f"<a href='/app/visitation/{follow_up.name}'>{follow_up.name}</a>"
                ),
                alert=True,
                indicator="green"
            )
            
        except Exception as e:
            frappe.log_error(frappe.get_traceback(), "Create Follow-up Visitation Error")
            frappe.msgprint(_("Error creating follow-up visitation: {0}").format(str(e)), alert=True)


@frappe.whitelist()
def create_weekly_visitations():
    """
    Scheduled function to create weekly visitations for counsellors and coordinators
    Called via hooks.py scheduler
    """
    try:
        # Check if feature is enabled
        settings = frappe.get_single("Church Settings")
        if not settings.create_weekly_visitation_sheet:
            return
        
        # Get all eligible members (counsellors and follow-up coordinators)
        eligible_members = frappe.get_all(
            "Member",
            filters={
                "status": "Active",
                "or_filters": [
                    {"is_counsellor": 1},
                    {"is_follow_up_cordinator": 1}
                ]
            },
            fields=["name", "full_name", "branch", "email", "is_counsellor", "is_follow_up_cordinator"]
        )
        
        created_count = 0
        next_week_date = add_days(nowdate(), 7)
        
        for member in eligible_members:
            # Get members to visit from this branch
            members_to_visit = get_members_for_visitation(member.branch, member.name)
            
            if not members_to_visit:
                continue
            
            for visitee in members_to_visit:
                # Check if visitation already exists for this week
                existing = frappe.db.exists("Visitation", {
                    "member_id": visitee.name,
                    "team_leader": member.name,
                    "date_of_visitation": ["between", [nowdate(), next_week_date]],
                    "docstatus": ["<", 2]
                })
                
                if existing:
                    continue
                
                # Create visitation
                visitation = frappe.get_doc({
                    "doctype": "Visitation",
                    "type": "Regular Visitation",
                    "branch": member.branch,
                    "member_id": visitee.name,
                    "visitee_full_name": visitee.full_name,
                    "team_leader": member.name,
                    "date_of_visitation": next_week_date,
                    "status": "Assigned",
                    "assigned_by": "Administrator"
                })
                
                visitation.insert(ignore_permissions=True)
                
                # Send notification email
                send_visitation_assignment_email(visitation, member)
                
                created_count += 1
        
        frappe.db.commit()
        
        frappe.logger().info(f"Created {created_count} weekly visitations")
        
        return {
            "success": True,
            "created_count": created_count,
            "message": f"Successfully created {created_count} visitations"
        }
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Weekly Visitation Creation Error")
        return {
            "success": False,
            "error": str(e)
        }


def get_members_for_visitation(branch, team_leader):
    """
    Get list of members who need visitation
    Logic: Members who haven't been visited in last 30 days
    """
    # Get members from branch excluding the team leader
    members = frappe.get_all(
        "Member",
        filters={
            "branch": branch,
            "status": "Active",
            "name": ["!=", team_leader]
        },
        fields=["name", "full_name", "email", "mobile_phone"]
    )
    
    # Filter members who haven't been visited recently
    members_needing_visit = []
    thirty_days_ago = add_days(nowdate(), -30)
    
    for member in members:
        last_visit = frappe.db.get_value(
            "Visitation",
            {
                "member_id": member.name,
                "docstatus": 1,
                "date_of_visitation": [">=", thirty_days_ago]
            },
            "date_of_visitation",
            order_by="date_of_visitation desc"
        )
        
        if not last_visit:
            members_needing_visit.append(member)
    
    # Limit to 5 members per week per team leader
    return members_needing_visit[:5]


def send_visitation_assignment_email(visitation, team_leader):
    """Send beautiful email notification for visitation assignment"""
    try:
        if not team_leader.email:
            return
        
        # Get church settings for branding
        settings = frappe.get_single("Church Settings")
        church_name = settings.church_name or "Our Church"
        
        # Create beautiful email message
        message = get_visitation_assignment_email_template(visitation, team_leader, church_name)
        
        frappe.sendmail(
            recipients=[team_leader.email],
            subject=f"New Visitation Assignment - {visitation.visitee_full_name}",
            message=message,
            header=[f"Visitation Assignment", "blue"],
            delayed=False
        )
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Visitation Email Error")


def get_visitation_assignment_email_template(visitation, team_leader, church_name):
    """Beautiful HTML email template for visitation assignment"""
    
    # Build address section if exists
    address_section = ""
    if visitation.address:
        address_section = f"""
                <div style="margin-top: 20px; padding-top: 20px; border-top: 1px solid #bdc3c7;">
                    <p style="color: #7f8c8d; margin: 0 0 8px 0; font-size: 14px; font-weight: 600;">📍 Address:</p>
                    <p style="color: #2c3e50; margin: 0; font-size: 15px; line-height: 1.5;">{visitation.address}</p>
                </div>
        """
    
    # Build contact section if exists
    contact_section = ""
    if visitation.phone:
        contact_section = f"""
                <div style="margin-top: 15px; padding-top: 15px; border-top: 1px solid #bdc3c7;">
                    <p style="color: #7f8c8d; margin: 0 0 8px 0; font-size: 14px; font-weight: 600;">📞 Contact:</p>
                    <p style="color: #2c3e50; margin: 0; font-size: 15px;">{visitation.phone}</p>
                </div>
        """
    
    # Format the date
    formatted_date = formatdate(visitation.date_of_visitation, "dd MMM yyyy")
    
    # Build the complete email
    email_html = f"""
    <div style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; max-width: 650px; margin: 0 auto; background: #f8f9fa; padding: 0;">
        
        <!-- Header -->
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 40px 30px; text-align: center; border-radius: 10px 10px 0 0;">
            <h1 style="color: #ffffff; margin: 0; font-size: 28px; font-weight: 700;">
                ⛪ {church_name}
            </h1>
            <p style="color: #e8f4f8; margin: 10px 0 0 0; font-size: 16px;">
                Visitation Ministry
            </p>
        </div>
        
        <!-- Main Content -->
        <div style="background: #ffffff; padding: 40px 30px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
            
            <h2 style="color: #2c3e50; margin: 0 0 20px 0; font-size: 24px;">
                Dear {team_leader.full_name},
            </h2>
            
            <p style="color: #34495e; font-size: 16px; line-height: 1.6; margin: 0 0 25px 0;">
                You have been assigned a new visitation. May God grant you wisdom and grace as you minister to His people.
            </p>
            
            <!-- Visitation Details Card -->
            <div style="background: linear-gradient(135deg, #e8f4f8 0%, #f0f8ff 100%); border-left: 5px solid #667eea; padding: 25px; margin: 25px 0; border-radius: 8px;">
                
                <h3 style="color: #667eea; margin: 0 0 20px 0; font-size: 20px; border-bottom: 2px solid #667eea; padding-bottom: 10px;">
                    📋 Visitation Details
                </h3>
                
                <table style="width: 100%; border-collapse: collapse;">
                    <tr>
                        <td style="padding: 12px 0; color: #7f8c8d; font-weight: 600; width: 40%;">Visitation ID:</td>
                        <td style="padding: 12px 0; color: #2c3e50; font-weight: 700;">{visitation.name}</td>
                    </tr>
                    <tr style="background: rgba(255,255,255,0.5);">
                        <td style="padding: 12px 0; color: #7f8c8d; font-weight: 600;">Member to Visit:</td>
                        <td style="padding: 12px 0; color: #2c3e50; font-weight: 700;">{visitation.visitee_full_name}</td>
                    </tr>
                    <tr>
                        <td style="padding: 12px 0; color: #7f8c8d; font-weight: 600;">Date:</td>
                        <td style="padding: 12px 0; color: #667eea; font-weight: 700;">{formatted_date} ({visitation.day})</td>
                    </tr>
                    <tr style="background: rgba(255,255,255,0.5);">
                        <td style="padding: 12px 0; color: #7f8c8d; font-weight: 600;">Type:</td>
                        <td style="padding: 12px 0; color: #2c3e50;">{visitation.type}</td>
                    </tr>
                    <tr>
                        <td style="padding: 12px 0; color: #7f8c8d; font-weight: 600;">Branch:</td>
                        <td style="padding: 12px 0; color: #2c3e50;">{visitation.branch}</td>
                    </tr>
                    <tr style="background: rgba(255,255,255,0.5);">
                        <td style="padding: 12px 0; color: #7f8c8d; font-weight: 600;">Location:</td>
                        <td style="padding: 12px 0; color: #2c3e50;">{visitation.location or 'See Address'}</td>
                    </tr>
                </table>
                
                {address_section}
                
                {contact_section}
                
            </div>
            
            <!-- Action Button -->
            <div style="text-align: center; margin: 35px 0;">
                <a href="{frappe.utils.get_url()}/app/visitation/{visitation.name}" 
                   style="display: inline-block; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: #ffffff; padding: 15px 40px; text-decoration: none; border-radius: 50px; font-weight: 700; font-size: 16px; box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4); transition: all 0.3s;">
                    📝 View Visitation Details
                </a>
            </div>
            
            <!-- Reminder -->
            <div style="background: #fff9c4; border-left: 5px solid #ffc107; padding: 20px; margin: 25px 0; border-radius: 8px;">
                <p style="color: #6d6d00; margin: 0; font-size: 15px; line-height: 1.6;">
                    <strong>💡 Reminder:</strong> Please complete the visitation report after your visit. Your insights help us better care for our members.
                </p>
            </div>
            
            <!-- Scripture -->
            <div style="text-align: center; margin: 30px 0; padding: 25px; background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%); border-radius: 10px;">
                <p style="color: #667eea; font-style: italic; font-size: 16px; margin: 0; line-height: 1.8;">
                    "And let us consider how we may spur one another on toward love and good deeds, not giving up meeting together..."
                </p>
                <p style="color: #7f8c8d; font-size: 14px; margin: 10px 0 0 0; font-weight: 600;">
                    - Hebrews 10:24-25
                </p>
            </div>
            
        </div>
        
        <!-- Footer -->
        <div style="background: #2c3e50; padding: 25px 30px; text-align: center; border-radius: 0 0 10px 10px;">
            <p style="color: #95a5a6; margin: 0; font-size: 13px;">
                This is an automated notification from {church_name} Ecclesia Management System
            </p>
            <p style="color: #7f8c8d; margin: 10px 0 0 0; font-size: 12px;">
                📅 Sent on {formatdate(nowdate(), "dd MMMM yyyy")}
            </p>
        </div>
        
    </div>
    """
    
    return email_html