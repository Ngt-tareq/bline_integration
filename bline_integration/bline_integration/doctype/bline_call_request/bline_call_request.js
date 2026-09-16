frappe.ui.form.on("Bline Call Request", {
	refresh(frm) {
		frm.set_query("sales_invoice", () => ({
			filters: frm.doc.customer ? { customer: frm.doc.customer } : {},
		}));

		if (frm.is_new() || frm.doc.status === "Placed") return;

		frm
			.add_custom_button(__("Call Now"), () => {
				frm.call("place").then((r) => {
					frm.reload_doc();
					if (!r.message) return;
					if (r.message.status === "Placed") {
						frappe.msgprint({
							title: __("Call Placed"),
							indicator: "green",
							message: __("Bline call {0} placed, state: {1}", [
								r.message.call_id || "",
								r.message.state || "",
							]),
						});
					} else {
						frappe.msgprint({
							title: __("Call Failed"),
							indicator: "red",
							message: r.message.error || __("Unknown error"),
						});
					}
				});
			})
			.addClass("btn-primary");
	},

	customer(frm) {
		frm.set_value("sales_invoice", "");
		if (!frm.doc.customer) return;
		frappe.call({
			method: "bline_integration.api.get_customer_phone",
			args: { customer: frm.doc.customer },
			callback(r) {
				if (r.message) frm.set_value("to_number", r.message);
			},
		});
	},

	load_invoice_details(frm) {
		if (!frm.doc.sales_invoice) {
			frappe.msgprint(__("Pick a Sales Invoice first."));
			return;
		}
		frappe.call({
			method: "bline_integration.api.build_invoice_context",
			args: { sales_invoice: frm.doc.sales_invoice },
			freeze: true,
			callback(r) {
				if (!r.message) return;
				frm.set_value("context", JSON.stringify(r.message, null, 2));
			},
		});
	},
});
