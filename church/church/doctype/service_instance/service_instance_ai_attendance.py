# Copyright (c) 2026, Church Management and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime, get_datetime, formatdate, add_days, cint, flt, getdate
import json
from datetime import datetime, timedelta


class ServiceInstance(Document):
    def validate(self):
        """Validate Service Instance"""
        self.calculate_total_attendance()
        
    def calculate_total_attendance(self):
        """Calculate total attendance from men, women, and children counts"""
        self.total_attendance = (self.men_count or 0) + (self.women_count or 0) + (self.children_count or 0)


@frappe.whitelist()
def auto_update_attendance_from_visitors(service_instance=None):
    """
    AI-Powered Automatic Attendance Update
    Intelligently updates Service Instance attendance from visitor records
    
    Can be called:
    1. Automatically via scheduler (30 mins after service)
    2. Manually via button
    """
    
    if service_instance:
        # Manual call for specific service
        services = [frappe.get_doc('Service Instance', service_instance)]
    else:
        # Automatic call - find services that ended 30 mins ago
        target_time = add_to_date(now_datetime(), minutes=-30)
        
        services = frappe.get_all(
            'Service Instance',
            filters={
                'status': 'Completed',
                'actual_end_time': ['>', add_to_date(target_time, minutes=-5)],
                'actual_end_time': ['<=', add_to_date(target_time, minutes=5)]
            },
            fields=['name']
        )
        
        services = [frappe.get_doc('Service Instance', s.name) for s in services]
    
    results = {
        'success': [],
        'failed': [],
        'total_processed': 0,
        'total_attendance': 0
    }
    
    for service_doc in services:
        try:
            # Update attendance using AI analytics
            attendance_data = calculate_smart_attendance(service_doc)
            
            # Update service instance
            service_doc.men_count = attendance_data['men_count']
            service_doc.women_count = attendance_data['women_count']
            service_doc.children_count = attendance_data['children_count']
            service_doc.total_attendance = attendance_data['total_attendance']
            service_doc.first_timers = attendance_data['first_timers']
            service_doc.new_converts = attendance_data['new_converts']
            
            service_doc.save(ignore_permissions=True)
            
            results['success'].append({
                'service': service_doc.name,
                'attendance': attendance_data['total_attendance']
            })
            results['total_attendance'] += attendance_data['total_attendance']
            
            frappe.logger().info(f"Attendance updated for {service_doc.name}: {attendance_data['total_attendance']} total")
            
        except Exception as e:
            results['failed'].append({
                'service': service_doc.name,
                'error': str(e)
            })
            frappe.log_error(
                message=f"Failed to update attendance for {service_doc.name}: {str(e)}",
                title="Auto Attendance Update Error"
            )
    
    results['total_processed'] = len(services)
    
    return results


