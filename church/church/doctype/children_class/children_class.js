// Copyright (c) 2026, kunle and contributors
// For license information, please see license.txt

frappe.ui.form.on('Children Class', {
    refresh: function(frm) {
        // Apply modern styling to child tables
        apply_modern_grid_styling(frm);
        
        // Add custom action buttons
        add_custom_buttons(frm);
        
        // Add dashboard indicators
        add_dashboard_indicators(frm);
        
        // Real-time statistics
        update_class_statistics(frm);
        
        // Apply conditional formatting
        apply_conditional_formatting(frm);
    },
    
    onload: function(frm) {
        // Set up field watchers
        setup_field_watchers(frm);
    },
    
    promotion_age: function(frm) {
        calculate_promotion_candidates(frm);
    },
    
    next_class_group: function(frm) {
        validate_promotion_path(frm);
    }
});

// ==================== MODERN GRID STYLING ====================
function apply_modern_grid_styling(frm) {
    // Style Children Class Members table
    style_grid_table(frm, 'children_class_member', {
        even_color: '#ffffff',
        odd_color: '#f0f9ff',
        hover_color: '#dbeafe',
        border_color: '#3b82f6'
    });
    
    // Style Slated Promotion table
    style_grid_table(frm, 'slated_promotion', {
        even_color: '#ffffff',
        odd_color: '#fef3c7',
        hover_color: '#fde68a',
        border_color: '#f59e0b'
    });
    
    // Style Assets table
    style_grid_table(frm, 'children_class_assets', {
        even_color: '#ffffff',
        odd_color: '#f0fdf4',
        hover_color: '#dcfce7',
        border_color: '#10b981'
    });
}

function style_grid_table(frm, fieldname, colors) {
    if (!frm.fields_dict[fieldname]) return;
    
    const grid_wrapper = frm.fields_dict[fieldname].grid.wrapper;
    
    // Apply alternating row colors with smooth transitions
    grid_wrapper.find('.grid-row').each(function(i, row) {
        const $row = $(row);
        const bg_color = i % 2 === 0 ? colors.even_color : colors.odd_color;
        
        $row.css({
            'background-color': bg_color,
            'transition': 'all 0.3s ease',
            'border-left': `3px solid transparent`
        });
        
        // Add hover effects
        $row.hover(
            function() {
                $(this).css({
                    'background-color': colors.hover_color,
                    'border-left': `3px solid ${colors.border_color}`,
                    'transform': 'translateX(2px)',
                    'box-shadow': '0 2px 8px rgba(0,0,0,0.1)'
                });
            },
            function() {
                $(this).css({
                    'background-color': bg_color,
                    'border-left': '3px solid transparent',
                    'transform': 'translateX(0)',
                    'box-shadow': 'none'
                });
            }
        );
    });
    
    // Style grid header
    grid_wrapper.find('.grid-heading-row').css({
        'background': `linear-gradient(135deg, ${colors.border_color}15 0%, ${colors.border_color}30 100%)`,
        'font-weight': '600',
        'color': '#1f2937',
        'border-bottom': `2px solid ${colors.border_color}`,
        'text-transform': 'uppercase',
        'font-size': '11px',
        'letter-spacing': '0.5px'
    });
}

// ==================== CUSTOM ACTION BUTTONS ====================
function add_custom_buttons(frm) {
    if (!frm.doc.__islocal) {
        // Check Promotion Eligibility
        frm.add_custom_button(__('🔍 Check Promotions'), function() {
            check_promotion_eligibility(frm);
        }, __('Actions'));
        
        // Export to Excel
        frm.add_custom_button(__('📊 Export Class Report'), function() {
            export_class_to_excel(frm);
        }, __('Reports'));
        
        // Send Class Update
        frm.add_custom_button(__('📧 Send Class Update'), function() {
            send_class_update_email(frm);
        }, __('Communications'));
        
        // Generate QR Codes for Assets
        frm.add_custom_button(__('🔲 Generate Asset QR Codes'), function() {
            generate_asset_qr_codes(frm);
        }, __('Assets'));
        
        // Print Class Roster
        frm.add_custom_button(__('🖨️ Print Class Roster'), function() {
            print_class_roster(frm);
        }, __('Reports'));
        
        // View Analytics Dashboard
        frm.add_custom_button(__('📈 View Analytics'), function() {
            show_class_analytics(frm);
        }, __('Reports'));
    }
}

