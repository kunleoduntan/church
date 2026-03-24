// Copyright (c) 2026, kunle and contributors
// For license information, please see license.txt
/* eslint-disable */

// church/church/report/service_attendance_summary/service_attendance_summary.js

frappe.query_reports["Service Attendance Summary"] = {

    filters: [
        {
            fieldname: "from_date",
            label: __("From Date"),
            fieldtype: "Date",
            reqd: 1,
            default: frappe.datetime.add_months(frappe.datetime.now_date(), -1)
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
            fieldname: "service_type",
            label: __("Service Type"),
            fieldtype: "Select",
            options: "\nSunday Service\nMid-Week Service\nPrayer Meeting\nBible Study\nEvening Service\nYouth Service\nChildren's Service\nWorkers' Meeting\nAll-Night Service\nSpecial Service"
        },
        {
            fieldname: "status",
            label: __("Status"),
            fieldtype: "Select",
            options: "\nScheduled\nCompleted\nCancelled",
            default: "Completed"
        }
    ],

    formatter: function(value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);
        if (!data) return value;

        // Status badge
        if (column.fieldname === "status") {
            const colours = { "Completed":"#27ae60", "Scheduled":"#3498db",
                              "Cancelled":"#e74c3c", "Ongoing":"#f39c12" };
            const bg = colours[data.status] || "#95a5a6";
            value = `<span style="background:${bg};color:#fff;
                                   padding:2px 8px;border-radius:10px;font-size:11px;">
                         ${data.status || ""}
                     </span>`;
        }

        // Total attendance — bold, colour by size
        if (column.fieldname === "total_attendance") {
            const n = parseInt(data.total_attendance) || 0;
            const col = n >= 200 ? "#27ae60" : n >= 100 ? "#f39c12" : "#2c3e50";
            value = `<strong style="color:${col};font-size:13px;">${n}</strong>`;
        }

        // Capacity % — progress bar
        if (column.fieldname === "capacity_pct") {
            const pct = parseFloat(data.capacity_pct) || 0;
            const col = pct >= 90 ? "#e74c3c" : pct >= 70 ? "#f39c12" : "#27ae60";
            const display = data.capacity ? `${pct}%` : "—";
            if (!data.capacity) return `<span style="color:#95a5a6;">—</span>`;
            value = `<div style="display:flex;align-items:center;gap:6px;">
                         <div style="flex:1;background:#ecf0f1;border-radius:4px;height:10px;min-width:60px;">
                             <div style="width:${Math.min(pct,100)}%;background:${col};
                                         height:10px;border-radius:4px;"></div>
                         </div>
                         <span style="font-size:11px;color:${col};font-weight:600;min-width:38px;">${display}</span>
                     </div>`;
        }

        // QR checkins — blue
        if (column.fieldname === "qr_checkins") {
            const n = parseInt(data.qr_checkins) || 0;
            value = `<span style="color:#3498db;font-weight:600;">📱 ${n}</span>`;
        }

        // First timers — orange
        if (column.fieldname === "first_timers") {
            const n = parseInt(data.first_timers) || 0;
            if (n > 0) {
                value = `<span style="color:#e67e22;font-weight:600;">👋 ${n}</span>`;
            }
        }

        // Service name — bold
        if (column.fieldname === "service_name") {
            value = `<strong>${data.service_name || ""}</strong>`;
        }

        return value;
    },

    onload: function(report) {
        report.page.add_inner_button(__("📅 This Month"), function() {
            const now = frappe.datetime.now_date();
            frappe.query_report.set_filter_value("from_date", now.substring(0,7) + "-01");
            frappe.query_report.set_filter_value("to_date",   now);
            frappe.query_report.refresh();
        });

        report.page.add_inner_button(__("📅 Last Month"), function() {
            const d    = new Date();
            const from = new Date(d.getFullYear(), d.getMonth()-1, 1);
            const to   = new Date(d.getFullYear(), d.getMonth(), 0);
            frappe.query_report.set_filter_value("from_date", frappe.datetime.obj_to_str(from).substring(0,10));
            frappe.query_report.set_filter_value("to_date",   frappe.datetime.obj_to_str(to).substring(0,10));
            frappe.query_report.refresh();
        });
    }
};
