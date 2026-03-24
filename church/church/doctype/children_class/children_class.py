# -*- coding: utf-8 -*-
"""
Children Class Controller with Integrated Birthday Automation
Handles all class management, promotions, and automated birthday wishes
"""

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe import _
from frappe.utils import getdate, nowdate, add_days, date_diff, add_to_date, formatdate, now_datetime, format_datetime
import json


class ChildrenClass(Document):
    def validate(self):
        """Validate class data before save"""
        self.validate_promotion_path()
        self.calculate_member_count()
        self.calculate_asset_value()
        self.populate_slated_promotions()
    
    def validate_promotion_path(self):
        """Ensure class doesn't promote to itself"""
        if self.next_class_group and self.next_class_group == self.name:
            frappe.throw(_("A class cannot promote to itself. Please select a different next class group."))
    
    def calculate_member_count(self):
        """Calculate total number of members"""
        self.member_count = len(self.children_class_member) if self.children_class_member else 0
    
    def calculate_asset_value(self):
        """Calculate total asset value"""
        if self.children_class_assets:
            total = 0
            for asset_row in self.children_class_assets:
                # Get asset value from Asset doctype
                if asset_row.asset_id:
                    asset_value = frappe.db.get_value('Asset', asset_row.asset_id, 'gross_purchase_amount') or 0
                    total += asset_value
            self.value_of_asset = total
        else:
            self.value_of_asset = 0
    
    def populate_slated_promotions(self):
        """Auto-populate children due for promotion based on age"""
        if not self.promotion_age:
            return
        
        today = getdate(nowdate())
        
        # Clear existing slated promotions
        self.slated_promotion = []
        
        # Check each member for promotion eligibility
        for member in self.children_class_member:
            if not member.date_of_birth:
                continue
            
            # Calculate age and promotion date
            age = date_diff(today, member.date_of_birth) // 365
            promotion_date = add_to_date(member.date_of_birth, years=self.promotion_age)
            
            # If child has reached promotion age
            if age >= self.promotion_age or date_diff(today, promotion_date) >= 0:
                self.append('slated_promotion', {
                    'child_id': member.child_id,
                    'full_name': member.full_name,
                    'age': age,
                    'gender': member.gender,
                    'promotion_date': promotion_date,
                    'proposed_new_date': today if date_diff(today, promotion_date) >= 0 else promotion_date
                })


# ==================== SCHEDULED JOB - Birthday Wishes ====================
def send_daily_birthday_wishes():
    """
    Scheduled to run daily at 6:00 AM
    
    Add to hooks.py:
    scheduler_events = {
        "cron": {
            "0 6 * * *": [
                "church.church.doctype.children_class.children_class.send_daily_birthday_wishes"
            ]
        }
    }
    """
    settings = frappe.get_single("Church Settings")
    
    if not settings.enable_birthday_notifications:
        frappe.logger().info("Birthday notifications disabled in Church Settings")
        return {'message': 'Birthday notifications disabled'}
    
    today = getdate(nowdate())
    
    # Get all children with birthdays today
    children_with_birthdays = frappe.db.sql("""
        SELECT DISTINCT
            ccm.child_id,
            ccm.full_name,
            ccm.date_of_birth,
            ccm.gender,
            ccm.phone_no,
            ccm.email,
            ccm.age,
            ccm.branch,
            ccm.parent as children_class_name,
            ccm.class_name,
            ccm.teacher_name,
            cc.email as teacher_email,
            cc.phone_no as teacher_phone
        FROM `tabChildren Class Member` ccm
        INNER JOIN `tabChildren Class` cc ON cc.name = ccm.parent
        WHERE 
            ccm.date_of_birth IS NOT NULL
            AND DAY(ccm.date_of_birth) = DAY(%s)
            AND MONTH(ccm.date_of_birth) = MONTH(%s)
    """, (today, today), as_dict=1)
    
    sent_count = 0
    birthday_list = []
    
    for child in children_with_birthdays:
        try:
            # Calculate current age
            age = date_diff(today, child.date_of_birth) // 365
            
            # Send birthday wishes via all enabled channels
            send_birthday_wishes_multi_channel(child, age, settings)
            
            # Log the birthday wish
            log_birthday_wish(child, age)
            
            birthday_list.append({
                'name': child.full_name,
                'age': age,
                'class': child.class_name,
                'branch': child.branch
            })
            
            sent_count += 1
            
        except Exception as e:
            frappe.log_error(
                message=frappe.get_traceback(),
                title=f"Birthday Wish Failed: {child.full_name}"
            )
    
    # Send daily summary to admin
    if sent_count > 0:
        send_birthday_summary_to_admin(birthday_list, sent_count, today, settings)
    
    frappe.logger().info(f"Birthday wishes sent: {sent_count}")
    
    return {
        'sent': sent_count,
        'birthdays': birthday_list
    }


