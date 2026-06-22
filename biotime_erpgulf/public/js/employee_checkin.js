frappe.listview_settings['Employee Checkin'] = {
    onload: function(listview) {
        listview.page.add_inner_button(__('Sync Now'), function() {

            frappe.db.get_single_value('BioTime Settings', 'integration_source')
                .then((source) => {

                    let methods = [];  // ✅ use methods array from start

                    if (source === "BioTime") {
                        methods = ["biotime_erpgulf.attendance.biotime_attendance"];
                    } else if (source === "UBio Alpeta") {
                        methods = ["biotime_erpgulf.ubio_attendance.ubio_attendance"];
                    } else if (source === "All") {
                        methods = [
                            "biotime_erpgulf.ubio_attendance.ubio_attendance",
                            "biotime_erpgulf.attendance.biotime_attendance"
                            
                        ];
                    }

                    // ✅ check array not empty string
                    if (!methods.length) {
                        frappe.msgprint(__('Integration Source not configured!'));
                        return;
                    }

                    // ✅ loop through methods
                    methods.forEach((method) => {
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
        });
    }
};