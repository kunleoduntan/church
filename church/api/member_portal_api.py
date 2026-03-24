# Copyright (c) 2026, Value Impacts Consulting
# License: MIT
#
# church/api/member_portal_api.py
# ─────────────────────────────────────────────────────────────────────────────
# All @frappe.whitelist() API methods for the Church Member Portal.
#
# Authentication model — token-based, NO ERPNext user required
# ─────────────────────────────────────────────────────────────
# Members authenticate with:  email  +  qr_token  (field on Member doctype)
#
# On successful portal_login():
#   1. A UUID4 session token is generated and stored on Member.portal_session_token
#   2. An expiry timestamp (24 h) is stored on Member.portal_session_expiry
#   3. The token is written as an httpOnly cookie named "portal_sid"
#      (SameSite=Lax, Path=/; browsers send it automatically on every request)
#
# Every protected endpoint calls _get_member() which:
#   1. Reads the portal_sid cookie
#   2. Matches it against Member.portal_session_token
#   3. Checks the expiry has not passed
#   4. Rolls the expiry forward 24 h on each valid call (sliding window)
#   5. Returns the Member document name
#
# Fallback credential — if a member has no QR token assigned yet, they may
# authenticate with email + date_of_birth (YYYY-MM-DD).  The server checks
# both methods and accepts whichever matches.
#
# Member DocType fields required (add via Customize Form if not present):
#   portal_session_token   Data      hidden=1  (active session UUID)
#   portal_session_expiry  Datetime  hidden=1  (token expiry datetime)
#
# Whitelist routes (called from member_portal.html):
#   church.api.member_portal_api.portal_login
#   church.api.member_portal_api.portal_logout
#   church.api.member_portal_api.get_portal_boot
#   church.api.member_portal_api.update_profile
#   church.api.member_portal_api.submit_prayer_request
#   church.api.member_portal_api.register_for_event
#   church.api.member_portal_api.get_giving_statement
# ─────────────────────────────────────────────────────────────────────────────

import uuid
import frappe
from frappe import _
from frappe.utils import now_datetime, today, cint, flt, add_to_date, get_datetime


# ─────────────────────────────────────────────────────────────────────────────
#  CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────

COOKIE_NAME    = "portal_sid"
SESSION_HOURS  = 24          # sliding window in hours
COOKIE_MAX_AGE = 60 * 60 * SESSION_HOURS   # seconds


# ─────────────────────────────────────────────────────────────────────────────
#  INTERNAL HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _get_portal_token():
    """
    Read the portal_sid value from the incoming request cookies.
    Guards against the request context not being fully initialised
    (e.g. during scheduled tasks that accidentally import portal functions).
    """
    try:
        req = getattr(frappe, "request", None) or getattr(frappe.local, "request", None)
        if req is None:
            return ""
        cookies = getattr(req, "cookies", {}) or {}
        return cookies.get(COOKIE_NAME, "").strip()
    except Exception:
        return ""


def _set_cookie(token):
    """
    Write the portal_sid cookie onto the HTTP response.
    httpOnly prevents JS from reading it (XSS protection).
    SameSite=Lax blocks cross-site POST forging.

    Frappe v13 : cookie_manager.set_cookie(key, value, **kwargs)
    Frappe v14+: cookie_manager.set_cookie(key, value, expires=<datetime>)
                 Extra kwargs like httponly/samesite are passed through to
                 Werkzeug's Response.set_cookie — both signatures work with
                 the **kwargs spread below.
    """
    from datetime import datetime, timedelta
    expires = datetime.utcnow() + timedelta(seconds=COOKIE_MAX_AGE)
    try:
        # Works on Frappe v13 and v14/v15 — extra kwargs forwarded to Werkzeug
        frappe.local.cookie_manager.set_cookie(
            COOKIE_NAME,
            token,
            expires=expires,
            httponly=True,
            samesite="Lax",
            path="/",
        )
    except TypeError:
        # Fallback: some Frappe builds only accept (key, value, expires)
        frappe.local.cookie_manager.set_cookie(COOKIE_NAME, token, expires)


