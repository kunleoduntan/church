// Copyright (c) 2026, kunle and contributors
// For license information, please see license.txt
/* eslint-disable */

// church/church/report/visitor_register/visitor_register.js

frappe.query_reports["Visitor Register"] = {

    filters: [
        {
            fieldname: "from_date",
            label: __("From Date"),
            fieldtype: "Date",
            default: frappe.datetime.add_months(frappe.datetime.now_date(), -1)
        },
        {
            fieldname: "to_date",
            label: __("To Date"),
            fieldtype: "Date",
            default: frappe.datetime.now_date()
        },
        {
            fieldname: "branch",
            label: __("Branch"),
            fieldtype: "Link",
            options: "Branch"
        },
        {
            fieldname: "conversion_status",
            label: __("Conversion Status"),
            fieldtype: "Select",
            options: "\nNew Visitor\nIn Follow-up\nConverted to Member\nActive Member\nLost Contact\nNot Interested"
        },
        {
            fieldname: "visit_type",
            label: __("Visit Type"),
            fieldtype: "Select",
            options: "\nFirst Time Visitor\nReturn Visitor\nGuest from Another Church\nRelocating Member\nOther"
        },
        {
            fieldname: "follow_up_coordinator",
            label: __("Follow-Up Coordinator"),
            fieldtype: "Link",
            options: "Member"
        }
    ],

    formatter: function(value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);
        if (!data) return value;

        // Conversion status badge
        if (column.fieldname === "conversion_status") {
            const styles = {
                "New Visitor":          { bg:"#3498db",  icon:"👋" },
                "In Follow-up":         { bg:"#f39c12",  icon:"🔄" },
                "Converted to Member":  { bg:"#27ae60",  icon:"✅" },
                "Active Member":        { bg:"#27ae60",  icon:"⭐" },
                "Lost Contact":         { bg:"#95a5a6",  icon:"❌" },
                "Not Interested":       { bg:"#e74c3c",  icon:"🚫" }
            };
            const s = styles[data.conversion_status] || { bg:"#95a5a6", icon:"" };
            value = `<span style="background:${s.bg};color:#fff;
                                   padding:3px 8px;border-radius:10px;font-size:11px;">
                         ${s.icon} ${data.conversion_status || ""}
                     </span>`;
        }

        // Visit type
        if (column.fieldname === "visit_type") {
            const colours = {
                "First Time Visitor":        "#e74c3c",
                "Return Visitor":            "#f39c12",
                "Guest from Another Church": "#3498db",
                "Relocating Member":         "#27ae60"
            };
            const col = colours[data.visit_type] || "#95a5a6";
            value = `<span style="color:${col};font-weight:600;font-size:12px;">
                         ${data.visit_type || ""}
                     </span>`;
        }

        // Follow-up count — badge when > 0
        if (column.fieldname === "follow_up_count") {
            const n = parseInt(data.follow_up_count) || 0;
            if (n > 0) {
                value = `<span style="background:#667eea;color:#fff;
                                       padding:2px 8px;border-radius:10px;font-size:11px;">
                             ${n} follow-up${n > 1 ? "s" : ""}
                         </span>`;
            } else {
                value = `<span style="color:#e74c3c;font-size:11px;">None yet</span>`;
            }
        }

        // Next follow-up — red if overdue
        if (column.fieldname === "next_follow_up_date" && data.next_follow_up_date) {
            const today = frappe.datetime.now_date();
            if (data.next_follow_up_date < today) {
                value = `<span style="color:#e74c3c;font-weight:700;">
                             ⚠️ ${frappe.format(data.next_follow_up_date, {fieldtype:"Date"})}
                         </span>`;
            }
        }

        // Membership / baptism interest checkboxes — styled
        if (column.fieldname === "interested_in_membership") {
            value = data.interested_in_membership
                ? `<span style="color:#27ae60;font-weight:700;">✅ Yes</span>`
                : `<span style="color:#95a5a6;">—</span>`;
        }
        if (column.fieldname === "interested_in_baptism") {
            value = data.interested_in_baptism
                ? `<span style="color:#3498db;font-weight:700;">✅ Yes</span>`
                : `<span style="color:#95a5a6;">—</span>`;
        }

        return value;
    },

    onload: function(report) {
        // Quick status filters
        report.page.add_inner_button(__("👋 New Visitors"), function() {
            frappe.query_report.set_filter_value("conversion_status", "New Visitor");
            frappe.query_report.refresh();
        });

        report.page.add_inner_button(__("🔄 In Follow-Up"), function() {
            frappe.query_report.set_filter_value("conversion_status", "In Follow-up");
            frappe.query_report.refresh();
        });

        report.page.add_inner_button(__("✅ Converted"), function() {
            frappe.query_report.set_filter_value("conversion_status", "Converted to Member");
            frappe.query_report.refresh();
        });

        report.page.add_inner_button(__("❌ Lost Contact"), function() {
            frappe.query_report.set_filter_value("conversion_status", "Lost Contact");
            frappe.query_report.refresh();
        });
    }
};
