# Bline Integration

A Frappe/ERPNext app that connects your bench to [Bline](https://bline.app) (a
voice-agent platform layered on top of your existing phone system). It:

- Receives Bline's `call.*`, `agent.*`, and `dashboard.snapshot` webhooks and
  stores them as Frappe documents.
- Shows everything in one **Bline** Workspace (shortcuts, a calls-per-day
  chart, and live overview number cards).
- Lets you place an outbound call through Bline from a dedicated **Bline Call
  Request** doctype, or with one click from any ERPNext **Contact** or
  **Lead**.
- Lets you test the connection to Bline and backfill recent calls/agents on
  demand, using a Bline-issued API token.

## Prerequisites

- A Frappe bench (v14+ recommended) with **ERPNext** already installed on the
  target site (this app's "Call via Bline" button lives on ERPNext's `Lead`
  doctype; `Contact` ships with core Frappe).
- Outbound HTTPS access from your bench to your Bline console's origin.
- Inbound HTTPS access to your site from Bline's servers (for the webhook).
- A Bline account with the "Integration with Bizcentric" panel available in
  its console.

## Install

```bash
bench get-app bline_integration /path/to/bline_integration
bench --site <your-site> install-app bline_integration
bench --site <your-site> migrate
```

(`bench get-app` normally clones a git URL; pointed at a local path it copies
the app in directly, which also works.)

## Connect it to Bline

1. In Bline's own console, go to **Integrations -> Integration with
   Bizcentric** and click **Connect**. Bline shows you a **webhook secret**
   once at this point — copy it now, you can't see it again unless you later
   rotate the webhook.
2. Bline builds the webhook URL itself as
   `<your Frappe site URL>/api/method/bline_integration.api.webhook` — make
   sure that's the URL Bline is configured to call (it derives this
   automatically from the site URL you give it, if asked).
3. In the same Bline panel, click **Generate API token**. Copy the token
   (`bline_live_...`).
4. In your Frappe desk, open **Bline Settings** (search it, or use the Bline
   workspace shortcut):
   - Check **Enabled**.
   - Paste the Bline console's own origin into **Bline Base URL**
     (e.g. `https://mycompany.bline.app`, no trailing slash, no `/api/v1`).
   - Paste the API token into **API Token**.
   - Paste the webhook secret into **Webhook Secret**.
   - Save.
5. Click **Test Connection**. A green message confirms the token and base
   URL both work.
6. Click **Fetch Options**, then pick a **Default Connection** and **Default
   Agent** from the dropdowns it populates (these back the outbound-call
   buttons whenever a call doesn't specify its own connection/agent). Save
   again.
7. Click **Sync Now** to backfill recent calls and agents from Bline. After
   this, new activity arrives live via the webhook; dashboard snapshots
   arrive automatically roughly every 15 minutes.
8. From Bline's console, you can send a `webhook.test` ping to confirm
   delivery — it will be accepted (200) but not stored as a document.

## Using it

- **Bline** workspace: shortcuts to all five doctypes, a calls-per-day chart,
  and four live number cards (active calls, agents, transfer rate, p95
  latency) reflecting the most recent dashboard snapshot.
- **Bline Call Request**: create one, optionally link a Contact/Lead and
  override the connection/agent, then click **Call Now**. To call about a
  specific invoice: pick a **Customer** (auto-fills **To Number** from their
  primary contact), pick one of their **Sales Invoice**s, click **Load
  Invoice Details** to preview exactly what will be sent (company, invoice
  number, amounts, due date, line items) in **Context**, edit it if needed,
  then **Call Now**. The agent gets these as background facts — it still
  opens with its own greeting, but can answer "which invoice / how much / by
  when" correctly instead of saying it has no access.
- **Contact** / **Lead**: open any record and use the **Bline** button group
  in the top toolbar -> **Call via Bline**. It prompts for/confirms the
  number, places the call, and shows Bline's own response (call id and state,
  or its exact error message on failure).

## Assumptions and simplifications made while building this app

Bline's REST/webhook contract was given precisely; a handful of things on the
Frappe side were left to reasonable judgment because the spec allowed it or
didn't fully pin them down:

