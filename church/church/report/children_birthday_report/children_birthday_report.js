// Copyright (c) 2026, kunle and contributors
// For license information, please see license.txt
/* eslint-disable */

// Copyright (c) 2026, Kunle and contributors
// For license information, please see license.txt

frappe.query_reports["Children Birthday Report"] = {
    "filters": [
        {
            "fieldname": "view_type",
            "label": __("View"),
            "fieldtype": "Select",
            "options": "All\nUpcoming 30 Days\nThis Month\nNext Month\nThis Quarter",
            "default": "Upcoming 30 Days",
            "reqd": 1
        },
        {
            "fieldname": "branch",
            "label": __("Branch"),
            "fieldtype": "Link",
            "options": "Branch"
        },
        {
            "fieldname": "class_name",
            "label": __("Class"),
            "fieldtype": "Link",
            "options": "Children Class"
        },
        {
            "fieldname": "age_group",
            "label": __("Age Group"),
            "fieldtype": "Select",
            "options": "\nAge 00 - 05\nAge 06 - 12"
        }
    ],
    
    "formatter": function(value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);
        
        // Highlight status with colors
        if (column.fieldname == "status") {
            if (data.status && data.status.includes("TODAY")) {
                value = `<span style="background: #10b981; color: white; padding: 4px 8px; border-radius: 4px; font-weight: bold;">${data.status}</span>`;
            } else if (data.status && data.status.includes("Tomorrow")) {
                value = `<span style="background: #f59e0b; color: white; padding: 4px 8px; border-radius: 4px; font-weight: bold;">${data.status}</span>`;
            } else if (data.status && data.status.includes("This Week")) {
                value = `<span style="background: #3b82f6; color: white; padding: 4px 8px; border-radius: 4px;">${data.status}</span>`;
            } else if (data.status && data.status.includes("This Month")) {
                value = `<span style="background: #8b5cf6; color: white; padding: 4px 8px; border-radius: 4px;">${data.status}</span>`;
            }
        }
        
        // Highlight days until
        if (column.fieldname == "days_until") {
            if (data.days_until == 0) {
                value = `<span style="color: #10b981; font-weight: bold; font-size: 14px;">🎂 ${value}</span>`;
            } else if (data.days_until <= 7) {
                value = `<span style="color: #f59e0b; font-weight: bold;">${value}</span>`;
            }
        }
        
        return value;
    },
    
    onload: function(report) {
        // Add action buttons
        report.page.add_inner_button(__('Send Birthday Wishes'), function() {
            send_birthday_wishes_batch(report);
        }, __('Actions'));
        
        report.page.add_inner_button(__('Export Birthday Calendar'), function() {
            export_birthday_calendar(report);
        }, __('Actions'));
        
        report.page.add_inner_button(__('Send Reminder to Teachers'), function() {
            send_teacher_reminders(report);
        }, __('Actions'));
    }
};

function send_birthday_wishes_batch(report) {
    const data = report.data;
    
    // Filter birthdays happening today
    const today_birthdays = data.filter(row => row.days_until === 0);
    
    if (today_birthdays.length === 0) {
        frappe.msgprint(__('No birthdays today'));
        return;
    }
    
    frappe.confirm(
        __(`Send birthday wishes to ${today_birthdays.length} children celebrating their birthday today?`),
        function() {
            frappe.call({
                method: 'church.church.report.children_birthday_report.children_birthday_report.send_batch_birthday_wishes',
                args: {
                    children: today_birthdays.map(row => row.child_id)
                },
                freeze: true,
                freeze_message: __('🎂 Sending birthday wishes...'),
                callback: function(r) {
                    if (r.message) {
                        frappe.msgprint({
                            title: __('Birthday Wishes Sent'),
                            message: __(`Successfully sent ${r.message.sent_count} birthday wishes`),
                            indicator: 'green'
                        });
                    }
                }
            });
        }
    );
}

function export_birthday_calendar(report) {
    frappe.call({
        method: 'church.church.report.children_birthday_report.children_birthday_report.export_birthday_calendar',
        args: {
            filters: report.get_filter_values()
        },
        freeze: true,
        freeze_message: __('📅 Generating birthday calendar...'),
        callback: function(r) {
            if (r.message && r.message.file_url) {
                window.open(r.message.file_url, '_blank');
                frappe.show_alert({
                    message: __('✅ Birthday calendar exported successfully!'),
                    indicator: 'green'
                }, 5);
            }
        }
    });
}

function send_teacher_reminders(report) {
    frappe.call({
        method: 'church.church.report.children_birthday_report.children_birthday_report.send_teacher_birthday_reminders',
        args: {
            filters: report.get_filter_values()
        },
        freeze: true,
        freeze_message: __('📧 Sending reminders...'),
        callback: function(r) {
            if (r.message) {
                frappe.msgprint({
                    title: __('Reminders Sent'),
                    message: __(`Successfully sent ${r.message.sent_count} reminder emails to teachers`),
                    indicator: 'green'
                });
            }
        }
    });
}