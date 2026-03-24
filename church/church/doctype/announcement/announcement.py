# apps/church/church/church/doctype/announcement/announcement.py
# Copyright (c) 2026, Value Impacts Consulting
#
# KEY DESIGN DECISIONS
# ─────────────────────────────────────────────────────────────────────────────
# 1. NO SUBMIT REQUIRED — send works from Draft (docstatus 0 or 1).
# 2. TEST SEND — saves doc only, never submits, never sets sent=1.
#    Uses now=True so email goes immediately.
# 3. BULK SEND — saves + submits first (for audit trail), then sends.
# 4. EMAIL BODY — wrapped in a professional HTML shell so plain text
#    and raw HTML both render beautifully in every email client.
# 5. WhatsApp / SMS via smsalat.com — same API as working Broadcast.
#
# Whitelisted endpoints:
#   church.church.doctype.announcement.announcement.send_announcement
#   church.church.doctype.announcement.announcement.send_test
#   church.church.doctype.announcement.announcement.retry_failed
#   church.church.doctype.announcement.announcement.cancel_scheduled
#   church.church.doctype.announcement.announcement.preview_message
#   church.church.doctype.announcement.announcement.import_recipients

import frappe
import json
import requests
from frappe.model.document import Document
from frappe.utils import now_datetime, get_datetime, cstr

WHATSAPP_SMS_API = "https://smsalat.com/app/api/http/sms/send"


# ─────────────────────────────────────────────────────────────────────────────
# CONTROLLER
# ─────────────────────────────────────────────────────────────────────────────

class Announcement(Document):

    def validate(self):
        self._deduplicate_recipients()
        self._sync_source_type()
        self._update_counts()

    def before_submit(self):
        if not self.recipients:
            frappe.throw("Cannot submit an Announcement with no recipients.")
        if self.schedule and self.schedule_time:
            if get_datetime(self.schedule_time) < now_datetime():
                frappe.throw("Schedule time cannot be in the past.")

    def on_submit(self):
        if self.schedule and self.schedule_time:
            self.db_set("status", "Scheduled")

    def _deduplicate_recipients(self):
        seen, unique = set(), []
        for row in self.recipients:
            key = (
                (row.email or "").lower().strip()
                or (row.mobile_phone or "").strip()
                or (row.full_name or "").strip()
            )
            if key and key not in seen:
                seen.add(key)
                unique.append(row)
        self.recipients = unique

    def _sync_source_type(self):
        audience = self.audience_group or ""
        for row in self.recipients:
            if not row.source_type:
                row.source_type = audience

    def _update_counts(self):
        self.total_recipients = len(self.recipients)
        self.sent_count    = sum(1 for r in self.recipients if r.delivery_status == "Sent")
        self.failed_count  = sum(1 for r in self.recipients if r.delivery_status == "Failed")
        self.pending_count = sum(1 for r in self.recipients if r.delivery_status == "Pending")


# ─────────────────────────────────────────────────────────────────────────────
# TEST SEND  —  never submits, never touches sent/status flags
# ─────────────────────────────────────────────────────────────────────────────

