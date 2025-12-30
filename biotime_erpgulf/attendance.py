# # # import requests
# # # import frappe
# # # from datetime import datetime, timedelta
# # # from collections import defaultdict
# # # from frappe.utils import get_datetime, get_time
# # # import pytz


# # # def time_diff_in_minutes(time1, time2):
# # #     if isinstance(time1, datetime) and isinstance(time2, datetime):
# # #         diff = abs((time1 - time2).total_seconds())
# # #     else:
# # #         dt1 = datetime.combine(datetime.today(), time1)
# # #         dt2 = datetime.combine(datetime.today(), time2)
# # #         diff = abs((dt1 - dt2).total_seconds())
# # #     return diff / 60


# # # def get_shift_info(employee):
# # #     sa = frappe.get_all(
# # #         "Shift Assignment",
# # #         filters=[["employee", "=", employee], ["docstatus", "=", 1]],
# # #         fields=["shift_type", "shift_location"],
# # #         order_by="start_date desc",
# # #         limit=1
# # #     )
# # #     if sa:
# # #         return sa[0].shift_type, sa[0].shift_location

# # #     return frappe.db.get_value("Employee", employee, "default_shift"), None


# # # def get_log_type(employee, punch_time, punch_state_display):

# # #     shift_type, shift_location = get_shift_info(employee)
# # #     if not shift_type:
# # #         return "IN" if punch_state_display == "Check In" else "OUT"

# # #     shift_doc = frappe.get_doc("Shift Type", shift_type)
# # #     start_time = get_time(shift_doc.start_time)
# # #     end_time = get_time(shift_doc.end_time)
# # #     late_grace = int(shift_doc.late_entry_grace_period or 0)
# # #     early_grace = int(shift_doc.early_exit_grace_period or 0)

# # #     punch_time_only = punch_time.time()

# # #     if punch_state_display == "Check In":
# # #         diff = time_diff_in_minutes(punch_time_only, start_time)
# # #         if punch_time_only > start_time and diff > late_grace:
# # #             return "Late Entry"
# # #         return "IN"

# # #     if punch_state_display == "Check Out":
# # #         diff = time_diff_in_minutes(end_time, punch_time_only)
# # #         if punch_time_only < end_time and diff > early_grace:
# # #             return "Early Exit"
# # #         return "OUT"

# # #     return "IN"


# # # def update_employee_custom_in(employee, punch_state_display, punch_time):

# # #     current_status = frappe.db.get_value("Employee", employee, "custom_in") or 0
# # #     psd = punch_state_display.lower()

# # #     if psd in ("check in", "checkin"):
# # #         new_status = 1
# # #     elif psd in ("check out", "checkout"):
# # #         new_status = 0
# # #     else:
# # #         new_status = 0 if current_status else 1

# # #     frappe.db.set_value("Employee", employee, "custom_in", new_status)

# # #     return get_log_type(
# # #         employee,
# # #         punch_time,
# # #         "Check In" if new_status else "Check Out"
# # #     )


# # # def checkin_exists(employee, punch_dt):
# # #     return frappe.db.exists(
# # #         "Employee Checkin",
# # #         {
# # #             "employee": employee,
# # #             "time": punch_dt,
# # #             "device_id": "BioTime"
# # #         }
# # #     )



# # # @frappe.whitelist()
# # # def biotime_attendance():
# # #     frappe.enqueue(
# # #         "biotime_erpgulf.attendance.run_biotime_attendance",
# # #         queue="long",
# # #         job_name="BioTime Sync Job"
# # #     )
# # #     return {"message": "BioTime sync"}



# # # def run_biotime_attendance():

# # #     import logging
# # #     logger = frappe.logger("biotime")

# # #     settings = frappe.get_single("BioTime Settings")

# # #     if not settings.start_year:
# # #         frappe.throw("Start Year is mandatory in BioTime Settings")

# # #     start_datetime = datetime(int(settings.start_year), 1, 1)

