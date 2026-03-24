# -*- coding: utf-8 -*-
"""
Service Instance Report Generator
Beautiful HTML reports with email functionality
"""

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.utils import getdate, formatdate, now_datetime, get_url, nowdate, format_date, format_datetime
import json


@frappe.whitelist()
def generate_service_report(service_instance_name, send_email=False, recipients=None):
    """
    Generate beautiful HTML report for Service Instance
    
    Args:
        service_instance_name: Name of the Service Instance
        send_email: Boolean to send via email
        recipients: JSON string or list of email addresses
    """
    try:
        # Get service instance document
        doc = frappe.get_doc("Service Instance", service_instance_name)
        
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
        frappe.log_error(frappe.get_traceback(), 'Service Report Generation Error')
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
        <title>Service Report - {doc.service_name}</title>
        <style>
            {get_report_styles()}
        </style>
    </head>
    <body>
        <div class="report-container">
            {generate_header(doc)}
            {generate_summary_section(summary, doc)}
            {generate_attendance_breakdown(doc)}
            {generate_ministry_team_section(doc)}
            {generate_visitors_section(doc)}
            {generate_sermon_section(doc)}
            {generate_charts_section(summary)}
            {generate_insights_section(summary, doc)}
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
            position: relative;
            overflow: hidden;
        }
        
        .report-header::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: url('data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 120"><path d="M0,0V46.29c47.79,22.2,103.59,32.17,158,28,70.36-5.37,136.33-33.31,206.8-37.5C438.64,32.43,512.34,53.67,583,72.05c69.27,18,138.3,24.88,209.4,13.08,36.15-6,69.85-17.84,104.45-29.34C989.49,25,1113-14.29,1200,52.47V0Z" opacity=".1" fill="white"/></svg>') no-repeat bottom;
            background-size: cover;
            opacity: 0.3;
        }
        
        .report-header h1 {
            font-size: 2.5em;
            margin-bottom: 10px;
            font-weight: 700;
            text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.2);
            position: relative;
            z-index: 1;
        }
        
        .report-header p {
            font-size: 1.2em;
            opacity: 0.95;
            margin: 5px 0;
            position: relative;
            z-index: 1;
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
            position: relative;
            z-index: 1;
        }
        
        .status-badge {
            display: inline-block;
            padding: 8px 20px;
            border-radius: 25px;
            background: rgba(255, 255, 255, 0.2);
            font-weight: 600;
            margin-top: 10px;
            border: 2px solid white;
        }
        
        .status-completed { background: #27ae60; }
        .status-ongoing { background: #f39c12; }
        .status-scheduled { background: #3498db; }
        .status-cancelled { background: #e74c3c; }
        
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
            position: relative;
            overflow: hidden;
        }
        
        .summary-card::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 4px;
            background: linear-gradient(90deg, #667eea, #764ba2);
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
        
        .summary-card.converts {
            background: linear-gradient(135deg, #43e97b 0%, #38f9d7 100%);
            color: white;
        }
        
        .card-icon {
            font-size: 2.5em;
            margin-bottom: 10px;
            opacity: 0.9;
        }
        
        .card-value {
            font-size: 3em;
            font-weight: 700;
            margin: 10px 0;
            text-shadow: 1px 1px 2px rgba(0, 0, 0, 0.1);
        }
        
        .card-label {
            font-size: 1.1em;
            opacity: 0.9;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        
        .section {
            padding: 40px;
        }
        
        .section:nth-child(even) {
            background: #f8f9fa;
        }
        
        .section-title {
            font-size: 1.8em;
            color: #667eea;
            margin-bottom: 25px;
            font-weight: 600;
            border-bottom: 3px solid #667eea;
            padding-bottom: 10px;
            position: relative;
        }
        
        .section-title::before {
            content: '';
            position: absolute;
            bottom: -3px;
            left: 0;
            width: 100px;
            height: 3px;
            background: linear-gradient(90deg, #f093fb, #f5576c);
        }
        
        .info-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }
        
        .info-item {
            background: white;
            padding: 15px 20px;
            border-radius: 8px;
            border-left: 4px solid #667eea;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
        }
        
        .info-label {
            font-size: 0.9em;
            color: #7f8c8d;
            margin-bottom: 5px;
            font-weight: 600;
        }
        
        .info-value {
            font-size: 1.1em;
            color: #2c3e50;
            font-weight: 600;
        }
        
        .team-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
            gap: 15px;
            margin-top: 20px;
        }
        
        .team-member {
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
            text-align: center;
            border-top: 3px solid #667eea;
        }
        
        .team-member-name {
            font-size: 1.1em;
            font-weight: 600;
            color: #2c3e50;
            margin-bottom: 5px;
        }
        
        .team-member-role {
            font-size: 0.9em;
            color: #7f8c8d;
            margin-bottom: 8px;
        }
        
        .team-member-present {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 15px;
            font-size: 0.85em;
            font-weight: 600;
        }
        
        .present-yes {
            background: #d4edda;
            color: #155724;
        }
        
        .present-no {
            background: #f8d7da;
            color: #721c24;
        }
        
        .visitors-table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
            border-radius: 8px;
            overflow: hidden;
        }
        
        .visitors-table thead {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }
        
        .visitors-table th {
            padding: 15px;
            text-align: left;
            font-weight: 600;
            text-transform: uppercase;
            font-size: 0.85em;
            letter-spacing: 1px;
        }
        
        .visitors-table td {
            padding: 12px 15px;
            border-bottom: 1px solid #e9ecef;
        }
        
        .visitors-table tbody tr:nth-child(even) {
            background-color: #f8f9fa;
        }
        
        .visitors-table tbody tr:hover {
            background-color: #e7f1ff;
            transition: background-color 0.3s;
        }
        
        .first-timer-badge {
            display: inline-block;
            padding: 3px 10px;
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
            color: white;
            border-radius: 12px;
            font-size: 0.8em;
            font-weight: 600;
        }
        
        .sermon-box {
            background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
            padding: 30px;
            border-radius: 12px;
            margin-top: 20px;
            border-left: 5px solid #667eea;
        }
        
        .sermon-title {
            font-size: 1.5em;
            color: #2c3e50;
            font-weight: 600;
            margin-bottom: 10px;
        }
        
        .sermon-text {
            font-size: 1.2em;
            color: #667eea;
            font-style: italic;
            margin-bottom: 15px;
        }
        
        .sermon-preacher {
            font-size: 1.1em;
            color: #7f8c8d;
        }
        
        .sermon-notes {
            margin-top: 20px;
            padding-top: 20px;
            border-top: 2px dashed #dee2e6;
            color: #34495e;
            line-height: 1.6;
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
        
        .insights-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }
        
        .insight-card {
            background: white;
            padding: 20px;
            border-radius: 12px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
            border-left: 5px solid #667eea;
        }
        
        .insight-card.positive {
            border-left-color: #27ae60;
            background: linear-gradient(135deg, #f0fff4 0%, #c6f6d5 100%);
        }
        
        .insight-card.warning {
            border-left-color: #f39c12;
            background: linear-gradient(135deg, #fffaf0 0%, #feebc8 100%);
        }
        
        .insight-card.info {
            border-left-color: #3498db;
            background: linear-gradient(135deg, #f0f9ff 0%, #cfe8fc 100%);
        }
        
        .insight-icon {
            font-size: 2em;
            margin-bottom: 10px;
        }
        
        .insight-title {
            font-size: 1.2em;
            font-weight: 600;
            color: #2c3e50;
            margin-bottom: 8px;
        }
        
        .insight-text {
            color: #34495e;
            line-height: 1.6;
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
            .visitors-table tbody tr:hover {
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
            
            .info-grid {
                grid-template-columns: 1fr;
            }
            
            .team-grid {
                grid-template-columns: 1fr;
            }
        }
    """


def generate_header(doc):
    """Generate report header"""
    formatted_date = format_date(doc.service_date, "dd MMM yyyy") if doc.service_date else ""
    generation_time = format_datetime(now_datetime(), "dd MMM yyyy HH:mm")
    
    status_class = f"status-{doc.status.lower()}" if doc.status else "status-scheduled"
    
    return f"""
    <div class="report-header">
        <div class="church-logo">⛪</div>
        <h1>{doc.service_name or 'Church Service'}</h1>
        <p><strong>{formatted_date}</strong></p>
        <p>{doc.service_time or ''} • {doc.venue or 'Main Sanctuary'}</p>
        <div class="status-badge {status_class}">
            {doc.status or 'Scheduled'}
        </div>
        <p style="font-size: 0.9em; margin-top: 15px; opacity: 0.8;">
            Generated on {generation_time}
        </p>
    </div>
    """


def generate_summary_section(summary, doc):
    """Generate summary cards section"""
    return f"""
    <div class="summary-section">
        <h2 class="summary-title">📊 Service Overview</h2>
        
        <div class="summary-cards">
            <div class="summary-card total">
                <div class="card-icon">👥</div>
                <div class="card-value">{summary['total_attendance']}</div>
                <div class="card-label">Total Attendance</div>
            </div>
            
            <div class="summary-card men">
                <div class="card-icon">🧔</div>
                <div class="card-value">{summary['men']}</div>
                <div class="card-label">Men</div>
                <div style="font-size: 0.9em; margin-top: 5px;">
                    {calculate_percentage(summary['men'], summary['total_attendance'])}%
                </div>
            </div>
            
            <div class="summary-card women">
                <div class="card-icon">👩</div>
                <div class="card-value">{summary['women']}</div>
                <div class="card-label">Women</div>
                <div style="font-size: 0.9em; margin-top: 5px;">
                    {calculate_percentage(summary['women'], summary['total_attendance'])}%
                </div>
            </div>
            
            <div class="summary-card children">
                <div class="card-icon">👶</div>
                <div class="card-value">{summary['children']}</div>
                <div class="card-label">Children</div>
                <div style="font-size: 0.9em; margin-top: 5px;">
                    {calculate_percentage(summary['children'], summary['total_attendance'])}%
                </div>
            </div>
            
            <div class="summary-card visitors">
                <div class="card-icon">🌟</div>
                <div class="card-value">{summary['first_timers']}</div>
                <div class="card-label">First-Timers</div>
            </div>
            
            <div class="summary-card converts">
                <div class="card-icon">🙏</div>
                <div class="card-value">{summary['new_converts']}</div>
                <div class="card-label">New Converts</div>
            </div>
        </div>
    </div>
    """


def generate_attendance_breakdown(doc):
    """Generate attendance breakdown section"""
    return f"""
    <div class="section">
        <h2 class="section-title">📈 Attendance Details</h2>
        
        <div class="info-grid">
            <div class="info-item">
                <div class="info-label">Minister/Pastor</div>
                <div class="info-value">{doc.minister or 'N/A'}</div>
            </div>
            
            <div class="info-item">
                <div class="info-label">Worship Leader</div>
                <div class="info-value">{doc.worship_leader or 'N/A'}</div>
            </div>
            
            <div class="info-item">
                <div class="info-label">Service Start Time</div>
                <div class="info-value">{doc.actual_start_time or doc.service_time or 'N/A'}</div>
            </div>
            
            <div class="info-item">
                <div class="info-label">Service End Time</div>
                <div class="info-value">{doc.actual_end_time or 'N/A'}</div>
            </div>
            
            <div class="info-item">
                <div class="info-label">Total Offering</div>
                <div class="info-value">{frappe.utils.fmt_money(doc.total_offering or 0, currency=frappe.db.get_single_value('Church Settings', 'default_currency') or 'NGN')}</div>
            </div>
            
            <div class="info-item">
                <div class="info-label">Total Tithe</div>
                <div class="info-value">{frappe.utils.fmt_money(doc.total_tithe or 0, currency=frappe.db.get_single_value('Church Settings', 'default_currency') or 'NGN')}</div>
            </div>
        </div>
    </div>
    """


def generate_ministry_team_section(doc):
    """Generate ministry team section"""
    if not doc.ministry_team or len(doc.ministry_team) == 0:
        return ""
    
    team_members_html = ""
    present_count = 0
    
    for member in doc.ministry_team:
        is_present = member.present if hasattr(member, 'present') else False
        if is_present:
            present_count += 1
        
        present_class = "present-yes" if is_present else "present-no"
        present_text = "✓ Present" if is_present else "✗ Absent"
        
        team_members_html += f"""
        <div class="team-member">
            <div class="team-member-name">{member.full_name or 'Unknown'}</div>
            <div class="team-member-role">{member.ministry_role or 'Team Member'}</div>
            <div class="team-member-present {present_class}">{present_text}</div>
        </div>
        """
    
    return f"""
    <div class="section">
        <h2 class="section-title">👨‍👩‍👧‍👦 Ministry Team ({present_count}/{len(doc.ministry_team)} Present)</h2>
        
        <div class="team-grid">
            {team_members_html}
        </div>
    </div>
    """


def generate_visitors_section(doc):
    """Generate visitors section"""
    if not doc.service_visitors or len(doc.service_visitors) == 0:
        return ""
    
    visitors_rows = ""
    for idx, visitor in enumerate(doc.service_visitors, 1):
        first_timer_badge = '<span class="first-timer-badge">⭐ First Timer</span>' if visitor.is_first_time else ''
        
        visitors_rows += f"""
        <tr>
            <td>{idx}</td>
            <td>{visitor.full_name or 'Unknown'}</td>
            <td>{visitor.phone or 'N/A'}</td>
            <td>{visitor.visit_type or 'N/A'}</td>
            <td>{'✓' if visitor.interested_in_membership else ''}</td>
            <td>{first_timer_badge}</td>
        </tr>
        """
    
    return f"""
    <div class="section">
        <h2 class="section-title">🌟 Visitors ({len(doc.service_visitors)})</h2>
        
        <table class="visitors-table">
            <thead>
                <tr>
                    <th>#</th>
                    <th>Name</th>
                    <th>Phone</th>
                    <th>Visit Type</th>
                    <th>Membership Interest</th>
                    <th>Status</th>
                </tr>
            </thead>
            <tbody>
                {visitors_rows}
            </tbody>
        </table>
    </div>
    """


def generate_sermon_section(doc):
    """Generate sermon section"""
    if not doc.sermon_title:
        return ""
    
    return f"""
    <div class="section">
        <h2 class="section-title">📖 Sermon Details</h2>
        
        <div class="sermon-box">
            <div class="sermon-title">{doc.sermon_title}</div>
            <div class="sermon-text">{doc.sermon_text or ''}</div>
            <div class="sermon-preacher">Preached by: {doc.preacher or 'N/A'}</div>
            {f'<div class="sermon-notes">{doc.sermon_notes}</div>' if doc.sermon_notes else ''}
        </div>
    </div>
    """


def generate_charts_section(summary):
    """Generate visual charts section"""
    total = summary['total_attendance']
    
    if total == 0:
        return ""
    
    men_percent = calculate_percentage(summary['men'], total)
    women_percent = calculate_percentage(summary['women'], total)
    children_percent = calculate_percentage(summary['children'], total)
    
    return f"""
    <div class="section">
        <h2 class="section-title">📊 Visual Analytics</h2>
        
        <div class="progress-bar-container">
            <div class="progress-label">
                <span>Men</span>
                <span>{summary['men']} ({men_percent}%)</span>
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
                <span>{summary['women']} ({women_percent}%)</span>
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
                <span>{summary['children']} ({children_percent}%)</span>
            </div>
            <div class="progress-bar">
                <div class="progress-fill children" style="width: {children_percent}%;">
                    {children_percent}%
                </div>
            </div>
        </div>
    </div>
    """


def generate_insights_section(summary, doc):
    """Generate AI insights section"""
    insights_html = ""
    
    # Attendance insight
    if summary['total_attendance'] > 100:
        insights_html += """
        <div class="insight-card positive">
            <div class="insight-icon">📈</div>
            <div class="insight-title">Excellent Turnout</div>
            <div class="insight-text">Great attendance! The congregation is growing.</div>
        </div>
        """
    
    # First-timers insight
    if summary['first_timers'] > 0:
        insights_html += f"""
        <div class="insight-card info">
            <div class="insight-icon">🌟</div>
            <div class="insight-title">New Visitors</div>
            <div class="insight-text">{summary['first_timers']} first-time visitor{'s' if summary['first_timers'] > 1 else ''} attended. Ensure proper follow-up!</div>
        </div>
        """
    
    # New converts insight
    if summary['new_converts'] > 0:
        insights_html += f"""
        <div class="insight-card positive">
            <div class="insight-icon">🎉</div>
            <div class="insight-title">Souls Won!</div>
            <div class="insight-text">{summary['new_converts']} new convert{'s' if summary['new_converts'] > 1 else ''} accepted Christ! Hallelujah!</div>
        </div>
        """
    
    # Ministry team insight
    if doc.ministry_team and len(doc.ministry_team) > 0:
        present_count = sum(1 for m in doc.ministry_team if getattr(m, 'present', False))
        if present_count == len(doc.ministry_team):
            insights_html += """
            <div class="insight-card positive">
                <div class="insight-icon">✅</div>
                <div class="insight-title">Full Team Present</div>
                <div class="insight-text">All ministry team members were present. Excellent commitment!</div>
            </div>
            """
    
    if not insights_html:
        return ""
    
    return f"""
    <div class="section">
        <h2 class="section-title">💡 Key Insights</h2>
        
        <div class="insights-grid">
            {insights_html}
        </div>
    </div>
    """


def generate_footer(doc):
    """Generate report footer"""
    return f"""
    <div class="report-footer">
        <div class="footer-info">
            <strong>⛪ Ecclesia Church Management System</strong>
        </div>
        <div class="footer-info">
            Service Instance ID: {doc.name} | {doc.service_name}
        </div>
        <div class="footer-info" style="font-size: 0.9em; opacity: 0.8;">
            This is an automated report. For questions, contact your church administrator.
        </div>
    </div>
    """


def calculate_summary(doc):
    """Calculate summary statistics"""
    return {
        'total_attendance': doc.total_attendance or 0,
        'men': doc.men_count or 0,
        'women': doc.women_count or 0,
        'children': doc.children_count or 0,
        'first_timers': doc.first_timers or 0,
        'new_converts': doc.new_converts or 0
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
    
    subject = _("Service Report - {0} ({1})").format(
        doc.service_name,
        formatdate(doc.service_date, "dd MMM yyyy")
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
        frappe.log_error(frappe.get_traceback(), 'Service Report Email Error')
        frappe.throw(_("Failed to send email: {0}").format(str(e)))


@frappe.whitelist()
def preview_report(service_instance_name):
    """Preview report in browser without sending email"""
    result = generate_service_report(service_instance_name, send_email=False)
    
    if result.get('success'):
        return result.get('html')
    else:
        frappe.throw(result.get('error', 'Failed to generate report'))


@frappe.whitelist()
def email_report(service_instance_name, recipients):
    """Email report to specified recipients"""
    return generate_service_report(
        service_instance_name,
        send_email=True,
        recipients=recipients
    )