// ==================== DASHBOARD INDICATORS ====================
function add_dashboard_indicators(frm) {
    if (frm.doc.__islocal) return;
    
    const indicators_html = `
        <div class="class-dashboard-indicators" style="
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 15px;
            margin: 20px 0;
            padding: 15px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border-radius: 12px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        ">
            <div class="indicator-card" style="
                background: white;
                padding: 15px;
                border-radius: 8px;
                text-align: center;
                box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            ">
                <div style="font-size: 28px; font-weight: bold; color: #3b82f6;">
                    ${frm.doc.member_count || 0}
                </div>
                <div style="color: #6b7280; font-size: 12px; margin-top: 5px;">Total Members</div>
            </div>
            
            <div class="indicator-card" style="
                background: white;
                padding: 15px;
                border-radius: 8px;
                text-align: center;
                box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            ">
                <div style="font-size: 28px; font-weight: bold; color: #f59e0b;">
                    ${(frm.doc.slated_promotion || []).length}
                </div>
                <div style="color: #6b7280; font-size: 12px; margin-top: 5px;">Due for Promotion</div>
            </div>
            
            <div class="indicator-card" style="
                background: white;
                padding: 15px;
                border-radius: 8px;
                text-align: center;
                box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            ">
                <div style="font-size: 28px; font-weight: bold; color: #10b981;">
                    ${(frm.doc.children_class_assets || []).length}
                </div>
                <div style="color: #6b7280; font-size: 12px; margin-top: 5px;">Total Assets</div>
            </div>
            
            <div class="indicator-card" style="
                background: white;
                padding: 15px;
                border-radius: 8px;
                text-align: center;
                box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            ">
                <div style="font-size: 28px; font-weight: bold; color: #8b5cf6;">
                    ${format_currency(frm.doc.value_of_asset || 0)}
                </div>
                <div style="color: #6b7280; font-size: 12px; margin-top: 5px;">Asset Value</div>
            </div>
        </div>
    `;
    
    // Insert after the title
    if (!frm.dashboard.stats_area_row) {
        frm.dashboard.add_section(indicators_html, __('Class Overview'));
        frm.dashboard.show();
    }
}

// ==================== STATISTICS & ANALYTICS ====================
function update_class_statistics(frm) {
    if (frm.doc.__islocal) return;
    
    const members = frm.doc.children_class_member || [];
    const males = members.filter(m => m.gender === 'Male').length;
    const females = members.filter(m => m.gender === 'Female').length;
    const avg_age = members.length > 0 
        ? (members.reduce((sum, m) => sum + (m.age || 0), 0) / members.length).toFixed(1)
        : 0;
    
    const stats_html = `
        <div class="class-statistics" style="
            background: linear-gradient(135deg, #f3f4f6 0%, #e5e7eb 100%);
            padding: 15px;
            border-radius: 8px;
            margin-top: 15px;
        ">
            <h4 style="margin: 0 0 10px 0; color: #374151;">📊 Class Statistics</h4>
            <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px;">
                <div style="background: white; padding: 10px; border-radius: 6px; text-align: center;">
                    <div style="color: #3b82f6; font-weight: bold;">👦 ${males}</div>
                    <div style="font-size: 11px; color: #6b7280;">Males</div>
                </div>
                <div style="background: white; padding: 10px; border-radius: 6px; text-align: center;">
                    <div style="color: #ec4899; font-weight: bold;">👧 ${females}</div>
                    <div style="font-size: 11px; color: #6b7280;">Females</div>
                </div>
                <div style="background: white; padding: 10px; border-radius: 6px; text-align: center;">
                    <div style="color: #8b5cf6; font-weight: bold;">🎂 ${avg_age}</div>
                    <div style="font-size: 11px; color: #6b7280;">Avg Age</div>
                </div>
            </div>
        </div>
    `;
    
    frm.set_df_property('note', 'description', stats_html);
}

