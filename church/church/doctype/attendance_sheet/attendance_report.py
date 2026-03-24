# -*- coding: utf-8 -*-
"""
Attendance Sheet Report Generator
Beautiful HTML reports with email functionality
"""

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.utils import getdate, formatdate, now_datetime, get_url, nowdate, format_date, format_datetime
import json


@frappe.whitelist()
def generate_attendance_report(attendance_sheet_name, send_email=False, recipients=None):
    """
    Generate beautiful HTML report for Attendance Sheet
    
    Args:
        attendance_sheet_name: Name of the Attendance Sheet
        send_email: Boolean to send via email
        recipients: JSON string or list of email addresses
    """
    try:
        # Get attendance sheet document
        doc = frappe.get_doc("Attendance Sheet", attendance_sheet_name)
        
        # Generate HTML report
        html_report = generate_html_report(doc)
        
        # If email requested
        if send_email:
            if isinstance(recipients, str):
                recipients = json.loads(recipients)
            
            if not recipients:
                # Default to pastors and administrators
                recipients = get_default_recipients()
            
            send_report_email(doc, html_report, recipients)
            
            return {
                'success': True,
                'message': _('Report generated and sent to {0} recipients').format(len(recipients)),
                'html': html_report
            }
        
        return {
            'success': True,
            'html': html_report
        }
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), 'Attendance Report Generation Error')
        return {
            'success': False,
            'error': str(e)
        }


