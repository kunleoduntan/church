// Copyright (c) 2026, kunle and contributors
// For license information, please see license.txt
/* eslint-disable */

// Copyright (c) 2026, Church Management
// License: MIT
//
// church/church/report/attendance_analysis_report/attendance_analysis_report.js

frappe.query_reports["Attendance Analysis Report"] = {
    "filters": [
        {
            "fieldname": "view_type",
            "label": __("View Type"),
            "fieldtype": "Select",
            "options": [
                "Detailed",
                "Summary",
                "Weekly",
                "Monthly",
                "Demographics",
                "Service Type Analysis",
                "Leader Dashboard"
            ],
            "default": "Detailed",
            "reqd": 1,
            "on_change": function(query_report) {
                // Update chart and columns when view type changes
                query_report.refresh();
            }
        },
        {
            "fieldname": "from_date",
            "label": __("From Date"),
            "fieldtype": "Date",
            "default": frappe.datetime.add_months(frappe.datetime.get_today(), -1),
            "reqd": 1
        },
        {
            "fieldname": "to_date",
            "label": __("To Date"),
            "fieldtype": "Date",
            "default": frappe.datetime.get_today(),
            "reqd": 1
        },
        {
            "fieldname": "branch",
            "label": __("Branch"),
            "fieldtype": "MultiSelectList",
            "options": "Branch",
            "get_data": function(txt) {
                return frappe.db.get_link_options("Branch", txt);
            }
        },
        {
            "fieldname": "service_type",
            "label": __("Service Type"),
            "fieldtype": "MultiSelectList",
            "options": "Service Type",
            "get_data": function(txt) {
                return frappe.call({
                    method: "church.church.report.attendance_analysis_report.attendance_analysis_report.get_filter_options",
                    callback: function(r) {
                        if (r.message && r.message.service_types) {
                            return r.message.service_types.map(st => ({ value: st, label: st }));
                        }
                        return [];
                    }
                });
            }
        },
        {
            "fieldname": "demographic_group",
            "label": __("Demographic Group"),
            "fieldtype": "Select",
            "options": [
                "",
                "Men",
                "Women",
                "Youth",
                "Teenagers",
                "Children",
                "Seniors"
            ]
        },
        {
            "fieldname": "present",
            "label": __("Attendance Status"),
            "fieldtype": "Select",
            "options": [
                {"value": "", "label": __("All")},
                {"value": "1", "label": __("Present Only")},
                {"value": "0", "label": __("Absent Only")}
            ]
        },
        {
            "fieldname": "is_visitor",
            "label": __("Visitor Status"),
            "fieldtype": "Select",
            "options": [
                {"value": "", "label": __("All")},
                {"value": "1", "label": __("Visitors Only")},
                {"value": "0", "label": __("Members Only")}
            ]
        },
        {
            "fieldname": "sunday_school_class",
            "label": __("Sunday School Class"),
            "fieldtype": "Data"
        },
        {
            "fieldname": "member_id",
            "label": __("Member"),
            "fieldtype": "Link",
            "options": "Member"
        },
        {
            "fieldname": "checkin_method",
            "label": __("Check-in Method"),
            "fieldtype": "Select",
            "options": [
                "",
                "QR Code",
                "Manual",
                "Bulk Upload",
                "Mobile App",
                "Kiosk"
            ]
        },
        {
            "fieldname": "min_attendance",
            "label": __("Minimum Attendance Count"),
            "fieldtype": "Int",
            "description": __("Filter members with at least this many attendances")
        },
        {
            "fieldname": "show_chart",
            "label": __("Show Chart"),
            "fieldtype": "Check",
            "default": 1
        },
        {
            "fieldname": "chart_type",
            "label": __("Chart Type"),
            "fieldtype": "Select",
            "options": [
                "Bar",
                "Line",
                "Pie",
                "Percentage"
            ],
            "default": "Bar",
            "depends_on": "eval:doc.show_chart"
        }
    ],

    "formatter": function(value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);

        // Add color coding for attendance rates
        if (column.fieldname === "attendance_rate" || column.fieldname === "retention_rate") {
            if (value >= 80) {
                value = `<span style="color: #10b981; font-weight: bold;">${value}%</span>`;
            } else if (value >= 50) {
                value = `<span style="color: #f59e0b; font-weight: bold;">${value}%</span>`;
            } else if (value > 0) {
                value = `<span style="color: #ef4444; font-weight: bold;">${value}%</span>`;
            }
        }

        // Color coding for trend direction
        if (column.fieldname === "trend_direction") {
            if (value && value.includes("↑")) {
                value = `<span style="color: #10b981; font-weight: bold;">${value}</span>`;
            } else if (value && value.includes("↓")) {
                value = `<span style="color: #ef4444; font-weight: bold;">${value}</span>`;
            }
        }

        // Highlight rows with high follow-up needs
        if (column.fieldname === "need_followup" && value > 10) {
            value = `<span style="color: #ef4444; font-weight: bold;">${value}</span>`;
        }

        // Add icons for certain fields
        if (column.fieldname === "checkin_method") {
            if (value === "QR Code") {
                value = `<i class="fa fa-qrcode" style="margin-right: 5px;"></i> ${value}`;
            } else if (value === "Manual") {
                value = `<i class="fa fa-pencil" style="margin-right: 5px;"></i> ${value}`;
            }
        }

        return value;
    },

    "onload": function(report) {
        // Load dynamic filter options
        frappe.call({
            method: "church.church.report.attendance_analysis_report.attendance_analysis_report.get_filter_options",
            callback: function(r) {
                if (r.message) {
                    report.page.fields_dict.sunday_school_class.df.options = r.message.sunday_school_classes;
                    report.page.fields_dict.sunday_school_class.refresh();
                    
                    // You can populate other filter options here
                }
            }
        });
        
        // Add custom buttons
        report.page.add_inner_button(__("Export to Excel"), function() {
            frappe.call({
                method: "church.church.report.attendance_analysis_report.attendance_analysis_report.export_to_excel",
                args: {
                    filters: report.get_values()
                },
                callback: function(r) {
                    // Handle file download
                    if (r.message) {
                        frappe.msgprint(__("Export started. File will download shortly."));
                    }
                }
            });
        });
        
        report.page.add_inner_button(__("Send to Leaders"), function() {
            show_send_report_dialog(report);
        });
        
        report.page.add_inner_button(__("Quick Stats"), function() {
            show_quick_stats_dialog(report);
        });
    },

    "tree": false,
    "name_field": "member_id",
    "parent_field": "branch",
    "initial_depth": 0
};