# # #     base_url = settings.biotime_url.rstrip("/") + "/iclock/api/transactions/"
# # #     headers = {
# # #         "Authorization": f"Token {settings.biotime_token}",
# # #         "Content-Type": "application/json"
# # #     }

# # #     params = {
# # #         "start_time": start_datetime.strftime("%Y-%m-%d %H:%M:%S")
# # #     }

# # #     inserted = 0
# # #     skipped = 0

# # #     url = base_url
# # #     page = 1


# # #     while url:
# # #         try:
# # #             response = requests.get(
# # #                 url,
# # #                 headers=headers,
# # #                 params=params if page == 1 else None,
# # #                 timeout=120
# # #             )
# # #             response.raise_for_status()
# # #             data = response.json()
# # #         except Exception:
# # #             logger.exception(f"BioTime fetch failed at page {page}")
# # #             break

# # #         rows = data.get("data") or []
# # #         if not rows:
# # #             break

# # #         oldest_punch_dt = get_datetime(rows[-1].get("punch_time"))
# # #         if oldest_punch_dt < start_datetime:
# # #             logger.info(
# # #                 f"Stopping pagination at page {page}, "
# # #                 f"oldest punch {oldest_punch_dt}"
# # #             )
# # #             break

# # #         for row in rows:
# # #             emp_code = row.get("emp_code")
# # #             punch_time = row.get("punch_time")
# # #             punch_state = row.get("punch_state_display")

# # #             if not (emp_code and punch_time and punch_state):
# # #                 skipped += 1
# # #                 continue

# # #             punch_dt = get_datetime(punch_time)

# # #             if punch_dt < start_datetime:
# # #                 skipped += 1
# # #                 continue

# # #             employee = frappe.db.get_value(
# # #                 "Employee",
# # #                 {"biotime_emp_code": emp_code},
# # #                 "name"
# # #             )
# # #             if not employee:
# # #                 skipped += 1
# # #                 continue

# # #             if checkin_exists(employee, punch_dt):
# # #                 skipped += 1
# # #                 continue

# # #             log_type = update_employee_custom_in(
# # #                 employee,
# # #                 punch_state,
# # #                 punch_dt
# # #             )

# # #             try:
# # #                 frappe.get_doc({
# # #                     "doctype": "Employee Checkin",
# # #                     "employee": employee,
# # #                     "time": punch_dt,
# # #                     "log_type": log_type,
# # #                     "device_id": "BioTime"
# # #                 }).insert(ignore_permissions=True)

# # #                 inserted += 1

# # #             except Exception:
# # #                 logger.exception(f"BioTime insert failed for {employee}")
# # #                 skipped += 1

# # #         url = data.get("next")
# # #         page += 1

# # #         if page > 2000:
# # #             logger.warning("Pagination stopped due to page limit")
# # #             break

# # #     frappe.db.commit()

# # #     logger.info(
# # #         f"BioTime Sync completed. Inserted={inserted}, Skipped={skipped}"
# # #     )

# # #     return f"BioTime Sync completed. Inserted: {inserted}, Skipped: {skipped}"




# import requests
# import frappe
# from datetime import datetime, timedelta
# from frappe.utils import get_datetime, get_time


# # ------------------------------------------------------------
# # Helpers
# # ------------------------------------------------------------

# def time_diff_in_minutes(time1, time2):
#     dt1 = datetime.combine(datetime.today(), time1)
#     dt2 = datetime.combine(datetime.today(), time2)
#     return abs((dt1 - dt2).total_seconds()) / 60


# def get_shift_info(employee):
#     sa = frappe.get_all(
#         "Shift Assignment",
#         filters={"employee": employee, "docstatus": 1},
#         fields=["shift_type"],
#         order_by="start_date desc",
#         limit=1,
#     )
#     if sa:
#         return sa[0].shift_type
#     return frappe.db.get_value("Employee", employee, "default_shift")