@frappe.whitelist()
def send_test(docname):
    """
    Send a test message.
    - Does NOT submit the document.
    - Does NOT set sent=1 or change status.
    - Email: now=True  → immediate SMTP delivery.
    - WhatsApp / SMS   → smsalat.com, same as Broadcast.
    """
    doc = frappe.get_doc("Announcement", docname)
    mt  = doc.message_type or "Email"

    do_email    = "Email"    in mt
    do_whatsapp = "WhatsApp" in mt
    do_sms      = "SMS"      in mt

    if do_email and not doc.test_email:
        frappe.throw("Please set the <b>Test Email</b> field before sending a test.")
    if (do_whatsapp or do_sms) and not doc.test_phone_number:
        frappe.throw("Please set the <b>Test Phone Number</b> field before sending a test.")

    context = {
        "full_name":       "Test Recipient",
        "salutation":      "Dear",
        "sender_name":     doc.from_name or "The Team",
        "summary":         doc.summary   or "",
        "unsubscribe_url": "#"
    }

    attachments, image_tags, raw_body = _prepare_content(doc)

    results = []

    if do_email and doc.test_email:
        rendered = _render_safe(raw_body, context)
        html     = _wrap_email_html(rendered, doc.subject, doc.from_name or "The Team")
        frappe.sendmail(
            recipients        = [doc.test_email],
            subject           = f"[TEST] {doc.subject or 'No Subject'}",
            message           = html,
            attachments       = attachments,
            reference_doctype = "Announcement",
            reference_name    = doc.name,
            now               = True,   # send immediately
            template          = False
        )
        results.append(f"Email → {doc.test_email}")

    if do_whatsapp and doc.test_phone_number:
        msg = _render_safe(doc.whatsapp_message_body or "", context)
        _send_whatsapp(doc.test_phone_number, msg, doc.whatsapp_image_url or "")
        results.append(f"WhatsApp → {doc.test_phone_number}")

    if do_sms and doc.test_phone_number:
        msg = _render_safe(doc.sms_message_body or "", context)
        _send_sms(doc.test_phone_number, msg)
        results.append(f"SMS → {doc.test_phone_number}")

    summary = ", ".join(results) if results else "Nothing sent — check channel settings."
    frappe.msgprint(f"✅ Test sent: {summary}", title="Test Successful", indicator="green")
    return {"success": True, "summary": summary}


# ─────────────────────────────────────────────────────────────────────────────
# BULK SEND  —  saves + submits for audit trail, then sends to all recipients
# ─────────────────────────────────────────────────────────────────────────────

