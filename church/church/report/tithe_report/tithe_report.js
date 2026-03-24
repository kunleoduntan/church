// Copyright (c) 2026, Your Organization
// For license information, please see license.txt

frappe.query_reports["Tithe Report"] = {
    "filters": [
        {
            "fieldname": "from_date",
            "label": __("🌸 From Date"),
            "fieldtype": "Date",
            "default": frappe.datetime.add_months(frappe.datetime.get_today(), -1),
            "reqd": 1
        },
        {
            "fieldname": "to_date",
            "label": __("🌼 To Date"),
            "fieldtype": "Date",
            "default": frappe.datetime.get_today(),
            "reqd": 1
        },
        {
            "fieldname": "batch_id",
            "label": __("📦 Batch"),
            "fieldtype": "Link",
            "options": "Tithe Batch Update",
            "get_query": function() {
                return {
                    filters: {
                        "docstatus": 1
                    }
                };
            }
        },
        {
            "fieldname": "member_id",
            "label": __("👤 Member"),
            "fieldtype": "Link",
            "options": "Member",
            "get_query": function() {
                return {
                    filters: {
                        "member_status": ["in", ["Active", "Inactive", "Left", "Transferred"]]
                    }
                };
            }
        },
        {
            "fieldname": "member_status",
            "label": __("⭐ Member Status"),
            "fieldtype": "Select",
            "options": ["All", "Active", "Inactive", "Left", "Transferred"],
            "default": "All"
        },
        {
            "fieldname": "type",
            "label": __("🌟 Source"),
            "fieldtype": "Select",
            "options": ["", "Worker", "Member"],
            "default": ""
        },
        {
            "fieldname": "branch",
            "label": __("🏢 Branch"),
            "fieldtype": "Link",
            "options": "Branch"
        },
        {
            "fieldname": "currency",
            "label": __("💵 Currency"),
            "fieldtype": "Link",
            "options": "Currency"
        },
        {
            "fieldname": "base_currency",
            "label": __("🏦 Base Currency"),
            "fieldtype": "Link",
            "options": "Currency",
            "default": "USD"
        }
    ],
    
    // Formatter with styling
    "formatter": function(value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);
        
        const colors = {
            active: "#10B981",
            inactive: "#6B7280",
            left: "#EF4444",
            transferred: "#F59E0B",
            subtotal: "#FEF3C7",
            subtotal_text: "#92400E",
            grand_total: "#D1FAE5",
            grand_total_text: "#065F46"
        };
        
        // Special styling for subtotal rows
        if (row && row.is_subtotal) {
            if (column.fieldname == "type") {
                return `<div style="background-color: ${colors.subtotal}; color: ${colors.subtotal_text}; padding: 4px 8px; border-radius: 6px; font-weight: bold; text-align: center;">✨ SUBTOTAL ✨</div>`;
            }
            if (column.fieldname == "receipt_reference") {
                return `<span style="color: ${colors.subtotal_text}; font-style: italic;">${value}</span>`;
            }
            if (column.fieldname == "full_name") {
                return `<strong style="color: ${colors.subtotal_text};">${value}</strong>`;
            }
            if (["amount_paid", "worker_tithe", "member_tithe", "total_base_currency"].includes(column.fieldname)) {
                return `<strong style="color: ${colors.subtotal_text};">${value}</strong>`;
            }
        }
        
        // Special styling for grand total row
        if (row && row.is_grand_total) {
            if (column.fieldname == "member_id") {
                return `<div style="background: linear-gradient(135deg, ${colors.grand_total}, #A7F3D0); padding: 6px 12px; border-radius: 8px; font-weight: bold; font-size: 1.1em; text-align: center;">🎯 ${value} 🎯</div>`;
            }
            if (column.fieldname == "type") {
                return `<div style="background-color: ${colors.grand_total}; color: ${colors.grand_total_text}; padding: 4px 8px; border-radius: 6px; font-weight: bold; text-align: center;">🏆 GRAND TOTAL 🏆</div>`;
            }
            if (column.fieldname == "receipt_reference") {
                return `<strong style="color: ${colors.grand_total_text};">${value}</strong>`;
            }
            if (["amount_paid", "worker_tithe", "member_tithe", "total_base_currency"].includes(column.fieldname)) {
                return `<strong style="color: ${colors.grand_total_text}; font-size: 1.05em;">${value}</strong>`;
            }
        }
        
        // Add emojis and styling to regular rows
        if (column.fieldname == "type" && value && !row.is_subtotal && !row.is_grand_total) {
            if (value == "Worker") value = "🙏 " + value;
            if (value == "Member") value = "🏡 " + value;
        }
        
        if (column.fieldname == "currency" && value && !row.is_subtotal && !row.is_grand_total) {
            value = "💵 " + value;
        }
        
        if (column.fieldname == "receipt_reference" && value && !row.is_subtotal && !row.is_grand_total) {
            value = "🧾 " + value;
        }
        
        if (column.fieldname == "member_status" && value) {
            const statusColors = {
                "Active": colors.active,
                "Inactive": colors.inactive,
                "Left": colors.left,
                "Transferred": colors.transferred
            };
            const statusEmojis = {
                "Active": "🟢",
                "Inactive": "⚪",
                "Left": "🔴",
                "Transferred": "🔄"
            };
            const color = statusColors[value] || colors.inactive;
            const emoji = statusEmojis[value] || "⭐";
            value = `<span style="color: ${color}; font-weight: 500;">${emoji} ${value}</span>`;
        }
        
        if (column.fieldname == "batch_name" && value) {
            value = `<span style="font-family: monospace; font-size: 0.9em;">📦 ${value}</span>`;
        }
        
        return value;
    },
    
    "tree": false,
    
    "onload": function(report) {
        frappe.show_alert({
            message: __("🎶 Counting blessings and tithes from submitted batches... ✨"),
            indicator: 'green'
        }, 3);
        
        // Add custom Excel button
        this.add_custom_excel_button(report);
        
        // Add friendly greeting
        setTimeout(() => {
            this.add_friendly_greeting();
        }, 500);
    },
    
    "refresh": function(report) {
        // Re-add button on refresh
        this.add_custom_excel_button(report);
    },
    
    "add_custom_excel_button": function(report) {
        // Wait for the page to be ready
        setTimeout(() => {
            // Check if button already exists
            if ($(".custom-excel-btn-styled").length > 0) {
                return;
            }
            
            // Find the report toolbar
            let toolbar = $(".page-actions .btn-group");
            
            if (toolbar.length === 0) {
                toolbar = $(".page-actions");
            }
            
            if (toolbar.length > 0) {
                // Create styled Excel button
                const excelButton = $(`
                    <button class="btn btn-success custom-excel-btn-styled" style="
                        background: linear-gradient(135deg, #10B981 0%, #059669 100%);
                        border: none;
                        color: white;
                        font-weight: 500;
                        margin-left: 8px;
                        padding: 6px 16px;
                        border-radius: 6px;
                        display: inline-flex;
                        align-items: center;
                        gap: 6px;
                        box-shadow: 0 1px 2px rgba(0,0,0,0.05);
                        transition: all 0.2s ease;
                    ">
                        📊 Export to Excel
                    </button>
                `);
                
                // Add click handler
                excelButton.on("click", () => {
                    this.export_to_excel(report);
                });
                
                // Add hover effect
                excelButton.hover(
                    function() {
                        $(this).css({
                            'background': 'linear-gradient(135deg, #059669 0%, #047857 100%)',
                            'transform': 'translateY(-1px)',
                            'box-shadow': '0 4px 6px rgba(0,0,0,0.1)'
                        });
                    },
                    function() {
                        $(this).css({
                            'background': 'linear-gradient(135deg, #10B981 0%, #059669 100%)',
                            'transform': 'translateY(0)',
                            'box-shadow': '0 1px 2px rgba(0,0,0,0.05)'
                        });
                    }
                );
                
                // Append to toolbar
                toolbar.append(excelButton);
            }
        }, 100);
    },
    
    "export_to_excel": function(report) {
        // Show loading message
        frappe.show_alert({
            message: __("✨ Preparing your Excel report..."),
            indicator: 'green'
        }, 2);
        
        // Get current filter values
        const filters = report.filters;
        const filter_values = {};
        
        if (filters) {
            for (let key in filters) {
                if (filters.hasOwnProperty(key) && filters[key] && filters[key].get_value) {
                    filter_values[key] = filters[key].get_value();
                }
            }
        }
        
        // Build URL for export
        const params = {
            doctype: "Tithe Report",
            report_name: "Tithe Report",
            format: "Excel",
            _lang: frappe.boot.lang,
            from_date: filter_values.from_date || frappe.datetime.add_months(frappe.datetime.get_today(), -1),
            to_date: filter_values.to_date || frappe.datetime.get_today(),
            batch_id: filter_values.batch_id || "",
            member_id: filter_values.member_id || "",
            member_status: filter_values.member_status || "All",
            type: filter_values.type || "",
            branch: filter_values.branch || "",
            currency: filter_values.currency || "",
            base_currency: filter_values.base_currency || "USD"
        };
        
        // Create query string
        const queryString = Object.keys(params)
            .map(key => `${encodeURIComponent(key)}=${encodeURIComponent(params[key])}`)
            .join('&');
        
        // Trigger download
        const url = `/api/method/frappe.core.report.report_export.export?${queryString}`;
        
        // Create hidden iframe or anchor for download
        const downloadFrame = document.createElement('iframe');
        downloadFrame.style.display = 'none';
        downloadFrame.src = url;
        document.body.appendChild(downloadFrame);
        
        // Remove iframe after download starts
        setTimeout(() => {
            document.body.removeChild(downloadFrame);
            frappe.show_alert({
                message: __("✅ Excel report generated! Check your downloads folder. 📥"),
                indicator: 'green'
            }, 3);
        }, 2000);
    },
    
    "add_friendly_greeting": function() {
        const report_container = $(".report-view");
        if (report_container.length && !$(".report-greeting").length) {
            report_container.prepend(`
                <div class="alert alert-info report-greeting" style="
                    margin: 10px 20px;
                    background: linear-gradient(135deg, #FEF3C7, #FDE68A);
                    border: none;
                    border-radius: 12px;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.05);
                ">
                    <div style="display: flex; align-items: center; justify-content: space-between;">
                        <div>
                            <span style="font-size: 1.1em; font-weight: 500;">✨ God bless your giving! 🙏</span>
                            <span style="margin-left: 12px; font-size: 0.9em; color: #92400E;">📊 Showing only submitted batches</span>
                        </div>
                        <button type="button" class="close" data-dismiss="alert" aria-label="Close" style="font-size: 1.2em;">
                            <span aria-hidden="true">&times;</span>
                        </button>
                    </div>
                </div>
            `);
        }
    }
};