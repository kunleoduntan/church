// Copyright (c) 2026, kunle and contributors
// For license information, please see license.txt

// Communication Campaign Client Script
// Comprehensive multi-channel communication system

frappe.ui.form.on('Communication Campaign', {
    // ========================================
    // FORM LOAD AND REFRESH
    // ========================================
    refresh: function(frm) {
        // Add custom buttons
        add_custom_buttons(frm);
        
        // Apply styling
        apply_universal_table_styling(frm);
        apply_status_badge(frm);
        
        // Set dynamic field properties
        set_dynamic_properties(frm);
    },
    
    onload: function(frm) {
        apply_universal_table_styling(frm);
        set_dynamic_properties(frm);
    },
    
    // ========================================
    // FIELD CHANGE HANDLERS
    // ========================================
    
    is_test: function(frm) {
        if (frm.doc.is_test === 0) {
            frm.set_value("test_email", "");
            frm.set_value("test_phone_number", "");
        }
    },
    
    audience_group: function(frm) {
        if (frm.doc.audience_group !== "Member") {
            frm.set_value("filter", "");
            clear_filter_fields(frm);
        }
        frm.set_value("recipient_type", "");
        frm.clear_table('recipients');
        frm.refresh_field('recipients');
    },
    
    recipient_type: function(frm) {
        // Clear all selection tables when type changes
        frm.clear_table('recipient_programs');
        frm.clear_table('recipient_courses');
        frm.clear_table('recipient_student_groups');
        frm.clear_table('recipient_departments');
        frm.refresh_field('recipient_programs');
        frm.refresh_field('recipient_courses');
        frm.refresh_field('recipient_student_groups');
        frm.refresh_field('recipient_departments');
    },
    
    filter: function(frm) {
        if (!frm.doc.filter) {
            clear_filter_fields(frm);
        }
    },
    
    send_immediately: function(frm) {
        if (frm.doc.send_immediately) {
            frm.set_value("schedule", 0);
            frm.set_value("scheduled_date", "");
            frm.set_value("schedule_time", "");
        }
    },
    
    schedule: function(frm) {
        if (frm.doc.schedule) {
            frm.set_value("send_immediately", 0);
        }
    },
    
    is_recurring: function(frm) {
        if (frm.doc.is_recurring) {
            frm.set_value("schedule", 1);
            frm.set_value("send_immediately", 0);
        } else {
            frm.set_value("recurrence_pattern", "");
            frm.set_value("recurrence_interval", 1);
            frm.set_value("recurrence_end_date", "");
        }
    }
});

// ========================================
// CUSTOM BUTTONS
// ========================================
function add_custom_buttons(frm) {
    // Get Contacts Button
    frm.add_custom_button(__('Get Contacts'), function() {
        get_contacts(frm);
    }).addClass("btn-success");
    
    // Import from Excel Button
    frm.add_custom_button(__('Import from Excel'), function() {
        show_import_dialog(frm);
    }).addClass("btn-info");
    
    // Download Template Button
    frm.add_custom_button(__('Download Excel Template'), function() {
        download_excel_template();
    });
    
    // Preview Button
    if (!frm.is_new()) {
        frm.add_custom_button(__('Preview Message'), function() {
            preview_message(frm);
        });
    }
    
    // Send Test Button - Available for Draft and Submitted documents
    if (!frm.is_new() && frm.doc.recipients && frm.doc.recipients.length > 0) {
        frm.add_custom_button(__('Send Test'), function() {
            send_test_campaign(frm);
        }, __('Actions')).addClass("btn-warning");
    }
    
    // Send Now Button - Only for Submitted documents that haven't been sent
    if (!frm.is_new() && frm.doc.docstatus === 1 && !frm.doc.sent) {
        frm.add_custom_button(__('Send Now'), function() {
            send_campaign_now(frm);
        }, __('Actions')).addClass("btn-primary");
    }
}

