// Copyright (c) 2026, kunle and contributors
// For license information, please see license.txt
/* eslint-disable */



frappe.query_reports["Children Class Analytics"] = {
    "filters": [
        {
            "fieldname": "branch",
            "label": __("Branch"),
            "fieldtype": "Link",
            "options": "Branch",
            "width": 100
        },
        {
            "fieldname": "age_group",
            "label": __("Age Group"),
            "fieldtype": "Select",
            "options": "\nAge 00 - 05\nAge 06 - 12",
            "width": 100
        },
        {
            "fieldname": "teacher",
            "label": __("Teacher"),
            "fieldtype": "Link",
            "options": "Member",
            "width": 100
        },
        {
            "fieldname": "class_name",
            "label": __("Class Name"),
            "fieldtype": "Link",
            "options": "Children Class",
            "width": 100
        }
    ],
    
    "formatter": function(value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);
        
        // Highlight ready for promotion
        if (column.fieldname == "ready_for_promotion" && data.ready_for_promotion > 0) {
            value = `<span style="color: #f59e0b; font-weight: bold;">${value}</span>`;
        }
        
        // Highlight birthdays this month
        if (column.fieldname == "birthdays_this_month" && data.birthdays_this_month > 0) {
            value = `<span style="color: #10b981; font-weight: bold;">🎂 ${value}</span>`;
        }
        
        // Highlight birthdays next month
        if (column.fieldname == "birthdays_next_month" && data.birthdays_next_month > 0) {
            value = `<span style="color: #f59e0b; font-weight: bold;">🎈 ${value}</span>`;
        }
        
        return value;
    },
    
    onload: function(report) {
        // Add custom buttons to report
        report.page.add_inner_button(__('Export All Classes'), function() {
            export_all_classes_report(report);
        }, __('Actions'));
        
        report.page.add_inner_button(__('Send Birthday Reminders'), function() {
            send_birthday_reminders(report);
        }, __('Actions'));
        
        report.page.add_inner_button(__('Process All Promotions'), function() {
            process_all_promotions(report);
        }, __('Actions'));
    }
};

function export_all_classes_report(report) {
    frappe.call({
        method: 'church.church.report.children_class_analytics.children_class_analytics.export_combined_report',
        args: {
            filters: report.get_filter_values()
        },
        freeze: true,
        freeze_message: __('📊 Generating combined Excel report...'),
        callback: function(r) {
            if (r.message && r.message.file_url) {
                window.open(r.message.file_url, '_blank');
                frappe.show_alert({
                    message: __('✅ Combined report generated successfully!'),
                    indicator: 'green'
                }, 5);
            }
        }
    });
}

function send_birthday_reminders(report) {
    frappe.confirm(
        __('Send birthday reminder emails to teachers for upcoming birthdays?'),
        function() {
            frappe.call({
                method: 'church.church.report.children_class_analytics.children_class_analytics.send_birthday_reminders',
                args: {
                    filters: report.get_filter_values()
                },
                freeze: true,
                freeze_message: __('📧 Sending birthday reminders...'),
                callback: function(r) {
                    if (r.message) {
                        frappe.msgprint({
                            title: __('Birthday Reminders Sent'),
                            message: __(`Successfully sent ${r.message.sent_count} reminder emails`),
                            indicator: 'green'
                        });
                    }
                }
            });
        }
    );
}

function process_all_promotions(report) {
    frappe.confirm(
        __('This will process promotions for ALL children ready for promotion. Continue?'),
        function() {
            frappe.call({
                method: 'church.church.report.children_class_analytics.children_class_analytics.process_all_promotions',
                args: {
                    filters: report.get_filter_values()
                },
                freeze: true,
                freeze_message: __('⏳ Processing promotions...'),
                callback: function(r) {
                    if (r.message) {
                        frappe.msgprint({
                            title: __('Promotions Processed'),
                            message: __(`Successfully promoted ${r.message.total_promoted} children from ${r.message.classes_processed} classes`),
                            indicator: 'green'
                        });
                        report.refresh();
                    }
                }
            });
        }
    );
}