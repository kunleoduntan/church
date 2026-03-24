#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Smart Attendance Installation Script
Automates the installation of smart attendance system

Usage:
    bench --site [site-name] execute ecclesia.attendance.install_smart_attendance

Or run directly in bench console:
    from ecclesia.attendance.install_smart_attendance import install
    install()
"""

import frappe
import json
import os

def install():
    """Main installation function"""
    
    print("\n" + "="*70)
    print("SMART ATTENDANCE SYSTEM - INSTALLATION")
    print("="*70 + "\n")
    
    try:
        # Step 1: Create Member Device DocType
        print("📋 Step 1: Creating Member Device DocType...")
        create_member_device_doctype()
        print("✅ Member Device DocType created\n")
        
        # Step 2: Import custom fields
        print("📋 Step 2: Importing custom fields...")
        import_custom_fields()
        print("✅ Custom fields imported\n")
        
        # Step 3: Create default settings
        print("📋 Step 3: Setting up default configuration...")
        setup_default_settings()
        print("✅ Default settings configured\n")
        
        # Step 4: Install dependencies check
        print("📋 Step 4: Checking dependencies...")
        check_dependencies()
        print("✅ Dependencies checked\n")
        
        # Step 5: Create sample data (optional)
        if frappe.confirm("Do you want to create sample QR codes for existing members?"):
            print("📋 Step 5: Generating QR codes for existing members...")
            generate_member_qr_codes()
            print("✅ QR codes generated\n")
        
        # Commit changes
        frappe.db.commit()
        
        print("\n" + "="*70)
        print("✅ INSTALLATION COMPLETE!")
        print("="*70)
        print("\nNext Steps:")
        print("1. Go to Church Settings → Smart Attendance Settings")
        print("2. Enable Smart Attendance")
        print("3. Set your church GPS coordinates")
        print("4. Configure your preferred check-in methods")
        print("5. Test with a few members first")
        print("\n" + "="*70 + "\n")
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Smart Attendance Installation Error")
        print(f"\n❌ Installation failed: {str(e)}")
        print("Check Error Log for details\n")


def create_member_device_doctype():
    """Create Member Device child table"""
    
    if frappe.db.exists('DocType', 'Member Device'):
        print("   Member Device DocType already exists, skipping...")
        return
    
    doctype = frappe.get_doc({
        "doctype": "DocType",
        "name": "Member Device",
        "module": "Church",
        "istable": 1,
        "editable_grid": 1,
        "autoname": "format:DEV-{####}",
        "fields": [
            {
                "fieldname": "device_name",
                "fieldtype": "Data",
                "label": "Device Name",
                "in_list_view": 1,
                "reqd": 1
            },
            {
                "fieldname": "device_type",
                "fieldtype": "Select",
                "label": "Device Type",
                "options": "Smartphone\nTablet\nLaptop\nOther",
                "default": "Smartphone",
                "in_list_view": 1
            },
            {
                "fieldname": "mac_address",
                "fieldtype": "Data",
                "label": "MAC Address",
                "in_list_view": 1
            },
            {
                "fieldname": "column_break_1",
                "fieldtype": "Column Break"
            },
            {
                "fieldname": "registered_on",
                "fieldtype": "Date",
                "label": "Registered On",
                "default": "Today",
                "read_only": 1
            },
            {
                "fieldname": "last_seen",
                "fieldtype": "Datetime",
                "label": "Last Seen",
                "in_list_view": 1,
                "read_only": 1
            },
            {
                "fieldname": "is_active",
                "fieldtype": "Check",
                "label": "Active",
                "default": "1"
            }
        ]
    })
    
    doctype.insert(ignore_permissions=True)


def import_custom_fields():
    """Import custom fields from JSON files"""
    
    import_paths = [
        'smart_attendance_church_settings_fields.json',
        'smart_attendance_member_fields.json',
        'smart_attendance_attendance_fields.json'
    ]
    
    for json_file in import_paths:
        print(f"   Importing {json_file}...")
        
        # Try to find file in multiple locations
        possible_paths = [
            os.path.join(frappe.get_app_path('ecclesia'), 'fixtures', json_file),
            os.path.join(frappe.get_app_path('ecclesia'), 'attendance', json_file),
            os.path.join(os.getcwd(), json_file)
        ]
        
        file_path = None
        for path in possible_paths:
            if os.path.exists(path):
                file_path = path
                break
        
        if not file_path:
            print(f"   ⚠️  {json_file} not found, please import manually")
            continue
        
        with open(file_path, 'r') as f:
            fields = json.load(f)
        
        for field in fields:
            try:
                # Check if field exists
                if frappe.db.exists('Custom Field', {
                    'dt': field['dt'],
                    'fieldname': field['fieldname']
                }):
                    continue
                
                # Create field
                doc = frappe.get_doc(field)
                doc.insert(ignore_permissions=True)
                
            except Exception as e:
                print(f"   ⚠️  Error creating {field['fieldname']}: {str(e)}")


def setup_default_settings():
    """Set up default Church Settings for smart attendance"""
    
    settings = frappe.get_single('Church Settings')
    
    # Set defaults if not already set
    if not settings.get('enable_smart_attendance'):
        settings.enable_smart_attendance = 0
    
    if not settings.get('attendance_check_in_window'):
        settings.attendance_check_in_window = 30
    
    if not settings.get('attendance_check_in_window_after'):
        settings.attendance_check_in_window_after = 30
    
    if not settings.get('qr_refresh_interval'):
        settings.qr_refresh_interval = '5 Minutes'
    
    if not settings.get('location_radius'):
        settings.location_radius = 100
    
    if not settings.get('max_check_ins_per_service'):
        settings.max_check_ins_per_service = 1
    
    if not settings.get('confirmation_message'):
        settings.confirmation_message = '✅ Welcome {member_name}! Your attendance has been recorded for {service_name} on {date}. God bless you!'
    
    if not settings.get('whatsapp_check_in_keyword'):
        settings.whatsapp_check_in_keyword = 'Present'
    
    settings.save(ignore_permissions=True)


def check_dependencies():
    """Check if required Python packages are installed"""
    
    required_packages = {
        'qrcode': 'qrcode',
        'PIL': 'pillow',
        'requests': 'requests'
    }
    
    missing = []
    
    for module_name, package_name in required_packages.items():
        try:
            __import__(module_name)
            print(f"   ✅ {package_name} installed")
        except ImportError:
            print(f"   ❌ {package_name} NOT installed")
            missing.append(package_name)
    
    if missing:
        print(f"\n   ⚠️  Missing packages: {', '.join(missing)}")
        print(f"   Install with: pip install {' '.join(missing)} --break-system-packages\n")
    else:
        print("   ✅ All dependencies installed")


def generate_member_qr_codes():
    """Generate QR codes for existing members"""
    
    from ecclesia.attendance.smart_attendance import generate_personal_qr_code
    
    members = frappe.get_all('Member', 
        filters={'personal_qr_code': ['is', 'not set']},
        limit=100  # Limit to 100 to avoid timeout
    )
    
    print(f"   Generating QR codes for {len(members)} members...")
    
    for idx, member in enumerate(members, 1):
        try:
            result = generate_personal_qr_code(member.name)
            if result.get('success'):
                print(f"   {idx}/{len(members)}: {member.name} ✅")
            else:
                print(f"   {idx}/{len(members)}: {member.name} ❌")
        except Exception as e:
            print(f"   {idx}/{len(members)}: {member.name} ❌ {str(e)}")
        
        if idx % 10 == 0:
            frappe.db.commit()  # Commit every 10 members
    
    frappe.db.commit()


# ============================================================================
# UNINSTALL FUNCTION
# ============================================================================

def uninstall():
    """Remove smart attendance customizations (use with caution!)"""
    
    print("\n" + "="*70)
    print("⚠️  SMART ATTENDANCE SYSTEM - UNINSTALLATION")
    print("="*70 + "\n")
    
    if not frappe.confirm("This will remove all smart attendance custom fields and data. Continue?"):
        print("Uninstallation cancelled.")
        return
    
    try:
        # Delete custom fields
        print("Removing custom fields...")
        
        custom_fields = frappe.get_all('Custom Field', filters={
            'dt': ['in', ['Member', 'Church Attendance', 'Church Settings']],
            'fieldname': ['like', '%smart%']
        })
        
        for cf in custom_fields:
            frappe.delete_doc('Custom Field', cf.name, force=True)
        
        # Delete Member Device DocType
        if frappe.db.exists('DocType', 'Member Device'):
            print("Removing Member Device DocType...")
            frappe.delete_doc('DocType', 'Member Device', force=True)
        
        frappe.db.commit()
        
        print("\n✅ Uninstallation complete")
        print("⚠️  You may need to restart the server\n")
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Smart Attendance Uninstall Error")
        print(f"\n❌ Uninstallation failed: {str(e)}\n")


# ============================================================================
# RUN INSTALLATION
# ============================================================================

if __name__ == "__main__":
    install()