// ========================================
// GET CONTACTS FUNCTION
// ========================================
function get_contacts(frm) {
    if (!frm.doc.audience_group) {
        frappe.msgprint(__('Please select an Audience Group first.'));
        return;
    }
    
    if (!frm.doc.recipient_type) {
        frappe.msgprint(__('Please select a Recipient Selection Method.'));
        return;
    }
    
    let filters = [];
    let doctype = frm.doc.audience_group;
    let fields = get_fields_for_doctype(doctype);
    
    // Build filters based on recipient type
    if (frm.doc.recipient_type === 'Filtered' && frm.doc.audience_group === 'Member') {
        filters = build_member_filters(frm);
    } else if (frm.doc.recipient_type === 'Programs/Courses') {
        get_recipients_from_programs_courses(frm);
        return;
    } else if (frm.doc.recipient_type === 'Student Groups') {
        get_recipients_from_student_groups(frm);
        return;
    } else if (frm.doc.recipient_type === 'Departments') {
        get_recipients_from_departments(frm);
        return;
    }
    
    // Fetch contacts
    frappe.call({
        method: 'frappe.client.get_list',
        args: {
            doctype: doctype,
            fields: fields,
            filters: filters,
            limit_page_length: 0
        },
        freeze: true,
        freeze_message: __('Fetching contacts...'),
        callback: function(r) {
            if (r.message && r.message.length) {
                populate_recipients(frm, r.message, doctype);
            } else {
                frappe.msgprint(__('No contacts found.'));
            }
        }
    });
}

// ========================================
// BUILD MEMBER FILTERS
// ========================================
function build_member_filters(frm) {
    let filters = [];
    let filter = frm.doc.filter;
    
    if (filter === "Sunday School Class" && frm.doc.sunday_school_class) {
        filters.push(["sunday_school_class", "=", frm.doc.sunday_school_class]);
    } else if (filter === "Gender" && frm.doc.gender) {
        filters.push(["gender", "=", frm.doc.gender]);
    } else if (filter === "Marital Status" && frm.doc.marital_status) {
        filters.push(["marital_status", "=", frm.doc.marital_status]);
    } else if (filter === "Branch" && frm.doc.branch) {
        filters.push(["branch", "=", frm.doc.branch]);
    } else if (filter === "Member Status" && frm.doc.member_status) {
        filters.push(["member_status", "=", frm.doc.member_status]);
    } else if (filter === "Pastors") {
        filters.push(["is_a_pastor", "=", 1]);
    } else if (filter === "Workers") {
        filters.push(["is_a_worker", "=", 1]);
    } else if (filter === "HODs") {
        filters.push(["is_hod", "=", 1]);
    } else if (filter === "Teenagers") {
        filters.push(["age", ">=", 13], ["age", "<=", 19]);
    } else if (filter === "Elders") {
        filters.push(["age", ">=", 50]);
    } else if (filter === "Adults") {
        filters.push(["age", ">=", 18]);
    } else if (filter === "Men") {
        filters.push(["gender", "=", "Male"], ["marital_status", "in", ["Married", "Widower"]]);
    } else if (filter === "Women") {
        filters.push(["gender", "=", "Female"], ["marital_status", "in", ["Married", "Widow"]]);
    } else if (filter === "Youth") {
        filters.push(["marital_status", "=", "Single"]);
    }
    
    return filters;
}

// ========================================
// GET FIELDS FOR DOCTYPE
// ========================================
function get_fields_for_doctype(doctype) {
    let fields = ['name'];
    
    if (doctype === "Member") {
        fields = ['name', 'full_name', 'email', 'mobile_phone', 'salutation'];
    } else if (doctype === "Customer") {
        fields = ['name', 'customer_name', 'email_id', 'mobile_no', 'custom_phone_no', 'custom_email', 'salutation'];
    } else if (doctype === "Supplier") {
        fields = ['name', 'supplier_name', 'email_id', 'mobile_no', 'custom_phone_no', 'custom_email', 'salutation'];
    } else if (doctype === "Employee") {
        fields = ['name', 'employee_name', 'cell_number', 'personal_email', 'custom_phone_no', 'company_email', 'salutation'];
    } else if (doctype === "Contact") {
        fields = ['name', 'first_name', 'last_name', 'mobile_no', 'email_id', 'custom_phone_no', 'salutation'];
    } else if (doctype === "Student") {
        fields = ['name', 'student_name', 'student_email_id', 'student_mobile_number', 'salutation'];
    } else if (doctype === "Guardian") {
        fields = ['name', 'guardian_name', 'email_address', 'mobile_number', 'salutation'];
    }
    
    return fields;
}