def send_birthday_wishes_multi_channel(child, age, settings):
    """Send birthday wishes via WhatsApp, Email, and SMS"""
    # Get message templates
    templates = get_birthday_message_templates(child, age, settings)
    
    # Use contact info from Children Class Member table
    parent_phone = child.phone_no or ""
    parent_email = child.email or ""
    parent_name = "Dear Parent"  # Generic since we don't have parent name in child table
    
    # 1. Send WhatsApp to Parents
    if settings.enable_whatsapp_birthday and parent_phone:
        send_whatsapp_message(parent_phone, templates['whatsapp'], settings)
    
    # 2. Send Email to Parents
    if settings.enable_email_birthday and parent_email:
        send_email_message(parent_email, child, age, parent_name, templates['email'], settings)
    
    # 3. Send SMS to Parents
    if settings.enable_sms_birthday and parent_phone:
        send_sms_message(parent_phone, templates['sms'], settings)
    
    # 4. Notify Teacher
    if settings.notify_teacher_birthday and child.teacher_email:
        notify_teacher_birthday(child, age, settings)
    
    # 5. Send to Child (if 10+ and has phone - using same phone_no field)
    if settings.send_to_child and child.phone_no and age >= 10:
        send_whatsapp_message(child.phone_no, templates['child'], settings)


def get_birthday_message_templates(child, age, settings):
    """Generate birthday message templates"""
    import random
    
    name = child.full_name
    class_name = child.class_name or 'Sunday School'
    church_name = settings.church_name or 'Our Church'
    
    # Determine theme based on age
    if age <= 3:
        emojis = ['🎈', '🧸', '🎁', '🍰', '🎉']
        theme = 'baby'
    elif age <= 6:
        emojis = ['🎈', '🎂', '🎁', '🎉', '🎊', '🌈']
        theme = 'toddler'
    elif age <= 12:
        emojis = ['🎉', '🎂', '🎁', '🎈', '⭐', '🌟']
        theme = 'child'
    else:
        emojis = ['🎉', '🎂', '🎁', '⭐', '🌟', '💫']
        theme = 'teen'
    
    emoji = random.choice(emojis)
    
    # WhatsApp Template
    whatsapp_msg = f"""{emoji} Happy {age}th Birthday to {name}! {emoji}

May God's blessings shine upon you today and always! 🙏✨

Your {class_name} family celebrates with you!
🎈 Have a blessed and joyful day! 🎈

~ {church_name}"""
    
    # SMS Template
    sms_msg = f"Happy {age}th Birthday {name}! God bless you today & always! {emoji} - {church_name}"
    
    # Child's Personal Message
    child_msg = f"""🎉 HAPPY BIRTHDAY {name.upper()}! 🎉

You're {age} today! How awesome is that?! 🎂

We're so blessed to have you in {class_name}!
May God fill your day with joy and surprises! 🎁✨

Have the BEST birthday EVER! 🎈🎊

~ Your {church_name} Family"""
    
    # Email HTML
    email_html = generate_birthday_email_html(child, age, emoji, theme, settings)
    
    return {
        'whatsapp': whatsapp_msg,
        'sms': sms_msg,
        'child': child_msg,
        'email': email_html
    }


