"""
diagnostic.py — Run in bench console to find what is referencing
the missing fields: send_email, expiry_date, summary

Usage:
    bench --site yoursite.com console
    exec(open('diagnostic.py').read())
"""

import frappe
import re

MISSING_FIELDS = ["send_email", "expiry_date", "summary"]

print("\n" + "="*70)
print("ANNOUNCEMENT / BROADCAST FIELD REFERENCE DIAGNOSTIC")
print("="*70)

# ── 1. Server Scripts
print("\n[1] Checking Server Scripts...")
scripts = frappe.get_all(
    "Server Script",
    filters=[["script", "like", "%Broadcast%"]],
    fields=["name", "script_type", "reference_doctype", "script"]
)
if scripts:
    for s in scripts:
        refs = [f for f in MISSING_FIELDS if f in (s.script or "")]
        if refs:
            print(f"  ⚠️  Server Script '{s.name}' ({s.reference_doctype}) references: {refs}")
        else:
            print(f"  ℹ️  Server Script '{s.name}' mentions Broadcast (no missing fields found in it)")
else:
    print("  ✅ No Server Scripts reference Broadcast")

# Also check Announcement
scripts2 = frappe.get_all(
    "Server Script",
    filters=[["script", "like", "%Announcement%"]],
    fields=["name", "script_type", "reference_doctype", "script"]
)
for s in scripts2:
    refs = [f for f in MISSING_FIELDS if f in (s.script or "")]
    if refs:
        print(f"  ⚠️  Server Script '{s.name}' references MISSING fields: {refs}")

# ── 2. Custom Scripts (legacy)
print("\n[2] Checking Custom Scripts (legacy)...")
try:
    custom = frappe.get_all(
        "Custom Script",
        filters=[["dt", "in", ["Broadcast", "Announcement"]]],
        fields=["name", "dt", "script"]
    )
    for s in custom:
        refs = [f for f in MISSING_FIELDS if f in (s.script or "")]
        if refs:
            print(f"  ⚠️  Custom Script on '{s.dt}' references: {refs}")
        else:
            print(f"  ℹ️  Custom Script on '{s.dt}' — no missing field refs")
    if not custom:
        print("  ✅ No Custom Scripts found")
except Exception as e:
    print(f"  (Custom Script doctype not present: {e})")

# ── 3. Notification DocType
print("\n[3] Checking Notifications...")
notifs = frappe.get_all(
    "Notification",
    filters=[["document_type", "in", ["Broadcast", "Announcement"]]],
    fields=["name", "document_type", "condition", "message"]
)
for n in notifs:
    text = (n.condition or "") + (n.message or "")
    refs = [f for f in MISSING_FIELDS if f in text]
    if refs:
        print(f"  ⚠️  Notification '{n.name}' on {n.document_type} references: {refs}")
    else:
        print(f"  ℹ️  Notification '{n.name}' on {n.document_type} — OK")
if not notifs:
    print("  ✅ No Notifications found for Broadcast/Announcement")

# ── 4. Print Formats
print("\n[4] Checking Print Formats...")
pfs = frappe.get_all(
    "Print Format",
    filters=[["doc_type", "in", ["Broadcast", "Announcement"]]],
    fields=["name", "doc_type", "html"]
)
for p in pfs:
    refs = [f for f in MISSING_FIELDS if f in (p.html or "")]
    if refs:
        print(f"  ⚠️  Print Format '{p.name}' references: {refs}")
    else:
        print(f"  ℹ️  Print Format '{p.name}' — OK")
if not pfs:
    print("  ✅ No Print Formats found")

# ── 5. Workflow / Workflow Actions
print("\n[5] Checking Workflows...")
wfs = frappe.get_all(
    "Workflow",
    filters=[["document_type", "in", ["Broadcast", "Announcement"]]],
    fields=["name", "document_type"]
)
for w in wfs:
    print(f"  ℹ️  Workflow '{w.name}' on {w.document_type}")
if not wfs:
    print("  ✅ No Workflows found")

# ── 6. Check if old broadcast.py controller still exists
print("\n[6] Checking for stale broadcast.py controller...")
import os
app_paths = frappe.get_installed_apps()
for app in app_paths:
    app_path = frappe.get_app_path(app)
    for root, dirs, files in os.walk(app_path):
        for fname in files:
            if fname == "broadcast.py":
                full = os.path.join(root, fname)
                with open(full) as f:
                    content = f.read()
                refs = [field for field in MISSING_FIELDS if field in content]
                if refs:
                    print(f"  ⚠️  {full} references: {refs}")
                else:
                    print(f"  ℹ️  Found broadcast.py at {full} (no missing field refs)")

print("\n" + "="*70)
print("DIAGNOSTIC COMPLETE")
print("="*70 + "\n")