// ========================================
// POPULATE RECIPIENTS
// ========================================
function populate_recipients(frm, contacts, doctype) {
    frm.clear_table('recipients');
    
    contacts.forEach(function(contact) {
        let row = frm.add_child('recipients');
        row.reference_doctype = doctype;
        row.reference_name = contact.name;
        row.full_name = get_full_name(contact, doctype);
        row.email = get_email(contact, doctype);
        row.mobile_phone = get_mobile(contact, doctype);
        row.salutation = contact.salutation || "Dear";
    });
    
    frm.refresh_field('recipients');
    frm.set_value('total_recipients', frm.doc.recipients.length);
    
    frappe.show_alert({
        message: __('Added {0} contacts to recipients', [contacts.length]),
        indicator: 'green'
    }, 5);
}

// ========================================
// HELPER FUNCTIONS FOR RECIPIENT DATA
// ========================================
function get_full_name(contact, doctype) {
    if (doctype === "Member") return contact.full_name;
    if (doctype === "Customer") return contact.customer_name;
    if (doctype === "Supplier") return contact.supplier_name;
    if (doctype === "Employee") return contact.employee_name;
    if (doctype === "Student") return contact.student_name;
    if (doctype === "Guardian") return contact.guardian_name;
    if (doctype === "Contact") {
        return contact.last_name ? `${contact.first_name} ${contact.last_name}` : contact.first_name;
    }
    return "";
}

function get_email(contact, doctype) {
    return contact.email || contact.email_id || contact.student_email_id || 
           contact.email_address || contact.preferred_email || 
           contact.custom_email || contact.company_email || contact.personal_email || "";
}

function get_mobile(contact, doctype) {
    return contact.mobile_phone || contact.mobile_no || contact.student_mobile_number ||
           contact.mobile_number || contact.cell_number || contact.custom_phone_no || "";
}

// ========================================
// GET RECIPIENTS FROM PROGRAMS/COURSES
// ========================================
function get_recipients_from_programs_courses(frm) {
    let programs = frm.doc.recipient_programs || [];
    let courses = frm.doc.recipient_courses || [];
    
    if (programs.length === 0 && courses.length === 0) {
        frappe.msgprint(__('Please select at least one Program or Course.'));
        return;
    }
    
    // Get students from selected programs and courses
    frappe.call({
        method: 'church.church.doctype.communication_campaign.communication_campaign.get_students_from_programs_courses',
        args: {
            programs: programs.map(p => p.program),
            courses: courses.map(c => c.course)
        },
        freeze: true,
        freeze_message: __('Fetching students...'),
        callback: function(r) {
            if (r.message && r.message.length) {
                populate_recipients(frm, r.message, 'Student');
            } else {
                frappe.msgprint(__('No students found.'));
            }
        }
    });
}

// ========================================
// GET RECIPIENTS FROM STUDENT GROUPS
// ========================================
function get_recipients_from_student_groups(frm) {
    let groups = frm.doc.recipient_student_groups || [];
    
    if (groups.length === 0) {
        frappe.msgprint(__('Please select at least one Student Group.'));
        return;
    }
    
    frappe.call({
        method: 'church.church.doctype.communication_campaign.communication_campaign.get_students_from_groups',
        args: {
            groups: groups.map(g => g.student_group)
        },
        freeze: true,
        freeze_message: __('Fetching students...'),
        callback: function(r) {
            if (r.message && r.message.length) {
                populate_recipients(frm, r.message, 'Student');
            } else {
                frappe.msgprint(__('No students found.'));
            }
        }
    });
}

