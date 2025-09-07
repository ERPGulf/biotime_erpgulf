frappe.listview_settings['Employee Checkin'] = {
    onload: function(listview) {
        listview.page.add_inner_button(__('Sync Now'), function() {
            frappe.call({
                method: "biotime_erpgulf.attendance.sync_biotime_attendance",
                callback: function(r) {
                    if (!r.exc) {
                        frappe.msgprint(__('Sync Up-to-date'));
                        listview.refresh();
                    }
                }
            });
        });
    }
};


