# Copyright (c) 2025, kunle and contributors
# For license information, please see license.txt


import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now, today, get_datetime, add_days
import qrcode
import io
import base64
import json
from church.utils.mac_encryption_utils import MACAddressSecurityManager

class PersonRegistry(Document):
    def autoname(self):
        """Auto-generate registry ID"""
        self.name = frappe.model.naming.make_autoname('PR-.#####')
        self.registry_id = self.name
    
    def validate(self):
        """Validate person registry data"""
        # Validate email uniqueness
        if self.email_id:
            existing = frappe.db.exists('Person Registry', {
                'email_id': self.email_id,
                'name': ['!=', self.name]
            })
            if existing:
                frappe.throw(_('Email ID already exists'))
        
        # Validate mobile uniqueness
        if self.mobile_number:
            existing = frappe.db.exists('Person Registry', {
                'mobile_number': self.mobile_number,
                'name': ['!=', self.name]
            })
            if existing:
                frappe.throw(_('Mobile number already exists'))
    
    def before_save(self):
        """Generate QR code if new record"""
        if self.is_new():
            self.generate_qr_code()
    
    def after_insert(self):
        """Send welcome email with QR code"""
        if self.email_id:
            self.send_qr_code_email()
    
    def generate_qr_code(self):
        """Generate QR code with security token"""
        # Generate unique security token
        self.qr_security_token = frappe.generate_hash(length=32)
        self.qr_last_regenerated = now()
        
        # Set token expiry
        settings = frappe.get_single('Attendance System Settings')
        validity_days = settings.qr_token_validity_days or 90
        self.token_expiry_date = add_days(today(), validity_days)
        
        # Create QR data
        qr_data = {
            'type': 'attendance',
            'registry_id': self.name,
            'token': self.qr_security_token,
            'name': self.full_name,
            'expires': str(self.token_expiry_date)
        }
        
        # Generate QR code image
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            box_size=10,
            border=4,
        )
        qr.add_data(json.dumps(qr_data))
        qr.make(fit=True)
        
        # Create image
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Convert to bytes
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        qr_bytes = buffer.getvalue()
        
        # Save as file
        file_name = f"QR_{self.name}_{frappe.utils.now_datetime().strftime('%Y%m%d_%H%M%S')}.png"
        
        # Delete old QR code file if exists
        if self.qr_code_image:
            try:
                old_file = frappe.get_doc('File', {'file_url': self.qr_code_image})
                old_file.delete()
            except:
                pass
        
        file_doc = frappe.get_doc({
            'doctype': 'File',
            'file_name': file_name,
            'content': qr_bytes,
            'is_private': 0,
            'folder': 'Home/Attachments',
            'attached_to_doctype': 'Person Registry',
            'attached_to_name': self.name
        })
        file_doc.save(ignore_permissions=True)
        
        self.qr_code_image = file_doc.file_url
        self.qr_identity_code = self.name  # For reference
    
    def send_qr_code_email(self):
        """Send QR code to person via email"""
        if not self.email_id:
            return
        
        try:
            frappe.sendmail(
                recipients=[self.email_id],
                subject=_('Your Attendance QR Code'),
                template='qr_code_email',
                args={
                    'full_name': self.full_name,
                    'registry_id': self.name,
                    'qr_code_url': frappe.utils.get_url(self.qr_code_image),
                    'expires': self.token_expiry_date
                },
                attachments=[{
                    'fname': f'QR_Code_{self.name}.png',
                    'fcontent': self.get_qr_code_content()
                }],
                now=True
            )
        except Exception as e:
            frappe.log_error(f'Failed to send QR email: {str(e)}', 'QR Email Error')


# ==================== WHITELISTED API METHODS ====================

@frappe.whitelist()
def regenerate_qr_code(registry_id):
    """
    Regenerate QR code for a person
    
    Args:
        registry_id: Person Registry ID
    
    Returns:
        dict: Success status and new QR code URL
    """
    if not frappe.has_permission('Person Registry', 'write'):
        frappe.throw(_('Insufficient permissions'))
    
    person = frappe.get_doc('Person Registry', registry_id)
    person.generate_qr_code()
    person.save(ignore_permissions=True)
    frappe.db.commit()
    
    return {
        'success': True,
        'message': _('QR Code regenerated successfully'),
        'qr_code_url': person.qr_code_image,
        'expires': person.token_expiry_date
    }


