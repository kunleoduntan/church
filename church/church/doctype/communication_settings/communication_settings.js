// Copyright (c) 2026, kunle and contributors
// For license information, please see license.txt

// Communication Settings Client Script

frappe.ui.form.on('Communication Settings', {
    refresh: function(frm) {
        // Add test buttons
        add_test_buttons(frm);
        
        // Update status indicators
        update_status_indicators(frm);
    },
    
    enable_sms: function(frm) {
        if (!frm.doc.enable_sms) {
            frm.set_value('sms_provider', '');
            frm.set_value('sms_enabled', 0);
        }
    },
    
    enable_whatsapp: function(frm) {
        if (!frm.doc.enable_whatsapp) {
            frm.set_value('whatsapp_provider', '');
            frm.set_value('whatsapp_enabled', 0);
        }
    },
    
    sms_provider: function(frm) {
        validate_sms_configuration(frm);
    },
    
    whatsapp_provider: function(frm) {
        validate_whatsapp_configuration(frm);
    },
    
    // Twilio SMS fields
    twilio_account_sid: function(frm) {
        validate_sms_configuration(frm);
    },
    twilio_auth_token: function(frm) {
        validate_sms_configuration(frm);
    },
    twilio_from_number: function(frm) {
        validate_sms_configuration(frm);
    },
    
    // Nexmo fields
    nexmo_api_key: function(frm) {
        validate_sms_configuration(frm);
    },
    nexmo_api_secret: function(frm) {
        validate_sms_configuration(frm);
    },
    
    // Custom SMS fields
    custom_sms_api_endpoint: function(frm) {
        validate_sms_configuration(frm);
    },
    
    // Twilio WhatsApp fields
    twilio_whatsapp_sid: function(frm) {
        validate_whatsapp_configuration(frm);
    },
    twilio_whatsapp_token: function(frm) {
        validate_whatsapp_configuration(frm);
    },
    
    // WATI fields
    wati_access_token: function(frm) {
        validate_whatsapp_configuration(frm);
    },
    
    // Custom WhatsApp fields
    custom_whatsapp_api_endpoint: function(frm) {
        validate_whatsapp_configuration(frm);
    }
});

function add_test_buttons(frm) {
    // Test SMS button
    if (frm.doc.enable_sms && frm.doc.sms_enabled) {
        frm.add_custom_button(__('Test SMS'), function() {
            test_sms(frm);
        }, __('Test'));
    }
    
    // Test WhatsApp button
    if (frm.doc.enable_whatsapp && frm.doc.whatsapp_enabled) {
        frm.add_custom_button(__('Test WhatsApp'), function() {
            test_whatsapp(frm);
        }, __('Test'));
    }
    
    // Test Email button
    if (frm.doc.enable_email) {
        frm.add_custom_button(__('Test Email'), function() {
            test_email(frm);
        }, __('Test'));
    }
    
    // Validate All Configuration
    frm.add_custom_button(__('Validate Configuration'), function() {
        validate_all_configuration(frm);
    }).addClass('btn-primary');
}

function test_sms(frm) {
    if (!frm.doc.test_phone_number) {
        frappe.msgprint(__('Please enter a Test Phone Number'));
        return;
    }
    
    frappe.prompt({
        label: __('Test Message'),
        fieldname: 'message',
        fieldtype: 'Small Text',
        default: 'This is a test SMS from Communication Settings',
        reqd: 1
    }, function(values) {
        frappe.call({
            method: 'church.church.doctype.communication_settings.communication_settings.test_sms_configuration',
            args: {
                phone_number: frm.doc.test_phone_number,
                message: values.message
            },
            freeze: true,
            freeze_message: __('Sending test SMS...'),
            callback: function(r) {
                if (r.message && r.message.success) {
                    frappe.show_alert({
                        message: __('Test SMS sent successfully!'),
                        indicator: 'green'
                    }, 5);
                    
                    frm.set_value('last_test_date', frappe.datetime.now_datetime());
                    frm.set_value('last_test_status', 'SMS: Success');
                    frm.save();
                } else {
                    frappe.msgprint({
                        title: __('Test Failed'),
                        indicator: 'red',
                        message: r.message.error || __('Failed to send test SMS')
                    });
                    
                    frm.set_value('last_test_status', 'SMS: Failed - ' + (r.message.error || 'Unknown error'));
                }
            }
        });
    }, __('Send Test SMS'));
}

