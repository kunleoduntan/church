# Copyright (c) 2026, kunle
# License: MIT

import frappe
from frappe import _
from frappe.utils import now_datetime, cint, flt, get_url
import re


class AttendanceMarking(frappe.model.document.Document):

	# --------------------------------------------------------
	# Core Lifecycle
	# --------------------------------------------------------

	def validate(self):
		self._compute_summary()

	def on_submit(self):
		self._compute_summary()

	def on_cancel(self):
		self._cancel_linked_attendance()


	# --------------------------------------------------------
	# Attendance Summary
	# --------------------------------------------------------

	def _compute_summary(self):

		total = len(self.attendance)
		present = sum(1 for r in self.attendance if cint(r.present))
		absent = total - present

		self.total_subscribers = total
		self.total_present = present
		self.total_absent = absent
		self.attendance_pct = flt((present / total) * 100, 1) if total else 0.0

		buckets = {
			"Men":           {"total": 0, "present": 0},
			"Women":         {"total": 0, "present": 0},
			"Youth":         {"total": 0, "present": 0},
			"Teens":         {"total": 0, "present": 0},
			"Children":      {"total": 0, "present": 0},
			"_unclassified": {"total": 0, "present": 0},
		}

		for row in self.attendance:
			group = (row.demographic_group or "").strip()
			key = group if group in buckets else "_unclassified"
			buckets[key]["total"] += 1
			if cint(row.present):
				buckets[key]["present"] += 1

		self.total_men               = buckets["Men"]["total"]
		self.total_men_present       = buckets["Men"]["present"]
		self.total_women             = buckets["Women"]["total"]
		self.total_women_present     = buckets["Women"]["present"]
		self.total_youth             = buckets["Youth"]["total"]
		self.total_youth_present     = buckets["Youth"]["present"]
		self.total_teens             = buckets["Teens"]["total"]
		self.total_teens_present     = buckets["Teens"]["present"]
		self.total_children          = buckets["Children"]["total"]
		self.total_children_present  = buckets["Children"]["present"]
		self.total_unclassified      = buckets["_unclassified"]["total"]
		self.total_unclassified_present = buckets["_unclassified"]["present"]

		def pct_of_total(n):
			return flt((n / total) * 100, 1) if total else 0.0

		def pct_of_group(p, t):
			return flt((p / t) * 100, 1) if t else 0.0

		self.pct_men          = pct_of_total(buckets["Men"]["total"])
		self.pct_women        = pct_of_total(buckets["Women"]["total"])
		self.pct_youth        = pct_of_total(buckets["Youth"]["total"])
		self.pct_teens        = pct_of_total(buckets["Teens"]["total"])
		self.pct_children     = pct_of_total(buckets["Children"]["total"])
		self.pct_unclassified = pct_of_total(buckets["_unclassified"]["total"])

		self.pct_men_present          = pct_of_group(buckets["Men"]["present"],           buckets["Men"]["total"])
		self.pct_women_present        = pct_of_group(buckets["Women"]["present"],         buckets["Women"]["total"])
		self.pct_youth_present        = pct_of_group(buckets["Youth"]["present"],         buckets["Youth"]["total"])
		self.pct_teens_present        = pct_of_group(buckets["Teens"]["present"],         buckets["Teens"]["total"])
		self.pct_children_present     = pct_of_group(buckets["Children"]["present"],      buckets["Children"]["total"])
		self.pct_unclassified_present = pct_of_group(buckets["_unclassified"]["present"], buckets["_unclassified"]["total"])


	# --------------------------------------------------------
	# Cancel linked Church Attendance records
	# --------------------------------------------------------

	def _cancel_linked_attendance(self):

		records = frappe.get_all(
			"Church Attendance",
			filters={"attendance_marking": self.name},
			fields=["name", "docstatus"]
		)

		cancelled = 0
		deleted = 0

		for r in records:
			try:
				doc = frappe.get_doc("Church Attendance", r.name)
				if doc.docstatus == 1:
					doc.cancel()
					cancelled += 1
				doc.delete()
				deleted += 1
			except Exception:
				frappe.log_error(
					frappe.get_traceback(),
					"Attendance Cancel/Delete Failed"
				)

		frappe.db.set_value("Attendance Marking", self.name, "attendance_created", 0)
		frappe.db.commit()

		frappe.msgprint(
			_("{0} attendance record(s) cancelled and {1} deleted.").format(cancelled, deleted)
		)


# --------------------------------------------------------
# Fetch Members
# --------------------------------------------------------

