
frappe.listview_settings['Employee Checkin'] = {
    onload: function(listview) {
        listview.page.add_inner_button(__('Sync Now'), function() {
            frappe.call({
                method: "biotime_erpgulf.attendance.biotime_attendance",
                callback: function(r) {
                    if (r && r.message) {
                        var msg = typeof r.message === 'string' ? r.message :
                        r.message.message ? r.message.message :
                        JSON.stringify(r.message);
                        frappe.msgprint(__('Debug Info: ') + msg);
                    } else {
                        frappe.msgprint(__('Sync has been queued in background.'));
                    }
                    listview.refresh();
                }


            });
        });
    }
};

