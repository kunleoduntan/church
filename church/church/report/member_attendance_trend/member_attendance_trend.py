# church/church/report/member_attendance_trend/member_attendance_trend.py

import frappe
from frappe import _
from frappe.utils import getdate, nowdate
from datetime import datetime, timedelta
import json
import csv
from io import StringIO

def execute(filters=None):
    filters = filters or {}
    columns = get_columns()
    data = get_data(filters)
    summary = get_summary(data, filters)
    chart = get_chart(data)
    
    return columns, data, None, chart, summary

def get_columns():
    columns = [
        {"fieldname": "member_name", "label": _("Member"), "fieldtype": "Data", "width": 200},
        {"fieldname": "member_id", "label": _("Member ID"), "fieldtype": "Link", "options": "Member", "width": 120},
        {"fieldname": "branch", "label": _("Branch"), "fieldtype": "Link", "options": "Branch", "width": 150},
        {"fieldname": "gender", "label": _("Gender"), "fieldtype": "Data", "width": 80},
        {"fieldname": "avg_attendance_pct", "label": _("Avg Attendance"), "fieldtype": "Percent", "width": 120},
        {"fieldname": "trend_status", "label": _("Trend"), "fieldtype": "Data", "width": 100},
        {"fieldname": "trend_visual", "label": _("Trend Visual"), "fieldtype": "HTML", "width": 200},
    ]
    
    # Add period columns dynamically
    for i in range(1, 6):
        columns.append({"fieldname": f"p{i}_period", "label": _(f"Period {i}"), "fieldtype": "Data", "width": 110})
        columns.append({"fieldname": f"p{i}_count", "label": _(f"P{i} Attended"), "fieldtype": "Int", "width": 100})
        columns.append({"fieldname": f"p{i}_pct", "label": _(f"P{i} %"), "fieldtype": "Percent", "width": 90})
    
    return columns

def get_data(filters):
    # Safely get filter values with defaults
    branch = filters.get("branch", "") if filters and filters.get("branch") else ""
    period_type = filters.get("period_type", "Monthly") if filters else "Monthly"
    start_period = filters.get("start_period") if filters and filters.get("start_period") else None
    threshold = float(filters.get("attendance_threshold", 75)) if filters else 75
    threshold = threshold / 100  # Convert to decimal
    show_only_consistent = filters.get("show_only_consistent", 0) if filters else 0
    show_declining_only = filters.get("show_declining_only", 0) if filters else 0
    
    # Get the 5 periods with safe handling
    periods = get_periods(start_period, period_type)
    
    if not periods:
        frappe.msgprint(_("No periods generated. Please check your date settings."))
        return []
    
    # Get active members
    branch_cond = "AND branch = %(branch)s" if branch else ""
    
    try:
        members = frappe.db.sql(f"""
            SELECT name, full_name, branch, gender
            FROM `tabMember`
            WHERE member_status = 'Active'
              {branch_cond}
        """, {"branch": branch}, as_dict=True)
    except Exception as e:
        frappe.log_error(f"Error fetching members: {str(e)}", "Attendance Trend Report")
        frappe.msgprint(_("Error fetching members. Please check the Member doctype fields."))
        return []
    
    result = []
    
    for member in members:
        member_data = {
            "member_name": member.get("full_name", ""),
            "member_id": member.get("name", ""),
            "branch": member.get("branch", ""),
            "gender": member.get("gender", ""),
        }
        
        attendance_data = []
        total_pct = 0
        
        # Get attendance for each period
        for i, period in enumerate(periods, 1):
            period_name = period.get("name", f"Period {i}")
            start_date = period.get("start_date")
            end_date = period.get("end_date")
            
            if not start_date or not end_date:
                member_data[f"p{i}_period"] = period_name
                member_data[f"p{i}_count"] = 0
                member_data[f"p{i}_pct"] = 0
                attendance_data.append({"period": period_name, "count": 0, "pct": 0})
                continue
            
            # Get attendance count for this member in this period
            try:
                attendance_count = frappe.db.count("Church Attendance", {
                    "member_id": member.get("name"),
                    "present": 1,
                    "service_date": ["between", [start_date, end_date]],
                    "docstatus": 1
                })
            except Exception as e:
                frappe.log_error(f"Error counting attendance for {member.get('name')}: {str(e)}", "Attendance Trend Report")
                attendance_count = 0
            
            # Get total services in this period
            try:
                service_filters = {
                    "service_date": ["between", [start_date, end_date]],
                    "status": "Completed"
                }
                
                if branch:
                    service_filters["branch"] = branch
                
                total_services = frappe.db.count("Service Instance", service_filters)
            except Exception as e:
                frappe.log_error(f"Error counting services: {str(e)}", "Attendance Trend Report")
                total_services = 0
            
            attendance_pct = (attendance_count / total_services * 100) if total_services > 0 else 0
            
            member_data[f"p{i}_period"] = period_name
            member_data[f"p{i}_count"] = attendance_count
            member_data[f"p{i}_pct"] = round(attendance_pct, 1)
            
            attendance_data.append({
                "period": period_name,
                "count": attendance_count,
                "pct": attendance_pct
            })
            total_pct += attendance_pct
        
        # Calculate average
        avg_pct = total_pct / 5 if attendance_data else 0
        member_data["avg_attendance_pct"] = round(avg_pct, 1)
        
        # Determine trend status
        if any(d["count"] > 0 for d in attendance_data):
            trend_status = determine_trend(attendance_data, threshold)
        else:
            trend_status = "no_attendance"
        
        member_data["trend_status"] = trend_status
        
        # Apply filters
        if show_only_consistent and trend_status != "consistent":
            continue
        if show_declining_only and trend_status != "declining":
            continue
        
        result.append(member_data)
    
    # Sort by trend status and average attendance
    result.sort(key=lambda x: (
        0 if x.get("trend_status") == "consistent" else 
        1 if x.get("trend_status") == "improving" else 
        2 if x.get("trend_status") == "declining" else 3,
        -(x.get("avg_attendance_pct", 0))
    ))
    
    return result

