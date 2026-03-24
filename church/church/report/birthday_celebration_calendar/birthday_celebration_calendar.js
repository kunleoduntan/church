// church/church/report/birthday_celebration_calendar/birthday_celebration_calendar.js

frappe.query_reports["Birthday Celebration Calendar"] = {

    filters: [
        {
            fieldname: "branch",
            label: __("Branch"),
            fieldtype: "Link",
            options: "Branch",
            width: 150
        },
        {
            fieldname: "view_type",
            label: __("View"),
            fieldtype: "Select",
            options: ["Calendar View", "List View"].join("\n"),
            default: "Calendar View",
            width: 120,
            on_change: function() {
                // Refresh report when view changes
                frappe.query_report.refresh();
            }
        },
        {
            fieldname: "year",
            label: __("Year"),
            fieldtype: "Select",
            options: () => {
                const currentYear = new Date().getFullYear();
                let years = ["", currentYear - 1, currentYear, currentYear + 1];
                return years.join("\n");
            },
            default: new Date().getFullYear().toString(),
            width: 100,
            // FIXED: Simple depends_on without eval:
            depends_on: "view_type == 'Calendar View'"
        },
        {
            fieldname: "month",
            label: __("Month"),
            fieldtype: "Select",
            options: [
                "", "January", "February", "March", "April", "May", "June",
                "July", "August", "September", "October", "November", "December"
            ].join("\n"),
            default: new Date().toLocaleString('default', { month: 'long' }),
            // FIXED: Simple depends_on without eval:
            depends_on: "view_type == 'Calendar View'"
        },
        {
            fieldname: "days_ahead",
            label: __("Days Ahead"),
            fieldtype: "Int",
            default: 30,
            // FIXED: Simple depends_on without eval:
            depends_on: "view_type == 'List View'"
        },
        {
            fieldname: "milestone_only",
            label: __("Milestones Only"),
            fieldtype: "Check",
            default: 0,
            // FIXED: Simple depends_on without eval:
            depends_on: "view_type == 'List View'"
        }
    ],

    formatter: function(value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);
        if (!data) return value;

        // Birthday celebrations styling
        if (column.fieldname === "celebration_type") {
            if (data.is_milestone) {
                value = `<span style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                                       color: white; padding: 4px 10px; border-radius: 20px; 
                                       font-weight: 600; font-size: 11px;">
                             ✨ Milestone ✨
                         </span>`;
            } else {
                value = `<span style="background: #48bb78; color: white; padding: 4px 10px; 
                                       border-radius: 20px; font-weight: 500; font-size: 11px;">
                             🎂 Birthday
                         </span>`;
            }
        }

        // Age with milestone highlight
        if (column.fieldname === "age_turning") {
            const age = parseInt(data.age_turning);
            const milestones = [1, 5, 10, 13, 16, 18, 21, 25, 30, 40, 50, 60, 70, 80, 90, 100];
            if (milestones.includes(age)) {
                value = `<span style="background: #fbbf24; color: #78350f; padding: 4px 8px; 
                                       border-radius: 12px; font-weight: 700; font-size: 12px;">
                             🎉 ${age} 🎉
                         </span>`;
            } else {
                value = `<span style="font-weight: 600; color: #4a5568;">${age} years</span>`;
            }
        }

        // Name with gender icon
        if (column.fieldname === "full_name") {
            const icon = data.gender === "Female" ? "👩" : "👨";
            const gradient = data.gender === "Female" 
                ? "linear-gradient(135deg, #f093fb 0%, #f5576c 100%)"
                : "linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)";
            value = `<span style="display: inline-flex; align-items: center; gap: 8px;">
                        <span style="display: inline-block; width: 28px; height: 28px; 
                                     background: ${gradient}; border-radius: 50%; 
                                     display: inline-flex; align-items: center; 
                                     justify-content: center; font-size: 14px;">
                            ${icon}
                        </span>
                        <span style="font-weight: 500;">${value}</span>
                     </span>`;
        }

        // Days away with progress bar
        if (column.fieldname === "days_away" && data.days_away !== undefined) {
            const days = parseInt(data.days_away);
            let color, emoji;
            if (days === 0) {
                color = "#f59e0b";
                emoji = "🎉";
                value = `<div style="text-align: center;">
                            <span style="background: ${color}; color: white; padding: 4px 12px; 
                                         border-radius: 20px; font-weight: 700; font-size: 12px;">
                                ${emoji} TODAY! ${emoji}
                            </span>
                         </div>`;
            } else if (days <= 3) {
                color = "#ef4444";
                emoji = "🔴";
                value = `<div><span style="color: ${color}; font-weight: 700;">${emoji} ${days} days</span></div>`;
            } else if (days <= 7) {
                color = "#f59e0b";
                emoji = "🟠";
                const percent = ((7 - days) / 7) * 100;
                value = `<div>
                            <span style="color: ${color}; font-weight: 600;">${emoji} ${days} days</span>
                            <div style="background: #e2e8f0; height: 4px; border-radius: 2px; margin-top: 4px;">
                                <div style="background: ${color}; width: ${percent}%; height: 4px; border-radius: 2px;"></div>
                            </div>
                         </div>`;
            } else {
                value = `<span style="color: #718096;">📅 ${days} days</span>`;
            }
        }

        return value;
    },

    get_datatable_options: function(options) {
        if (!options.hooks) options.hooks = {};
        
        // Row styling based on days away
        options.hooks.beforeRenderRow = function(row) {
            if (row && row[4]) {
                const daysAway = parseInt(row[4].content);
                if (daysAway === 0) {
                    return "background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%); font-weight: 600;";
                } else if (daysAway <= 3) {
                    return "background: #fee2e2;";
                } else if (daysAway <= 7) {
                    return "background: #fff7ed;";
                }
            }
            return "";
        };
        
        return options;
    },

    onload: function(report) {
        // Add quick action buttons
        report.page.add_inner_button(__("📅 This Month"), function() {
            const now = new Date();
            frappe.query_report.set_filter_value("view_type", "Calendar View");
            frappe.query_report.set_filter_value("month", now.toLocaleString('default', { month: 'long' }));
            frappe.query_report.set_filter_value("year", now.getFullYear().toString());
            frappe.query_report.refresh();
        });

        report.page.add_inner_button(__("🎯 Next 30 Days"), function() {
            frappe.query_report.set_filter_value("view_type", "List View");
            frappe.query_report.set_filter_value("days_ahead", 30);
            frappe.query_report.set_filter_value("milestone_only", 0);
            frappe.query_report.refresh();
        });

        report.page.add_inner_button(__("✨ Milestones Only"), function() {
            frappe.query_report.set_filter_value("view_type", "List View");
            frappe.query_report.set_filter_value("days_ahead", 365);
            frappe.query_report.set_filter_value("milestone_only", 1);
            frappe.query_report.refresh();
        });

        // Send Reminders button with proper dialog handling
        report.page.add_inner_button(__("📧 Send Reminders"), function() {
            // Get current filters
            const filters = frappe.query_report.get_filter_values();
            
            // Show confirmation dialog
            frappe.confirm(
                __('Birthday reminders will be sent to members with birthdays in the next 7 days. Continue?'),
                () => {
                    // On confirm - send reminders
                    frappe.call({
                        method: "church.church.report.birthday_celebration_calendar.birthday_celebration_calendar.send_reminders",
                        args: {
                            filters: filters
                        },
                        callback: function(response) {
                            if (response.message) {
                                frappe.msgprint({
                                    title: __("Reminders Sent"),
                                    message: __("Successfully sent {0} birthday reminders", [response.message.sent]),
                                    indicator: "green"
                                });
                            }
                        },
                        error: function(error) {
                            frappe.msgprint({
                                title: __("Error"),
                                message: __("Failed to send reminders. Please check the error log."),
                                indicator: "red"
                            });
                            console.error(error);
                        }
                    });
                },
                () => {
                    // On cancel - do nothing
                    frappe.msgprint(__("Reminder sending cancelled"));
                }
            );
        });
    },

    refresh: function(report) {
        // This runs after data is loaded
        setTimeout(() => {
            const viewType = frappe.query_report.get_filter_value("view_type");
            if (viewType === "Calendar View" && report.data && report.data.length > 0) {
                this.render_calendar_view(report);
            }
        }, 100);
    },

    render_calendar_view: function(report) {
        const data = report.data;
        if (!data || data.length === 0) {
            // Show no data message
            const $reportContainer = $(report.page.body).find('.report-content');
            $reportContainer.find('.calendar-container').remove();
            $reportContainer.prepend('<div class="alert alert-info">No birthdays found for the selected month</div>');
            return;
        }

        const month = frappe.query_report.get_filter_value("month");
        const year = parseInt(frappe.query_report.get_filter_value("year"));
        
        if (!month || !year) return;
        
        // Group birthdays by date
        const birthdaysByDate = {};
        data.forEach(member => {
            if (member.birthday_this_year) {
                const date = new Date(member.birthday_this_year);
                const dateKey = date.getDate();
                if (!birthdaysByDate[dateKey]) birthdaysByDate[dateKey] = [];
                birthdaysByDate[dateKey].push(member);
            }
        });

        // Get days in month
        const monthIndex = new Date(Date.parse(month + " 1, " + year)).getMonth();
        const daysInMonth = new Date(year, monthIndex + 1, 0).getDate();
        const firstDay = new Date(year, monthIndex, 1).getDay();

        // Remove existing calendar
        const $reportContainer = $(report.page.body).find('.report-content');
        $reportContainer.find('.calendar-container').remove();
        
        // Inject calendar HTML
        const calendarHtml = `
            <div class="calendar-container" style="padding: 20px; background: white; border-radius: 16px; margin-top: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
                <div class="calendar-header" style="display: grid; grid-template-columns: repeat(7, 1fr); gap: 8px; margin-bottom: 16px;">
                    ${['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].map(day => 
                        `<div style="text-align: center; font-weight: 600; color: #4a5568; padding: 12px; background: #f7fafc; border-radius: 8px;">${day}</div>`
                    ).join('')}
                </div>
                <div class="calendar-grid" style="display: grid; grid-template-columns: repeat(7, 1fr); gap: 8px;">
                    ${Array(firstDay).fill('<div style="padding: 12px; background: #f7fafc; border-radius: 8px; min-height: 100px;"></div>').join('')}
                    ${Array.from({length: daysInMonth}, (_, i) => {
                        const day = i + 1;
                        const birthdays = birthdaysByDate[day] || [];
                        const hasBirthdays = birthdays.length > 0;
                        const milestoneCount = birthdays.filter(m => m.is_milestone).length;
                        
                        return `
                            <div class="calendar-day" data-day="${day}" style="
                                border: 1px solid #e2e8f0;
                                border-radius: 12px;
                                padding: 12px;
                                min-height: 100px;
                                background: ${hasBirthdays ? '#fef9e7' : 'white'};
                                transition: all 0.2s;
                                cursor: pointer;
                                position: relative;
                            ">
                                <div style="font-weight: 600; color: #2d3748; margin-bottom: 8px; font-size: 14px;">${day}</div>
                                ${hasBirthdays ? `
                                    <div style="display: flex; flex-direction: column; gap: 4px;">
                                        ${birthdays.slice(0, 2).map(m => `
                                            <div style="
                                                background: ${m.is_milestone ? '#667eea' : '#48bb78'};
                                                color: white;
                                                padding: 4px 8px;
                                                border-radius: 8px;
                                                font-size: 11px;
                                                white-space: nowrap;
                                                overflow: hidden;
                                                text-overflow: ellipsis;
                                                text-align: center;
                                            ">
                                                ${m.is_milestone ? '✨' : '🎂'} ${m.full_name.split(' ')[0]}
                                            </div>
                                        `).join('')}
                                        ${birthdays.length > 2 ? `
                                            <div style="color: #718096; font-size: 10px; text-align: center;">
                                                +${birthdays.length - 2} more
                                            </div>
                                        ` : ''}
                                    </div>
                                ` : ''}
                                ${milestoneCount > 0 ? `
                                    <div style="
                                        position: absolute;
                                        top: -8px;
                                        right: -8px;
                                        background: #fbbf24;
                                        color: #78350f;
                                        border-radius: 20px;
                                        padding: 2px 6px;
                                        font-size: 10px;
                                        font-weight: 700;
                                    ">
                                        🎉 ${milestoneCount}
                                    </div>
                                ` : ''}
                            </div>
                        `;
                    }).join('')}
                </div>
            </div>
            <style>
                .calendar-day:hover {
                    transform: translateY(-2px);
                    box-shadow: 0 4px 12px rgba(0,0,0,0.15);
                    border-color: #cbd5e0;
                }
            </style>
        `;
        
        $reportContainer.prepend(calendarHtml);
        
        // Add click handlers for calendar days
        $('.calendar-day').on('click', function() {
            const day = $(this).data('day');
            const birthdays = birthdaysByDate[day];
            if (birthdays && birthdays.length > 0) {
                let message = `<div style="padding: 10px;">
                                <h4 style="margin-bottom: 15px;">🎂 Birthdays on ${month} ${day}, ${year}</h4>
                                <div style="max-height: 400px; overflow-y: auto;">`;
                birthdays.forEach(m => {
                    message += `<div style="padding: 12px; border-bottom: 1px solid #e2e8f0; display: flex; align-items: center; gap: 10px;">
                                    <div style="font-size: 24px;">${m.gender === "Female" ? "👩" : "👨"}</div>
                                    <div style="flex: 1;">
                                        <strong style="font-size: 14px;">${m.full_name}</strong><br>
                                        <span style="font-size: 12px; color: #718096;">Turning ${m.age_turning} years old</span>
                                        ${m.is_milestone ? '<span style="margin-left: 8px; background: #fbbf24; padding: 2px 8px; border-radius: 12px; font-size: 11px;">✨ MILESTONE!</span>' : ''}
                                    </div>
                                </div>`;
                });
                message += `</div></div>`;
                frappe.msgprint({
                    title: __("Birthday Celebrations"),
                    message: message,
                    indicator: "green"
                });
            }
        });
    }
};