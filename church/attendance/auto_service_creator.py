# Copyright (c) 2026, kunle and contributors
# For license information, please see license.txt

"""
Auto Service Creator — Full Multi-Slot Implementation
=====================================================

Two distinct responsibilities:

── STEP 1: Church Service Creation (one-time setup, NO TEMPLATE NEEDED) ───────
  Called from a button in Church Settings (or manually).
  For every weekly_services row × every active branch × every slot number:
    Calculates each slot's start time:
      slot_1_start = time_from
      slot_2_start = time_from + (duration_hours × 60) + gap_minutes
      slot_3_start = slot_2_start + (duration_hours × 60) + gap_minutes
      ...
    Creates a Church Service record named:
      "{service_label} - {1st/2nd/3rd} Service - {Branch}"
    with sensible defaults (no base template required).
    Staff then opens each branch's record and fills in their specific
    minister, worship leader, ministry team, service order etc.

── STEP 2: Service Instance Creation (cron, every 5 minutes) ──────────────────
  Runs every 5 minutes.
  For each Church Service whose service_time is within the 10-minute window:
    Checks if a Service Instance already exists for today.
    If not → creates one, generates QR, notifies pastors.

Place at: church/attendance/auto_service_creator.py
"""

import frappe
from frappe import _
from frappe.utils import (
    now_datetime, getdate, get_datetime,
    formatdate, add_to_date, nowdate, cint
)
from datetime import datetime, timedelta
import hashlib
import qrcode
import io
import base64
from frappe.utils.file_manager import save_file
from urllib.parse import quote as _url_quote


# ── CONSTANTS ────────────────────────────────────────────────────────────────

DAY_MAP = {
    "Sun": 6,   # Python weekday(): Mon=0 … Sun=6
    "Mon": 0,
    "Tue": 1,
    "Wed": 2,
    "Thu": 3,
    "Fri": 4,
    "Sat": 5,
}

ORDINAL_SUFFIXES = {
    1: "1st",
    2: "2nd",
    3: "3rd",
    4: "4th",
    5: "5th",
    6: "6th",
    7: "7th",
}

LOOKAHEAD_MINUTES    = 10   # create instance this many minutes before service
SCHEDULER_INTERVAL   = 5    # cron fires every N minutes (must match hooks.py)
DEFAULT_GAP_MINUTES  = 30   # fallback if not set in Church Settings


# ============================================================================
# ── STEP 1: CHURCH SERVICE TEMPLATE CREATION ─────────────────────────────────
# ============================================================================

@frappe.whitelist()
def setup_church_services():
    """
    One-time (idempotent) setup: creates all Church Service records
    for every weekly_services row × active branch × slot number.
    No base template required — records are created from scratch.

    Called from:
      - A button in Church Settings JS
      - Manual console call: frappe.call('church.attendance.auto_service_creator.setup_church_services')

    Safe to re-run — skips records that already exist.
    Returns a summary dict.
    """
    try:
        settings    = frappe.get_single('Church Settings')
        branches    = _get_active_branches()
        gap_minutes = cint(getattr(settings, 'service_gap_minutes', DEFAULT_GAP_MINUTES)) or DEFAULT_GAP_MINUTES

        if not settings.weekly_services:
            return {'success': False, 'message': 'No weekly_services rows configured in Church Settings.'}

        if not branches:
            return {'success': False, 'message': 'No active branches found.'}

        created  = []
        skipped  = []
        errors   = []

        for row in settings.weekly_services:
            if not row.service or not row.time_from:
                continue

            num_slots        = cint(row.no_of_service_per_day) or 1
            duration_minutes = int(float(row.duration or 1.5) * 60)

            # Calculate start time for each slot
            slot_times = _calculate_slot_times(
                base_time=row.time_from,
                num_slots=num_slots,
                duration_minutes=duration_minutes,
                gap_minutes=gap_minutes
            )

            for branch in branches:
                for slot_idx, slot_time in enumerate(slot_times, start=1):
                    try:
                        result = _ensure_church_service_exists(
                            base_service_name = row.service,
                            branch            = branch,
                            slot_index        = slot_idx,
                            num_slots         = num_slots,
                            slot_time         = slot_time,
                            duration_minutes  = duration_minutes,
                            day_of_week       = row.day,
                            settings          = settings
                        )
                        if result == 'created':
                            label = _slot_service_name(row.service, slot_idx, num_slots, branch)
                            created.append(label)
                        else:
                            label = _slot_service_name(row.service, slot_idx, num_slots, branch)
                            skipped.append(label)

                    except Exception as e:
                        err = f"{row.service} slot {slot_idx} @ {branch}: {str(e)}"
                        errors.append(err)
                        frappe.log_error(frappe.get_traceback(), f"setup_church_services — {err}")

        frappe.db.commit()

        msg = (
            f"Setup complete. "
            f"Created: {len(created)}, "
            f"Already existed (skipped): {len(skipped)}, "
            f"Errors: {len(errors)}."
        )

        return {
            'success': True,
            'message': msg,
            'created': created,
            'skipped': skipped,
            'errors':  errors
        }

    except Exception:
        frappe.log_error(frappe.get_traceback(), "setup_church_services — fatal error")
        return {'success': False, 'message': 'Fatal error. Check error logs.'}


