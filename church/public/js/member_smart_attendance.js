// ============================================================================
// MEMBER FORM - SMART ATTENDANCE CLIENT SCRIPT
// ============================================================================

frappe.ui.form.on("Member", {
    refresh: function(frm) {
        // Add Generate QR Code button
        if (!frm.doc.__islocal && frm.doc.personal_qr_code) {
            frm.add_custom_button(__('View My QR Code'), function() {
                view_member_qr_code(frm);
            }, __('Smart Check-in'));
            
            frm.add_custom_button(__('Download QR Code'), function() {
                download_qr_code(frm);
            }, __('Smart Check-in'));
        }
        
        if (!frm.doc.__islocal && !frm.doc.personal_qr_code) {
            frm.add_custom_button(__('Generate My QR Code'), function() {
                generate_member_qr(frm);
            }, __('Smart Check-in'));
        }
        
        // Add Register Device button
        if (!frm.doc.__islocal) {
            frm.add_custom_button(__('Register Current Device'), function() {
                register_current_device(frm);
            }, __('Smart Check-in'));
        }
        
        // Add View Check-in History button
        if (!frm.doc.__islocal) {
            frm.add_custom_button(__('View Check-in History'), function() {
                view_checkin_history(frm);
            }, __('Smart Check-in'));
        }
        
        // Show statistics
        if (frm.doc.total_smart_check_ins > 0) {
            let stats_html = `
                <div style="padding: 15px; background: #f8f9fa; border-radius: 8px; margin-top: 10px;">
                    <h4 style="margin-bottom: 10px;">📊 Check-in Statistics</h4>
                    <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px;">
                        <div>
                            <strong>Total Check-ins:</strong><br>
                            <span style="font-size: 24px; color: #667eea;">${frm.doc.total_smart_check_ins}</span>
                        </div>
                        <div>
                            <strong>Last Method:</strong><br>
                            <span style="font-size: 18px;">${frm.doc.last_check_in_method || 'N/A'}</span>
                        </div>
                        <div>
                            <strong>Last Check-in:</strong><br>
                            <span style="font-size: 16px;">${frappe.datetime.str_to_user(frm.doc.last_check_in_time) || 'N/A'}</span>
                        </div>
                    </div>
                </div>
            `;
            frm.set_df_property('smart_check_in_section', 'description', stats_html);
        }
    },
    
    consent_location_tracking: function(frm) {
        if (frm.doc.consent_location_tracking) {
            frappe.msgprint({
                title: __('Location Tracking Enabled'),
                message: __('You have consented to share your GPS location for attendance verification. This helps prevent remote check-ins.'),
                indicator: 'green'
            });
        }
    },
    
    consent_device_tracking: function(frm) {
        if (frm.doc.consent_device_tracking) {
            frappe.msgprint({
                title: __('Device Tracking Enabled'),
                message: __('You have consented to WiFi device tracking. Register your devices below for automatic check-in.'),
                indicator: 'green'
            });
        }
    }
});

frappe.ui.form.on("Member Device", {
    registered_devices_add: function(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        
        // Set default values
        if (!row.registered_on) {
            frappe.model.set_value(cdt, cdn, 'registered_on', frappe.datetime.get_today());
        }
    }
});

function generate_member_qr(frm) {
    frappe.show_alert({
        message: __('Generating your QR code...'),
        indicator: 'blue'
    });
    
    frappe.call({
        method: 'church.attendance.smart_attendance.generate_personal_qr_code',
        args: {
            member_id: frm.doc.name
        },
        callback: function(r) {
            if (r.message && r.message.success) {
                // Save QR code to member
                frm.set_value('personal_qr_code', r.message.qr_code);
                frm.save();
                
                // Show QR code in dialog
                show_qr_dialog(r.message.qr_image, r.message.full_name, r.message.qr_code);
                
                frappe.show_alert({
                    message: __('QR Code generated successfully!'),
                    indicator: 'green'
                });
            } else {
                frappe.msgprint({
                    title: __('Error'),
                    message: r.message.message || __('Failed to generate QR code'),
                    indicator: 'red'
                });
            }
        }
    });
}

