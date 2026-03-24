// Copyright (c) 2026, kunle and contributors
// For license information, please see license.txt
/* eslint-disable */

// church/church/report/department_strength/department_strength.js

frappe.query_reports["Department Strength"] = {

    filters: [
        {
            fieldname: "department",
            label: __("Department"),
            fieldtype: "Link",
            options: "Church Department"
        },
        {
            fieldname: "show_members",
            label: __("Show Member Detail"),
            fieldtype: "Check",
            default: 0,
            description: "Tick to expand each department and show individual members"
        }
    ],

    formatter: function(value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);
        if (!data) return value;

        const is_dept_row   = !!data.total_members;   // department summary row
        const is_member_row = !!data.member_id;       // individual member row

        // Department name — bold, coloured header row
        if (column.fieldname === "department") {
            if (is_dept_row && data.department) {
                value = `<strong style="color:#1F3864;font-size:13px;">
                             🏢 ${data.department}
                         </strong>`;
            } else if (is_member_row) {
                value = "";  // no dept name on member rows
            }
        }

        // Active / inactive count
        if (column.fieldname === "active_members" && is_dept_row) {
            const n = parseInt(data.active_members) || 0;
            value = `<span style="color:#27ae60;font-weight:700;">${n}</span>`;
        }
        if (column.fieldname === "inactive_members" && is_dept_row) {
            const n = parseInt(data.inactive_members) || 0;
            value = n > 0
                ? `<span style="color:#e74c3c;">${n}</span>`
                : `<span style="color:#95a5a6;">0</span>`;
        }

        // Total members — large bold
        if (column.fieldname === "total_members" && is_dept_row) {
            const n = parseInt(data.total_members) || 0;
            const col = n >= 20 ? "#27ae60" : n >= 10 ? "#f39c12" : "#3498db";
            value = `<strong style="color:${col};font-size:14px;">${n}</strong>`;
        }

        // Member row — full name link
        if (column.fieldname === "full_name" && is_member_row) {
            value = `<span style="padding-left:20px;color:#2c3e50;">
                         ${data.full_name || ""}
                     </span>`;
        }

        // Member row — is_primary badge
        if (column.fieldname === "is_primary" && is_member_row) {
            value = data.is_primary
                ? `<span style="background:#667eea;color:#fff;
                                 padding:2px 6px;border-radius:8px;font-size:10px;">
                       ⭐ Primary
                   </span>`
                : "";
        }

        // Gender split — male/female bar
        if (column.fieldname === "male_count" && is_dept_row) {
            const m = parseInt(data.male_count)   || 0;
            const f = parseInt(data.female_count) || 0;
            const total = m + f || 1;
            const mpct  = Math.round(m / total * 100);
            value = `<div style="display:flex;align-items:center;gap:4px;">
                         <span style="color:#3498db;font-size:11px;">♂</span>
                         <div style="flex:1;background:#ecf0f1;border-radius:3px;height:8px;min-width:40px;">
                             <div style="width:${mpct}%;background:#3498db;height:8px;border-radius:3px;"></div>
                         </div>
                         <span style="font-size:11px;color:#3498db;">${m}</span>
                     </div>`;
        }
        if (column.fieldname === "female_count" && is_dept_row) {
            const f = parseInt(data.female_count) || 0;
            const m = parseInt(data.male_count)   || 0;
            const total = m + f || 1;
            const fpct  = Math.round(f / total * 100);
            value = `<div style="display:flex;align-items:center;gap:4px;">
                         <span style="color:#e91e8c;font-size:11px;">♀</span>
                         <div style="flex:1;background:#ecf0f1;border-radius:3px;height:8px;min-width:40px;">
                             <div style="width:${fpct}%;background:#e91e8c;height:8px;border-radius:3px;"></div>
                         </div>
                         <span style="font-size:11px;color:#e91e8c;">${f}</span>
                     </div>`;
        }

        return value;
    },

    // Alternate background for department summary rows vs member rows
    get_datatable_options: function(options) {
        return options;
    },

    onload: function(report) {
        report.page.add_inner_button(__("📋 Summary Only"), function() {
            frappe.query_report.set_filter_value("show_members", 0);
            frappe.query_report.refresh();
        });

        report.page.add_inner_button(__("👥 Show All Members"), function() {
            frappe.query_report.set_filter_value("show_members", 1);
            frappe.query_report.refresh();
        });
    }
};