def _clear_cookie():
    """Expire the portal_sid cookie immediately."""
    from datetime import datetime
    try:
        frappe.local.cookie_manager.set_cookie(
            COOKIE_NAME, "",
            expires=datetime(1970, 1, 1),
            httponly=True,
            samesite="Lax",
            path="/",
        )
    except TypeError:
        frappe.local.cookie_manager.set_cookie(
            COOKIE_NAME, "", datetime(1970, 1, 1)
        )


def _get_member():
    """
    Resolve the portal_sid cookie to a Member document name.

    Steps:
      1. Read cookie
      2. Find Member with matching portal_session_token
      3. Verify expiry has not passed
      4. Roll expiry forward (sliding 24-hour window)
      5. Return member name

    Raises frappe.AuthenticationError on any failure so the JS can
    intercept the 401 and re-show the login dialog.
    """
    token = _get_portal_token()
    if not token:
        frappe.throw(
            _("Your session has expired. Please log in again."),
            frappe.AuthenticationError,
        )

    member_name = frappe.db.get_value(
        "Member",
        {"portal_session_token": token},
        "name",
    )
    if not member_name:
        _clear_cookie()
        frappe.throw(
            _("Invalid session. Please log in again."),
            frappe.AuthenticationError,
        )

    expiry_str = frappe.db.get_value("Member", member_name, "portal_session_expiry")
    if not expiry_str or get_datetime(expiry_str) < get_datetime(now_datetime()):
        # Token exists but has expired — clean up and reject
        frappe.db.set_value("Member", member_name, {
            "portal_session_token":  "",
            "portal_session_expiry": None,
        }, update_modified=False)
        frappe.db.commit()
        _clear_cookie()
        frappe.throw(
            _("Your session has expired. Please log in again."),
            frappe.AuthenticationError,
        )

    # Slide the expiry window forward on every valid request
    new_expiry = add_to_date(now_datetime(), hours=SESSION_HOURS)
    frappe.db.set_value(
        "Member", member_name,
        "portal_session_expiry", new_expiry,
        update_modified=False,
    )
    frappe.db.commit()

    return member_name


# ─────────────────────────────────────────────────────────────────────────────
#  LOGIN / LOGOUT
# ─────────────────────────────────────────────────────────────────────────────

@frappe.whitelist(allow_guest=True)
def portal_login(email, credential):
    """
    Authenticate a church member and issue a portal session cookie.

    Parameters
    ----------
    email      : str   Member's email address (case-insensitive)
    credential : str   Either the member's QR token  OR  date of birth (YYYY-MM-DD)
                       The server tries qr_token first, then date_of_birth.

    Returns
    -------
    dict  { success, member_name, full_name, message }

    Sets httpOnly cookie "portal_sid" on success.
    Throws frappe.AuthenticationError on failure so the dialog can show
    an appropriate error without revealing which field was wrong.
    """
    if not email or not credential:
        frappe.throw(_("Email and credential are required."), frappe.AuthenticationError)

    email      = (email or "").strip().lower()
    credential = (credential or "").strip()

    # ── Find member by email (case-insensitive) ──────────────────────────────
    member_name = frappe.db.get_value(
        "Member",
        {"email": ["like", email]},
        "name",
    )
    if not member_name:
        # Slight delay to deter enumeration attacks
        import time; time.sleep(0.4)
        frappe.throw(
            _("No member account found with that email address."),
            frappe.AuthenticationError,
        )

    member = frappe.get_doc("Member", member_name)

    # ── Validate credential — qr_token first, then date_of_birth ────────────
    qr_token  = (member.qr_token or "").strip()
    dob       = str(member.date_of_birth or "").strip()

    matched = False
    if qr_token and credential == qr_token:
        matched = True
    elif dob and credential == dob:
        matched = True

    if not matched:
        import time; time.sleep(0.4)
        frappe.throw(
            _("The credential you entered does not match our records."),
            frappe.AuthenticationError,
        )

    # ── Issue session token ──────────────────────────────────────────────────
    token  = str(uuid.uuid4())
    expiry = add_to_date(now_datetime(), hours=SESSION_HOURS)

    frappe.db.set_value("Member", member_name, {
        "portal_session_token":  token,
        "portal_session_expiry": expiry,
    }, update_modified=False)
    frappe.db.commit()

    _set_cookie(token)

    return {
        "success":     True,
        "member_name": member_name,
        "full_name":   member.full_name or "",
        "message":     _("Welcome back, {0}! 🙏").format(member.first_name or member.full_name),
    }


