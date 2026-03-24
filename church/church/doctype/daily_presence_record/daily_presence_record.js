// File: attendance_management/attendance_management/doctype/daily_presence_record/daily_presence_record.js

frappe.ui.form.on('Daily Presence Record', {
    refresh: function(frm) {
        // Color code status
        if (frm.doc.presence_status === 'Present') {
            frm.dashboard.set_headline_alert('Present', 'green');
        } else if (frm.doc.presence_status === 'Absent') {
            frm.dashboard.set_headline_alert('Absent', 'red');
        } else if (frm.doc.presence_status === 'Half Day') {
            frm.dashboard.set_headline_alert('Half Day', 'orange');
        } else if (frm.doc.presence_status === 'Late') {
            frm.dashboard.set_headline_alert('Late', 'yellow');
        }

        // Show duration indicator
        if (frm.doc.total_duration_minutes) {
            const hours = Math.floor(frm.doc.total_duration_minutes / 60);
            const minutes = frm.doc.total_duration_minutes % 60;
            frm.dashboard.add_indicator(
                __('Duration: {0}h {1}m', [hours, minutes]),
                frm.doc.is_overtime ? 'blue' : 'grey'
            );
        }

        // Show late/early indicators
        if (frm.doc.late_arrival) {
            frm.dashboard.add_indicator(__('Late Arrival'), 'orange');
        }
        if (frm.doc.early_departure) {
            frm.dashboard.add_indicator(__('Early Departure'), 'red');
        }

        // Custom buttons
        if (!frm.is_new()) {
            // Mark check-out button
            if (frm.doc.check_in_time && !frm.doc.check_out_time) {
                frm.add_custom_button(__('Mark Check-Out'), function() {
                    mark_checkout(frm);
                });
            }

            // Update status button
            frm.add_custom_button(__('Update Status'), function() {
                update_status_dialog(frm);
            }, __('Actions'));

            // View person button
            if (frm.doc.person_registry) {
                frm.add_custom_button(__('View Person'), function() {
                    frappe.set_route('Form', 'Person Registry', frm.doc.person_registry);
                }, __('Actions'));
            }

            // View logs button
            frm.add_custom_button(__('View Presence Logs'), function() {
                view_presence_logs(frm);
            }, __('Actions'));

            // Monthly summary button
            frm.add_custom_button(__('Monthly Summary'), function() {
                show_monthly_summary(frm);
            }, __('Reports'));
        }

        // Calculate and display attendance statistics
        if (frm.doc.person_registry) {
            load_attendance_statistics(frm);
        }
    },

    person_registry: function(frm) {
        // Auto-fill person details
        if (frm.doc.person_registry) {
            frappe.call({
                method: 'frappe.client.get',
                args: {
                    doctype: 'Person Registry',
                    name: frm.doc.person_registry
                },
                callback: function(r) {
                    if (r.message) {
                        frm.set_value('person_name', r.message.full_name);
                        frm.set_value('organization_unit', r.message.organization_unit);
                        frm.set_value('registry_type', r.message.registry_type);
                    }
                }
            });
        }
    },

    check_in_time: function(frm) {
        calculate_duration(frm);
    },

    check_out_time: function(frm) {
        calculate_duration(frm);
    },

    attendance_date: function(frm) {
        // Check for duplicate
        if (frm.doc.person_registry && frm.doc.attendance_date) {
            frappe.call({
                method: 'frappe.client.get_count',
                args: {
                    doctype: 'Daily Presence Record',
                    filters: {
                        person_registry: frm.doc.person_registry,
                        attendance_date: frm.doc.attendance_date,
                        name: ['!=', frm.doc.name]
                    }
                },
                callback: function(r) {
                    if (r.message > 0) {
                        frappe.msgprint({
                            title: __('Duplicate Record'),
                            indicator: 'orange',
                            message: __('An attendance record already exists for this person on this date')
                        });
                    }
                }
            });
        }
    }
});

// ==================== CUSTOM FUNCTIONS ====================

function calculate_duration(frm) {
    if (frm.doc.check_in_time && frm.doc.check_out_time) {
        frappe.call({
            method: 'church.church.doctype.daily_presence_record.daily_presence_record.calculate_duration',
            args: {
                check_in_time: frm.doc.check_in_time,
                check_out_time: frm.doc.check_out_time
            },
            callback: function(r) {
                if (r.message) {
                    frm.set_value('total_duration_minutes', r.message);
                }
            }
        });
    }
}

