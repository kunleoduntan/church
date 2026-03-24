# File: attendance_management/attendance_management/utils/mac_encryption_utils.py

"""
MAC Address Security Manager
Provides comprehensive encryption, hashing, and aliasing for MAC addresses
Ensures privacy and security in attendance tracking systems
"""

import frappe
from frappe import _
import hashlib
import hmac
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend
import secrets
import string
import re


class MACAddressSecurityManager:
    """
    Comprehensive MAC address security manager
    """

    def __init__(self):
        self.encryption_key = self._get_or_create_encryption_key()
        self.cipher_suite = Fernet(self.encryption_key)

    def _get_or_create_encryption_key(self):
        try:
            settings = frappe.get_single('Attendance System Settings')
            encryption_key = settings.mac_encryption_key

            if not encryption_key:
                password = frappe.conf.get('encryption_key', frappe.generate_hash(length=32))
                salt = secrets.token_bytes(32)

                kdf = PBKDF2HMAC(
                    algorithm=hashes.SHA256(),
                    length=32,
                    salt=salt,
                    iterations=100000,
                    backend=default_backend()
                )
                key = base64.urlsafe_b64encode(kdf.derive(password.encode()))

                settings.mac_encryption_key = key.decode()
                settings.mac_encryption_salt = base64.b64encode(salt).decode()
                settings.save(ignore_permissions=True)
                frappe.db.commit()

                frappe.log_error("New MAC encryption key generated and stored",
                                 "MAC Encryption Key Generation")

                encryption_key = key.decode()

            return encryption_key.encode()

        except Exception as e:
            frappe.log_error(f"Encryption key error: {str(e)}", "MAC Encryption")
            fallback_key = Fernet.generate_key()
            return fallback_key

    def encrypt_mac_address(self, mac_address):
        normalized_mac = self._normalize_mac_address(mac_address)

        if not normalized_mac:
            frappe.throw(_("Invalid MAC address format. Expected: AA:BB:CC:DD:EE:FF"))

        encrypted_bytes = self.cipher_suite.encrypt(normalized_mac.encode())
        encrypted_b64 = base64.b64encode(encrypted_bytes).decode()

        mac_hash = self._generate_mac_hash(normalized_mac)
        alias = self._generate_device_alias()

        return {
            'encrypted': encrypted_b64,
            'hash': mac_hash,
            'alias': alias,
            'normalized': normalized_mac
        }

    def decrypt_mac_address(self, encrypted_mac):
        try:
            encrypted_bytes = base64.b64decode(encrypted_mac)
            decrypted = self.cipher_suite.decrypt(encrypted_bytes)
            return decrypted.decode()
        except Exception as e:
            frappe.log_error(f"Decryption failed: {str(e)}", "MAC Decryption")
            return None

    def _normalize_mac_address(self, mac_address):
        if not mac_address:
            return None

        clean_mac = re.sub(r'[^A-Fa-f0-9]', '', str(mac_address).upper())

        if len(clean_mac) != 12:
            return None

        if not all(c in '0123456789ABCDEF' for c in clean_mac):
            return None

        return ':'.join([clean_mac[i:i+2] for i in range(0, 12, 2)])

    def _generate_mac_hash(self, mac_address):
        secret_key = frappe.conf.get('encryption_key', 'default-hmac-key-change-this')

        return hmac.new(
            secret_key.encode(),
            mac_address.encode(),
            hashlib.sha256
        ).hexdigest()

    def _generate_device_alias(self):
        max_attempts = 100

        for _ in range(max_attempts):
            letters = ''.join(secrets.choice(string.ascii_uppercase) for _ in range(3))
            numbers = ''.join(secrets.choice(string.digits) for _ in range(3))
            alias = f"DEV-{letters}{numbers}"

            if not frappe.db.exists('Device Registry Entry', {'device_alias': alias}):
                return alias

        fallback = f"DEV-{secrets.token_hex(3).upper()}"
        return fallback

    def verify_mac_address(self, mac_address, stored_hash):
        normalized = self._normalize_mac_address(mac_address)
        if not normalized:
            return False

        computed = self._generate_mac_hash(normalized)
        return hmac.compare_digest(computed, stored_hash)

    def find_person_by_mac(self, mac_address):
        normalized = self._normalize_mac_address(mac_address)
        if not normalized:
            return None

        mac_hash = self._generate_mac_hash(normalized)

        result = frappe.db.sql("""
            SELECT 
                dre.parent as person_id,
                dre.device_alias,
                dre.device_label,
                dre.device_category,
                dre.last_seen,
                pr.full_name,
                pr.email_id,
                pr.mobile_number,
                pr.organization_unit,
                pr.status,
                pr.enable_mac_detection,
                pr.allow_auto_attendance
            FROM `tabDevice Registry Entry` dre
            INNER JOIN `tabPerson Registry` pr ON dre.parent = pr.name
            WHERE dre.mac_address_hash = %s
              AND dre.is_active = 1
              AND pr.status = 'Active'
            LIMIT 1
        """, (mac_hash,), as_dict=True)

        return result[0] if result else None

    def update_device_last_seen(self, device_alias, ip_address=None):
        try:
            frappe.db.sql("""
                UPDATE `tabDevice Registry Entry`
                SET 
                    last_seen = NOW(),
                    ip_address_last_known = COALESCE(%s, ip_address_last_known)
                WHERE device_alias = %s
            """, (ip_address, device_alias))
            frappe.db.commit()
        except Exception as e:
            frappe.log_error(f"Device update error: {str(e)}", "Device Update")

    def get_all_devices_for_person(self, registry_id):
        return frappe.db.sql("""
            SELECT 
                device_alias,
                device_label,
                device_category,
                is_active,
                last_seen,
                ip_address_last_known,
                registration_timestamp
            FROM `tabDevice Registry Entry`
            WHERE parent = %s
            ORDER BY registration_timestamp DESC
        """, (registry_id,), as_dict=True)

    def deactivate_device(self, device_alias):
        try:
            frappe.db.set_value(
                'Device Registry Entry',
                {'device_alias': device_alias},
                'is_active',
                0
            )
            frappe.db.commit()
            return True
        except Exception:
            return False

    def search_devices(self, query, limit=50):
        search_term = f"%{query}%"
        return frappe.db.sql("""
            SELECT 
                dre.device_alias,
                dre.device_label,
                dre.device_category,
                dre.is_active,
                dre.last_seen,
                dre.parent as person_id,
                pr.full_name as person_name,
                pr.organization_unit
            FROM `tabDevice Registry Entry` dre
            INNER JOIN `tabPerson Registry` pr ON dre.parent = pr.name
            WHERE (dre.device_alias LIKE %s OR dre.device_label LIKE %s)
            ORDER BY dre.last_seen DESC
            LIMIT %s
        """, (search_term, search_term, limit), as_dict=True)

    def get_statistics(self):
        stats = frappe.db.sql("""
            SELECT 
                COUNT(*) as total_devices,
                SUM(CASE WHEN is_active = 1 THEN 1 ELSE 0 END) as active_devices,
                SUM(CASE WHEN last_seen >= DATE_SUB(NOW(), INTERVAL 24 HOUR) THEN 1 ELSE 0 END) as seen_today,
                COUNT(DISTINCT parent) as persons_with_devices
            FROM `tabDevice Registry Entry`
        """, as_dict=True)

        return stats[0] if stats else {}


