frappe.ui.form.on("Bline Settings", {
	refresh(frm) {
		frm.add_custom_button(
			__("Test Connection"),
			() => {
				frm.call("test_connection").then((r) => {
					if (!r.message) return;
					frappe.msgprint({
						title: __("Bline Connection"),
						indicator: r.message.success ? "green" : "red",
						message: r.message.message,
					});
				});
			},
			__("Bline")
		);

		frm.add_custom_button(
			__("Fetch Options"),
			() => {
				frm.call("fetch_options").then((r) => {
					if (!r.message) return;
					const connections = r.message.connections || [];
					const agents = r.message.agents || [];
					frm.set_df_property("default_connection", "options", [""].concat(connections).join("\n"));
					frm.set_df_property("default_agent", "options", [""].concat(agents).join("\n"));
					frm.refresh_field("default_connection");
					frm.refresh_field("default_agent");
					frappe.msgprint(
						__("Fetched {0} connection(s) and {1} agent(s) from Bline. Pick the defaults and save.", [
							connections.length,
							agents.length,
						])
					);
				});
			},
			__("Bline")
		);

		frm.add_custom_button(
			__("Sync Now"),
			() => {
				frappe.dom.freeze(__("Syncing with Bline..."));
				frm
					.call("sync_now")
					.then((r) => {
						frappe.dom.unfreeze();
						if (!r.message) return;
						frappe.msgprint(
							__("Synced {0} agent(s) and {1} call(s) from Bline.", [
								r.message.agents_synced,
								r.message.calls_synced,
							])
						);
					})
					.catch(() => frappe.dom.unfreeze());
			},
			__("Bline")
		);
	},
});