# def get_log_type(employee, punch_dt, punch_state_display):
#     shift_type = get_shift_info(employee)

#     if not shift_type:
#         return "IN" if punch_state_display == "Check In" else "OUT"

#     shift = frappe.get_doc("Shift Type", shift_type)

#     start = get_time(shift.start_time)
#     end = get_time(shift.end_time)
#     late_grace = int(shift.late_entry_grace_period or 0)
#     early_grace = int(shift.early_exit_grace_period or 0)

#     punch_time = punch_dt.time()

#     if punch_state_display == "Check In":
#         if punch_time > start and time_diff_in_minutes(punch_time, start) > late_grace:
#             return "Late Entry"
#         return "IN"

#     if punch_state_display == "Check Out":
#         if punch_time < end and time_diff_in_minutes(end, punch_time) > early_grace:
#             return "Early Exit"
#         return "OUT"

#     return "IN"


# def update_employee_custom_in(employee, punch_state):
#     new_status = 1 if punch_state.lower().startswith("check in") else 0
#     frappe.db.set_value("Employee", employee, "custom_in", new_status)


# def checkin_exists(employee, punch_dt):
#     return frappe.db.exists(
#         "Employee Checkin",
#         {"employee": employee, "time": punch_dt, "device_id": "BioTime"},
#     )


# # ------------------------------------------------------------
# # API trigger
# # ------------------------------------------------------------

# @frappe.whitelist()
# def biotime_attendance():
#     frappe.enqueue(
#         "biotime_erpgulf.attendance.run_biotime_attendance",
#         queue="long",
#         job_name="BioTime Datetime Sync",
#     )
#     return {"message": "BioTime datetime sync started"}


# # ------------------------------------------------------------
# # MAIN SYNC (DATETIME BASED)
# # ------------------------------------------------------------

# def run_biotime_attendance():
#     logger = frappe.logger("biotime")

#     settings = frappe.get_single("BioTime Settings")

#     if not settings.start_year:
#         frappe.throw("Start Year is mandatory")

#     # last synced time (resume point)
#     last_sync = settings.last_synced_datetime
#     if last_sync:
#         start_dt = get_datetime(last_sync)
#     else:
#         start_dt = datetime(int(settings.start_year), 1, 1)

#     # sync in small safe windows
#     end_dt = start_dt + timedelta(hours=6)

#     base_url = settings.biotime_url.rstrip("/") + "/iclock/api/transactions/"
#     headers = {"Authorization": f"Token {settings.biotime_token}"}

#     inserted = skipped = 0

#     logger.info(f"BioTime sync window: {start_dt} → {end_dt}")

#     try:
#         response = requests.get(
#             base_url,
#             headers=headers,
#             params={
#                 "start_time": start_dt.strftime("%Y-%m-%d %H:%M:%S"),
#                 "end_time": end_dt.strftime("%Y-%m-%d %H:%M:%S"),
#             },
#             timeout=60,
#         )
#         response.raise_for_status()
#         rows = response.json().get("data") or []

#     except Exception:
#         logger.exception("BioTime API failed")
#         return

#     for row in rows:
#         emp_code = row.get("emp_code")
#         punch_time = row.get("punch_time")
#         punch_state = row.get("punch_state_display")

#         if not (emp_code and punch_time and punch_state):
#             skipped += 1
#             continue

#         punch_dt = get_datetime(punch_time)

#         employee = frappe.db.get_value(
#             "Employee", {"biotime_emp_code": emp_code}, "name"
#         )
#         if not employee or checkin_exists(employee, punch_dt):
#             skipped += 1
#             continue

#         log_type = get_log_type(employee, punch_dt, punch_state)

#         try:
#             frappe.get_doc(
#                 {
#                     "doctype": "Employee Checkin",
#                     "employee": employee,
#                     "time": punch_dt,
#                     "log_type": log_type,
#                     "device_id": "BioTime",
#                 }
#             ).insert(ignore_permissions=True)

