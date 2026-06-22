# ubio_attendance_processor.py

import frappe
from frappe.utils import getdate, get_time, today, add_days
def mark_attendance_from_checkins(employee, attendance_date):

    has_shift = frappe.db.exists(
        "Shift Assignment",
        {
            "employee": employee,
            "start_date": ["<=", attendance_date],
            "docstatus": 1,
            "status": "Active",
            "end_date": ["in", ["", None]],  # no end date = permanent
        }
    ) or frappe.db.exists(
        "Shift Assignment",
        {
            "employee": employee,
            "start_date": ["<=", attendance_date],
            "end_date": [">=", attendance_date],  # end date not yet passed
            "docstatus": 1,
            "status": "Active",
        }
    )
    if has_shift:
        return "has_shift_assignment"

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
            "attendance_date": attendance_date,
            "docstatus": ["!=", 2],
        }
    ):
        return "attendance_exists"

    employee_name = frappe.db.get_value("Employee", employee, "employee_name")

    attendance = frappe.get_doc({
        "doctype": "Attendance",
        "employee": employee,
        "employee_name": employee_name,
        "attendance_date": attendance_date,
        "status": "Present",
        "shift": "",  # no shift — that's why we're here
        "in_time": first_in,
        "out_time": last_out,
    })

    attendance.insert(ignore_permissions=True, ignore_links=True)
    attendance.submit()

    return "attendance_marked"

# def mark_attendance_from_checkins(employee, attendance_date):

#     checkins = frappe.get_all(
#         "Employee Checkin",
#         filters={
#             "employee": employee,
#             "time": ["between", [
#                 f"{attendance_date} 00:00:00",
#                 f"{attendance_date} 23:59:59"
#             ]]
#         },
#         fields=["name", "time", "log_type"],
#         order_by="time asc"
#     )

#     if not checkins:
#         return "no_checkins"

#     first_in = None
#     last_out = None

#     for row in checkins:
#         if row.log_type == "IN" and not first_in:
#             first_in = row.time
#         if row.log_type == "OUT":
#             last_out = row.time

#     # fallback
#     if not first_in:
#         first_in = checkins[0].time
#     if not last_out:
#         last_out = checkins[-1].time

#     # Skip if attendance already exists
#     if frappe.db.exists(
#         "Attendance",
#         {
#             "employee": employee,
#             "attendance_date": attendance_date,
#             "docstatus": ["!=", 2],  # not cancelled
#         }
#     ):
#         return "attendance_exists"

#     matched_shift = ""
#     first_in_time = get_time(first_in)
#     shifts = frappe.get_all(
#         "Shift Type",
#         fields=["name", "start_time", "end_time"]
#     )

#     for shift in shifts:
#         shift_start = get_time(shift.start_time)
#         shift_end = get_time(shift.end_time)
#         if shift_start <= first_in_time <= shift_end:
#             matched_shift = shift.name
#             break

#     # frappe.log_error(
#     #     title="Shift Match Debug",
#     #     message=f"""
#     #     Employee: {employee}
#     #     Date: {attendance_date}
#     #     First IN: {first_in}
#     #     Last OUT: {last_out}
#     #     Matched Shift: {matched_shift}
#     #     """
#     # )
#     employee_name = frappe.db.get_value("Employee", employee, "employee_name")

#     attendance = frappe.get_doc({
#         "doctype": "Attendance",
#         "employee": employee,
#         "employee_name": employee_name,
#         "attendance_date": attendance_date,
#         "status": "Present",
#         "shift": matched_shift,
#         "in_time": first_in,
#         "out_time": last_out,
#     })

#     attendance.insert(ignore_permissions=True, ignore_links=True)
#     attendance.submit()

#     return "attendance_marked"

def process_daily_attendance():
    from frappe.utils import today, add_days, getdate, date_diff

    yesterday = getdate(add_days(today(), -1))
    cache_key = f"last_attendance_sync_date:{frappe.local.site}"
    last_sync = frappe.cache().get_value(cache_key)

    if last_sync:
        start_date = getdate(add_days(last_sync, 1))
    else:
        start_date = getdate(add_days(today(), -30))
    if date_diff(yesterday, start_date) > 60:
        start_date = getdate(add_days(yesterday, -60))

    if start_date > yesterday:
        frappe.log_error(
            title="Daily Attendance Summary",
            message="Nothing to process — attendance is up to date."
        )
        return

    frappe.log_error(
        title="Daily Attendance Summary",
        message=f"Processing attendance from {start_date} to {yesterday}"
    )

    employees = frappe.get_all(
        "Employee",
        filters={"status": "Active"},
        fields=["name", "date_of_joining"]
    )

    current_date = start_date
    while current_date <= yesterday:
        inserted = 0
        skipped = 0
        errors = 0

        for emp in employees:
            try:
                if emp.date_of_joining and getdate(emp.date_of_joining) > current_date:
                    skipped += 1
                    continue
                result = mark_attendance_from_checkins(emp.name, current_date)
                if result == "attendance_marked":
                    inserted += 1
                elif result == "has_shift_assignment":
                    skipped += 1  
                else:
                    skipped += 1
                # result = mark_attendance_from_checkins(emp.name, current_date)
                # if result == "attendance_marked":
                #     inserted += 1
                # else:
                #     skipped += 1

            except Exception:
                frappe.log_error(
                    title="Daily Attendance Error",
                    message=f"Employee: {emp.name} | Date: {current_date}"
                )
                errors += 1

        frappe.db.commit()
        frappe.log_error(
            title="Daily Attendance Summary",
            message=f"Date: {current_date} | Marked: {inserted} | Skipped: {skipped} | Errors: {errors}"
        )

        current_date = getdate(add_days(current_date, 1))
    frappe.cache().set_value(
        cache_key,
        str(yesterday),
        expires_in_sec=60 * 60 * 24 * 90 
    )

    frappe.log_error(
        title="Daily Attendance Summary",
        message=f"Last attendance sync date updated to {yesterday}"
    )