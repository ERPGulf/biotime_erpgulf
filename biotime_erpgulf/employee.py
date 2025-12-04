import frappe
import requests
from frappe.utils import getdate, nowdate

def safe_log(title, message):
    if len(title) > 140:
        title = title[:137] + "..."
    frappe.log_error(title=title, message=message)

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
        skipped_employees = []

        while url:
            try:
                response = requests.get(url, headers=headers, timeout=30)
                response.raise_for_status()
                data = response.json()
            except Exception as req_err:
                safe_log("BioTime Employee Sync Request Error", str(req_err))
                break

            employees = data.get("data", [])
            total_fetched += len(employees)

            safe_log(f"BioTime Sync Page {page}", f"Fetched {len(employees)} employees")

            for emp in employees:
                emp_code = emp.get("emp_code")
                if not emp_code:
                    skipped_employees.append(("UNKNOWN", "Missing emp_code"))
                    continue

                try:
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

                except Exception as parse_err:
                    reason = f"Data parsing error: {str(parse_err)}"
                    skipped_employees.append((emp_code, reason))
                    safe_log(f"Skipped Employee {emp_code}", reason)
                    continue

                try:
                    # ❗ NEW RULE: Search by arabic_full_name = full_name
                    arabic_match = frappe.db.get_value(
                        "Employee",
                        {"arabic_full_name": full_name},
                        "name"
                    )

                    if arabic_match:
                        # Update only mapped fields without breaking existing values
                        doc = frappe.get_doc("Employee", arabic_match)

                        # only overwrite allowed fields
                        protected_update_fields = [
                            "employee_name", "first_name", "last_name", "gender",
                            "date_of_joining", "date_of_birth", "department",
                            "designation", "employment_type", "cell_number",
                            "current_address", "personal_email", "status",
                            "relieving_date"
                        ]

                        for field in protected_update_fields:
                            if employee_doc.get(field) is not None:
                                doc.set(field, employee_doc[field])

                        # set biotime code if missing
                        if not doc.biotime_emp_code:
                            doc.biotime_emp_code = emp_code

                        doc.save(ignore_permissions=True)
                        total_updated += 1
                        continue

                    # Normal existing employee lookup
                    existing = frappe.db.exists("Employee", {"biotime_emp_code": emp_code})

                    if not existing:
                        doc = frappe.get_doc(employee_doc)
                        doc.insert(ignore_permissions=True)
                        total_inserted += 1

                    else:
                        doc = frappe.get_doc("Employee", existing)
                        doc.update(employee_doc)
                        doc.save(ignore_permissions=True)
                        total_updated += 1

                except Exception as sync_err:
                    reason = f"Error syncing: {str(sync_err)}"
                    skipped_employees.append((emp_code, reason))
                    safe_log(f"Skipped Employee {emp_code}", reason)
                    continue

            url = data.get("next")
            page += 1

        summary = (
            f"Employee Sync Completed.\n"
            f"Total Fetched: {total_fetched}\n"
            f"Inserted: {total_inserted}\n"
            f"Updated: {total_updated}\n"
            f"Skipped: {len(skipped_employees)}\n"
            f"Skipped Employees List: {skipped_employees}"
        )

        safe_log("BioTime Employee Sync Summary", summary)

        return {"status": "success", "message": summary, "skipped": skipped_employees}

    except Exception as e:
        safe_log("BioTime Employee Sync Failed", str(e))
        return {"status": "error", "message": str(e)}
