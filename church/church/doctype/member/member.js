// ============================================================================
// Member - Enhanced Client Script
// Optimized for automatic age calculation, demographic grouping, bulk operations,
// advanced analytics, profile management, and QR code generation
// ============================================================================

frappe.ui.form.on('Member', {
    // ========================================================================
    // FORM REFRESH
    // ========================================================================
    refresh: function(frm) {
        add_custom_buttons(frm);
        set_readonly_fields(frm);
        calculate_department_count(frm);
        add_dashboard_indicators(frm);
        show_birthday_alert(frm);
        validate_primary_department(frm);
    },

    // ========================================================================
    // DATE OF BIRTH CHANGED
    // ========================================================================
    date_of_birth: function(frm) {
        calculate_age(frm);
        assign_age_category(frm);
        assign_demographic_group(frm);
    },

    // ========================================================================
    // GENDER CHANGED
    // ========================================================================
    gender: function(frm) {
        assign_demographic_group(frm);
    },

    // ========================================================================
    // BEFORE SAVE
    // ========================================================================
    before_save: function(frm) {
        calculate_age(frm);
        assign_age_category(frm);
        assign_demographic_group(frm);
        calculate_department_count(frm);
        update_full_name(frm);
        // NOTE: QR generation is intentionally NOT called here.
        // Use the "Generate QR Code" button instead to avoid validation errors.
    },

    // ========================================================================
    // EMAIL VALIDATION
    // ========================================================================
    email: function(frm) {
        if (frm.doc.email && !validate_email(frm.doc.email)) {
            frappe.msgprint({
                title: __('Invalid Email'),
                indicator: 'red',
                message: __('Please enter a valid email address')
            });
            frm.set_value('email', '');
        }
    },

    // ========================================================================
    // PHONE NUMBER FORMATTING
    // ========================================================================
    mobile_phone: function(frm) {
        if (frm.doc.mobile_phone) {
            format_phone_number(frm, 'mobile_phone');
        }
    },

    alternative_phone: function(frm) {
        if (frm.doc.alternative_phone) {
            format_phone_number(frm, 'alternative_phone');
        }
    },

    // ========================================================================
    // NAME FIELDS - AUTO-UPDATE FULL NAME
    // ========================================================================
    first_name: function(frm) { update_full_name(frm); },
    middle_name: function(frm) { update_full_name(frm); },
    last_name: function(frm) { update_full_name(frm); },

    // ========================================================================
    // SETUP - CONFIGURE QUERIES
    // ========================================================================
    setup: function(frm) {
        frm.set_query('branch', function() {
            return { filters: { 'is_active': 1 } };
        });

        frm.set_query('parish', function() {
            return { filters: { 'is_active': 1 } };
        });
    }
});


// ============================================================================
// CHILD TABLE EVENTS - DEPARTMENTS
// ============================================================================

frappe.ui.form.on('Member Department', {
    departments_add: function(frm) {
        calculate_department_count(frm);
    },

    departments_remove: function(frm) {
        calculate_department_count(frm);
    },

    is_active: function(frm, cdt, cdn) {
        calculate_department_count(frm);
        validate_primary_department(frm);
    },

    is_primary: function(frm, cdt, cdn) {
        validate_primary_department(frm);
    },

    department: function(frm, cdt, cdn) {
        check_duplicate_departments(frm);
    }
});


// ============================================================================
// CORE CALCULATION FUNCTIONS
// ============================================================================

function set_readonly_fields(frm) {
    frm.set_df_property('full_name', 'read_only', 1);
    frm.set_df_property('age', 'read_only', 1);
    frm.set_df_property('category', 'read_only', 1);
    frm.set_df_property('demographic_group', 'read_only', 1);
    frm.set_df_property('department_count', 'read_only', 1);
}


function calculate_age(frm) {
    if (!frm.doc.date_of_birth) {
        frm.set_value('age', null);
        return;
    }

    const dob = new Date(frm.doc.date_of_birth);
    const today = new Date();

    let age = today.getFullYear() - dob.getFullYear();
    const month_diff = today.getMonth() - dob.getMonth();

    if (month_diff < 0 || (month_diff === 0 && today.getDate() < dob.getDate())) {
        age--;
    }

    age = Math.max(0, age);
    frm.set_value('age', age);

    frappe.show_alert({
        message: __('Age calculated: {0} years', [age]),
        indicator: 'green'
    }, 3);
}


