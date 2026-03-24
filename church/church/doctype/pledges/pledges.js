// Copyright (c) 2026, kunle and contributors
// For license information, please see license.txt

// Copyright (c) 2026, kunle and contributors
// For license information, please see license.txt

frappe.ui.form.on('Pledges', {

    first_name: function(frm) { update_full_name(frm); },
    last_name:  function(frm) { update_full_name(frm); },
    salutation: function(frm) { update_full_name(frm); },

    before_save: function(frm) {
        update_full_name(frm);
        validate_dates(frm);
    },

    member_id: function(frm) {
        if (frm.doc.member_id) {
            setTimeout(() => update_full_name(frm), 500);
        }
    },

    redemption_date: function(frm) { validate_dates(frm); },
    closing_date:    function(frm) { validate_dates(frm); },

    refresh: function(frm) {
        render_pledge_dashboard(frm);
    },

    onload: function(frm) {
        render_pledge_dashboard(frm);
    }
});

// ─── Dashboard ────────────────────────────────────────────────────────────────

function render_pledge_dashboard(frm) {
    if (!frm.doc.name || frm.doc.__islocal) return;

    const pledge_amount   = frm.doc.amount || 0;
    const total_redeemed  = frm.doc.total_redeemed || 0;
    const outstanding     = frm.doc.outstanding_balance || pledge_amount;
    const status          = frm.doc.redemption_status || 'Pending';
    const pct             = pledge_amount > 0 ? Math.min((total_redeemed / pledge_amount) * 100, 100).toFixed(1) : 0;

    const status_colors = {
        'Pending':            { bg: '#fff8e1', border: '#f59e0b', text: '#92400e', badge: '#f59e0b' },
        'Partially Redeemed': { bg: '#e0f2fe', border: '#0284c7', text: '#0c4a6e', badge: '#0284c7' },
        'Fully Redeemed':     { bg: '#dcfce7', border: '#16a34a', text: '#14532d', badge: '#16a34a' }
    };
    const colors = status_colors[status] || status_colors['Pending'];

    const fmt = (val) => frappe.format(val, { fieldtype: 'Currency' });

    const html = `
    <div style="
        font-family: 'Segoe UI', system-ui, sans-serif;
        background: ${colors.bg};
        border: 1.5px solid ${colors.border};
        border-radius: 12px;
        padding: 24px 28px 20px;
        margin: 8px 0 16px;
    ">
        <!-- Header row -->
        <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:20px;">
            <div>
                <div style="font-size:13px; color:#6b7280; letter-spacing:0.05em; text-transform:uppercase; font-weight:600;">
                    Pledge Redemption Summary
                </div>
                <div style="font-size:11px; color:#9ca3af; margin-top:2px;">
                    ${frm.doc.name} &nbsp;·&nbsp; ${frm.doc.programme || '—'}
                </div>
            </div>
            <span style="
                background:${colors.badge};
                color:#fff;
                padding: 4px 14px;
                border-radius: 20px;
                font-size: 12px;
                font-weight: 700;
                letter-spacing: 0.04em;
            ">${status.toUpperCase()}</span>
        </div>

        <!-- 3 stat cards -->
        <div style="display:grid; grid-template-columns:1fr 1fr 1fr; gap:16px; margin-bottom:20px;">
            <div style="background:#fff; border-radius:8px; padding:14px 16px; box-shadow:0 1px 3px rgba(0,0,0,0.06);">
                <div style="font-size:11px; color:#9ca3af; text-transform:uppercase; font-weight:600; margin-bottom:6px;">Pledge Amount</div>
                <div style="font-size:20px; font-weight:700; color:#1f2937;">${fmt(pledge_amount)}</div>
            </div>
            <div style="background:#fff; border-radius:8px; padding:14px 16px; box-shadow:0 1px 3px rgba(0,0,0,0.06);">
                <div style="font-size:11px; color:#9ca3af; text-transform:uppercase; font-weight:600; margin-bottom:6px;">Total Redeemed</div>
                <div style="font-size:20px; font-weight:700; color:#16a34a;">${fmt(total_redeemed)}</div>
            </div>
            <div style="background:#fff; border-radius:8px; padding:14px 16px; box-shadow:0 1px 3px rgba(0,0,0,0.06);">
                <div style="font-size:11px; color:#9ca3af; text-transform:uppercase; font-weight:600; margin-bottom:6px;">Outstanding Balance</div>
                <div style="font-size:20px; font-weight:700; color:${outstanding > 0 ? '#dc2626' : '#16a34a'};">${fmt(outstanding)}</div>
            </div>
        </div>

        <!-- Progress bar -->
        <div>
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                <span style="font-size:12px; color:#6b7280; font-weight:600;">Redemption Progress</span>
                <span style="font-size:13px; font-weight:700; color:${colors.text};">${pct}%</span>
            </div>
            <div style="background:#e5e7eb; border-radius:999px; height:10px; overflow:hidden;">
                <div style="
                    width:${pct}%;
                    height:100%;
                    background: linear-gradient(90deg, ${colors.border}, ${colors.badge});
                    border-radius:999px;
                    transition: width 0.6s ease;
                "></div>
            </div>
            ${status === 'Fully Redeemed'
                ? `<div style="margin-top:10px; font-size:13px; font-weight:600; color:#16a34a; text-align:center;">
                    🎉 This pledge has been fully redeemed. Thank you!
                   </div>`
                : `<div style="margin-top:8px; font-size:12px; color:#6b7280; text-align:right;">
                    ${fmt(outstanding)} remaining to complete this pledge
                   </div>`
            }
        </div>
    </div>`;

    frm.fields_dict['pledge_dashboard_html'].$wrapper.html(html);
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function update_full_name(frm) {
    const full_name   = get_full_name(frm);
    const description = `Pledge redemption by ${frm.doc.salutation || ''} ${full_name}`.trim();
    frm.set_value('description', description);
}

function get_full_name(frm) {
    const first = (frm.doc.first_name || '').trim();
    const last  = (frm.doc.last_name  || '').trim();
    return `${first} ${last}`.trim();
}

function validate_dates(frm) {
    if (frm.doc.redemption_date && frm.doc.closing_date) {
        const redemption = frappe.datetime.str_to_obj(frm.doc.redemption_date);
        const closing    = frappe.datetime.str_to_obj(frm.doc.closing_date);

        if (closing < redemption) {
            frappe.msgprint({
                title: __('Invalid Date Range'),
                indicator: 'red',
                message: __('Expected Completion Date cannot be before Redemption Start Date')
            });
            frm.set_value('closing_date', '');
        }
    }
}