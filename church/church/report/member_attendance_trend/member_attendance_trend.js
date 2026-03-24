// Copyright (c) 2026, kunle and contributors
// For license information, please see license.txt
/* eslint-disable */


// church/church/report/member_attendance_trend/member_attendance_trend.js

frappe.query_reports["Member Attendance Trend"] = {

    filters: [
        {
            fieldname: "branch",
            label: __("Branch"),
            fieldtype: "Link",
            options: "Branch",
            width: 150
        },
        {
            fieldname: "period_type",
            label: __("Period Type"),
            fieldtype: "Select",
            options: ["Monthly", "Quarterly"],
            default: "Monthly",
            width: 120,
            on_change: function() {
                frappe.query_report.refresh();
            }
        },
        {
            fieldname: "start_period",
            label: __("Start Period"),
            fieldtype: "Select",
            options: () => {
                const periods = [];
                const currentDate = new Date();
                for (let i = 0; i < 12; i++) {
                    const date = new Date(currentDate.getFullYear(), currentDate.getMonth() - i, 1);
                    const period = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`;
                    periods.push(period);
                }
                return periods.join("\n");
            },
            default: () => {
                const date = new Date();
                return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`;
            },
            width: 120
        },
        {
            fieldname: "attendance_threshold",
            label: __("Attendance Threshold (%)"),
            fieldtype: "Percent",
            default: 75,
            width: 150,
            description: __("Minimum attendance percentage to be considered consistent")
        },
        {
            fieldname: "show_only_consistent",
            label: __("Show Only Consistent Members"),
            fieldtype: "Check",
            default: 0,
            width: 150
        }
    ],

    formatter: function(value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);
        if (!data) return value;

        // Member name with status indicator
        if (column.fieldname === "member_name") {
            let statusBadge = "";
            if (data.trend_status === "improving") {
                statusBadge = `<span style="background: #27ae60; color: white; padding: 2px 8px; border-radius: 12px; font-size: 10px; margin-left: 8px;">📈 Improving</span>`;
            } else if (data.trend_status === "declining") {
                statusBadge = `<span style="background: #e74c3c; color: white; padding: 2px 8px; border-radius: 12px; font-size: 10px; margin-left: 8px;">📉 Declining</span>`;
            } else if (data.trend_status === "consistent") {
                statusBadge = `<span style="background: #f39c12; color: white; padding: 2px 8px; border-radius: 12px; font-size: 10px; margin-left: 8px;">⭐ Consistent</span>`;
            }
            
            const icon = data.gender === "Female" ? "👩" : "👨";
            value = `<div style="display: flex; align-items: center; gap: 8px;">
                        <span style="font-size: 18px;">${icon}</span>
                        <span style="font-weight: 600;">${value}</span>
                        ${statusBadge}
                     </div>`;
        }

        // Attendance percentage with color coding
        if (column.fieldname === "avg_attendance_pct") {
            const pct = parseFloat(value);
            let color = "#e74c3c";
            let icon = "🔴";
            if (pct >= 80) {
                color = "#27ae60";
                icon = "🟢";
            } else if (pct >= 50) {
                color = "#f39c12";
                icon = "🟡";
            }
            value = `<span style="color: ${color}; font-weight: 700;">${icon} ${pct}%</span>`;
        }

        // Trend arrow for period-to-period changes
        if (column.fieldname.startsWith("p") && column.fieldname.includes("_pct")) {
            const currentPct = parseFloat(value);
            const periodIndex = parseInt(column.fieldname.split("_")[0].substring(1));
            
            if (periodIndex > 1) {
                const prevField = `p${periodIndex-1}_pct`;
                const prevPct = parseFloat(data[prevField]);
                if (!isNaN(currentPct) && !isNaN(prevPct) && prevPct > 0) {
                    const change = currentPct - prevPct;
                    if (change > 5) {
                        value = `<span style="color: #27ae60;">▲ ${currentPct}%</span>`;
                    } else if (change < -5) {
                        value = `<span style="color: #e74c3c;">▼ ${currentPct}%</span>`;
                    } else {
                        value = `<span style="color: #7f8c8d;">→ ${currentPct}%</span>`;
                    }
                } else {
                    value = `<span style="color: #7f8c8d;">${currentPct}%</span>`;
                }
            } else {
                value = `<span style="color: #3498db;">${currentPct}%</span>`;
            }
        }

        // Attendance count with badge
        if (column.fieldname.endsWith("_count") && column.fieldname.startsWith("p")) {
            const count = parseInt(value);
            if (count === 0) {
                value = `<span style="color: #e74c3c;">${count}</span>`;
            } else if (count >= 3) {
                value = `<span style="color: #27ae60; font-weight: 600;">${count}</span>`;
            }
        }

        // Trend line visualization
        if (column.fieldname === "trend_visual") {
            const periods = [data.p1_pct, data.p2_pct, data.p3_pct, data.p4_pct, data.p5_pct];
            const maxHeight = 40;
            const maxPct = Math.max(...periods, 100);
            
            const bars = periods.map(pct => {
                const height = (pct / maxPct) * maxHeight;
                let color = "#3498db";
                if (pct >= 80) color = "#27ae60";
                else if (pct >= 50) color = "#f39c12";
                else color = "#e74c3c";
                
                return `<div style="display: inline-block; width: 30px; margin: 0 2px; text-align: center;">
                            <div style="height: ${height}px; background: ${color}; width: 100%; border-radius: 3px 3px 0 0;"></div>
                            <div style="font-size: 10px; margin-top: 2px;">${pct}%</div>
                        </div>`;
            }).join('');
            
            value = `<div style="display: flex; align-items: flex-end; justify-content: center; height: 60px;">${bars}</div>`;
        }

        return value;
    },

    get_datatable_options: function(options) {
        if (!options.hooks) options.hooks = {};
        
        options.hooks.beforeRenderRow = function(row) {
            if (row && row[1]) {
                const data = row[1].meta.rowData;
                if (data && data.trend_status === "consistent") {
                    return "background: #fff9e6;";
                } else if (data && data.trend_status === "improving") {
                    return "background: #e8f5e9;";
                } else if (data && data.trend_status === "declining") {
                    return "background: #ffebee;";
                }
            }
            return "";
        };
        
        return options;
    },

    onload: function(report) {
        // Quick action buttons
        report.page.add_inner_button(__("🏆 Consistent Members"), function() {
            frappe.query_report.set_filter_value("show_only_consistent", 1);
            frappe.query_report.set_filter_value("attendance_threshold", 75);
            frappe.query_report.refresh();
        });

        report.page.add_inner_button(__("📈 Improving Trend"), function() {
            frappe.query_report.set_filter_value("show_only_consistent", 0);
            frappe.query_report.set_filter_value("attendance_threshold", 0);
            frappe.query_report.refresh();
        });

        report.page.add_inner_button(__("⚠️ At Risk Members"), function() {
            frappe.query_report.set_filter_value("show_only_consistent", 0);
            frappe.query_report.set_filter_value("attendance_threshold", 0);
            // This will be handled by the backend to show declining trend
            frappe.query_report.set_filter_value("show_declining_only", 1);
            frappe.query_report.refresh();
        });

        report.page.add_inner_button(__("📊 Export Trend Data"), function() {
            const filters = frappe.query_report.get_filter_values();
            frappe.call({
                method: "church.church.report.member_attendance_trend.member_attendance_trend.export_trend_data",
                args: { filters: filters },
                callback: function(r) {
                    if (r.message) {
                        window.open(r.message);
                    }
                }
            });
        });
    },

    refresh: function(report) {
        // Add custom summary cards after data is loaded
        setTimeout(() => {
            const summary = report.data?.summary;
            if (summary) {
                this.render_summary_cards(summary);
            }
        }, 100);
    },

    render_summary_cards: function(summary) {
        const $reportContainer = $(frappe.query_report.page.body).find('.report-content');
        const existingCards = $reportContainer.find('.trend-summary-cards');
        if (existingCards.length) existingCards.remove();
        
        const cardsHtml = `
            <div class="trend-summary-cards" style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; margin-bottom: 20px; padding: 10px;">
                <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 15px; border-radius: 10px; color: white;">
                    <div style="font-size: 12px; opacity: 0.9;">Total Members Tracked</div>
                    <div style="font-size: 28px; font-weight: bold;">${summary.total_members || 0}</div>
                </div>
                <div style="background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); padding: 15px; border-radius: 10px; color: white;">
                    <div style="font-size: 12px; opacity: 0.9;">Consistent Members</div>
                    <div style="font-size: 28px; font-weight: bold;">${summary.consistent_members || 0}</div>
                    <div style="font-size: 11px;">≥${summary.threshold}% attendance</div>
                </div>
                <div style="background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%); padding: 15px; border-radius: 10px; color: white;">
                    <div style="font-size: 12px; opacity: 0.9;">Improving Trend</div>
                    <div style="font-size: 28px; font-weight: bold;">${summary.improving_members || 0}</div>
                </div>
                <div style="background: linear-gradient(135deg, #fa709a 0%, #fee140 100%); padding: 15px; border-radius: 10px; color: white;">
                    <div style="font-size: 12px; opacity: 0.9;">At Risk / Declining</div>
                    <div style="font-size: 28px; font-weight: bold;">${summary.declining_members || 0}</div>
                    <div style="font-size: 11px;">Needs attention</div>
                </div>
            </div>
        `;
        
        $reportContainer.prepend(cardsHtml);
    }
};