function view_member_qr_code(frm) {
    if (!frm.doc.personal_qr_code) {
        frappe.msgprint(__('Please generate your QR code first'));
        return;
    }
    
    frappe.call({
        method: 'church.attendance.smart_attendance.generate_personal_qr_code',
        args: {
            member_id: frm.doc.name
        },
        callback: function(r) {
            if (r.message && r.message.success) {
                show_qr_dialog(r.message.qr_image, r.message.full_name, r.message.qr_code);
            }
        }
    });
}

function show_qr_dialog(qr_image, member_name, qr_code) {
    let d = new frappe.ui.Dialog({
        title: __('My QR Code'),
        size: 'large',
        fields: [
            {
                fieldtype: 'HTML',
                fieldname: 'qr_display',
                options: `
                    <div style="text-align: center; padding: 30px;">
                        <h2 style="margin-bottom: 20px;">${member_name}</h2>
                        <div style="background: white; padding: 20px; border-radius: 15px; display: inline-block; box-shadow: 0 4px 12px rgba(0,0,0,0.1);">
                            <img src="${qr_image}" style="width: 300px; height: 300px;">
                        </div>
                        <p style="margin-top: 20px; font-size: 14px; color: #666;">
                            Code: <strong>${qr_code}</strong>
                        </p>
                        <p style="margin-top: 10px; font-size: 12px; color: #999;">
                            Show this QR code at church check-in stations
                        </p>
                    </div>
                `
            }
        ],
        primary_action_label: __('Download'),
        primary_action: function() {
            download_qr_image(qr_image, member_name);
        }
    });
    
    d.show();
}

function download_qr_code(frm) {
    frappe.call({
        method: 'church.attendance.smart_attendance.generate_personal_qr_code',
        args: {
            member_id: frm.doc.name
        },
        callback: function(r) {
            if (r.message && r.message.success) {
                download_qr_image(r.message.qr_image, r.message.full_name);
            }
        }
    });
}

function download_qr_image(qr_image, member_name) {
    // Create download link
    let link = document.createElement('a');
    link.download = `${member_name.replace(/\s+/g, '_')}_QR_Code.png`;
    link.href = qr_image;
    link.click();
    
    frappe.show_alert({
        message: __('QR Code downloaded'),
        indicator: 'green'
    });
}

function register_current_device(frm) {
    if (!frm.doc.consent_device_tracking) {
        frappe.msgprint({
            title: __('Consent Required'),
            message: __('Please enable "Consent to Device Tracking" first'),
            indicator: 'orange'
        });
        return;
    }
    
    frappe.prompt([
        {
            fieldname: 'device_name',
            fieldtype: 'Data',
            label: __('Device Name'),
            reqd: 1,
            description: __('e.g., John\'s iPhone, Mary\'s Samsung'),
            default: `${frm.doc.full_name}'s Device`
        },
        {
            fieldname: 'device_type',
            fieldtype: 'Select',
            label: __('Device Type'),
            options: 'Smartphone\nTablet\nLaptop\nOther',
            default: 'Smartphone',
            reqd: 1
        },
        {
            fieldname: 'mac_address',
            fieldtype: 'Data',
            label: __('MAC Address'),
            reqd: 1,
            description: __('Find in: Settings → About Phone → Status → WiFi MAC Address')
        }
    ], function(values) {
        frappe.call({
            method: 'church.attendance.smart_attendance.register_device',
            args: {
                member_id: frm.doc.name,
                device_name: values.device_name,
                mac_address: values.mac_address.toUpperCase(),
                device_type: values.device_type
            },
            callback: function(r) {
                if (r.message && r.message.success) {
                    frappe.show_alert({
                        message: __('Device registered successfully!'),
                        indicator: 'green'
                    });
                    frm.reload_doc();
                } else {
                    frappe.msgprint({
                        title: __('Error'),
                        message: r.message.message || __('Failed to register device'),
                        indicator: 'red'
                    });
                }
            }
        });
    }, __('Register Device'));
}

function view_checkin_history(frm) {
    frappe.route_options = {
        "member_id": frm.doc.name
    };
    frappe.set_route("List", "Church Attendance");
}

// Auto-generate QR code when member is created
frappe.ui.form.on("Member", {
    after_save: function(frm) {
        if (!frm.doc.personal_qr_code && !frm.doc.__islocal) {
            // Auto-generate QR code for new members
            setTimeout(function() {
                generate_member_qr(frm);
            }, 1000);
        }
    }
});