@frappe.whitelist(allow_guest=True)
def portal_logout():
    """
    Invalidate the current portal session — clears token from DB and cookie.
    allow_guest=True so the call succeeds even if the token is already expired.
    """
    token = _get_portal_token()
    if token:
        member_name = frappe.db.get_value(
            "Member", {"portal_session_token": token}, "name"
        )
        if member_name:
            frappe.db.set_value("Member", member_name, {
                "portal_session_token":  "",
                "portal_session_expiry": None,
            }, update_modified=False)
            frappe.db.commit()
    _clear_cookie()
    return {"success": True, "message": _("You have been signed out.")}


@frappe.whitelist(allow_guest=True)
def check_session():
    """
    Called on page load to check if a valid portal session exists.
    Returns { authenticated: bool, full_name: str }.
    allow_guest=True so guests can call it without a 403.
    """
    token = _get_portal_token()
    if not token:
        return {"authenticated": False}

    member_name = frappe.db.get_value(
        "Member", {"portal_session_token": token}, "name"
    )
    if not member_name:
        _clear_cookie()
        return {"authenticated": False}

    expiry_str = frappe.db.get_value("Member", member_name, "portal_session_expiry")
    if not expiry_str or get_datetime(expiry_str) < get_datetime(now_datetime()):
        frappe.db.set_value("Member", member_name, {
            "portal_session_token":  "",
            "portal_session_expiry": None,
        }, update_modified=False)
        frappe.db.commit()
        _clear_cookie()
        return {"authenticated": False}

    full_name = frappe.db.get_value("Member", member_name, "full_name") or ""
    return {"authenticated": True, "full_name": full_name}


# ─────────────────────────────────────────────────────────────────────────────
#  BOOT — single call that hydrates the entire portal on first load
# ─────────────────────────────────────────────────────────────────────────────

