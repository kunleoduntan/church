// Reusable functions for all hierarchy levels
frappe.provide('church.worker_utils');

church.worker_utils = {
    add_worker_buttons: function(frm, doctype_name, doctype_label) {
        if (!frm.doc.__islocal) {
            // Add fetch workers button
            frm.add_custom_button(__('Get Workers from Members'), function() {
                church.worker_utils.get_workers_from_members(frm, doctype_name, doctype_label);
            }, __('Actions'));

            // Add export button
            frm.add_custom_button(__('Export Workers to Excel'), function() {
                church.worker_utils.export_workers_to_excel(frm, doctype_name, doctype_label);
            }, __('Actions'));
        }
    },

    get_workers_from_members: function(frm, doctype_name, doctype_label) {
        frappe.confirm(
            `This will fetch all workers from the Member doctype where ${doctype_label} matches this ${doctype_label}. Continue?`,
            function() {
                frappe.call({
                    method: 'church.church.api.worker_management.get_workers_from_members',
                    args: {
                        doctype: doctype_name,
                        doc_name: frm.doc.name,
                        field_name: doctype_name.toLowerCase()
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
                            church.worker_utils.update_worker_counts(frm);
                            
                            frappe.show_alert({
                                message: __('Successfully fetched {0} workers', [r.message.length]),
                                indicator: 'green'
                            }, 5);
                        }
                    }
                });
            }
        );
    },

    update_worker_counts: function(frm) {
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
    },

    export_workers_to_excel: function(frm, doctype_name, doctype_label) {
        if (!frm.doc.workers || frm.doc.workers.length === 0) {
            frappe.msgprint(__('No workers to export'));
            return;
        }
        
        frappe.call({
            method: 'church.church.api.worker_management.export_workers_to_excel',
            args: {
                doctype: doctype_name,
                doc_name: frm.doc.name,
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
};