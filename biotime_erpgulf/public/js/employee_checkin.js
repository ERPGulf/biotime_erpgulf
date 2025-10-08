
frappe.listview_settings['Employee Checkin'] = {
    onload: function(listview) {
        listview.page.add_inner_button(__('Sync Now'), function() {
            frappe.call({
                method: "biotime_erpgulf.attendance.biotime_attendance",
                callback: function(r) {
                    if (r.message) {
                        frappe.msgprint(__('Debug Info: ') + JSON.stringify(r.message, null, 2));
                    } else {
                        frappe.msgprint(__('No data received'));
                    }
                    listview.refresh();
                }
            });
        });
    }
};