def calculate_smart_attendance(service_doc):
    """
    AI-Powered Smart Attendance Calculator
    Analyzes multiple data sources with intelligent deduplication
    """
    
    # Initialize counters
    attendance_data = {
        'men_count': 0,
        'women_count': 0,
        'children_count': 0,
        'total_attendance': 0,
        'first_timers': 0,
        'new_converts': 0,
        'breakdown': {
            'members': {'men': 0, 'women': 0, 'children': 0},
            'visitors': {'men': 0, 'women': 0, 'children': 0},
            'first_timers': {'men': 0, 'women': 0, 'children': 0}
        }
    }
    
    tracked_people = set()  # Prevent double counting
    
    # Source 1: Service Visitors Table (Primary Source)
    if service_doc.service_visitors:
        for visitor in service_doc.service_visitors:
            if visitor.visitor and visitor.visitor not in tracked_people:
                tracked_people.add(visitor.visitor)
                
                # Get visitor details
                visitor_doc = frappe.db.get_value('Visitor', visitor.visitor, 
                    ['gender', 'age', 'age_category', 'is_born_again'], as_dict=1)
                
                if visitor_doc:
                    # Categorize by age and gender
                    age = visitor_doc.age or 0
                    gender = visitor_doc.gender
                    
                    if age < 13:
                        attendance_data['children_count'] += 1
                        attendance_data['breakdown']['visitors']['children'] += 1
                    elif gender == 'Male':
                        attendance_data['men_count'] += 1
                        attendance_data['breakdown']['visitors']['men'] += 1
                    elif gender == 'Female':
                        attendance_data['women_count'] += 1
                        attendance_data['breakdown']['visitors']['women'] += 1
                    
                    # Track first timers
                    if visitor.is_first_time:
                        attendance_data['first_timers'] += 1
                        if age < 13:
                            attendance_data['breakdown']['first_timers']['children'] += 1
                        elif gender == 'Male':
                            attendance_data['breakdown']['first_timers']['men'] += 1
                        elif gender == 'Female':
                            attendance_data['breakdown']['first_timers']['women'] += 1
                    
                    # Track new converts
                    if visitor_doc.is_born_again and visitor.is_first_time:
                        attendance_data['new_converts'] += 1
    
    # Source 2: Direct Visitor Records (for this service date)
    additional_visitors = frappe.get_all(
        'Visitor',
        filters={
            'date_of_visit': service_doc.service_date,
            'service': service_doc.service
        },
        fields=['name', 'gender', 'age', 'visit_type', 'is_born_again']
    )
    
    for visitor in additional_visitors:
        if visitor.name not in tracked_people:
            tracked_people.add(visitor.name)
            
            age = visitor.age or 0
            gender = visitor.gender
            
            if age < 13:
                attendance_data['children_count'] += 1
                attendance_data['breakdown']['visitors']['children'] += 1
            elif gender == 'Male':
                attendance_data['men_count'] += 1
                attendance_data['breakdown']['visitors']['men'] += 1
            elif gender == 'Female':
                attendance_data['women_count'] += 1
                attendance_data['breakdown']['visitors']['women'] += 1
            
            # Track first timers
            if visitor.visit_type == 'First Time Visitor':
                attendance_data['first_timers'] += 1
            
            # Track new converts
            if visitor.is_born_again and visitor.visit_type == 'First Time Visitor':
                attendance_data['new_converts'] += 1
    
    # Source 3: AI Estimation from Church Attendance Analysis (if no visitor data)
    if attendance_data['total_attendance'] == 0:
        # Try to find attendance sheet data
        attendance_sheet = frappe.get_all(
            'Church Attendance Analysis',
            filters={
                'date': service_doc.service_date,
                'branch': service_doc.get('branch'),
                'programme': ['like', f'%{service_doc.service_name}%']
            },
            fields=['men', 'women', 'children', 'new_men', 'new_women', 'new_children'],
            limit=1
        )
        
        if attendance_sheet:
            sheet = attendance_sheet[0]
            attendance_data['men_count'] = sheet.men or 0
            attendance_data['women_count'] = sheet.women or 0
            attendance_data['children_count'] = sheet.children or 0
            attendance_data['first_timers'] = (sheet.new_men or 0) + (sheet.new_women or 0) + (sheet.new_children or 0)
    
    # Calculate totals
    attendance_data['total_attendance'] = (
        attendance_data['men_count'] + 
        attendance_data['women_count'] + 
        attendance_data['children_count']
    )
    
    return attendance_data


@frappe.whitelist()
def generate_attendance_analytics_report(service_instance):
    """
    Generate Beautiful AI-Powered Attendance Analytics Report
    """
    
    service_doc = frappe.get_doc('Service Instance', service_instance)
    
    # Calculate detailed analytics
    analytics = calculate_detailed_analytics(service_doc)
    
    # Generate HTML report
    report_html = generate_analytics_html(service_doc, analytics)
    
    return {
        'success': True,
        'report_html': report_html,
        'analytics': analytics
    }


