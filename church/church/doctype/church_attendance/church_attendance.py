# -*- coding: utf-8 -*-
# Copyright (c) 2026, Church Management
# License: MIT
#
# church/church/doctype/church_attendance/church_attendance.py
# ─────────────────────────────────────────────────────────────────────────────

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import (
    getdate, nowdate, nowtime, get_time, now_datetime,
    add_days, today, formatdate, cint, flt, escape_html,
)
from frappe.utils.data import get_url


# ─────────────────────────────────────────────────────────────────────────────
#  CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────

# Fields on Member that mark someone as a branch leader / responsible party.
# Any member whose branch matches AND any of these is 1 will receive
# pastoral / absent-member reports for that branch.
LEADER_FLAGS = (
    "is_a_pastor",
    "is_hod",
    "is_cancellor",
    "is_follow_up_cordinator",
    "is_men_president",
    "is_women_president",
    "is_youth_president",
    "is_teenager_president",
)

# Sunday service types that must fall on a Sunday.
SUNDAY_SERVICE_TYPES = ("Sunday Service", "Sunday School")


# ─────────────────────────────────────────────────────────────────────────────
#  DOCUMENT CLASS
# ─────────────────────────────────────────────────────────────────────────────

class ChurchAttendance(Document):

    # ── Lifecycle hooks ───────────────────────────────────────────────────────

    def validate(self):
        self._validate_duplicate_attendance()
        self._validate_service_date()
        self._validate_sunday_school_fields()
        self._set_defaults()

    def before_insert(self):
        self._set_marked_details()

    def on_submit(self):
        self._update_attendance_sheet()
        self._update_service_instance()
        # Enqueue so the API response returns immediately (QR, bulk, etc.)
        frappe.enqueue(
            "church.church.doctype.church_attendance.church_attendance"
            "._enqueued_send_confirmation",
            attendance_name=self.name,
            queue="short",
            now=frappe.flags.in_test,
        )

    def on_cancel(self):
        self._update_attendance_sheet()
        self._update_service_instance()

    # ── Validation helpers ────────────────────────────────────────────────────

    def _validate_duplicate_attendance(self):
        if not (self.member_id and self.service_date and self.service_type):
            return

        duplicate = frappe.db.exists(
            "Church Attendance",
            {
                "member_id":    self.member_id,
                "service_date": self.service_date,
                "service_type": self.service_type,
                "name":         ["!=", self.name],
                "docstatus":    ["!=", 2],
            },
        )
        if duplicate:
            frappe.throw(
                _("Attendance already exists for {0} on {1} for {2}.").format(
                    frappe.bold(self.full_name or self.member_id),
                    frappe.format(self.service_date, {"fieldtype": "Date"}),
                    frappe.bold(self.service_type),
                ),
                title=_("Duplicate Attendance"),
            )

    def _validate_service_date(self):
        if not (self.service_date and self.service_type):
            return
        if self.service_type in SUNDAY_SERVICE_TYPES:
            service_date = getdate(self.service_date)
            if service_date.weekday() != 6:  # 6 = Sunday
                frappe.throw(
                    _("{0} must be recorded on a Sunday. The selected date is {1}.").format(
                        frappe.bold(self.service_type),
                        frappe.bold(service_date.strftime("%A, %d %b %Y")),
                    )
                )

    def _validate_sunday_school_fields(self):
        if self.service_type == "Sunday School" and not self.sunday_school_class:
            frappe.throw(
                _("Sunday School Class is required for Sunday School attendance."),
                title=_("Missing Field"),
            )

    # ── Defaults ──────────────────────────────────────────────────────────────

    def _set_defaults(self):
        if not self.branch and self.member_id:
            self.branch = frappe.db.get_value("Member", self.member_id, "branch")

    def _set_marked_details(self):
        if not self.marked_by:
            self.marked_by = frappe.session.user
        if not self.marked_at:
            self.marked_at = now_datetime()

    # ── Related-document updates ──────────────────────────────────────────────

    def _update_attendance_sheet(self):
        if not (self.service_date and self.branch):
            return
        sheet = frappe.db.get_value(
            "Attendance Sheet",
            {"reporting_date": self.service_date, "branch": self.branch},
            "name",
        )
        if sheet:
            frappe.enqueue(
                "church.church.doctype.attendance_sheet"
                ".attendance_sheet.recalculate_attendance",
                attendance_sheet=sheet,
                queue="short",
                now=frappe.flags.in_test,
            )

    def _update_service_instance(self):
        if not self.service_instance:
            return
        frappe.enqueue(
            "church.church.doctype.service_instance"
            ".service_instance.update_attendance_count",
            service_instance=self.service_instance,
            queue="short",
            now=frappe.flags.in_test,
        )


