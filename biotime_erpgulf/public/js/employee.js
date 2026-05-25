
// frappe.listview_settings['Employee'] = {
//     onload: function (listview) {
//         listview.page.add_inner_button(__('Sync Now'), function () {

//             frappe.show_alert(
//                 {
//                     message: __('BioTime employee sync has started'),
//                     indicator: 'blue'
//                 },
//                 5
//             );

//             frappe.call({
//                 method: "biotime_erpgulf.employee.sync_biotime_employees",
//                 callback: function (r) {
//                     if (!r.exc) {
//                         if (r.message && r.message.status === "success") {
//                             frappe.msgprint(__(r.message.message));
//                         } else {
//                             frappe.msgprint(__('Employee sync request submitted successfully'));
//                         }
//                         listview.refresh();
//                     }
//                 },
//                 error: function () {
//                     frappe.msgprint(__('Failed to start BioTime sync'));
//                 }
//             });
//         });
//     }
// };


frappe.listview_settings['Employee'] = {
    onload: function (listview) {
        listview.page.add_inner_button(__('Sync Now'), function () {

            frappe.show_alert(
                {
                    message: __('Employee sync has started'),
                    indicator: 'blue'
                },
                5
            );

            // 🔁 Get integration source dynamically
            frappe.db.get_single_value('BioTime Settings', 'integration_source')
                .then((source) => {

                    let method = "";

                    if (source === "BioTime") {
                        method = "biotime_erpgulf.employee.sync_biotime_employees";
                    } else if (source === "UBio Alpeta") {
                        method = "biotime_erpgulf.ubio_employee.sync_ubio_employees";
                    }

                    // ⚠ Safety check
                    if (!method) {
                        frappe.msgprint(__('Integration Source not configured!'));
                        return;
                    }

                    frappe.call({
                        method: method,
                        callback: function (r) {
                            if (!r.exc) {
                                if (r.message && r.message.message) {
                                    frappe.msgprint(__(r.message.message));
                                } else {
                                    frappe.msgprint(__('Employee sync started successfully'));
                                }
                                listview.refresh();
                            }
                        },
                        error: function () {
                            frappe.msgprint(__('Failed to start employee sync'));
                        }
                    });

                });
        });
    }
};