def calculate_detailed_analytics(service_doc):
    """
    AI-Powered Analytics Engine
    Calculates comprehensive attendance insights
    """
    
    analytics = {
        'basic': {
            'total_attendance': service_doc.total_attendance or 0,
            'men': service_doc.men_count or 0,
            'women': service_doc.women_count or 0,
            'children': service_doc.children_count or 0,
            'first_timers': service_doc.first_timers or 0,
            'new_converts': service_doc.new_converts or 0
        },
        'percentages': {},
        'demographics': {},
        'trends': {},
        'insights': [],
        'recommendations': []
    }
    
    total = analytics['basic']['total_attendance']
    
    if total > 0:
        # Calculate percentages
        analytics['percentages'] = {
            'men_percent': round((analytics['basic']['men'] / total) * 100, 1),
            'women_percent': round((analytics['basic']['women'] / total) * 100, 1),
            'children_percent': round((analytics['basic']['children'] / total) * 100, 1),
            'first_timers_percent': round((analytics['basic']['first_timers'] / total) * 100, 1),
            'retention_rate': round(((total - analytics['basic']['first_timers']) / total) * 100, 1)
        }
        
        # Demographics analysis
        analytics['demographics'] = {
            'adult_count': analytics['basic']['men'] + analytics['basic']['women'],
            'adult_percent': round(((analytics['basic']['men'] + analytics['basic']['women']) / total) * 100, 1),
            'gender_ratio': round(analytics['basic']['men'] / analytics['basic']['women'], 2) if analytics['basic']['women'] > 0 else 0,
            'family_units_estimate': round(total / 3.5)  # Average family size
        }
    
    # Trend analysis - compare with previous services
    previous_services = frappe.get_all(
        'Service Instance',
        filters={
            'service': service_doc.service,
            'service_date': ['<', service_doc.service_date],
            'status': 'Completed'
        },
        fields=['total_attendance', 'first_timers', 'service_date'],
        order_by='service_date desc',
        limit=5
    )
    
    if previous_services:
        avg_attendance = sum(s.total_attendance or 0 for s in previous_services) / len(previous_services)
        avg_first_timers = sum(s.first_timers or 0 for s in previous_services) / len(previous_services)
        
        analytics['trends'] = {
            'attendance_trend': 'up' if total > avg_attendance else 'down',
            'attendance_change': round(((total - avg_attendance) / avg_attendance) * 100, 1) if avg_attendance > 0 else 0,
            'first_timers_trend': 'up' if analytics['basic']['first_timers'] > avg_first_timers else 'down',
            'first_timers_change': round(((analytics['basic']['first_timers'] - avg_first_timers) / avg_first_timers) * 100, 1) if avg_first_timers > 0 else 0,
            'average_attendance': round(avg_attendance),
            'comparison_period': f'Last {len(previous_services)} services'
        }
    
    # AI-Generated Insights
    analytics['insights'] = generate_ai_insights(analytics, service_doc)
    
    # AI-Generated Recommendations
    analytics['recommendations'] = generate_ai_recommendations(analytics, service_doc)
    
    return analytics