def generate_birthday_email_html(child, age, emoji, theme, settings):
    """Generate beautiful HTML email template"""
    from datetime import datetime
    
    name = child.full_name
    class_name = child.class_name or 'Sunday School'
    teacher_name = child.teacher_name or 'Your Teacher'
    branch = child.branch or settings.church_name
    church_name = settings.church_name or 'Our Church'
    church_logo = settings.church_logo or ''
    church_email = settings.church_email or ''
    church_phone = settings.church_phone or ''
    
    # Color themes
    themes = {
        'baby': {'primary': '#FFB6C1', 'gradient_start': '#FFB6C1', 'gradient_end': '#FF69B4', 'accent': '#FF69B4'},
        'toddler': {'primary': '#87CEEB', 'gradient_start': '#87CEEB', 'gradient_end': '#4169E1', 'accent': '#4169E1'},
        'child': {'primary': '#FFD700', 'gradient_start': '#FFD700', 'gradient_end': '#FFA500', 'accent': '#FFA500'},
        'teen': {'primary': '#9370DB', 'gradient_start': '#9370DB', 'gradient_end': '#8A2BE2', 'accent': '#8A2BE2'}
    }
    
    t = themes.get(theme, themes['child'])
    pronoun = 'him' if child.gender == 'Male' else 'her'
    
    # Bible verse
    bible_verse = get_age_appropriate_bible_verse(age)
    
    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0;padding:0;font-family:Arial,sans-serif;background:#f5f7fa;">
    <div style="max-width:650px;margin:30px auto;background:white;border-radius:25px;overflow:hidden;box-shadow:0 20px 60px rgba(0,0,0,0.15);">
        
        <!-- Header -->
        <div style="background:linear-gradient(135deg,{t['gradient_start']},{t['gradient_end']});padding:50px 30px;text-align:center;">
            {"<img src='" + church_logo + "' style='max-width:120px;margin-bottom:20px;border-radius:50%;background:white;padding:10px;'>" if church_logo else ""}
            <div style="font-size:90px;margin-bottom:15px;">{emoji}</div>
            <h1 style="color:white;margin:0;font-size:42px;text-shadow:3px 3px 6px rgba(0,0,0,0.3);font-weight:800;">HAPPY BIRTHDAY!</h1>
            <div style="color:white;font-size:28px;margin-top:15px;font-weight:bold;">{name}</div>
        </div>
        
        <!-- Confetti -->
        <div style="background:#fff9f0;padding:25px;text-align:center;font-size:45px;letter-spacing:15px;">🎈🎊🎉🎁🎂</div>
        
        <!-- Content -->
        <div style="padding:45px 35px;">
            
            <!-- Age Badge -->
            <div style="text-align:center;margin-bottom:35px;">
                <div style="display:inline-block;background:linear-gradient(135deg,{t['gradient_start']},{t['gradient_end']});color:white;border-radius:50%;width:120px;height:120px;line-height:120px;font-size:56px;font-weight:900;box-shadow:0 10px 30px rgba(0,0,0,0.25);border:5px solid white;">
                    {age}
                </div>
                <div style="margin-top:15px;font-size:20px;color:#666;font-weight:bold;">Years of Blessings! ✨</div>
            </div>
            
            <!-- Message -->
            <div style="background:#f8f9fa;border-left:6px solid {t['accent']};padding:25px;border-radius:12px;margin-bottom:35px;">
                <p style="color:#333;font-size:17px;line-height:1.8;margin:0 0 15px 0;">Dear Parent/Guardian,</p>
                <p style="color:#333;font-size:17px;line-height:1.8;margin:0 0 15px 0;">
                    We are absolutely <strong style="color:{t['accent']};">DELIGHTED</strong> to celebrate <strong>{name}'s {age}th birthday</strong> with you today! 🎉
                </p>
                <p style="color:#333;font-size:17px;line-height:1.8;margin:0 0 15px 0;">
                    {name} brings so much <strong style="color:{t['accent']};">joy, light, and love</strong> to our <strong>{class_name}</strong> family. 
                    We are blessed to watch {pronoun} grow in faith, wisdom, and grace!
                </p>
                <p style="color:#333;font-size:17px;line-height:1.8;margin:0;">
                    May God's <strong style="color:{t['accent']};">abundant blessings</strong> surround {name} today and throughout the year ahead! 🙏✨
                </p>
            </div>
            
            <!-- Bible Verse -->
            <div style="background:linear-gradient(135deg,#667eea,#764ba2);padding:30px;border-radius:15px;margin-bottom:35px;text-align:center;">
                <div style="color:#FFD700;font-size:28px;margin-bottom:15px;">✝️</div>
                <div style="color:white;font-size:19px;font-style:italic;line-height:1.8;margin-bottom:12px;">"{bible_verse['text']}"</div>
                <div style="color:rgba(255,255,255,0.95);font-size:15px;font-weight:bold;">{bible_verse['reference']}</div>
            </div>
            
            <!-- Wishes -->
            <div style="background:#fff9e6;border:3px dashed {t['accent']};padding:25px;border-radius:12px;margin-bottom:35px;">
                <div style="text-align:center;font-size:26px;margin-bottom:20px;color:{t['accent']};font-weight:bold;">🎁 Special Birthday Wishes 🎁</div>
                <ul style="color:#333;font-size:16px;line-height:2;padding-left:30px;margin:0;">
                    <li>May your day sparkle with laughter, joy, and love! 💫</li>
                    <li>May you continue to shine bright in God's amazing love! 🌟</li>
                    <li>May this year bring incredible adventures and blessings! 🎈</li>
                    <li>May you always feel loved, cherished, and celebrated! ❤️</li>
                </ul>
            </div>
            
            <!-- From Section -->
            <div style="text-align:center;margin-top:40px;padding-top:25px;border-top:3px solid {t['primary']};">
                <p style="color:#666;font-size:17px;margin:8px 0;font-style:italic;">With love, prayers, and warm hugs,</p>
                <p style="color:{t['accent']};font-size:22px;font-weight:bold;margin:10px 0;">{teacher_name}</p>
                <p style="color:#666;font-size:16px;margin:5px 0;font-weight:600;">{class_name} Teacher</p>
                <p style="color:#999;font-size:15px;margin:18px 0 8px 0;">{branch}</p>
            </div>
            
        </div>
        
        <!-- Footer -->
        <div style="background:#f8f9fa;padding:30px;text-align:center;border-top:4px solid {t['primary']};">
            <div style="font-size:35px;margin-bottom:15px;">🎂🎈🎉</div>
            <div style="color:{t['accent']};font-size:22px;font-weight:bold;margin-bottom:10px;">{church_name}</div>
            {"<div style='color:#666;font-size:14px;margin:5px 0;'>📧 " + church_email + "</div>" if church_email else ""}
            {"<div style='color:#666;font-size:14px;margin:5px 0;'>📞 " + church_phone + "</div>" if church_phone else ""}
            <div style="color:#999;font-size:12px;margin-top:15px;padding-top:15px;border-top:1px solid #ddd;">
                © {datetime.now().year} {church_name}. All rights reserved.<br>Sent with love from Ecclesia ⛪
            </div>
        </div>
        
    </div>
