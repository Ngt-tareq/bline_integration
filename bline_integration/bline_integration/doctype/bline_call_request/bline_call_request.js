frappe.ui.form.on("Bline Call Request", {
	refresh(frm) {
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
});