// ==================== CONDITIONAL FORMATTING ====================
function apply_conditional_formatting(frm) {
    // Highlight children due for promotion soon
    const promotion_rows = frm.fields_dict.slated_promotion.grid.grid_rows;
    
    promotion_rows.forEach(row => {
        const promotion_date = row.doc.promotion_date;
        if (promotion_date) {
            const days_until = frappe.datetime.get_day_diff(promotion_date, frappe.datetime.nowdate());
            
            if (days_until <= 7 && days_until >= 0) {
                $(row.wrapper).css({
                    'background': 'linear-gradient(90deg, #fee2e2 0%, #fecaca 100%)',
                    'border-left': '4px solid #ef4444',
                    'font-weight': '500'
                });
            }
        }
    });
}

// ==================== PROMOTION ELIGIBILITY CHECKER ====================
function check_promotion_eligibility(frm) {
    frappe.call({
        method: 'church.church.doctype.children_class.children_class.check_promotion_eligibility',
        args: {
            class_name: frm.doc.name
        },
        freeze: true,
        freeze_message: __('🔍 Checking promotion eligibility...'),
        callback: function(r) {
            if (r.message) {
                const eligible = r.message.eligible || [];
                const upcoming = r.message.upcoming || [];
                
                let message = `
                    <div style="font-family: sans-serif;">
                        <h3 style="color: #1f2937; margin-bottom: 15px;">📋 Promotion Eligibility Report</h3>
                        
                        <div style="background: #dcfce7; padding: 15px; border-radius: 8px; margin-bottom: 15px;">
                            <h4 style="color: #166534; margin: 0 0 10px 0;">✅ Ready for Promotion (${eligible.length})</h4>
                            ${eligible.length > 0 ? `
                                <ul style="margin: 0; padding-left: 20px;">
                                    ${eligible.map(child => `
                                        <li style="margin: 5px 0;">
                                            <strong>${child.full_name}</strong> - Age ${child.age}
                                            <span style="color: #059669;">(Promote to ${frm.doc.next_class_group})</span>
                                        </li>
                                    `).join('')}
                                </ul>
                            ` : '<p style="margin: 0; color: #6b7280;">No children ready for immediate promotion</p>'}
                        </div>
                        
                        <div style="background: #fef3c7; padding: 15px; border-radius: 8px;">
                            <h4 style="color: #92400e; margin: 0 0 10px 0;">⏰ Upcoming Promotions (${upcoming.length})</h4>
                            ${upcoming.length > 0 ? `
                                <ul style="margin: 0; padding-left: 20px;">
                                    ${upcoming.map(child => `
                                        <li style="margin: 5px 0;">
                                            <strong>${child.full_name}</strong> - Age ${child.age}
                                            <span style="color: #d97706;">(Due: ${frappe.datetime.str_to_user(child.promotion_date)})</span>
                                        </li>
                                    `).join('')}
                                </ul>
                            ` : '<p style="margin: 0; color: #6b7280;">No upcoming promotions in the next 30 days</p>'}
                        </div>
                    </div>
                `;
                
                frappe.msgprint({
                    title: __('Promotion Eligibility'),
                    message: message,
                    indicator: 'blue',
                    primary_action: {
                        label: __('Process Promotions'),
                        action: function() {
                            process_eligible_promotions(frm, eligible);
                        }
                    }
                });
            }
        }
    });
}

// ==================== EXCEL EXPORT ====================
function export_class_to_excel(frm) {
    frappe.call({
        method: 'church.church.doctype.children_class.children_class.export_class_report',
        args: {
            class_name: frm.doc.name
        },
        freeze: true,
        freeze_message: __('📊 Generating Excel report...'),
        callback: function(r) {
            if (r.message) {
                // Download the file
                window.open(r.message.file_url, '_blank');
                
                frappe.show_alert({
                    message: __('✅ Excel report generated successfully!'),
                    indicator: 'green'
                }, 5);
            }
        }
    });
}

