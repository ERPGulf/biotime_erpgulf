import requests
import frappe
from datetime import datetime, timedelta
from frappe.utils import get_datetime, get_time, now_datetime, getdate


def get_ubio_session(settings):
    cache_key = f"ubio_session:{frappe.local.site}"
    cached = frappe.cache().get_value(cache_key)
    if cached:
        return cached

    base_url = settings.ubio_url.rstrip("/")

    response = requests.post(
        f"{base_url}/v1/login",
        json={"userId": "1111", "password": "1598753", "userType": 0},
        headers={"Content-Type": "application/json"},
        timeout=30
    )
    response.raise_for_status()

    extinfo = response.cookies.get("extinfo") or ""
    new_uuid = response.cookies.get("ucsinfo") or settings.ubio_uuid

    if not extinfo:
        extinfo = response.json().get("extinfo") or ""

    if not extinfo:
        raise Exception(f"UBio login succeeded but no extinfo in response: {response.text[:200]}")

    cookie_header = f"extinfo={extinfo}; ucsinfo={new_uuid}"
    frappe.cache().set_value(cache_key, cookie_header, expires_in_sec=60 * 60 * 8)
    return cookie_header


def clear_ubio_session():
    frappe.cache().delete_value(f"ubio_session:{frappe.local.site}")


# def get_ubio_emp_codes():
#     """Return cached set of emp_codes from UBio API."""
#     cache_key = f"ubio_emp_codes:{frappe.local.site}"
#     cached = frappe.cache().get_value(cache_key)
#     if cached:
#         return set(str(c) for c in cached)
#     return set()


def checkin_exists(employee, punch_dt):
    start = punch_dt.replace(second=0, microsecond=0)
    end = start + timedelta(minutes=1)
    return frappe.db.exists(
        "Employee Checkin",
        {
            "employee": employee,
            "device_id": "UBio Alpeta",
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

    # # ✅ Only process emp_codes that came from UBio API
    # ubio_codes = get_ubio_emp_codes()
    # if ubio_codes and str(emp_code) not in ubio_codes:
    #     return "skipped"

    punch_dt = get_datetime(punch_time)
    employee = frappe.db.get_value("Employee", {"ubio_emp_code": emp_code}, "name")
    if not employee:
        return "skipped"

    if checkin_exists(employee, punch_dt):
        return "skipped"

    log_type = "IN" if punch_state == "Check In" else "OUT"

    frappe.get_doc({
        "doctype": "Employee Checkin",
        "employee": employee,
        "time": punch_dt,
        "log_type": log_type,
        "device_id": "UBio Alpeta",
        "custom_location_id": area_alias,
    }).insert(ignore_permissions=True)

    return "inserted"


@frappe.whitelist()
def ubio_attendance():
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

        start_date = datetime.strptime(settings.start_date, "%Y-%m-%d").strftime("%Y-%m-%d")
        end_date = datetime.strptime(settings.end_date, "%Y-%m-%d").strftime("%Y-%m-%d")

        try:
            cookie_header = get_ubio_session(settings)
        except Exception as login_err:
            frappe.log_error(str(login_err), "UBio Login Failed")
            return {"status": "error", "message": f"Login failed: {str(login_err)}"}

        def fetch_logs(cookie):
            return requests.get(
                f"{settings.ubio_url.rstrip('/')}/v1/authLogs",
                params={
                    "startTime": start_date,
                    "endTime": end_date,
                    "offset": 0,
                    "limit": settings.limit_no_of_records or 100
                },
                headers={"Cookie": cookie},
                timeout=90,
            )

        response = fetch_logs(cookie_header)

        if response.status_code == 401:
            clear_ubio_session()
            cookie_header = get_ubio_session(settings)
            response = fetch_logs(cookie_header)

        response.raise_for_status()
        payload = response.json()
        rows = payload.get("AuthLogList", [])

        # ubio_emp_codes = list(set([
        #     str(r.get("UserID")) for r in rows if r.get("UserID")
        # ]))
        # frappe.cache().set_value(
        #     f"ubio_emp_codes:{frappe.local.site}",
        #     ubio_emp_codes,
        #     expires_in_sec=60 * 60 * 24
        # )
        # frappe.log_error(
        #     f"UBio emp_codes cached: {len(ubio_emp_codes)}",
        #     "UBio Emp Codes"
        # )

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

                if result == "inserted":
                    inserted += 1
                else:
                    skipped += 1

            except frappe.UniqueValidationError:
                skipped += 1
            except Exception:
                logger.exception("UBio row failed")
                skipped += 1

        frappe.db.commit()
        logger.info(f"UBio sync done | Inserted={inserted} | Skipped={skipped}")
        return {"status": "success", "message": f"Inserted: {inserted}, Skipped: {skipped}"}

    except Exception as e:
        frappe.log_error(title="UBio Attendance Sync Failed", message=str(e))
        return {"status": "error", "message": str(e)}