@frappe.whitelist()
def send_announcement(docname):
    """
    Send to all recipients.
    Called after JS has already saved + submitted the doc.
    """
    doc = frappe.get_doc("Announcement", docname)

    if doc.sent:
        frappe.throw("This Announcement has already been sent.")
    if doc.status == "Cancelled":
        frappe.throw("This Announcement has been cancelled.")
    if doc.expiry_date and get_datetime(doc.expiry_date) < now_datetime():
        frappe.throw("This Announcement has passed its expiry date.")
    if not doc.recipients:
        frappe.throw("No recipients found. Please add recipients first.")

    mt          = doc.message_type or "Email"
    do_email    = "Email"    in mt
    do_whatsapp = "WhatsApp" in mt
    do_sms      = "SMS"      in mt

    attachments, image_tags, raw_body = _prepare_content(doc)

    failed_list = []

    for recipient in doc.recipients:
        if recipient.delivery_status == "Sent":
            continue
        if not recipient.email and not recipient.mobile_phone:
            continue

        context = {
            "full_name":       recipient.full_name  or "",
            "salutation":      recipient.salutation or "Dear",
            "sender_name":     doc.from_name        or "The Team",
            "summary":         doc.summary          or "",
            "unsubscribe_url": _unsubscribe_url(doc.name, recipient.name)
        }

        row_errors = []

        # ── Email ──────────────────────────────────────────────────────────
        if do_email and recipient.email:
            try:
                rendered = _render_safe(raw_body, context)
                if doc.unsubscribe_link:
                    rendered += _unsubscribe_block(doc.name, recipient.name)
                html = _wrap_email_html(
                    rendered, doc.subject, doc.from_name or "The Team"
                )
                sender = (
                    f"{doc.from_name} <{doc.from_email}>"
                    if doc.from_email else None
                )
                frappe.sendmail(
                    recipients        = [recipient.email],
                    subject           = doc.subject or "No Subject",
                    message           = html,
                    sender            = sender,
                    reply_to          = doc.reply_to_email or doc.from_email,
                    attachments       = attachments,
                    reference_doctype = "Announcement",
                    reference_name    = doc.name,
                    now               = False,  # queued — Frappe flushes every 1 min
                    template          = False
                )
                frappe.db.set_value("Announcement Recipient", recipient.name,
                                    "email_status", "Sent")
            except Exception as e:
                err = str(e)
                row_errors.append(f"Email: {err}")
                frappe.db.set_value("Announcement Recipient", recipient.name,
                                    "email_status", "Failed")
                frappe.log_error(err, f"Announcement Email [{docname}]")

        # ── WhatsApp ────────────────────────────────────────────────────────
        if do_whatsapp and recipient.mobile_phone:
            try:
                msg = _render_safe(doc.whatsapp_message_body or "", context)
                _send_whatsapp(recipient.mobile_phone, msg,
                               doc.whatsapp_image_url or "")
                frappe.db.set_value("Announcement Recipient", recipient.name,
                                    "whatsapp_status", "Sent")
            except Exception as e:
                err = str(e)
                row_errors.append(f"WhatsApp: {err}")
                frappe.db.set_value("Announcement Recipient", recipient.name,
                                    "whatsapp_status", "Failed")
                frappe.log_error(err, f"Announcement WhatsApp [{docname}]")

        # ── SMS ─────────────────────────────────────────────────────────────
        if do_sms and recipient.mobile_phone:
            try:
                msg = _render_safe(doc.sms_message_body or "", context)
                _send_sms(recipient.mobile_phone, msg)
                frappe.db.set_value("Announcement Recipient", recipient.name,
                                    "sms_status", "Sent")
            except Exception as e:
                err = str(e)
                row_errors.append(f"SMS: {err}")
                frappe.db.set_value("Announcement Recipient", recipient.name,
                                    "sms_status", "Failed")
                frappe.log_error(err, f"Announcement SMS [{docname}]")

        # ── Row result ───────────────────────────────────────────────────────
        if row_errors:
            frappe.db.set_value("Announcement Recipient", recipient.name, {
                "delivery_status": "Failed",
                "error_message":   "; ".join(row_errors),
                "sent_at":         now_datetime()
            })
            failed_list.append(recipient.email or recipient.mobile_phone)
        else:
            frappe.db.set_value("Announcement Recipient", recipient.name, {
                "delivery_status": "Sent",
                "error_message":   "",
                "sent_at":         now_datetime()
            })

    frappe.db.commit()

    # ── Final status ─────────────────────────────────────────────────────────
    total    = len(doc.recipients)
    n_failed = len(failed_list)
    n_sent   = total - n_failed

    if n_failed == 0:
        doc.db_set({"status": "Sent", "sent": 1,
                    "sent_count": n_sent, "failed_count": 0,
                    "pending_count": 0, "total_recipients": total})
        frappe.msgprint(
            f"✅ Announcement sent to {n_sent} recipient(s).",
            title="Sent", indicator="green"
        )
    elif n_sent == 0:
        doc.db_set({"status": "Failed",
                    "sent_count": 0, "failed_count": n_failed,
                    "pending_count": 0, "total_recipients": total})
        frappe.msgprint(
            "❌ Announcement failed for all recipients. Check the Error Log.",
            title="Failed", indicator="red"
        )
    else:
        doc.db_set({"status": "Partially Sent",
                    "sent_count": n_sent, "failed_count": n_failed,
                    "pending_count": 0, "total_recipients": total})
        frappe.log_error("\n".join(failed_list), "Announcement Partial Failure")
        frappe.msgprint(
            f"⚠️ Sent to {n_sent}, failed for {n_failed}. Check the Error Log.",
            title="Partially Sent", indicator="orange"
        )

    return {"success": True, "sent": n_sent, "failed": n_failed}


# ─────────────────────────────────────────────────────────────────────────────
# OTHER WHITELISTED ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────────

@frappe.whitelist()
def retry_failed(docname):
    doc = frappe.get_doc("Announcement", docname)
    reset = 0
    for row in doc.recipients:
        if row.delivery_status == "Failed":
            row.delivery_status = "Pending"
            row.error_message   = ""
            reset += 1
    if not reset:
        frappe.throw("No failed recipients to retry.")
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    result = send_announcement(docname)
    return {"retried": reset, **result}


