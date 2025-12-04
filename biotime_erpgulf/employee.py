import frappe
import requests
from frappe.utils import getdate, nowdate
from collections import defaultdict

def execute():
    sync_biotime_employees()

@frappe.whitelist()
def sync_biotime_employees():
    try:
        settings = frappe.get_single("BioTime Settings")
        url = settings.biotime_url.rstrip("/") + "/personnel/api/employees/"
        token = settings.biotime_token

        headers = {
            "Authorization": f"Token {token}",
            "Content-Type": "application/json"
        }

        emp_type_map = {1: "Full-time", 2: "Part-time", 3: "Contract"}
        gender_map = {"M": "Male", "F": "Female"}
        default_company = frappe.db.get_single_value("Global Defaults", "default_company")

        total_fetched = 0
        total_inserted = 0
        total_updated = 0

        page = 1

        while url:
            try:
                response = requests.get(url, headers=headers, timeout=30)
                response.raise_for_status()
                data = response.json()
            except Exception as req_err:
                frappe.log_error(f"BioTime Employee Sync Error: {str(req_err)}", "BioTime Sync")
                break

            employees = data.get("data", [])
            frappe.log_error(f"Page {page}: Fetched {len(employees)} employees", "BioTime Employee Sync")
            total_fetched += len(employees)

            for emp in employees:
                emp_code = emp.get("emp_code")
                if not emp_code:
                    continue

                first_name = emp.get("first_name") or ""
                last_name = emp.get("last_name") or ""
                full_name = f"{first_name} {last_name}".strip()
                gender = gender_map.get(emp.get("gender"), "")
                employment_type = emp_type_map.get(emp.get("emp_type"))
                hire_date = emp.get("hire_date")
                birthday = emp.get("birthday")

                department = emp.get("department", {}).get("dept_name") if emp.get("department") else ""
                designation = emp.get("position", {}).get("position_name") if emp.get("position") else ""
                mobile_no = emp.get("mobile") or ""
                current_address = emp.get("address") or ""
                personal_email = emp.get("email") or ""

                if emp.get("attemployee", {}).get("enable_attendance") is False:
                    erp_status = "Left"
                    relieving_date = getdate(emp.get("update_time")) if emp.get("update_time") else nowdate()
                else:
                    erp_status = "Active"
                    relieving_date = None

                employee_doc = {
                    "doctype": "Employee",
                    "employee_name": full_name,
                    "first_name": first_name,
                    "last_name": last_name,
                    "gender": gender,
                    "date_of_joining": getdate(hire_date) if hire_date else None,
                    "date_of_birth": getdate(birthday) if birthday else None,
                    "department": department,
                    "designation": designation,
                    "employment_type": employment_type,
                    "cell_number": mobile_no,
                    "current_address": current_address,
                    "personal_email": personal_email,
                    "company": default_company,
                    "status": erp_status,
                    "relieving_date": relieving_date,   
                    "naming_series": "HR-EMP-",
                    "biotime_emp_code": emp_code
                }

                try:
                    existing = frappe.db.exists("Employee", {"biotime_emp_code": emp_code})
                    if not existing:
                        doc = frappe.get_doc(employee_doc)
                        doc.insert(ignore_permissions=True)
                        total_inserted += 1
                        frappe.log_error(f"Inserted employee {emp_code} ({full_name})", "BioTime Sync")
                    else:
                        doc = frappe.get_doc("Employee", existing)
                        doc.update(employee_doc)
                        doc.save(ignore_permissions=True)
                        total_updated += 1
                        frappe.log_error(f"Updated employee {emp_code} ({full_name})", "BioTime Sync")

                except Exception as sync_err:
                    frappe.log_error(f"Error syncing {emp_code}: {str(sync_err)}", "BioTime Sync")

            url = data.get("next")
            page += 1

        summary = f"BioTime Employee Sync completed. Total fetched: {total_fetched}, Inserted: {total_inserted}, Updated: {total_updated}"
        frappe.log_error(summary, "BioTime Sync Summary")
        return {"status": "success", "message": summary}

    except Exception as e:
        frappe.log_error(f"Sync failed: {str(e)}", "BioTime Sync")
        return {"status": "error", "message": str(e)}