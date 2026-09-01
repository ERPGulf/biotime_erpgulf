import frappe


@frappe.whitelist()
def calculate_salary_allowances(base):
    """Calculate Housing and Transportation allowance from base salary.

    Housing Allowance = 25% of base
    Transportation Allowance = 10% of base
    """
    base = frappe.utils.flt(base)

    housing_allowance = base * 0.25
    transportation_allowance = base * 0.10

    return {
        "housing_allowance": housing_allowance,
        "transportation_allowance": transportation_allowance,
    }