@frappe.whitelist()
def cancel_scheduled(docname):
    doc = frappe.get_doc("Announcement", docname)
    if doc.status != "Scheduled":
        frappe.throw("Only Scheduled announcements can be cancelled.")
    doc.db_set("status", "Cancelled")
    return {"cancelled": True}


@frappe.whitelist()
def preview_message(docname):
    """Returns a fully rendered HTML preview of the email body."""
    doc = frappe.get_doc("Announcement", docname)

    if doc.option == "HTML":
        raw = doc.message_tx_html or ""
    else:
        raw = doc.message_body or ""

    # Build images
    image_tags = _build_image_tags(docname)
    raw_body   = raw + image_tags

    context = {
        "full_name":       "John Doe",
        "salutation":      "Dear",
        "sender_name":     doc.from_name or "The Team",
        "summary":         doc.summary   or "",
        "unsubscribe_url": "#"
    }

    rendered = _render_safe(raw_body, context)
    html     = _wrap_email_html(rendered, doc.subject, doc.from_name or "The Team")

    return {"html": html, "subject": doc.subject or "No Subject"}


@frappe.whitelist()
def import_recipients(docname, rows, column_map):
    doc = frappe.get_doc("Announcement", docname)
    if isinstance(rows,       str): rows       = json.loads(rows)
    if isinstance(column_map, str): column_map = json.loads(column_map)

    existing = {(r.email or "").lower().strip() for r in doc.recipients}
    added = skipped = 0

    for row in rows:
        full_name  = cstr(row.get(column_map.get("full_name",    ""), "")).strip()
        email      = cstr(row.get(column_map.get("email",        ""), "")).strip()
        mobile     = cstr(row.get(column_map.get("mobile_phone", ""), "")).strip()
        salutation = cstr(row.get(column_map.get("salutation",   ""), "")).strip()

        if not full_name:
            skipped += 1
            continue
        if email and email.lower() in existing:
            skipped += 1
            continue

        doc.append("recipients", {
            "full_name":       full_name,
            "email":           email,
            "mobile_phone":    mobile,
            "salutation":      salutation,
            "source_type":     doc.audience_group or "Imported",
            "delivery_status": "Pending"
        })
        if email:
            existing.add(email.lower())
        added += 1

    doc.total_recipients = len(doc.recipients)
    doc.save(ignore_permissions=True)
    return {"added": added, "skipped": skipped, "total": len(doc.recipients)}


# ─────────────────────────────────────────────────────────────────────────────
# SCHEDULER JOB
# hooks.py: "*/15 * * * *": ["church.church.doctype.announcement.announcement.process_scheduled"]
# ─────────────────────────────────────────────────────────────────────────────

def process_scheduled():
    now = now_datetime()
    due = frappe.get_all(
        "Announcement",
        filters={"docstatus": 1, "status": "Scheduled",
                 "schedule": 1, "schedule_time": ["<=", now]},
        fields=["name", "expiry_date"]
    )
    for ann in due:
        if ann.expiry_date and get_datetime(ann.expiry_date) < now:
            frappe.db.set_value("Announcement", ann.name, "status", "Cancelled")
            continue
        try:
            send_announcement(ann.name)
        except Exception:
            frappe.log_error(frappe.get_traceback(),
                             f"Scheduled Announcement Failed: {ann.name}")


# ─────────────────────────────────────────────────────────────────────────────
# INTERNAL — CONTENT PREPARATION
# ─────────────────────────────────────────────────────────────────────────────