@frappe.whitelist()
def fetch_member_list(branch, demography=None):

	filters = {"branch": branch, "member_status": "Active"}

	if demography and demography != "All":
		filters["demographic_group"] = demography

	return frappe.get_all(
		"Member",
		filters=filters,
		fields=[
			"name as member_id",
			"full_name",
			"salutation",
			"mobile_phone",
			"email",
			"whatsapp_number",
			"gender",
			"demographic_group",
		],
		order_by="full_name asc",
	)


# --------------------------------------------------------
# Create Attendance Records
# --------------------------------------------------------

@frappe.whitelist()
def create_attendance_records(docname):

	doc = frappe.get_doc("Attendance Marking", docname)

	if doc.docstatus != 1:
		frappe.throw(_("Document must be submitted before creating attendance records."))

	if doc.attendance_created:
		frappe.throw(_("Attendance records have already been created for this document."))

	if not doc.attendance:
		frappe.throw(_("Attendance table is empty. Please fetch members first."))

	if not doc.service_type:
		frappe.throw(_("Please set a Service Type before creating attendance records."))

	if not doc.service_instance:
		frappe.throw(_("Please select a Service Instance before creating attendance records."))

	created = 0
	skipped = 0
	errors  = []

	for row in doc.attendance:

		if not row.member_id:
			skipped += 1
			continue

		# ── Only create records for present members ───────────────────────
		if not cint(row.present):
			skipped += 1
			continue

		# ── Existence check: service_instance + full_name + service_date ──
		if frappe.db.exists("Church Attendance", {
			"service_instance": doc.service_instance,
			"full_name":        row.full_name,
			"service_date":     doc.service_date,
		}):
			skipped += 1
			continue

		try:
			catt = frappe.new_doc("Church Attendance")

			catt.attendance_marking = doc.name
			catt.service_date       = doc.service_date
			catt.service_instance   = doc.service_instance
			catt.service_type       = doc.service_type
			catt.branch             = doc.branch

			catt.member_id          = row.member_id
			catt.full_name          = row.full_name

			catt.present            = 1
			catt.is_visitor         = cint(row.is_visitor) if hasattr(row, "is_visitor") else 0
			catt.visitor_source     = (row.visitor_source
				if hasattr(row, "visitor_source") and cint(row.is_visitor)
				else None)

			catt.demography         = row.demographic_group
			catt.checkin_method     = "Manual"
			catt.marked_by          = frappe.session.user

			catt.flags.ignore_permissions = True
			catt.insert()
			catt.submit()

			created += 1

		except Exception as exc:
			err = "{0}: {1}".format(row.full_name or row.member_id, str(exc))
			errors.append(err)
			frappe.log_error(title="Church Attendance Creation Error", message=err)

	# ── Persist & commit ──────────────────────────────────────────────────
	update_values = {"attendance_created": 1}

	if errors:
		error_block = (
			"\n-- Attendance Creation Errors [{0}] --\n".format(now_datetime())
			+ "\n".join(errors)
		)
		existing_log = frappe.db.get_value("Attendance Marking", docname, "notification_log") or ""
		update_values["notification_log"] = existing_log + error_block

	frappe.db.set_value("Attendance Marking", docname, update_values)
	frappe.db.commit()

	parts = [
		"{0} record(s) created.".format(created),
		"{0} skipped.".format(skipped),
	]
	if errors:
		parts.append("{0} error(s) — check Error Log.".format(len(errors)))

	frappe.msgprint(
		_("{0} attendance record(s) created, {1} skipped.").format(created, skipped),
		indicator="green" if not errors else "orange",
		alert=True
	)

	return {
		"created": created,
		"skipped": skipped,
		"errors":  errors,
		"message": " ".join(parts),
	}


# --------------------------------------------------------
# Notifications
# --------------------------------------------------------

