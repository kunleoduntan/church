// Copyright (c) 2026, kunle and contributors
// For license information, please see license.txt

// Church Settings form controller
// Adds the "Setup Church Services" button that creates all Church Service
// template records for every weekly_services row × branch × slot.

frappe.ui.form.on('Church Settings', {

    refresh: function(frm) {
        add_setup_buttons(frm);
    },

    onload: function(frm) {
        add_setup_buttons(frm);
    }
});


// ============================================================================
// SETUP BUTTONS
// ============================================================================

function add_setup_buttons(frm) {

    // ── SETUP CHURCH SERVICES ──────────────────────────────────────────────
    /**
     * Creates Church Service template records for every combination of:
     *   weekly_services row × active branch × slot number
     *
     * This is a ONE-TIME setup (idempotent — safe to re-run).
     * After this runs, the cron job can start creating Service Instances.
     *
     * Naming convention:
     *   1 service/day  → "{Service} - {Branch}"
     *   2 services/day → "{Service} - 1st Service - {Branch}"
     *                    "{Service} - 2nd Service - {Branch}"
     */
    frm.add_custom_button(__('⚙️ Setup Church Services'), function() {
        show_setup_dialog(frm);
    }, __('Service Setup'));

    // ── PREVIEW SLOTS ─────────────────────────────────────────────────────
    /**
     * Shows a preview of what service slots and times will be created
     * without actually creating anything.
     */
    frm.add_custom_button(__('🔍 Preview Service Slots'), function() {
        preview_service_slots(frm);
    }, __('Service Setup'));

    // ── MANUAL TRIGGER ────────────────────────────────────────────────────
    /**
     * Manually fires the cron logic right now — useful for testing.
     * Creates Service Instances for any slot that is within 10 minutes.
     */
    if (frappe.user.has_role('System Manager')) {
        frm.add_custom_button(__('⚡ Run Instance Creator Now'), function() {
            frappe.confirm(
                __('Run the auto-instance creator now? This will create Service Instances for any service slots within the next 10 minutes.'),
                function() {
                    frappe.call({
                        method: 'church.attendance.auto_service_creator.trigger_now',
                        freeze: true,
                        freeze_message: __('Running auto-instance creator…'),
                        callback: function(r) {
                            frappe.msgprint({
                                title: __('Done'),
                                indicator: 'green',
                                message: r.message ? r.message.message : __('Completed. Check error logs for details.')
                            });
                        }
                    });
                }
            );
        }, __('Service Setup'));
    }
}


// ============================================================================
// SETUP DIALOG
// ============================================================================

function show_setup_dialog(frm) {
    /**
     * Shows a confirmation dialog with a preview of what will be created,
     * then calls setup_church_services() on the server.
     */

    if (!frm.doc.weekly_services || frm.doc.weekly_services.length === 0) {
        frappe.msgprint({
            title: __('No Weekly Services'),
            indicator: 'orange',
            message: __(
                'Please add services to the Weekly Services table first, then run Setup.'
            )
        });
        return;
    }

    // Build preview table
    const gap = frm.doc.service_gap_minutes || 30;
    let preview_rows = '';
    let total_count  = 0;

    frm.doc.weekly_services.forEach(function(row) {
        if (!row.service || !row.time_from) return;

        const num_slots        = row.no_of_service_per_day || 1;
        const duration_minutes = Math.round((row.duration || 1.5) * 60);
        const slot_times       = calculate_slot_times(row.time_from, num_slots, duration_minutes, gap);

        slot_times.forEach(function(time, idx) {
            const ordinal = ['1st','2nd','3rd','4th','5th','6th','7th'][idx] || `${idx+1}th`;
            const label   = num_slots > 1
                ? `${row.service} - ${ordinal} Service - [Branch]`
                : `${row.service} - [Branch]`;

            preview_rows += `
                <tr style="background:${total_count % 2 === 0 ? '#f8f9fa' : '#fff'}">
                    <td style="padding:8px 10px;border:1px solid #dee2e6;">${row.day}</td>
                    <td style="padding:8px 10px;border:1px solid #dee2e6;">${label}</td>
                    <td style="padding:8px 10px;border:1px solid #dee2e6;">${time}</td>
                    <td style="padding:8px 10px;border:1px solid #dee2e6;">${duration_minutes} min</td>
                </tr>
            `;
            total_count++;
        });
    });

    const html = `
        <div style="font-family:Arial,sans-serif;font-size:13px;">
            <p style="margin-bottom:12px;color:#555;">
                The following Church Service records will be created
                <strong>per active branch</strong>.
                Records that already exist will be skipped.
            </p>
            <p style="margin-bottom:12px;color:#555;">
                Gap between services: <strong>${gap} minutes</strong>
                (configurable in Church Settings → service_gap_minutes)
            </p>
            <table style="width:100%;border-collapse:collapse;font-size:13px;">
                <thead>
                    <tr style="background:#2E75B6;">
                        <th style="padding:8px 10px;border:1px solid #dee2e6;
                                   text-align:left;color:white;">Day</th>
                        <th style="padding:8px 10px;border:1px solid #dee2e6;
                                   text-align:left;color:white;">Service Name (per branch)</th>
                        <th style="padding:8px 10px;border:1px solid #dee2e6;
                                   text-align:left;color:white;">Start Time</th>
                        <th style="padding:8px 10px;border:1px solid #dee2e6;
                                   text-align:left;color:white;">Duration</th>
                    </tr>
                </thead>
                <tbody>${preview_rows}</tbody>
            </table>
            <p style="margin-top:14px;color:#888;font-size:12px;">
                Total slots: <strong>${total_count}</strong> per branch.
                Final count = ${total_count} × number of active branches.
            </p>
        </div>
    `;

    let d = new frappe.ui.Dialog({
        title: __('Setup Church Services — Preview'),
        size: 'extra-large',
        fields: [{ fieldtype: 'HTML', fieldname: 'preview_html' }],
        primary_action_label: __('✅ Create Church Services'),
        primary_action: function() {
            d.hide();
            run_setup();
        },
        secondary_action_label: __('Cancel'),
        secondary_action: function() { d.hide(); }
    });

    d.fields_dict.preview_html.$wrapper.html(html);
    d.show();
}