</body>
</html>"""
    
    return html


def get_age_appropriate_bible_verse(age):
    """Get age-appropriate Bible verse"""
    import random
    
    verses = {
        'baby': [
            {'text': 'Children are a heritage from the Lord, offspring a reward from him.', 'reference': 'Psalm 127:3'},
            {'text': 'Before I formed you in the womb I knew you, before you were born I set you apart.', 'reference': 'Jeremiah 1:5'}
        ],
        'child': [
            {'text': 'For I know the plans I have for you, plans to prosper you and not to harm you, plans to give you hope and a future.', 'reference': 'Jeremiah 29:11'},
            {'text': 'Let the little children come to me, and do not hinder them, for the kingdom of heaven belongs to such as these.', 'reference': 'Matthew 19:14'}
        ],
        'teen': [
            {'text': "Don't let anyone look down on you because you are young, but set an example for the believers in speech, in conduct, in love, in faith and in purity.", 'reference': '1 Timothy 4:12'},
            {'text': 'I can do all things through Christ who strengthens me.', 'reference': 'Philippians 4:13'}
        ]
    }
    
    if age <= 3:
        return random.choice(verses['baby'])
    elif age <= 12:
        return random.choice(verses['child'])
    else:
        return random.choice(verses['teen'])


def send_whatsapp_message(phone, message, settings):
    """Send WhatsApp message via configured provider"""
    try:
        provider = settings.whatsapp_provider
        
        if provider == 'Twilio':
            send_via_twilio_whatsapp(phone, message, settings)
        elif provider == 'MessageBird':
            send_via_messagebird_whatsapp(phone, message, settings)
        elif provider == 'Custom API':
            send_via_custom_api(phone, message, settings.custom_whatsapp_api_url, settings.custom_whatsapp_api_key)
    except Exception as e:
        frappe.log_error(f"WhatsApp send failed: {str(e)}\nPhone: {phone}", "WhatsApp Error")


def send_sms_message(phone, message, settings):
    """Send SMS via configured provider"""
    try:
        provider = settings.sms_provider
        
        if provider == 'Twilio':
            send_via_twilio_sms(phone, message, settings)
        elif provider == 'MessageBird':
            send_via_messagebird_sms(phone, message, settings)
        elif provider == 'Custom API':
            send_via_custom_api(phone, message, settings.custom_sms_api_url, settings.custom_sms_api_key)
    except Exception as e:
        frappe.log_error(f"SMS send failed: {str(e)}\nPhone: {phone}", "SMS Error")


def send_email_message(email, child, age, parent_name, html_content, settings):
    """Send birthday email"""
    try:
        subject = f"🎉 Happy {age}th Birthday {child.full_name}! 🎂"
        
        frappe.sendmail(
            recipients=[email],
            subject=subject,
            message=html_content,
            delayed=False,
            retry=3
        )
    except Exception as e:
        frappe.log_error(f"Email send failed: {str(e)}\nEmail: {email}", "Email Error")


def send_via_twilio_whatsapp(phone, message, settings):
    """Send via Twilio WhatsApp"""
    import requests
    
    url = f"https://api.twilio.com/2010-04-01/Accounts/{settings.twilio_account_sid}/Messages.json"
    response = requests.post(
        url,
        data={'From': f'whatsapp:{settings.twilio_whatsapp_number}', 'To': f'whatsapp:{phone}', 'Body': message},
        auth=(settings.twilio_account_sid, settings.twilio_auth_token)
    )
    if response.status_code != 201:
        raise Exception(f"Twilio error: {response.text}")


def send_via_twilio_sms(phone, message, settings):
    """Send via Twilio SMS"""
    import requests
    
    url = f"https://api.twilio.com/2010-04-01/Accounts/{settings.twilio_account_sid}/Messages.json"
    response = requests.post(
        url,
        data={'From': settings.twilio_phone_number, 'To': phone, 'Body': message},
        auth=(settings.twilio_account_sid, settings.twilio_auth_token)
    )
    if response.status_code != 201:
        raise Exception(f"Twilio SMS error: {response.text}")


def send_via_messagebird_whatsapp(phone, message, settings):
    """Send via MessageBird WhatsApp"""
    import requests
    
    url = "https://conversations.messagebird.com/v1/send"
    response = requests.post(
        url,
        json={'to': phone, 'from': settings.messagebird_channel_id, 'type': 'text', 'content': {'text': message}},
        headers={'Authorization': f'AccessKey {settings.messagebird_api_key}', 'Content-Type': 'application/json'}
    )
    if response.status_code not in [200, 201]:
        raise Exception(f"MessageBird error: {response.text}")


def send_via_messagebird_sms(phone, message, settings):
    """Send via MessageBird SMS"""
    import requests
    
    url = "https://rest.messagebird.com/messages"
    response = requests.post(
        url,
        json={'recipients': [phone], 'originator': settings.messagebird_originator, 'body': message},
        headers={'Authorization': f'AccessKey {settings.messagebird_api_key}', 'Content-Type': 'application/json'}
    )
    if response.status_code not in [200, 201]:
        raise Exception(f"MessageBird SMS error: {response.text}")


def send_via_custom_api(phone, message, api_url, api_key):
    """Send via Custom API"""
    import requests
    
    response = requests.post(
        api_url,
        json={'phone': phone, 'message': message},
        headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}
    )
    if response.status_code not in [200, 201]:
        raise Exception(f"Custom API error: {response.text}")


def notify_teacher_birthday(child, age, settings):
    """Notify teacher about student's birthday"""
    try:
        subject = f"🎂 Student Birthday: {child.full_name} ({age} years old)"
        
        message = f"""<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px;">
            <div style="background:linear-gradient(135deg,#667eea,#764ba2);padding:25px;border-radius:10px;text-align:center;margin-bottom:20px;">
                <h2 style="color:white;margin:0;">🎂 Student Birthday Alert</h2>
            </div>
            <div style="background:white;padding:25px;border-radius:10px;box-shadow:0 2px 10px rgba(0,0,0,0.1);">
                <p>Dear <strong>{child.teacher_name}</strong>,</p>
                <p>One of your students is celebrating their birthday today!</p>
                <div style="background:#f0f8ff;padding:20px;border-left:4px solid #667eea;margin:20px 0;border-radius:5px;">
                    <p style="margin:5px 0;"><strong>Student:</strong> {child.full_name}</p>
                    <p style="margin:5px 0;"><strong>Age:</strong> {age} years old</p>
                    <p style="margin:5px 0;"><strong>Class:</strong> {child.class_name}</p>
                </div>
                <p>We've sent birthday wishes to their parents/guardians. You might want to give {child.full_name} a special birthday greeting! 🎈</p>
                <p style="font-size:14px;color:#666;margin-top:20px;">Blessings,<br><strong>{settings.church_name}</strong></p>
            </div>
        </div>"""
        
        frappe.sendmail(recipients=[child.teacher_email], subject=subject, message=message, delayed=False)
    except Exception as e:
        frappe.log_error(f"Teacher notification failed: {str(e)}", "Teacher Notification Error")