@frappe.whitelist(allow_guest=True)
def get_portal_boot():
    """
    Return all data needed to render the member portal in one round-trip.
    Protected by _get_member() which validates the portal_sid cookie.

    Returns:
      member, church, attendance, giving, pledges, events,
      services, sunday_school, prayers, registrations
    """
    member_id = _get_member()
    member    = frappe.get_doc("Member", member_id)
    settings  = frappe.get_single("Church Settings")

    # ── Attendance ────────────────────────────────────────────────────────────
    att_records = frappe.get_all(
        "Church Attendance",
        filters={"member_id": member_id, "docstatus": 1},
        fields=[
            "service_date", "service_type", "service_instance",
            "present", "branch",
        ],
        order_by="service_date desc",
        limit=50,
    )
    total_att   = len(att_records)
    present_att = sum(1 for r in att_records if cint(r.present))
    att_pct     = flt((present_att / total_att) * 100, 1) if total_att else 0.0

    # ── Giving ────────────────────────────────────────────────────────────────
    tithe_doc = frappe.db.get_value(
        "Member Tithe Record",
        {"member_id": member_id},
        ["name", "amount_paid", "last_synced"],
        as_dict=True,
    )
    giving_payments = []
    if tithe_doc:
        giving_payments = frappe.get_all(
            "Tithe Payment Schedule",
            filters={"parent": tithe_doc["name"]},
            fields=[
                "date", "receipt_no", "full_name", "amount_paid",
                "amount_in_lc", "currency", "other_details",
            ],
            order_by="date desc",
            limit=24,
        )

    # ── Pledges ───────────────────────────────────────────────────────────────
    pledges = frappe.get_all(
        "Pledges",
        filters={"member_id": member_id, "docstatus": ["!=", 2]},
        fields=[
            "name", "pledge_date", "programme", "amount", "balance",
            "amount_paid", "redemption_date", "closing_date",
            "is_payable_on_installment",
        ],
        order_by="pledge_date desc",
    )

    # ── Upcoming Church Events ────────────────────────────────────────────────
    upcoming_events = frappe.get_all(
        "Church Event",
        filters={
            "start_date": [">=", today()],
            "status":     ["in", ["Planning", "Approved", "In Progress"]],
        },
        fields=[
            "name", "event_name", "event_type", "status",
            "start_date", "start_time", "end_date", "venue",
            "event_theme", "requires_registration", "registration_fee",
            "target_audience", "max_participants", "total_registered",
        ],
        order_by="start_date asc",
        limit=12,
    )

    # ── Upcoming Service Instances ────────────────────────────────────────────
    upcoming_services = frappe.get_all(
        "Service Instance",
        filters={
            "service_date": [">=", today()],
            "status":       ["in", ["Scheduled", "Ongoing"]],
        },
        fields=[
            "name", "service_name", "service_date", "service_time",
            "service_type", "branch", "venue", "sermon_title",
            "status", "minister",
        ],
        order_by="service_date asc",
        limit=6,
    )
    for svc in upcoming_services:
        if svc.get("minister"):
            svc["minister_name"] = (
                frappe.db.get_value("Member", svc["minister"], "full_name") or ""
            )

    # ── Sunday School / Children Class ───────────────────────────────────────
    ss_info  = None
    ss_class = member.sunday_school_class
    if ss_class:
        if frappe.db.exists("Sunday School Class", ss_class):
            ss_info = frappe.db.get_value(
                "Sunday School Class", ss_class,
                [
                    "name", "sunday_school_class_category", "teacher_name",
                    "phone_no", "email", "assistant_teacher_name",
                    "assistant_teacher_phone_no",
                ],
                as_dict=True,
            )
        elif frappe.db.exists("Children Class", ss_class):
            raw = frappe.db.get_value(
                "Children Class", ss_class,
                [
                    "class_name", "age_group", "teacher_name", "phone_no",
                    "email", "assistant_teacher_name", "assistant_teacher_phone_no",
                ],
                as_dict=True,
            )
            if raw:
                ss_info = {
                    "name":                         raw["class_name"],
                    "sunday_school_class_category": raw["age_group"],
                    "teacher_name":                 raw["teacher_name"],
                    "phone_no":                     raw["phone_no"],
                    "email":                        raw["email"],
                    "assistant_teacher_name":       raw["assistant_teacher_name"],
                    "assistant_teacher_phone_no":   raw["assistant_teacher_phone_no"],
                }

    # ── Prayer Requests ───────────────────────────────────────────────────────
    prayers = frappe.get_all(
        "Prayer Request",
        filters={"member_id": member_id},
        fields=[
            "name", "creation", "prayer_title", "prayer_body",
            "category", "status", "is_anonymous", "is_urgent",
        ],
        order_by="creation desc",
        limit=12,
    )

    # ── Event Registrations ───────────────────────────────────────────────────
    registrations = frappe.get_all(
        "Event Registration",
        filters={"member_id": member_id},
        fields=[
            "name", "event", "event_name", "registration_date",
            "status", "payment_status", "payment_amount",
        ],
        order_by="registration_date desc",
        limit=20,
    )

    # ── Assemble and return ───────────────────────────────────────────────────
    return {
        "member": {
            "id":                member.name,
            "full_name":         member.full_name          or "",
            "first_name":        member.first_name         or "",
            "last_name":         member.last_name          or "",
            "salutation":        str(member.salutation     or ""),
            "photo":             member.photo              or "",
            "qr_code_image":     member.qr_code_image      or "",
            "email":             member.email              or "",
            "mobile_phone":      member.mobile_phone       or "",
            "whatsapp_number":   member.whatsapp_number    or "",
            "gender":            str(member.gender         or ""),
            "date_of_birth":     str(member.date_of_birth) if member.date_of_birth else "",
            "age":               member.age                or "",
            "occupation":        member.occupation         or "",
            "marital_status":    member.marital_status     or "",
            "address":           member.address            or "",
            "city":              member.city               or "",
            "state":             member.state              or "",
            "branch":            str(member.branch         or ""),
            "parish":            str(member.parish         or ""),
            "zone":              str(member.zone           or ""),
            "area":              str(member.area           or ""),
            "region":            str(member.region         or ""),
            "province":          str(member.province       or ""),
            "member_status":     member.member_status      or "Active",
            "type":              member.type               or "",
            "date_of_joining":   str(member.date_of_joining) if member.date_of_joining else "",
            "demographic_group": member.demographic_group  or "",
            "sunday_school_class": member.sunday_school_class or "",
            "is_a_worker":       cint(member.is_a_worker),
            "is_a_pastor":       cint(member.is_a_pastor),
            "designation":       str(member.designation    or ""),
        },
        "church": {
            "name":         settings.church_name          or "Church",
            "abbreviation": settings.church_abbreviation  or "",
            "currency":     settings.default_currency     or "NGN",
            "headquarters": settings.headquarters         or "",
        },
        "attendance": {
            "total":   total_att,
            "present": present_att,
            "absent":  total_att - present_att,
            "pct":     att_pct,
            "recent": [
                {
                    "service_date":     str(r.service_date),
                    "service_type":     r.service_type      or "",
                    "service_instance": r.service_instance  or "",
                    "branch":           str(r.branch        or ""),
                    "present":          cint(r.present),
                }
                for r in att_records
            ],
        },
        "giving": {
            "total_paid":  flt(tithe_doc["amount_paid"]) if tithe_doc else 0.0,
            "last_synced": str(tithe_doc["last_synced"]) if tithe_doc else "",
            "payments": [
                {
                    "date":          str(p.date),
                    "receipt_no":    p.receipt_no    or "",
                    "full_name":     p.full_name     or "",
                    "amount_paid":   flt(p.amount_paid),
                    "amount_in_lc":  flt(p.amount_in_lc),
                    "currency":      p.currency      or "NGN",
                    "other_details": p.other_details or "",
                }
                for p in giving_payments
            ],
        },
        "pledges": [
            {
                "name":                      p.name,
                "pledge_date":               str(p.pledge_date),
                "programme":                 p.programme    or "",
                "amount":                    flt(p.amount),
                "balance":                   flt(p.balance),
                "amount_paid":               flt(p.amount_paid),
                "redemption_date":           str(p.redemption_date) if p.redemption_date else "",
                "closing_date":              str(p.closing_date)    if p.closing_date    else "",
                "is_payable_on_installment": cint(p.is_payable_on_installment),
            }
            for p in pledges
        ],
        "events": [
            {
                "name":                  e.name,
                "event_name":            e.event_name,
                "event_type":            e.event_type      or "",
                "status":                e.status,
                "start_date":            str(e.start_date),
                "start_time":            str(e.start_time  or ""),
                "end_date":              str(e.end_date),
                "venue":                 e.venue           or "",
                "event_theme":           e.event_theme     or "",
                "target_audience":       e.target_audience or "",
                "requires_registration": cint(e.requires_registration),
                "registration_fee":      flt(e.registration_fee),
                "max_participants":      cint(e.max_participants),
                "total_registered":      cint(e.total_registered),
            }
            for e in upcoming_events
        ],
        "services": [
            {
                "name":          s.name,
                "service_name":  s.service_name  or s.name,
                "service_date":  str(s.service_date),
                "service_time":  str(s.service_time or ""),
                "service_type":  s.service_type  or "",
                "branch":        str(s.branch    or ""),
                "venue":         s.venue         or "",
                "sermon_title":  s.sermon_title  or "",
                "status":        s.status        or "Scheduled",
                "minister_name": s.get("minister_name", ""),
            }
            for s in upcoming_services
        ],
        "sunday_school": ss_info,
        "prayers": [
            {
                "name":         p.name,
                "creation":     str(p.creation),
                "prayer_title": p.prayer_title,
                "prayer_body":  p.prayer_body   or "",
                "category":     p.category      or "General",
                "status":       p.status        or "Pending",
                "is_anonymous": cint(p.is_anonymous),
                "is_urgent":    cint(p.is_urgent),
            }
            for p in prayers
        ],
        "registrations": [
            {
                "name":              r.name,
                "event":             r.event,
                "event_name":        r.event_name        or "",
                "registration_date": str(r.registration_date),
                "status":            r.status            or "",
                "payment_status":    r.payment_status    or "Not Required",
                "payment_amount":    flt(r.payment_amount),
            }
            for r in registrations
        ],
    }


