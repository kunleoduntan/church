// Copyright (c) 2026, kunle and contributors
// For license information, please see license.txt
/* eslint-disable */

// church/church/report/absenteeism_report/absenteeism_report.js

frappe.query_reports["Absenteeism Report"] = {

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
            fieldname: "min_absent_services",
            label: __("Min Absent Services"),
            fieldtype: "Int",
            default: 2
        },
        {
            fieldname: "risk_level",
            label: __("Risk Level"),
            fieldtype: "Select",
            options: "\n🔴 High\n🟡 Medium\n🟢 Low"
        }
    ],

    formatter: function(value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);
        if (!data) return value;

        // Risk level — colour badge
        if (column.fieldname === "risk_level") {
            if (data.risk_level && data.risk_level.includes("High")) {
                value = `<span style="background:#e74c3c;color:#fff;
                                       padding:3px 10px;border-radius:10px;
                                       font-weight:700;font-size:12px;">
                             🔴 High Risk
                         </span>`;
            } else if (data.risk_level && data.risk_level.includes("Medium")) {
                value = `<span style="background:#f39c12;color:#fff;
                                       padding:3px 10px;border-radius:10px;
                                       font-weight:700;font-size:12px;">
                             🟡 Medium
                         </span>`;
            } else {
                value = `<span style="background:#27ae60;color:#fff;
                                       padding:3px 10px;border-radius:10px;
                                       font-size:12px;">
                             🟢 Low
                         </span>`;
            }
        }

        // Trend
        if (column.fieldname === "trend") {
            if (data.trend && data.trend.includes("Improving"))
                value = `<span style="color:#27ae60;font-weight:700;">⬆️ Improving</span>`;
            else if (data.trend && data.trend.includes("Declining"))
                value = `<span style="color:#e74c3c;font-weight:700;">⬇️ Declining</span>`;
            else
                value = `<span style="color:#95a5a6;">➡️ Stable</span>`;
        }

        // Attendance % — progress bar
        if (column.fieldname === "attendance_pct") {
            const pct = parseFloat(data.attendance_pct) || 0;
            const col = pct >= 75 ? "#27ae60" : pct >= 50 ? "#f39c12" : "#e74c3c";
            value = `<div style="display:flex;align-items:center;gap:6px;">
                         <div style="flex:1;background:#ecf0f1;border-radius:4px;height:10px;min-width:80px;">
                             <div style="width:${pct}%;background:${col};
                                         height:10px;border-radius:4px;transition:width 0.3s;"></div>
                         </div>
                         <span style="font-size:11px;min-width:38px;color:${col};font-weight:600;">${pct}%</span>
                     </div>`;
        }

        // Consecutive absent — red when high
        if (column.fieldname === "consecutive_absent") {
            const n = parseInt(data.consecutive_absent) || 0;
            const col = n >= 4 ? "#e74c3c" : n >= 2 ? "#e67e22" : "#27ae60";
            value = `<strong style="color:${col};font-size:14px;">${n}</strong>`;
        }

        // Days absent — colour scale
        if (column.fieldname === "days_absent") {
            const d = parseInt(data.days_absent);
            if (d === 999) {
                value = `<span style="color:#95a5a6;font-style:italic;">Never seen</span>`;
            } else {
                const col = d > 60 ? "#e74c3c" : d > 30 ? "#e67e22" : "#27ae60";
                value = `<span style="color:${col};font-weight:600;">${d} days</span>`;
            }
        }

        // Last seen — red if too long ago
        if (column.fieldname === "last_seen") {
            if (!data.last_seen) {
                value = `<span style="color:#e74c3c;font-style:italic;">—</span>`;
            }
        }

        // Prev period % comparison
        if (column.fieldname === "prev_period_pct") {
            const curr = parseFloat(data.attendance_pct) || 0;
            const prev = parseFloat(data.prev_period_pct) || 0;
            const diff = curr - prev;
            const sign = diff > 0 ? "+" : "";
            const col  = diff > 0 ? "#27ae60" : diff < 0 ? "#e74c3c" : "#95a5a6";
            value = `<span style="color:#7f8c8d;">${prev}%</span>
                     <span style="color:${col};font-size:11px;margin-left:4px;">(${sign}${diff.toFixed(1)}%)</span>`;
        }

        return value;
    },

    onload: function(report) {
        // Quick filter buttons
        report.page.add_inner_button(__("🔴 High Risk Only"), function() {
            frappe.query_report.set_filter_value("risk_level", "🔴 High");
            frappe.query_report.refresh();
        });

        report.page.add_inner_button(__("📋 All Risk Levels"), function() {
            frappe.query_report.set_filter_value("risk_level", "");
            frappe.query_report.refresh();
        });

        report.page.add_inner_button(__("📅 Last 3 Months"), function() {
            frappe.query_report.set_filter_value("from_date", frappe.datetime.add_months(frappe.datetime.now_date(), -3));
            frappe.query_report.set_filter_value("to_date",   frappe.datetime.now_date());
            frappe.query_report.refresh();
        });

        report.page.add_inner_button(__("📅 Last 6 Months"), function() {
            frappe.query_report.set_filter_value("from_date", frappe.datetime.add_months(frappe.datetime.now_date(), -6));
            frappe.query_report.set_filter_value("to_date",   frappe.datetime.now_date());
            frappe.query_report.refresh();
        });
    }
};