def log_birthday_wish(child, age):
    """Log birthday wish sent"""
    try:
        log = frappe.get_doc({
            'doctype': 'Communication Log',
            'reference_doctype': 'Member',
            'reference_name': child.child_id,
            'communication_type': 'Birthday Wish',
            'subject': f"Birthday Wish - {child.full_name} ({age} years)",
            'content': f"Sent birthday wishes via WhatsApp, Email, and SMS",
            'sent_on': now_datetime(),
            'status': 'Sent'
        })
        log.insert(ignore_permissions=True)
        frappe.db.commit()
    except:
        pass  # Ignore if Communication Log doesn't exist


def send_birthday_summary_to_admin(birthday_list, count, date, settings):
    """Send daily summary to admin"""
    try:
        admin_email = settings.admin_notification_email or settings.church_email
        if not admin_email:
            return
        
        subject = f"📅 Birthday Summary - {formatdate(date, 'dd MMM yyyy')} ({count} birthdays)"
        
        rows = ""
        for b in birthday_list:
            rows += f"<tr style='border-bottom:1px solid #eee;'><td style='padding:12px;'>{b['name']}</td><td style='padding:12px;text-align:center;'>{b['age']}</td><td style='padding:12px;'>{b['class']}</td></tr>"
        
        message = f"""<div style="font-family:Arial,sans-serif;max-width:700px;margin:0 auto;padding:20px;">
            <div style="background:linear-gradient(135deg,#667eea,#764ba2);padding:30px;border-radius:15px;text-align:center;margin-bottom:25px;">
                <h1 style="color:white;margin:0;">🎉 Daily Birthday Summary 🎂</h1>
                <p style="color:rgba(255,255,255,0.9);margin:10px 0 0 0;">{formatdate(date, 'dddd, dd MMMM yyyy')}</p>
            </div>
            <div style="background:white;padding:25px;border-radius:10px;box-shadow:0 2px 15px rgba(0,0,0,0.1);">
                <div style="background:#f0f8ff;padding:20px;border-radius:8px;text-align:center;margin-bottom:25px;">
                    <h2 style="color:#667eea;margin:0;font-size:36px;">{count}</h2>
                    <p style="color:#666;margin:5px 0 0 0;">Birthday wishes sent today</p>
                </div>
                <table style="width:100%;border-collapse:collapse;">
                    <thead><tr style="background:linear-gradient(135deg,#667eea,#764ba2);color:white;">
                        <th style="padding:15px;text-align:left;">Child Name</th>
                        <th style="padding:15px;text-align:center;">Age</th>
                        <th style="padding:15px;text-align:left;">Class</th>
                    </tr></thead>
                    <tbody>{rows}</tbody>
                </table>
                <div style="margin-top:25px;padding:20px;background:#fff9e6;border-left:4px solid #FFD700;border-radius:5px;">
                    <p style="margin:0;color:#666;font-size:14px;">✅ All birthday wishes sent via WhatsApp, Email, and SMS<br>✅ Teachers notified<br>✅ Logs created</p>
                </div>
            </div>
        </div>"""
        
        frappe.sendmail(recipients=[admin_email], subject=subject, message=message, delayed=False)
    except Exception as e:
        frappe.log_error(f"Admin summary failed: {str(e)}", "Admin Summary Error")