def _ensure_church_service_exists(
    base_service_name, branch, slot_index, num_slots,
    slot_time, duration_minutes, day_of_week, settings
):
    """
    Create a Church Service record for one slot + branch if it doesn't exist.

    NO TEMPLATE REQUIRED.
    Records are created from scratch using sensible defaults. Staff then
    opens each branch's Church Service record and fills in their specific
    minister, worship leader, ministry team, service order etc.

    Returns 'created' or 'exists'.
    """
    service_name = _slot_service_name(
        base_service_name, slot_index, num_slots, branch
    )

    # Already exists — skip
    if frappe.db.exists('Church Service', service_name):
        return 'exists'

    # ── Day of week full name ─────────────────────────────────────────────────
    day_full_map = {
        "Sun": "Sunday", "Mon": "Monday", "Tue": "Tuesday",
        "Wed": "Wednesday", "Thu": "Thursday", "Fri": "Friday", "Sat": "Saturday"
    }
    day_full = day_full_map.get(day_of_week, day_of_week)

    # ── Determine service_type ────────────────────────────────────────────────
    # Map the plain service label to a Church Service service_type option.
    # If the label matches a known type exactly, use it; otherwise default
    # to the label itself (the field is a Select but ignore_mandatory handles it).
    known_types = [
        'Sunday Service', 'Mid-Week Service', 'Prayer Meeting', 'Bible Study',
        'Evening Service', 'Youth Service', "Children's Service",
        "Workers' Meeting", 'Corporate Prayer', 'Fasting & Prayer',
        'All-Night Service', 'Special Service'
    ]
    service_type = base_service_name if base_service_name in known_types else 'Sunday Service'

    # ── Venue resolution (2-level priority) ──────────────────────────────────
    # venue is reqd=1 on Church Service.
    # Priority:
    #   1. Branch address/venue field — each branch has its own location
    #   2. Branch name               — always non-empty, safe last resort
    venue = ''
    branch_data = frappe.db.get_value(
        'Branch', branch,
        ['venue', 'location', 'full_address'],
        as_dict=True
    )
    if branch_data:
        venue = (
            branch_data.get('venue')        or
            branch_data.get('location')     or
            branch_data.get('full_address') or
            ''
        )
    venue = venue or branch   # branch name as final fallback

    # ── Create Church Service ─────────────────────────────────────────────────
    cs = frappe.new_doc('Church Service')
    cs.service_name       = service_name
    cs.branch             = branch
    cs.status             = 'Active'
    cs.service_time       = slot_time
    cs.duration_minutes   = duration_minutes
    cs.is_recurring       = 1
    cs.recurrence_pattern = 'Weekly'
    cs.day_of_week        = day_full
    cs.service_type       = service_type
    cs.venue              = venue

    # Sensible defaults — staff will update these per branch as needed
    cs.enable_attendance_tracking = 1
    cs.enable_offering_collection = 1
    cs.auto_track_visitors        = 1
    cs.visitor_follow_up_enabled  = 1
    cs.enable_live_streaming      = 0

    # ignore_mandatory=True so any other reqd fields that are branch-specific
    # (and therefore empty at creation time) do not block auto-creation.
    # Staff fills them in when configuring the branch's service record.
    cs.insert(ignore_permissions=True, ignore_mandatory=True)

    frappe.logger().info(
        f"[AutoServiceCreator] ✅ Church Service created: '{service_name}' "
        f"branch='{branch}' time='{slot_time}' venue='{venue}'"
    )
    return 'created'


