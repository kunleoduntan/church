// Copyright (c) 2026, kunle and contributors
// For license information, please see license.txt



frappe.ui.form.on('Church Attendance', {
    refresh: function(frm) {
        // Add custom buttons for quick actions
        if (!frm.is_new()) {
            add_custom_buttons(frm);
        }
        
        // Apply conditional formatting
        apply_conditional_formatting(frm);
    },
    
    onload: function(frm) {
        // Set default values
        if (frm.is_new()) {
            frm.set_value('marked_by', frappe.session.user);
            frm.set_value('marked_at', frappe.datetime.now_datetime());
        }
        
        // Filter service instances based on service type and date
        set_service_instance_filter(frm);
    },
    
    service_type: function(frm) {
        // Auto-clear Sunday School fields when changing service type
        if (frm.doc.service_type !== 'Sunday School') {
            frm.set_value('sunday_school_class', '');
            frm.set_value('sunday_school_category', '');
        }
        
        // Update service instance filter
        set_service_instance_filter(frm);
        
        // Refresh fields to show/hide conditional sections
        frm.refresh_fields();
    },
    
    service_date: function(frm) {
        // Validate service date based on service type
        validate_service_date(frm);
        
        // Update service instance filter
        set_service_instance_filter(frm);
    },
    
    member_id: function(frm) {
        if (frm.doc.member_id) {
            // Check for duplicate attendance on same date and service
            check_duplicate_attendance(frm);
            
            // Refresh member fields
            frm.refresh_fields(['full_name', 'email', 'phone', 'age', 'gender', 'branch']);
        }
    },
    
    is_visitor: function(frm) {
        if (!frm.doc.is_visitor) {
            frm.set_value('visitor_source', '');
        }
    },
    
    before_save: function(frm) {
        // Ensure marked_at is updated
        if (!frm.doc.marked_at) {
            frm.set_value('marked_at', frappe.datetime.now_datetime());
        }
    }
});

// Helper Functions

function add_custom_buttons(frm) {
    // View member profile
    frm.add_custom_button(__('View Member Profile'), function() {
        frappe.set_route('Form', 'Member', frm.doc.member_id);
    }, __('Actions'));
    
    // View all attendance for this member
    frm.add_custom_button(__('Member Attendance History'), function() {
        frappe.set_route('List', 'Church Attendance', {
            'member_id': frm.doc.member_id
        });
    }, __('Actions'));
    
    // View service instance if linked
    if (frm.doc.service_instance) {
        frm.add_custom_button(__('View Service Instance'), function() {
            frappe.set_route('Form', 'Service Instance', frm.doc.service_instance);
        }, __('Actions'));
    }
}

function apply_conditional_formatting(frm) {
    // Highlight visitor records
    if (frm.doc.is_visitor) {
        frm.dashboard.add_indicator(__('Visitor'), 'orange');
    }
    
    // Highlight if marked recently (within last hour)
    if (frm.doc.marked_at) {
        const marked_time = frappe.datetime.str_to_obj(frm.doc.marked_at);
        const now = frappe.datetime.now_datetime(true);
        const diff_minutes = frappe.datetime.get_diff(now, marked_time, 'minutes');
        
        if (diff_minutes <= 60) {
            frm.dashboard.add_indicator(__('Recently Marked'), 'green');
        }
    }
}

function set_service_instance_filter(frm) {
    // Filter service instances by service type and date
    frm.set_query('service_instance', function() {
        let filters = {};
        
        if (frm.doc.service_type) {
            filters.service_type = frm.doc.service_type;
        }
        
        if (frm.doc.service_date) {
            filters.service_date = frm.doc.service_date;
        }
        
        return {
            filters: filters
        };
    });
}

function validate_service_date(frm) {
    if (!frm.doc.service_date || !frm.doc.service_type) {
        return;
    }
    
    const service_date = frappe.datetime.str_to_obj(frm.doc.service_date);
    const day_of_week = service_date.getDay();
    
    // Validate Sunday services (day 0 = Sunday)
    if (frm.doc.service_type === 'Sunday Service' || frm.doc.service_type === 'Sunday School') {
        if (day_of_week !== 0) {
            frappe.msgprint({
                title: __('Invalid Date'),
                message: __('Sunday services must be on a Sunday. Please select a Sunday date.'),
                indicator: 'orange'
            });
        }
    }
}

function check_duplicate_attendance(frm) {
    if (!frm.doc.member_id || !frm.doc.service_date || !frm.doc.service_type) {
        return;
    }
    
    frappe.call({
        method: 'frappe.client.get_list',
        args: {
            doctype: 'Church Attendance',
            filters: {
                'member_id': frm.doc.member_id,
                'service_date': frm.doc.service_date,
                'service_type': frm.doc.service_type,
                'name': ['!=', frm.doc.name]
            },
            fields: ['name']
        },
        callback: function(r) {
            if (r.message && r.message.length > 0) {
                frappe.msgprint({
                    title: __('Duplicate Attendance'),
                    message: __('This member already has an attendance record for this service on this date: {0}', 
                        ['<a href="/app/church-attendance/' + r.message[0].name + '">' + r.message[0].name + '</a>']),
                    indicator: 'orange'
                });
            }
        }
    });
}

// List View Customization
frappe.listview_settings['Church Attendance'] = {
    add_fields: ['service_type', 'service_date', 'is_visitor', 'present'],
    
    get_indicator: function(doc) {
        if (doc.is_visitor) {
            return [__('Visitor'), 'orange', 'is_visitor,=,1'];
        } else if (doc.present) {
            return [__('Present'), 'green', 'present,=,1'];
        } else {
            return [__('Absent'), 'red', 'present,=,0'];
        }
    },
    
    formatters: {
        service_date: function(value) {
            return frappe.datetime.str_to_user(value);
        }
    },
    
    onload: function(listview) {
        // Add bulk actions
        listview.page.add_action_item(__('Mark as Present'), function() {
            bulk_update_attendance(listview, 'present', 1);
        });
        
        listview.page.add_action_item(__('Mark as Absent'), function() {
            bulk_update_attendance(listview, 'present', 0);
        });
    }
};

function bulk_update_attendance(listview, field, value) {
    const selected = listview.get_checked_items();
    
    if (selected.length === 0) {
        frappe.msgprint(__('Please select at least one record'));
        return;
    }
    
    frappe.confirm(
        __('Update {0} records?', [selected.length]),
        function() {
            frappe.call({
                method: 'church.church.doctype.church_attendance.church_attendance.bulk_update_attendance',
                args: {
                    attendance_names: selected.map(item => item.name),
                    field: field,
                    value: value
                },
                callback: function(r) {
                    if (!r.exc) {
                        frappe.msgprint(__('Updated {0} records successfully', [selected.length]));
                        listview.refresh();
                    }
                }
            });
        }
    );
}