function mark_checkout(frm) {
    const d = new frappe.ui.Dialog({
        title: __('Mark Check-Out'),
        fields: [
            {
                label: __('Check-Out Time'),
                fieldname: 'check_out_time',
                fieldtype: 'Time',
                default: frappe.datetime.now_time(),
                reqd: 1
            },
            {
                label: __('Location'),
                fieldname: 'checkpoint_location',
                fieldtype: 'Link',
                options: 'Checkpoint Location'
            }
        ],
        primary_action_label: __('Mark Check-Out'),
        primary_action: function(values) {
            frappe.call({
                method: 'church.church.doctype.daily_presence_record.daily_presence_record.mark_check_out',
                args: {
                    registry_id: frm.doc.person_registry,
                    attendance_date: frm.doc.attendance_date,
                    check_out_time: values.check_out_time,
                    checkpoint_location: values.checkpoint_location
                },
                freeze: true,
                callback: function(r) {
                    if (r.message && r.message.success) {
                        frappe.show_alert({
                            message: __('Check-out recorded: {0}', [r.message.duration_hours + 'h']),
                            indicator: 'green'
                        }, 5);
                        d.hide();
                        frm.reload_doc();
                    }
                }
            });
        }
    });

    d.show();
}

function update_status_dialog(frm) {
    const d = new frappe.ui.Dialog({
        title: __('Update Attendance Status'),
        fields: [
            {
                label: __('New Status'),
                fieldname: 'new_status',
                fieldtype: 'Select',
                options: 'Present\nAbsent\nHalf Day\nOn Leave\nWork From Home\nLate',
                default: frm.doc.presence_status,
                reqd: 1
            },
            {
                label: __('Reason for Change'),
                fieldname: 'remarks',
                fieldtype: 'Small Text',
                reqd: 1
            }
        ],
        primary_action_label: __('Update'),
        primary_action: function(values) {
            frappe.call({
                method: 'church.church.doctype.daily_presence_record.daily_presence_record.update_attendance_status',
                args: {
                    record_id: frm.doc.name,
                    new_status: values.new_status,
                    remarks: values.remarks
                },
                freeze: true,
                callback: function(r) {
                    if (r.message && r.message.success) {
                        frappe.show_alert({
                            message: __('Status updated successfully'),
                            indicator: 'green'
                        }, 5);
                        d.hide();
                        frm.reload_doc();
                    }
                }
            });
        }
    });

    d.show();
}

function view_presence_logs(frm) {
    frappe.route_options = {
        'person_registry': frm.doc.person_registry,
        'log_date': frm.doc.attendance_date
    };
    frappe.set_route('List', 'Presence Log');
}

function show_monthly_summary(frm) {
    const date = frappe.datetime.str_to_obj(frm.doc.attendance_date);
    const year = date.getFullYear();
    const month = date.getMonth() + 1;

    frappe.call({
        method: 'church.church.doctype.daily_presence_record.daily_presence_record.get_monthly_summary',
        args: {
            registry_id: frm.doc.person_registry,
            year: year,
            month: month
        },
        callback: function(r) {
            if (r.message && r.message.success) {
                show_monthly_summary_dialog(r.message);
            }
        }
    });
}

function show_monthly_summary_dialog(data) {
    const stats = data.statistics;
    
    const html = `
        <div style="padding: 20px;">
            <h3>${data.person_name} - ${data.month_name} ${data.year}</h3>
            <br>
            <table class="table table-bordered">
                <tr>
                    <td><strong>Total Days:</strong></td>
                    <td>${stats.total_days}</td>
                </tr>
                <tr>
                    <td><strong>Present Days:</strong></td>
                    <td style="color: green;">${stats.present_days}</td>
                </tr>
                <tr>
                    <td><strong>Absent Days:</strong></td>
                    <td style="color: red;">${stats.absent_days}</td>
                </tr>
                <tr>
                    <td><strong>Not Marked:</strong></td>
                    <td style="color: orange;">${stats.not_marked}</td>
                </tr>
                <tr>
                    <td><strong>Late Days:</strong></td>
                    <td>${stats.late_days}</td>
                </tr>
                <tr>
                    <td><strong>Total Hours:</strong></td>
                    <td>${stats.total_hours}h</td>
                </tr>
                <tr>
                    <td><strong>Average Hours/Day:</strong></td>
                    <td>${stats.average_hours_per_day}h</td>
                </tr>
                <tr>
                    <td><strong>Attendance Rate:</strong></td>
                    <td><strong style="color: ${stats.attendance_rate >= 80 ? 'green' : 'red'};">${stats.attendance_rate}%</strong></td>
                </tr>
            </table>
        </div>
    `;

    const d = new frappe.ui.Dialog({
        title: __('Monthly Summary'),
        size: 'large'
    });

    d.$body.html(html);
    d.show();
}

function load_attendance_statistics(frm) {
    frappe.call({
        method: 'church.church.doctype.daily_presence_record.daily_presence_record.get_person_attendance_history',
        args: {
            registry_id: frm.doc.person_registry,
            from_date: frappe.datetime.add_days(frm.doc.attendance_date, -30),
            to_date: frm.doc.attendance_date
        },
        callback: function(r) {
            if (r.message && r.message.success) {
                const stats = r.message.statistics;
                
                frm.dashboard.add_comment(
                    `<strong>30-Day Statistics:</strong><br>
                    Attendance Rate: ${stats.attendance_rate}% | 
                    Present: ${stats.present_days} | 
                    Absent: ${stats.absent_days} | 
                    Late: ${stats.late_arrivals}`,
                    'blue'
                );
            }
        }
    });
}