# ============================================================================
# ── STEP 2: SERVICE INSTANCE CREATION (cron, every 5 minutes) ────────────────
# ============================================================================

def auto_create_service_instances():
    """
    Scheduled entry point — runs every 5 minutes.

    hooks.py:
        "*/5 * * * *": [
            "church.attendance.auto_service_creator.auto_create_service_instances"
        ]

    Logic:
      1. Read weekly_services from Church Settings.
      2. For each row matching today's day-of-week:
         a. Calculate all slot start times.
         b. For each slot whose start time is within the 10-minute window:
            - Loop all active branches.
            - Find the Church Service for that slot + branch.
            - If no Service Instance exists today → create it + QR + notify.
    """
    try:
        settings    = frappe.get_single('Church Settings')
        gap_minutes = cint(getattr(settings, 'service_gap_minutes', DEFAULT_GAP_MINUTES)) or DEFAULT_GAP_MINUTES

        if not settings.weekly_services:
            return

        now           = now_datetime()
        today         = getdate()
        today_weekday = today.weekday()

        branches = _get_active_branches()
        if not branches:
            return

        created = []
        skipped = []
        errors  = []

        for row in settings.weekly_services:
            try:
                row_weekday = DAY_MAP.get(row.day)
                if row_weekday is None or row_weekday != today_weekday:
                    continue

                if not row.service or not row.time_from:
                    continue

                num_slots        = cint(row.no_of_service_per_day) or 1
                duration_minutes = int(float(row.duration or 1.5) * 60)

                slot_times = _calculate_slot_times(
                    base_time        = row.time_from,
                    num_slots        = num_slots,
                    duration_minutes = duration_minutes,
                    gap_minutes      = gap_minutes
                )

                for slot_idx, slot_time in enumerate(slot_times, start=1):
                    # Is this slot within the look-ahead window?
                    slot_dt       = get_datetime(f"{today} {slot_time}")
                    minutes_until = (slot_dt - now).total_seconds() / 60

                    if not (0 <= minutes_until <= LOOKAHEAD_MINUTES + SCHEDULER_INTERVAL):
                        continue

                    frappe.logger().info(
                        f"[AutoServiceCreator] Slot {slot_idx}/{num_slots} of "
                        f"'{row.service}' starts in {minutes_until:.1f}min — "
                        f"processing all branches."
                    )

                    for branch in branches:
                        try:
                            res = _process_slot_for_branch(
                                base_service_name = row.service,
                                branch            = branch,
                                slot_index        = slot_idx,
                                num_slots         = num_slots,
                                slot_time         = slot_time,
                                today             = today,
                                settings          = settings
                            )
                            svc_label = _slot_service_name(row.service, slot_idx, num_slots, branch)
                            if res == "created":
                                created.append(svc_label)
                            else:
                                skipped.append(f"{svc_label}: {res}")

                        except Exception as e:
                            err = f"Slot {slot_idx} @ {branch}: {str(e)}"
                            errors.append(err)
                            frappe.log_error(
                                frappe.get_traceback(),
                                f"AutoServiceCreator — {err}"
                            )

            except Exception as e:
                frappe.log_error(
                    frappe.get_traceback(),
                    f"AutoServiceCreator — row '{row.service}': {str(e)}"
                )

        if created or errors:
            frappe.logger().info(
                f"[AutoServiceCreator] Created: {len(created)}, "
                f"Skipped: {len(skipped)}, Errors: {len(errors)}. "
                f"Details: {created}"
            )

    except Exception:
        frappe.log_error(frappe.get_traceback(), "AutoServiceCreator — fatal error in cron")