@frappe.whitelist()
def send_notifications(docname):

	doc = frappe.get_doc("Attendance Marking", docname)

	if not doc.message_type:
		frappe.throw(_("Message Type is required."))

	if not doc.attendance:
		frappe.throw(_("Attendance table is empty."))

	rows = list(doc.attendance)

	if cint(doc.notify_present_only):
		rows = [r for r in rows if cint(r.present)]
	elif cint(doc.notify_absent_only):
		rows = [r for r in rows if not cint(r.present)]

	if not rows:
		frappe.throw(_("No recipients match the current filter criteria."))

	test_mode = cint(doc.is_test_email)
	sent = 0
	log = []

	for row in rows:

		row_ok = True

		try:
			if doc.message_type in ("Email", "All"):
				_send_email(doc, row, test_mode)

			if doc.message_type in ("WhatsApp", "All"):
				_send_whatsapp(doc, row, test_mode)

			if doc.message_type in ("SMS", "All"):
				_send_sms(doc, row, test_mode)

		except Exception as exc:
			row_ok = False
			log.append("FAIL: {0} — {1}".format(row.full_name, str(exc)))
			frappe.log_error(title="Attendance Notification Error", message=str(exc))

		if row_ok:
			frappe.db.set_value("Attendance Marking Item", row.name, "notification_sent", 1)
			sent += 1
			log.append("OK: {0}".format(row.full_name))

	log_entry = "\n-- Notifications [{0}] --\n".format(now_datetime()) + "\n".join(log)
	existing_log = frappe.db.get_value("Attendance Marking", docname, "notification_log") or ""

	frappe.db.set_value("Attendance Marking", docname, {
		"notification_log": existing_log + log_entry,
		"sent": 1,
	})
	frappe.db.commit()

	return {
		"sent":    sent,
		"total":   len(rows),
		"log":     log_entry,
		"message": "{0} of {1} notification(s) sent.".format(sent, len(rows)),
	}


# --------------------------------------------------------
# Messaging Helpers
# --------------------------------------------------------

def _render_message(doc, row, is_html=False):

	body = ""

	if doc.message_type in ("Email", "All") and doc.option == "HTML":
		body = doc.message_tx_html or ""
	elif doc.message_type in ("WhatsApp", "All"):
		body = doc.whatsapp_message_body or ""
	else:
		body = doc.message_body or ""

	present_label = "Present" if cint(row.present) else "Absent"

	replacements = {
		"{{member_name}}":    row.full_name or "",
		"{{salutation}}":     row.salutation or "",
		"{{service_date}}":   str(doc.service_date),
		"{{branch}}":         doc.branch or "",
		"{{subject}}":        doc.subject or "",
		"{{service_type}}":   doc.service_type or "",
		"{{present_status}}": present_label,
	}

	for key, val in replacements.items():
		body = body.replace(key, val)

	return body


def _get_church_logo():
	"""Fetch church logo from Company doctype"""
	try:
		company = frappe.get_doc("Company", frappe.defaults.get_user_default("Company") or "Your Church")
		if company and company.company_logo:
			return company.company_logo
	except:
		pass
	return None