@frappe.whitelist()
def bulk_register_persons(data):
    """
    Bulk register persons from Excel/CSV data
    
    Args:
        data: JSON string containing list of person records
        Format: [
            {
                'full_name': 'John Doe',
                'email_id': 'john@example.com',
                'mobile_number': '+1234567890',
                'organization_unit': 'IT Department',
                'registry_type': 'Employee'
            },
            ...
        ]
    
    Returns:
        dict: Summary of created records and errors
    """
    if not frappe.has_permission('Person Registry', 'create'):
        frappe.throw(_('Insufficient permissions'))
    
    import json
    if isinstance(data, str):
        data = json.loads(data)
    
    created = []
    errors = []
    
    for idx, record in enumerate(data):
        try:
            # Check if already exists
            if record.get('email_id'):
                existing = frappe.db.exists('Person Registry', {'email_id': record['email_id']})
                if existing:
                    errors.append({
                        'row': idx + 1,
                        'error': f"Email {record['email_id']} already exists"
                    })
                    continue
            
            if record.get('mobile_number'):
                existing = frappe.db.exists('Person Registry', {'mobile_number': record['mobile_number']})
                if existing:
                    errors.append({
                        'row': idx + 1,
                        'error': f"Mobile {record['mobile_number']} already exists"
                    })
                    continue
            
            # Create person
            person = frappe.get_doc({
                'doctype': 'Person Registry',
                'full_name': record.get('full_name'),
                'email_id': record.get('email_id'),
                'mobile_number': record.get('mobile_number'),
                'organization_unit': record.get('organization_unit'),
                'registry_type': record.get('registry_type', 'Member'),
                'designation': record.get('designation'),
                'employee_reference': record.get('employee_reference'),
                'status': record.get('status', 'Active'),
                'allow_auto_attendance': 1,
                'enable_mac_detection': 1
            })
            person.insert(ignore_permissions=True)
            created.append({
                'registry_id': person.name,
                'name': person.full_name
            })
            
        except Exception as e:
            errors.append({
                'row': idx + 1,
                'error': str(e)
            })
    
    frappe.db.commit()
    
    return {
        'success': True,
        'created_count': len(created),
        'error_count': len(errors),
        'created': created,
        'errors': errors
    }


@frappe.whitelist()
def register_device(registry_id, mac_address, device_label, device_category='Mobile'):
    """
    Register a device (MAC address) for a person
    
    Args:
        registry_id: Person Registry ID
        mac_address: MAC address of device
        device_label: User-friendly device name
        device_category: Type of device (Mobile/Laptop/Tablet/etc.)
    
    Returns:
        dict: Device alias and registration status
    """
    # Verify person exists and user has permission
    person = frappe.get_doc('Person Registry', registry_id)
    
    # Check if user is registering own device or has permission
    if frappe.session.user != person.email_id and not frappe.has_permission('Person Registry', 'write'):
        frappe.throw(_('You can only register your own devices'))
    
    # Encrypt MAC address
    mac_manager = MACAddressSecurityManager()
    encrypted_data = mac_manager.encrypt_mac_address(mac_address)
    
    # Check if MAC already registered
    existing = frappe.db.exists('Device Registry Entry', {
        'mac_address_hash': encrypted_data['hash']
    })
    
    if existing:
        frappe.throw(_('This device is already registered'))
    
    # Add device to person's registry
    person.append('registered_devices', {
        'device_alias': encrypted_data['alias'],
        'device_label': device_label,
        'device_category': device_category,
        'mac_address_encrypted': encrypted_data['encrypted'],
        'mac_address_hash': encrypted_data['hash'],
        'encryption_method': 'AES-256-CBC',
        'is_active': 1,
        'registration_timestamp': now(),
        'registered_by': frappe.session.user
    })
    
    person.save(ignore_permissions=True)
    frappe.db.commit()
    
    return {
        'success': True,
        'message': _('Device registered successfully'),
        'device_alias': encrypted_data['alias'],
        'device_label': device_label,
        'registry_id': registry_id
    }