def _process_slot_for_branch(
    base_service_name, branch, slot_index, num_slots,
    slot_time, today, settings
):
    """
    Create a Service Instance for one slot × one branch if not already existing.

    Returns:
        "created"            — new instance created
        "exists"             — already exists today
        "no_church_service"  — Church Service not found for this slot+branch (run Setup first)
    """
    church_service_name = _slot_service_name(
        base_service_name, slot_index, num_slots, branch
    )

    # Church Service must already exist (created by setup_church_services)
    if not frappe.db.exists('Church Service', church_service_name):
        frappe.logger().warning(
            f"[AutoServiceCreator] Church Service '{church_service_name}' not found. "
            f"Run Setup Church Services from Church Settings to create it."
        )
        return "no_church_service"

    # Service Instance already exists today?
    existing = frappe.db.exists('Service Instance', {
        'service':      church_service_name,
        'branch':       branch,
        'service_date': today
    })
    if existing:
        return "exists"

    # Create it
    instance_name = _create_service_instance(
        church_service_name = church_service_name,
        branch              = branch,
        slot_time           = slot_time,
        service_date        = today,
        settings            = settings
    )

    return "created" if instance_name else "no_church_service"


def _create_service_instance(
    church_service_name, branch, slot_time, service_date, settings
):
    """
    Create one Service Instance from its Church Service record.
    Returns the new instance name, or None on failure.
    """
    try:
        svc = frappe.get_doc('Church Service', church_service_name)

        si = frappe.new_doc('Service Instance')

        # Core
        si.service         = svc.name
        si.service_name    = svc.service_name
        si.service_type    = svc.service_type
        si.service_date    = service_date
        si.service_time    = slot_time
        si.status          = 'Scheduled'
        si.branch          = branch
        si.duration_minutes = svc.duration_minutes or 120

        # Location
        si.venue    = svc.venue    or ''
        si.capacity = svc.capacity or 0

        # Leadership
        si.minister       = svc.default_minister       or ''
        si.worship_leader = svc.default_worship_leader or ''
        si.choir          = svc.default_choir          or ''
        si.ushering_team  = svc.default_ushering_team  or ''

        # Settings
        si.enable_attendance_tracking = svc.enable_attendance_tracking or 1
        si.enable_offering_collection = svc.enable_offering_collection or 1
        si.enable_live_streaming      = svc.enable_live_streaming      or 0
        si.livestream_url             = svc.livestream_url             or ''
        si.auto_track_visitors        = svc.auto_track_visitors        or 1
        si.visitor_follow_up_enabled  = svc.visitor_follow_up_enabled  or 1
        si.follow_up_coordinator      = svc.default_follow_up_coordinator or ''
        si.service_order              = svc.service_order_template     or ''

        # Ministry team
        for tm in (svc.ministry_team or []):
            si.append('ministry_team', {
                'member':          tm.member         or '',
                'full_name':       tm.full_name      or '',
                'phone':           tm.phone          or '',
                'email':           tm.email          or '',
                'ministry_role':   tm.ministry_role  or '',
                'responsibility':  tm.responsibility or '',
                'present':         0
            })

        si.insert(ignore_permissions=True)
        frappe.db.commit()

        # Post-insert
        _generate_qr(si.name, settings)
        _notify_pastors(si, svc, settings)

        frappe.logger().info(
            f"[AutoServiceCreator] ✅ Instance created: {si.name}"
        )
        return si.name

    except Exception:
        frappe.log_error(
            frappe.get_traceback(),
            f"AutoServiceCreator — _create_service_instance failed: "
            f"{church_service_name} @ {branch}"
        )
        return None


# ============================================================================
# QR CODE GENERATION
# ============================================================================