def generate_html_report(doc):
    """Generate beautiful HTML report"""
    
    # Calculate summary statistics
    summary = calculate_summary(doc)
    
    # Build HTML
    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Attendance Report - {doc.branch}</title>
        <style>
            {get_report_styles()}
        </style>
    </head>
    <body>
        <div class="report-container">
            {generate_header(doc)}
            {generate_summary_section(summary)}
            {generate_detailed_table(doc)}
            {generate_charts_section(summary)}
            {generate_footer(doc)}
        </div>
    </body>
    </html>
    """
    
    return html


def get_report_styles():
    """Return CSS styles for the report"""
    return """
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
            color: #333;
        }
        
        .report-container {
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 16px;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
            overflow: hidden;
        }
        
        .report-header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 40px;
            text-align: center;
        }
        
        .report-header h1 {
            font-size: 2.5em;
            margin-bottom: 10px;
            font-weight: 700;
            text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.2);
        }
        
        .report-header p {
            font-size: 1.2em;
            opacity: 0.95;
            margin: 5px 0;
        }
        
        .church-logo {
            width: 80px;
            height: 80px;
            margin: 0 auto 20px;
            background: white;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 2em;
            box-shadow: 0 4px 8px rgba(0, 0, 0, 0.2);
        }
        
        .summary-section {
            padding: 40px;
            background: #f8f9fa;
        }
        
        .summary-title {
            font-size: 1.8em;
            color: #667eea;
            margin-bottom: 25px;
            text-align: center;
            font-weight: 600;
        }
        
        .summary-cards {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        
        .summary-card {
            background: white;
            padding: 25px;
            border-radius: 12px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
            text-align: center;
            transition: transform 0.3s, box-shadow 0.3s;
        }
        
        .summary-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 8px 20px rgba(0, 0, 0, 0.15);
        }
        
        .summary-card.total {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }
        
        .summary-card.men {
            background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
            color: white;
        }
        
        .summary-card.women {
            background: linear-gradient(135deg, #fa709a 0%, #fee140 100%);
            color: white;
        }
        
        .summary-card.children {
            background: linear-gradient(135deg, #a8edea 0%, #fed6e3 100%);
            color: #333;
        }
        
        .summary-card.visitors {
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
            color: white;
        }
        
        .card-value {
            font-size: 3em;
            font-weight: 700;
            margin: 10px 0;
        }
        
        .card-label {
            font-size: 1.1em;
            opacity: 0.9;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        
        .detailed-section {
            padding: 40px;
        }
        
        .section-title {
            font-size: 1.8em;
            color: #667eea;
            margin-bottom: 25px;
            font-weight: 600;
            border-bottom: 3px solid #667eea;
            padding-bottom: 10px;
        }
        
        .attendance-table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
            border-radius: 8px;
            overflow: hidden;
        }
        
        .attendance-table thead {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }
        
        .attendance-table th {
            padding: 15px;
            text-align: left;
            font-weight: 600;
            text-transform: uppercase;
            font-size: 0.85em;
            letter-spacing: 1px;
        }
        
        .attendance-table td {
            padding: 12px 15px;
            border-bottom: 1px solid #e9ecef;
        }
        
        .attendance-table tbody tr:nth-child(even) {
            background-color: #f8f9fa;
        }
        
        .attendance-table tbody tr:hover {
            background-color: #e7f1ff;
            transition: background-color 0.3s;
        }
        
        .attendance-table tfoot {
            background: #f8f9fa;
            font-weight: 700;
            border-top: 3px solid #667eea;
        }
        
        .attendance-table tfoot td {
            padding: 15px;
            font-size: 1.1em;
            color: #667eea;
        }
        
        .number-cell {
            text-align: center;
            font-weight: 600;
        }
        
        .total-cell {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            font-weight: 700;
        }
        
        .charts-section {
            padding: 40px;
            background: #f8f9fa;
        }
        
        .progress-bar-container {
            margin: 20px 0;
        }
        
        .progress-label {
            display: flex;
            justify-content: space-between;
            margin-bottom: 8px;
            font-weight: 600;
            color: #495057;
        }
        
        .progress-bar {
            height: 30px;
            background: #e9ecef;
            border-radius: 15px;
            overflow: hidden;
            box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.1);
        }
        
        .progress-fill {
            height: 100%;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-weight: 600;
            transition: width 1s ease;
        }
        
        .progress-fill.men {
            background: linear-gradient(90deg, #4facfe 0%, #00f2fe 100%);
        }
        
        .progress-fill.women {
            background: linear-gradient(90deg, #fa709a 0%, #fee140 100%);
        }
        
        .progress-fill.children {
            background: linear-gradient(90deg, #a8edea 0%, #fed6e3 100%);
        }
        
        .progress-fill.visitors {
            background: linear-gradient(90deg, #f093fb 0%, #f5576c 100%);
        }
        
        .report-footer {
            background: #343a40;
            color: white;
            padding: 30px 40px;
            text-align: center;
        }
        
        .footer-info {
            margin: 10px 0;
            opacity: 0.9;
        }
        
        .divider {
            height: 3px;
            background: linear-gradient(90deg, transparent, #667eea, transparent);
            margin: 30px 0;
        }
        
        @media print {
            body {
                background: white;
                padding: 0;
            }
            
            .report-container {
                box-shadow: none;
            }
            
            .summary-card:hover,
            .attendance-table tbody tr:hover {
                transform: none;
                background-color: inherit;
            }
        }
        
        @media (max-width: 768px) {
            .report-header h1 {
                font-size: 1.8em;
            }
            
            .summary-cards {
                grid-template-columns: 1fr;
            }
            
            .attendance-table {
                font-size: 0.85em;
            }
            
            .attendance-table th,
            .attendance-table td {
                padding: 8px;
            }
        }
    """


def generate_header(doc):
    """Generate report header"""
    from frappe.utils import format_datetime, format_date
    
    # Format date properly
    formatted_date = format_date(doc.reporting_date, "dd MMM yyyy") if doc.reporting_date else ""
    
    # Format datetime for generation timestamp
    generation_time = format_datetime(now_datetime(), "dd MMM yyyy HH:mm")
    
    return f"""
    <div class="report-header">
        <div class="church-logo">⛪</div>
        <h1>Attendance Report</h1>
        <p><strong>{doc.branch}</strong></p>
        <p>{formatted_date} • {doc.month}</p>
        <p style="font-size: 0.9em; margin-top: 10px; opacity: 0.8;">
            Generated on {generation_time}
        </p>
    </div>
    """


def generate_summary_section(summary):
    """Generate summary cards section"""
    total_attendance = summary['total_attendance']
    
    return f"""
    <div class="summary-section">
        <h2 class="summary-title">📊 Summary Overview</h2>
        
        <div class="summary-cards">
            <div class="summary-card total">
                <div class="card-label">Total Attendance</div>
                <div class="card-value">{total_attendance}</div>
            </div>
            
            <div class="summary-card men">
                <div class="card-label">Men</div>
                <div class="card-value">{summary['total_men']}</div>
                <div style="font-size: 0.9em; margin-top: 5px;">
                    {calculate_percentage(summary['total_men'], total_attendance)}%
                </div>
            </div>
            
            <div class="summary-card women">
                <div class="card-label">Women</div>
                <div class="card-value">{summary['total_women']}</div>
                <div style="font-size: 0.9em; margin-top: 5px;">
                    {calculate_percentage(summary['total_women'], total_attendance)}%
                </div>
            </div>
            
            <div class="summary-card children">
                <div class="card-label">Children</div>
                <div class="card-value">{summary['total_children']}</div>
                <div style="font-size: 0.9em; margin-top: 5px;">
                    {calculate_percentage(summary['total_children'], total_attendance)}%
                </div>
            </div>
            
            <div class="summary-card visitors">
                <div class="card-label">Visitors</div>
                <div class="card-value">{summary['total_visitors']}</div>
                <div style="font-size: 0.9em; margin-top: 5px;">
                    {calculate_percentage(summary['total_visitors'], total_attendance)}%
                </div>
            </div>
        </div>
    </div>
    """


def generate_detailed_table(doc):
    """Generate detailed attendance table"""
    from frappe.utils import format_date
    
    table_rows = ""
    for row in doc.church_attendance_analysis:
        # Format date properly - handle None case
        formatted_date = format_date(row.date, "dd MMM") if row.date else ""
        
        table_rows += f"""
        <tr>
            <td>{formatted_date}</td>
            <td>{row.day or ''}</td>
            <td><strong>{row.programme}</strong></td>
            <td class="number-cell">{row.men or 0}</td>
            <td class="number-cell">{row.women or 0}</td>
            <td class="number-cell">{row.children or 0}</td>
            <td class="number-cell total-cell">{row.total or 0}</td>
            <td class="number-cell">{row.new_men or 0}</td>
            <td class="number-cell">{row.new_women or 0}</td>
            <td class="number-cell">{row.new_children or 0}</td>
            <td class="number-cell total-cell">{row.new_total or 0}</td>
        </tr>
        """
    
    return f"""
    <div class="detailed-section">
        <h2 class="section-title">📋 Detailed Breakdown by Programme</h2>
        
        <table class="attendance-table">
            <thead>
                <tr>
                    <th>Date</th>
                    <th>Day</th>
                    <th>Programme</th>
                    <th>Men</th>
                    <th>Women</th>
                    <th>Children</th>
                    <th>Total</th>
                    <th>New Men</th>
                    <th>New Women</th>
                    <th>New Children</th>
                    <th>Visitors</th>
                </tr>
            </thead>
            <tbody>
                {table_rows}
            </tbody>
            <tfoot>
                <tr>
                    <td colspan="3"><strong>GRAND TOTAL</strong></td>
                    <td class="number-cell">{doc.total_men or 0}</td>
                    <td class="number-cell">{doc.total_women or 0}</td>
                    <td class="number-cell">{doc.total_children or 0}</td>
                    <td class="number-cell total-cell">{doc.total_first or 0}</td>
                    <td class="number-cell">{doc.total_new_men or 0}</td>
                    <td class="number-cell">{doc.total_new_women or 0}</td>
                    <td class="number-cell">{doc.total_new_children or 0}</td>
                    <td class="number-cell total-cell">{doc.total_second or 0}</td>
                </tr>
            </tfoot>
        </table>
    </div>
    """


def generate_charts_section(summary):
    """Generate visual charts section"""
    total = summary['total_attendance']
    
    if total == 0:
        return ""
    
    men_percent = calculate_percentage(summary['total_men'], total)
    women_percent = calculate_percentage(summary['total_women'], total)
    children_percent = calculate_percentage(summary['total_children'], total)
    visitors_percent = calculate_percentage(summary['total_visitors'], total)
    
    return f"""
    <div class="charts-section">
        <h2 class="section-title">📈 Visual Analytics</h2>
        
        <div class="progress-bar-container">
            <div class="progress-label">
                <span>Men</span>
                <span>{summary['total_men']} ({men_percent}%)</span>
            </div>
            <div class="progress-bar">
                <div class="progress-fill men" style="width: {men_percent}%;">
                    {men_percent}%
                </div>
            </div>
        </div>
        
        <div class="progress-bar-container">
            <div class="progress-label">
                <span>Women</span>
                <span>{summary['total_women']} ({women_percent}%)</span>
            </div>
            <div class="progress-bar">
                <div class="progress-fill women" style="width: {women_percent}%;">
                    {women_percent}%
                </div>
            </div>
        </div>
        
        <div class="progress-bar-container">
            <div class="progress-label">
                <span>Children</span>
                <span>{summary['total_children']} ({children_percent}%)</span>
            </div>
            <div class="progress-bar">
                <div class="progress-fill children" style="width: {children_percent}%;">
                    {children_percent}%
                </div>
            </div>
        </div>
        
        <div class="progress-bar-container">
            <div class="progress-label">
                <span>Visitors</span>
                <span>{summary['total_visitors']} ({visitors_percent}%)</span>
            </div>
            <div class="progress-bar">
                <div class="progress-fill visitors" style="width: {visitors_percent}%;">
                    {visitors_percent}%
                </div>
            </div>
        </div>
    </div>
    """


def generate_footer(doc):
    """Generate report footer"""
    return f"""
    <div class="report-footer">
        <div class="footer-info">
            <strong>Ecclesia Church Management System</strong>
        </div>
        <div class="footer-info">
            Report ID: {doc.name} | Branch: {doc.branch}
        </div>
        <div class="footer-info" style="font-size: 0.9em; opacity: 0.8;">
            This is an automated report. For questions, contact your church administrator.
        </div>
    </div>
    """


def calculate_summary(doc):
    """Calculate summary statistics"""
    return {
        'total_attendance': doc.total_first or 0,
        'total_men': doc.total_men or 0,
        'total_women': doc.total_women or 0,
        'total_children': doc.total_children or 0,
        'total_visitors': doc.total_second or 0,
        'total_members': doc.total_third or 0
    }


def calculate_percentage(value, total):
    """Calculate percentage"""
    if total == 0:
        return 0
    return round((value / total) * 100, 1)


def get_default_recipients():
    """Get default email recipients (pastors and administrators)"""
    recipients = []
    
    # Get pastors
    pastors = frappe.get_all(
        "Member",
        filters={'is_a_pastor': 1},
        fields=['email', 'name']
    )
    
    for pastor in pastors:
        if pastor.email:
            recipients.append(pastor.email)
    
    # If no pastors, get system managers
    if not recipients:
        system_managers = frappe.get_all(
            "User",
            filters={'enabled': 1},
            fields=['email', 'name']
        )
        
        for user in system_managers:
            if user.email and '@' in user.email:
                recipients.append(user.email)
    
    return recipients


def send_report_email(doc, html_report, recipients):
    """Send report via email"""
    
    subject = _("Attendance Report - {0} ({1})").format(
        doc.branch,
        formatdate(doc.reporting_date, "dd MMM yyyy")
    )
    
    try:
        frappe.sendmail(
            recipients=recipients,
            subject=subject,
            message=html_report,
            delayed=False
        )
        
        frappe.msgprint(
            _("Report sent successfully to {0} recipients").format(len(recipients)),
            indicator='green'
        )
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), 'Attendance Report Email Error')
        frappe.throw(_("Failed to send email: {0}").format(str(e)))


@frappe.whitelist()
def preview_report(attendance_sheet_name):
    """Preview report in browser without sending email"""
    result = generate_attendance_report(attendance_sheet_name, send_email=False)
    
    if result.get('success'):
        return result.get('html')
    else:
        frappe.throw(result.get('error', 'Failed to generate report'))


@frappe.whitelist()
def email_report(attendance_sheet_name, recipients):
    """Email report to specified recipients"""
    return generate_attendance_report(
        attendance_sheet_name,
        send_email=True,
        recipients=recipients
    )