// Copyright (c) 2026, kunle and contributors
// For license information, please see license.txt

// -*- coding: utf-8 -*-
/**
 * Smart Attendance QR Code - Client Side
 * Add to Member.js or as separate client script
 */

frappe.ui.form.on('Member', {
    refresh: function(frm) {
        // Only show buttons for saved documents
        if (!frm.is_new()) {
            add_qr_buttons(frm);
        }
    }
});

function add_qr_buttons(frm) {
    // Button: Generate QR Code
    frm.add_custom_button(__('Generate QR Code'), function() {
        generate_qr_code(frm);
    }, __('QR Actions'));
    
    // Button: View QR Code
    if (frm.doc.personal_qr_code) {
        frm.add_custom_button(__('View QR Code'), function() {
            view_qr_code(frm);
        }, __('QR Actions'));
        
        frm.add_custom_button(__('Download QR Code'), function() {
            download_qr_code(frm);
        }, __('QR Actions'));
        
        frm.add_custom_button(__('Print QR Badge'), function() {
            print_qr_badge(frm);
        }, __('QR Actions'));
    }
    
    // Button: Regenerate QR Code
    if (frm.doc.personal_qr_code) {
        frm.add_custom_button(__('Regenerate QR'), function() {
            regenerate_qr_code(frm);
        }, __('QR Actions'));
    }
}

function generate_qr_code(frm) {
    frappe.call({
        method: 'church.church.doctype.member.member.generate_personal_qr_code',
        args: {
            member_name: frm.doc.name
        },
        freeze: true,
        freeze_message: __('Generating QR Code...'),
        callback: function(r) {
            if (r.message && r.message.success) {
                frappe.show_alert({
                    message: r.message.message,
                    indicator: 'green'
                }, 5);
                
                frm.reload_doc();
                
                // Auto-show QR code
                setTimeout(() => {
                    view_qr_code(frm);
                }, 500);
            } else {
                frappe.msgprint({
                    title: __('Error'),
                    message: r.message.error || __('Failed to generate QR code'),
                    indicator: 'red'
                });
            }
        }
    });
}

function view_qr_code(frm) {
    if (!frm.doc.personal_qr_code) {
        frappe.msgprint(__('QR code not generated yet. Click "Generate QR Code" first.'));
        return;
    }
    
    // Create beautiful QR display dialog
    let d = new frappe.ui.Dialog({
        title: __('Personal QR Code - {0}', [frm.doc.full_name]),
        size: 'large',
        fields: [
            {
                fieldtype: 'HTML',
                fieldname: 'qr_display',
                options: get_qr_display_html(frm)
            }
        ],
        primary_action_label: __('Download'),
        primary_action: function() {
            download_qr_code(frm);
        },
        secondary_action_label: __('Print Badge'),
        secondary_action: function() {
            print_qr_badge(frm);
        }
    });
    
    d.show();
}

function get_qr_display_html(frm) {
    return `
        <div style="text-align: center; padding: 30px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 15px;">
            <div style="background: white; padding: 30px; border-radius: 12px; display: inline-block; box-shadow: 0 8px 30px rgba(0,0,0,0.2);">
                <img src="${frm.doc.personal_qr_code}" 
                     style="width: 300px; height: 300px; display: block;" 
                     alt="QR Code">
                
                <div style="margin-top: 20px; padding-top: 20px; border-top: 2px solid #ecf0f1;">
                    <h3 style="margin: 10px 0; color: #2c3e50; font-size: 24px;">
                        ${frm.doc.full_name}
                    </h3>
                    <p style="margin: 5px 0; color: #7f8c8d; font-size: 16px;">
                        Member ID: ${frm.doc.name}
                    </p>
                    <p style="margin: 5px 0; color: #7f8c8d; font-size: 14px;">
                        ${frm.doc.demographic_group || 'Member'} • ${frm.doc.branch || 'Church'}
                    </p>
                </div>
            </div>
            
            <div style="margin-top: 25px; color: white; font-size: 14px;">
                <p style="margin: 5px 0;">📱 Scan this code for quick check-in</p>
                <p style="margin: 5px 0; opacity: 0.8;">Generated: ${frappe.datetime.now_datetime()}</p>
            </div>
        </div>
    `;
}

function download_qr_code(frm) {
    window.open(
        `/api/method/church.church.doctype.member.member.download_member_qr?member_name=${frm.doc.name}`,
        '_blank'
    );
    
    frappe.show_alert({
        message: __('Downloading QR Code...'),
        indicator: 'blue'
    }, 3);
}

