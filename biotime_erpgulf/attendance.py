import requests
import frappe
from datetime import datetime, timedelta
from frappe.utils import get_datetime, get_time
import traceback



def time_diff_in_minutes(time1, time2):
    dt1 = datetime.combine(datetime.today(), time1)
    dt2 = datetime.combine(datetime.today(), time2)
    return abs((dt1 - dt2).total_seconds()) / 60


def get_shift_info(employee):
    sa = frappe.get_all(
        "Shift Assignment",
        filters={"employee": employee, "docstatus": 1},
        fields=["shift_type"],
        order_by="start_date desc",
        limit=1,
    )
    if sa:
        return sa[0].shift_type

    return frappe.db.get_value("Employee", employee, "default_shift")


def get_log_type(employee, punch_dt, punch_state_display):
    shift_type = get_shift_info(employee)

    if not shift_type:
        return "IN" if punch_state_display == "Check In" else "OUT"

    shift = frappe.get_doc("Shift Type", shift_type)

    start = get_time(shift.start_time)
    end = get_time(shift.end_time)
    late_grace = int(shift.late_entry_grace_period or 0)
    early_grace = int(shift.early_exit_grace_period or 0)

    punch_time = punch_dt.time()

    if punch_state_display == "Check In":
        if punch_time > start and time_diff_in_minutes(punch_time, start) > late_grace:
            return "Late Entry"
        return "IN"

    if punch_state_display == "Check Out":
        if punch_time < end and time_diff_in_minutes(end, punch_time) > early_grace:
            return "Early Exit"
        return "OUT"

    return "IN"


def update_employee_custom_in(employee, punch_state):
    new_status = 1 if punch_state.lower().startswith("check in") else 0
    frappe.db.set_value("Employee", employee, "custom_in", new_status)


def checkin_exists(employee, punch_dt):
    return frappe.db.exists(
        "Employee Checkin",
        {
            "employee": employee,
            "time": punch_dt,
            "device_id": "BioTime",
        },
    )



@frappe.whitelist()
def biotime_attendance():
    frappe.enqueue(
        "biotime_erpgulf.attendance.run_biotime_attendance",
        queue="long",
        job_name="BioTime Monthly Datetime Sync",
    )
    return {"message": "BioTime monthly sync started"}



def run_biotime_attendance():
    logger = frappe.logger("biotime")

    try:
        settings = frappe.get_single("BioTime Settings")  
    except Exception:
        frappe.throw("BioTime Settings DocType not found")

    if not settings.start_year:
        frappe.throw("Start Year is mandatory in BioTime Settings")

    if settings.last_synced_datetime:
        start_dt = get_datetime(settings.last_synced_datetime)
    else:
        start_dt = datetime(int(settings.start_year), 1, 1)

    end_dt = start_dt + timedelta(days=30)

    logger.info(f"BioTime sync window: {start_dt} → {end_dt}")

    base_url = settings.biotime_url.rstrip("/") + "/iclock/api/transactions/"
    headers = {"Authorization": f"Token {settings.biotime_token}"}

    inserted = 0
    skipped = 0
    page = 1

    while True:
        try:
            response = requests.get(
                base_url,
                headers=headers,
                params={
                    "start_time": start_dt.strftime("%Y-%m-%d %H:%M:%S"),
                    "end_time": end_dt.strftime("%Y-%m-%d %H:%M:%S"),
                    "page": page,
                },
                timeout=90,
            )
            response.raise_for_status()
            payload = response.json()
            rows = payload.get("data") or []

        except Exception:
            logger.exception("BioTime API failed")
            break

        if not rows:
            break

        for row in rows:
            try:
                emp_code = row.get("emp_code")
                punch_time = row.get("punch_time")
                punch_state = row.get("punch_state_display")

                if not (emp_code and punch_time and punch_state):
                    skipped += 1
                    continue

                punch_dt = get_datetime(punch_time)

                employee = frappe.db.get_value(
                    "Employee",
                    {"biotime_emp_code": emp_code},
                    "name",
                )

                if not employee or checkin_exists(employee, punch_dt):
                    skipped += 1
                    continue

                log_type = get_log_type(employee, punch_dt, punch_state)

                frappe.get_doc(
                    {
                        "doctype": "Employee Checkin",
                        "employee": employee,
                        "time": punch_dt,
                        "log_type": log_type,
                        "device_id": "BioTime",
                    }
                ).insert(ignore_permissions=True)

                update_employee_custom_in(employee, punch_state)
                inserted += 1

            except Exception:
                logger.exception("Row insert failed")
                skipped += 1

        if payload.get("next"):
            page += 1
        else:
            break

    frappe.db.set_value(
        "BioTime Settings",
        None,
        "last_synced_datetime",
        end_dt,
    )
    frappe.db.commit()

    logger.info(f"BioTime sync done. Inserted={inserted}, Skipped={skipped}")
    return f"Inserted={inserted}, Skipped={skipped}"