# ─────────────────────────────────────────────────────────────────────────────
#  PROFILE UPDATE
# ─────────────────────────────────────────────────────────────────────────────

@frappe.whitelist(allow_guest=True)
def update_profile(
    mobile_phone=None,
    whatsapp_number=None,
    address=None,
    city=None,
    state=None,
    occupation=None,
):
    """
    Allow a member to update their own contact details.
    Sensitive fields (branch, zone, designation) require office action.
    """
    member_id = _get_member()
    doc = frappe.get_doc("Member", member_id)

    if mobile_phone    is not None: doc.mobile_phone    = mobile_phone
    if whatsapp_number is not None: doc.whatsapp_number = whatsapp_number
    if address         is not None: doc.address         = address
    if city            is not None: doc.city            = city
    if state           is not None: doc.state           = state
    if occupation      is not None: doc.occupation      = occupation

    doc.flags.ignore_permissions = True
    doc.save()
    frappe.db.commit()

    return {"success": True, "message": _("Profile updated successfully.")}


# ─────────────────────────────────────────────────────────────────────────────
#  PRAYER REQUEST
# ─────────────────────────────────────────────────────────────────────────────

@frappe.whitelist(allow_guest=True)
def submit_prayer_request(
    prayer_title,
    prayer_body,
    category="General",
    is_anonymous=0,
    is_urgent=0,
):
    """
    Create a new Prayer Request for the authenticated member.
    Lands in the pastoral care queue with status Pending.
    """
    member_id = _get_member()

    if not (prayer_title or "").strip():
        frappe.throw(_("Prayer title is required."))
    if not (prayer_body or "").strip():
        frappe.throw(_("Please describe your prayer request."))

    doc              = frappe.new_doc("Prayer Request")
    doc.member_id    = member_id
    doc.full_name    = frappe.db.get_value("Member", member_id, "full_name") or ""
    doc.prayer_title = prayer_title.strip()
    doc.prayer_body  = prayer_body.strip()
    doc.category     = category or "General"
    doc.is_anonymous = cint(is_anonymous)
    doc.is_urgent    = cint(is_urgent)
    doc.status       = "Pending"
    doc.submitted_on = now_datetime()

    doc.flags.ignore_permissions = True
    doc.insert()
    frappe.db.commit()

    return {
        "success": True,
        "name":    doc.name,
        "message": _(
            "Your prayer request has been submitted. "
            "The church is praying with you. 🙏"
        ),
    }


