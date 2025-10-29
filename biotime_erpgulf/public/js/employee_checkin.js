
frappe.listview_settings['Employee Checkin'] = {
    onload: function(listview) {
        listview.page.add_inner_button(__('Sync Now'), function() {
            frappe.call({
                method: "biotime_erpgulf.attendance.biotime_attendance",
                callback: function(r) {
                    if (r && r.message) {
                        frappe.msgprint(__('Debug Info: ') + r.message);
                    } else {
                        frappe.msgprint(__('BioTime sync has been queued in background.'));
                    }
                    listview.refresh();
                }

            });
        });
    }
};