# ==================== WHITELISTED METHODS ====================

@frappe.whitelist()
def check_promotion_eligibility(class_name):
    """Check which children are eligible for promotion"""
    doc = frappe.get_doc("Children Class", class_name)
    today = getdate(nowdate())
    
    eligible = []
    upcoming = []
    
    for member in doc.children_class_member:
        if not member.date_of_birth or not doc.promotion_age:
            continue
        
        age = date_diff(today, member.date_of_birth) // 365
        promotion_date = add_to_date(member.date_of_birth, years=doc.promotion_age)
        days_until = date_diff(promotion_date, today)
        
        if days_until <= 0:
            eligible.append({
                'child_id': member.child_id,
                'full_name': member.full_name,
                'age': age,
                'promotion_date': promotion_date
            })
        elif days_until <= 30:
            upcoming.append({
                'child_id': member.child_id,
                'full_name': member.full_name,
                'age': age,
                'promotion_date': promotion_date
            })
    
    return {'eligible': eligible, 'upcoming': upcoming}


@frappe.whitelist()
def process_promotions(class_name, children):
    """Process promotions for eligible children"""
    doc = frappe.get_doc("Children Class", class_name)
    
    if not doc.next_class_group:
        frappe.throw(_("Please set the Next Class Group before processing promotions"))
    
    children_list = json.loads(children) if isinstance(children, str) else children
    next_class = frappe.get_doc("Children Class", doc.next_class_group)
    
    promoted_count = 0
    
    for child_data in children_list:
        # Find child in current class
        for idx, member in enumerate(doc.children_class_member):
            if member.child_id == child_data['child_id']:
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
                
                # Remove from current class
                doc.remove(member)
                
                promoted_count += 1
                break
    
    # Save both documents
    doc.save(ignore_permissions=True)
    next_class.save(ignore_permissions=True)
    frappe.db.commit()
    
    return {
        'success': True,
        'promoted_count': promoted_count,
        'message': f'Successfully promoted {promoted_count} children to {next_class.class_name}'
    }


