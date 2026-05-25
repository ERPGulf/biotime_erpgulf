
frappe.listview_settings['Employee Checkin'] = {
    onload: function(listview) {
        listview.page.add_inner_button(__('Sync Now'), function() {
            // First get integration_source from settings
            frappe.db.get_single_value('BioTime Settings', 'integration_source')
                .then((source) => {

                    let method = "";

                    if (source === "BioTime") {
                        method = "biotime_erpgulf.attendance.biotime_attendance";
                    } else if (source === "UBio Alpeta") {
                        method = "biotime_erpgulf.ubio_attendance.biotime_attendance";
                    }

                    frappe.call({
                        method: method,
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
        });
    }
};

