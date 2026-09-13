from bline_integration import __version__ as app_version

app_name = "bline_integration"
app_title = "Bline Integration"
app_publisher = "Bizcentric"
app_description = "Two-way integration between Bline (voice-agent platform) and ERPNext/Frappe: receives Bline's call/agent/dashboard webhooks, and lets Frappe place outbound calls through Bline."
app_email = "t.jouma@bizcentric.me"
app_license = "MIT"

required_apps = ["erpnext"]

doctype_js = {
    "Contact": "public/js/contact.js",
    "Lead": "public/js/lead.js",
}

after_install = "bline_integration.install.after_install"
