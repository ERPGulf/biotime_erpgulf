import requests
import frappe
from dateutil.parser import parse

def sync_biotime_attendance():
    frappe.log_error("BioTime Sync function called", "BioTime Debug")

    try:
        settings = frappe.get_single("BioTime Settings")
        url = settings.biotime_url.rstrip("/") + "/iclock/api/transactions/"
        token = settings.biotime_token

        headers = {
            "Authorization": f"Token {token}",
            "Content-Type": "application/json"
        }
        frappe.log_error(f"Fetching BioTime data from URL: {url}", "BioTime Debug")

        resp = requests.get(url, headers=headers, timeout=10)
        frappe.log_error(
            f"BioTime Status: {resp.status_code} | Content-Type: {resp.headers.get('Content-Type')}",
            "BioTime Debug"
        )
        frappe.log_error(f"BioTime Payload (first 1k chars):\n{resp.text[:1000]}", "BioTime Debug")

        if resp.status_code != 200:
            frappe.log_error(f"Unexpected HTTP {resp.status_code}", "BioTime Sync")
            return

        try:
            payload = resp.json()
        except Exception as e:
            frappe.log_error(f" JSON parse error: {e}", "BioTime Sync")
            return

        logs = payload.get("data", [])
        frappe.log_error(f"Logs fetched: {len(logs)}", "BioTime Debug")
        if not logs:
            frappe.log_error(" No logs found in payload", "BioTime Sync")
            return

        for log in logs:
            emp_code       = log.get("emp_code")
            punch_time_str = log.get("punch_time")
            punch_state    = log.get("punch_state")
            terminal_sn    = log.get("terminal_sn") or "BioTime"

            frappe.log_error(f"Processing log: emp_code={emp_code}, punch_time={punch_time_str}, state={punch_state}", "BioTime Debug")

            log_type = "IN" if punch_state == "0" else "OUT"

            try:
                dt = parse(punch_time_str)
                punch_time = dt.replace(tzinfo=None, microsecond=0)
            except Exception as e:
                frappe.log_error(f"Time parse error for '{punch_time_str}': {e}", "BioTime Sync")
                continue

            frappe.log_error(f"Looking up Employee for emp_code={emp_code}", "BioTime Debug")
            employee = frappe.db.get_value("Employee", {"employee": emp_code}, "name")
            frappe.log_error(f"Employee found: {employee}", "BioTime Debug")

            if not employee:
                frappe.log_error(f"No Employee found for emp_code={emp_code}", "BioTime Sync")
                continue

            exists = frappe.db.exists("Employee Checkin", {"employee": employee, "time": punch_time})
            frappe.log_error(f"Duplicate check for {employee}@{punch_time}: exists={exists}", "BioTime Debug")
            if exists:
                frappe.log_error(f" Duplicate skipped for {employee}@{punch_time}", "BioTime Sync")
                continue

            try:
                checkin = frappe.get_doc({
                    "doctype": "Employee Checkin",
                    "employee": employee,
                    "time": punch_time,
                    "log_type": log_type,
                    "device_id": terminal_sn
                })
                checkin.insert(ignore_permissions=True)
                frappe.db.commit()
                frappe.log_error(f"Inserted {log_type} for {employee} @ {punch_time}", "BioTime Sync")
            except Exception as e:
                frappe.log_error(f" Insert failed for {emp_code}@{punch_time}: {e}", "BioTime Sync")

    except Exception as e:
        frappe.log_error(f"Fatal error in sync_biotime_attendance: {str(e)}", "BioTime Sync")