def _generate_qr(instance_name, settings):
    """Generate and attach a venue QR to a Service Instance."""
    try:
        site_url    = frappe.utils.get_url()
        interval    = 10
        church_name = settings.church_name or ''
        now         = now_datetime()
        time_block  = int(now.timestamp() / (interval * 60))

        hash_input = f"{instance_name}{time_block}{church_name}"
        code       = f"CHK-{hashlib.sha256(hash_input.encode()).hexdigest()[:12].upper()}"
        checkin_url = f"{site_url}/checkin?code={code}&service={_url_quote(instance_name)}"

        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            box_size=10, border=4
        )
        qr.add_data(checkin_url)
        qr.make(fit=True)

        img    = qr.make_image(fill_color="black", back_color="white")
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)

        file_doc = save_file(
            fname=f"{instance_name}_venue_qr.png",
            content=buffer.getvalue(),
            dt="Service Instance",
            dn=instance_name,
            is_private=0
        )

        svc_vals = frappe.db.get_value(
            'Service Instance', instance_name,
            ['service_date', 'service_time'], as_dict=True
        )
        expiry = add_to_date(
            get_datetime(f"{svc_vals.service_date} {svc_vals.service_time}"),
            minutes=40
        )

        frappe.db.set_value(
            'Service Instance', instance_name,
            {
                'venue_qr_code':        file_doc.file_url,
                'venue_qr_checkin_url': checkin_url,
                'venue_qr_expires_at':  expiry,
                'venue_qr_code_hash':   code
            },
            update_modified=False
        )
        frappe.db.commit()

    except Exception:
        frappe.log_error(
            frappe.get_traceback(),
            f"AutoServiceCreator — QR failed for {instance_name}"
        )


# ============================================================================
# PASTOR NOTIFICATION
# ============================================================================

def _notify_pastors(si, svc, settings):
    """Email all active pastors when a Service Instance is auto-created."""
    try:
        pastors = frappe.get_all(
            'Member',
            filters={'is_a_pastor': 1, 'member_status': 'Active'},
            fields=['name', 'full_name', 'email']
        )
        if not pastors:
            return

        church_name      = settings.church_name or 'Church'
        site_url         = frappe.utils.get_url()
        display_url      = f"{site_url}/service-display?service={_url_quote(si.name)}"
        service_date_fmt = formatdate(si.service_date, "dddd, dd MMMM yyyy")
        service_time_fmt = str(si.service_time or '')
        service_name     = si.service_name or si.service or 'Service'
        branch_name      = si.branch or 'N/A'

        qr_url   = frappe.db.get_value('Service Instance', si.name, 'venue_qr_code') or ''
        qr_block = (
            f'<div style="text-align:center;margin:16px 0;">'
            f'<img src="{site_url}{qr_url}" '
            f'style="width:160px;height:160px;border:2px solid #e0e0e0;border-radius:8px;">'
            f'<p style="font-size:11px;color:#aaa;margin-top:4px;">'
            f'Venue QR — refreshes every 10 min</p></div>'
        ) if qr_url else ''

        for pastor in pastors:
            if not pastor.email:
                continue
            try:
                frappe.sendmail(
                    recipients=[pastor.email],
                    subject=(
                        f"⛪ Auto-Created: {service_name} [{branch_name}] "
                        f"— {service_date_fmt} at {service_time_fmt}"
                    ),
                    message=f"""
                    <div style="font-family:'Segoe UI',Arial,sans-serif;
                                max-width:600px;margin:0 auto;">
                        <div style="background:linear-gradient(135deg,#667eea,#764ba2);
                                    padding:24px;border-radius:12px 12px 0 0;
                                    text-align:center;color:white;">
                            <div style="font-size:32px;">⛪</div>
                            <h1 style="margin:6px 0 0;font-size:18px;font-weight:700;">
                                Service Instance Auto-Created
                            </h1>
                            <p style="margin:4px 0 0;opacity:0.8;font-size:13px;">
                                {church_name}
                            </p>
                        </div>
                        <div style="background:#fff;padding:24px;
                                    border-radius:0 0 12px 12px;
                                    border:1px solid #e8e8e8;">
                            <p style="font-size:15px;color:#2c3e50;">
                                Dear <strong>{pastor.full_name}</strong>,
                            </p>
                            <p style="color:#555;margin-bottom:16px;">
                                A Service Instance was automatically created
                                <strong>10 minutes before the service.</strong>
                            </p>
                            <div style="background:#f8f6ff;border-left:4px solid #667eea;
                                        padding:14px;border-radius:8px;margin-bottom:16px;">
                                <table style="width:100%;font-size:13px;
                                              color:#2c3e50;border-collapse:collapse;">
                                    <tr><td style="padding:4px 0;width:110px;">
                                        <strong>Service:</strong></td>
                                        <td>{service_name}</td></tr>
                                    <tr><td style="padding:4px 0;">
                                        <strong>Branch:</strong></td>
                                        <td>{branch_name}</td></tr>
                                    <tr><td style="padding:4px 0;">
                                        <strong>Date:</strong></td>
                                        <td>{service_date_fmt}</td></tr>
                                    <tr><td style="padding:4px 0;">
                                        <strong>Time:</strong></td>
                                        <td>{service_time_fmt}</td></tr>
                                    <tr><td style="padding:4px 0;">
                                        <strong>Venue:</strong></td>
                                        <td>{si.venue or 'N/A'}</td></tr>
                                    <tr><td style="padding:4px 0;">
                                        <strong>Record:</strong></td>
                                        <td style="font-family:monospace;font-size:11px;">
                                            {si.name}</td></tr>
                                </table>
                            </div>
                            <div style="background:#e8f5e9;border-left:4px solid #27ae60;
                                        padding:14px;border-radius:8px;margin-bottom:16px;">
                                <p style="margin:0 0 8px;font-weight:700;
                                           color:#1a6b35;font-size:13px;">
                                    📺 Display QR on Screen
                                </p>
                                <a href="{display_url}"
                                   style="display:inline-block;background:#27ae60;
                                          color:white;padding:9px 18px;border-radius:8px;
                                          text-decoration:none;font-weight:600;font-size:13px;">
                                    📺 Open Display Screen →
                                </a>
                            </div>
                            {qr_block}
                            <div style="background:#fff8e1;border-left:4px solid #f39c12;
                                        padding:10px 14px;border-radius:8px;">
                                <p style="margin:0;font-size:12px;color:#8b6914;">
                                    ⏰ QR expires 40 minutes after service time.
                                </p>
                            </div>
                            <p style="font-size:13px;color:#555;margin-top:16px;">
                                God bless,<br>
                                <strong>{church_name} Management System</strong>
                            </p>
                        </div>
                    </div>
                    """,
                    delayed=False,
                    now=True
                )
            except Exception:
                frappe.log_error(
                    frappe.get_traceback(),
                    f"AutoServiceCreator — pastor email failed: {pastor.name}"
                )

    except Exception:
        frappe.log_error(frappe.get_traceback(), "AutoServiceCreator — _notify_pastors")


