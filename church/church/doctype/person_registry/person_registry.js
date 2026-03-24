// Copyright (c) 2025, kunle and contributors
// For license information, please see license.txt

// File: attendance_management/attendance_management/doctype/person_registry/person_registry.js

frappe.ui.form.on('Person Registry', {
    refresh: function(frm) {
        // Add custom buttons
        if (!frm.is_new()) {
            // Regenerate QR Code button
            frm.add_custom_button(__('Regenerate QR Code'), function() {
                regenerate_qr_code(frm);
            }, __('Actions'));

            // Download QR Code button
            frm.add_custom_button(__('Download QR Code'), function() {
                download_qr_code(frm);
            }, __('Actions'));

            // View Attendance History button
            frm.add_custom_button(__('View Attendance History'), function() {
                view_attendance_history(frm);
            }, __('Actions'));

            // Register New Device button
            frm.add_custom_button(__('Register Device'), function() {
                register_device_dialog(frm);
            }, __('Devices'));

            // Send QR Code Email button
            if (frm.doc.email_id) {
                frm.add_custom_button(__('Send QR Code Email'), function() {
                    send_qr_email(frm);
                }, __('Actions'));
            }

            // Show QR Code in modal
            if (frm.doc.qr_code_image) {
                frm.add_custom_button(__('Show QR Code'), function() {
                    show_qr_code_modal(frm);
                }, __('Actions'));
            }
        }

        // Color code status
        if (frm.doc.status === 'Active') {
            frm.dashboard.set_headline_alert('Status: Active', 'green');
        } else if (frm.doc.status === 'Inactive') {
            frm.dashboard.set_headline_alert('Status: Inactive', 'red');
        } else if (frm.doc.status === 'Pending Approval') {
            frm.dashboard.set_headline_alert('Status: Pending Approval', 'orange');
        }

        // Show token expiry warning
        if (frm.doc.token_expiry_date) {
            const today = frappe.datetime.get_today();
            const expiry = frm.doc.token_expiry_date;
            
            if (expiry < today) {
                frm.dashboard.set_headline_alert('QR Code Expired! Please regenerate.', 'red');
            } else if (frappe.datetime.get_day_diff(expiry, today) < 7) {
                frm.dashboard.set_headline_alert('QR Code expires soon!', 'orange');
            }
        }

        // Refresh device list display
        refresh_device_list(frm);
    },

    onload: function(frm) {
        // Set filters for organization unit
        frm.set_query('organization_unit', function() {
            return {
                filters: {
                    'is_active': 1
                }
            };
        });

        // Set filters for membership category
        frm.set_query('membership_category', function() {
            return {
                filters: {
                    'is_active': 1
                }
            };
        });
    },

    status: function(frm) {
        // Auto-generate QR code when status changes to Active
        if (frm.doc.status === 'Active' && !frm.doc.qr_code_image) {
            frappe.msgprint(__('QR Code will be generated automatically when you save.'));
        }
    },

    email_id: function(frm) {
        // Validate email format
        if (frm.doc.email_id) {
            const email_regex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
            if (!email_regex.test(frm.doc.email_id)) {
                frappe.msgprint(__('Please enter a valid email address'));
                frm.set_value('email_id', '');
            }
        }
    }
});

// Child table: Device Registry Entry
frappe.ui.form.on('Device Registry Entry', {
    is_active: function(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        
        if (row.is_active === 0) {
            frappe.msgprint(__('Device {0} has been deactivated', [row.device_label]));
        }
    }
});

// ==================== CUSTOM FUNCTIONS ====================

function regenerate_qr_code(frm) {
    frappe.confirm(
        __('Are you sure you want to regenerate the QR code? The old QR code will no longer work.'),
        function() {
            frappe.call({
                method: 'church.church.doctype.person_registry.person_registry.regenerate_qr_code',
                args: {
                    registry_id: frm.doc.name
                },
                freeze: true,
                freeze_message: __('Regenerating QR Code...'),
                callback: function(r) {
                    if (r.message && r.message.success) {
                        frappe.show_alert({
                            message: __('QR Code regenerated successfully'),
                            indicator: 'green'
                        }, 5);
                        frm.reload_doc();
                    }
                }
            });
        }
    );
}

function download_qr_code(frm) {
    if (!frm.doc.qr_code_image) {
        frappe.msgprint(__('QR Code not generated yet'));
        return;
    }

    window.open(frm.doc.qr_code_image, '_blank');
    
    frappe.show_alert({
        message: __('QR Code opened in new tab'),
        indicator: 'blue'
    }, 3);
}

function view_attendance_history(frm) {
    frappe.route_options = {
        'person_registry': frm.doc.name
    };
    frappe.set_route('List', 'Daily Presence Record');
}

function register_device_dialog(frm) {
    const d = new frappe.ui.Dialog({
        title: __('Register New Device'),
        fields: [
            {
                label: __('Device Name'),
                fieldname: 'device_label',
                fieldtype: 'Data',
                reqd: 1,
                description: __('E.g., "John\'s iPhone", "Work Laptop"')
            },
            {
                label: __('MAC Address'),
                fieldname: 'mac_address',
                fieldtype: 'Data',
                reqd: 1,
                description: __('Format: AA:BB:CC:DD:EE:FF or AA-BB-CC-DD-EE-FF')
            },
            {
                label: __('Device Type'),
                fieldname: 'device_category',
                fieldtype: 'Select',
                options: 'Mobile\nTablet\nLaptop\nDesktop\nWearable\nOther',
                default: 'Mobile',
                reqd: 1
            }
        ],
        primary_action_label: __('Register'),
        primary_action: function(values) {
            frappe.call({
                method: 'church.church.doctype.person_registry.person_registry.register_device',
                args: {
                    registry_id: frm.doc.name,
                    mac_address: values.mac_address,
                    device_label: values.device_label,
                    device_category: values.device_category
                },
                freeze: true,
                freeze_message: __('Registering device...'),
                callback: function(r) {
                    if (r.message && r.message.success) {
                        frappe.show_alert({
                            message: __('Device registered as {0}', [r.message.device_alias]),
                            indicator: 'green'
                        }, 5);
                        d.hide();
                        frm.reload_doc();
                    }
                }
            });
        }
    });

    d.show();
}