def encrypt_and_register_mac(person_id, mac_address, device_label, device_category='Mobile'):
    manager = MACAddressSecurityManager()
    encrypted = manager.encrypt_mac_address(mac_address)

    existing = frappe.db.get_value('Device Registry Entry',
                                   {'mac_address_hash': encrypted['hash']},
                                   'device_alias')

    if existing:
        frappe.throw(_("This device is already registered with alias: {0}").format(existing))

    if not frappe.db.exists('Person Registry', person_id):
        frappe.throw(_("Person Registry {0} not found").format(person_id))

    person = frappe.get_doc('Person Registry', person_id)

    person.append('registered_devices', {
        'device_alias': encrypted['alias'],
        'device_label': device_label,
        'device_category': device_category,
        'mac_address_encrypted': encrypted['encrypted'],
        'mac_address_hash': encrypted['hash'],
        'encryption_method': 'AES-256-CBC',
        'is_active': 1,
        'registration_timestamp': frappe.utils.now(),
        'registered_by': frappe.session.user
    })

    person.save(ignore_permissions=True)
    frappe.db.commit()

    return encrypted['alias']


def find_person_by_mac(mac):
    return MACAddressSecurityManager().find_person_by_mac(mac)


def decrypt_mac_for_admin(enc):
    if not frappe.has_permission('Person Registry', 'write'):
        frappe.throw(_("Insufficient permissions to decrypt MAC addresses"))

    manager = MACAddressSecurityManager()
    decrypted = manager.decrypt_mac_address(enc)

    if not decrypted:
        frappe.throw(_("Failed to decrypt MAC address"))

    frappe.log_error(f"MAC address decrypted by {frappe.session.user}",
                     "MAC Address Decryption Audit")

    return decrypted


def validate_mac_address(mac):
    return MACAddressSecurityManager()._normalize_mac_address(mac) is not None


def get_device_info(device_alias):
    device = frappe.db.sql("""
        SELECT 
            dre.*,
            pr.full_name as person_name,
            pr.email_id
        FROM `tabDevice Registry Entry` dre
        INNER JOIN `tabPerson Registry` pr ON dre.parent = pr.name
        WHERE dre.device_alias = %s
    """, (device_alias,), as_dict=True)

    return device[0] if device else None


@frappe.whitelist()
def register_device_api(person_id, mac_address, device_label, device_category='Mobile'):
    return encrypt_and_register_mac(person_id, mac_address, device_label, device_category)


@frappe.whitelist()
def search_devices_api(query):
    if not frappe.has_permission('Person Registry', 'read'):
        frappe.throw(_('Insufficient permissions'))
    return MACAddressSecurityManager().search_devices(query)


@frappe.whitelist()
def get_device_statistics():
    if not frappe.has_permission('Attendance System Settings', 'read'):
        frappe.throw(_('Insufficient permissions'))
    return MACAddressSecurityManager().get_statistics()
