import frappe
from frappe.utils import getdate, get_time


def mark_attendance_from_checkins(employee, attendance_date):

    checkins = frappe.get_all(
        "Employee Checkin",
        filters={
            "employee": employee,
            "time": ["between", [
                f"{attendance_date} 00:00:00",
                f"{attendance_date} 23:59:59"
            ]]
        },
        fields=["name", "time", "log_type"],
        order_by="time asc"
    )

    if not checkins:
        return "no_checkins"

    first_in = None
    last_out = None

    for row in checkins:

        if row.log_type == "IN" and not first_in:
            first_in = row.time

        if row.log_type == "OUT":
            last_out = row.time

    # fallback
    if not first_in:
        first_in = checkins[0].time

    if not last_out:
        last_out = checkins[-1].time

    # Skip if attendance already exists
    if frappe.db.exists(
        "Attendance",
        {
            "employee": employee,
            "attendance_date": attendance_date
        }
    ):
        return "attendance_exists"

    matched_shift = ""
    first_in_time = get_time(first_in)
    shifts = frappe.get_all(
        "Shift Type",
        fields=["name", "start_time", "end_time"]
    )

    for shift in shifts:

        shift_start = get_time(shift.start_time)
        shift_end = get_time(shift.end_time)

        if shift_start <= first_in_time <= shift_end:
            matched_shift = shift.name
            break

    frappe.log_error(
        title="Shift Match Debug",
        message=f"""
        Employee: {employee}
        Date: {attendance_date}
        First in: {first_in_time}
        First IN: {first_in}
        Last OUT: {last_out}
        Matched Shift: {matched_shift}
        """
    )

    attendance = frappe.get_doc({
        "doctype": "Attendance",
        "employee": employee,
        "attendance_date": attendance_date,
        "status": "Present",
        "shift": matched_shift
    })

    attendance.insert(ignore_permissions=True)
    attendance.submit()

    return "attendance_marked"