# ─────────────────────────────────────────────────────────────────────────────
#  EVENT REGISTRATION
# ─────────────────────────────────────────────────────────────────────────────

@frappe.whitelist(allow_guest=True)
def register_for_event(event_id, notes=None):
    """
    Register the authenticated member for a Church Event.
    Guards: event exists, not already registered, not at capacity.
    Increments Church Event.total_registered on success.
    """
    member_id = _get_member()

    if not frappe.db.exists("Church Event", event_id):
        frappe.throw(_("Event not found."))

    if frappe.db.exists(
        "Event Registration",
        {"member_id": member_id, "event": event_id},
    ):
        frappe.throw(_("You are already registered for this event."))

    event = frappe.get_doc("Church Event", event_id)

    if (
        cint(event.max_participants) > 0
        and cint(event.total_registered) >= cint(event.max_participants)
    ):
        frappe.throw(
            _("This event has reached maximum capacity ({0}).").format(
                event.max_participants
            )
        )

    fee               = flt(event.registration_fee)
    doc               = frappe.new_doc("Event Registration")
    doc.member_id     = member_id
    doc.full_name     = frappe.db.get_value("Member", member_id, "full_name") or ""
    doc.event         = event_id
    doc.event_name    = event.event_name
    doc.registration_date = today()
    doc.status        = "Registered"
    doc.payment_status = "Pending" if fee > 0 else "Not Required"
    doc.payment_amount = fee
    doc.notes         = (notes or "").strip()

    doc.flags.ignore_permissions = True
    doc.insert()

    frappe.db.set_value(
        "Church Event", event_id,
        "total_registered", cint(event.total_registered) + 1,
    )
    frappe.db.commit()

    return {
        "success": True,
        "name":    doc.name,
        "message": _(
            "You are now registered for {0}. See you there! 🎉"
        ).format(event.event_name),
    }