function run_setup() {
    frappe.show_alert({ message: __('Setting up Church Services…'), indicator: 'blue' }, 3);

    frappe.call({
        method: 'church.attendance.auto_service_creator.setup_church_services',
        freeze: true,
        freeze_message: __('Creating Church Service records for all branches and slots…'),
        callback: function(r) {
            if (!r.message) {
                frappe.msgprint({ title: __('Error'), indicator: 'red',
                    message: __('No response from server.') });
                return;
            }

            const res = r.message;

            if (!res.success) {
                frappe.msgprint({ title: __('Setup Failed'), indicator: 'red',
                    message: res.message });
                return;
            }

            // Show results
            let html = `
                <div style="font-family:Arial,sans-serif;font-size:14px;">
                    <p style="margin-bottom:12px;">${res.message}</p>
            `;

            if (res.created && res.created.length > 0) {
                html += `
                    <h4 style="color:#27ae60;margin-bottom:8px;">
                        ✅ Created (${res.created.length})
                    </h4>
                    <ul style="margin:0 0 16px;padding-left:20px;
                               max-height:200px;overflow-y:auto;">
                        ${res.created.map(n =>
                            `<li style="margin-bottom:3px;font-size:13px;">${n}</li>`
                        ).join('')}
                    </ul>
                `;
            }

            if (res.skipped && res.skipped.length > 0) {
                html += `
                    <h4 style="color:#f39c12;margin-bottom:8px;">
                        ⏭️ Already Existed — Skipped (${res.skipped.length})
                    </h4>
                    <ul style="margin:0 0 16px;padding-left:20px;
                               max-height:120px;overflow-y:auto;color:#888;">
                        ${res.skipped.slice(0, 10).map(n =>
                            `<li style="margin-bottom:3px;font-size:12px;">${n}</li>`
                        ).join('')}
                        ${res.skipped.length > 10
                            ? `<li style="font-size:12px;color:#aaa;">
                               … and ${res.skipped.length - 10} more</li>`
                            : ''}
                    </ul>
                `;
            }

            if (res.errors && res.errors.length > 0) {
                html += `
                    <h4 style="color:#e74c3c;margin-bottom:8px;">
                        ❌ Errors (${res.errors.length})
                    </h4>
                    <ul style="margin:0;padding-left:20px;color:#c0392b;">
                        ${res.errors.map(e =>
                            `<li style="margin-bottom:3px;font-size:12px;">${e}</li>`
                        ).join('')}
                    </ul>
                `;
            }

            html += `
                    <div style="background:#e8f5e9;border-radius:8px;padding:12px;
                                margin-top:16px;border-left:4px solid #27ae60;">
                        <p style="margin:0;font-size:13px;color:#1a6b35;">
                            ✅ Setup complete. The cron job will now automatically
                            create Service Instances 10 minutes before each scheduled service.
                        </p>
                    </div>
                </div>
            `;

            let result_d = new frappe.ui.Dialog({
                title: __('Setup Results'),
                size: 'large',
                fields: [{ fieldtype: 'HTML', fieldname: 'result_html' }],
                primary_action_label: __('Close'),
                primary_action: function() { result_d.hide(); }
            });
            result_d.fields_dict.result_html.$wrapper.html(html);
            result_d.show();
        }
    });
}


// ============================================================================
// PREVIEW SLOTS (no creation)
// ============================================================================

