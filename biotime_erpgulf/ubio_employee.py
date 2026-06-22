import frappe
import requests
from frappe.utils import nowdate
from datetime import datetime
# from biotime_erpgulf.ubio_attendance import get_ubio_session, clear_ubio_session


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

@frappe.whitelist()
def sync_ubio_employees():
    frappe.enqueue(
        "biotime_erpgulf.ubio_employee.run_ubio_employee_sync",
        queue="long",
        job_name="UBio Employee Sync",
    )
    return {"message": "UBio employee sync started"}


def run_ubio_employee_sync():
    frappe.db.sql("SET SESSION innodb_lock_wait_timeout = 300")
    logger = frappe.logger("ubio_employee")

    try:
        settings = frappe.get_single("BioTime Settings")
        base_url = settings.ubio_url.rstrip("/")
        start_date = datetime.strptime(settings.start_date, "%Y-%m-%d").strftime("%Y-%m-%d")
        end_date = datetime.strptime(settings.end_date, "%Y-%m-%d").strftime("%Y-%m-%d")

        # start_date = str(datetime.strptime(
        #     settings.start_date, "%Y-%m-%d"
        # ).strftime("%Y-%m-%d"))

        # end_date = str(datetime.strptime(
        #     settings.end_date, "%Y-%m-%d"
        # ).strftime("%Y-%m-%d"))

        # ✅ Auto-login to get fresh session
        try:
            cookie_header = get_ubio_session(settings)
        except Exception as login_err:
            frappe.log_error(str(login_err), "UBio Login Failed")
            return {"status": "error", "message": f"Login failed: {str(login_err)}"}

        def fetch_logs(cookie):
            return requests.get(
                f"{base_url}/v1/authLogs",
                params={
                    "startTime": start_date,
                    "endTime": end_date,
                    "offset": 0,
                    "limit": settings.limit_no_of_records or 100
                },
                headers={"Cookie": cookie},
                timeout=60
            )

        response = fetch_logs(cookie_header)

        # ✅ If 401 — clear cache and retry with fresh login
        if response.status_code == 401:
            clear_ubio_session()
            cookie_header = get_ubio_session(settings)
            response = fetch_logs(cookie_header)

        data = response.json()
        logs = data.get("AuthLogList", [])
        frappe.log_error("logs", logs)

        inserted = 0
        skipped = 0

        for log in logs:
            emp_id = log.get("UserID")
            emp_name = (log.get("UserName") or "").strip()

            if not emp_id:
                skipped += 1
                continue

            if not emp_name:
                emp_name = f"Employee {emp_id}"

            existing = frappe.db.exists(
                "Employee",
                {"ubio_emp_code": emp_id}
            )

            if not existing:
                try:
                    employee = frappe.get_doc({
                        "doctype": "Employee",
                        "employee_name": emp_name,
                        "first_name": emp_name,
                        "ubio_emp_code": emp_id,
                        "status": "Active",
                        "company": frappe.defaults.get_user_default("Company"),
                        "gender": "Male",
                        "date_of_birth": "2000-01-01",
                        "date_of_joining": "2020-01-01",
                    })
                    employee.insert(ignore_permissions=True)
                    frappe.db.commit()
                    inserted += 1
                except Exception as e:
                    frappe.log_error(
                        f"Failed to insert emp_id={emp_id}: {str(e)}",
                        "UBio Employee Insert Error"
                    )
                    frappe.db.rollback()
                    skipped += 1
            else:
                skipped += 1

        summary = f"UBio Employee Sync Done | Inserted: {inserted}, Skipped: {skipped}"
        frappe.log_error(summary, "UBio Employee Sync Summary")
        return {"status": "success", "message": summary}

    except Exception as e:
        frappe.log_error(
            message=str(e),
            title="UBio Employee Sync Failed"
        )
        return {
            "status": "error",
            "message": str(e)
        }