// ============================================================================
// CHURCH ATTENDANCE - SMART CHECK-IN CLIENT SCRIPT
// ============================================================================

frappe.ui.form.on("Church Attendance", {
    refresh: function(frm) {
        // Color code based on check-in method
        if (frm.doc.check_in_method) {
            let color = get_method_color(frm.doc.check_in_method);
            frm.dashboard.set_headline_alert(
                `Checked in via: <strong>${frm.doc.check_in_method}</strong>`,
                color
            );
        }
        
        // Show fraud alert if suspicious
        if (frm.doc.is_suspicious) {
            frm.dashboard.set_headline_alert(
                `⚠️ Flagged as Suspicious: ${frm.doc.fraud_reason}`,
                'red'
            );
            
            // Add verify button for admins
            if (frappe.user_roles.includes('System Manager') || frappe.user_roles.includes('Church Admin')){
                frm.add_custom_button(__('Mark as Verified'), function() {
                    verify_attendance(frm);
                }, __('Actions'));
                
                frm.add_custom_button(__('Reject Check-in'), function() {
                    reject_attendance(frm);
                }, __('Actions'));
            }
        }
        
        // Show location on map if available
        if (frm.doc.gps_latitude && frm.doc.gps_longitude) {
            frm.add_custom_button(__('View on Map'), function() {
                show_location_map(frm);
            }, __('Location'));
            
            // Show distance indicator
            if (frm.doc.distance_from_church) {
                let color = frm.doc.location_verified ? 'green' : 'red';
                let icon = frm.doc.location_verified ? '✓' : '✗';
                frm.set_df_property('distance_from_church', 'description', 
                    `<span style="color: ${color};">${icon} ${frm.doc.distance_from_church.toFixed(0)}m from church</span>`
                );
            }
        }
        
        // Add manual check-in button for draft
        if (frm.doc.__islocal) {
            frm.add_custom_button(__('Quick Check-in'), function() {
                quick_checkin(frm);
            });
        }
    },
    
    is_suspicious: function(frm) {
        if (frm.doc.is_suspicious && !frm.doc.fraud_reason) {
            frappe.prompt([
                {
                    fieldname: 'reason',
                    fieldtype: 'Small Text',
                    label: __('Reason for Flagging'),
                    reqd: 1
                }
            ], function(values) {
                frm.set_value('fraud_reason', values.reason);
            }, __('Fraud Detection'));
        }
    }
});

function get_method_color(method) {
    const color_map = {
        'QR Code - Personal': 'blue',
        'QR Code - Service': 'green',
        'WiFi Auto': 'purple',
        'WhatsApp': 'orange',
        'WhatsApp + Location': 'green',
        'WhatsApp + Daily Code': 'blue',
        'Mobile App': 'purple',
        'Manual Entry': 'gray'
    };
    return color_map[method] || 'blue';
}

function verify_attendance(frm) {
    frappe.prompt([
        {
            fieldname: 'notes',
            fieldtype: 'Small Text',
            label: __('Verification Notes'),
            reqd: 1
        }
    ], function(values) {
        frm.set_value('is_suspicious', 0);
        frm.set_value('verified_by_admin', frappe.session.user);
        frm.set_value('admin_notes', values.notes);
        frm.save();
        
        frappe.show_alert({
            message: __('Attendance verified'),
            indicator: 'green'
        });
    }, __('Verify Attendance'));
}

function reject_attendance(frm) {
    frappe.confirm(
        __('Are you sure you want to reject this check-in? This will mark the member as absent.'),
        function() {
            frm.set_value('present', 0);
            frm.set_value('verified_by_admin', frappe.session.user);
            frm.set_value('admin_notes', 'Rejected - Fraudulent check-in');
            frm.save();
            
            frappe.show_alert({
                message: __('Check-in rejected'),
                indicator: 'red'
            });
        }
    );
}

function show_location_map(frm) {
    let d = new frappe.ui.Dialog({
        title: __('Check-in Location'),
        size: 'extra-large',
        fields: [
            {
                fieldtype: 'HTML',
                fieldname: 'map_display',
                options: `
                    <div id="attendance-map" style="height: 500px; width: 100%;"></div>
                    <div style="margin-top: 15px; padding: 15px; background: #f8f9fa; border-radius: 8px;">
                        <strong>Location Details:</strong><br>
                        Latitude: ${frm.doc.gps_latitude}<br>
                        Longitude: ${frm.doc.gps_longitude}<br>
                        Distance from Church: ${frm.doc.distance_from_church ? frm.doc.distance_from_church.toFixed(0) + 'm' : 'N/A'}<br>
                        Location Verified: ${frm.doc.location_verified ? '✅ Yes' : '❌ No'}
                    </div>
                `
            }
        ]
    });
    
    d.show();
    
    // Load map after dialog is shown
    setTimeout(function() {
        load_location_map(frm.doc.gps_latitude, frm.doc.gps_longitude);
    }, 500);
}

function load_location_map(lat, lng) {
    // Simple map display using Google Maps (if available)
    // Or OpenStreetMap
    let mapDiv = document.getElementById('attendance-map');
    if (mapDiv) {
        mapDiv.innerHTML = `
            <iframe 
                width="100%" 
                height="500" 
                frameborder="0" 
                scrolling="no" 
                marginheight="0" 
                marginwidth="0" 
                src="https://www.openstreetmap.org/export/embed.html?bbox=${lng-0.01}%2C${lat-0.01}%2C${lng+0.01}%2C${lat+0.01}&layer=mapnik&marker=${lat}%2C${lng}"
                style="border: 1px solid #ccc; border-radius: 8px;">
            </iframe>
        `;
    }
}

function quick_checkin(frm) {
    frappe.call({
        method: 'church.attendance.smart_attendance.get_current_service',
        callback: function(r) {
            if (r.message) {
                frm.set_value('service_instance', r.message);
                frm.set_value('present', 1);
                frm.set_value('check_in_method', 'Manual Entry');
                frm.set_value('check_in_timestamp', frappe.datetime.now_datetime());
                
                frappe.show_alert({
                    message: __('Service auto-filled. Please select member and save.'),
                    indicator: 'blue'
                });
            } else {
                frappe.msgprint(__('No active service found'));
            }
        }
    });
}

// Auto-fill service details when member is selected
frappe.ui.form.on("Church Attendance", {
    member_id: function(frm) {
        if (frm.doc.member_id && frm.doc.__islocal) {
            // Get member details
            frappe.db.get_doc('Member', frm.doc.member_id)
                .then(member => {
                    // You can auto-fill additional fields if needed
                    console.log('Member loaded:', member.full_name);
                });
        }
    }
});