function print_qr_badge(frm) {
    let badge_html = `
        <!DOCTYPE html>
        <html>
        <head>
            <title>QR Badge - ${frm.doc.full_name}</title>
            <style>
                @page {
                    size: 4in 6in;
                    margin: 0;
                }
                body {
                    margin: 0;
                    padding: 0;
                    font-family: 'Segoe UI', Arial, sans-serif;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    min-height: 100vh;
                    background: white;
                }
                .badge {
                    width: 3.5in;
                    height: 5.5in;
                    border: 3px solid #667eea;
                    border-radius: 20px;
                    padding: 30px;
                    text-align: center;
                    background: linear-gradient(135deg, #f8f9fa 0%, #ffffff 100%);
                    box-shadow: 0 4px 20px rgba(0,0,0,0.1);
                }
                .badge-header {
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    padding: 20px;
                    border-radius: 12px;
                    margin-bottom: 20px;
                }
                .badge-header h1 {
                    margin: 0;
                    font-size: 28px;
                }
                .badge-header p {
                    margin: 5px 0 0 0;
                    font-size: 14px;
                    opacity: 0.9;
                }
                .qr-container {
                    background: white;
                    padding: 20px;
                    border-radius: 12px;
                    margin: 20px 0;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                }
                .qr-container img {
                    width: 250px;
                    height: 250px;
                }
                .member-info {
                    margin-top: 20px;
                    color: #2c3e50;
                }
                .member-info h2 {
                    margin: 10px 0;
                    font-size: 24px;
                    color: #667eea;
                }
                .member-info p {
                    margin: 5px 0;
                    font-size: 14px;
                    color: #7f8c8d;
                }
                .instructions {
                    margin-top: 20px;
                    padding: 15px;
                    background: #fff3cd;
                    border-radius: 8px;
                    font-size: 12px;
                    color: #856404;
                }
                @media print {
                    body {
                        background: white;
                    }
                    .badge {
                        box-shadow: none;
                    }
                }
            </style>
        </head>
        <body>
            <div class="badge">
                <div class="badge-header">
                    <h1>⛪ Member Badge</h1>
                    <p>${frm.doc.branch || 'Church'}</p>
                </div>
                
                <div class="qr-container">
                    <img src="${frm.doc.personal_qr_code}" alt="QR Code">
                </div>
                
                <div class="member-info">
                    <h2>${frm.doc.full_name}</h2>
                    <p><strong>ID:</strong> ${frm.doc.name}</p>
                    <p><strong>Group:</strong> ${frm.doc.demographic_group || 'Member'}</p>
                </div>
                
                <div class="instructions">
                    📱 Scan this QR code for quick check-in at church services and events
                </div>
            </div>
        </body>
        </html>
    `;
    
    // Open print preview
    let print_window = window.open('', '_blank');
    print_window.document.write(badge_html);
    print_window.document.close();
    
    // Auto-print after load
    print_window.onload = function() {
        print_window.print();
    };
}

function regenerate_qr_code(frm) {
    frappe.confirm(
        __('Are you sure you want to regenerate the QR code? The old QR code will no longer work.'),
        function() {
            frappe.call({
                method: 'church.church.doctype.member.member.regenerate_member_qr',
                args: {
                    member_name: frm.doc.name
                },
                freeze: true,
                freeze_message: __('Regenerating QR Code...'),
                callback: function(r) {
                    if (r.message && r.message.success) {
                        frappe.show_alert({
                            message: __('QR Code regenerated successfully'),
                            indicator: 'green'
                        }, 5);
                        
                        frm.reload_doc();
                    } else {
                        frappe.msgprint({
                            title: __('Error'),
                            message: r.message.error || __('Failed to regenerate QR code'),
                            indicator: 'red'
                        });
                    }
                }
            });
        }
    );
}

// ============================================================================
// BULK QR GENERATION
// Add to Member List view
// ============================================================================

frappe.listview_settings['Member'] = {
    onload: function(listview) {
        listview.page.add_inner_button(__('Bulk Generate QR Codes'), function() {
            bulk_generate_qr_codes(listview);
        });
    }
};

function bulk_generate_qr_codes(listview) {
    let selected = listview.get_checked_items();
    
    if (selected.length === 0) {
        frappe.msgprint(__('Please select members first'));
        return;
    }
    
    frappe.confirm(
        __('Generate QR codes for {0} selected members?', [selected.length]),
        function() {
            let member_names = selected.map(item => item.name);
            
            frappe.call({
                method: 'church.church.doctype.member.member.bulk_generate_qr_codes',
                args: {
                    filters: {
                        'name': ['in', member_names]
                    }
                },
                freeze: true,
                freeze_message: __('Generating QR codes...'),
                callback: function(r) {
                    if (r.message && r.message.success) {
                        frappe.show_alert({
                            message: __('Generated {0} QR codes ({1} failed)', 
                                [r.message.generated, r.message.failed]),
                            indicator: 'green'
                        }, 5);
                        
                        listview.refresh();
                    } else {
                        frappe.msgprint({
                            title: __('Error'),
                            message: r.message.error || __('Failed to generate QR codes'),
                            indicator: 'red'
                        });
                    }
                }
            });
        }
    );
}