function assign_age_category(frm) {
    if (!frm.doc.age && frm.doc.age !== 0) {
        frm.set_value('category', null);
        return;
    }

    let category;
    const age = frm.doc.age;

    if (age < 13) {
        category = "Child";
    } else if (age < 18) {
        category = "Teenager";
    } else if (age < 36) {
        category = "Youth";
    } else if (age < 60) {
        category = "Adult";
    } else {
        category = "Elder";
    }

    frm.set_value('category', category);
}


function assign_demographic_group(frm) {
    if (!frm.doc.age || !frm.doc.gender) return;

    frappe.call({
        method: "church.church.doctype.member.member.get_demographic_group",
        args: {
            age: frm.doc.age,
            gender: frm.doc.gender
        },
        callback: function(r) {
            if (r.message) {
                frm.set_value('demographic_group', r.message);
                frappe.show_alert({
                    message: __('Demographic group: {0}', [r.message]),
                    indicator: 'blue'
                }, 3);
            } else {
                frappe.show_alert({
                    message: __('No matching demographic group found'),
                    indicator: 'orange'
                }, 3);
            }
        }
    });
}


function calculate_department_count(frm) {
    if (!frm.doc.departments) {
        frm.set_value('department_count', 0);
        return;
    }

    const active_count = frm.doc.departments.filter(d => d.is_active).length;
    frm.set_value('department_count', active_count);
}


function update_full_name(frm) {
    let parts = [];

    if (frm.doc.first_name) parts.push(frm.doc.first_name);
    if (frm.doc.middle_name) parts.push(frm.doc.middle_name);
    if (frm.doc.last_name) parts.push(frm.doc.last_name);

    let full_name = parts.join(' ').trim();

    if (full_name && full_name !== frm.doc.full_name) {
        frm.set_value('full_name', full_name);
    }
}


// ============================================================================
// VALIDATION FUNCTIONS
// ============================================================================

function validate_primary_department(frm) {
    if (!frm.doc.departments || frm.doc.departments.length === 0) return;

    const primary_depts = frm.doc.departments.filter(d => d.is_primary && d.is_active);

    if (primary_depts.length > 1) {
        frappe.msgprint({
            title: __('Multiple Primary Departments'),
            indicator: 'red',
            message: __('Only one department can be marked as Primary. Please uncheck others.')
        });
    } else if (primary_depts.length === 0) {
        const first_active = frm.doc.departments.find(d => d.is_active);
        if (first_active) {
            frappe.model.set_value(first_active.doctype, first_active.name, 'is_primary', 1);
            frappe.show_alert({
                message: __('Auto-set {0} as Primary Department', [first_active.department]),
                indicator: 'blue'
            }, 5);
        }
    }
}


function check_duplicate_departments(frm) {
    if (!frm.doc.departments) return;

    const dept_names = frm.doc.departments.map(d => d.department).filter(Boolean);
    const unique_names = new Set(dept_names);

    if (dept_names.length !== unique_names.size) {
        frappe.msgprint({
            title: __('Duplicate Department'),
            indicator: 'red',
            message: __('Cannot assign the same department multiple times')
        });
    }
}


function validate_email(email) {
    const regex = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/;
    return regex.test(email);
}


function format_phone_number(frm, fieldname) {
    let phone = frm.doc[fieldname];
    if (!phone) return;

    phone = phone.replace(/[^\d+]/g, '');

    if (!phone.startsWith('+')) {
        if (phone.length === 10 || phone.length === 11) {
            phone = '+234' + phone.replace(/^0+/, '');
        } else {
            phone = '+' + phone;
        }
    }

    frm.set_value(fieldname, phone);
}


// ============================================================================
// DASHBOARD INDICATORS
// ============================================================================

function add_dashboard_indicators(frm) {
    if (!frm.doc || frm.is_new()) return;

    if (is_birthday_today(frm.doc.date_of_birth)) {
        frm.dashboard.add_indicator(__('🎂 Birthday Today!'), 'orange');
    }

    if (frm.doc.age !== null && frm.doc.age !== undefined) {
        frm.dashboard.add_indicator(
            __('Age: {0} years ({1})', [frm.doc.age, frm.doc.category || 'N/A']),
            'blue'
        );
    }

    if (frm.doc.department_count > 0) {
        frm.dashboard.add_indicator(
            __('🏢 Departments: {0}', [frm.doc.department_count]),
            'green'
        );
    }

    if (frm.doc.member_status) {
        const status_colors = {
            'Active': 'green',
            'Inactive': 'orange',
            'Transferred': 'blue',
            'Left': 'red'
        };
        frm.dashboard.add_indicator(
            frm.doc.member_status,
            status_colors[frm.doc.member_status] || 'grey'
        );
    }

    // QR indicator
    const has_qr = frm.doc.member_qr_code || frm.doc.personal_qr_code;
    frm.dashboard.add_indicator(
        has_qr ? __('🔲 QR Code Ready') : __('⚠️ No QR Code'),
        has_qr ? 'green' : 'orange'
    );
}