// ========================================
// GET RECIPIENTS FROM DEPARTMENTS
// ========================================
function get_recipients_from_departments(frm) {
    let departments = frm.doc.recipient_departments || [];
    
    if (departments.length === 0) {
        frappe.msgprint(__('Please select at least one Church Department.'));
        return;
    }
    
    frappe.call({
        method: 'church.church.doctype.communication_campaign.communication_campaign.get_members_from_departments',
        args: {
            departments: departments.map(d => d.department)
        },
        freeze: true,
        freeze_message: __('Fetching members...'),
        callback: function(r) {
            if (r.message && r.message.length) {
                populate_recipients(frm, r.message, 'Member');
            } else {
                frappe.msgprint(__('No members found.'));
            }
        }
    });
}

// ========================================
// SEND CAMPAIGN
// ========================================
function send_campaign_now(frm) {
    // Confirmation dialog
    frappe.confirm(
        __('Are you sure you want to send this campaign to <strong>{0} recipients</strong> now?', [frm.doc.total_recipients]),
        function() {
            // Yes - proceed with sending
            frappe.call({
                method: "church.church.doctype.communication_campaign.communication_campaign.send_campaign",
                args: {
                    docname: frm.doc.name
                },
                callback: function(r) {
                    if (r.exc) {
                        frappe.msgprint({
                            title: __('Error'),
                            indicator: 'red',
                            message: __('Failed to send campaign. Please check error logs.')
                        });
                    } else {
                        frappe.msgprint({
                            title: __('Success'),
                            indicator: 'green',
                            message: r.message || __('Campaign sent successfully!')
                        });
                        frm.reload_doc();
                    }
                },
                freeze: true,
                freeze_message: __('Sending campaign...')
            });
        },
        function() {
            // No - cancelled
            frappe.show_alert({
                message: __('Campaign sending cancelled'),
                indicator: 'orange'
            }, 3);
        }
    );
}

