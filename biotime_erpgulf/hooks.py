app_name = "biotime_erpgulf"
app_title = "biotime_erpgulf"
app_publisher = "ERPGUlf"
app_description = "Biotime Integration with ERPNext HR Module"
app_email = "support@erpgulf.com"
app_license = "mit"

# Apps
# ------------------

required_apps = ["hrms"]


doctype_list_js = {
    "Employee Checkin": "public/js/employee_checkin.js",
    "Employee": "public/js/employee.js"}



scheduler_events = {
    "hourly": [
        "biotime_erpgulf.ubio_attendance.ubio_attendance",
        "biotime_erpgulf.attendance.biotime_attendance",
        
       
    ],
    "daily": [
        "biotime_erpgulf.ubio_attendance_processor.process_daily_attendance",
    ],

}



fixtures = [
    {"dt": "Custom Field", "filters": {"module": "biotime_erpgulf"}},
    {"dt": "Property Setter", "filters": {"module": "biotime_erpgulf"}}
]

