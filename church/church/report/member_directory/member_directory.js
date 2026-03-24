// Copyright (c) 2026, kunle and contributors
// For license information, please see license.txt
/* eslint-disable */

// church/church/report/member_directory/member_directory.js

frappe.query_reports["Member Directory"] = {

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
            options: "\nActive\nInactive\nTransferred\nLeft",
            default: "Active"
        },
        {
            fieldname: "gender",
            label: __("Gender"),
            fieldtype: "Link",
            options: "Gender"
        },
        {
            fieldname: "demographic_group",
            label: __("Demographic Group"),
            fieldtype: "Data"
        },
        {
            fieldname: "category",
            label: __("Age Category"),
            fieldtype: "Select",
            options: "\nChild\nTeenager\nYouth\nAdult\nElder"
        },
        {
            fieldname: "from_date",
            label: __("Joined From"),
            fieldtype: "Date"
        },
        {
            fieldname: "to_date",
            label: __("Joined To"),
            fieldtype: "Date"
        }
    ],

    // ── Column formatters ─────────────────────────────────────────────────────
    formatter: function(value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);

        if (!data) return value;

        // Status badge colours
        if (column.fieldname === "member_status") {
            const colours = {
                "Active":      "green",
                "Inactive":    "orange",
                "Transferred": "blue",
                "Left":        "red"
            };
            const col = colours[data.member_status] || "grey";
            value = `<span class="badge badge-${col}"
                          style="background:${_badge_bg(col)};color:#fff;
                                 padding:3px 8px;border-radius:10px;font-size:11px;">
                         ${data.member_status || ""}
                     </span>`;
        }

        // Age category badge
        if (column.fieldname === "category") {
            const colours = {
                "Child":    "#3498db",
                "Teenager": "#9b59b6",
                "Youth":    "#27ae60",
                "Adult":    "#2c3e50",
                "Elder":    "#e67e22"
            };
            const bg = colours[data.category] || "#95a5a6";
            value = `<span style="background:${bg};color:#fff;
                                  padding:2px 8px;border-radius:10px;font-size:11px;">
                         ${data.category || ""}
                     </span>`;
        }

        // Highlight missing contact info
        if (column.fieldname === "mobile_phone" && !data.mobile_phone) {
            value = `<span style="color:#e74c3c;font-style:italic;">No phone</span>`;
        }
        if (column.fieldname === "email" && !data.email) {
            value = `<span style="color:#e74c3c;font-style:italic;">No email</span>`;
        }

        // Department count — colour code
        if (column.fieldname === "department_count") {
            const n = parseInt(data.department_count) || 0;
            const col = n === 0 ? "#e74c3c" : n >= 3 ? "#27ae60" : "#2c3e50";
            value = `<span style="color:${col};font-weight:600;">${n}</span>`;
        }

        return value;
    },

    // ── Row-level highlight ───────────────────────────────────────────────────
    get_datatable_options: function(options) {
        options.getRowHTML = function(cells, props) {
            return null; // use default but allow CSS overrides
        };
        return options;
    },

    onload: function(report) {
        // Add export button
        report.page.add_inner_button(__("📊 Export Excel"), function() {
            frappe.call({
                method: "church.church.doctype.member.member.export_members_to_excel",
                freeze: true,
                freeze_message: __("Generating Excel…"),
                callback: function(r) {
                    if (r.message && r.message.success) {
                        const link = document.createElement("a");
                        link.href = "data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,"
                                    + r.message.file_content;
                        link.download = r.message.filename;
                        link.click();
                    }
                }
            });
        });
    }
};

function _badge_bg(name) {
    return { green:"#27ae60", orange:"#e67e22", blue:"#2980b9",
             red:"#e74c3c",   grey:"#95a5a6",  purple:"#8e44ad" }[name] || "#95a5a6";
}
