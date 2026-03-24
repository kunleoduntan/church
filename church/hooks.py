# -*- coding: utf-8 -*-
# Copyright (c) 2026, Church Management
# License: MIT
#
# church/hooks.py
# ─────────────────────────────────────────────────────────────────────────────

from . import __version__ as app_version  # noqa

app_name        = "church"
app_title       = "church"
app_publisher   = "kunle"
app_description = "Church Management"
app_email       = "kunleoduntan@gmail.com"
app_license     = "MIT"
app_version     = app_version


# ─────────────────────────────────────────────────────────────────────────────
# WEBSITE ROUTES
# ─────────────────────────────────────────────────────────────────────────────

website_route_rules = [
    {"from_route": "/member_portal", "to_route": "member_portal"},
]


# ─────────────────────────────────────────────────────────────────────────────
# PORTAL MENU
# ─────────────────────────────────────────────────────────────────────────────

portal_menu_items = [
    {"title": "Member Portal", "route": "/member_portal", "reference_doctype": "Member"},
]


# ─────────────────────────────────────────────────────────────────────────────
# CLIENT-SIDE SCRIPTS
# ─────────────────────────────────────────────────────────────────────────────

doctype_js = {
    "Purchase Invoice":    "public/js/purchase_invoice.js",
    "Bank Reconciliation": "public/js/bank_reconciliation_manual.js",
    "Annual Budget":       "public/js/annual_budget_manual.js",
    "Receipts":            "doctype/receipts/receipts.js",
    "Member":              "public/js/member_smart_attendance.js",
    "Church Attendance":   "public/js/church_attendance_smart.js",
}


# ─────────────────────────────────────────────────────────────────────────────
# DOCUMENT EVENTS
# ─────────────────────────────────────────────────────────────────────────────

doc_events = {

    "Church Attendance": {},

    "Attendance Sheet": {
        "before_save": "church.church.doctype.attendance_sheet.attendance_sheet.update_attendance_analysis",
        "on_submit":   "church.church.doctype.attendance_sheet.attendance_sheet.send_attendance_sheet_notification",
    },

    "Person Registry": {
        "after_insert": "church.church.doctype.person_registry.person_registry.after_insert",
    },

    "Bank Reconciliation": {
        "validate": "church.tasks.import_bank_statement_from_excel",
    },

    "Receipts": {
        "after_insert": "church.church.doctype.member_tithe_record.member_tithe_record.on_receipt_created",
        "on_update":    "church.church.doctype.member_tithe_record.member_tithe_record.on_receipt_updated",
        "on_submit":    "church.church.doctype.member_tithe_record.member_tithe_record.on_receipt_submitted",
        "on_cancel":    "church.church.doctype.member_tithe_record.member_tithe_record.on_receipt_cancelled",
    },

    "Member": {
        "after_save":   "church.attendance.smart_attendance.auto_generate_qr_code",
        #"after_insert": "church.church.doctype.member.member.generate_member_qr",
        "on_trash":     "church.api.member_portal_api.clear_member_portal_session",
        "on_update": "church.church.doctype.announcement.announcement.notify_member_update",
    },

    "Attendance Marking": {
        "on_cancel": "church.church.doctype.attendance_marking.attendance_marking.cancel_linked_attendance",
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# SCHEDULED TASKS
# ─────────────────────────────────────────────────────────────────────────────

scheduler_events = {

    "cron": {

        "*/5 * * * *": [
            "church.attendance.smart_attendance.auto_check_wifi_connections",
            "church.attendance.auto_service_creator.auto_create_service_instances",
            
        ],

        "*/10 * * * *": [
            "church.utils.network_detection_service.scheduled_network_scan",
        ],

        "*/15 * * * *": [
            "church.church.doctype.communication_campaign.communication_campaign.process_scheduled_campaigns",
            "church.church.doctype.visitor.visitor.send_welcome_message",
            "church.church.doctype.service_instance.service_instance_ai_attendance.auto_update_attendance_from_visitors",
            "church.church.doctype.announcement.announcement.process_scheduled",
        ],

        "0 */1 * * *": [
            "church.attendance.smart_attendance.cleanup_expired_qr_tokens",
        ],

        "0 6 * * *": [
            "church.church.doctype.children_class.children_class.send_daily_birthday_wishes",
        ],

        "0 6 * * 0": [
            "church.church.doctype.attendance_sheet.attendance_sheet.auto_create_attendance_sheets",
        ],

        "0 20 * * 0": [
            "church.church.doctype.church_attendance.church_attendance.send_attendance_reminders",
        ],
    },

    "hourly": [
        "church.church.doctype.church_attendance.church_attendance.auto_submit_attendance",
        "church.api.announcement_api.process_scheduled",
    ],

    "daily": [

        "church.church.doctype.presence_log.presence_log.auto_process_yesterday_logs",
        "church.church.doctype.daily_presence_record.daily_presence_record.auto_mark_absent",

        "church.church.doctype.communication_campaign.communication_campaign.process_recurring_campaigns",

        "church.church.doctype.member_tithe_record.member_tithe_record.sync_all_tithe_records",

        "church.church.doctype.church_department.church_department.daily_birthday_wishes",
        "church.church.doctype.member.member.send_birthday_wishes",

        "church.attendance.smart_attendance.cleanup_old_attendance_data",
        "church.attendance.smart_attendance.cleanup_expired_qr_tokens",

        "church.church.doctype.church_attendance.church_attendance.send_absent_member_emails",
        "church.church.doctype.church_attendance.church_attendance.send_absent_member_report",
        "church.church.doctype.church_attendance.church_attendance.run_member_followup_monitor",
        "church.church.doctype.pledges.pledges.send_pledge_reminders",

        # Member portal session cleanup
        "church.api.member_portal_api.purge_expired_portal_sessions",
    ],

    "weekly": [
        "church.church.doctype.member_tithe_record.member_tithe_record.create_missing_tithe_records",
        "church.church.doctype.offering_sheet.offering_sheet.auto_create_offering_sheets",
        "church.church.doctype.attendance_sheet.attendance_sheet.auto_create_attendance_sheets",
        "church.church.doctype.member.member.reclassify_members",
        "church.church.doctype.visitation.visitation.create_weekly_visitations",
        
    ],

    "yearly": [
        "church.church.doctype.member.member.reclassify_members",
    ],
    "all": [
        # Poll WiFi connections every 5 minutes (runs on every scheduler tick)
        # Only activates if enable_wifi_checkin is True in Church Settings
        "church.attendance.smart_attendance.auto_check_wifi_connections",
    ],
}


# ─────────────────────────────────────────────────────────────────────────────
# LOGOUT HANDLER
# ─────────────────────────────────────────────────────────────────────────────

on_logout = "church.api.member_portal_api.on_frappe_logout"