// Helper function to show send report dialog
function show_send_report_dialog(report) {
    let filters = report.get_values();
    
    let dialog = new frappe.ui.Dialog({
        title: __("Send Report to Leaders"),
        fields: [
            {
                fieldname: "recipients",
                label: __("Recipients"),
                fieldtype: "MultiSelectList",
                options: "Member",
                get_data: function(txt) {
                    return frappe.db.get_link_options("Member", txt, {
                        member_status: "Active",
                        is_a_pastor: 1
                    });
                },
                reqd: 1
            },
            {
                fieldname: "message",
                label: __("Additional Message"),
                fieldtype: "Text",
                description: __("Optional message to include with the report")
            },
            {
                fieldname: "include_chart",
                label: __("Include Chart"),
                fieldtype: "Check",
                default: 1
            },
            {
                fieldname: "send_as_attachment",
                label: __("Send as Excel Attachment"),
                fieldtype: "Check",
                default: 1
            }
        ],
        primary_action_label: __("Send Report"),
        primary_action: function(values) {
            dialog.hide();
            frappe.show_alert({
                message: __("Sending report to {0} recipients...", [values.recipients.length]),
                indicator: "blue"
            });
            
            frappe.call({
                method: "church.church.doctype.church_attendance.church_attendance.send_leader_report",
                args: {
                    filters: filters,
                    recipients: values.recipients,
                    message: values.message,
                    include_chart: values.include_chart,
                    send_as_attachment: values.send_as_attachment
                },
                callback: function(r) {
                    if (r.message && r.message.success) {
                        frappe.show_alert({
                            message: __("Report sent successfully"),
                            indicator: "green"
                        });
                    } else {
                        frappe.show_alert({
                            message: __("Failed to send report"),
                            indicator: "red"
                        });
                    }
                }
            });
        }
    });
    
    dialog.show();
}