def _prepare_content(doc):
    """Returns (attachments, image_tags, raw_body) — same pattern as Broadcast."""
    files = frappe.get_all(
        "File",
        filters={"attached_to_doctype": "Announcement",
                 "attached_to_name": doc.name},
        fields=["file_url", "file_name", "is_private"]
    )

    image_urls       = []
    attachment_files = []
    for f in files:
        if f["file_url"].lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp')):
            image_urls.append(f["file_url"])
        else:
            attachment_files.append(f)

    image_tags = "".join(
        "<p style='text-align:center;margin:12px 0;'>"
        f"<img src='{url}' style='max-width:100%;height:auto;"
        f"border-radius:8px;display:block;margin:0 auto;'/></p>"
        for url in image_urls
    )

    attachments = []
    if doc.include_attachments:
        for file in attachment_files:
            try:
                fd   = frappe.get_doc("File", {"file_url": file["file_url"]})
                path = frappe.get_site_path(
                    "private" if fd.is_private else "public",
                    fd.file_url.lstrip("/")
                )
                with open(path, "rb") as fp:
                    attachments.append((fd.file_name, fp.read()))
            except Exception as e:
                frappe.log_error(str(e), f"Announcement Attachment [{doc.name}]")

    if doc.option == "HTML":
        raw = doc.message_tx_html or ""
    else:
        # Convert plain text to HTML paragraphs
        raw = _text_to_html(doc.message_body or "")

    raw_body = raw + image_tags
    return attachments, image_tags, raw_body


def _build_image_tags(docname):
    files = frappe.get_all(
        "File",
        filters={"attached_to_doctype": "Announcement", "attached_to_name": docname},
        fields=["file_url"]
    )
    return "".join(
        "<p style='text-align:center;margin:12px 0;'>"
        f"<img src='{f.file_url}' style='max-width:100%;height:auto;"
        f"border-radius:8px;display:block;margin:0 auto;'/></p>"
        for f in files
        if f.file_url.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp'))
    )


def _text_to_html(text):
    """Convert plain text to basic HTML paragraphs."""
    if not text:
        return ""
    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
    return "".join(f"<p style='margin:0 0 14px 0;'>{p}</p>" for p in paragraphs)


def _render_safe(template_str, context):
    """
    Safely render a Jinja template string.
    Falls back to the raw string if rendering fails (e.g. invalid syntax).
    """
    if not template_str:
        return ""
    try:
        return frappe.render_template(template_str, context)
    except Exception as e:
        frappe.log_error(str(e), "Announcement Template Render Error")
        return template_str  # return unrendered rather than empty


# ─────────────────────────────────────────────────────────────────────────────
# INTERNAL — PROFESSIONAL EMAIL HTML WRAPPER
# Wraps any body (plain HTML or text) in a responsive email shell that
# renders consistently in Gmail, Outlook, Apple Mail, and mobile clients.
# ─────────────────────────────────────────────────────────────────────────────

