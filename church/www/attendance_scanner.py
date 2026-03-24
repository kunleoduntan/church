# File: attendance_management/www/attendance_scanner.py
# This creates a web page route at: yoursite.com/attendance-scanner

import frappe

def get_context(context):
    """
    Context for QR Scanner web page
    Accessible without login (allow_guest=True)
    """
    context.no_cache = 1
    context.show_sidebar = False
    
    # Get checkpoint locations for dropdown
    locations = frappe.get_all(
        'Checkpoint Location',
        filters={'is_active': 1},
        fields=['name', 'location_name'],
        order_by='location_name'
    )
    
    context.checkpoint_locations = locations
    context.title = "Attendance Scanner"
    
    return context