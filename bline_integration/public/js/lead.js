frappe.ui.form.on("Lead", {
	refresh(frm) {
		if (frm.is_new()) return;

		const default_number = frm.doc.mobile_no || frm.doc.phone || "";

		frm.add_custom_button(
			__("Call via Bline"),
			() => {
				frappe.prompt(
					[
						{
							fieldname: "to_number",
							fieldtype: "Data",
							label: __("Phone Number"),
							reqd: 1,
							default: default_number,
						},
					],
					(values) => {
						frappe.call({
							method: "bline_integration.api.call_from_doctype",
							args: {
								doctype: frm.doctype,
								name: frm.docname,
								to_number: values.to_number,
							},
							freeze: true,
							freeze_message: __("Placing call via Bline..."),
							callback(r) {
								if (!r.message) return;
								const res = r.message;
								if (res.status === "Placed") {
									frappe.msgprint({
										title: __("Call Placed"),
										indicator: "green",
										message: __("Bline call {0} placed.", [res.call_id || res.bline_call_id || ""]),
									});
								} else {
									frappe.msgprint({
										title: __("Call Failed"),
										indicator: "red",
										message: res.error || __("Unknown error placing call via Bline."),
									});
								}
							},
						});
					},
					__("Call via Bline"),
					__("Call")
				);
			},
			__("Bline")
		);
	},
});