// ==================== LIST VIEW SETTINGS ====================

frappe.listview_settings['Daily Presence Record'] = {
    onload: function(listview) {
        // Add bulk absent marking
        listview.page.add_inner_button(__('Mark Bulk Absent'), function() {
            mark_bulk_absent_dialog(listview);
        }, __('Actions'));

        // Add export button
        listview.page.add_inner_button(__('Export Report'), function() {
            export_attendance_report(listview);
        }, __('Actions'));

        // Filter shortcuts
        listview.page.add_inner_button(__('Today'), function() {
            listview.filter_area.add([
                ['Daily Presence Record', 'attendance_date', '=', frappe.datetime.get_today()]
            ]);
        }, __('Filters'));

        listview.page.add_inner_button(__('This Week'), function() {
            listview.filter_area.add([
                ['Daily Presence Record', 'attendance_date', 'between', 
                    [frappe.datetime.week_start(), frappe.datetime.week_end()]]
            ]);
        }, __('Filters'));

        listview.page.add_inner_button(__('This Month'), function() {
            listview.filter_area.add([
                ['Daily Presence Record', 'attendance_date', 'between', 
                    [frappe.datetime.month_start(), frappe.datetime.month_end()]]
            ]);
        }, __('Filters'));
    },

    // Custom indicators
    get_indicator: function(doc) {
        const status_colors = {
            'Present': ['Present', 'green', 'presence_status,=,Present'],
            'Absent': ['Absent', 'red', 'presence_status,=,Absent'],
            'Half Day': ['Half Day', 'orange', 'presence_status,=,Half Day'],
            'Late': ['Late', 'yellow', 'presence_status,=,Late'],
            'On Leave': ['On Leave', 'blue', 'presence_status,=,On Leave'],
            'Work From Home': ['WFH', 'purple', 'presence_status,=,Work From Home']
        };

        return status_colors[doc.presence_status] || ['Unknown', 'grey'];
    },

    // Custom formatters
    formatters: {
        total_duration_minutes: function(value) {
            if (!value) return '--';
            const hours = Math.floor(value / 60);
            const minutes = value % 60;
            return `${hours}h ${minutes}m`;
        }
    }
};

function mark_bulk_absent_dialog(listview) {
    const d = new frappe.ui.Dialog({
        title: __('Mark Bulk Absent'),
        fields: [
            {
                label: __('Date'),
                fieldname: 'attendance_date',
                fieldtype: 'Date',
                default: frappe.datetime.get_today(),
                reqd: 1
            },
            {
                label: __('Organization Unit'),
                fieldname: 'organization_unit',
                fieldtype: 'Link',
                options: 'Organization Unit'
            },
            {
                label: __('Remarks'),
                fieldname: 'remarks',
                fieldtype: 'Small Text'
            }
        ],
        primary_action_label: __('Mark Absent'),
        primary_action: function(values) {
            // Get all persons from selected unit
            frappe.call({
                method: 'church.church.doctype.daily_presence_record.daily_presence_record.mark_bulk_absent',
                args: values,
                freeze: true,
                freeze_message: __('Marking absent...'),
                callback: function(r) {
                    if (r.message && r.message.success) {
                        frappe.msgprint({
                            title: __('Bulk Absent Marking Complete'),
                            indicator: 'green',
                            message: __('Marked {0} persons as absent', [r.message.marked_count])
                        });
                        d.hide();
                        listview.refresh();
                    }
                }
            });
        }
    });

    d.show();
}

function export_attendance_report(listview) {
    const d = new frappe.ui.Dialog({
        title: __('Export Attendance Report'),
        fields: [
            {
                label: __('From Date'),
                fieldname: 'from_date',
                fieldtype: 'Date',
                default: frappe.datetime.month_start(),
                reqd: 1
            },
            {
                label: __('To Date'),
                fieldname: 'to_date',
                fieldtype: 'Date',
                default: frappe.datetime.month_end(),
                reqd: 1
            },
            {
                label: __('Format'),
                fieldname: 'format',
                fieldtype: 'Select',
                options: 'Excel\nPDF',
                default: 'Excel',
                reqd: 1
            }
        ],
        primary_action_label: __('Export'),
        primary_action: function(values) {
            const url = `/api/method/church.church.doctype.daily_presence_record.daily_presence_record.export_attendance_report?from_date=${values.from_date}&to_date=${values.to_date}&format=${values.format.toLowerCase()}`;
            window.open(url, '_blank');
            d.hide();
        }
    });

    d.show();
}

// ==================== CALENDAR VIEW ====================

frappe.views.calendar['Daily Presence Record'] = {
    field_map: {
        start: 'attendance_date',
        end: 'attendance_date',
        id: 'name',
        title: 'person_name',
        status: 'presence_status',
        allDay: true
    },
    get_events_method: 'church.church.doctype.daily_presence_record.daily_presence_record.get_events'
};