function show_birthday_alert(frm) {
    if (is_birthday_today(frm.doc.date_of_birth)) {
        const age = frm.doc.age || '?';
        frappe.show_alert({
            message: __('🎉 Today is {0}\'s {1}th birthday!', [frm.doc.first_name || frm.doc.full_name, age]),
            indicator: 'blue'
        }, 10);
    }
}


function is_birthday_today(date_of_birth) {
    if (!date_of_birth) return false;

    const dob = new Date(date_of_birth);
    const today = new Date();

    return dob.getDate() === today.getDate() &&
           dob.getMonth() === today.getMonth();
}


// ============================================================================
// CUSTOM BUTTONS
// ============================================================================

function add_custom_buttons(frm) {
    if (frm.doc.__islocal) return;

    // ── ACTIONS GROUP ──────────────────────────────────────────────────────

    // View Profile
    frm.add_custom_button(__('📋 View Profile'), function() {
        view_member_profile(frm);
    }, __('Actions'));

    // ── QR CODE BUTTON (FIXED) ─────────────────────────────────────────────
    // Calls the server directly WITHOUT triggering form save, so required-
    // field validation (Status, Gender, Parish, etc.) is never triggered.
    const has_qr = frm.doc.member_qr_code || frm.doc.personal_qr_code;

    frm.add_custom_button(
        has_qr ? __('🔲 View QR Code') : __('🔲 Generate QR Code'),
        function() {
            if (has_qr) {
                view_qr_code(frm);
            } else {
                generate_qr_code(frm);
            }
        },
        __('Actions')
    );

    // Birthday wish (only on birthday)
    if (is_birthday_today(frm.doc.date_of_birth)) {
        frm.add_custom_button(__('🎂 Send Birthday Wish'), function() {
            send_birthday_wish(frm);
        }, __('Actions')).addClass('btn-primary');
    }

    // ── PAGE MENU ──────────────────────────────────────────────────────────

    frm.page.add_menu_item(__('📄 Export to PDF'), function() {
        export_member_to_pdf(frm);
    });

    // ── ADMIN ACTIONS ──────────────────────────────────────────────────────

    if (frappe.user.has_role('System Manager')) {
        frm.page.add_menu_item(__('📊 Export All Members to Excel'), function() {
            export_all_members_to_excel();
        });

        frm.page.add_menu_item(__('🔄 Reclassify All Members'), function() {
            reclassify_all_members();
        });

        frm.page.add_menu_item(__('📈 View Member Statistics'), function() {
            view_member_statistics();
        });
    }
}


// ============================================================================
// QR CODE FUNCTIONS - FIXED
// ============================================================================

function generate_qr_code(frm) {
    /**
     * FIXED: Calls server method directly with frappe.call().
     * Does NOT call frm.save() first, so validation errors for required fields
     * (Member Status, Gender, Parish) are never triggered.
     *
     * The server-side generate_personal_qr() uses frappe.db.set_value()
     * which writes directly to the database, bypassing the Document
     * validation chain entirely.
     */
    frappe.show_alert({
        message: __('Generating QR code...'),
        indicator: 'blue'
    }, 3);

    frappe.call({
        method: 'church.church.doctype.member.member.generate_personal_qr',
        args: {
            member_name: frm.doc.name
        },
        callback: function(r) {
            if (!r.message) {
                frappe.msgprint({
                    title: __('QR Generation Failed'),
                    indicator: 'red',
                    message: __('No response from server. Please check error logs.')
                });
                return;
            }

            const res = r.message;

            if (res.status === 'success' || res.status === 'exists') {
                frappe.show_alert({
                    message: res.status === 'success'
                        ? __('✅ QR Code generated successfully!')
                        : __('ℹ️ QR Code already exists'),
                    indicator: 'green'
                }, 5);

                // Reload the form so the QR image and dashboard indicator refresh
                frm.reload_doc();

            } else {
                frappe.msgprint({
                    title: __('QR Generation Failed'),
                    indicator: 'red',
                    message: res.message || __('Unknown error. Please check error logs.')
                });
            }
        }
    });
}


