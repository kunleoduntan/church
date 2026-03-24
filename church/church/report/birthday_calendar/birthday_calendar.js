// church/church/report/birthday_calendar/birthday_calendar.js

frappe.query_reports["Birthday Calendar"] = {

    filters: [
        {
            fieldname: "branch",
            label: __("Branch"),
            fieldtype: "Link",
            options: "Branch"
        },
        {
            fieldname: "month",
            label: __("Month"),
            fieldtype: "Select",
            options: [
                "", "1 - January", "2 - February", "3 - March",
                "4 - April", "5 - May", "6 - June",
                "7 - July", "8 - August", "9 - September",
                "10 - October", "11 - November", "12 - December"
            ].join("\n"),
            default: (new Date().getMonth() + 1).toString(),
            on_change: function() {
                const val = frappe.query_report.get_filter_value("month");
                if (val && val.includes(" - ")) {
                    frappe.query_report.set_filter_value("month", val.split(" - ")[0]);
                }
            }
        },
        {
            fieldname: "days_ahead",
            label: __("Days Ahead"),
            fieldtype: "Int",
            default: 30,
            // FIXED: Remove the "eval:" prefix and use simple expression
            depends_on: "!month"
        }
    ],

    formatter: function(value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);
        if (!data) return value;

        if (column.fieldname === "days_away") {
            const days = parseInt(data.days_away);
            if (days === 0) {
                value = `<span style="background:#f39c12;color:#fff;padding:2px 8px;border-radius:10px;font-weight:700;font-size:12px;">🎂 TODAY!</span>`;
            } else if (days <= 7) {
                value = `<span style="color:#e67e22;font-weight:600;">${days} day${days > 1 ? "s" : ""}</span>`;
            } else {
                value = `<span style="color:#7f8c8d;">${days} days</span>`;
            }
        }

        if (column.fieldname === "age_turning") {
            const age = parseInt(data.age_turning);
            const milestones = [1,5,10,13,16,18,21,25,30,40,50,60,70,80,90,100];
            if (milestones.includes(age)) {
                value = `<span style="color:#9b59b6;font-weight:700;font-size:13px;">🌟 ${age}</span>`;
            } else {
                value = `<strong>${age}</strong>`;
            }
        }

        if (column.fieldname === "full_name") {
            const icon = data.gender === "Female" ? "♀" : "♂";
            const col  = data.gender === "Female" ? "#e91e8c" : "#3498db";
            value = `<span style="color:${col};margin-right:4px;">${icon}</span>${value}`;
        }

        return value;
    },

    get_datatable_options: function(options) {
        if (!options.hooks) options.hooks = {};
        options.hooks.beforeRenderRow = function(row) {
            if (row && row[7] && row[7].content == 0) {
                return "background:#fff9e6;";
            }
            return "";
        };
        return options;
    },

    onload: function(report) {
        report.page.add_inner_button(__("📅 This Month"), function() {
            frappe.query_report.set_filter_value("month", (new Date().getMonth() + 1).toString());
            frappe.query_report.refresh();
        });

        report.page.add_inner_button(__("📅 Next Month"), function() {
            const next = (new Date().getMonth() + 2) % 12 || 12;
            frappe.query_report.set_filter_value("month", next.toString());
            frappe.query_report.refresh();
        });

        report.page.add_inner_button(__("🎂 Next 30 Days"), function() {
            frappe.query_report.set_filter_value("month", "");
            frappe.query_report.set_filter_value("days_ahead", 30);
            frappe.query_report.refresh();
        });
    }
};