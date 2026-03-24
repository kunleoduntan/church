# apps/church/church/church/doctype/announcement/announcement.py
# Copyright (c) 2026, Value Impacts Consulting
#
# Whitelisted endpoints:
#   church.church.doctype.announcement.announcement.send_announcement
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
        self._validate_content()

    def before_submit(self):
        if not self.is_test and not self.recipients:
            frappe.throw("Cannot submit an Announcement with no recipients.")
        if self.schedule and self.schedule_time:
            if get_datetime(self.schedule_time) < now_datetime():
                frappe.throw("Schedule time cannot be in the past.")

    def on_submit(self):
        if self.schedule and self.schedule_time:
            self.db_set("status", "Scheduled")

    def _validate_content(self):
        mt = self.message_type or ""
        if "Email" in mt and self.option == "HTML" and not self.message_tx_html:
            frappe.msgprint("Warning: HTML format selected but no HTML body provided.", alert=True)
        elif "Email" in mt and self.option == "Text" and not self.message_body:
            frappe.msgprint("Warning: Text format selected but no text body provided.", alert=True)
        if "WhatsApp" in mt and not self.whatsapp_message_body:
            frappe.msgprint("Warning: WhatsApp selected but no WhatsApp message provided.", alert=True)
        if "SMS" in mt and not self.sms_message_body:
            frappe.msgprint("Warning: SMS selected but no SMS message provided.", alert=True)

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
# MAIN SEND — whitelisted, called directly from the JS button
# Mirrors exactly how broadcast_processor.py works
# ─────────────────────────────────────────────────────────────────────────────

@frappe.whitelist()
def send_announcement(docname):
    doc = frappe.get_doc("Announcement", docname)

    subject = doc.subject or "No Subject"
    mt      = doc.message_type or "Email"

    do_email    = "Email"    in mt
    do_whatsapp = "WhatsApp" in mt
    do_sms      = "SMS"      in mt

    # ── 1. Get attached files ────────────────────────────────────────────────
    files = frappe.get_all(
        "File",
        filters={"attached_to_doctype": "Announcement", "attached_to_name": doc.name},
        fields=["file_url", "file_name", "is_private"]
    )
    image_urls       = []
    attachment_files = []
    for f in files:
        if f["file_url"].lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp')):
            image_urls.append(f["file_url"])
        else:
            attachment_files.append(f)

    # ── 2. Build image tags ──────────────────────────────────────────────────
    image_tags = "".join(
        "<p style='text-align:center;'>"
        f"<img src='{url}' style='max-width:100%;height:auto;border-radius:6px;'/>"
        "</p>"
        for url in image_urls
    )

    # ── 3. Build message body ────────────────────────────────────────────────
    if doc.option == "HTML":
        message_body = doc.message_tx_html or ""
    else:
        message_body = doc.message_body or ""
    message_with_images = message_body + image_tags

    # ── 4. Build attachments list ────────────────────────────────────────────
    attachments = []
    if doc.include_attachments:
        for file in attachment_files:
            try:
                file_doc  = frappe.get_doc("File", {"file_url": file["file_url"]})
                file_path = frappe.get_site_path(
                    "private" if file_doc.is_private else "public",
                    file_doc.file_url.lstrip("/")
                )
                with open(file_path, "rb") as fp:
                    attachments.append((file_doc.file_name, fp.read()))
            except Exception as e:
                frappe.log_error(str(e), f"Announcement Attachment Error [{docname}]")

    # ── 5. TEST SEND ─────────────────────────────────────────────────────────
    # Same pattern as Broadcast: render once with dummy context, send with now=True
    if doc.is_test:
        context = {
            "full_name":       "Test Recipient",
            "salutation":      "Dear",
            "sender_name":     doc.from_name or "The Team",
            "summary":         doc.summary   or "",
            "unsubscribe_url": "#"
        }

        if do_email and doc.test_email:
            rendered = frappe.render_template(message_with_images, context)
            frappe.sendmail(
                recipients       = [doc.test_email],
                subject          = f"[TEST] {subject}",
                message          = rendered,
                attachments      = attachments,
                reference_doctype= "Announcement",
                reference_name   = doc.name,
                now              = True,    # send immediately like Broadcast test
                template         = False
            )
            frappe.msgprint(f"Test email sent to {doc.test_email}")

        if do_whatsapp and doc.test_phone_number:
            _send_whatsapp(doc.test_phone_number,
                           doc.whatsapp_message_body or "",
                           doc.whatsapp_image_url    or "")

        if do_sms and doc.test_phone_number:
            _send_sms(doc.test_phone_number, doc.sms_message_body or "")

        return {"success": True, "test": True}

    # ── 6. BULK SEND ─────────────────────────────────────────────────────────
    # Loop recipients exactly like broadcast_processor.py does
    failed = []

    for recipient in doc.recipients:
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

        # ── Email ─────────────────────────────────────────────────────────
        if do_email and recipient.email:
            try:
                rendered = frappe.render_template(message_with_images, context)
                if doc.unsubscribe_link:
                    rendered += _unsubscribe_block(doc.name, recipient.name)

                sender = (
                    f"{doc.from_name} <{doc.from_email}>"
                    if doc.from_email else None
                )
                frappe.sendmail(
                    recipients       = [recipient.email],
                    subject          = subject,
                    message          = rendered,
                    sender           = sender,
                    reply_to         = doc.reply_to_email or doc.from_email,
                    attachments      = attachments,
                    reference_doctype= "Announcement",
                    reference_name   = doc.name,
                    now              = False,   # queue it — Frappe flushes every 1 min
                    template         = False
                )
                frappe.db.set_value("Announcement Recipient", recipient.name,
                                    "email_status", "Sent")
            except Exception as e:
                err = str(e)
                row_errors.append(f"Email: {err}")
                frappe.db.set_value("Announcement Recipient", recipient.name,
                                    "email_status", "Failed")
                frappe.log_error(err, f"Announcement Email Error [{docname}]")

        # ── WhatsApp ──────────────────────────────────────────────────────
        if do_whatsapp and recipient.mobile_phone:
            try:
                msg = frappe.render_template(doc.whatsapp_message_body or "", context)
                _send_whatsapp(recipient.mobile_phone, msg,
                               doc.whatsapp_image_url or "")
                frappe.db.set_value("Announcement Recipient", recipient.name,
                                    "whatsapp_status", "Sent")
            except Exception as e:
                err = str(e)
                row_errors.append(f"WhatsApp: {err}")
                frappe.db.set_value("Announcement Recipient", recipient.name,
                                    "whatsapp_status", "Failed")
                frappe.log_error(err, f"Announcement WhatsApp Error [{docname}]")

        # ── SMS ───────────────────────────────────────────────────────────
        if do_sms and recipient.mobile_phone:
            try:
                msg = frappe.render_template(doc.sms_message_body or "", context)
                _send_sms(recipient.mobile_phone, msg)
                frappe.db.set_value("Announcement Recipient", recipient.name,
                                    "sms_status", "Sent")
            except Exception as e:
                err = str(e)
                row_errors.append(f"SMS: {err}")
                frappe.db.set_value("Announcement Recipient", recipient.name,
                                    "sms_status", "Failed")
                frappe.log_error(err, f"Announcement SMS Error [{docname}]")

        # ── Per-row delivery status ────────────────────────────────────────
        if row_errors:
            frappe.db.set_value("Announcement Recipient", recipient.name, {
                "delivery_status": "Failed",
                "error_message":   "; ".join(row_errors),
                "sent_at":         now_datetime()
            })
            failed.append(recipient.email or recipient.mobile_phone)
        else:
            frappe.db.set_value("Announcement Recipient", recipient.name, {
                "delivery_status": "Sent",
                "error_message":   "",
                "sent_at":         now_datetime()
            })

    frappe.db.commit()

    # ── 7. Final status — same logic as Broadcast ────────────────────────────
    total    = len(doc.recipients)
    n_failed = len(failed)
    n_sent   = total - n_failed

    if n_failed == 0:
        doc.db_set("status", "Sent")
        doc.db_set("sent", 1)
        frappe.msgprint(f"Announcement sent to {n_sent} recipient(s).")
    elif n_sent == 0:
        doc.db_set("status", "Failed")
        frappe.msgprint("Announcement failed for all recipients. Check the Error Log.")
    else:
        doc.db_set("status", "Partially Sent")
        frappe.log_error("\n".join(failed), "Announcement Partial Failure")
        frappe.msgprint(f"Announcement sent to {n_sent}, failed for {n_failed}. Check Error Log.")

    doc.db_set({
        "sent_count":       n_sent,
        "failed_count":     n_failed,
        "pending_count":    0,
        "total_recipients": total
    })

    return {"success": True, "sent": n_sent, "failed": n_failed, "test": False}


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
        frappe.throw("Only Scheduled announcements can be cancelled this way.")
    doc.db_set("status", "Cancelled")
    return {"cancelled": True}


