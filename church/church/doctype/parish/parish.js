// Copyright (c) 2026, kunle and contributors
// For license information, please see license.txt

frappe.ui.form.on('Parish', {
    refresh: function(frm) {
        // Add custom button to fetch workers
        if (!frm.doc.__islocal) {
            frm.add_custom_button(__('Get Workers from Members'), function() {
                get_workers_from_members(frm);
            }, __('Actions'));

            // Add export button
            frm.add_custom_button(__('Export Workers to Excel'), function() {
                export_workers_to_excel(frm);
            }, __('Actions'));
        }
    }
});

function get_workers_from_members(frm) {
    frappe.confirm(
        'This will fetch all workers from the Member doctype where Parish matches this Parish. Continue?',
        function() {
            // On yes
            frappe.call({
                method: 'church.church.doctype.parish.parish.get_workers_from_members',
                args: {
                    parish_name: frm.doc.name
                },
                freeze: true,
                freeze_message: __('Fetching Workers...'),
                callback: function(r) {
                    if (r.message) {
                        // Clear existing workers
                        frm.clear_table('workers');
                        
                        // Add new workers
                        r.message.forEach(function(worker) {
                            let row = frm.add_child('workers');
                            row.full_name = worker.full_name;
                            row.gender = worker.gender;
                            row.date_of_birth = worker.date_of_birth;
                            row.mobile_phone = worker.mobile_phone;
                            row.email = worker.email;
                            row.alternative_phone = worker.alternative_phone;
                            row.department = worker.designation;
                            row.date_of_joining = worker.date_of_joining;
                        });
                        
                        frm.refresh_field('workers');
                        
                        // Update counts
                        update_worker_counts(frm);
                        
                        frappe.show_alert({
                            message: __('Successfully fetched {0} workers', [r.message.length]),
                            indicator: 'green'
                        }, 5);
                    }
                }
            });
        }
    );
}

function update_worker_counts(frm) {
    let male_count = 0;
    let female_count = 0;
    
    frm.doc.workers.forEach(function(worker) {
        if (worker.gender === 'Male') {
            male_count++;
        } else if (worker.gender === 'Female') {
            female_count++;
        }
    });
    
    frm.set_value('worker_count_male', male_count);
    frm.set_value('worker_count_female', female_count);
}

function export_workers_to_excel(frm) {
    if (!frm.doc.workers || frm.doc.workers.length === 0) {
        frappe.msgprint(__('No workers to export'));
        return;
    }
    
    frappe.call({
        method: 'church.church.doctype.parish.parish.export_workers_to_excel',
        args: {
            parish_name: frm.doc.name,
            workers: frm.doc.workers
        },
        freeze: true,
        freeze_message: __('Generating Excel File...'),
        callback: function(r) {
            if (r.message) {
                // Download the file
                window.open(r.message.file_url);
                
                frappe.show_alert({
                    message: __('Excel file generated successfully'),
                    indicator: 'green'
                }, 5);
            }
        }
    });
}


frappe.ui.form.on('Parish', {
    refresh: function(frm) {
        // Add section button in Workers tab
        if (!frm.doc.__islocal) {
            frm.fields_dict['workers'].grid.add_custom_button(__('Fetch from Members'), function() {
                get_workers_from_members(frm);
            });
        }
    },
    
    workers_on_form_rendered: function(frm) {
        // Add export button on workers grid
        frm.fields_dict['workers'].grid.grid_buttons
            .find('.btn-open-row').parent()
            .prepend(`
                <button class="btn btn-xs btn-success export-workers-btn" 
                        style="margin-right: 5px;">
                    <i class="fa fa-file-excel-o"></i> Export to Excel
                </button>
            `);
        
        $('.export-workers-btn').off('click').on('click', function() {
            export_workers_to_excel(frm);
        });
    }
});