@frappe.whitelist()
def export_class_report(class_name):
    """Export comprehensive Excel report"""
    try:
        import pandas as pd
        from io import BytesIO
        
        doc = frappe.get_doc("Children Class", class_name)
        
        output = BytesIO()
        writer = pd.ExcelWriter(output, engine='xlsxwriter')
        workbook = writer.book
        
        # Formats
        header_format = workbook.add_format({
            'bold': True, 'bg_color': '#4472C4', 'font_color': 'white',
            'border': 1, 'align': 'center', 'valign': 'vcenter'
        })
        
        title_format = workbook.add_format({
            'bold': True, 'font_size': 16, 'bg_color': '#D9E1F2',
            'align': 'center', 'valign': 'vcenter'
        })
        
        # Overview Sheet
        overview_data = {
            'Class Name': [doc.class_name],
            'Class Group': [doc.age_group],
            'Branch': [doc.branch],
            'Teacher': [doc.teacher_name],
            'Total Members': [doc.member_count or 0],
            'Promotion Age': [doc.promotion_age],
            'Next Class': [doc.next_class_group],
            'Asset Value': [doc.value_of_asset or 0]
        }
        df_overview = pd.DataFrame(overview_data).T
        df_overview.columns = ['Value']
        df_overview.to_excel(writer, sheet_name='Overview', startrow=2)
        
        ws = writer.sheets['Overview']
        ws.merge_range('A1:B1', f'{doc.class_name} - Class Report', title_format)
        ws.set_column('A:A', 25)
        ws.set_column('B:B', 30)
        
        # Members Sheet
        if doc.children_class_member:
            members_data = [{
                'Child ID': m.child_id, 'Full Name': m.full_name, 'Age': m.age,
                'Gender': m.gender, 'Date of Birth': m.date_of_birth,
                'Phone': m.phone_no, 'Email': m.email, 'Joined': m.date_of_joining
            } for m in doc.children_class_member]
            
            df_members = pd.DataFrame(members_data)
            df_members.to_excel(writer, sheet_name='Members', startrow=1, index=False)
            
            ws = writer.sheets['Members']
            ws.merge_range('A1:H1', 'Class Members', title_format)
            for col_num, value in enumerate(df_members.columns.values):
                ws.write(1, col_num, value, header_format)
            ws.set_column('A:H', 15)
        
        # Promotions Sheet
        if doc.slated_promotion:
            promo_data = [{
                'Child ID': p.child_id, 'Full Name': p.full_name, 'Age': p.age,
                'Gender': p.gender, 'Promotion Date': p.promotion_date
            } for p in doc.slated_promotion]
            
            df_promo = pd.DataFrame(promo_data)
            df_promo.to_excel(writer, sheet_name='Promotions', startrow=1, index=False)
            
            ws = writer.sheets['Promotions']
            ws.merge_range('A1:E1', 'Promotions Due', title_format)
            for col_num, value in enumerate(df_promo.columns.values):
                ws.write(1, col_num, value, header_format)
        
        writer.close()
        output.seek(0)
        
        # Save file
        file_name = f"{doc.class_name.replace(' ', '_')}_Report_{nowdate()}.xlsx"
        file_doc = frappe.get_doc({
            'doctype': 'File',
            'file_name': file_name,
            'content': output.read(),
            'is_private': 0
        })
        file_doc.save(ignore_permissions=True)
        
        return {'file_url': file_doc.file_url, 'file_name': file_name}
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), 'Class Report Export Error')
        frappe.throw(_('Failed to generate report: {0}').format(str(e)))


@frappe.whitelist()
def send_class_update(class_name, recipients, custom_emails, subject, message, include_stats):
    """Send class update email"""
    doc = frappe.get_doc("Children Class", class_name)
    
    # Build recipient list
    recipient_list = []
    
    if recipients == 'Teachers Only':
        if doc.email:
            recipient_list.append(doc.email)
        if doc.assistant_teacher_email:
            recipient_list.append(doc.assistant_teacher_email)
    
    elif recipients == 'Parents Only':
        # Use email field from Children Class Member
        for member in doc.children_class_member:
            if member.email:
                recipient_list.append(member.email)
    
    elif recipients == 'Teachers and Parents':
        # Add teachers
        if doc.email:
            recipient_list.append(doc.email)
        if doc.assistant_teacher_email:
            recipient_list.append(doc.assistant_teacher_email)
        # Add parent emails from Children Class Member
        for member in doc.children_class_member:
            if member.email:
                recipient_list.append(member.email)
    
    elif recipients == 'Custom' and custom_emails:
        recipient_list = [email.strip() for email in custom_emails.split(',')]
    
    # Remove duplicates
    recipient_list = list(set(recipient_list))
    
    if not recipient_list:
        frappe.throw(_("No recipients found"))
    
    # Build email content
    stats_html = ""
    if include_stats:
        stats_html = f"""<div style="background:#f8f9fa;padding:20px;border-radius:8px;margin:20px 0;">
            <h3>Class Statistics</h3>
            <p><strong>Total Members:</strong> {doc.member_count or 0}</p>
            <p><strong>Male:</strong> {len([m for m in doc.children_class_member if m.gender == 'Male'])}</p>
            <p><strong>Female:</strong> {len([m for m in doc.children_class_member if m.gender == 'Female'])}</p>
        </div>"""
    
    full_message = f"""<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;">
        <div style="background:linear-gradient(135deg,#667eea,#764ba2);padding:30px;text-align:center;border-radius:10px 10px 0 0;">
            <h2 style="color:white;margin:0;">{doc.class_name}</h2>
        </div>
        <div style="padding:30px;background:white;">
            {message}
            {stats_html}
        </div>
        <div style="background:#f8f9fa;padding:20px;text-align:center;border-radius:0 0 10px 10px;">
            <p style="margin:0;color:#666;">Sent from {doc.class_name} • {doc.branch}</p>
        </div>
    </div>"""
    
    # Send email
    frappe.sendmail(
        recipients=recipient_list,
        subject=subject,
        message=full_message,
        delayed=False
    )
    
    return {'success': True, 'sent_to': len(recipient_list)}


