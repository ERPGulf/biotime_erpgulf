frappe.listview_settings['Employee'] = {
    onload: function(listview) {
        listview.page.add_inner_button(__('Sync Now'), function() {
            frappe.call({
                method: "biotime_erpgulf.employee.sync_biotime_employees", 
                callback: function(r) {
                    if (!r.exc) {
                        if (r.message && r.message.status === "success") {
                            frappe.msgprint(__(r.message.message));  
                        } else {
                            frappe.msgprint(__('Employee Sync Completed'));
                        }
                        listview.refresh();
                    }
                }
            });
        });
    }
};