def generate_ai_insights(analytics, service_doc):
    """AI-Generated Insights based on data patterns"""
    
    insights = []
    basic = analytics['basic']
    percentages = analytics.get('percentages', {})
    trends = analytics.get('trends', {})
    
    # Attendance insights
    if trends.get('attendance_trend') == 'up' and trends.get('attendance_change', 0) > 10:
        insights.append({
            'type': 'positive',
            'icon': '📈',
            'title': 'Strong Growth',
            'message': f"Attendance increased by {trends['attendance_change']}% compared to recent average!"
        })
    elif trends.get('attendance_trend') == 'down' and trends.get('attendance_change', 0) < -10:
        insights.append({
            'type': 'warning',
            'icon': '📉',
            'title': 'Attendance Decline',
            'message': f"Attendance decreased by {abs(trends['attendance_change'])}%. Consider engagement strategies."
        })
    
    # First-timers insights
    if basic['first_timers'] > 0:
        if percentages.get('first_timers_percent', 0) > 20:
            insights.append({
                'type': 'positive',
                'icon': '🌟',
                'title': 'Excellent Visitor Turnout',
                'message': f"{basic['first_timers']} first-timers ({percentages['first_timers_percent']}% of attendance). Great evangelism!"
            })
        else:
            insights.append({
                'type': 'info',
                'icon': '👋',
                'title': 'New Visitors',
                'message': f"{basic['first_timers']} first-time visitors attended. Ensure proper follow-up."
            })
    
    # New converts insight
    if basic['new_converts'] > 0:
        insights.append({
            'type': 'celebration',
            'icon': '🎉',
            'title': 'Souls Won!',
            'message': f"{basic['new_converts']} new convert{'s' if basic['new_converts'] > 1 else ''} accepted Christ! Hallelujah!"
        })
    
    # Demographics insights
    demographics = analytics.get('demographics', {})
    if demographics.get('children_percent', 0) > 30:
        insights.append({
            'type': 'info',
            'icon': '👨‍👩‍👧‍👦',
            'title': 'Family-Friendly Service',
            'message': f"High children attendance ({percentages.get('children_percent', 0)}%). Consider family programs."
        })
    
    # Gender ratio insight
    if demographics.get('gender_ratio', 0) > 0:
        ratio = demographics['gender_ratio']
        if ratio < 0.7 or ratio > 1.3:
            insights.append({
                'type': 'info',
                'icon': '⚖️',
                'title': 'Gender Demographics',
                'message': f"Gender ratio: {ratio:.2f} (Men:Women). Consider targeted outreach."
            })
    
    return insights


def generate_ai_recommendations(analytics, service_doc):
    """AI-Generated Action Recommendations"""
    
    recommendations = []
    basic = analytics['basic']
    trends = analytics.get('trends', {})
    
    # First-timers follow-up
    if basic['first_timers'] > 0:
        recommendations.append({
            'priority': 'high',
            'icon': '📞',
            'action': 'Follow-up Required',
            'details': f"Send coordinator assignments for {basic['first_timers']} first-timers within 48 hours."
        })
    
    # Attendance decline action
    if trends.get('attendance_trend') == 'down' and trends.get('attendance_change', 0) < -15:
        recommendations.append({
            'priority': 'high',
            'icon': '🎯',
            'action': 'Engagement Campaign',
            'details': 'Consider member re-engagement campaign, special programs, or pastoral visits.'
        })
    
    # Growth strategies
    if trends.get('attendance_trend') == 'up':
        recommendations.append({
            'priority': 'medium',
            'icon': '🚀',
            'action': 'Sustain Growth',
            'details': 'Document successful strategies and replicate in other services.'
        })
    
    # Capacity planning
    if basic['total_attendance'] > 0:
        recommendations.append({
            'priority': 'low',
            'icon': '🏛️',
            'action': 'Capacity Review',
            'details': f"Current attendance: {basic['total_attendance']}. Review venue capacity and seating."
        })
    
    return recommendations


