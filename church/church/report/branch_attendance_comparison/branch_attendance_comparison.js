// Copyright (c) 2026, kunle and contributors
// For license information, please see license.txt
/* eslint-disable */

// church/church/report/branch_attendance_comparison/branch_attendance_comparison.js

frappe.query_reports["Branch Attendance Comparison"] = {

    filters: [
        {
            fieldname: "from_date",
            label: __("From Date"),
            fieldtype: "Date",
            reqd: 1,
            default: frappe.datetime.add_months(frappe.datetime.now_date(), -3)
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
            label: __("Branch (leave blank for all)"),
            fieldtype: "Link",
            options: "Branch"
        }
    ],

    formatter: function(value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);
        if (!data) return value;

        // Branch — coloured label
        if (column.fieldname === "branch") {
            const colours = [
                "#3498db","#27ae60","#e74c3c","#f39c12",
                "#9b59b6","#1abc9c","#e67e22","#2980b9"
            ];
            // Consistent colour per branch name
            let hash = 0;
            for (const c of (data.branch || "")) hash = c.charCodeAt(0) + ((hash << 5) - hash);
            const bg = colours[Math.abs(hash) % colours.length];
            value = `<span style="background:${bg};color:#fff;
                                   padding:2px 10px;border-radius:10px;
                                   font-size:12px;font-weight:600;">
                         ${data.branch || ""}
                     </span>`;
        }

        // Total attendance — bold
        if (column.fieldname === "total_att") {
            const n = parseInt(data.total_att) || 0;
            value = `<strong style="color:#2c3e50;font-size:13px;">${n.toLocaleString()}</strong>`;
        }

        // Avg per service — colour by performance
        if (column.fieldname === "avg_att") {
            const n = parseFloat(data.avg_att) || 0;
            const col = n >= 100 ? "#27ae60" : n >= 50 ? "#f39c12" : "#e74c3c";
            value = `<span style="color:${col};font-weight:600;">${n}</span>`;
        }

        // QR % — progress bar
        if (column.fieldname === "qr_pct") {
            const pct = parseFloat(data.qr_pct) || 0;
            value = `<div style="display:flex;align-items:center;gap:4px;">
                         <div style="flex:1;background:#ecf0f1;border-radius:3px;height:8px;min-width:50px;">
                             <div style="width:${pct}%;background:#3498db;height:8px;border-radius:3px;"></div>
                         </div>
                         <span style="font-size:11px;color:#3498db;">${pct}%</span>
                     </div>`;
        }

        // First timers — orange
        if (column.fieldname === "first_timers") {
            const n = parseInt(data.first_timers) || 0;
            if (n > 0) value = `<span style="color:#e67e22;font-weight:600;">👋 ${n}</span>`;
        }

        // Period — bold blue
        if (column.fieldname === "period") {
            value = `<strong style="color:#2E75B6;">${data.period || ""}</strong>`;
        }

        return value;
    },

    onload: function(report) {
        report.page.add_inner_button(__("📅 Last Quarter"), function() {
            frappe.query_report.set_filter_value("from_date", frappe.datetime.add_months(frappe.datetime.now_date(), -3));
            frappe.query_report.set_filter_value("to_date",   frappe.datetime.now_date());
            frappe.query_report.set_filter_value("period",    "Monthly");
            frappe.query_report.refresh();
        });

        report.page.add_inner_button(__("📅 This Year"), function() {
            frappe.query_report.set_filter_value("from_date", new Date().getFullYear() + "-01-01");
            frappe.query_report.set_filter_value("to_date",   frappe.datetime.now_date());
            frappe.query_report.set_filter_value("period",    "Monthly");
            frappe.query_report.refresh();
        });
    }
};
