
frappe.listview_settings['Employee'] = {
    onload: function (listview) {
        listview.page.add_inner_button(__('Sync Now'), function () {

            frappe.show_alert(
                {
                    message: __('BioTime employee sync has started'),
                    indicator: 'blue'
                },
                5
            );

            frappe.call({
                method: "biotime_erpgulf.employee.sync_biotime_employees",
                callback: function (r) {
                    if (!r.exc) {
                        if (r.message && r.message.status === "success") {
                            frappe.msgprint(__(r.message.message));
                        } else {
                            frappe.msgprint(__('Employee sync request submitted successfully'));
                        }
                        listview.refresh();
                    }
                },
                error: function () {
                    frappe.msgprint(__('Failed to start BioTime sync'));
                }
            });
        });
    }
};