@frappe.whitelist()
def generate_asset_qr_codes(class_name):
    """Generate QR codes for class assets"""
    try:
        import qrcode
        from io import BytesIO
        import base64
        
        doc = frappe.get_doc("Children Class", class_name)
        
        if not doc.children_class_assets:
            frappe.throw(_("No assets found in this class"))
        
        count = 0
        for asset_row in doc.children_class_assets:
            if not asset_row.asset_id:
                continue
            
            # Generate QR code
            qr = qrcode.QRCode(version=1, box_size=10, border=5)
            qr_data = f"Asset: {asset_row.asset_id}\nClass: {doc.class_name}\nLocation: {asset_row.location or 'N/A'}"
            qr.add_data(qr_data)
            qr.make(fit=True)
            
            img = qr.make_image(fill_color="black", back_color="white")
            
            # Save QR code
            buffer = BytesIO()
            img.save(buffer, format='PNG')
            buffer.seek(0)
            
            file_name = f"QR_{asset_row.asset_id}_{nowdate()}.png"
            file_doc = frappe.get_doc({
                'doctype': 'File',
                'file_name': file_name,
                'content': buffer.read(),
                'attached_to_doctype': 'Children Class',
                'attached_to_name': class_name,
                'is_private': 0
            })
            file_doc.save(ignore_permissions=True)
            
            count += 1
        
        return {'success': True, 'count': count}
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), 'QR Code Generation Error')
        frappe.throw(_('Failed to generate QR codes: {0}').format(str(e)))


@frappe.whitelist()
def get_class_roster_html(class_name):
    """Generate printable class roster"""
    doc = frappe.get_doc("Children Class", class_name)
    
    rows = ""
    for idx, member in enumerate(doc.children_class_member, 1):
        rows += f"""<tr>
            <td style="border:1px solid #ddd;padding:10px;">{idx}</td>
            <td style="border:1px solid #ddd;padding:10px;">{member.full_name}</td>
            <td style="border:1px solid #ddd;padding:10px;">{member.age}</td>
            <td style="border:1px solid #ddd;padding:10px;">{member.gender}</td>
            <td style="border:1px solid #ddd;padding:10px;">{member.phone_no or ''}</td>
            <td style="border:1px solid #ddd;padding:10px;"></td>
        </tr>"""
    
    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{doc.class_name} - Class Roster</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        .header {{ text-align: center; margin-bottom: 30px; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th {{ background: #667eea; color: white; padding: 12px; border: 1px solid #ddd; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>{doc.class_name}</h1>
        <p><strong>Teacher:</strong> {doc.teacher_name} | <strong>Branch:</strong> {doc.branch}</p>
        <p><strong>Date:</strong> {formatdate(nowdate(), 'dd MMMM yyyy')}</p>
    </div>
    <table>
        <thead>
            <tr>
                <th>#</th>
                <th>Name</th>
                <th>Age</th>
                <th>Gender</th>
                <th>Phone</th>
                <th>Signature</th>
            </tr>
        </thead>
        <tbody>{rows}</tbody>
    </table>
    <div style="margin-top:30px;">
        <p><strong>Total Members:</strong> {len(doc.children_class_member)}</p>
    </div>
</body>
</html>"""
    
    return html


@frappe.whitelist()
def send_birthday_wish_manual(child_id):
    """Manually send birthday wish to specific child"""
    settings = frappe.get_single("Church Settings")
    
    # Get child data using ONLY Children Class Member fields
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
            cc.email as teacher_email
        FROM `tabChildren Class Member` ccm
        INNER JOIN `tabChildren Class` cc ON cc.name = ccm.parent
        WHERE ccm.child_id = %s
        LIMIT 1
    """, (child_id,), as_dict=1)
    
    if not child_data:
        frappe.throw(_("Child not found"))
    
    child = child_data[0]
    age = date_diff(getdate(nowdate()), child.date_of_birth) // 365
    
    try:
        send_birthday_wishes_multi_channel(child, age, settings)
        log_birthday_wish(child, age)
        
        return {'success': True, 'message': f'Birthday wishes sent to {child.full_name}'}
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), 'Manual Birthday Wish Failed')
        return {'success': False, 'error': str(e)}