@frappe.whitelist()
def preview_message(docname):
    doc  = frappe.get_doc("Announcement", docname)
    body = doc.message_tx_html if doc.option == "HTML" else (doc.message_body or "")
    context = {
        "full_name":       "John Doe",
        "salutation":      "Dear",
        "sender_name":     doc.from_name or "The Team",
        "summary":         doc.summary   or "",
        "unsubscribe_url": "#"
    }
    return {
        "html":    frappe.render_template(body or "", context),
        "subject": doc.subject
    }


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
        filters={
            "docstatus":     1,
            "status":        "Scheduled",
            "schedule":      1,
            "schedule_time": ["<=", now]
        },
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
# INTERNAL HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _send_whatsapp(phone, message, image_url=""):
    """
    Same API as Broadcast (smsalat.com).
    """
    payload = {"phone": phone, "message": message}
    if image_url:
        payload["image_url"] = image_url
    response = requests.post(WHATSAPP_SMS_API, json=payload)
    response.raise_for_status()


def _send_sms(phone, message):
    """
    Same API as Broadcast (smsalat.com).
    """
    payload = {"phone": phone, "message": message}
    response = requests.post(WHATSAPP_SMS_API, json=payload)
    response.raise_for_status()


def _unsubscribe_url(docname, rid):
    token = frappe.generate_hash(length=24)
    return (
        f"{frappe.utils.get_url()}/unsubscribe"
        f"?doc={docname}&rid={rid}&token={token}"
    )


def _unsubscribe_block(docname, rid):
    url = _unsubscribe_url(docname, rid)
    return (
        "<br><br>"
        "<hr style='border:none;border-top:1px solid #eee;margin:24px 0;'>"
        "<p style='font-size:11px;color:#aaa;text-align:center;'>"
        "You received this because you are on our mailing list. "
        f"<a href='{url}' style='color:#aaa;'>Unsubscribe</a></p>"
    )