@frappe.whitelist(allow_guest=True)
def auto_detect_and_register_device(identifier, device_name):
    """
    Auto-detect device MAC and register (for self-service portal)
    
    Args:
        identifier: Email or mobile number
        device_name: User-friendly device name
    
    Returns:
        dict: Registration status and device alias
    """
    # Find person by identifier
    person = frappe.db.get_value('Person Registry', {
        'email_id': identifier
    }, 'name')
    
    if not person:
        person = frappe.db.get_value('Person Registry', {
            'mobile_number': identifier
        }, 'name')
    
    if not person:
        return {
            'success': False,
            'message': _('Person not found. Please contact administrator.')
        }
    
    # Get MAC address from request
    ip_address = frappe.local.request_ip if hasattr(frappe.local, 'request_ip') else None
    
    if not ip_address:
        return {
            'success': False,
            'message': _('Could not detect device. Please ensure you are connected to the organization network.')
        }
    
    # Get MAC from IP (requires network-level access)
    mac_address = get_mac_from_ip(ip_address)
    
    if not mac_address:
        return {
            'success': False,
            'message': _('Could not detect device MAC address. Please try manual registration.')
        }
    
    # Register device
    try:
        result = register_device(person, mac_address, device_name, 'Mobile')
        return result
    except Exception as e:
        frappe.log_error(str(e), 'Auto Device Registration Error')
        return {
            'success': False,
            'message': str(e)
        }


@frappe.whitelist()
def deactivate_device(device_alias):
    """
    Deactivate a registered device
    
    Args:
        device_alias: Device alias to deactivate
    
    Returns:
        dict: Success status
    """
    device = frappe.db.get_value('Device Registry Entry', 
        {'device_alias': device_alias}, 
        ['parent', 'name'], 
        as_dict=True
    )
    
    if not device:
        frappe.throw(_('Device not found'))
    
    # Check permissions
    person = frappe.get_doc('Person Registry', device.parent)
    if frappe.session.user != person.email_id and not frappe.has_permission('Person Registry', 'write'):
        frappe.throw(_('Insufficient permissions'))
    
    # Deactivate device
    frappe.db.set_value('Device Registry Entry', device.name, 'is_active', 0)
    frappe.db.commit()
    
    return {
        'success': True,
        'message': _('Device deactivated successfully')
    }


@frappe.whitelist()
def get_person_details(registry_id):
    """
    Get complete person details including devices
    
    Args:
        registry_id: Person Registry ID
    
    Returns:
        dict: Person details with devices
    """
    person = frappe.get_doc('Person Registry', registry_id)
    
    # Check permissions
    if frappe.session.user != person.email_id and not frappe.has_permission('Person Registry', 'read'):
        frappe.throw(_('Insufficient permissions'))
    
    devices = []
    for device in person.registered_devices:
        devices.append({
            'alias': device.device_alias,
            'label': device.device_label,
            'category': device.device_category,
            'is_active': device.is_active,
            'last_seen': device.last_seen,
            'registered_on': device.registration_timestamp
        })
    
    return {
        'registry_id': person.name,
        'full_name': person.full_name,
        'email_id': person.email_id,
        'mobile_number': person.mobile_number,
        'organization_unit': person.organization_unit,
        'designation': person.designation,
        'registry_type': person.registry_type,
        'status': person.status,
        'qr_code_url': person.qr_code_image,
        'qr_expires': person.token_expiry_date,
        'profile_picture': person.profile_picture,
        'devices': devices,
        'allow_auto_attendance': person.allow_auto_attendance,
        'enable_mac_detection': person.enable_mac_detection
    }


@frappe.whitelist()
def download_qr_code(registry_id):
    """
    Download QR code as image file
    
    Args:
        registry_id: Person Registry ID
    
    Returns:
        File download
    """
    person = frappe.get_doc('Person Registry', registry_id)
    
    # Check permissions
    if frappe.session.user != person.email_id and not frappe.has_permission('Person Registry', 'read'):
        frappe.throw(_('Insufficient permissions'))
    
    if not person.qr_code_image:
        frappe.throw(_('QR Code not generated'))
    
    # Get file
    file_doc = frappe.get_doc('File', {'file_url': person.qr_code_image})
    
    frappe.local.response.filename = f"QR_{person.full_name.replace(' ', '_')}.png"
    frappe.local.response.filecontent = file_doc.get_content()
    frappe.local.response.type = "download"


