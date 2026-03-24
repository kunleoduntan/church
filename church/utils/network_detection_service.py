# File: church/attendance_management/utils/network_detection_service.py

import frappe
from frappe import _
from frappe.utils import now, today, cint
import requests
import json

# FIXED IMPORTS - Use correct module paths
try:
    from church.church.utils.mac_encryption_utils import MACAddressSecurityManager
except ImportError:
    # Fallback if path is different
    from church.utils.mac_encryption_utils import MACAddressSecurityManager

try:
    from church.church.doctype.presence_log.presence_log import mark_attendance_mac
except ImportError:
    # Fallback if path is different
    from church.doctype.presence_log.presence_log import mark_attendance_mac


class NetworkDetectionService:
    """
    Service for detecting devices on network and marking attendance
    Supports multiple router types and network configurations
    """
    
    def __init__(self):
        self.settings = frappe.get_single('Attendance System Settings')
        self.mac_manager = MACAddressSecurityManager()
        self.detected_devices = []
        self.processed_count = 0
        self.error_count = 0
        self.errors = []
    
    def scan_network(self):
        """
        Main method to scan network and process attendance
        Returns summary of scan results
        """
        if not self.settings.enable_mac_attendance:
            return {
                'success': False,
                'message': 'MAC attendance is disabled in settings'
            }
        
        if not self.settings.router_integration_enabled:
            return {
                'success': False,
                'message': 'Router integration is disabled in settings'
            }
        
        frappe.logger().info("Starting network scan for attendance detection")
        
        # Get connected devices based on router type
        router_type = self.settings.router_type
        
        if router_type == 'MikroTik':
            self.detected_devices = self.scan_mikrotik()
        elif router_type == 'UniFi':
            self.detected_devices = self.scan_unifi()
        elif router_type == 'Cisco':
            self.detected_devices = self.scan_cisco()
        elif router_type == 'TP-Link':
            self.detected_devices = self.scan_tplink()
        elif router_type == 'OpenWRT':
            self.detected_devices = self.scan_openwrt()
        elif router_type == 'DD-WRT':
            self.detected_devices = self.scan_ddwrt()
        else:
            return {
                'success': False,
                'message': f'Unsupported router type: {router_type}'
            }
        
        frappe.logger().info(f"Detected {len(self.detected_devices)} devices on network")
        
        # Process each detected device
        for device in self.detected_devices:
            self.process_device(device)
        
        summary = {
            'success': True,
            'scan_time': now(),
            'total_devices': len(self.detected_devices),
            'processed_count': self.processed_count,
            'error_count': self.error_count,
            'errors': self.errors[:10]  # Limit errors in response
        }
        
        # Log summary
        frappe.log_error(
            json.dumps(summary, indent=2, default=str),
            'Network Scan Summary'
        )
        
        return summary
    
    def process_device(self, device):
        """
        Process a detected device and mark attendance if registered
        
        Args:
            device: dict with keys 'mac_address', 'ip_address', 'hostname', etc.
        """
        try:
            mac_address = device.get('mac_address')
            
            if not mac_address:
                return
            
            # Mark attendance via MAC
            result = mark_attendance_mac(
                mac_address=mac_address,
                checkpoint_location='Network Auto-Detection',
                ip_address=device.get('ip_address')
            )
            
            if result.get('success'):
                self.processed_count += 1
                frappe.logger().info(
                    f"Attendance marked for {result.get('person_data', {}).get('name', 'Unknown')}"
                )
            elif result.get('error_code') == 'ALREADY_MARKED':
                # Not an error, just already processed
                pass
            elif result.get('error_code') == 'DEVICE_NOT_REGISTERED':
                # Device not in system, skip silently
                pass
            else:
                # Log other errors
                self.error_count += 1
                self.errors.append({
                    'mac': mac_address[:8] + '...',
                    'error': result.get('message')
                })
        
        except Exception as e:
            self.error_count += 1
            self.errors.append({
                'device': device.get('mac_address', 'Unknown')[:8] + '...',
                'error': str(e)
            })
            frappe.log_error(f"Device processing error: {str(e)}", "Device Processing Error")
    
    # ==================== ROUTER-SPECIFIC METHODS ====================
    
    def scan_mikrotik(self):
        """
        Scan MikroTik router for connected devices
        Uses RouterOS API
        """
        devices = []
        
        try:
            # Import RouterOS library
            try:
                import librouteros
            except ImportError:
                frappe.throw(_("librouteros library not installed. Install with: pip install librouteros"))
            
            # Connect to router
            api = librouteros.connect(
                host=self.settings.router_ip_address,
                username=self.settings.router_api_username,
                password=self.settings.get_password('router_api_password')
            )
            
            # Get DHCP leases
            dhcp_leases = api.path('/ip/dhcp-server/lease')
            
            for lease in dhcp_leases:
                if lease.get('active-mac-address'):
                    devices.append({
                        'mac_address': lease.get('active-mac-address'),
                        'ip_address': lease.get('active-address'),
                        'hostname': lease.get('host-name'),
                        'status': lease.get('status')
                    })
            
            # Also get ARP entries for devices not in DHCP
            arp_entries = api.path('/ip/arp')
            
            for arp in arp_entries:
                mac = arp.get('mac-address')
                if mac and not any(d['mac_address'] == mac for d in devices):
                    devices.append({
                        'mac_address': mac,
                        'ip_address': arp.get('address'),
                        'hostname': None,
                        'status': 'arp'
                    })
            
            api.close()
        
        except Exception as e:
            frappe.log_error(f"MikroTik scan error: {str(e)}", "MikroTik Scan Error")
        
        return devices
    
    def scan_unifi(self):
        """
        Scan UniFi controller for connected devices
        Uses UniFi Controller API
        """
        devices = []
        
        try:
            base_url = f"https://{self.settings.router_ip_address}:8443"
            
            # Create session
            session = requests.Session()
            session.verify = False  # Disable SSL verification for self-signed certs
            
            # Login
            login_data = {
                'username': self.settings.router_api_username,
                'password': self.settings.get_password('router_api_password')
            }
            
            login_response = session.post(
                f"{base_url}/api/login",
                json=login_data,
                timeout=10
            )
            
            if login_response.status_code != 200:
                frappe.throw(_("Failed to login to UniFi Controller"))
            
            # Get active clients
            clients_response = session.get(
                f"{base_url}/api/s/default/stat/sta",
                timeout=10
            )
            
            if clients_response.status_code == 200:
                clients_data = clients_response.json()
                clients = clients_data.get('data', [])
                
                for client in clients:
                    devices.append({
                        'mac_address': client.get('mac'),
                        'ip_address': client.get('ip'),
                        'hostname': client.get('hostname'),
                        'status': 'connected'
                    })
            
            # Logout
            session.post(f"{base_url}/api/logout")
        
        except Exception as e:
            frappe.log_error(f"UniFi scan error: {str(e)}", "UniFi Scan Error")
        
        return devices
    
    def scan_cisco(self):
        """
        Scan Cisco router/switch for connected devices
        Uses SSH and CLI commands
        """
        devices = []
        
        try:
            import paramiko
            
            # SSH connection
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            ssh.connect(
                self.settings.router_ip_address,
                username=self.settings.router_api_username,
                password=self.settings.get_password('router_api_password'),
                timeout=10
            )
            
            # Execute command to get ARP table
            stdin, stdout, stderr = ssh.exec_command('show ip arp')
            arp_output = stdout.read().decode('utf-8')
            
            # Parse ARP output
            for line in arp_output.split('\n'):
                parts = line.split()
                if len(parts) >= 4 and ':' in parts[3]:
                    devices.append({
                        'mac_address': parts[3],
                        'ip_address': parts[1],
                        'hostname': None,
                        'status': 'arp'
                    })
            
            ssh.close()
        
        except Exception as e:
            frappe.log_error(f"Cisco scan error: {str(e)}", "Cisco Scan Error")
        
        return devices
    
    def scan_tplink(self):
        """
        Scan TP-Link router for connected devices
        Uses TP-Link Web API
        """
        devices = []
        
        try:
            # TP-Link routers typically use web scraping or proprietary API
            # Implementation varies by model
            base_url = f"http://{self.settings.router_ip_address}"
            
            # This is a generic implementation - adjust for specific models
            session = requests.Session()
            
            # Login (varies by model)
            import base64
            auth_string = f"{self.settings.router_api_username}:{self.settings.get_password('router_api_password')}"
            auth_bytes = auth_string.encode('ascii')
            auth_b64 = base64.b64encode(auth_bytes).decode('ascii')
            
            headers = {
                'Authorization': f'Basic {auth_b64}'
            }
            
            # Try to get DHCP client list
            response = session.get(
                f"{base_url}/userRpm/AssignedIpAddrListRpm.htm",
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                # Parse HTML response (basic example)
                import re
                mac_pattern = r'([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})'
                ip_pattern = r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b'
                
                macs = re.findall(mac_pattern, response.text)
                ips = re.findall(ip_pattern, response.text)
                
                for i, mac in enumerate(macs):
                    devices.append({
                        'mac_address': mac[0] + mac[1],
                        'ip_address': ips[i] if i < len(ips) else None,
                        'hostname': None,
                        'status': 'connected'
                    })
        
        except Exception as e:
            frappe.log_error(f"TP-Link scan error: {str(e)}", "TP-Link Scan Error")
        
        return devices
    
    def scan_openwrt(self):
        """
        Scan OpenWRT router for connected devices
        Uses SSH to read DHCP leases file
        """
        devices = []
        
        try:
            import paramiko
            
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            ssh.connect(
                self.settings.router_ip_address,
                username=self.settings.router_api_username,
                password=self.settings.get_password('router_api_password'),
                timeout=10
            )
            
            # Read DHCP leases file
            stdin, stdout, stderr = ssh.exec_command('cat /tmp/dhcp.leases')
            leases = stdout.read().decode('utf-8')
            
            # Parse leases file
            # Format: timestamp MAC IP hostname client-id
            for line in leases.strip().split('\n'):
                if not line:
                    continue
                
                parts = line.split()
                if len(parts) >= 3:
                    devices.append({
                        'mac_address': parts[1],
                        'ip_address': parts[2],
                        'hostname': parts[3] if len(parts) > 3 else None,
                        'status': 'dhcp'
                    })
            
            # Also get wireless clients
            stdin, stdout, stderr = ssh.exec_command('iw dev wlan0 station dump')
            station_dump = stdout.read().decode('utf-8')
            
            import re
            mac_pattern = r'Station ([0-9a-f:]+)'
            macs = re.findall(mac_pattern, station_dump)
            
            for mac in macs:
                if not any(d['mac_address'] == mac for d in devices):
                    devices.append({
                        'mac_address': mac,
                        'ip_address': None,
                        'hostname': None,
                        'status': 'wireless'
                    })
            
            ssh.close()
        
        except Exception as e:
            frappe.log_error(f"OpenWRT scan error: {str(e)}", "OpenWRT Scan Error")
        
        return devices
    
    def scan_ddwrt(self):
        """
        Scan DD-WRT router for connected devices
        Similar to OpenWRT but different file locations
        """
        devices = []
        
        try:
            import paramiko
            
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            ssh.connect(
                self.settings.router_ip_address,
                username=self.settings.router_api_username,
                password=self.settings.get_password('router_api_password'),
                timeout=10
            )
            
            # Get active wireless clients
            stdin, stdout, stderr = ssh.exec_command('wl assoclist')
            assoc_output = stdout.read().decode('utf-8')
            
            import re
            mac_pattern = r'([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}'
            macs = re.findall(mac_pattern, assoc_output)
            
            # Get ARP table for IP addresses
            stdin, stdout, stderr = ssh.exec_command('cat /proc/net/arp')
            arp_output = stdout.read().decode('utf-8')
            
            arp_dict = {}
            for line in arp_output.split('\n')[1:]:  # Skip header
                parts = line.split()
                if len(parts) >= 4:
                    arp_dict[parts[3]] = parts[0]  # MAC -> IP mapping
            
            for mac in macs:
                devices.append({
                    'mac_address': mac,
                    'ip_address': arp_dict.get(mac),
                    'hostname': None,
                    'status': 'wireless'
                })
            
            ssh.close()
        
        except Exception as e:
            frappe.log_error(f"DD-WRT scan error: {str(e)}", "DD-WRT Scan Error")
        
        return devices


# ==================== WHITELISTED API METHODS ====================

@frappe.whitelist()
def trigger_network_scan():
    """
    Manually trigger network scan
    Requires admin permissions
    
    Returns:
        dict: Scan summary
    """
    if not frappe.has_permission('Attendance System Settings', 'write'):
        frappe.throw(_('Insufficient permissions to trigger network scan'))
    
    service = NetworkDetectionService()
    result = service.scan_network()
    
    return result


@frappe.whitelist()
def get_scan_history(limit=20):
    """
    Get history of network scans from logs
    
    Args:
        limit: Number of recent scans to retrieve
    
    Returns:
        list: Scan history
    """
    if not frappe.has_permission('Attendance System Settings', 'read'):
        frappe.throw(_('Insufficient permissions'))
    
    # Get error logs for network scans
    logs = frappe.get_all('Error Log',
        filters={
            'error': ['like', '%Network Scan Summary%']
        },
        fields=['creation', 'error'],
        order_by='creation desc',
        limit=cint(limit)
    )
    
    history = []
    for log in logs:
        try:
            # Parse JSON from log
            log_lines = log.error.split('\n')
            for line in log_lines:
                if line.strip().startswith('{'):
                    scan_data = json.loads(line)
                    scan_data['timestamp'] = log.creation
                    history.append(scan_data)
                    break
        except:
            pass
    
    return {
        'success': True,
        'scan_count': len(history),
        'scans': history
    }


@frappe.whitelist()
def test_router_connection():
    """
    Test router connection without running full scan
    
    Returns:
        dict: Connection test results
    """
    if not frappe.has_permission('Attendance System Settings', 'write'):
        frappe.throw(_('Insufficient permissions'))
    
    settings = frappe.get_single('Attendance System Settings')
    
    if not settings.router_integration_enabled:
        return {
            'success': False,
            'message': 'Router integration is disabled'
        }
    
    router_type = settings.router_type
    
    try:
        if router_type == 'UniFi':
            # Test UniFi connection
            base_url = f"https://{settings.router_ip_address}:8443"
            response = requests.get(f"{base_url}/api/self", timeout=5, verify=False)
            
            return {
                'success': response.status_code == 200,
                'message': 'Connection successful' if response.status_code == 200 else 'Connection failed',
                'router_type': router_type
            }
        
        elif router_type in ['OpenWRT', 'DD-WRT', 'Cisco']:
            # Test SSH connection
            import paramiko
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            ssh.connect(
                settings.router_ip_address,
                username=settings.router_api_username,
                password=settings.get_password('router_api_password'),
                timeout=5
            )
            
            ssh.close()
            
            return {
                'success': True,
                'message': 'SSH connection successful',
                'router_type': router_type
            }
        
        else:
            return {
                'success': False,
                'message': f'Testing not implemented for {router_type}'
            }
    
    except Exception as e:
        return {
            'success': False,
            'message': str(e),
            'router_type': router_type
        }


# ==================== SCHEDULED JOB (MODULE-LEVEL FUNCTION) ====================

def scheduled_network_scan():
    """
    Scheduled job to automatically scan network
    This is a MODULE-LEVEL function that can be called by Frappe scheduler
    
    Usage in hooks.py:
        scheduler_events = {
            "cron": {
                "*/10 * * * *": [  # Every 10 minutes
                    "church.church.utils.network_detection_service.scheduled_network_scan"
                ]
            }
        }
    
    Returns:
        dict: Scan summary (optional, for logging)
    """
    try:
        settings = frappe.get_single('Attendance System Settings')
        
        if not settings.enable_mac_attendance or not settings.router_integration_enabled:
            frappe.logger().info("Network scan skipped: MAC attendance or router integration disabled")
            return {
                'success': False,
                'message': 'Scan skipped - disabled in settings'
            }
        
        frappe.logger().info("Starting scheduled network scan...")
        
        service = NetworkDetectionService()
        result = service.scan_network()
        
        frappe.logger().info(
            f"Scheduled network scan completed: {result.get('processed_count', 0)} attendance records created"
        )
        
        return result
    
    except Exception as e:
        error_msg = f"Scheduled scan error: {str(e)}"
        frappe.log_error(error_msg, "Scheduled Network Scan Error")
        frappe.logger().error(error_msg)
        
        return {
            'success': False,
            'error': str(e)
        }