function preview_service_slots(frm) {
    if (!frm.doc.weekly_services || frm.doc.weekly_services.length === 0) {
        frappe.msgprint(__('No weekly services configured.'));
        return;
    }

    const gap = frm.doc.service_gap_minutes || 30;
    let html  = `
        <div style="font-family:Arial,sans-serif;font-size:13px;">
        <p style="margin-bottom:12px;color:#555;">
            Slot times based on current weekly_services configuration.
            Gap between services: <strong>${gap} min</strong>.
        </p>
        <table style="width:100%;border-collapse:collapse;">
            <thead>
                <tr style="background:#2E75B6;">
                    <th style="padding:8px;border:1px solid #dee2e6;color:white;text-align:left;">Day</th>
                    <th style="padding:8px;border:1px solid #dee2e6;color:white;text-align:left;">Base Service</th>
                    <th style="padding:8px;border:1px solid #dee2e6;color:white;text-align:left;">Slots</th>
                    <th style="padding:8px;border:1px solid #dee2e6;color:white;text-align:left;">Slot Times</th>
                    <th style="padding:8px;border:1px solid #dee2e6;color:white;text-align:left;">Duration/slot</th>
                </tr>
            </thead>
            <tbody>
    `;

    frm.doc.weekly_services.forEach(function(row, i) {
        if (!row.service || !row.time_from) return;

        const num_slots        = row.no_of_service_per_day || 1;
        const duration_minutes = Math.round((row.duration || 1.5) * 60);
        const slot_times       = calculate_slot_times(row.time_from, num_slots, duration_minutes, gap);
        const bg               = i % 2 === 0 ? '#f8f9fa' : '#fff';

        html += `
            <tr style="background:${bg};">
                <td style="padding:8px;border:1px solid #dee2e6;">${row.day}</td>
                <td style="padding:8px;border:1px solid #dee2e6;">${row.service}</td>
                <td style="padding:8px;border:1px solid #dee2e6;text-align:center;">
                    <strong>${num_slots}</strong>
                </td>
                <td style="padding:8px;border:1px solid #dee2e6;">
                    ${slot_times.map((t, idx) => {
                        const ordinal = ['1st','2nd','3rd','4th','5th'][idx] || `${idx+1}th`;
                        const label   = num_slots > 1 ? `${ordinal}: ${t}` : t;
                        return `<div>${label}</div>`;
                    }).join('')}
                </td>
                <td style="padding:8px;border:1px solid #dee2e6;">
                    ${duration_minutes} min
                </td>
            </tr>
        `;
    });

    html += '</tbody></table></div>';

    let d = new frappe.ui.Dialog({
        title: __('Service Slot Preview'),
        size: 'large',
        fields: [{ fieldtype: 'HTML', fieldname: 'preview_html' }],
        primary_action_label: __('Close'),
        primary_action: function() { d.hide(); }
    });
    d.fields_dict.preview_html.$wrapper.html(html);
    d.show();
}


// ============================================================================
// CLIENT-SIDE SLOT TIME CALCULATOR (mirrors Python logic)
// ============================================================================

function calculate_slot_times(base_time, num_slots, duration_minutes, gap_minutes) {
    /**
     * Mirrors _calculate_slot_times() in auto_service_creator.py.
     * Used for client-side preview only.
     *
     * base_time: "HH:MM:SS" or "HH:MM"
     */
    const parts  = String(base_time).split(':');
    let current  = parseInt(parts[0]) * 60 + parseInt(parts[1]);
    const times  = [];

    for (let i = 0; i < num_slots; i++) {
        const h = Math.floor(current / 60);
        const m = current % 60;
        times.push(`${String(h).padStart(2,'0')}:${String(m).padStart(2,'0')}`);
        current += duration_minutes + gap_minutes;
    }

    return times;
}


frappe.ui.form.on('Weekly Services', {
    time_to: function(frm, cdt, cdn) {
        calculate_duration(frm, cdt, cdn);
    },
    time_from: function(frm, cdt, cdn) {
        calculate_duration(frm, cdt, cdn);
    }
});

function calculate_duration(frm, cdt, cdn) {
    let row = locals[cdt][cdn];
    if (row.time_from && row.time_to) {
        let parse_seconds = function(time_str) {
            let parts = time_str.split(":");
            let h = parseInt(parts[0], 10) || 0;
            let m = parseInt(parts[1], 10) || 0;
            let s = parseInt(parts[2], 10) || 0;
            return (h * 3600) + (m * 60) + s;
        };

        let from_secs = parse_seconds(row.time_from);
        let to_secs   = parse_seconds(row.time_to);

        if (to_secs < from_secs) {
            to_secs += 86400;
        }

        let diff_secs = to_secs - from_secs;

        let hours   = Math.floor(diff_secs / 3600);
        let minutes = Math.floor((diff_secs % 3600) / 60);

        // Format as decimal: e.g. 1h 30m → 1.30, 2h 05m → 2.05
        let duration_decimal = parseFloat(
            hours + "." + String(minutes).padStart(2, "0")
        );

        row.duration = duration_decimal;
        refresh_field("weekly_services");
    }
}