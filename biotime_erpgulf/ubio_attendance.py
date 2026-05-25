import requests
import frappe
from datetime import datetime, timedelta
from frappe.utils import get_datetime, get_time, now_datetime, getdate
from biotime_erpgulf.ubio_attendance_processor import mark_attendance_from_checkins



def checkin_exists(employee, punch_dt):
    # Treat any punch within the same minute as duplicate
    start = punch_dt.replace(second=0, microsecond=0)
    end = start + timedelta(minutes=1)

    return frappe.db.exists(
        "Employee Checkin",
        {
            "employee": employee,
            "device_id": "BioTime",
            "time": ["between", [start, end]],
        },
    )


def process_simple_checkin(row):
    emp_code = row.get("emp_code")
    punch_time = row.get("punch_time")
    punch_state = row.get("punch_state_display")
    area_alias = row.get("area_alias") or None

    if not (emp_code and punch_time and punch_state):
        return "skipped"

    punch_dt = get_datetime(punch_time)

    employee = frappe.db.get_value(
        "Employee",
        {"biotime_emp_code": emp_code},
        "name",
    )
    if not employee:
        return "skipped"

    if checkin_exists(employee, punch_dt):
        return "skipped"

    log_type = "IN" if punch_state == "Check In" else "OUT"

    frappe.get_doc(
        {
            "doctype": "Employee Checkin",
            "employee": employee,
            "time": punch_dt,
            "log_type": log_type,
            "device_id": "BioTime",
            "custom_location_id": area_alias,
        }
    ).insert(ignore_permissions=True)

    return "inserted"


@frappe.whitelist()
def biotime_attendance():
    frappe.enqueue(
        "biotime_erpgulf.ubio_attendance.run_ubio_attendance",
        queue="long",
        job_name="UBio Alpeta Sync",
    )
    return {"message": "UBio Alpeta sync started"}



def run_ubio_attendance():

    logger = frappe.logger("ubio")

    try:
        settings = frappe.get_single("BioTime Settings")

        inserted = 0
        skipped = 0
        start_date = datetime.strptime(
            settings.start_date,
            "%Y-%m-%d"
        ).strftime("%Y-%m-%d")

        end_date = datetime.strptime(
            settings.end_date,
            "%Y-%m-%d"
        ).strftime("%Y-%m-%d")

        response = requests.get(
            f"{settings.ubio_url.rstrip('/')}/v1/authLogs",
            params={
                "startTime": start_date,
                "endTime": end_date,
                "offset": 0,
                "limit": settings.limit_no_of_records or 100
            },
            headers={
                # "Cookie": f"extinfo={settings.ubio_extinfo}; ucsinfo={settings.ubio_uuid}"
                "Cookie": f"extinfo=cc846eed53994e5653338f93d057b2c3; ucsinfo={settings.ubio_uuid}"
            },
            timeout=90,
        )

        response.raise_for_status()

        payload = response.json()

        rows = payload.get("AuthLogList", [])

        frappe.log_error(
            title="UBio Logs",
            message=frappe.as_json(rows[:5], indent=2)
        )

        for row in rows:

            try:
                mapped_row = {
                    "emp_code": row.get("UserID"),
                    "punch_time": row.get("EventTime"),
                    "punch_state_display": (
                        "Check In" if row.get("Func") == 1 else "Check Out"
                    ),
                    "area_alias": row.get("TerminalName")
                }

                result = process_simple_checkin(mapped_row)
                
                employee = frappe.db.get_value(
                    "Employee",
                    {"biotime_emp_code": mapped_row.get("emp_code")},
                    "name"
                )
                attendance_date = getdate(mapped_row.get("punch_time"))

                if result == "inserted":
                    inserted += 1
                else:
                    skipped += 1
                    
                if employee:
                    mark_attendance_from_checkins(
                        employee,
                        attendance_date
                    )
                    
            except frappe.UniqueValidationError:
                skipped += 1

            except Exception:
                logger.exception("UBio row failed")
                skipped += 1

        frappe.db.commit()

        logger.info(
            f"UBio sync done | Inserted={inserted} | Skipped={skipped}"
        )

        return {
            "status": "success",
            "message": f"Inserted: {inserted}, Skipped: {skipped}"
        }

    except Exception as e:

        frappe.log_error(
            title="UBio Attendance Sync Failed",
            message=str(e)
        )

        return {
            "status": "error",
            "message": str(e)
        }