def get_periods(start_period, period_type):
    """Generate 5 consecutive periods with robust error handling"""
    periods = []
    
    # SAFE HANDLING: If start_period is None or empty, use current date
    if not start_period or start_period == "" or start_period == "null" or start_period == "None":
        current_date = datetime.now()
        if period_type == "Monthly":
            start_period = current_date.strftime("%Y-%m")
        else:  # Quarterly
            quarter = ((current_date.month - 1) // 3) + 1
            start_period = f"{current_date.year}-Q{quarter}"
    
    try:
        if period_type == "Monthly":
            # SAFE SPLIT: Ensure the string has the correct format
            start_period_str = str(start_period)
            
            if "-" not in start_period_str:
                # Invalid format, use current month
                current_date = datetime.now()
                start_period = current_date.strftime("%Y-%m")
                start_period_str = start_period
            
            parts = start_period_str.split("-")
            
            # Ensure we have exactly 2 parts
            if len(parts) != 2:
                current_date = datetime.now()
                start_period = current_date.strftime("%Y-%m")
                parts = start_period.split("-")
            
            # Safely parse year and month
            try:
                year = int(parts[0])
                month = int(parts[1])
                
                # Validate month range
                if month < 1 or month > 12:
                    current_date = datetime.now()
                    year = current_date.year
                    month = current_date.month
                
                start_date = datetime(year, month, 1)
            except (ValueError, TypeError):
                # If parsing fails, use current date
                current_date = datetime.now()
                start_date = datetime(current_date.year, current_date.month, 1)
            
            # Generate 5 periods
            for i in range(5):
                try:
                    period_date = start_date - timedelta(days=30 * i)
                    period_name = period_date.strftime("%b %Y")
                    period_start = period_date.replace(day=1)
                    
                    # Get end of month
                    if period_date.month == 12:
                        period_end = period_date.replace(year=period_date.year + 1, month=1, day=1) - timedelta(days=1)
                    else:
                        period_end = period_date.replace(month=period_date.month + 1, day=1) - timedelta(days=1)
                    
                    periods.append({
                        "name": period_name,
                        "start_date": period_start.strftime("%Y-%m-%d"),
                        "end_date": period_end.strftime("%Y-%m-%d"),
                        "order": i
                    })
                except Exception as e:
                    frappe.log_error(f"Error generating period {i}: {str(e)}", "Attendance Trend Report")
                    continue
        
        else:  # Quarterly
            # SAFE SPLIT: Ensure the string has the correct format
            start_period_str = str(start_period)
            
            if "-Q" not in start_period_str:
                # Invalid format, use current quarter
                current_date = datetime.now()
                quarter = ((current_date.month - 1) // 3) + 1
                start_period = f"{current_date.year}-Q{quarter}"
                start_period_str = start_period
            
            # Safely parse quarter
            try:
                if "-Q" in start_period_str:
                    year_part, quarter_part = start_period_str.split("-Q")
                    year = int(year_part)
                    quarter_num = int(quarter_part)
                else:
                    current_date = datetime.now()
                    year = current_date.year
                    quarter_num = ((current_date.month - 1) // 3) + 1
                
                # Validate quarter range
                if quarter_num < 1 or quarter_num > 4:
                    current_date = datetime.now()
                    year = current_date.year
                    quarter_num = ((current_date.month - 1) // 3) + 1
                
            except (ValueError, TypeError):
                current_date = datetime.now()
                year = current_date.year
                quarter_num = ((current_date.month - 1) // 3) + 1
            
            # Generate 5 periods
            for i in range(5):
                try:
                    q_year = year
                    q_num = quarter_num - i
                    
                    while q_num < 1:
                        q_num += 4
                        q_year -= 1
                    
                    # Calculate quarter start and end dates
                    if q_num == 1:
                        start_date = datetime(q_year, 1, 1)
                        end_date = datetime(q_year, 3, 31)
                    elif q_num == 2:
                        start_date = datetime(q_year, 4, 1)
                        end_date = datetime(q_year, 6, 30)
                    elif q_num == 3:
                        start_date = datetime(q_year, 7, 1)
                        end_date = datetime(q_year, 9, 30)
                    else:  # q_num == 4
                        start_date = datetime(q_year, 10, 1)
                        end_date = datetime(q_year, 12, 31)
                    
                    periods.append({
                        "name": f"Q{q_num} {q_year}",
                        "start_date": start_date.strftime("%Y-%m-%d"),
                        "end_date": end_date.strftime("%Y-%m-%d"),
                        "order": i
                    })
                except Exception as e:
                    frappe.log_error(f"Error generating quarter period {i}: {str(e)}", "Attendance Trend Report")
                    continue
    
    except Exception as e:
        frappe.log_error(f"Error generating periods: {str(e)}", "Attendance Trend Report")
        # FALLBACK: Generate last 5 months
        current_date = datetime.now()
        for i in range(5):
            try:
                period_date = current_date - timedelta(days=30 * i)
                period_name = period_date.strftime("%b %Y")
                period_start = period_date.replace(day=1)
                
                if period_date.month == 12:
                    period_end = period_date.replace(year=period_date.year + 1, month=1, day=1) - timedelta(days=1)
                else:
                    period_end = period_date.replace(month=period_date.month + 1, day=1) - timedelta(days=1)
                
                periods.append({
                    "name": period_name,
                    "start_date": period_start.strftime("%Y-%m-%d"),
                    "end_date": period_end.strftime("%Y-%m-%d"),
                    "order": i
                })
            except Exception as e:
                frappe.log_error(f"Error generating fallback period {i}: {str(e)}", "Attendance Trend Report")
                continue
    
    # Reverse to show oldest first
    periods.reverse()
    return periods

def determine_trend(attendance_data, threshold):
    """Determine trend based on attendance patterns"""
    if not attendance_data or len(attendance_data) < 2:
        return "variable"
    
    # Extract percentages safely
    valid_data = []
    for d in attendance_data:
        pct = d.get("pct", 0)
        if pct is not None and isinstance(pct, (int, float)):
            valid_data.append({"pct": pct})
    
    if len(valid_data) < 2:
        return "variable"
    
    # Check if consistently above threshold
    consistent = all(d["pct"] >= threshold * 100 for d in valid_data)
    if consistent:
        return "consistent"
    
    # Check for improving trend
    if valid_data[-1]["pct"] > valid_data[0]["pct"] + 10:
        improvements = 0
        for i in range(1, len(valid_data)):
            if valid_data[i]["pct"] > valid_data[i-1]["pct"]:
                improvements += 1
        if improvements >= len(valid_data) / 2:
            return "improving"
    
    # Check for declining trend
    if valid_data[0]["pct"] > valid_data[-1]["pct"] + 10:
        declines = 0
        for i in range(1, len(valid_data)):
            if valid_data[i]["pct"] < valid_data[i-1]["pct"]:
                declines += 1
        if declines >= len(valid_data) / 2:
            return "declining"
    
    # Check if recent attendance is very low
    if valid_data[-1]["pct"] < 30:
        return "declining"
    
    return "variable"

def get_summary(data, filters):
    threshold = float(filters.get("attendance_threshold", 75)) if filters else 75
    total_members = len(data)
    consistent_members = sum(1 for d in data if d.get("trend_status") == "consistent")
    improving_members = sum(1 for d in data if d.get("trend_status") == "improving")
    declining_members = sum(1 for d in data if d.get("trend_status") == "declining")
    
    return {
        "total_members": total_members,
        "consistent_members": consistent_members,
        "improving_members": improving_members,
        "declining_members": declining_members,
        "threshold": threshold
    }

def get_chart(data):
    if not data:
        return {}
    
    # Group by trend status
    trend_counts = {
        "Consistent": 0,
        "Improving": 0,
        "Declining": 0,
        "Variable": 0
    }
    
    for d in data:
        status = d.get("trend_status", "variable")
        if status == "consistent":
            trend_counts["Consistent"] += 1
        elif status == "improving":
            trend_counts["Improving"] += 1
        elif status == "declining":
            trend_counts["Declining"] += 1
        else:
            trend_counts["Variable"] += 1
    
    # Remove zero values
    filtered_counts = {k: v for k, v in trend_counts.items() if v > 0}
    
    if not filtered_counts:
        return {}
    
    return {
        "data": {
            "labels": list(filtered_counts.keys()),
            "datasets": [{
                "name": _("Members by Trend"),
                "values": list(filtered_counts.values()),
                "chartType": "pie",
                "colors": ["#27ae60", "#3498db", "#e74c3c", "#95a5a6"]
            }]
        },
        "type": "pie",
        "title": _("Member Attendance Trend Distribution"),
        "height": 300
    }

@frappe.whitelist()
def export_trend_data(filters):
    """Export trend data to CSV"""
    try:
        if isinstance(filters, str):
            filters = json.loads(filters)
        
        data = get_data(filters)
        
        # Create CSV
        output = StringIO()
        writer = csv.writer(output)
        
        # Write headers
        headers = ["Member Name", "Member ID", "Branch", "Gender", "Average Attendance %", "Trend Status"]
        writer.writerow(headers)
        
        # Write data
        for row in data:
            writer.writerow([
                row.get("member_name", ""),
                row.get("member_id", ""),
                row.get("branch", ""),
                row.get("gender", ""),
                row.get("avg_attendance_pct", 0),
                row.get("trend_status", "")
            ])
        
        # Create file
        filename = f"attendance_trend_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        file_path = f"/tmp/{filename}"
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(output.getvalue())
        
        return file_path
        
    except Exception as e:
        frappe.log_error(f"Error exporting trend data: {str(e)}", "Attendance Trend Export")
        frappe.msgprint(_("Error exporting data: {0}").format(str(e)))
        return None