@frappe.whitelist()
def search_persons(query, filters=None):
    """
    Search persons by name, email, or phone
    
    Args:
        query: Search query string
        filters: Additional filters (JSON string)
    
    Returns:
        list: Matching persons
    """
    if not frappe.has_permission('Person Registry', 'read'):
        frappe.throw(_('Insufficient permissions'))
    
    conditions = []
    values = []
    
    if query:
        conditions.append("""
            (full_name LIKE %s OR email_id LIKE %s OR mobile_number LIKE %s OR registry_id LIKE %s)
        """)
        search_term = f"%{query}%"
        values.extend([search_term, search_term, search_term, search_term])
    
    # Apply additional filters
    if filters:
        import json
        if isinstance(filters, str):
            filters = json.loads(filters)
        
        for key, value in filters.items():
            conditions.append(f"{key} = %s")
            values.append(value)
    
    where_clause = " AND ".join(conditions) if conditions else "1=1"
    
    persons = frappe.db.sql(f"""
        SELECT 
            name as registry_id,
            full_name,
            email_id,
            mobile_number,
            organization_unit,
            designation,
            registry_type,
            status,
            profile_picture,
            qr_code_image
        FROM `tabPerson Registry`
        WHERE {where_clause}
        ORDER BY full_name
        LIMIT 50
    """, tuple(values), as_dict=True)
    
    return persons


# ==================== HELPER FUNCTIONS ====================

def get_mac_from_ip(ip_address):
    """
    Get MAC address from IP address using ARP table
    This requires server-level access or router API
    
    Args:
        ip_address: IP address
    
    Returns:
        str: MAC address or None
    """
    import subprocess
    import re
    
    try:
        # Try ARP command (Linux/Unix)
        arp_output = subprocess.check_output(['arp', '-n', ip_address], 
                                             stderr=subprocess.DEVNULL,
                                             timeout=5)
        arp_output = arp_output.decode('utf-8')
        
        # Extract MAC address using regex
        mac_pattern = r'([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})'
        match = re.search(mac_pattern, arp_output)
        
        if match:
            return match.group(0)
    
    except:
        pass
    
    # Alternative: Query router API
    try:
        mac = get_mac_from_router_api(ip_address)
        if mac:
            return mac
    except:
        pass
    
    return None


def get_mac_from_router_api(ip_address):
    """
    Get MAC address from router API
    Implementation varies by router type
    
    Args:
        ip_address: IP address to lookup
    
    Returns:
        str: MAC address or None
    """
    settings = frappe.get_single('Attendance System Settings')
    
    if not settings.router_integration_enabled:
        return None
    
    router_type = settings.router_type
    
    # Implement based on router type
    if router_type == 'MikroTik':
        return get_mac_from_mikrotik(ip_address, settings)
    elif router_type == 'UniFi':
        return get_mac_from_unifi(ip_address, settings)
    elif router_type == 'OpenWRT':
        return get_mac_from_openwrt(ip_address, settings)
    
    return None


def get_mac_from_mikrotik(ip_address, settings):
    """Get MAC from MikroTik router"""
    # Implementation for MikroTik API
    # Use librouteros or API requests
    return None


def get_mac_from_unifi(ip_address, settings):
    """Get MAC from UniFi controller"""
    import requests
    
    try:
        # UniFi Controller API
        base_url = f"https://{settings.router_ip_address}:8443"
        
        # Login
        session = requests.Session()
        login_response = session.post(
            f"{base_url}/api/login",
            json={
                'username': settings.router_api_username,
                'password': settings.get_password('router_api_password')
            },
            verify=False
        )
        
        if login_response.status_code == 200:
            # Get active clients
            clients_response = session.get(
                f"{base_url}/api/s/default/stat/sta",
                verify=False
            )
            
            if clients_response.status_code == 200:
                clients = clients_response.json().get('data', [])
                
                for client in clients:
                    if client.get('ip') == ip_address:
                        return client.get('mac')
    
    except Exception as e:
        frappe.log_error(str(e), 'UniFi MAC Lookup Error')
    
    return None


def get_mac_from_openwrt(ip_address, settings):
    """Get MAC from OpenWRT router"""
    import paramiko
    
    try:
        # SSH to router and read DHCP leases
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        ssh.connect(
            settings.router_ip_address,
            username=settings.router_api_username,
            password=settings.get_password('router_api_password')
        )
        
        stdin, stdout, stderr = ssh.exec_command('cat /tmp/dhcp.leases')
        leases = stdout.read().decode('utf-8')
        
        # Parse leases file
        for line in leases.split('\n'):
            if ip_address in line:
                parts = line.split()
                if len(parts) >= 2:
                    return parts[1]  # MAC address is second field
        
        ssh.close()
    
    except Exception as e:
        frappe.log_error(str(e), 'OpenWRT MAC Lookup Error')
    
    return None