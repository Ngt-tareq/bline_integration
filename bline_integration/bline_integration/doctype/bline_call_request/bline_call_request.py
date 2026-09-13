import frappe
from frappe.model.document import Document

from bline_integration import bline_client


class BlineCallRequest(Document):
	def before_insert(self):
		if not self.placed_by:
			self.placed_by = frappe.session.user

	@frappe.whitelist()
	def place(self):
		settings = frappe.get_single("Bline Settings")
		try:
			result = settings.place_call(
				to_number=self.to_number,
				contact=self.contact,
				lead=self.lead,
				connection=self.connection,
				agent=self.agent,
			)
		except (bline_client.BlineAPIError, frappe.ValidationError) as exc:
			self.status = "Failed"
			self.error = str(exc)
			self.save(ignore_permissions=True)
			return {"status": "Failed", "error": self.error}

		self.status = "Placed"
		self.bline_call_id = result.get("call_id")
		self.error = None
		self.placed_at = frappe.utils.now_datetime()
		self.save(ignore_permissions=True)
		return {"status": "Placed", "call_id": result.get("call_id"), "state": result.get("state")}
