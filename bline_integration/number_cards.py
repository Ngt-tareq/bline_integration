"""Custom-type Number Card backends for the Bline workspace.

Standard Frappe Number Cards aggregate (count/sum/average) over a doctype;
they cannot express "the latest row's field value" directly. Since the
workspace needs the most recent Bline Dashboard Snapshot's figures, these
Number Cards use type "Custom" with a `method` pointing at the functions
below, each returning a single number.
"""

import frappe


def _latest_snapshot():
    name = frappe.db.get_value(
        "Bline Dashboard Snapshot", {}, "name", order_by="captured_at desc"
    )
    return frappe.get_doc("Bline Dashboard Snapshot", name) if name else None


@frappe.whitelist()
def active_calls():
    doc = _latest_snapshot()
    return doc.active_calls if doc else 0


@frappe.whitelist()
def agents_count():
    doc = _latest_snapshot()
    return doc.agents if doc else 0


@frappe.whitelist()
def transfer_rate():
    doc = _latest_snapshot()
    return doc.transfer_rate if doc else 0


@frappe.whitelist()
def p95_latency():
    doc = _latest_snapshot()
    return doc.p95_turn_latency_ms if doc else 0
