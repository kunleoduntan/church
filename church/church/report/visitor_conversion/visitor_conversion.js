// Copyright (c) 2026, kunle and contributors
// For license information, please see license.txt
/* eslint-disable */

// church/church/report/visitor_conversion/visitor_conversion.js

frappe.query_reports["Visitor Conversion"] = {

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

        // Period — bold blue
        if (column.fieldname === "period") {
            value = `<strong style="color:#2E75B6;">${data.period || ""}</strong>`;
        }

        // Total visitors — bold
        if (column.fieldname === "total_visitors") {
            value = `<strong>${data.total_visitors || 0}</strong>`;
        }

        // Converted — green
        if (column.fieldname === "converted") {
            const n = parseInt(data.converted) || 0;
            value = n > 0
                ? `<span style="color:#27ae60;font-weight:700;">✅ ${n}</span>`
                : `<span style="color:#95a5a6;">0</span>`;
        }

        // Lost contact — red
        if (column.fieldname === "lost_contact") {
            const n = parseInt(data.lost_contact) || 0;
            value = n > 0
                ? `<span style="color:#e74c3c;">❌ ${n}</span>`
                : `<span style="color:#95a5a6;">0</span>`;
        }

        // In follow-up — orange
        if (column.fieldname === "in_followup") {
            const n = parseInt(data.in_followup) || 0;
            value = n > 0
                ? `<span style="color:#e67e22;font-weight:600;">🔄 ${n}</span>`
                : `<span style="color:#95a5a6;">0</span>`;
        }

        // Conversion rate — progress bar + %
        if (column.fieldname === "conversion_rate") {
            const pct = parseFloat(data.conversion_rate) || 0;
            const col = pct >= 20 ? "#27ae60" : pct >= 10 ? "#f39c12" : "#e74c3c";
            value = `<div style="display:flex;align-items:center;gap:6px;">
                         <div style="flex:1;background:#ecf0f1;border-radius:4px;
                                     height:10px;min-width:60px;">
                             <div style="width:${Math.min(pct * 3, 100)}%;background:${col};
                                         height:10px;border-radius:4px;"></div>
                         </div>
                         <span style="color:${col};font-weight:700;font-size:12px;
                                      min-width:40px;">${pct}%</span>
                     </div>`;
        }

        return value;
    },

    onload: function(report) {
        report.page.add_inner_button(__("📅 Last 12 Months"), function() {
            frappe.query_report.set_filter_value("from_date", frappe.datetime.add_months(frappe.datetime.now_date(), -12));
            frappe.query_report.set_filter_value("to_date",   frappe.datetime.now_date());
            frappe.query_report.set_filter_value("period",    "Monthly");
            frappe.query_report.refresh();
        });

        report.page.add_inner_button(__("📅 This Year"), function() {
            frappe.query_report.set_filter_value("from_date", new Date().getFullYear() + "-01-01");
            frappe.query_report.set_filter_value("to_date",   frappe.datetime.now_date());
            frappe.query_report.set_filter_value("period",    "Quarterly");
            frappe.query_report.refresh();
        });
    }
};
