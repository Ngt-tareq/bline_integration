import json

import frappe
from frappe import _
from frappe.model.document import Document

from bline_integration import bline_client


class BlineSettings(Document):
	@frappe.whitelist()
	def test_connection(self):
		try:
			data = bline_client.get(self, "/dashboard/summary")
		except bline_client.BlineAPIError as exc:
			return {"success": False, "message": str(exc)}
		return {
			"success": True,
			"message": _("Connected to Bline. {0} agent(s), {1} call(s) today.").format(
				data.get("agents", 0), data.get("calls_today", 0)
			),
		}

	@frappe.whitelist()
	def fetch_options(self):
		try:
			connections_resp = bline_client.get(self, "/connections", params={"limit": 200})
			agents_resp = bline_client.get(self, "/agents", params={"limit": 200, "offset": 0})
		except bline_client.BlineAPIError as exc:
			frappe.throw(str(exc))

		connections = connections_resp.get("items") if isinstance(connections_resp, dict) else connections_resp
		agents = agents_resp.get("items") if isinstance(agents_resp, dict) else agents_resp

		connection_options = [
			f"{c['id']} | {c.get('name') or c['id']} ({c.get('kind', '')})"
			for c in (connections or [])
			if c.get("id")
		]
		agent_options = [
			f"{a['id']} | {a.get('name') or a['id']} ({a.get('status', '')})"
			for a in (agents or [])
			if a.get("id")
		]
		return {"connections": connection_options, "agents": agent_options}

	@frappe.whitelist()
	def sync_now(self):
		try:
			agents_synced = self._sync_agents()
			calls_synced = self._sync_calls()
		except bline_client.BlineAPIError as exc:
			frappe.throw(str(exc))
		return {"agents_synced": agents_synced, "calls_synced": calls_synced}

	def _sync_agents(self):
		resp = bline_client.get(self, "/agents", params={"limit": 200, "offset": 0})
		items = resp.get("items", []) if isinstance(resp, dict) else (resp or [])
		for item in items:
			_upsert_agent(item)
		return len(items)

	def _sync_calls(self):
		resp = bline_client.get(self, "/calls", params={"limit": 200, "offset": 0})
		items = resp.get("items", []) if isinstance(resp, dict) else (resp or [])
		for item in items:
			_upsert_call_from_rest(item)
		return len(items)

	@frappe.whitelist()
	def place_call(self, to_number, contact=None, lead=None, connection=None, agent=None, from_number=None):
		connection_id = _parse_option(connection) or _parse_option(self.default_connection)
		agent_id = _parse_option(agent) or _parse_option(self.default_agent)
		if not connection_id:
			frappe.throw(
				_(
					"No Bline connection is configured. Set Default Connection in Bline Settings, "
					"or pass one explicitly."
				)
			)

		body = {"connection_id": connection_id, "to_number": to_number}
		if agent_id:
			body["agent_id"] = agent_id
		resolved_from = from_number or self.default_from_number
		if resolved_from:
			body["from_number"] = resolved_from

		result = bline_client.post(self, "/calls/outbound", json_body=body)

		call_id = result.get("call_id")
		if call_id:
			doc = (
				frappe.get_doc("Bline Call", call_id)
				if frappe.db.exists("Bline Call", call_id)
				else frappe.new_doc("Bline Call")
			)
			doc.bline_call_id = call_id
			doc.direction = "outbound"
			doc.status = result.get("state")
			if contact:
				doc.contact = contact
			if lead:
				doc.lead = lead
			doc.raw_payload = json.dumps(result, indent=2)
			doc.save(ignore_permissions=True)

		return result


def _parse_option(value):
	if not value:
		return None
	return value.split(" | ", 1)[0].strip()


def _upsert_agent(item):
	agent_id = item.get("id")
	if not agent_id:
		return
	doc = (
		frappe.get_doc("Bline Agent", agent_id)
		if frappe.db.exists("Bline Agent", agent_id)
		else frappe.new_doc("Bline Agent")
	)
	doc.bline_agent_id = agent_id
	doc.agent_name = item.get("name")
	doc.status = item.get("status")
	doc.language = item.get("language_mode")
	doc.updated_at = item.get("updated_at")
	doc.save(ignore_permissions=True)


def _upsert_call_from_rest(item):
	call_id = item.get("id")
	if not call_id:
		return
	doc = (
		frappe.get_doc("Bline Call", call_id)
		if frappe.db.exists("Bline Call", call_id)
		else frappe.new_doc("Bline Call")
	)
	doc.bline_call_id = call_id
	if item.get("agent_id") and frappe.db.exists("Bline Agent", item["agent_id"]):
		doc.agent = item["agent_id"]
	doc.direction = item.get("direction")
	doc.status = item.get("status")
	doc.started_at = item.get("started_at")
	doc.duration_seconds = item.get("duration_seconds")
	doc.transfer_target = item.get("transfer_target")
	doc.end_reason = item.get("end_reason")
	if item.get("language_summary") is not None:
		doc.language_summary = json.dumps(item.get("language_summary"), indent=2)
	doc.raw_payload = json.dumps(item, indent=2)
	doc.save(ignore_permissions=True)