function send_qr_email(frm) {
    frappe.confirm(
        __('Send QR code to {0}?', [frm.doc.email_id]),
        function() {
            frappe.call({
                method: 'frappe.core.doctype.communication.email.make',
                args: {
                    recipients: frm.doc.email_id,
                    subject: __('Your Attendance QR Code'),
                    content: `
                        <p>Dear ${frm.doc.full_name},</p>
                        <p>Please find your attendance QR code attached.</p>
                        <p>Use this to mark your attendance by scanning at our checkpoints.</p>
                        <p>QR Code expires on: ${frappe.datetime.str_to_user(frm.doc.token_expiry_date)}</p>
                        <br>
                        <p>Best regards,<br>Attendance Management Team</p>
                    `,
                    doctype: 'Person Registry',
                    name: frm.doc.name,
                    send_email: 1
                },
                freeze: true,
                freeze_message: __('Sending email...'),
                callback: function(r) {
                    frappe.show_alert({
                        message: __('Email sent successfully'),
                        indicator: 'green'
                    }, 5);
                }
            });
        }
    );
}

function show_qr_code_modal(frm) {
    const d = new frappe.ui.Dialog({
        title: __('QR Code - {0}', [frm.doc.full_name]),
        size: 'small'
    });

    const html = `
        <div style="text-align: center; padding: 20px;">
            <img src="${frm.doc.qr_code_image}" style="max-width: 100%; border: 2px solid #ddd; border-radius: 8px;">
            <p style="margin-top: 15px; color: #666;">
                <strong>Registry ID:</strong> ${frm.doc.name}<br>
                <strong>Expires:</strong> ${frappe.datetime.str_to_user(frm.doc.token_expiry_date)}
            </p>
            <button class="btn btn-primary btn-sm" onclick="window.open('${frm.doc.qr_code_image}', '_blank')" style="margin-top: 10px;">
                Download QR Code
            </button>
        </div>
    `;

    d.$body.html(html);
    d.show();
}

function refresh_device_list(frm) {
    if (frm.doc.registered_devices && frm.doc.registered_devices.length > 0) {
        const active_devices = frm.doc.registered_devices.filter(d => d.is_active === 1).length;
        const total_devices = frm.doc.registered_devices.length;
        
        frm.dashboard.add_indicator(
            __('Devices: {0} active / {1} total', [active_devices, total_devices]),
            active_devices > 0 ? 'blue' : 'grey'
        );
    }
}

// ==================== BULK OPERATIONS ====================

frappe.listview_settings['Person Registry'] = {
    onload: function(listview) {
        // Add bulk regenerate QR codes button
        listview.page.add_inner_button(__('Regenerate QR Codes'), function() {
            const selected = listview.get_checked_items();
            
            if (selected.length === 0) {
                frappe.msgprint(__('Please select persons'));
                return;
            }

            frappe.confirm(
                __('Regenerate QR codes for {0} selected persons?', [selected.length]),
                function() {
                    regenerate_bulk_qr_codes(selected);
                }
            );
        }, __('Actions'));

        // Add bulk export button
        listview.page.add_inner_button(__('Export Selected'), function() {
            const selected = listview.get_checked_items();
            
            if (selected.length === 0) {
                frappe.msgprint(__('Please select persons'));
                return;
            }

            export_persons(selected);
        }, __('Actions'));
    },

    // Custom indicators
    get_indicator: function(doc) {
        if (doc.status === 'Active') {
            return [__('Active'), 'green', 'status,=,Active'];
        } else if (doc.status === 'Inactive') {
            return [__('Inactive'), 'red', 'status,=,Inactive'];
        } else if (doc.status === 'Pending Approval') {
            return [__('Pending'), 'orange', 'status,=,Pending Approval'];
        } else if (doc.status === 'Suspended') {
            return [__('Suspended'), 'darkgrey', 'status,=,Suspended'];
        }
    }
};

function regenerate_bulk_qr_codes(selected) {
    const registry_ids = selected.map(s => s.name);
    
    frappe.call({
        method: 'church.church.doctype.person_registry.person_registry.bulk_regenerate_qr_codes',
        args: {
            registry_ids: registry_ids
        },
        freeze: true,
        freeze_message: __('Regenerating QR codes...'),
        callback: function(r) {
            if (r.message) {
                frappe.msgprint({
                    title: __('QR Code Regeneration Complete'),
                    indicator: 'green',
                    message: __('Successfully regenerated {0} QR codes', [r.message.success_count])
                });
                cur_list.refresh();
            }
        }
    });
}

function export_persons(selected) {
    const registry_ids = selected.map(s => s.name).join(',');
    const url = `/api/method/church.church.doctype.person_registry.person_registry.export_persons?registry_ids=${registry_ids}`;
    
    window.open(url, '_blank');
    
    frappe.show_alert({
        message: __('Exporting {0} persons...', [selected.length]),
        indicator: 'blue'
    }, 3);
}