def generate_analytics_html(service_doc, analytics):
    """Generate Beautiful HTML Report"""
    
    service_name = service_doc.service_name or "Church Service"
    service_date = formatdate(service_doc.service_date, "dd MMM yyyy")
    basic = analytics['basic']
    percentages = analytics.get('percentages', {})
    trends = analytics.get('trends', {})
    demographics = analytics.get('demographics', {})
    
    html = f"""
    <div style="font-family: 'Segoe UI', Arial, sans-serif; max-width: 1000px; margin: 0 auto; padding: 20px; background: #f8f9fa; border-radius: 10px;">
        <!-- Header -->
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; border-radius: 10px 10px 0 0; text-align: center; color: white;">
            <h1 style="margin: 0 0 10px 0; font-size: 32px;">📊 Attendance Analytics Report</h1>
            <h2 style="margin: 0; font-size: 20px; font-weight: normal;">{service_name}</h2>
            <p style="margin: 10px 0 0 0; font-size: 16px; opacity: 0.9;">{service_date}</p>
        </div>
        
        <div style="background: white; padding: 30px; border-radius: 0 0 10px 10px;">
            
            <!-- Key Metrics Cards -->
            <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; margin-bottom: 30px;">
                <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 8px; text-align: center;">
                    <div style="font-size: 36px; font-weight: bold;">{basic['total_attendance']}</div>
                    <div style="font-size: 14px; opacity: 0.9;">Total Attendance</div>
                </div>
                <div style="background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); color: white; padding: 20px; border-radius: 8px; text-align: center;">
                    <div style="font-size: 36px; font-weight: bold;">{basic['first_timers']}</div>
                    <div style="font-size: 14px; opacity: 0.9;">First-Timers</div>
                </div>
                <div style="background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%); color: white; padding: 20px; border-radius: 8px; text-align: center;">
                    <div style="font-size: 36px; font-weight: bold;">{basic['new_converts']}</div>
                    <div style="font-size: 14px; opacity: 0.9;">New Converts</div>
                </div>
                <div style="background: linear-gradient(135deg, #43e97b 0%, #38f9d7 100%); color: white; padding: 20px; border-radius: 8px; text-align: center;">
                    <div style="font-size: 36px; font-weight: bold;">{percentages.get('retention_rate', 0)}%</div>
                    <div style="font-size: 14px; opacity: 0.9;">Retention Rate</div>
                </div>
            </div>
            
            <!-- Demographics Breakdown -->
            <h3 style="color: #2c3e50; margin-top: 30px; margin-bottom: 15px; font-size: 20px;">👥 Demographics Breakdown</h3>
            <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; margin-bottom: 30px;">
                <div style="background: #e8f4fd; padding: 20px; border-radius: 8px; border-left: 4px solid #3498db;">
                    <div style="font-size: 28px; font-weight: bold; color: #2c3e50;">{basic['men']}</div>
                    <div style="font-size: 14px; color: #7f8c8d;">Men ({percentages.get('men_percent', 0)}%)</div>
                    <div style="background: #3498db; height: 8px; border-radius: 4px; margin-top: 10px; width: {percentages.get('men_percent', 0)}%;"></div>
                </div>
                <div style="background: #fce8f3; padding: 20px; border-radius: 8px; border-left: 4px solid #e91e63;">
                    <div style="font-size: 28px; font-weight: bold; color: #2c3e50;">{basic['women']}</div>
                    <div style="font-size: 14px; color: #7f8c8d;">Women ({percentages.get('women_percent', 0)}%)</div>
                    <div style="background: #e91e63; height: 8px; border-radius: 4px; margin-top: 10px; width: {percentages.get('women_percent', 0)}%;"></div>
                </div>
                <div style="background: #fff8e1; padding: 20px; border-radius: 8px; border-left: 4px solid #f39c12;">
                    <div style="font-size: 28px; font-weight: bold; color: #2c3e50;">{basic['children']}</div>
                    <div style="font-size: 14px; color: #7f8c8d;">Children ({percentages.get('children_percent', 0)}%)</div>
                    <div style="background: #f39c12; height: 8px; border-radius: 4px; margin-top: 10px; width: {percentages.get('children_percent', 0)}%;"></div>
                </div>
            </div>
            
            {generate_trends_section(trends) if trends else ''}
            {generate_insights_section(analytics['insights']) if analytics['insights'] else ''}
            {generate_recommendations_section(analytics['recommendations']) if analytics['recommendations'] else ''}
            
            <!-- Footer -->
            <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #dee2e6; text-align: center; color: #7f8c8d; font-size: 12px;">
                <p style="margin: 5px 0;">Generated by AI-Powered Church Analytics System</p>
                <p style="margin: 5px 0;">Report created on {formatdate(now_datetime(), "dd MMM yyyy HH:mm")}</p>
            </div>
        </div>
    </div>
    """
    
    return html


