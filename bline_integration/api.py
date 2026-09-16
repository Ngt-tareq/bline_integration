import hashlib
import hmac
import json
import time

import frappe
from frappe import _

from bline_integration import bline_client


def verify_signature(secret: str, body: bytes, header: str, tolerance_seconds: int = 300) -> bool:
    if not header:
        return False
    try:
        parts = dict(p.split("=", 1) for p in header.split(",") if "=" in p)
    except ValueError:
        return False
    try:
        stamp = int(parts.get("t", ""))
    except ValueError:
        return False
    if abs(int(time.time()) - stamp) > tolerance_seconds:
        return False
    expected = hmac.new(secret.encode(), f"{stamp}.".encode() + body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(parts.get("v1", ""), expected)


@frappe.whitelist(allow_guest=True)
def webhook():
    # Signature is HMAC'd over the exact raw bytes Bline sent, so this must
    # read frappe.request.get_data() rather than frappe.request.json /
    # frappe.form_dict, which would re-serialize the body and break the HMAC.
    raw_body = frappe.request.get_data()
    signature_header = frappe.get_request_header("X-Bline-Signature")
    delivery_id = frappe.get_request_header("X-Bline-Delivery")

    settings = frappe.get_single("Bline Settings")
    secret = settings.get_password("webhook_secret", raise_exception=False)

    if not secret or not verify_signature(secret, raw_body, signature_header or ""):
        frappe.local.response.http_status_code = 401
        frappe.throw(_("Invalid webhook signature"), frappe.PermissionError)

    payload = json.loads(raw_body.decode("utf-8"))
    event_type = payload.get("type")
    data = payload.get("data") or {}

    # Dedupe on delivery id: retries reuse the same X-Bline-Delivery, so a
    # short-lived cache key is enough to avoid double-processing a retry.
    if delivery_id:
        cache_key = f"bline_webhook_delivery::{delivery_id}"
        if frappe.cache().get_value(cache_key):
            return {"ok": True, "duplicate": True}
        frappe.cache().set_value(cache_key, 1, expires_in_sec=86400)

    if event_type in ("call.started", "call.completed"):
        _upsert_call_from_event(event_type, data, payload.get("created_at"))
        _touch_last_event()
    elif event_type == "call.transferred":
        _handle_call_transferred(data)
        _touch_last_event()
    elif event_type in ("agent.created", "agent.updated"):
        _upsert_agent_from_event(data)
        _touch_last_event()
    elif event_type == "dashboard.snapshot":
        # A time series: always insert a new row rather than upserting, so
        # history of the ~15-minute snapshots is preserved for the chart.
        _insert_snapshot(data)
        _touch_last_event()
    else:
        # Covers webhook.test and any future event type: just acknowledge.
        pass

    frappe.local.response.http_status_code = 200
    return {"ok": True}


def _touch_last_event():
    frappe.db.set_single_value("Bline Settings", "last_event_at", frappe.utils.now_datetime())


def _get_or_new_call(call_id):
    if frappe.db.exists("Bline Call", call_id):
        return frappe.get_doc("Bline Call", call_id)
    doc = frappe.new_doc("Bline Call")
    doc.bline_call_id = call_id
    return doc


def _merge_raw_payload(doc, data):
    merged = {}
    if doc.raw_payload:
        try:
            merged = json.loads(doc.raw_payload)
        except ValueError:
            merged = {}
    merged.update(data)
    doc.raw_payload = json.dumps(merged, indent=2)


def _upsert_call_from_event(event_type, data, created_at):
    call_id = data.get("call_id")
    if not call_id:
        return
    doc = _get_or_new_call(call_id)

    if event_type == "call.started":
        doc.status = "started"
        if data.get("direction"):
            doc.direction = data["direction"]
        if not doc.started_at:
            doc.started_at = bline_client.parse_datetime(created_at) or frappe.utils.now_datetime()
    elif event_type == "call.completed":
        doc.status = "completed"
        if "end_reason" in data:
            doc.end_reason = data.get("end_reason")
        if "duration_seconds" in data:
            doc.duration_seconds = data.get("duration_seconds")
        if "transfer_target" in data:
            doc.transfer_target = data.get("transfer_target")

    _merge_raw_payload(doc, data)
    doc.save(ignore_permissions=True)


def _handle_call_transferred(data):
    call_id = data.get("call_id") if isinstance(data, dict) else None
    if call_id:
        doc = _get_or_new_call(call_id)
        if isinstance(data.get("transfer_target"), str):
            doc.transfer_target = data["transfer_target"]
        _merge_raw_payload(doc, data)
        doc.save(ignore_permissions=True)
    else:
        frappe.get_doc(
            {
                "doctype": "Bline Call",
                "bline_call_id": f"transfer-{frappe.generate_hash(length=10)}",
                "status": "transferred",
                "raw_payload": json.dumps(data, indent=2),
            }
        ).insert(ignore_permissions=True)


def _upsert_agent_from_event(data):
    agent_id = data.get("agent_id")
    if not agent_id:
        return
    if frappe.db.exists("Bline Agent", agent_id):
        doc = frappe.get_doc("Bline Agent", agent_id)
    else:
        doc = frappe.new_doc("Bline Agent")
        doc.bline_agent_id = agent_id
    if data.get("name"):
        doc.agent_name = data["name"]
    if data.get("status"):
        doc.status = data["status"]
    if data.get("language_mode"):
        doc.language = data["language_mode"]
    doc.updated_at = frappe.utils.now_datetime()
    doc.save(ignore_permissions=True)


def _insert_snapshot(data):
    frappe.get_doc(
        {
            "doctype": "Bline Dashboard Snapshot",
            "captured_at": frappe.utils.now_datetime(),
            "calls_today": data.get("calls_today"),
            "calls_total": data.get("calls_total"),
            "active_calls": data.get("active_calls"),
            "average_duration_seconds": data.get("average_duration_seconds"),
            "transfer_rate": data.get("transfer_rate"),
            "p95_turn_latency_ms": data.get("p95_turn_latency_ms"),
            "agents": data.get("agents"),
            "campaigns_running": data.get("campaigns_running"),
            "dnc_entries": data.get("dnc_entries"),
            "raw_payload": json.dumps(data, indent=2),
        }
    ).insert(ignore_permissions=True)


@frappe.whitelist()
def call_from_doctype(doctype, name, to_number):
    if doctype not in ("Contact", "Lead"):
        frappe.throw(_("Calling via Bline is only available from Contact or Lead."))

    request_doc = frappe.new_doc("Bline Call Request")
    request_doc.to_number = to_number
    if doctype == "Contact":
        request_doc.contact = name
    else:
        request_doc.lead = name
    request_doc.insert(ignore_permissions=True)
    result = request_doc.place()
    result["name"] = request_doc.name
    return result
