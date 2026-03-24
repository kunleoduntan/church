// Copyright (c) 2026, kunle and contributors
// For license information, please see license.txt
/* eslint-disable */

// church/church/report/member_growth/member_growth.js

frappe.query_reports["Member Growth"] = {

    filters: [
        {
            fieldname: "from_date",
            label: __("From Date"),
            fieldtype: "Date",
            reqd: 1,
            default: frappe.datetime.add_months(frappe.datetime.now_date(), -12)
        },
        {
            fieldname: "to_date",
            label: __("To Date"),
            fieldtype: "Date",
            reqd: 1,
            default: frappe.datetime.now_date()
        },
        {
            fieldname: "period",
            label: __("Group By"),
            fieldtype: "Select",
            options: "Monthly\nQuarterly\nYearly",
            default: "Monthly"
        },
        {
            fieldname: "branch",
            label: __("Branch"),
            fieldtype: "Link",
            options: "Branch"
        }
    ],

    formatter: function(value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);
        if (!data) return value;

        // Highlight the period column
        if (column.fieldname === "period") {
            value = `<strong style="color:#2E75B6;">${data.period || ""}</strong>`;
        }

        // New members — colour by size
        if (column.fieldname === "new_members") {
            const n = parseInt(data.new_members) || 0;
            const col = n >= 20 ? "#27ae60" : n >= 10 ? "#f39c12" : "#2c3e50";
            value = `<span style="color:${col};font-weight:600;">${n}</span>`;
        }

        // Cumulative — always bold blue
        if (column.fieldname === "cumulative") {
            value = `<strong style="color:#2980b9;">${data.cumulative || 0}</strong>`;
        }

        // Gender split indicator
        if (column.fieldname === "male") {
            value = `<span style="color:#3498db;">${data.male || 0}</span>`;
        }
        if (column.fieldname === "female") {
            value = `<span style="color:#e91e8c;">${data.female || 0}</span>`;
        }

        return value;
    },

    onload: function(report) {
        // Auto-refresh when period changes
        report.page.add_inner_button(__("🔄 Refresh"), function() {
            report.refresh();
        });
    }
};