# ─────────────────────────────────────────────────────────────────────────────
#  EMAIL HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _get_church_context():
    """
    Return a dict with church_name and church_logo (absolute URL).
    Logo comes from the Company DocType (company_logo_url field).
    Church name comes from Church Settings.
    """
    church_name = (
        frappe.db.get_single_value("Church Settings", "church_name") or "Our Church"
    )

    # company_logo_url lives on the Company DocType (not a Single)
    # Use the default company for the site.
    company_name = frappe.db.get_default("company")
    church_logo  = ""
    if company_name:
        raw_logo = frappe.db.get_value("Company", company_name, "company_logo") or ""
        if raw_logo:
            church_logo = (get_url() + raw_logo) if raw_logo.startswith("/") else raw_logo

    return {"church_name": church_name, "church_logo": church_logo}


def _email_wrapper(body_html: str, church_name: str, church_logo: str) -> str:
    """
    Wraps any body HTML in the standard branded blue container.
    All user-supplied strings interpolated here must already be escape_html()-safe.
    """
    logo_block = (
        f'<img src="{church_logo}" alt="{church_name}" class="logo" '
        f'onerror="this.style.display=\'none\'">'
        if church_logo else ""
    )
    year = getdate(nowdate()).year

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{church_name}</title>
<style>
  /* ── Reset ── */
  body,table,td,p,a{{margin:0;padding:0;border:0;}}
  body{{background:#e8f0fe;font-family:'Segoe UI',Arial,sans-serif;}}
  /* ── Outer wrapper ── */
  .wrapper{{width:100%;background:#e8f0fe;padding:40px 16px;}}
  /* ── Card ── */
  .card{{max-width:600px;margin:0 auto;background:#ffffff;
         border-radius:20px;overflow:hidden;
         box-shadow:0 8px 40px rgba(26,63,144,0.18);}}
  /* ── Header ── */
  .hdr{{background:linear-gradient(135deg,#1a3f90 0%,#2563eb 100%);
        padding:36px 40px 28px;text-align:center;}}
  .logo{{width:88px;height:88px;border-radius:50%;
         object-fit:cover;border:3px solid rgba(255,255,255,0.35);
         margin-bottom:14px;display:block;margin-left:auto;margin-right:auto;}}
  .hdr-title{{color:#ffffff;font-size:22px;font-weight:700;
              letter-spacing:.4px;margin:0 0 4px;}}
  .hdr-sub{{color:rgba(255,255,255,.80);font-size:13px;margin:0;}}
  /* ── Body ── */
  .body{{padding:36px 40px 28px;}}
  .greeting{{font-size:20px;font-weight:700;color:#1a3f90;margin:0 0 12px;}}
  .greeting span{{border-bottom:3px solid #2563eb;padding-bottom:3px;}}
  .lead{{font-size:15px;color:#374151;line-height:1.65;margin:0 0 24px;}}
  /* ── Info card ── */
  .info-card{{background:#f0f6ff;border:1px solid #bfdbfe;
              border-radius:14px;padding:24px;margin:0 0 24px;}}
  .info-card .badge{{display:inline-block;
                     background:linear-gradient(135deg,#1a3f90,#2563eb);
                     color:#fff;font-size:14px;font-weight:600;
                     padding:8px 22px;border-radius:999px;
                     margin-bottom:18px;letter-spacing:.3px;}}
  .info-row{{display:flex;align-items:center;
             background:#fff;border-radius:999px;
             padding:10px 16px;margin:8px 0;
             box-shadow:0 1px 3px rgba(0,0,0,.06);}}
  .info-icon{{font-size:18px;width:28px;text-align:center;margin-right:12px;}}
  .info-label{{color:#6b7280;font-size:13px;font-weight:500;width:80px;}}
  .info-value{{color:#111827;font-size:14px;font-weight:600;flex:1;}}
  .status-ok{{color:#16a34a;}}
  /* ── Verse box ── */
  .verse{{background:#fff;border-left:4px solid #2563eb;
          border-radius:10px;padding:18px 22px;
          margin:0 0 24px;text-align:center;}}
  .verse p{{font-size:15px;font-style:italic;color:#1e40af;
            line-height:1.7;margin:0 0 6px;}}
  .verse cite{{font-size:12px;color:#6b7280;}}
  /* ── Footer ── */
  .ftr{{background:#f8faff;border-top:1px solid #dbeafe;
        padding:24px 40px 20px;text-align:center;}}
  .ftr p{{font-size:12px;color:#6b7280;line-height:1.7;margin:4px 0;}}
  .ftr strong{{color:#1a3f90;}}
  /* ── Responsive ── */
  @media(max-width:600px){{
    .body,.ftr{{padding:28px 24px 20px;}}
    .hdr{{padding:28px 24px 20px;}}
  }}
</style>
</head>
<body>
<div class="wrapper">
  <div class="card">
    <div class="hdr">
      {logo_block}
      <h1 class="hdr-title">{church_name}</h1>
      <p class="hdr-sub">Church Management System</p>
    </div>
    <div class="body">
      {body_html}
    </div>
    <div class="ftr">
      <p><strong>{church_name}</strong></p>
      <p>This is an automated message — please do not reply directly.</p>
      <p>&copy; {year} {church_name}. All rights reserved.</p>
      <p style="margin-top:10px;">🙏 God bless you abundantly!</p>
    </div>
  </div>
</div>
</body>
</html>"""


# ─────────────────────────────────────────────────────────────────────────────
#  ATTENDANCE CONFIRMATION EMAIL
# ─────────────────────────────────────────────────────────────────────────────

def _enqueued_send_confirmation(attendance_name: str):
    """Worker function — called by the enqueue in on_submit."""
    try:
        doc = frappe.get_doc("Church Attendance", attendance_name)
        _send_confirmation_email(doc)
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Attendance Confirmation Email Error")


def _send_confirmation_email(doc):
    """Build and dispatch the attendance confirmation email."""
    if not doc.member_id:
        return

    member_email = frappe.db.get_value("Member", doc.member_id, "email")
    if not member_email:
        return

    ctx          = _get_church_context()
    member_name  = escape_html(doc.full_name or doc.member_id)
    service_type = escape_html(doc.service_type or "Service")
    branch       = escape_html(doc.branch or "")
    formatted_dt = frappe.format(doc.service_date, {"fieldtype": "Date"})

    time_row = ""
    if doc.time_in:
        formatted_time = frappe.format(doc.time_in, {"fieldtype": "Time"})
        time_row = f"""
        <div class="info-row">
          <span class="info-icon">⏱️</span>
          <span class="info-label">Time In</span>
          <span class="info-value">{escape_html(formatted_time)}</span>
        </div>"""

    ss_row = ""
    if doc.sunday_school_class:
        ss_row = f"""
        <div class="info-row">
          <span class="info-icon">📚</span>
          <span class="info-label">Class</span>
          <span class="info-value">{escape_html(doc.sunday_school_class)}</span>
        </div>"""

    branch_row = ""
    if branch:
        branch_row = f"""
        <div class="info-row">
          <span class="info-icon">📍</span>
          <span class="info-label">Branch</span>
          <span class="info-value">{branch}</span>
        </div>"""

    body = f"""
    <p class="greeting">Hello, <span>{member_name}</span></p>
    <p class="lead">
      Your attendance has been confirmed. We are glad you joined us —
      your presence enriches our community!
    </p>

    <div class="info-card">
      <div style="text-align:center;">
        <div class="badge">{service_type}</div>
      </div>
      <div class="info-row">
        <span class="info-icon">📅</span>
        <span class="info-label">Date</span>
        <span class="info-value">{escape_html(formatted_dt)}</span>
      </div>
      {time_row}
      {branch_row}
      {ss_row}
      <div class="info-row">
        <span class="info-icon">✅</span>
        <span class="info-label">Status</span>
        <span class="info-value status-ok">Confirmed ✓</span>
      </div>
    </div>

    <div class="verse">
      <p>"Let us not give up meeting together, as some are in the habit of doing,
         but let us encourage one another."</p>
      <cite>— Hebrews 10:25</cite>
    </div>

    <p class="lead" style="text-align:center;font-size:14px;color:#6b7280;">
      We look forward to seeing you at our next service!
    </p>"""

    frappe.sendmail(
        recipients=[member_email],
        subject=f"✅ Attendance Confirmed — {service_type}",
        message=_email_wrapper(body, ctx["church_name"], ctx["church_logo"]),
    )


# ─────────────────────────────────────────────────────────────────────────────
#  ABSENT MEMBER — INDIVIDUAL ENCOURAGEMENT EMAIL
# ─────────────────────────────────────────────────────────────────────────────

def send_absent_member_emails():
    """
    Scheduled daily.
    Sends a warm encouragement email to every active member who was absent
    from today's service.  Bails early if no submitted attendance exists for
    today (i.e. no service ran today).
    """
    today_date = today()

    # Guard: only proceed if a service actually happened today
    service_dates = frappe.get_all(
        "Church Attendance",
        filters={"service_date": today_date, "docstatus": 1},
        fields=["member_id", "branch"],
        limit=0,
    )
    if not service_dates:
        return  # No service today — nothing to do

    attended_ids = {r.member_id for r in service_dates if r.member_id}

    active_members = frappe.get_all(
        "Member",
        filters={"member_status": "Active"},
        fields=["name", "full_name", "email"],
        limit=0,
    )

    ctx = _get_church_context()

    for member in active_members:
        if member.name in attended_ids:
            continue
        if not member.email:
            continue
        try:
            _send_absent_encouragement_email(member, today_date, ctx)
        except Exception:
            frappe.log_error(
                frappe.get_traceback(),
                f"Absent Email Error — {member.name}",
            )

    frappe.db.commit()


def _send_absent_encouragement_email(member, date_str: str, ctx: dict):
    """Send a warm 'we missed you' email to a single absent member."""
    member_name  = escape_html(member.full_name or member.name)
    church_name  = ctx["church_name"]
    church_logo  = ctx["church_logo"]
    formatted_dt = formatdate(date_str)

    body = f"""
    <p class="greeting">Dear <span>{member_name}</span>,</p>
    <p class="lead">
      We noticed you were not able to join us for worship on
      <strong>{escape_html(formatted_dt)}</strong>.
      We just want you to know that <strong>you were missed</strong>.
    </p>

    <div class="info-card">
      <div style="text-align:center;margin-bottom:4px;">
        <div class="badge">You are loved ❤️</div>
      </div>
      <p style="font-size:14px;color:#374151;line-height:1.65;margin:12px 0 0;">
        We pray that the Lord strengthens you, fills your heart with peace,
        and guides your steps throughout this week. Whatever season you may
        be walking through, your church family is here for you.
      </p>
    </div>

    <div class="verse">
      <p>"The Lord bless you and keep you; the Lord make His face shine upon you
         and be gracious to you."</p>
      <cite>— Numbers 6:24–25</cite>
    </div>

    <p class="lead" style="text-align:center;font-size:14px;color:#6b7280;">
      We look forward to worshipping together again soon. 🙏
    </p>"""

    frappe.sendmail(
        recipients=[member.email],
        subject=f"We Missed You Today at {church_name}",
        message=_email_wrapper(body, church_name, church_logo),
        delayed=True,
    )


# ─────────────────────────────────────────────────────────────────────────────
#  ABSENT MEMBER REPORT — BRANCH LEADERS
# ─────────────────────────────────────────────────────────────────────────────

def send_absent_member_report():
    """
    Scheduled (typically after each service day).
    Compiles a branch-aware absent-member report and emails it to all
    qualified branch leaders (any of the LEADER_FLAGS set to 1).
    """
    today_date = today()

    attendance_records = frappe.get_all(
        "Church Attendance",
        filters={"service_date": today_date, "docstatus": 1},
        fields=["member_id", "branch"],
        limit=0,
    )
    if not attendance_records:
        return  # No service today

    # Build  branch → set(attended member_ids)
    attended_by_branch: dict[str, set] = {}
    for rec in attendance_records:
        branch = rec.branch or ""   # keep None-branch as empty string consistently
        member = rec.member_id
        if not member:
            continue
        attended_by_branch.setdefault(branch, set()).add(member)

    active_members = frappe.get_all(
        "Member",
        filters={"member_status": "Active"},
        fields=["name", "full_name", "email", "mobile_phone",
                "demographic_group", "branch"],
        limit=0,
    )

    # Build  branch → [absent member dicts]
    absent_by_branch: dict[str, list] = {}
    for m in active_members:
        branch = m.branch or ""
        if m.name not in attended_by_branch.get(branch, set()):
            absent_by_branch.setdefault(branch, []).append(m)

    if not absent_by_branch:
        return

    ctx = _get_church_context()

    for branch, absent_members in absent_by_branch.items():
        recipients = _get_branch_leader_emails(branch)
        if not recipients:
            continue
        try:
            _send_leader_absent_report(
                absent_members, today_date, branch, recipients, ctx
            )
        except Exception:
            frappe.log_error(
                frappe.get_traceback(),
                f"Leader Absent Report Error — branch: {branch}",
            )


def _get_branch_leader_emails(branch: str) -> list[str]:
    """
    Return email addresses of all active members in `branch` who hold
    at least one leadership role defined in LEADER_FLAGS.
    An empty branch string matches members whose branch field is also empty.
    """
    # Build OR filter: any leader flag == 1
    or_filters = [[flag, "=", 1] for flag in LEADER_FLAGS]

    candidates = frappe.get_all(
        "Member",
        filters={
            "member_status": "Active",
            "branch":        branch,
            "email":         ["is", "set"],
        },
        or_filters=or_filters,
        fields=["email"] + list(LEADER_FLAGS),
        limit=0,
    )

    emails = []
    for c in candidates:
        # Double-check: at least one flag is truly set (defensive against OR-filter edge cases)
        if any(cint(c.get(flag)) for flag in LEADER_FLAGS):
            if c.email and c.email not in emails:
                emails.append(c.email)
    return emails


def _build_absent_table(absent_members: list) -> str:
    """Return an HTML table of absent members (escaped)."""
    rows = ""
    for idx, m in enumerate(absent_members, 1):
        bg = "#f8faff" if idx % 2 == 0 else "#ffffff"
        rows += f"""
        <tr style="background:{bg};">
          <td style="{_td()}">{escape_html(m.full_name or "")}</td>
          <td style="{_td()}">{escape_html(m.mobile_phone or "")}</td>
          <td style="{_td()}">{escape_html(m.email or "")}</td>
          <td style="{_td()}">{escape_html(m.demographic_group or "")}</td>
        </tr>"""

    return f"""
    <table width="100%" cellpadding="0" cellspacing="0"
           style="border-collapse:collapse;width:100%;
                  font-family:'Segoe UI',Arial,sans-serif;
                  font-size:13px;border-radius:10px;overflow:hidden;">
      <thead>
        <tr style="background:linear-gradient(135deg,#1a3f90,#2563eb);color:#fff;">
          <th style="{_th()}">Full Name</th>
          <th style="{_th()}">Phone</th>
          <th style="{_th()}">Email</th>
          <th style="{_th()}">Demographic Group</th>
        </tr>
      </thead>
      <tbody>{rows}</tbody>
    </table>"""


def _th() -> str:
    return "padding:11px 14px;text-align:left;font-weight:600;white-space:nowrap;"

def _td() -> str:
    return "padding:10px 14px;border-bottom:1px solid #e5e7eb;color:#374151;vertical-align:top;"


def _send_leader_absent_report(
    absent_members: list,
    date_str: str,
    branch: str,
    recipients: list[str],
    ctx: dict,
):
    church_name  = ctx["church_name"]
    church_logo  = ctx["church_logo"]
    branch_label = escape_html(branch) if branch else "Unassigned Branch"
    total        = len(absent_members)
    formatted_dt = formatdate(date_str)
    table_html   = _build_absent_table(absent_members)

    body = f"""
    <p class="greeting">Pastoral Report — <span>{branch_label}</span></p>
    <p class="lead">
      The following <strong>{total} member{'' if total == 1 else 's'}</strong>
      from <strong>{branch_label}</strong> were not recorded in attendance
      for the service held on <strong>{escape_html(formatted_dt)}</strong>.
    </p>

    <div style="margin:0 0 24px;">
      {table_html}
    </div>

    <div class="verse">
      <p>"Carry each other's burdens, and in this way you will fulfil the law of Christ."</p>
      <cite>— Galatians 6:2</cite>
    </div>

    <p class="lead" style="font-size:13px;color:#6b7280;">
      Please consider reaching out for pastoral care, encouragement,
      or follow-up where necessary. This report is confidential and
      intended for pastoral leadership only.
    </p>"""

    frappe.sendmail(
        recipients=recipients,
        subject=f"{church_name} — Absent Members Report | {branch_label} | {formatted_dt}",
        message=_email_wrapper(body, church_name, church_logo),
        delayed=True,
    )


# ─────────────────────────────────────────────────────────────────────────────
#  ATTENDANCE REMINDERS (members not seen in 2 weeks)
# ─────────────────────────────────────────────────────────────────────────────

def send_attendance_reminders():
    """
    Scheduled weekly.
    Emails members who have not appeared in any submitted attendance
    record in the past 14 days.
    """
    two_weeks_ago = add_days(nowdate(), -14)

    recent_ids = {
        r.member_id
        for r in frappe.get_all(
            "Church Attendance",
            filters={
                "service_date": [">=", two_weeks_ago],
                "docstatus":    1,
            },
            fields=["member_id"],
            limit=0,
        )
        if r.member_id
    }

    active_members = frappe.get_all(
        "Member",
        filters={"member_status": "Active"},
        fields=["name", "full_name", "email"],
        limit=0,
    )

    ctx = _get_church_context()

    for member in active_members:
        if member.name in recent_ids or not member.email:
            continue
        try:
            _send_reminder_email(member, ctx)
        except Exception:
            frappe.log_error(
                frappe.get_traceback(),
                f"Attendance Reminder Error — {member.name}",
            )


def _send_reminder_email(member, ctx: dict):
    member_name = escape_html(member.full_name or member.name)
    church_name = ctx["church_name"]
    church_logo = ctx["church_logo"]

    body = f"""
    <p class="greeting">Dear <span>{member_name}</span>,</p>
    <p class="lead">
      We noticed you haven't been able to join us recently, and we
      simply want you to know that <strong>you are missed</strong> and
      <strong>always welcome home</strong>.
    </p>

    <div class="info-card">
      <div style="text-align:center;margin-bottom:4px;">
        <div class="badge">You are always welcome ⛪</div>
      </div>
      <p style="font-size:14px;color:#374151;line-height:1.65;margin:12px 0 0;">
        Whatever you have been walking through, we are here for you.
        Come as you are — your church family cannot wait to worship
        alongside you again.
      </p>
    </div>

    <div class="verse">
      <p>"Cast all your anxiety on Him because He cares for you."</p>
      <cite>— 1 Peter 5:7</cite>
    </div>

    <p class="lead" style="text-align:center;font-size:14px;color:#6b7280;">
      We hope to see you this Sunday. 🙏
    </p>"""

    frappe.sendmail(
        recipients=[member.email],
        subject=f"We Miss You — {church_name}",
        message=_email_wrapper(body, church_name, church_logo),
        delayed=True,
    )


# ─────────────────────────────────────────────────────────────────────────────
#  MEMBER FOLLOW-UP ESCALATION SYSTEM
# ─────────────────────────────────────────────────────────────────────────────

def run_member_followup_monitor():
    """
    Scheduled (e.g. every Sunday evening after service).
    For each active member, counts how many of the last N Sunday Services
    they missed and escalates accordingly:
      2 missed → warm personal email to member
      3 missed → alert demographic group leaders
      4+missed → create pastoral ToDo assigned to branch pastor
    Only runs if a Sunday Service was actually submitted today.
    """
    today_date = today()

    # Guard: only run on actual service days
    service_ran = frappe.db.exists(
        "Church Attendance",
        {"service_date": today_date, "service_type": "Sunday Service", "docstatus": 1},
    )
    if not service_ran:
        return

    active_members = frappe.get_all(
        "Member",
        filters={"member_status": "Active"},
        fields=["name", "full_name", "email", "mobile_phone",
                "branch", "demographic_group"],
        limit=0,
    )

    ctx = _get_church_context()

    for member in active_members:
        try:
            missed = _calculate_missed_sunday_services(member.name)
            if missed == 2:
                _send_second_absence_email(member, ctx)
            elif missed == 3:
                _notify_group_leaders(member, ctx)
            elif missed >= 4:
                _create_pastoral_care_task(member, ctx)
        except Exception:
            frappe.log_error(
                frappe.get_traceback(),
                f"Follow-Up Monitor Error — {member.name}",
            )

    frappe.db.commit()


def _calculate_missed_sunday_services(member_id: str) -> int:
    """
    Return how many of the last 4 distinct Sunday Service dates the
    given member was absent from.
    """
    # The 4 most recent distinct service dates that had submitted records
    recent_service_dates = frappe.db.sql(
        """
        SELECT DISTINCT service_date
        FROM   `tabChurch Attendance`
        WHERE  service_type = 'Sunday Service'
          AND  docstatus    = 1
        ORDER  BY service_date DESC
        LIMIT  4
        """,
        as_dict=True,
    )

    if not recent_service_dates:
        return 0

    missed = 0
    for row in recent_service_dates:
        was_present = frappe.db.exists(
            "Church Attendance",
            {
                "member_id":    member_id,
                "service_date": row.service_date,
                "service_type": "Sunday Service",
                "docstatus":    1,
            },
        )
        if not was_present:
            missed += 1

    return missed


def _send_second_absence_email(member, ctx: dict):
    if not member.email:
        return

    member_name = escape_html(member.full_name or member.name)
    church_name = ctx["church_name"]
    church_logo = ctx["church_logo"]

    body = f"""
    <p class="greeting">Dear <span>{member_name}</span>,</p>
    <p class="lead">
      We have missed your presence over the last couple of Sundays
      and just wanted to take a moment to check in on you.
    </p>

    <div class="info-card">
      <p style="font-size:14px;color:#374151;line-height:1.65;margin:0;">
        We hope everything is well with you and your family.
        Please know that our doors are always open, and our hearts
        are full of love for you.
      </p>
    </div>

    <div class="verse">
      <p>"Where can I go from Your Spirit? Where can I flee from Your presence?"</p>
      <cite>— Psalm 139:7</cite>
    </div>

    <p class="lead" style="text-align:center;font-size:14px;color:#6b7280;">
      Your church family is praying for you. 🙏
    </p>"""

    frappe.sendmail(
        recipients=[member.email],
        subject=f"{church_name} — We've Been Thinking of You",
        message=_email_wrapper(body, church_name, church_logo),
        delayed=True,
    )


def _notify_group_leaders(member, ctx: dict):
    """Alert the member's demographic group leaders in their branch."""
    leaders = _get_group_leader_emails(
        member.demographic_group or "", member.branch or ""
    )
    if not leaders:
        return

    member_name    = escape_html(member.full_name or member.name)
    branch_label   = escape_html(member.branch or "Unassigned")
    demographic    = escape_html(member.demographic_group or "N/A")
    phone          = escape_html(member.mobile_phone or "—")
    email          = escape_html(member.email or "—")
    church_name    = ctx["church_name"]
    church_logo    = ctx["church_logo"]

    body = f"""
    <p class="greeting">Follow-Up Required</p>
    <p class="lead">
      The member below has missed <strong>3 consecutive Sunday services</strong>
      and may need pastoral encouragement or a welfare check.
    </p>

    <div class="info-card">
      <div class="info-row">
        <span class="info-icon">👤</span>
        <span class="info-label">Name</span>
        <span class="info-value">{member_name}</span>
      </div>
      <div class="info-row">
        <span class="info-icon">📞</span>
        <span class="info-label">Phone</span>
        <span class="info-value">{phone}</span>
      </div>
      <div class="info-row">
        <span class="info-icon">📧</span>
        <span class="info-label">Email</span>
        <span class="info-value">{email}</span>
      </div>
      <div class="info-row">
        <span class="info-icon">👥</span>
        <span class="info-label">Group</span>
        <span class="info-value">{demographic}</span>
      </div>
      <div class="info-row">
        <span class="info-icon">📍</span>
        <span class="info-label">Branch</span>
        <span class="info-value">{branch_label}</span>
      </div>
    </div>

    <div class="verse">
      <p>"Carry each other's burdens, and in this way you will fulfil the law of Christ."</p>
      <cite>— Galatians 6:2</cite>
    </div>

    <p class="lead" style="font-size:13px;color:#6b7280;">
      Please reach out to this member with care and prayer.
      This notification is confidential.
    </p>"""

    frappe.sendmail(
        recipients=leaders,
        subject=f"{church_name} — Follow-Up Needed: {member.full_name}",
        message=_email_wrapper(body, church_name, church_logo),
        delayed=True,
    )


def _get_group_leader_emails(demographic_group: str, branch: str) -> list[str]:
    """
    Return emails of demographic-specific leaders in `branch`.
    Maps demographic group name → the president flag on Member.
    Falls back to all branch leaders (all LEADER_FLAGS) if the group
    is not one of the four standard groups.
    """
    GROUP_PRESIDENT_MAP = {
        "Men":        "is_men_president",
        "Women":      "is_women_president",
        "Youth":      "is_youth_president",
        "Teenagers":  "is_teenager_president",
    }

    specific_flag = GROUP_PRESIDENT_MAP.get(demographic_group)

    if specific_flag:
        # Primary: only that group's president
        leaders = frappe.get_all(
            "Member",
            filters={
                "member_status": "Active",
                "branch":        branch,
                "email":         ["is", "set"],
                specific_flag:   1,
            },
            fields=["email"],
            limit=0,
        )
    else:
        # Unknown / non-standard group → fall back to all branch leaders
        leaders = frappe.get_all(
            "Member",
            filters={
                "member_status": "Active",
                "branch":        branch,
                "email":         ["is", "set"],
            },
            or_filters=[[flag, "=", 1] for flag in LEADER_FLAGS],
            fields=["email"] + list(LEADER_FLAGS),
            limit=0,
        )

    seen   = set()
    result = []
    for ldr in leaders:
        if ldr.email and ldr.email not in seen:
            # For fallback path: verify at least one flag is set
            if specific_flag or any(cint(ldr.get(f)) for f in LEADER_FLAGS):
                seen.add(ldr.email)
                result.append(ldr.email)
    return result


def _create_pastoral_care_task(member, ctx: dict):
    """Create a ToDo assigned to the branch pastor(s) for 4+ missed services."""
    pastors = frappe.get_all(
        "Member",
        filters={
            "member_status": "Active",
            "branch":        member.branch or "",
            "is_a_pastor":   1,
        },
        fields=["name", "email"],
        limit=0,
    )

    # Assign to first available pastor; notify all by email
    assigned_to = pastors[0].name if pastors else None

    description = (
        f"<b>Pastoral Care Required — 4+ Consecutive Missed Services</b><br><br>"
        f"<b>Member:</b> {escape_html(member.full_name or member.name)}<br>"
        f"<b>Phone:</b> {escape_html(member.mobile_phone or '—')}<br>"
        f"<b>Email:</b> {escape_html(member.email or '—')}<br>"
        f"<b>Demographic Group:</b> {escape_html(member.demographic_group or '—')}<br>"
        f"<b>Branch:</b> {escape_html(member.branch or '—')}<br><br>"
        f"Please arrange a pastoral visit or phone call."
    )

    todo = frappe.get_doc({
        "doctype":      "ToDo",
        "description":  description,
        "status":       "Open",
        "priority":     "High",
        "assigned_by":  frappe.session.user,
    })
    if assigned_to:
        todo.allocated_to = assigned_to
    todo.insert(ignore_permissions=True)

    # Email all pastors
    pastor_emails = [p.email for p in pastors if p.email]
    if pastor_emails:
        _send_pastoral_alert_email(member, ctx, pastor_emails)


def _send_pastoral_alert_email(member, ctx: dict, recipients: list[str]):
    member_name  = escape_html(member.full_name or member.name)
    branch_label = escape_html(member.branch or "Unassigned")
    phone        = escape_html(member.mobile_phone or "—")
    email_addr   = escape_html(member.email or "—")
    demographic  = escape_html(member.demographic_group or "—")
    church_name  = ctx["church_name"]
    church_logo  = ctx["church_logo"]

    body = f"""
    <p class="greeting" style="color:#b91c1c;">⚠️ Pastoral Alert</p>
    <p class="lead">
      The member below has missed <strong>4 or more consecutive Sunday services</strong>.
      A pastoral care task has been created in the system. Please prioritise a
      personal visit or call.
    </p>

    <div class="info-card" style="border-color:#fca5a5;background:#fff5f5;">
      <div class="info-row">
        <span class="info-icon">👤</span>
        <span class="info-label">Name</span>
        <span class="info-value">{member_name}</span>
      </div>
      <div class="info-row">
        <span class="info-icon">📞</span>
        <span class="info-label">Phone</span>
        <span class="info-value">{phone}</span>
      </div>
      <div class="info-row">
        <span class="info-icon">📧</span>
        <span class="info-label">Email</span>
        <span class="info-value">{email_addr}</span>
      </div>
      <div class="info-row">
        <span class="info-icon">👥</span>
        <span class="info-label">Group</span>
        <span class="info-value">{demographic}</span>
      </div>
      <div class="info-row">
        <span class="info-icon">📍</span>
        <span class="info-label">Branch</span>
        <span class="info-value">{branch_label}</span>
      </div>
    </div>

    <div class="verse">
      <p>"What do you think? If a man owns a hundred sheep, and one of them wanders
         away, will he not leave the ninety-nine on the hills and go to look for
         the one that wandered off?"</p>
      <cite>— Matthew 18:12</cite>
    </div>

    <p class="lead" style="font-size:13px;color:#6b7280;">
      A follow-up task has been assigned in the system. This alert is confidential.
    </p>"""

    frappe.sendmail(
        recipients=recipients,
        subject=f"{church_name} — ⚠️ Pastoral Alert: {member.full_name}",
        message=_email_wrapper(body, church_name, church_logo),
        delayed=True,
    )


# ─────────────────────────────────────────────────────────────────────────────
#  AUTO-SUBMIT SCHEDULED TASK
# ─────────────────────────────────────────────────────────────────────────────

def auto_submit_attendance():
    """
    Scheduled hourly.
    Auto-submits draft Church Attendance records for today if the
    configured auto-submit time has passed.
    """
    auto_submit_time = frappe.db.get_single_value(
        "Church Settings", "auto_submit_attendance_time"
    )
    if not auto_submit_time:
        return

    if get_time(nowtime()) < get_time(auto_submit_time):
        return

    today_date = getdate(nowdate())

    drafts = frappe.get_all(
        "Church Attendance",
        filters={"docstatus": 0, "service_date": today_date},
        fields=["name"],
        limit=0,
    )

    for record in drafts:
        try:
            doc = frappe.get_doc("Church Attendance", record.name)
            doc.submit()
        except Exception:
            frappe.log_error(
                frappe.get_traceback(),
                f"Auto Submit Attendance Error — {record.name}",
            )

    frappe.db.commit()


# ─────────────────────────────────────────────────────────────────────────────
#  WHITELISTED API METHODS
# ─────────────────────────────────────────────────────────────────────────────

@frappe.whitelist()
def mark_attendance_from_qr(
    member_id: str,
    service_type: str,
    service_date: str = None,
    service_instance: str = None,
):
    """
    Mark attendance from a QR scan.
    Returns success/failure dict — never throws to the client.
    """
    if not service_date:
        service_date = nowdate()

    # Idempotency guard
    existing = frappe.db.exists(
        "Church Attendance",
        {
            "member_id":    member_id,
            "service_date": service_date,
            "service_type": service_type,
            "docstatus":    ["!=", 2],
        },
    )
    if existing:
        member_name = frappe.db.get_value("Member", member_id, "full_name") or member_id
        return {
            "success": False,
            "already_marked": True,
            "message": _("Attendance already marked for {0}").format(member_name),
        }

    member = frappe.get_doc("Member", member_id)

    doc = frappe.get_doc({
        "doctype":          "Church Attendance",
        "member_id":        member_id,
        "full_name":        member.full_name,
        "service_date":     service_date,
        "service_type":     service_type,
        "service_instance": service_instance,
        "branch":           member.branch,
        "present":          1,
        "checkin_method":   "QR Code",
        "time_in":          get_time(now_datetime()),
    })
    doc.flags.ignore_permissions = True
    doc.insert()
    doc.submit()
    frappe.db.commit()

    return {
        "success":         True,
        "attendance_name": doc.name,
        "message":         _("Attendance marked for {0}").format(member.full_name),
    }


@frappe.whitelist()
def bulk_update_attendance(attendance_names, field: str, value):
    """
    Bulk-update a single allowed field across multiple attendance records.
    Field is restricted to a safe whitelist to prevent abuse.
    """
    ALLOWED_FIELDS = {
        "present", "is_visitor", "visitor_source",
        "sunday_school_class", "sunday_school_category",
        "checkin_method", "checkin_gate", "checkin_device", "demography",
    }

    if field not in ALLOWED_FIELDS:
        frappe.throw(
            _("Field '{0}' is not permitted for bulk update.").format(field),
            frappe.PermissionError,
        )

    if not isinstance(attendance_names, list):
        attendance_names = frappe.parse_json(attendance_names)

    updated, skipped, errors = 0, 0, []

    for name in attendance_names:
        try:
            doc = frappe.get_doc("Church Attendance", name)
            if doc.docstatus == 2:
                skipped += 1
                continue
            doc.set(field, value)
            doc.save(ignore_permissions=True)
            updated += 1
        except Exception as exc:
            errors.append({"name": name, "error": str(exc)})
            frappe.log_error(frappe.get_traceback(), f"Bulk Attendance Update Error — {name}")

    frappe.db.commit()

    return {
        "success": True,
        "updated": updated,
        "skipped": skipped,
        "errors":  errors,
        "total":   len(attendance_names),
    }