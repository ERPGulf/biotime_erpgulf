import requests
import frappe
from datetime import datetime, timedelta
from collections import defaultdict
from frappe.utils import get_datetime, get_time
import pytz

def time_diff_in_minutes(time1, time2):
    """Return absolute difference in minutes between two time/datetime objects"""
    if isinstance(time1, datetime) and isinstance(time2, datetime):
        diff = abs((time1 - time2).total_seconds())
    else:
        dt1 = datetime.combine(datetime.today(), time1)
        dt2 = datetime.combine(datetime.today(), time2)
        diff = abs((dt1 - dt2).total_seconds())
    return diff / 60

def get_shift_info(employee):
    """Return latest shift_type and shift_location for employee"""
    sa = frappe.get_all(
        "Shift Assignment",
        filters=[["employee", "=", employee], ["docstatus", "=", 1]],
        fields=["shift_type", "shift_location"],
        order_by="start_date desc",
        limit=1
    )
    if sa:
        return sa[0].shift_type, sa[0].shift_location
    return frappe.db.get_value("Employee", employee, "default_shift"), None

def get_shift_tz_for_location(shift_location):
    if shift_location == "Beirut, Lebanon":
        return pytz.timezone("Asia/Beirut")
    elif shift_location == "Riyadh, Saudi Arabia":
        return pytz.timezone("Asia/Riyadh")
    return pytz.UTC

def get_log_type(employee, punch_time, punch_state_display):
    """Determine log type (IN, OUT, Late Entry, Early Exit considering shift)"""
    punch_dt = punch_time

    shift_type, shift_location = get_shift_info(employee)
    if not shift_type:
        return "IN" if punch_state_display == "Check In" else "OUT"

    shift_doc = frappe.get_doc("Shift Type", shift_type)
    start_time = get_time(shift_doc.start_time)
    end_time = get_time(shift_doc.end_time)
    late_grace = int(shift_doc.late_entry_grace_period or 0)
    early_grace = int(shift_doc.early_exit_grace_period or 0)

    punch_time_only = punch_dt.time()

    if punch_state_display == "Check In":
        diff = time_diff_in_minutes(punch_time_only, start_time)
        if punch_time_only > start_time and diff > late_grace:
            return "Late Entry"
        return "IN"
    elif punch_state_display == "Check Out":
        diff = time_diff_in_minutes(end_time, punch_time_only)
        if punch_time_only < end_time and diff > early_grace:
            return "Early Exit"
        return "OUT"
    return "IN"

@frappe.whitelist()
def biotime_attendance():
    frappe.msgprint("Starting BioTime Sync...")
    settings = frappe.get_single("BioTime Settings")
    url = settings.biotime_url.rstrip("/") + "/iclock/api/transactions/"
    token = settings.biotime_token

    headers = {
        "Authorization": f"Token {token}",
        "Content-Type": "application/json"
    }

    inserted_count = 0
    skipped_count = 0
    employee_punches = defaultdict(lambda: {"Check In": [], "Check Out": []})

    while url:
        try:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            data = response.json()
        except Exception:
            frappe.log_error(frappe.get_traceback(), "BioTime Sync Error")
            break

        rows = data.get("data", [])
        frappe.log_error(f"Fetched {len(rows)} rows from {url}", "BioTime Debug")

        for row in rows:
            emp_code = row.get("emp_code")
            punch_time = row.get("punch_time")
            punch_state_display = row.get("punch_state_display")
            upload_time = row.get("upload_time")

            if not (emp_code and punch_time and punch_state_display and upload_time):
                skipped_count += 1
                continue

            employee = frappe.db.get_value("Employee", {"biotime_emp_code": emp_code}, "name")
            if not employee:
                skipped_count += 1
                continue

            punch_dt = get_datetime(punch_time)  # naive datetime
            upload_dt = get_datetime(upload_time)  # naive datetime

            local_date = punch_dt.date()

            employee_punches[(employee, local_date)][punch_state_display].append({
                "punch_dt": punch_dt,
                "upload_time": upload_dt
            })

        url = data.get("next")

    # Insert only latest punches
    for (employee, local_date), punches in employee_punches.items():
        employee_name = frappe.db.get_value("Employee", employee, "employee_name") or ""
        local_start = datetime(local_date.year, local_date.month, local_date.day, 0, 0, 0)
        local_end = local_start + timedelta(days=1)

        # Check In
        if punches["Check In"]:
            last_checkin_data = max(punches["Check In"], key=lambda x: x["upload_time"])
            last_checkin = last_checkin_data["punch_dt"]
            log_type = get_log_type(employee, last_checkin, "Check In")

            # Delete older punches
            frappe.db.sql("""
                DELETE FROM `tabEmployee Checkin`
                WHERE employee=%s AND device_id='BioTime'
                AND log_type IN ('IN','Late Entry') AND time BETWEEN %s AND %s
            """, (employee, local_start, local_end))
            frappe.db.commit()

            try:
                frappe.get_doc({
                    "doctype": "Employee Checkin",
                    "employee": employee,
                    "employee_name": employee_name,
                    "time": last_checkin,
                    "log_type": log_type,
                    "device_id": "BioTime"
                }).insert(ignore_permissions=True)
                frappe.db.commit()
                inserted_count += 1
            except Exception:
                frappe.log_error(frappe.get_traceback(), f"BioTime Sync Error - Check In {employee}")
                skipped_count += 1

        # Check Out
        if punches["Check Out"]:
            last_checkout_data = max(punches["Check Out"], key=lambda x: x["upload_time"])
            last_checkout = last_checkout_data["punch_dt"]
            log_type = get_log_type(employee, last_checkout, "Check Out")

            # Delete older punches
            frappe.db.sql("""
                DELETE FROM `tabEmployee Checkin`
                WHERE employee=%s AND device_id='BioTime'
                AND log_type IN ('OUT','Early Exit') AND time BETWEEN %s AND %s
            """, (employee, local_start, local_end))
            frappe.db.commit()

            try:
                frappe.get_doc({
                    "doctype": "Employee Checkin",
                    "employee": employee,
                    "employee_name": employee_name,
                    "time": last_checkout,
                    "log_type": log_type,
                    "device_id": "BioTime"
                }).insert(ignore_permissions=True)
                frappe.db.commit()
                inserted_count += 1
            except Exception:
                frappe.log_error(frappe.get_traceback(), f"BioTime Sync Error - Check Out {employee}")
                skipped_count += 1

    return f"BioTime Sync completed. Inserted: {inserted_count}, Skipped: {skipped_count}"