function send_test_campaign(frm) {
    // Show dialog to collect test contact info
    let test_channels = [];
    
    if (frm.doc.communication_channel && frm.doc.communication_channel.includes('Email')) {
        test_channels.push({
            label: __('Test Email Address'),
            fieldname: 'test_email',
            fieldtype: 'Data',
            options: 'Email',
            reqd: 1
        });
    }
    
    if (frm.doc.communication_channel === 'SMS' || 
        (frm.doc.communication_channel && frm.doc.communication_channel.includes('SMS'))) {
        test_channels.push({
            label: __('Test Phone Number'),
            fieldname: 'test_phone',
            fieldtype: 'Data',
            options: 'Phone',
            reqd: 1,
            description: __('Include country code (e.g., +1234567890)')
        });
    }
    
    if (frm.doc.communication_channel && frm.doc.communication_channel.includes('WhatsApp')) {
        if (!test_channels.some(f => f.fieldname === 'test_phone')) {
            test_channels.push({
                label: __('Test Phone Number (WhatsApp)'),
                fieldname: 'test_phone',
                fieldtype: 'Data',
                options: 'Phone',
                reqd: 1,
                description: __('Include country code (e.g., +1234567890)')
            });
        }
    }
    
    if (test_channels.length === 0) {
        frappe.msgprint(__('Please select a communication channel first'));
        return;
    }
    
    // Add test recipient name
    test_channels.unshift({
        label: __('Test Recipient Name'),
        fieldname: 'test_name',
        fieldtype: 'Data',
        default: 'Test Recipient',
        reqd: 1
    });
    
    let d = new frappe.ui.Dialog({
        title: __('Send Test Campaign'),
        fields: [
            {
                fieldtype: 'HTML',
                fieldname: 'info_html',
                options: `
                    <div style="padding: 15px; background: #fef3c7; border-radius: 8px; margin-bottom: 15px;">
                        <strong>ℹ️ Test Mode:</strong> This will send the campaign to the test contact(s) only, 
                        not to the actual recipients.
                    </div>
                `
            },
            ...test_channels
        ],
        primary_action_label: __('Send Test'),
        primary_action: function(values) {
            frappe.call({
                method: 'church.church.doctype.communication_campaign.communication_campaign.send_test_campaign',
                args: {
                    docname: frm.doc.name,
                    test_name: values.test_name,
                    test_email: values.test_email || '',
                    test_phone: values.test_phone || ''
                },
                freeze: true,
                freeze_message: __('Sending test campaign...'),
                callback: function(r) {
                    if (r.message && r.message.success) {
                        frappe.show_alert({
                            message: __('Test campaign sent successfully!'),
                            indicator: 'green'
                        }, 5);
                        d.hide();
                        
                        // Show detailed results
                        let results_html = '<div style="padding: 15px;"><h4>Test Results:</h4><ul>';
                        if (r.message.email_sent) {
                            results_html += `<li>✅ Email sent to ${values.test_email}</li>`;
                        }
                        if (r.message.sms_sent) {
                            results_html += `<li>✅ SMS sent to ${values.test_phone}</li>`;
                        }
                        if (r.message.whatsapp_sent) {
                            results_html += `<li>✅ WhatsApp sent to ${values.test_phone}</li>`;
                        }
                        results_html += '</ul></div>';
                        
                        frappe.msgprint({
                            title: __('Test Campaign Sent'),
                            message: results_html,
                            indicator: 'green'
                        });
                    } else {
                        frappe.msgprint({
                            title: __('Test Failed'),
                            indicator: 'red',
                            message: r.message.error || __('Failed to send test campaign')
                        });
                    }
                }
            });
        }
    });
    
    d.show();
}

// ========================================
// PREVIEW MESSAGE
// ========================================
function preview_message(frm) {
    let message = '';
    
    if (frm.doc.communication_channel && frm.doc.communication_channel.includes('Email')) {
        if (frm.doc.message_format === 'HTML') {
            message = frm.doc.message_html || '';
        } else {
            message = frm.doc.message_body || '';
        }
    } else if (frm.doc.communication_channel === 'SMS') {
        message = frm.doc.message_body || '';
    } else if (frm.doc.communication_channel && frm.doc.communication_channel.includes('WhatsApp')) {
        message = frm.doc.whatsapp_message_body || '';
    }
    
    let d = new frappe.ui.Dialog({
        title: __('Message Preview'),
        fields: [
            {
                fieldtype: 'HTML',
                fieldname: 'preview_html'
            }
        ]
    });
    
    d.fields_dict.preview_html.$wrapper.html(`
        <div style="padding: 20px; background: #f9f9f9; border-radius: 8px;">
            <h4 style="margin-bottom: 15px;">Subject: ${frm.doc.subject || 'No Subject'}</h4>
            <div style="background: white; padding: 20px; border-radius: 6px;">
                ${message}
            </div>
        </div>
    `);
    
    d.show();
}