# ─────────────────────────────────────────────────────────────────────────────
#  GIVING STATEMENT
# ─────────────────────────────────────────────────────────────────────────────

@frappe.whitelist(allow_guest=True)
def get_giving_statement(from_date=None, to_date=None):
    """
    Return the member's tithe payment history, optionally filtered by date.
    total is computed from amount_in_lc with fallback to amount_paid.
    """
    member_id  = _get_member()
    tithe_name = frappe.db.get_value(
        "Member Tithe Record", {"member_id": member_id}, "name"
    )
    if not tithe_name:
        return {"payments": [], "total": 0.0, "member": {}, "church": {}}

    filters = {"parent": tithe_name}
    if from_date and to_date:
        filters["date"] = ["between", [from_date, to_date]]
    elif from_date:
        filters["date"] = [">=", from_date]
    elif to_date:
        filters["date"] = ["<=", to_date]

    payments = frappe.get_all(
        "Tithe Payment Schedule",
        filters=filters,
        fields=[
            "date", "receipt_no", "amount_paid",
            "amount_in_lc", "currency", "other_details",
        ],
        order_by="date asc",
    )
    total    = sum(flt(p.amount_in_lc or p.amount_paid) for p in payments)
    member   = frappe.get_doc("Member", member_id)
    settings = frappe.get_single("Church Settings")

    return {
        "member": {
            "full_name": member.full_name,
            "id":        member_id,
            "branch":    str(member.branch  or ""),
            "parish":    str(member.parish  or ""),
        },
        "church": {
            "name":     settings.church_name,
            "currency": settings.default_currency or "NGN",
        },
        "from_date": from_date or "",
        "to_date":   to_date   or "",
        "payments": [
            {
                "date":          str(p.date),
                "receipt_no":    p.receipt_no    or "",
                "amount_paid":   flt(p.amount_paid),
                "amount_in_lc":  flt(p.amount_in_lc),
                "currency":      p.currency      or "NGN",
                "other_details": p.other_details or "",
            }
            for p in payments
        ],
        "total": total,
    }


# ─────────────────────────────────────────────────────────────────────────────
#  HOOKS CALLBACKS
#  Called from hooks.py — not directly by the portal frontend.
# ─────────────────────────────────────────────────────────────────────────────

def clear_member_portal_session(doc, method=None):
    """
    doc_events hook — Member on_trash.
    When a Member record is deleted, immediately invalidate any live
    portal session so the browser cookie can no longer grant access.
    """
    try:
        if doc.get("portal_session_token"):
            frappe.db.set_value(
                "Member", doc.name,
                {
                    "portal_session_token":  "",
                    "portal_session_expiry": None,
                },
                update_modified=False,
            )
            frappe.db.commit()
    except Exception:
        pass   # non-fatal — Member is being deleted anyway


def purge_expired_portal_sessions():
    """
    Scheduled daily task.
    Finds all Member records whose portal_session_expiry has passed and
    clears their token fields.  Keeps the Member table clean and prevents
    the portal_session_token index from growing with stale rows.
    """
    expired = frappe.db.sql(
        """
        SELECT name
          FROM `tabMember`
         WHERE portal_session_token  IS NOT NULL
           AND portal_session_token  != ''
           AND portal_session_expiry IS NOT NULL
           AND portal_session_expiry < NOW()
        """,
        as_dict=True,
    )
    if not expired:
        return

    names = [r.name for r in expired]
    frappe.db.sql(
        """
        UPDATE `tabMember`
           SET portal_session_token  = '',
               portal_session_expiry = NULL
         WHERE name IN ({placeholders})
        """.format(placeholders=", ".join(["%s"] * len(names))),
        names,
    )
    frappe.db.commit()
    frappe.logger().info(
        f"[MemberPortal] purged {len(names)} expired portal session(s)."
    )


def on_frappe_logout():
    """
    on_logout hook — called when anyone hits Frappe's /logout route.
    Clears the portal_sid cookie so a shared browser doesn't keep a
    member portal session alive after a staff user signs out.
    This is a best-effort call; failures are silently ignored.
    """
    try:
        _clear_cookie()
    except Exception:
        pass