def _wrap_email_html(body, subject, sender_name):
    site_url = frappe.utils.get_url()
    year     = now_datetime().year
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta http-equiv="X-UA-Compatible" content="IE=edge">
<title>{subject or ''}</title>
<!--[if mso]>
<noscript><xml><o:OfficeDocumentSettings>
<o:PixelsPerInch>96</o:PixelsPerInch>
</o:OfficeDocumentSettings></xml></noscript>
<![endif]-->
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background-color: #f4f6f9; font-family: -apple-system, BlinkMacSystemFont,
          'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
          font-size: 15px; line-height: 1.7; color: #1a1a2e; -webkit-text-size-adjust: 100%; }}
  .email-wrapper {{ background-color: #f4f6f9; padding: 40px 20px; }}
  .email-container {{ max-width: 620px; margin: 0 auto; background: #ffffff;
                      border-radius: 12px; overflow: hidden;
                      box-shadow: 0 4px 24px rgba(0,0,0,0.08); }}
  .email-header {{ background: linear-gradient(135deg, #1e3a8a 0%, #2563eb 100%);
                   padding: 36px 40px; text-align: center; }}
  .email-header h1 {{ color: #ffffff; font-size: 22px; font-weight: 700;
                      letter-spacing: -0.3px; margin: 0; line-height: 1.3; }}
  .email-header p {{ color: rgba(255,255,255,0.85); font-size: 13px;
                     margin-top: 6px; }}
  .email-body {{ padding: 40px 40px 32px; }}
  .email-body h1, .email-body h2, .email-body h3 {{
      color: #1e3a8a; font-weight: 700; margin-bottom: 12px; line-height: 1.3; }}
  .email-body h1 {{ font-size: 22px; }}
  .email-body h2 {{ font-size: 18px; }}
  .email-body h3 {{ font-size: 16px; }}
  .email-body p {{ margin-bottom: 16px; color: #374151; font-size: 15px; }}
  .email-body ul, .email-body ol {{ padding-left: 20px; margin-bottom: 16px; }}
  .email-body li {{ margin-bottom: 6px; color: #374151; }}
  .email-body a {{ color: #2563eb; text-decoration: none; font-weight: 500; }}
  .email-body a:hover {{ text-decoration: underline; }}
  .email-body img {{ max-width: 100%; height: auto; border-radius: 8px;
                     display: block; margin: 0 auto 20px; }}
  .email-body table {{ width: 100%; border-collapse: collapse; margin-bottom: 20px; }}
  .email-body table td, .email-body table th {{
      border: 1px solid #e5e7eb; padding: 10px 14px; text-align: left; }}
  .email-body table th {{ background: #f0f6ff; color: #1e3a8a; font-weight: 700; }}
  .email-divider {{ border: none; border-top: 1px solid #e5e7eb;
                    margin: 24px 0; }}
  .email-cta {{ text-align: center; margin: 28px 0; }}
  .email-cta a {{ display: inline-block; background: linear-gradient(135deg,#2563eb,#1d4ed8);
                  color: #ffffff !important; padding: 14px 32px; border-radius: 8px;
                  font-weight: 700; font-size: 15px; text-decoration: none;
                  box-shadow: 0 4px 12px rgba(37,99,235,0.35); }}
  .email-footer {{ background: #f8fafc; padding: 24px 40px; text-align: center;
                   border-top: 1px solid #e5e7eb; }}
  .email-footer p {{ font-size: 12px; color: #9ca3af; margin-bottom: 4px; }}
  .email-footer a {{ color: #6b7280; text-decoration: none; }}
  @media only screen and (max-width: 600px) {{
    .email-body {{ padding: 28px 24px 24px; }}
    .email-header {{ padding: 28px 24px; }}
    .email-footer {{ padding: 20px 24px; }}
    .email-header h1 {{ font-size: 18px; }}
  }}
</style>
</head>
<body>
<div class="email-wrapper">
  <div class="email-container">

    <div class="email-header">
      <h1>{subject or 'Announcement'}</h1>
      <p>From {sender_name}</p>
    </div>

    <div class="email-body">
      {body}
    </div>

    <div class="email-footer">
      <p>© {year} {sender_name}. All rights reserved.</p>
      <p><a href="{site_url}">{site_url}</a></p>
    </div>

  </div>
</div>
</body>
</html>"""


# ─────────────────────────────────────────────────────────────────────────────
# INTERNAL — MESSAGING GATEWAYS
# ─────────────────────────────────────────────────────────────────────────────

def _send_whatsapp(phone, message, image_url=""):
    payload = {"phone": phone, "message": message}
    if image_url:
        payload["image_url"] = image_url
    r = requests.post(WHATSAPP_SMS_API, json=payload, timeout=15)
    r.raise_for_status()


def _send_sms(phone, message):
    payload = {"phone": phone, "message": message}
    r = requests.post(WHATSAPP_SMS_API, json=payload, timeout=15)
    r.raise_for_status()


def _unsubscribe_url(docname, rid):
    token = frappe.generate_hash(length=24)
    return (
        f"{frappe.utils.get_url()}/unsubscribe"
        f"?doc={docname}&rid={rid}&token={token}"
    )


def _unsubscribe_block(docname, rid):
    url = _unsubscribe_url(docname, rid)
    return (
        "<hr style='border:none;border-top:1px solid #e5e7eb;margin:32px 0 20px;'>"
        "<p style='font-size:12px;color:#9ca3af;text-align:center;margin:0;'>"
        "You received this because you are on our mailing list. "
        f"<a href='{url}' style='color:#9ca3af;text-decoration:underline;'>"
        "Unsubscribe</a></p>"
    )