# ============================================================================
# HELPERS
# ============================================================================

def _slot_service_name(base_name, slot_index, num_slots, branch):
    """
    Build the Church Service name for a specific slot and branch.

    num_slots=1 → "Sunday Service - Lagos"
    num_slots=2 → "Sunday Service - 1st Service - Lagos"
    num_slots=3 → "Sunday Service - 2nd Service - Lagos"
    """
    if num_slots <= 1:
        return f"{base_name} - {branch}"
    ordinal = ORDINAL_SUFFIXES.get(slot_index, f"{slot_index}th")
    return f"{base_name} - {ordinal} Service - {branch}"


def _calculate_slot_times(base_time, num_slots, duration_minutes, gap_minutes):
    """
    Calculate start time for each slot.

    Args:
        base_time        : str or time object — start of first slot (e.g. "07:00:00")
        num_slots        : int — total number of slots
        duration_minutes : int — duration of each slot in minutes
        gap_minutes      : int — break between end of one slot and start of next

    Returns:
        list of time strings ["07:00:00", "09:30:00", ...]
    """
    # Parse base_time to a datetime for arithmetic
    if hasattr(base_time, 'hour'):
        # It's a timedelta or time object from Frappe
        total_seconds = int(base_time.total_seconds()) if hasattr(base_time, 'total_seconds') else 0
        if total_seconds == 0:
            # It's a datetime.time
            total_seconds = base_time.hour * 3600 + base_time.minute * 60 + base_time.second
        base_minutes_from_midnight = total_seconds // 60
    else:
        # It's a string like "07:00:00" or "07:00"
        parts = str(base_time).split(':')
        base_minutes_from_midnight = int(parts[0]) * 60 + int(parts[1])

    slot_times = []
    current_start = base_minutes_from_midnight

    for _ in range(num_slots):
        hours   = current_start // 60
        minutes = current_start % 60
        slot_times.append(f"{hours:02d}:{minutes:02d}:00")
        # Next slot starts after: this slot's duration + gap
        current_start += duration_minutes + gap_minutes

    return slot_times


