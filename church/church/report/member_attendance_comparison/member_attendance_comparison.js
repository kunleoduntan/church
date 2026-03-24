// Copyright (c) 2026, kunle and contributors
// For license information, please see license.txt
/* eslint-disable */

// church/church/report/member_attendance_comparison/member_attendance_comparison.js

frappe.query_reports["Member Attendance Comparison"] = {

    filters: [
        {
            fieldname: "period1_from",
            label: __("Period 1 — From"),
            fieldtype: "Date",
            reqd: 1,
            default: frappe.datetime.add_months(frappe.datetime.now_date(), -2)
        },
        {
            fieldname: "period1_to",
            label: __("Period 1 — To"),
            fieldtype: "Date",
            reqd: 1,
            default: frappe.datetime.add_months(frappe.datetime.now_date(), -1)
        },
        {
            fieldname: "period2_from",
            label: __("Period 2 — From"),
            fieldtype: "Date",
            reqd: 1,
            default: frappe.datetime.add_months(frappe.datetime.now_date(), -1)
        },
        {
            fieldname: "period2_to",
            label: __("Period 2 — To"),
            fieldtype: "Date",
            reqd: 1,
            default: frappe.datetime.now_date()
        },
        {
            fieldname: "branch",
            label: __("Branch"),
            fieldtype: "Link",
            options: "Branch"
        },
        {
            fieldname: "demographic_group",
            label: __("Demographic Group"),
            fieldtype: "Data"
        },
        {
            fieldname: "min_attendance",
            label: __("Min Attendance (either period)"),
            fieldtype: "Int",
            default: 0
        }
    ],

    // Validate period2 is after period1
    onload: function(report) {
        report.page.add_inner_button(__("⬆️ Most Improved"), function() {
            // Already sorted by change desc — just refresh
            frappe.query_report.refresh();
        });

        report.page.add_inner_button(__("⬇️ Most Declined"), function() {
            // Client-side sort by change ascending
            const data = frappe.query_report.data;
            if (!data) return;
            data.sort((a, b) => a.change - b.change);
            frappe.query_report.datatable.refresh(data);
        });

        // Validate dates on filter change
        ["period1_from","period1_to","period2_from","period2_to"].forEach(f => {
            const filter = report.get_filter(f);
            if (filter) {
                filter.$input.on("change", () => _validate_periods());
            }
        });
    },

    formatter: function(value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);
        if (!data) return value;

        // Trend indicator
        if (column.fieldname === "trend") {
            if      (data.trend && data.trend.includes("Up"))   value = `<span style="color:#27ae60;font-weight:700;font-size:14px;">⬆️ Improving</span>`;
            else if (data.trend && data.trend.includes("Down")) value = `<span style="color:#e74c3c;font-weight:700;font-size:14px;">⬇️ Declining</span>`;
            else                                                  value = `<span style="color:#95a5a6;font-size:14px;">➡️ Stable</span>`;
        }

        // Change column — colour + sign
        if (column.fieldname === "change") {
            const n = parseInt(data.change);
            if (n > 0)      value = `<span style="color:#27ae60;font-weight:700;">+${n}</span>`;
            else if (n < 0) value = `<span style="color:#e74c3c;font-weight:700;">${n}</span>`;
            else             value = `<span style="color:#95a5a6;">0</span>`;
        }

        // Change % — same colour coding
        if (column.fieldname === "change_pct") {
            const n = parseFloat(data.change_pct);
            const sign = n > 0 ? "+" : "";
            const col  = n > 0 ? "#27ae60" : n < 0 ? "#e74c3c" : "#95a5a6";
            value = `<span style="color:${col};font-weight:600;">${sign}${n}%</span>`;
        }

        // Period 1 — grey (old)
        if (column.fieldname === "period1") {
            value = `<span style="color:#7f8c8d;">${data.period1 || 0}</span>`;
        }

        // Period 2 — bold (current)
        if (column.fieldname === "period2") {
            const col = (data.period2 || 0) >= (data.period1 || 0) ? "#27ae60" : "#e74c3c";
            value = `<strong style="color:${col};">${data.period2 || 0}</strong>`;
        }

        return value;
    }
};

function _validate_periods() {
    const p1f = frappe.query_report.get_filter_value("period1_from");
    const p1t = frappe.query_report.get_filter_value("period1_to");
    const p2f = frappe.query_report.get_filter_value("period2_from");
    const p2t = frappe.query_report.get_filter_value("period2_to");

    if (p1f && p1t && p1f > p1t) {
        frappe.show_alert({ message: __("Period 1: From date must be before To date"), indicator: "red" }, 4);
    }
    if (p2f && p2t && p2f > p2t) {
        frappe.show_alert({ message: __("Period 2: From date must be before To date"), indicator: "red" }, 4);
    }
}