// Helper function to show quick stats dialog
function show_quick_stats_dialog(report) {
    let filters = report.get_values();
    
    frappe.call({
        method: "frappe.client.get_list",
        args: {
            doctype: "Church Attendance",
            filters: {
                service_date: ["between", [filters.from_date, filters.to_date]],
                docstatus: 1
            },
            fields: ["service_type", "present"],
            limit_page_length: 0
        },
        callback: function(r) {
            if (r.message) {
                let data = r.message;
                let total = data.length;
                let present = data.filter(d => d.present).length;
                let absent = total - present;
                
                // Group by service type
                let service_types = {};
                data.forEach(d => {
                    if (!service_types[d.service_type]) {
                        service_types[d.service_type] = { total: 0, present: 0 };
                    }
                    service_types[d.service_type].total++;
                    if (d.present) {
                        service_types[d.service_type].present++;
                    }
                });
                
                let html = `
                    <div class="row" style="margin-bottom: 20px;">
                        <div class="col-xs-4 text-center">
                            <h3 style="color: #1a3f90;">${total}</h3>
                            <p>Total Records</p>
                        </div>
                        <div class="col-xs-4 text-center">
                            <h3 style="color: #10b981;">${present}</h3>
                            <p>Present</p>
                        </div>
                        <div class="col-xs-4 text-center">
                            <h3 style="color: #ef4444;">${absent}</h3>
                            <p>Absent</p>
                        </div>
                    </div>
                    <h5>Attendance Rate: ${((present / total) * 100).toFixed(1)}%</h5>
                    <hr>
                    <h5>Breakdown by Service Type:</h5>
                    <table class="table table-bordered">
                        <thead>
                            <tr>
                                <th>Service Type</th>
                                <th>Total</th>
                                <th>Present</th>
                                <th>Rate</th>
                            </tr>
                        </thead>
                        <tbody>
                `;
                
                for (let [type, stats] of Object.entries(service_types)) {
                    let rate = ((stats.present / stats.total) * 100).toFixed(1);
                    html += `
                        <tr>
                            <td>${type}</td>
                            <td>${stats.total}</td>
                            <td>${stats.present}</td>
                            <td>${rate}%</td>
                        </tr>
                    `;
                }
                
                html += `</tbody></table>`;
                
                frappe.msgprint({
                    title: __("Quick Statistics"),
                    message: html,
                    wide: true
                });
            }
        }
    });
}

// Add custom initialization for multi-select filters
frappe.query_reports["Attendance Analysis Report"].refresh = function(report) {
    // Ensure multi-select filters work properly
    if (report.page.fields_dict.branch) {
        report.page.fields_dict.branch.df.get_data = function() {
            return frappe.db.get_link_options("Branch");
        };
        report.page.fields_dict.branch.refresh();
    }
    
    if (report.page.fields_dict.service_type) {
        report.page.fields_dict.service_type.df.get_data = function(txt) {
            return frappe.call({
                method: "church.church.report.attendance_analysis_report.attendance_analysis_report.get_filter_options",
                callback: function(r) {
                    if (r.message && r.message.service_types) {
                        return r.message.service_types.map(st => ({ value: st, label: st }));
                    }
                    return [];
                }
            });
        };
        report.page.fields_dict.service_type.refresh();
    }
};