function view_qr_code(frm) {
    /**
     * Show existing QR code in a dialog
     */
    const qr_url = frm.doc.member_qr_code || frm.doc.personal_qr_code;

    if (!qr_url) {
        frappe.msgprint({
            title: __('No QR Code'),
            indicator: 'orange',
            message: __('No QR code found. Click "Generate QR Code" to create one.')
        });
        return;
    }

    let d = new frappe.ui.Dialog({
        title: __('QR Code — {0}', [frm.doc.full_name]),
        fields: [
            {
                fieldtype: 'HTML',
                fieldname: 'qr_html'
            }
        ],
        primary_action_label: __('Download'),
        primary_action: function() {
            const link = document.createElement('a');
            link.href = qr_url;
            link.download = `${frm.doc.name}_qr.png`;
            link.click();
        }
    });

    d.fields_dict.qr_html.$wrapper.html(`
        <div style="text-align: center; padding: 30px;">
            <img src="${qr_url}"
                 style="width: 250px; height: 250px; border: 2px solid #eee; border-radius: 8px;"
                 alt="Member QR Code">
            <p style="margin-top: 15px; color: #7f8c8d; font-size: 13px;">
                Scan this code to check in ${frappe.utils.escape_html(frm.doc.full_name)}
            </p>
        </div>
    `);

    d.show();
}


// ============================================================================
// ACTION FUNCTIONS
// ============================================================================

function view_member_profile(frm) {
    frappe.show_alert({
        message: __('Loading profile...'),
        indicator: 'blue'
    }, 2);

    frappe.call({
        method: 'church.church.doctype.member.member.get_member_profile_html',
        args: { member_name: frm.doc.name },
        callback: function(r) {
            if (r.message) {
                let d = new frappe.ui.Dialog({
                    title: __('Member Profile — {0}', [frm.doc.full_name]),
                    size: 'extra-large',
                    fields: [{ fieldtype: 'HTML', fieldname: 'profile_html' }],
                    primary_action_label: __('Print Profile'),
                    primary_action: function() {
                        print_profile(r.message);
                    },
                    secondary_action_label: __('Download PDF'),
                    secondary_action: function() {
                        download_profile_pdf(r.message, frm.doc.full_name);
                    }
                });

                d.fields_dict.profile_html.$wrapper.html(r.message);
                d.show();
            }
        }
    });
}


function send_birthday_wish(frm) {
    frappe.confirm(
        __('Send birthday wish to {0}?', [frm.doc.full_name]),
        function() {
            frappe.call({
                method: 'church.church.doctype.member.member.send_birthday_wishes_manual',
                args: { member_name: frm.doc.name },
                freeze: true,
                freeze_message: __('Sending birthday wish...'),
                callback: function(r) {
                    if (r.message && r.message.success) {
                        frappe.msgprint({
                            title: __('🎉 Birthday Wish Sent'),
                            indicator: 'green',
                            message: __('Birthday wish sent successfully to {0}', [frm.doc.email || 'member'])
                        });
                    } else {
                        frappe.msgprint({
                            title: __('Failed'),
                            indicator: 'red',
                            message: r.message ? r.message.message : __('No email address found')
                        });
                    }
                }
            });
        }
    );
}


function export_all_members_to_excel() {
    frappe.show_alert({
        message: __('Generating Excel file...'),
        indicator: 'blue'
    }, 3);

    frappe.call({
        method: 'church.church.doctype.member.member.export_members_to_excel',
        freeze: true,
        freeze_message: __('Generating Excel export...'),
        callback: function(r) {
            if (r.message && r.message.success) {
                const link = document.createElement('a');
                link.href = 'data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,' + r.message.file_content;
                link.download = r.message.filename;
                link.click();

                frappe.show_alert({
                    message: __('✅ Excel file downloaded: {0}', [r.message.filename]),
                    indicator: 'green'
                }, 5);
            } else {
                frappe.msgprint({
                    title: __('Export Failed'),
                    indicator: 'red',
                    message: __('Failed to generate Excel file')
                });
            }
        }
    });
}


function reclassify_all_members() {
    frappe.confirm(
        __('This will recalculate age and demographic group for ALL members in the background. Continue?'),
        function() {
            frappe.call({
                method: 'church.church.doctype.member.member.reclassify_members',
                freeze: true,
                freeze_message: __('Starting background reclassification...'),
                callback: function(r) {
                    if (r.message && r.message.success) {
                        frappe.msgprint({
                            title: __('Reclassification Started'),
                            indicator: 'green',
                            message: r.message.message
                        });
                    }
                }
            });
        }
    );
}