// ========================================
// EXCEL IMPORT FUNCTIONALITY
// ========================================
function show_import_dialog(frm) {
    let d = new frappe.ui.Dialog({
        title: __('Import Recipients from Excel'),
        fields: [
            {
                fieldtype: 'HTML',
                fieldname: 'instructions_html',
                options: `
                    <div style="padding: 15px; background: #f0f9ff; border-radius: 8px; margin-bottom: 15px;">
                        <h4 style="margin-top: 0; color: #0369a1;">📋 Instructions</h4>
                        <ol style="margin-bottom: 0;">
                            <li>Download the Excel template using the "Download Excel Template" button</li>
                            <li>Fill in the recipient details (Full Name, Email, Mobile Phone, Salutation)</li>
                            <li>Save the Excel file</li>
                            <li>Upload it below</li>
                        </ol>
                    </div>
                `
            },
            {
                label: __('Excel File'),
                fieldname: 'excel_file',
                fieldtype: 'Attach',
                reqd: 1
            },
            {
                fieldtype: 'Section Break'
            },
            {
                fieldtype: 'HTML',
                fieldname: 'required_columns_html',
                options: `
                    <div style="padding: 10px; background: #fef3c7; border-radius: 6px;">
                        <strong>Required Columns:</strong>
                        <ul style="margin-bottom: 0;">
                            <li><strong>Full Name</strong> - Recipient's full name (required)</li>
                            <li><strong>Email</strong> - Email address (required for email campaigns)</li>
                            <li><strong>Mobile Phone</strong> - Phone number (required for SMS/WhatsApp)</li>
                            <li><strong>Salutation</strong> - e.g., Mr., Mrs., Dr. (optional)</li>
                            <li><strong>Reference DocType</strong> - e.g., Member, Customer (optional)</li>
                            <li><strong>Reference Name</strong> - Document name (optional)</li>
                        </ul>
                    </div>
                `
            }
        ],
        primary_action_label: __('Import'),
        primary_action: function(values) {
            if (!values.excel_file) {
                frappe.msgprint(__('Please attach an Excel file'));
                return;
            }
            
            // Call server method to process Excel
            frappe.call({
                method: 'church.church.doctype.communication_campaign.communication_campaign.import_recipients_from_excel',
                args: {
                    file_url: values.excel_file,
                    campaign_name: frm.doc.name
                },
                freeze: true,
                freeze_message: __('Processing Excel file...'),
                callback: function(r) {
                    if (r.message && r.message.success) {
                        // Clear existing recipients and add imported ones
                        frm.clear_table('recipients');
                        
                        r.message.recipients.forEach(function(recipient) {
                            let row = frm.add_child('recipients');
                            row.reference_doctype = recipient.reference_doctype || '';
                            row.reference_name = recipient.reference_name || '';
                            row.full_name = recipient.full_name;
                            row.salutation = recipient.salutation || 'Dear';
                            row.email = recipient.email || '';
                            row.mobile_phone = recipient.mobile_phone || '';
                        });
                        
                        frm.refresh_field('recipients');
                        frm.set_value('total_recipients', frm.doc.recipients.length);
                        
                        frappe.show_alert({
                            message: __('Successfully imported {0} recipients', [r.message.count]),
                            indicator: 'green'
                        }, 5);
                        
                        d.hide();
                        
                        // Show summary
                        if (r.message.errors && r.message.errors.length > 0) {
                            show_import_summary(r.message);
                        }
                    } else {
                        frappe.msgprint({
                            title: __('Import Failed'),
                            indicator: 'red',
                            message: r.message.error || __('Failed to import recipients')
                        });
                    }
                }
            });
        }
    });
    
    d.show();
}

function show_import_summary(result) {
    let error_html = '';
    
    if (result.errors && result.errors.length > 0) {
        error_html = '<h4 style="color: #dc2626;">⚠️ Import Warnings</h4><ul>';
        result.errors.forEach(function(error) {
            error_html += `<li>Row ${error.row}: ${error.message}</li>`;
        });
        error_html += '</ul>';
    }
    
    let d = new frappe.ui.Dialog({
        title: __('Import Summary'),
        fields: [
            {
                fieldtype: 'HTML',
                fieldname: 'summary_html',
                options: `
                    <div style="padding: 15px;">
                        <div style="background: #d1fae5; padding: 15px; border-radius: 8px; margin-bottom: 15px;">
                            <h4 style="color: #065f46; margin-top: 0;">✅ Import Successful</h4>
                            <p style="margin-bottom: 0;"><strong>${result.count}</strong> recipients imported successfully</p>
                        </div>
                        ${error_html}
                    </div>
                `
            }
        ]
    });
    
    d.show();
}