def generate_trends_section(trends):
    """Generate trends section HTML"""
    
    trend_icon = '📈' if trends.get('attendance_trend') == 'up' else '📉'
    trend_color = '#27ae60' if trends.get('attendance_trend') == 'up' else '#e74c3c'
    change = trends.get('attendance_change', 0)
    
    return f"""
    <h3 style="color: #2c3e50; margin-top: 30px; margin-bottom: 15px; font-size: 20px;">{trend_icon} Attendance Trends</h3>
    <div style="background: #f8f9fa; padding: 20px; border-radius: 8px; margin-bottom: 30px;">
        <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 20px;">
            <div>
                <div style="font-size: 14px; color: #7f8c8d; margin-bottom: 5px;">Trend vs {trends.get('comparison_period', 'Previous')}</div>
                <div style="font-size: 24px; font-weight: bold; color: {trend_color};">
                    {'+' if change > 0 else ''}{change}%
                </div>
            </div>
            <div>
                <div style="font-size: 14px; color: #7f8c8d; margin-bottom: 5px;">Average Attendance</div>
                <div style="font-size: 24px; font-weight: bold; color: #2c3e50;">
                    {trends.get('average_attendance', 0)}
                </div>
            </div>
        </div>
    </div>
    """


def generate_insights_section(insights):
    """Generate insights section HTML"""
    
    if not insights:
        return ''
    
    type_colors = {
        'positive': '#27ae60',
        'warning': '#f39c12',
        'info': '#3498db',
        'celebration': '#e91e63'
    }
    
    insights_html = '<h3 style="color: #2c3e50; margin-top: 30px; margin-bottom: 15px; font-size: 20px;">💡 AI-Generated Insights</h3>'
    
    for insight in insights:
        color = type_colors.get(insight['type'], '#3498db')
        insights_html += f"""
        <div style="background: white; padding: 15px; margin-bottom: 15px; border-left: 4px solid {color}; border-radius: 4px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
            <div style="font-size: 18px; margin-bottom: 5px;">{insight['icon']} <strong>{insight['title']}</strong></div>
            <div style="font-size: 14px; color: #34495e;">{insight['message']}</div>
        </div>
        """
    
    return insights_html


def generate_recommendations_section(recommendations):
    """Generate recommendations section HTML"""
    
    if not recommendations:
        return ''
    
    priority_colors = {
        'high': '#e74c3c',
        'medium': '#f39c12',
        'low': '#3498db'
    }
    
    recs_html = '<h3 style="color: #2c3e50; margin-top: 30px; margin-bottom: 15px; font-size: 20px;">🎯 Recommended Actions</h3>'
    
    for rec in recommendations:
        color = priority_colors.get(rec['priority'], '#3498db')
        recs_html += f"""
        <div style="background: white; padding: 15px; margin-bottom: 15px; border-left: 4px solid {color}; border-radius: 4px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
            <div style="display: flex; align-items: center; margin-bottom: 8px;">
                <span style="font-size: 20px; margin-right: 10px;">{rec['icon']}</span>
                <div>
                    <div style="font-size: 16px; font-weight: bold; color: #2c3e50;">{rec['action']}</div>
                    <div style="font-size: 12px; color: white; background: {color}; display: inline-block; padding: 2px 8px; border-radius: 3px; margin-top: 3px;">
                        {rec['priority'].upper()} PRIORITY
                    </div>
                </div>
            </div>
            <div style="font-size: 14px; color: #34495e;">{rec['details']}</div>
        </div>
        """
    
    return recs_html


def add_to_date(dt, **kwargs):
    """Add time to datetime"""
    if isinstance(dt, str):
        dt = get_datetime(dt)
    return dt + timedelta(**kwargs)