function view_member_statistics() {
    frappe.show_alert({
        message: __('Loading statistics...'),
        indicator: 'blue'
    }, 2);

    frappe.call({
        method: 'church.church.doctype.member.member.get_member_statistics',
        callback: function(r) {
            if (r.message && r.message.success) {
                show_statistics_dialog(r.message.statistics);
            }
        }
    });
}


function show_statistics_dialog(stats) {
    let html = `
        <div style="padding: 20px;">
            <h3 style="margin-top: 0;">📊 Member Statistics</h3>

            <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 15px; margin: 20px 0;">
                <div style="background: linear-gradient(135deg, #667eea, #764ba2); padding: 20px; border-radius: 8px; color: white;">
                    <div style="font-size: 32px; font-weight: bold;">${stats.total}</div>
                    <div>Total Members</div>
                </div>
                <div style="background: linear-gradient(135deg, #f093fb, #f5576c); padding: 20px; border-radius: 8px; color: white;">
                    <div style="font-size: 32px; font-weight: bold;">${stats.recent_joiners}</div>
                    <div>Recent Joiners (30 days)</div>
                </div>
            </div>

            <h4>By Gender</h4>
            <table class="table table-bordered">
                ${Object.entries(stats.by_gender).map(([gender, count]) => `
                    <tr><td>${gender}</td><td><strong>${count}</strong></td></tr>
                `).join('')}
            </table>

            <h4>By Demographic Group</h4>
            <table class="table table-bordered">
                ${Object.entries(stats.by_demographic).map(([demo, count]) => `
                    <tr><td>${demo}</td><td><strong>${count}</strong></td></tr>
                `).join('')}
            </table>

            <h4>Age Distribution</h4>
            <table class="table table-bordered">
                ${Object.entries(stats.age_distribution).map(([range, count]) => `
                    <tr><td>${range}</td><td><strong>${count}</strong></td></tr>
                `).join('')}
            </table>

            <div style="background: #fff3cd; padding: 15px; border-radius: 8px; margin-top: 20px;">
                <h5 style="margin-top: 0;">⚠️ Data Quality Alerts</h5>
                <ul style="margin: 0;">
                    <li><strong>${stats.no_contact}</strong> members without contact info</li>
                    <li><strong>${stats.incomplete_profiles}</strong> incomplete profiles</li>
                </ul>
            </div>
        </div>
    `;

    let d = new frappe.ui.Dialog({
        title: __('Member Statistics'),
        size: 'large',
        fields: [{ fieldtype: 'HTML', fieldname: 'stats_html' }]
    });

    d.fields_dict.stats_html.$wrapper.html(html);
    d.show();
}


function print_profile(html) {
    let printWindow = window.open('', '', 'height=600,width=800');
    printWindow.document.write(html);
    printWindow.document.close();
    printWindow.print();
}


function download_profile_pdf(html, member_name) {
    frappe.msgprint({
        title: __('PDF Export'),
        message: __('PDF export feature coming soon! Use Print for now.')
    });
}


function export_member_to_pdf(frm) {
    frappe.msgprint({
        title: __('PDF Export'),
        message: __('Single member PDF export coming soon!')
    });
}


// ============================================================================
// KEYBOARD SHORTCUTS
// ============================================================================

frappe.ui.keys.add_shortcut({
    shortcut: 'ctrl+p',
    action: () => {
        if (cur_frm && cur_frm.doctype === 'Member' && !cur_frm.is_new()) {
            view_member_profile(cur_frm);
        }
    },
    description: __('View Member Profile'),
    page: 'Form/Member'
});

frappe.ui.keys.add_shortcut({
    shortcut: 'ctrl+shift+q',
    action: () => {
        if (cur_frm && cur_frm.doctype === 'Member' && !cur_frm.is_new()) {
            const has_qr = cur_frm.doc.member_qr_code || cur_frm.doc.personal_qr_code;
            if (has_qr) {
                view_qr_code(cur_frm);
            } else {
                generate_qr_code(cur_frm);
            }
        }
    },
    description: __('Generate / View QR Code'),
    page: 'Form/Member'
});

frappe.ui.keys.add_shortcut({
    shortcut: 'ctrl+shift+s',
    action: () => {
        if (cur_frm && cur_frm.doctype === 'Member' && frappe.user.has_role('System Manager')) {
            view_member_statistics();
        }
    },
    description: __('View Member Statistics'),
    page: 'Form/Member'
});