// ==================== EMAIL COMMUNICATIONS ====================
function send_class_update_email(frm) {
    const d = new frappe.ui.Dialog({
        title: __('📧 Send Class Update'),
        fields: [
            {
                label: __('Recipients'),
                fieldname: 'recipients',
                fieldtype: 'Select',
                options: 'Teachers Only\nParents Only\nTeachers and Parents\nCustom',
                default: 'Teachers and Parents',
                reqd: 1
            },
            {
                label: __('Custom Email Addresses'),
                fieldname: 'custom_emails',
                fieldtype: 'Small Text',
                depends_on: 'eval:doc.recipients=="Custom"',
                description: 'Enter email addresses separated by commas'
            },
            {
                label: __('Subject'),
                fieldname: 'subject',
                fieldtype: 'Data',
                default: `Update from ${frm.doc.class_name}`,
                reqd: 1
            },
            {
                label: __('Message'),
                fieldname: 'message',
                fieldtype: 'Text Editor',
                reqd: 1
            },
            {
                label: __('Include Class Statistics'),
                fieldname: 'include_stats',
                fieldtype: 'Check',
                default: 1
            }
        ],
        primary_action_label: __('Send Email'),
        primary_action(values) {
            frappe.call({
                method: 'church.church.doctype.children_class.children_class.send_class_update',
                args: {
                    class_name: frm.doc.name,
                    recipients: values.recipients,
                    custom_emails: values.custom_emails,
                    subject: values.subject,
                    message: values.message,
                    include_stats: values.include_stats
                },
                callback: function(r) {
                    if (r.message) {
                        frappe.show_alert({
                            message: __('✅ Email sent successfully!'),
                            indicator: 'green'
                        }, 5);
                        d.hide();
                    }
                }
            });
        }
    });
    
    d.show();
}

// ==================== ANALYTICS DASHBOARD ====================
function show_class_analytics(frm) {
    frappe.route_options = {
        class_name: frm.doc.name
    };
    frappe.set_route('query-report', 'Children Class Analytics');
}

// ==================== QR CODE GENERATION ====================
function generate_asset_qr_codes(frm) {
    frappe.call({
        method: 'church.church.doctype.children_class.children_class.generate_asset_qr_codes',
        args: {
            class_name: frm.doc.name
        },
        freeze: true,
        freeze_message: __('🔲 Generating QR codes...'),
        callback: function(r) {
            if (r.message) {
                frm.reload_doc();
                frappe.show_alert({
                    message: __(`✅ Generated ${r.message.count} QR codes`),
                    indicator: 'green'
                }, 5);
            }
        }
    });
}

// ==================== PRINT CLASS ROSTER ====================
function print_class_roster(frm) {
    frappe.call({
        method: 'church.church.doctype.children_class.children_class.get_class_roster_html',
        args: {
            class_name: frm.doc.name
        },
        callback: function(r) {
            if (r.message) {
                const print_window = window.open('', '_blank');
                print_window.document.write(r.message);
                print_window.document.close();
                setTimeout(() => {
                    print_window.print();
                }, 250);
            }
        }
    });
}

// ==================== HELPER FUNCTIONS ====================
function format_currency(value) {
    return frappe.format(value, {fieldtype: 'Currency'});
}

function setup_field_watchers(frm) {
    // Watch for changes in member table
    frm.fields_dict.children_class_member.grid.grid_rows_by_docname = {};
}

function validate_promotion_path(frm) {
    if (frm.doc.next_class_group === frm.doc.name) {
        frappe.msgprint({
            title: __('Invalid Promotion Path'),
            message: __('A class cannot promote to itself'),
            indicator: 'red'
        });
        frm.set_value('next_class_group', '');
    }
}

function calculate_promotion_candidates(frm) {
    const members = frm.doc.children_class_member || [];
    const promotion_age = frm.doc.promotion_age;
    
    if (!promotion_age) return;
    
    const candidates = members.filter(m => m.age >= promotion_age);
    
    if (candidates.length > 0) {
        frappe.show_alert({
            message: __(`${candidates.length} children are eligible for promotion`),
            indicator: 'orange'
        }, 7);
    }
}

function process_eligible_promotions(frm, eligible_children) {
    frappe.confirm(
        __(`Are you sure you want to promote ${eligible_children.length} children to ${frm.doc.next_class_group}?`),
        () => {
            frappe.call({
                method: 'church.church.doctype.children_class.children_class.process_promotions',
                args: {
                    class_name: frm.doc.name,
                    children: eligible_children
                },
                freeze: true,
                freeze_message: __('Processing promotions...'),
                callback: function(r) {
                    if (r.message) {
                        frm.reload_doc();
                        frappe.show_alert({
                            message: __('✅ Promotions processed successfully!'),
                            indicator: 'green'
                        }, 5);
                    }
                }
            });
        }
    );
}