// Detailed Member Attendance Report - JS Filters
frappe.query_reports["Detailed Member Attendance Report"] = {
    "filters": [
        {
            "fieldname": "period",
            "label": __("Period"),
            "fieldtype": "Select",
            "options": [
                "",
                "Today",
                "Yesterday",
                "This Week",
                "Last Week",
                "This Month",
                "Last Month",
                "This Quarter",
                "Last Quarter",
                "This Year",
                "Last Year",
                "Last 7 Days",
                "Last 30 Days",
                "Last 90 Days",
                "Year to Date"
            ],
            "default": "Last 30 Days"
        },
        {
            "fieldname": "from_date",
            "label": __("From Date"),
            "fieldtype": "Date",
            "default": frappe.datetime.add_days(frappe.datetime.get_today(), -30)
        },
        {
            "fieldname": "to_date",
            "label": __("To Date"),
            "fieldtype": "Date",
            "default": frappe.datetime.get_today()
        },
        {
            "fieldname": "service_instance",
            "label": __("Service Instance"),
            "fieldtype": "Link",
            "options": "Service Instance"
        },
        {
            "fieldname": "year",
            "label": __("Year"),
            "fieldtype": "Select",
            "options": ["", "2026", "2025", "2024", "2023", "2022", "2021", "2020"]
        },
        {
            "fieldname": "month",
            "label": __("Month"),
            "fieldtype": "Select",
            "options": ["", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12"]
        },
        {
            "fieldname": "week",
            "label": __("Week"),
            "fieldtype": "Select",
            "options": ["", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10",
                       "11", "12", "13", "14", "15", "16", "17", "18", "19", "20",
                       "21", "22", "23", "24", "25", "26", "27", "28", "29", "30",
                       "31", "32", "33", "34", "35", "36", "37", "38", "39", "40",
                       "41", "42", "43", "44", "45", "46", "47", "48", "49", "50",
                       "51", "52"]
        },
        {
            "fieldname": "branch",
            "label": __("Branch"),
            "fieldtype": "Link",
            "options": "Branch"
        },
        {
            "fieldname": "demographic_group",
            "label": __("Demographic"),
            "fieldtype": "Select",
            "options": ["", "Men", "Women", "Youth", "Teens", "Children"]
        },
        {
            "fieldname": "status",
            "label": __("Status"),
            "fieldtype": "Select",
            "options": ["", "Excellent", "Good", "Fair", "Poor", "Very Poor"]
        },
        {
            "fieldname": "show_services",
            "label": __("Show Services"),
            "fieldtype": "Check",
            "default": 0
        }
    ]
};