function download_excel_template() {
    // Create template data
    const template_data = [
        ['Full Name', 'Email', 'Mobile Phone', 'Salutation', 'Reference DocType', 'Reference Name'],
        ['John Doe', 'john.doe@example.com', '+1234567890', 'Mr.', 'Member', 'MEM-001'],
        ['Jane Smith', 'jane.smith@example.com', '+1234567891', 'Mrs.', 'Member', 'MEM-002'],
        ['Example User', 'example@example.com', '+1234567892', 'Dr.', '', '']
    ];
    
    // Call server method to generate Excel
    frappe.call({
        method: 'church.church.doctype.communication_campaign.communication_campaign.generate_excel_template',
        args: {
            data: template_data
        },
        callback: function(r) {
            if (r.message) {
                // Open the file in new tab for download
                window.open(r.message.file_url, '_blank');
                
                frappe.show_alert({
                    message: __('Template downloaded successfully'),
                    indicator: 'green'
                }, 3);
            }
        }
    });
}

// ========================================
// UTILITY FUNCTIONS
// ========================================
function clear_filter_fields(frm) {
    frm.set_value("gender", "");
    frm.set_value("sunday_school_class", "");
    frm.set_value("branch", "");
    frm.set_value("marital_status", "");
    frm.set_value("member_status", "");
}

function set_dynamic_properties(frm) {
    // Make total_recipients read-only
    frm.set_df_property('total_recipients', 'read_only', 1);
}

// ========================================
// STYLING FUNCTIONS
// ========================================
function apply_universal_table_styling(frm) {
    setTimeout(() => {
        if (!frm.fields_dict || !frm.fields_dict.recipients) return;
        
        const grid = frm.fields_dict.recipients.grid;
        if (!grid) return;
        
        // Alternate row colors
        grid.wrapper.find('.grid-row').each((i, row) => {
            $(row).css({
                'background-color': i % 2 === 0 ? '#ffffff' : '#ffefd5',
                'transition': 'all 0.3s ease'
            });
            
            $(row).hover(
                function() {
                    $(this).css({
                        'background-color': '#f0f9ff',
                        'box-shadow': '0 2px 8px rgba(0, 0, 0, 0.08)'
                    });
                },
                function() {
                    $(this).css({
                        'background-color': i % 2 === 0 ? '#ffffff' : '#ffefd5',
                        'box-shadow': 'none'
                    });
                }
            );
        });
    }, 200);
}

function apply_status_badge(frm) {
    setTimeout(() => {
        const status = frm.doc.status || 'Draft';
        const statusConfig = {
            'Draft': { color: '#2563eb', bg: '#dbeafe', icon: '📝' },
            'Scheduled': { color: '#d97706', bg: '#fef3c7', icon: '⏰' },
            'Sending': { color: '#7c3aed', bg: '#ede9fe', icon: '📤' },
            'Completed': { color: '#065f46', bg: '#d1fae5', icon: '✅' },
            'Cancelled': { color: '#991b1b', bg: '#fee2e2', icon: '❌' },
            'Failed': { color: '#991b1b', bg: '#fee2e2', icon: '⚠️' }
        };
        
        const config = statusConfig[status] || { color: '#6b7280', bg: '#f3f4f6', icon: '📄' };
        
        $('.custom-status-badge').remove();
        const badge = $(`
            <div class="custom-status-badge"
                style="display: inline-flex;
                align-items: center;
                gap: 6px;
                padding: 6px 14px;
                border-radius: 20px;
                font-weight: 700;
                font-size: 13px;
                color: ${config.color};
                background: ${config.bg};
                margin-left: 12px;
                box-shadow: 0 2px 8px ${config.color}30;
                border: 2px solid ${config.color}40;">
                <span>${config.icon}</span>
                <span>${status.toUpperCase()}</span>
            </div>
        `);
        
        const title = $('.page-title');
        if (title.length && !title.find('.custom-status-badge').length) {
            title.append(badge);
        }
    }, 400);
}

console.log("✅ Communication Campaign Client Script Loaded");