def _wrap_in_container(content, subject, church_logo=None):
	"""Wrap content in a beautiful container with blue theme and logo"""
	
	logo_html = ""
	if church_logo:
		logo_html = f'''
		<div class="logo-container">
			<img src="{church_logo}" alt="Church Logo" class="church-logo">
		</div>
		'''
	else:
		logo_html = '''
		<div class="logo-container">
			<div class="logo-placeholder">✝️</div>
		</div>
		'''
	
	return f'''
	<!DOCTYPE html>
	<html>
	<head>
		<meta charset="UTF-8">
		<meta name="viewport" content="width=device-width, initial-scale=1.0">
		<style>
			@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
			
			body {{
				margin: 0;
				padding: 0;
				background-color: #eef2f6;
				font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
				-webkit-font-smoothing: antialiased;
			}}
			
			.email-wrapper {{
				max-width: 600px;
				margin: 30px auto;
				background: #ffffff;
				border-radius: 24px;
				box-shadow: 0 25px 50px -12px rgba(0, 50, 100, 0.25);
				overflow: hidden;
				border: 1px solid rgba(0, 112, 243, 0.15);
			}}
			
			.email-header {{
				background: linear-gradient(145deg, #0a2540 0%, #1a3b5c 100%);
				padding: 35px 40px 25px;
				text-align: center;
				border-bottom: 5px solid #0070f3;
			}}
			
			.logo-container {{
				margin-bottom: 15px;
				display: inline-block;
			}}
			
			.church-logo {{
				max-width: 110px;
				max-height: 110px;
				border-radius: 50%;
				border: 4px solid rgba(255, 255, 255, 0.2);
				background: white;
				padding: 5px;
				box-shadow: 0 15px 30px -10px rgba(0, 0, 0, 0.3);
			}}
			
			.logo-placeholder {{
				width: 100px;
				height: 100px;
				border-radius: 50%;
				background: rgba(255, 255, 255, 0.1);
				backdrop-filter: blur(10px);
				display: flex;
				align-items: center;
				justify-content: center;
				font-size: 48px;
				color: white;
				border: 3px solid rgba(255, 255, 255, 0.2);
				margin: 0 auto;
			}}
			
			.email-subject {{
				color: white;
				font-size: 24px;
				font-weight: 600;
				margin: 15px 0 5px;
				letter-spacing: -0.3px;
				word-break: break-word;
			}}
			
			.email-content {{
				padding: 40px 45px;
				background: #ffffff;
			}}
			
			.message-body {{
				color: #2c3e50;
				font-size: 16px;
				line-height: 1.7;
			}}
			
			.message-body p {{
				margin: 0 0 20px 0;
			}}
			
			.message-body h1, .message-body h2, .message-body h3 {{
				color: #0a2540;
				margin-top: 25px;
				margin-bottom: 15px;
			}}
			
			.footer {{
				background: #f8fafd;
				padding: 30px 45px 25px;
				text-align: center;
				border-top: 2px solid #e9edf2;
			}}
			
			.footer-text {{
				color: #5a6b7c;
				font-size: 14px;
				line-height: 1.6;
				margin: 5px 0;
			}}
			
			.blessing {{
				font-size: 18px;
				color: #0070f3;
				font-weight: 500;
				margin: 15px 0 5px;
				font-style: italic;
			}}
			
			.divider {{
				height: 3px;
				width: 60px;
				background: linear-gradient(90deg, #0070f3, #00a8ff);
				margin: 25px auto;
				border-radius: 3px;
			}}
			
			@media only screen and (max-width: 600px) {{
				.email-wrapper {{
					margin: 15px;
					border-radius: 20px;
				}}
				.email-header {{
					padding: 25px 25px 20px;
				}}
				.email-content {{
					padding: 30px 25px;
				}}
				.footer {{
					padding: 25px 25px 20px;
				}}
			}}
		</style>
	</head>
	<body>
		<div class="email-wrapper">
			<!-- Header with Logo -->
			<div class="email-header">
				{logo_html}
				<div class="email-subject">{subject}</div>
			</div>
			
			<!-- Main Content -->
			<div class="email-content">
				<div class="message-body">
					{content}
				</div>
			</div>
			
			<!-- Footer -->
			<div class="footer">
				<div class="divider"></div>
				<p class="footer-text">"For where two or three gather in my name, there am I with them."</p>
				<p class="footer-text">— Matthew 18:20</p>
				<p class="blessing">🙏 God bless you</p>
				<p class="footer-text" style="margin-top: 20px; font-size: 12px; opacity: 0.6;">
					This is an automated message. Please do not reply to this email.
				</p>
			</div>
		</div>
	</body>
	</html>
	'''


def _send_email(doc, row, test_mode=False):

	recipient = doc.test_email if test_mode else row.email
	if not recipient:
		return

	# Get church logo
	church_logo = _get_church_logo()

	if doc.email_template:
		template = frappe.get_doc("Email Template", doc.email_template)
		subject = frappe.render_template(template.subject, {"doc": doc, "row": row})
		body = frappe.render_template(template.response, {"doc": doc, "row": row})
		
		# Wrap the content in our beautiful container
		final_body = _wrap_in_container(body, subject, church_logo)
	else:
		subject = doc.subject or "Church Notification"
		body = _render_message(doc, row, is_html=(doc.option == "HTML"))
		
		if doc.option == "HTML":
			# If it's HTML content, wrap it directly
			final_body = _wrap_in_container(body, subject, church_logo)
		else:
			# If it's plain text, convert to HTML paragraphs first
			html_content = body.replace('\n', '<br>')
			final_body = _wrap_in_container(f'<p>{html_content}</p>', subject, church_logo)

	frappe.sendmail(
		recipients=[recipient],
		subject=subject,
		message=final_body,
		now=not cint(doc.schedule),
		send_after=doc.schedule_time if cint(doc.schedule) else None,
		reference_doctype="Attendance Marking",
		reference_name=doc.name,
	)


def _send_whatsapp(doc, row, test_mode=False):

	phone = doc.test_phone_number if test_mode else (row.whatsapp_number or row.mobile_phone)
	if not phone:
		return

	if doc.whatsapp_template:
		template = frappe.get_doc("Email Template", doc.whatsapp_template)
		body = frappe.render_template(template.response, {"doc": doc, "row": row})
	else:
		body = _render_message(doc, row)

	# TODO: integrate your WhatsApp gateway here
	frappe.logger().info("[WhatsApp STUB] To: {0} | Body: {1}".format(phone, body[:80]))


def _send_sms(doc, row, test_mode=False):

	phone = doc.test_phone_number if test_mode else row.mobile_phone
	if not phone:
		return

	body = _render_message(doc, row)

	# TODO: integrate your SMS gateway here
	frappe.logger().info("[SMS STUB] To: {0} | Body: {1}".format(phone, body[:80]))