def _get_active_branches():
    """Return names of all active branches."""
    try:
        branches = frappe.get_all('Branch', filters={'is_active': 1}, pluck='name')
        if branches:
            return branches
        branches = frappe.get_all('Branch', filters={'status': 'Active'}, pluck='name')
        if branches:
            return branches
        return frappe.get_all('Branch', pluck='name')
    except Exception:
        frappe.log_error(frappe.get_traceback(), "AutoServiceCreator — _get_active_branches")
        return []


# ============================================================================
# MANUAL TRIGGERS  (whitelisted)
# ============================================================================

@frappe.whitelist()
def manual_create_instances_for_service(service_name, service_date=None):
    """
    Manually create Service Instances for a specific Church Service name
    (already slot-qualified, e.g. "Sunday Service - 1st Service - Lagos")
    or a base service name across all branches and slots.

    Args:
        service_name : Church Service name or base service name
        service_date : YYYY-MM-DD string, defaults to today
    """
    try:
        settings    = frappe.get_single('Church Settings')
        gap_minutes = cint(getattr(settings, 'service_gap_minutes', DEFAULT_GAP_MINUTES)) or DEFAULT_GAP_MINUTES
        target_date = getdate(service_date) if service_date else getdate()
        branches    = _get_active_branches()

        created  = {}
        skipped  = []
        errors   = []

        day_abbr = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][target_date.weekday()]

        # Find matching weekly_services row
        matching_row = None
        for row in (settings.weekly_services or []):
            if row.service == service_name and row.day == day_abbr:
                matching_row = row
                break

        if not matching_row:
            # Try all rows for this service regardless of day
            for row in (settings.weekly_services or []):
                if row.service == service_name:
                    matching_row = row
                    break

        if not matching_row:
            return {
                'success': False,
                'message': f"No weekly_services row found for '{service_name}'."
            }

        num_slots        = cint(matching_row.no_of_service_per_day) or 1
        duration_minutes = int(float(matching_row.duration or 1.5) * 60)
        slot_times       = _calculate_slot_times(
            matching_row.time_from, num_slots, duration_minutes, gap_minutes
        )

        for slot_idx, slot_time in enumerate(slot_times, start=1):
            for branch in branches:
                try:
                    res = _process_slot_for_branch(
                        base_service_name = matching_row.service,
                        branch            = branch,
                        slot_index        = slot_idx,
                        num_slots         = num_slots,
                        slot_time         = slot_time,
                        today             = target_date,
                        settings          = settings
                    )
                    label = _slot_service_name(service_name, slot_idx, num_slots, branch)
                    if res == "created":
                        inst = frappe.db.get_value(
                            'Service Instance',
                            {
                                'service':      label,
                                'branch':       branch,
                                'service_date': target_date
                            },
                            'name'
                        )
                        created[label] = inst
                    else:
                        skipped.append(f"{label}: {res}")
                except Exception as e:
                    errors.append(f"Slot {slot_idx} @ {branch}: {str(e)}")

        return {
            'success':  True,
            'created':  created,
            'skipped':  skipped,
            'errors':   errors,
            'message':  (
                f"Done. Created: {len(created)}, "
                f"Skipped: {len(skipped)}, Errors: {len(errors)}."
            )
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "manual_create_instances_for_service")
        return {'success': False, 'message': str(e)}


@frappe.whitelist()
def trigger_now():
    """Run the full auto-creation check immediately (ignores time window)."""
    auto_create_service_instances()
    return {'success': True, 'message': 'Check completed. See error logs for details.'}