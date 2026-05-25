import frappe
import requests
from frappe.utils import nowdate
from datetime import datetime


@frappe.whitelist()
def sync_ubio_employees():
    frappe.enqueue(
        "biotime_erpgulf.ubio_employee.run_ubio_employee_sync",
        queue="long",
        job_name="UBio Employee Sync",
    )
    return {"message": "UBio employee sync started"}


def run_ubio_employee_sync():
    logger = frappe.logger("ubio_employee")

    try:
        settings = frappe.get_single("BioTime Settings")
        base_url = settings.ubio_url.rstrip("/")
        employees = {}
        start_date = str(datetime.strptime(
            settings.start_date,
            "%Y-%m-%d"
        ).strftime("%Y-%m-%d"))

        end_date = str(datetime.strptime(
            settings.end_date,
            "%Y-%m-%d"
        ).strftime("%Y-%m-%d"))
        # frappe.log_error("start_date", start_date)
        # frappe.log_error("end_date", end_date)
        response = requests.get(
            f"{base_url}/v1/authLogs",
            params={
                "startTime": start_date,
                "endTime": end_date,
                "offset": 0,
                # "limit": 10
                "limit": settings.limit_no_of_records or 100
            },
            headers={
                # "Cookie": "extinfo=cc846eed53994e5653338f93d057b2c3; ucsinfo=c508047c-b517-4ace-6ff5-66af31f7032c"
                "Cookie": f"extinfo=cc846eed53994e5653338f93d057b2c3; ucsinfo={settings.ubio_uuid}"
            },
            timeout=60
        )
        data = response.json()
        logs = data.get("AuthLogList", [])
        frappe.log_error("logs", logs)
        
        for log in logs:

            emp_id = log.get("UserID")
            emp_name = log.get("UserName")

            # skip empty users
            if not emp_id or not emp_name:
                continue

            existing = frappe.db.exists(
                "Employee",
                {"biotime_emp_code": emp_id}
            )

            if not existing:

                employee = frappe.get_doc({
                    "doctype": "Employee",
                    "employee_name": emp_name.strip(),
                    "first_name": emp_name.strip(),
                    "biotime_emp_code": emp_id,
                    "status": "Active",
                    "company": frappe.defaults.get_user_default("Company"),

                    # mandatory fields
                    "gender": "Male",
                    "date_of_birth": "2000-01-01",
                    "date_of_joining": frappe.utils.nowdate()
                })

                employee.insert(ignore_permissions=True)
        
        # while True:
            # frappe.log_error("1")
            # response = requests.get(
            #     f"{base_url}/v1/authLogs",
            #     params={
            #         "startTime": "2020-01-01",
            #         "endTime": "2026-04-30",
            #         "offset": offset,
            #         "limit": limit
            #     },
            #     # headers={
            #     #     "Cookie": f"ucsinfo={settings.ubio_uuid}"
            #     # },
            #     headers = {
            #         "Cookie":"extinfo=cc846eed53994e5653338f93d057b2c3; ucsinfo=7280fecc-72ea-42d5-4d8b-98b97181ee05",
            #         "Content-Type": "application/json"
            #     },
            #     timeout=60
            # )
            # frappe.log_error("response",response)
            # frappe.log_error("Final URL", response.url)

            # response.raise_for_status()
            # data = response.json()

            # logs = data.get("AuthLogList", [])
            # frappe.log_error("logs",logs)
            # total = data.get("Total", {}).get("Count", 0)

            # if not logs:
            #     break
            # frappe.log_error("2")

            # for log in logs:
            #     emp_id = log.get("UserID")
            #     name = log.get("UserName")

            #     # skip empty users
            #     if not emp_id:
            #         continue

            #     if emp_id not in employees:
            #         employees[emp_id] = name.strip()

            # offset += limit
            # frappe.log_error("3")

            # logger.info(f"Fetched {offset}/{total}")

            # if offset >= total:
            #     break
        # ✅ Create Employees
        # default_company = frappe.db.get_single_value("Global Defaults", "default_company")

        # inserted = 0
        # updated = 0

        # for emp_id, full_name in employees.items():
        #     frappe.log_error("4")

        #     employee_doc = {
        #         "doctype": "Employee",
        #         "employee_name": full_name,
        #         "first_name": full_name,
        #         "company": default_company,
        #         "status": "Active",
        #         "naming_series": "HR-EMP-",
        #         "biotime_emp_code": emp_id
        #     }

        #     try:
        #         existing = frappe.db.exists("Employee", {"biotime_emp_code": emp_id})

        #         if not existing:
        #             frappe.get_doc(employee_doc).insert(ignore_permissions=True)
        #             inserted += 1
        #         else:
        #             doc = frappe.get_doc("Employee", existing)
        #             doc.update(employee_doc)
        #             doc.save(ignore_permissions=True)
        #             updated += 1

        #     except Exception as e:
        #         frappe.log_error(
        #             message=str(e),
        #             title="UBio Employee Error"
        #         )

        # summary = f"UBio Sync Done | Inserted: {inserted}, Updated: {updated}"

        # logger.info(summary)

        # return {
        #     "status": "success",
        #     "message": summary
        # }

    except Exception as e:
        frappe.log_error(
            message=str(e),
            title="UBio Employee Sync Failed"
        )
        return {
            "status": "error",
            "message": str(e)
        }