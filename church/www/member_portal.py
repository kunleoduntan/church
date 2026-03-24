# Copyright (c) 2026, Value Impacts Consulting
# License: MIT
#
# church/www/member_portal.py
# ─────────────────────────────────────────────────────────────────────────────
# Frappe www page controller for the Church Member Portal.
#
# IMPORTANT — Authentication model
# ─────────────────────────────────
# Members are NOT required to be ERPNext / Frappe users.
# Authentication is handled entirely inside member_portal.html via a
# login dialog that calls:
#     church.api.member_portal_api.portal_login(email, qr_token)
#
# On success the API writes a short-lived token to an httpOnly cookie
# (portal_sid).  Every subsequent API call reads that cookie via
# _get_member() in member_portal_api.py.
#
# get_context() therefore does NOT redirect guests — it always serves the
# HTML shell.  The JS inside the shell decides whether to show the login
# dialog or the portal dashboard based on the cookie state.
#
# File layout on disk:
#   apps/church/church/www/member_portal.py       <- this file
#   apps/church/church/www/member_portal.html     <- SPA shell + login dialog
#   apps/church/church/api/__init__.py            <- empty package marker
#   apps/church/church/api/member_portal_api.py   <- all API handlers
#
# Member DocType - two fields required (add via Customize Form if missing):
#   portal_session_token   Data      (stores the active session UUID)
#   portal_session_expiry  Datetime  (token expiry - 24-hour rolling window)
#
# URL:  https://yoursite.com/member_portal
# ─────────────────────────────────────────────────────────────────────────────

import frappe
import json


def get_context(context):
    """
    Serve the portal shell to everyone - guests and logged-in users alike.
    The HTML/JS layer handles the login gate via its own dialog + cookie auth.
    Frappe's own session is irrelevant for this portal.
    """
    context.no_cache     = 1
    context.show_sidebar = 0
    context.title        = "Member Portal"

    # Minimal server-side boot data - the JS uses this only to know the
    # site name for display purposes.  It carries no auth information.
    context.boot = json.dumps({
        "site": frappe.local.site,
    })