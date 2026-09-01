frappe.ui.form.on('Salary Structure Assignment', {
    base: function (frm) {
        if (!frm.doc.base) {
            return;
        }

        frappe.call({
            method: 'biotime_erpgulf.biotime_erpgulf.api.calculate_salary_allowances',
            args: {
                base: frm.doc.base
            },
            callback: function (r) {
                if (!r.exc && r.message) {
                    frm.set_value('custom_house_allowance', r.message.housing_allowance);
                    frm.set_value('custom_transportation_allowance', r.message.transportation_allowance);
                }
            }
        });
    }
});