#             update_employee_custom_in(employee, punch_state)
#             inserted += 1

#         except Exception:
#             logger.exception(f"Insert failed for {employee}")
#             skipped += 1

#     frappe.db.set_value(
#         "BioTime Settings", None, "last_synced_datetime", end_dt
#     )
#     frappe.db.commit()

#     logger.info(
#         f"BioTime Sync done. Inserted={inserted}, Skipped={skipped}"
#     )

#     return f"Inserted={inserted}, Skipped={skipped}"


import requests
import frappe
from datetime import datetime, timedelta
from frappe.utils import get_datetime, get_time


# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------

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
        {"employee": employee, "time": punch_dt, "device_id": "BioTime"},
    )


# ------------------------------------------------------------
# API trigger
# ------------------------------------------------------------

@frappe.whitelist()
def biotime_attendance():
    frappe.enqueue(
        "biotime_erpgulf.attendance.run_biotime_attendance",
        queue="long",
        job_name="BioTime Datetime Sync",
    )
    return {"message": "BioTime datetime sync started"}


# ------------------------------------------------------------
# MAIN SYNC (DATETIME BASED – FIXED)
# ------------------------------------------------------------

def run_biotime_attendance():
    logger = frappe.logger("biotime")

    settings = frappe.get_single("BioTime Settings")

    if not settings.start_year:
        frappe.throw("Start Year is mandatory")

    # Resume point
    last_sync = settings.last_synced_datetime
    if last_sync:
        start_dt = get_datetime(last_sync)
    else:
        start_dt = datetime(int(settings.start_year), 1, 1)

    # Small safe window
    end_dt = start_dt + timedelta(hours=6)

    base_url = settings.biotime_url.rstrip("/") + "/iclock/api/transactions/"
    headers = {"Authorization": f"Token {settings.biotime_token}"}

    inserted = skipped = 0
    max_punch_dt_in_run = None  # ✅ CRITICAL FIX

    logger.info(f"BioTime sync window: {start_dt} → {end_dt}")

    try:
        response = requests.get(
            base_url,
            headers=headers,
            params={
                "start_time": start_dt.strftime("%Y-%m-%d %H:%M:%S"),
                "end_time": end_dt.strftime("%Y-%m-%d %H:%M:%S"),
            },
            timeout=60,
        )
        response.raise_for_status()
        rows = response.json().get("data") or []

    except Exception:
        logger.exception("BioTime API failed")
        return

    # Defensive ordering
    rows.sort(key=lambda r: r.get("punch_time") or "")

    for row in rows:
        emp_code = row.get("emp_code")
        punch_time = row.get("punch_time")
        punch_state = row.get("punch_state_display")

        if not (emp_code and punch_time and punch_state):
            skipped += 1
            continue

        punch_dt = get_datetime(punch_time)

        # Track max datetime ONLY
        if not max_punch_dt_in_run or punch_dt > max_punch_dt_in_run:
            max_punch_dt_in_run = punch_dt

        employee = frappe.db.get_value(
            "Employee", {"biotime_emp_code": emp_code}, "name"
        )
        if not employee or checkin_exists(employee, punch_dt):
            skipped += 1
            continue

        log_type = get_log_type(employee, punch_dt, punch_state)

        try:
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
            logger.exception(f"Insert failed for {employee}")
            skipped += 1

    # ✅ UPDATE CURSOR ONLY ONCE, TO REAL MAX DATETIME
    if max_punch_dt_in_run:
        frappe.db.set_value(
            "BioTime Settings",
            "BioTime Settings",
            "last_synced_datetime",
            max_punch_dt_in_run,
        )
        frappe.db.commit()

    logger.info(
        f"BioTime Sync done. Inserted={inserted}, Skipped={skipped}, "
        f"LastSync={max_punch_dt_in_run}"
    )

    return f"Inserted={inserted}, Skipped={skipped}"