- **Module/doctype folder nesting.** Doctypes live at the standard
  `bench new-app`-generated path,
  `bline_integration/bline_integration/bline_integration/doctype/<name>/`
  (app repo / python package / module-named-same-as-app folder), because
  that's what Frappe's module loader actually requires when `modules.txt`
  lists a single module called "Bline Integration". This is one level deeper
  than the shorthand path sketched in the original spec.
- **`default_connection` / `default_agent` as Select fields.** Since Bline
  connections/agents are UUIDs with no natural short label, each option is
  stored as the string `"<id> | <name> (<kind or status>)"`. Server code
  parses the id back out by splitting on `" | "`. `Fetch Options` populates
  the two Select fields' `options` dynamically via `set_df_property`; nothing
  is auto-selected, so pick and save the defaults once after fetching.
- **Autonaming.** `Bline Agent` and `Bline Call` use
  `autoname: field:<bline_*_id>` so their Frappe document name is the Bline
  id itself — this makes webhook upserts a simple existence check.
  `Bline Dashboard Snapshot` uses hash autonaming (it's an append-only time
  series). `Bline Call Request` uses a `BLINE-CREQ-.#####` series.
- **`call.started`/`call.completed` field merging.** Fields not carried by a
  given event type are left untouched on an existing `Bline Call`; the raw
  event `data` is merged (not replaced) into `raw_payload` so the full
  history of what each event reported is visible for traceability, alongside
  the merged/flattened structured fields.
- **`call.transferred`.** Handled defensively per the spec: if `data.call_id`
  is present it's merged into the existing/new `Bline Call` record (updating
  `transfer_target` if given); if not, the raw payload is stored as a
  standalone `Bline Call` row with a synthetic id (`transfer-<hash>`) rather
  than being dropped.
- **Webhook delivery dedup.** Implemented via `frappe.cache()` with a
  24-hour expiry keyed on `X-Bline-Delivery`, per the spec's suggestion —
  a document-existence check was the other option offered, but the cache
  approach doesn't require guessing which doctype/field a given event type
  would dedupe against.
- **Number Cards showing "latest snapshot" values.** Frappe's built-in
  Number Card aggregate functions (Count/Sum/Average) can't express "the
  most recent row's field value" directly. The four overview number cards
  (`Bline Active Calls`, `Bline Agents`, `Bline Transfer Rate`,
  `Bline P95 Latency`) use Number Card's `type: "Custom"` with a `method`
  pointing at small whitelisted functions in
  `bline_integration/number_cards.py` that read the latest
  `Bline Dashboard Snapshot` row. If your Frappe version's Number Card
  doctype doesn't support the `Custom` type/`method` field the same way,
  these may need adjusting (fall back to a Query Report + a "Report" type
  number card, or a custom Insights/Dashboard chart).
- **Workspace JSON.** Hand-written to match the modern (v13+) Frappe
  Workspace fixture shape (`content` block layout plus `shortcuts` /
  `charts` / `number_cards` child tables). This wasn't validated against a
  running bench (none is available in this environment); if `bench migrate`
  reports a workspace schema mismatch on your Frappe version, the safest fix
  is opening the Bline workspace in the desk UI once and re-saving it there,
  which will normalize the JSON for you (`bench export-fixtures` afterwards
  to pull the corrected version back into this app if desired).
- **Contact vs Lead phone field.** `Contact` has no flat phone field — its
  number lives in the `phone_nos` child table, so the button prefers the row
  flagged `is_primary_mobile_no`, then `is_primary_phone`, then the first
  row. `Lead` has flat `mobile_no` and `phone` fields on stock ERPNext, so
  the button prefers `mobile_no` then `phone`. Either way the number is shown
  in an editable prompt before the call is placed, so a wrong guess here
  never blocks placing the call.
- **`/connections` pagination shape.** Treated defensively as `{"items":
  [...], "total": N}` if the response is a dict, else as a bare list, per the
  spec's own hedge.
- **Permissions.** Every doctype currently grants full access only to
  `System Manager`. Add/adjust roles (e.g. a "Bline User" role with just
  read + the call-placing rights) to fit your organization before rolling
  this out beyond admins.
- **`required_apps = ["erpnext"]`** in `hooks.py`, since the `Lead` doctype
  the Lead button hooks into belongs to ERPNext, not core Frappe.
