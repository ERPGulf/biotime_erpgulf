frappe.listview_settings['Employee'] = {
    onload: function (listview) {

        frappe.db.get_single_value(
            'BioTime Settings',
            'enable_sync_button_for_employee'
        ).then((enabled) => {

            if (!enabled) return;

            listview.page.add_inner_button(__('Sync Now'), function () {

                frappe.show_alert(
                    { message: __('Employee sync has started'), indicator: 'blue' },
                    5
                );

                frappe.db.get_single_value(
                    'BioTime Settings',
                    'integration_source'
                ).then((source) => {

                    let methods = [];

                    if (source === "BioTime") {
                        methods = ["biotime_erpgulf.employee.sync_biotime_employees"];
                    } else if (source === "UBio Alpeta") {
                        methods = ["biotime_erpgulf.ubio_employee.sync_ubio_employees"];
                    } else if (source === "All") {
                        methods = [
                            "biotime_erpgulf.employee.sync_biotime_employees",
                            "biotime_erpgulf.ubio_employee.sync_ubio_employees"
                        ];
                    }

                    if (!methods.length) {
                        frappe.msgprint(__('Integration Source not configured!'));
                        return;
                    }

                    function callNext(index) {
                        if (index >= methods.length) {
                            frappe.show_alert({
                                message: __('All syncs completed'),
                                indicator: 'green'
                            }, 5);
                            listview.refresh();
                            return;
                        }

                        const method = methods[index];
                        frappe.show_alert({
                            message: __('Running: ') + method.split('.').pop(),
                            indicator: 'blue'
                        }, 3);

                        frappe.call({
                            method: method,
                            callback: function (r) {
                                if (!r.exc) {
                                    frappe.show_alert({
                                        message: r.message?.message || __('Sync step completed'),
                                        indicator: 'green'
                                    }, 4);
                                } else {
                                    frappe.show_alert({
                                        message: __('Error in: ') + method.split('.').pop(),
                                        indicator: 'red'
                                    }, 4);
                                }
                                // ✅ Wait 5 seconds before next sync to release DB locks
                                setTimeout(() => {
                                    callNext(index + 1);
                                }, 5000);
                            },
                            error: function () {
                                frappe.show_alert({
                                    message: __('Failed: ') + method.split('.').pop(),
                                    indicator: 'red'
                                }, 4);
                                setTimeout(() => {
                                    callNext(index + 1);
                                }, 5000);
                            }
                        });
                    }

                    callNext(0);
                });
            });
        });
    }
};


// frappe.listview_settings['Employee Checkin'] = {
//     onload: function(listview) {
//         listview.page.add_inner_button(__('Sync Now'), function() {

//             frappe.db.get_single_value('BioTime Settings', 'integration_source')
//                 .then((source) => {

//                     let methods = [];

//                     if (source === "BioTime") {
//                         methods = ["biotime_erpgulf.attendance.biotime_attendance"];
//                     } else if (source === "UBio Alpeta") {
//                         methods = ["biotime_erpgulf.ubio_attendance.ubio_attendance"];
//                     } else if (source === "All") {
//                         methods = [
//                             "biotime_erpgulf.attendance.biotime_attendance",
//                             "biotime_erpgulf.ubio_attendance.ubio_attendance"
//                         ];
//                     }

//                     if (!methods.length) {
//                         frappe.msgprint(__('Integration Source not configured!'));bench restart
//                         return;
//                     }

//                     function callNext(index) {
//                         if (index >= methods.length) {
//                             frappe.show_alert({
//                                 message: __('All checkin syncs completed'),
//                                 indicator: 'green'
//                             }, 5);
//                             listview.refresh();
//                             return;
//                         }

//                         const method = methods[index];
//                         frappe.show_alert({
//                             message: __('Running: ') + method.split('.').pop(),
//                             indicator: 'blue'
//                         }, 3);

//                         frappe.call({
//                             method: method,
//                             callback: function(r) {
//                                 if (r && r.message) {
//                                     var msg = typeof r.message === 'string' ? r.message :
//                                         r.message.message ? r.message.message :
//                                         JSON.stringify(r.message);
//                                     frappe.show_alert({
//                                         message: __('Debug Info: ') + msg,
//                                         indicator: 'green'
//                                     }, 4);
//                                 } else {
//                                     frappe.show_alert({
//                                         message: __('Sync has been queued in background.'),
//                                         indicator: 'green'
//                                     }, 4);
//                                 }
//                                 // ✅ Wait 5 seconds before next sync to release DB locks
//                                 setTimeout(() => {
//                                     callNext(index + 1);
//                                 }, 5000);
//                             },
//                             error: function() {
//                                 frappe.show_alert({
//                                     message: __('Failed: ') + method.split('.').pop(),
//                                     indicator: 'red'
//                                 }, 4);
//                                 setTimeout(() => {
//                                     callNext(index + 1);
//                                 }, 5000);
//                             }
//                         });
//                     }

//                     callNext(0);
//                 });
//         });
//     }
// };