function test_whatsapp(frm) {
    if (!frm.doc.test_phone_number) {
        frappe.msgprint(__('Please enter a Test Phone Number'));
        return;
    }
    
    let d = new frappe.ui.Dialog({
        title: __('Send Test WhatsApp'),
        fields: [
            {
                label: __('Test Message'),
                fieldname: 'message',
                fieldtype: 'Small Text',
                default: 'This is a test WhatsApp message from Communication Settings',
                reqd: 1
            },
            {
                label: __('Image URL (Optional)'),
                fieldname: 'image_url',
                fieldtype: 'Data'
            }
        ],
        primary_action_label: __('Send'),
        primary_action: function(values) {
            frappe.call({
                method: 'church.church.doctype.communication_settings.communication_settings.test_whatsapp_configuration',
                args: {
                    phone_number: frm.doc.test_phone_number,
                    message: values.message,
                    image_url: values.image_url
                },
                freeze: true,
                freeze_message: __('Sending test WhatsApp...'),
                callback: function(r) {
                    if (r.message && r.message.success) {
                        frappe.show_alert({
                            message: __('Test WhatsApp sent successfully!'),
                            indicator: 'green'
                        }, 5);
                        
                        frm.set_value('last_test_date', frappe.datetime.now_datetime());
                        frm.set_value('last_test_status', 'WhatsApp: Success');
                        frm.save();
                        d.hide();
                    } else {
                        frappe.msgprint({
                            title: __('Test Failed'),
                            indicator: 'red',
                            message: r.message.error || __('Failed to send test WhatsApp')
                        });
                        
                        frm.set_value('last_test_status', 'WhatsApp: Failed - ' + (r.message.error || 'Unknown error'));
                    }
                }
            });
        }
    });
    
    d.show();
}

function test_email(frm) {
    if (!frm.doc.test_email) {
        frappe.msgprint(__('Please enter a Test Email Address'));
        return;
    }
    
    frappe.prompt([
        {
            label: __('Subject'),
            fieldname: 'subject',
            fieldtype: 'Data',
            default: 'Test Email from Communication Settings',
            reqd: 1
        },
        {
            label: __('Message'),
            fieldname: 'message',
            fieldtype: 'Text Editor',
            default: 'This is a test email to verify your email configuration.',
            reqd: 1
        }
    ], function(values) {
        frappe.call({
            method: 'church.church.doctype.communication_settings.communication_settings.test_email_configuration',
            args: {
                email: frm.doc.test_email,
                subject: values.subject,
                message: values.message
            },
            freeze: true,
            freeze_message: __('Sending test email...'),
            callback: function(r) {
                if (r.message && r.message.success) {
                    frappe.show_alert({
                        message: __('Test email sent successfully!'),
                        indicator: 'green'
                    }, 5);
                    
                    frm.set_value('last_test_date', frappe.datetime.now_datetime());
                    frm.set_value('last_test_status', 'Email: Success');
                    frm.save();
                } else {
                    frappe.msgprint({
                        title: __('Test Failed'),
                        indicator: 'red',
                        message: r.message.error || __('Failed to send test email')
                    });
                    
                    frm.set_value('last_test_status', 'Email: Failed - ' + (r.message.error || 'Unknown error'));
                }
            }
        });
    }, __('Send Test Email'));
}

