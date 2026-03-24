// Copyright (c) 2026, kunle and contributors
// For license information, please see license.txt
/* eslint-disable */

// church/church/report/age_demographic_distribution/age_demographic_distribution.js

frappe.query_reports["Age and Demographic Distribution"] = {

    filters: [
        {
            fieldname: "branch",
            label: __("Branch"),
            fieldtype: "Link",
            options: "Branch"
        },
        {
            fieldname: "member_status",
            label: __("Status"),
            fieldtype: "Select",
            options: "\nActive\nInactive",
            default: "Active"
        }
    ],

    formatter: function(value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);
        if (!data) return value;

        // Demographic group — colour coded
        if (column.fieldname === "demographic_group") {
            const colours = {
                "Men":      "#2980b9",
                "Women":    "#e91e8c",
                "Youth":    "#27ae60",
                "Teens":    "#9b59b6",
                "Children": "#f39c12",
                "Unassigned":"#95a5a6"
            };
            const bg = colours[data.demographic_group] || "#667eea";
            value = `<span style="background:${bg};color:#fff;
                                  padding:3px 10px;border-radius:10px;font-size:12px;
                                  font-weight:600;">
                         ${data.demographic_group || ""}
                     </span>`;
        }

        // Gender icon
        if (column.fieldname === "gender") {
            if (data.gender === "Male")   value = `<span style="color:#3498db;">♂ Male</span>`;
            if (data.gender === "Female") value = `<span style="color:#e91e8c;">♀ Female</span>`;
        }

        // Percentage — progress bar
        if (column.fieldname === "pct") {
            const pct = parseFloat(data.pct) || 0;
            const col = pct >= 30 ? "#27ae60" : pct >= 15 ? "#f39c12" : "#3498db";
            value = `<div style="display:flex;align-items:center;gap:6px;">
                         <div style="flex:1;background:#ecf0f1;border-radius:4px;height:10px;">
                             <div style="width:${Math.min(pct,100)}%;background:${col};
                                         height:10px;border-radius:4px;"></div>
                         </div>
                         <span style="font-size:11px;color:#555;min-width:36px;">${pct}%</span>
                     </div>`;
        }

        // Count — bold
        if (column.fieldname === "count") {
            value = `<strong style="color:#2c3e50;">${data.count || 0}</strong>`;
        }

        return value;
    }
};
