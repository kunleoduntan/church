// Copyright (c) 2026, Your Organization
// For license information, please see license.txt

frappe.query_reports["Member Tithe Record"] = {
    "filters": [
        {
            "fieldname": "member_id",
            "label": __("👤 Member"),
            "fieldtype": "Link",
            "options": "Member Tithe Record",
            "reqd": 1
        },
        {
            "fieldname": "from_date",
            "label": __("🌸 From Date"),
            "fieldtype": "Date",
            "default": frappe.datetime.add_months(frappe.datetime.get_today(), -12),
            "reqd": 0
        },
        {
            "fieldname": "to_date",
            "label": __("🌼 To Date"),
            "fieldtype": "Date",
            "default": frappe.datetime.get_today(),
            "reqd": 0
        },
        {
            "fieldname": "branch",
            "label": __("🏢 Branch"),
            "fieldtype": "Link",
            "options": "Branch",
            "reqd": 0
        },
        {
            "fieldname": "currency",
            "label": __("💵 Currency"),
            "fieldtype": "Link",
            "options": "Currency",
            "reqd": 0
        }
    ],
    
    "formatter": function(value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);
        
        // Skip formatting for summary row
        if (row && row.is_summary) {
            if (column.fieldname == "amount_paid" || column.fieldname == "amount_in_lc") {
                return `<strong style="color: #4F46E5;">${value}</strong>`;
            }
            if (column.fieldname == "other_details") {
                return `<span style="color: #92400E; font-style: italic;">${value}</span>`;
            }
            return value;
        }
        
        // Add styling to amount columns
        if (column.fieldname == "amount_in_lc") {
            return `<strong style="color: #10B981;">${value}</strong>`;
        }
        
        if (column.fieldname == "exchange_rate" && value) {
            return `<span style="font-family: monospace;">${value}</span>`;
        }
        
        if (column.fieldname == "receipt_no" && value) {
            return `<span style="font-family: monospace;">🧾 ${value}</span>`;
        }
        
        return value;
    },
    
    "tree": false,
    
    "onload": function(report) {
        // Show welcome message
        frappe.show_alert({
            message: __("📜 Preparing Member Tithe Record..."),
            indicator: 'green'
        }, 2);
        
        // Add custom print button after report loads
        setTimeout(() => {
            this.add_print_button(report);
        }, 500);
    },
    
    "refresh": function(report) {
        // Re-add button on refresh
        setTimeout(() => {
            this.add_print_button(report);
        }, 500);
    },
    
    "add_print_button": function(report) {
        // Check if button already exists
        if ($(".custom-print-btn").length > 0) {
            return;
        }
        
        // Find the toolbar
        let toolbar = $(".page-actions .btn-group");
        if (toolbar.length === 0) {
            toolbar = $(".page-actions");
        }
        
        if (toolbar.length > 0) {
            const printButton = $(`
                <button class="btn btn-primary custom-print-btn" style="
                    background: linear-gradient(135deg, #4F46E5 0%, #7C3AED 100%);
                    border: none;
                    color: white;
                    font-weight: 500;
                    margin-left: 8px;
                    padding: 6px 16px;
                    border-radius: 6px;
                    display: inline-flex;
                    align-items: center;
                    gap: 6px;
                    transition: all 0.2s ease;
                ">
                    🖨️ Print Member Record
                </button>
            `);
            
            printButton.on("click", () => {
                this.print_member_record(report);
            });
            
            printButton.hover(
                function() {
                    $(this).css({
                        'background': 'linear-gradient(135deg, #4338CA 0%, #6D28D9 100%)',
                        'transform': 'translateY(-1px)',
                        'box-shadow': '0 4px 6px rgba(0,0,0,0.1)'
                    });
                },
                function() {
                    $(this).css({
                        'background': 'linear-gradient(135deg, #4F46E5 0%, #7C3AED 100%)',
                        'transform': 'translateY(0)',
                        'box-shadow': '0 1px 2px rgba(0,0,0,0.05)'
                    });
                }
            );
            
            toolbar.append(printButton);
        }
    },
    
    "print_member_record": function(report) {
        // Get the member_id filter value
        let member_id = null;
        
        // Try to get the filter value safely
        if (report && report.filters) {
            // Check if filters is an array
            if (Array.isArray(report.filters)) {
                const member_filter = report.filters.find(f => f.fieldname === "member_id");
                if (member_filter && member_filter.get_value) {
                    member_id = member_filter.get_value();
                } else if (member_filter && member_filter.value) {
                    member_id = member_filter.value;
                }
            } 
            // Check if filters is an object
            else if (typeof report.filters === "object") {
                if (report.filters.member_id) {
                    if (report.filters.member_id.get_value) {
                        member_id = report.filters.member_id.get_value();
                    } else {
                        member_id = report.filters.member_id;
                    }
                }
            }
        }
        
        // Also check the global filter values
        if (!member_id && frappe.query_report && frappe.query_report.filters) {
            const member_filter = frappe.query_report.filters.find(f => f.fieldname === "member_id");
            if (member_filter && member_filter.get_value) {
                member_id = member_filter.get_value();
            }
        }
        
        if (!member_id) {
            frappe.msgprint({
                title: __("⚠️ No Member Selected"),
                message: __("Please select a member from the filter above to print their tithe record."),
                indicator: "orange"
            });
            return;
        }
        
        frappe.show_alert({
            message: __("📄 Preparing print-ready document..."),
            indicator: 'blue'
        }, 2);
        
        // Open the print view directly
        const print_url = `/printview?doctype=Member%20Tithe%20Record&name=${encodeURIComponent(member_id)}&format=Member%20Tithe%20Record%20Print`;
        window.open(print_url, '_blank');
    }
};