function validate_sms_configuration(frm) {
    if (!frm.doc.enable_sms || !frm.doc.sms_provider) {
        frm.set_value('sms_enabled', 0);
        return;
    }
    
    let is_valid = false;
    
    if (frm.doc.sms_provider === 'Twilio') {
        is_valid = frm.doc.twilio_account_sid && frm.doc.twilio_auth_token && frm.doc.twilio_from_number;
    } else if (frm.doc.sms_provider === 'Nexmo/Vonage') {
        is_valid = frm.doc.nexmo_api_key && frm.doc.nexmo_api_secret && frm.doc.nexmo_from_number;
    } else if (frm.doc.sms_provider === 'Custom API') {
        is_valid = frm.doc.custom_sms_api_endpoint && frm.doc.custom_sms_body_template;
    }
    
    frm.set_value('sms_enabled', is_valid ? 1 : 0);
    
    if (is_valid) {
        frappe.show_alert({
            message: __('SMS configuration is valid'),
            indicator: 'green'
        }, 3);
    }
}

function validate_whatsapp_configuration(frm) {
    if (!frm.doc.enable_whatsapp || !frm.doc.whatsapp_provider) {
        frm.set_value('whatsapp_enabled', 0);
        return;
    }
    
    let is_valid = false;
    
    if (frm.doc.whatsapp_provider === 'Twilio') {
        is_valid = frm.doc.twilio_whatsapp_sid && frm.doc.twilio_whatsapp_token && frm.doc.twilio_whatsapp_number;
    } else if (frm.doc.whatsapp_provider === 'WATI') {
        is_valid = frm.doc.wati_access_token && frm.doc.wati_number;
    } else if (frm.doc.whatsapp_provider === 'Custom API') {
        is_valid = frm.doc.custom_whatsapp_api_endpoint && frm.doc.custom_whatsapp_body_template;
    }
    
    frm.set_value('whatsapp_enabled', is_valid ? 1 : 0);
    
    if (is_valid) {
        frappe.show_alert({
            message: __('WhatsApp configuration is valid'),
            indicator: 'green'
        }, 3);
    }
}

function validate_all_configuration(frm) {
    let results = {
        email: frm.doc.enable_email,
        sms: frm.doc.sms_enabled,
        whatsapp: frm.doc.whatsapp_enabled
    };
    
    let message = '<div style="padding: 15px;">';
    message += '<h4>Configuration Status</h4>';
    message += '<table class="table table-bordered">';
    message += '<tr><th>Channel</th><th>Status</th></tr>';
    
    message += `<tr>
        <td><strong>Email</strong></td>
        <td>${results.email ? '<span style="color: green;">✓ Enabled</span>' : '<span style="color: red;">✗ Disabled</span>'}</td>
    </tr>`;
    
    message += `<tr>
        <td><strong>SMS</strong></td>
        <td>${results.sms ? '<span style="color: green;">✓ Configured</span>' : '<span style="color: orange;">⚠ Not Configured</span>'}</td>
    </tr>`;
    
    message += `<tr>
        <td><strong>WhatsApp</strong></td>
        <td>${results.whatsapp ? '<span style="color: green;">✓ Configured</span>' : '<span style="color: orange;">⚠ Not Configured</span>'}</td>
    </tr>`;
    
    message += '</table></div>';
    
    frappe.msgprint({
        title: __('Configuration Validation'),
        message: message,
        indicator: (results.email || results.sms || results.whatsapp) ? 'green' : 'orange'
    });
}

function update_status_indicators(frm) {
    // Add visual indicators for enabled channels
    setTimeout(() => {
        // SMS Status
        if (frm.doc.sms_enabled) {
            frm.set_df_property('sms_enabled', 'description', '✅ SMS is properly configured');
        } else if (frm.doc.enable_sms) {
            frm.set_df_property('sms_enabled', 'description', '⚠️ SMS enabled but not configured');
        }
        
        // WhatsApp Status
        if (frm.doc.whatsapp_enabled) {
            frm.set_df_property('whatsapp_enabled', 'description', '✅ WhatsApp is properly configured');
        } else if (frm.doc.enable_whatsapp) {
            frm.set_df_property('whatsapp_enabled', 'description', '⚠️ WhatsApp enabled but not configured');
        }
    }, 200);
}

console.log("✅ Communication Settings Client Script Loaded");