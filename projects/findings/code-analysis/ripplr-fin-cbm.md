# Ripplr-fin — Cheque Bounce Management, Scan/OCR, Outstanding/PDC Suspense, Schedulers

Repo: `/Users/vikas1141sharma/Developer/ripplr copy/Ripplr-fin/ripplr-fin` (v2 current, v1 legacy).
Subject: Vikas Sharma. Read-only pass; no repo files modified; no databases, CloudWatch, or apps touched.
Per explicit direction partway through this pass: git history (`git log`/`git blame`) was used early on to orient
the read, but per later instruction it was stopped, and ownership is not re-litigated below — every file in the
given paths is treated as the subject's own work. The one exception kept is Section 12, which flags two spots
where the *numbers or mechanism* the interview story describes don't line up with what the current code does —
that is a claim-accuracy note, not an authorship one, and it exists purely so a follow-up question doesn't land
unexpectedly.

---

## 1. Ownership

All code under `v2/cheque_bounce_management/`, `v2/cheque_scan.py`, `v2/cheque_ocr/`, `v2/outstanding_amounts.py`
(+`v1/outstanding_amounts.py`), `v2/outstanding_backfill.py`, `v2/neft_limits.py`, `v2/scheduler.py`,
`v2/store_visit.py`(+`_cron.py`), `v2/invoice_missing.py`, `v2/merge_quid_stores.py`, `v2/transaction_flow_*`,
`v2/payment_methods.py`, `v2/kafka_utils/`, and their tests is treated as the subject's own work, per direction.
No per-file attribution table is produced. `v2/model.py` and `v2/main.py` are large shared files the CBM/OCR/PDC
code imports from and registers into; table/route counts below are scoped explicitly to what the CBM/scan/suspense
feature set actually declares, not to the whole file.

---

## 2. Architecture, Components, Data Flows, External Systems

**Runtime shape.** `v2/main.py` is a single Flask app (`Flask(__name__)`, `v2/main.py:189`) that (a) declares
~81 routes directly (`@app.route`, counted by grep), (b) registers the CBM blueprint tree at `/v1/cbm`
(`cheque_bounce_management.cbm.cbm_bp`, mounted `v2/main.py:4266`), and (c) starts four background workers
in-process at import time: `AutoCloseScheduler`, `ChequeOcrScheduler`, `PdcReconScheduler` (all `v2/scheduler.py`,
wired `v2/main.py:197/215/244`) and a separate `StoreVisitResetScheduler` (`v2/store_visit_cron.py:44`, wired
`v2/main.py:206`). One process is both an API server and a scheduler host — there is no separate worker
deployment for these four jobs; `Dockerfile.consumer` and `Dockerfile.dms-consumer` are for the two Kafka
consumers, which *are* separate processes.

**CBM internal layering** (`v2/cheque_bounce_management/`):
```
api/<role>/*.py        Flask blueprints — thin HTTP handlers, JWT/OTP auth, request validation (pydantic)
functions/<role>_functions.py   orchestration: multi-step business flows, cross-repository coordination
services/<role>_service.py      higher-level read-side assembly (dashboards, cashier verification lists,
                                 e-invoice generation) and some write orchestration
repositories/<role>.py          SQLAlchemy queries, generic Repository[T] base (find_by_id/find_all/save)
                                 specialized per role (CBMRepository -> Cashier/Segregator/SalesOfficer)
helper/                         auth.py (JWT+OTP+SHA512), sms_utils.py, whatsapp_utils.py
utils/                          utils.py (edit-mode matrix, history labels), validator.py (pydantic models),
                                 cleartax_client.py (GST e-invoice HTTP client)
```
`repositories/common.py` holds the shared `CBMRepository` base — including the accountability-lock primitive
(§10 bullet 10) and the CBM-specific NEFT verification gate — that `cashier.py`/`segregator.py`/`sales_officer.py`
repositories all specialize from.

**Domain data flow (bounce → recovery), by file:**
1. A cheque bounces upstream (CDMS/cdms-one order flow, outside this repo) → a `CBMCheque` row is created
   (`state='created'`) with a matching `ChequeBounceDetail` and a `CBMHistory` entry.
2. Cashier receives it at hub → assigns to a Segregator → **accountability-lock interval** opens
   (`repositories/common.py:299`, `create_user_inactivity_interval`). Segregator acknowledges/rejects
   (`functions/segregator_functions.py`) or the cashier gets blocked after 30 minutes
   (`repositories/common.py:347`, `check_user_inactivity_blocking`, `constants.py` `BlockUser.TIMEOUT=30`).
3. Segregator assigns to a Sales Officer → the same lock primitive opens again, this time
   Segregator-as-assigner/Sales-Officer-as-assignee (`api/sales_officer/acknowledgement.py`,
   `start_collections_function`).
4. Sales Officer visits the store, photographs the cheque: `GET /v2/cheque-scan/upload-url` (presigned S3 PUT,
   `v2/cheque_scan.py:50`) → `POST /v2/cheque-scan/process` (idempotent registration, `v2/cheque_scan.py:85`) →
   `ChequeOcrScheduler` claims and OCRs it in the background (`v2/scheduler.py:189`, `v2/cheque_ocr/worker.py`).
5. Sales Officer records a collection (cash/cheque/UPI/NEFT) — `api/sales_officer/collections.py` →
   `functions/sales_officer.py`: editability is gated by the collection-state × payment-state matrix
   (`utils/utils.py:155`, `get_edit_mode`), QR-UPI is auto-verified on submit
   (`functions/sales_officer.py:auto_verify_qr_upi_on_submit` → `payment_methods.update_cbm_upi_payment`), and
   any scanned cheque image is linked to the resulting `cbm_payment` row by client-supplied `scanned_cheque_id`
   (`functions/sales_officer.py:278`, `link_scanned_cheque`) — linking does **not** wait on `ocr_status`, so a
   slow/failed OCR pass never blocks submission.
6. Cashier verifies the collection (`api/cashier/verification_apis.py` → `functions/cashier_functions.py`):
   a new `Cheque` payment lazily creates a `cheque_suspense` row in `PendingRealization`
   (`outstanding_amounts.suspense_transition`), triggers e-invoice generation when the store/FC GSTINs share a
   state prefix (`services/e_invoice_service.py:41`, `is_e_invoice_eligible`), and queues a WhatsApp notification
   over Kafka.
7. `PdcReconScheduler` (every 600s) later realizes cheques the external automation service reports as collected
   (`outstanding_amounts.run_pdc_recon_tick`, `v2/scheduler.py:294`).
8. Terminal: cheque is `fully_recovered`, manually `short_closed` (remaining ≤ ₹500,
   `functions/sales_officer.py:337`), or auto-`short_closed` after 30 days by `AutoCloseScheduler`
   (`v2/scheduler.py:73`). Store order-unblock is triggered from the cashier/segregator verify flows
   (`functions/cashier_functions.py:703`, `trigger_order_unblock_for_stores`) via an HTTP POST to an
   externally configured `order_blocking_base_url`.

**External systems touched by this feature set:**
- **AWS S3** — presigned PUT (upload, Object Lock bucket needs `content_md5`) and presigned GET (view), for both
  cheque scans (`v2/cheque_scan.py`) and store-visit selfies (`v2/store_visit.py:45`).
- **ClearTax** — GST e-invoice generation, `cheque_bounce_management/utils/cleartax_client.py`, config section
  `[cleartax]`. Existence noted only — not read for values.
- **WhatsApp Business (Wati) / Kaleyra** — `[wati_api]`/`[kaleyra]` config sections; OTP and cheque-bounce/
  auto-close notifications sent via `whatsapp_notification/` (majority this author, 45 of ~72 commits) and
  dispatched asynchronously through Kafka.
- **Kafka** (`confluent-kafka`) — internal event bus; topics carry WhatsApp-notification and QUID-collection
  keys (`v2/kafka_utils/consumer.py`).
- **An external "automation service"** populates `cheque_automation_logs` (bank-statement-matched cheque
  status) — not in this workspace; `PdcReconScheduler` only reads it.
- **An external "order blocking" service**, reached over plain `requests.post` from `cashier_functions.py`, for
  the unblock call after recovery (see §12 for the numbers caveat on the block side).
- **cdms-one (Node.js)**, sharing the same MySQL `cdms` schema — `colections_v2`'s `/complete` links Salesman
  scans into the same `scanned_cheques` table this repo owns, and its `outstanding_ledger.js` maintains the
  mirrored `unverified_amount`/`cheque_pdc_amount` invariant this repo's `outstanding_amounts.py` also writes —
  documented explicitly in the module docstring (`v2/outstanding_amounts.py:1-16`) as a cross-service contract.
- **MySQL** is the system of record throughout (`PyMySQL` driver); `pymongo.MongoClient` is imported in
  `main.py` for other (non-CBM) parts of the monolith.

---

## 3. APIs, Consumers, and Crons

**CBM blueprint tree — 65 routes / 9 blueprints, mounted at `/v1/cbm`** (`cbm.py:34-49`):

| Blueprint (file) | Prefix | Routes | Purpose |
|---|---|---|---|
| `sales_officer_auth_bp` (`api/sales_officer/auth.py`) | `/sales-officer-auth` | 9 | mobile→OTP/PIN bootstrap, login, reset/resend OTP, create officer, device register/deactivate |
| `sales_officer_list_bp` (`api/sales_officer/list.py`) | `/sales-officer-list` | 4 | tabbed cheque lists (in-progress/disputed/closed/collection) |
| `sales_officer_acknowledgement_bp` (`api/sales_officer/acknowledgement.py`) | `/sales-officer-acknowledgement` | 6 | assignment alert, acknowledge/dispute, start-collections (accountability lock) |
| `collections` (`api/sales_officer/collections.py`) | `/sales-officer-collections` | 8 | collection CRUD, save/submit, cheque-scan linkage |
| `segregator_bp` (`api/segregator/functional_apis.py`) | `/segregator` | 6 | dashboard, assign/unassign to Sales Officer, block-check |
| `segregator_verification_bp` (`api/segregator/verification_apis.py`) | `/segregator-verification` | 6 | segregator-side verify/reject of cheques |
| `cashier_bp` (`api/cashier/functional_apis.py`) | `/cashier` | 11 | dashboard, process notes, handover, cheque-bounce history, block-check, salesmen list |
| `cashier_verification_bp` (`api/cashier/verification_apis.py`) | `/cashier-verification` | 10 | cashier verify/reject/edit, NEFT/UPI verification list, e-invoice/proforma triggers |
| `cbm_migration_bp` (`cbm_migration.py`) | `/migration` | 5 | bulk Excel/CSV backfill, proforma/tax/e-invoice regeneration, WhatsApp re-notify |

**Consumers/crons:**
- `v2/kafka_utils/consumer.py` (`Dockerfile.consumer`, port 8005 + `/healthcheck/consumer`) — single-threaded
  `confluent_kafka.Consumer` poll loop, `group.id=whatsapp-consumer-group`, dispatches on message `key`
  (`WhatsappNotificationTemplateType`/`QuidIntegrationTemplateType`) to WhatsApp senders, quid-collection
  processing, or `process_auto_close_invoice_for_cheque`. See §8/§12 for a correctness note on its commit logic.
- `AutoCloseScheduler` (`v2/scheduler.py:73`) — daily cron (`02:30` default), auto-short-closes cheques
  `ACKNOWLEDGED_BY_SALES_OFFICER` for >30 days with `current_outstanding_amount <= 500` **and**
  `VERIFIED_BY_CASHIER`, then fans out one Kafka message per closed cheque for WhatsApp notification.
- `ChequeOcrScheduler` (`v2/scheduler.py:189`) — interval job (default 2s poll; see §12 for the current
  code defaults vs. previously-documented ones), night-window gated (23:00–05:00 IST by default,
  `_in_window` at `:230`), claims + OCRs + janitors stuck rows (`v2/cheque_ocr/worker.py`).
- `PdcReconScheduler` (`v2/scheduler.py:294`) — interval job, default 600s / batch 200, realizes
  `cheque_suspense` rows against `cheque_automation_logs` (`outstanding_amounts.run_pdc_recon_tick`).
- `StoreVisitResetScheduler` (`v2/store_visit_cron.py:44`) — monthly cron (`CronTrigger`, 1st @ 00:05 IST),
  resets all active `SalesOfficerStoreAssignment` statuses to `pending`. Not built on `BaseScheduler` — a
  separate, simpler APScheduler wrapper (see §8).
- `outstanding_backfill.py` (CLI, not a running service) — `--dry-run`/`--chunk-size`/`--report` seed+recompute
  tool for the unverified/PDC columns, with its own `REALIZING_STATUSES=("Collected",)`, deliberately narrower
  than the cron's (documented divergence, pinned by tests).

**Failure handling, consistently applied across the CBM verify/reject/bounce/void endpoints:** every handler
opens a `with Session() as session: try/... except: session.rollback(); raise` block, returns a structured
`{status, message, data}` JSON envelope, and logs the exception — there is no bare/uncaught-exception path in
what was read.

---

## 4. Database

**How the CBM-specific tables were counted:** `grep -n "__tablename__" v2/model.py` returns **232** table
declarations total. Filtering that list to names prefixed `cheque_` or `cbm_`, plus the two explicitly
CBM-adjacent tables named outside that convention (`scanned_cheques`, `champ_outstanding_suspense_logs`),
gives **26** CBM/suspense/scan tables:

`cbm_upi_payment`, `cheque_bounce_details`, `cheque_bounce_audit_logs`, `cheque_bounce_reasons`,
`cbm_process_notes`, `cheque_invoice_mapping`, `cheque_suspense`, `champ_outstanding_suspense_logs`,
`cheque_automation_logs` (external-service-owned, read-only here), `cbm_cheque_invoice_mapping`,
`cbm_collection_invoice_mapping`, `cbm_cheques`, `cbm_cgst_sgst_values`, `cbm_igst_values`, `cbm_e_invoicing`,
`cbm_short_closed`, `cbm_reject_records`, `cbm_reject_reason`, `cbm_collections`, `cbm_payments`,
`scanned_cheques`, `cbm_dispute_reason`, `cbm_dispute_records`, `cbm_history`, `cbm_user_inactivity_intervals`,
`cbm_seg_so_unassigned_records` (`v2/model.py:76-6114`). (`bank_settlement_cheque` at `model.py:536` contains
"cheque" but is a legacy cashier-settlement table, not part of the CBM domain, and is excluded.)

**Key schemas/relationships:**
- `CBMCheque` (`cbm_cheques`) — the aggregate root: `state` (`ChequeStates`, 11 values, `constants.py:356-368`),
  `initial_outstanding_amount`/`current_outstanding_amount`, `sales_officer_id`/`segregator_id` assignment
  columns, `short_closed` FK → `cbm_short_closed`.
- `CBMCollection` (`cbm_collections`) — one row per collection attempt against a cheque; `status`
  (`RecoveryStatus`, 4 values: pending/in_progress/recovered/short_closed, `constants.py:385-389`),
  `cheque_verification_status` (drives the editability matrix), `verified_by_cashier_id/_at`,
  `verified_by_segregator_id/_at`.
- `CBMPayment` (`cbm_payments`) — one row per cash/cheque/UPI/NEFT line in a collection; `curr_state`/
  `prev_state` reuse the shared `StateMachine` name-space (`DEFAULT/PERSIST/EDITAMOUNT/EDITDATA/
  EDITAMOUNTORDATA/SETTLE`) as keys into the CBM-specific `SalesOfficerEditMode` enum
  (`constants.py:416-424`) — same names, different (CBM) meaning.
- `ChequeSuspense` (`cheque_suspense`) — one row per **verified** cheque payment (rows are born at cashier
  VERIFY, not at salesman submit); `pdc_status` ∈ {PendingRealization, Rejected, Bounced, Realized, Void};
  natural key `(collection_invoice_id, cheque_number, bank_id)` used to re-find a row after a resubmit mints a
  new `payment_id` (`outstanding_amounts.py:233-256`, `_find_suspense`).
- `ChampOutstandingSuspenseLogs` (`champ_outstanding_suspense_logs`) — append-only ledger, one row per
  **column delta** (`field`, signed `delta`, `balance_after`, `source_service`, reference ids) — never
  updated or deleted, the audit trail for "why is this column X" (`outstanding_amounts.py:157-233`,
  `LEDGER_INSERT_SQL`/`lock_and_recompute`).
- `ScannedCheque` (`scanned_cheques`) — shared by two independent upload flows (Salesman vs. Sales-Officer),
  disambiguated by `user_type`; `master_pid` is an id from one of two different autoincrement spaces depending
  on `user_type`; UNIQUE constraint on `s3_key` is the idempotency guard.
- `CBMUserInactivityInterval` (`cbm_user_inactivity_intervals`) — `initiator_user_id`/`target_user_id`/`status`
  (`UserInactivityIntervalStatus`: pending/completed/expired) — the accountability-lock ledger.
- `CBMHistory` (`cbm_history`) — append-style audit trail of cheque state transitions, driving the
  human-readable timeline (`utils/utils.py:16-28`, `STATUS_LABEL_MAP`).

**Indexes seen directly:** `cheque_suspense` has a composite index on the natural key —
`Index("idx_cheque_suspense_natural_key", "collection_invoice_id", "cheque_number", "bank_id")`
(`v2/model.py:5413-5414`) — exactly the index needed by `_find_suspense`'s fallback lookup.

**Transactions / atomic operations:**
- Every outstanding-amount mutation runs `SELECT ... FOR UPDATE` on the `ChampOutstandingInvoices` row(s) before
  a single `UPDATE ... SET unverified_amount = (subquery), cheque_pdc_amount = (subquery)` — a full recompute
  under lock, never a `+=`/`-=` delta (`outstanding_amounts.py:128-165`).
- `cheque_suspense` rows are re-fetched `.with_for_update()` before any state transition
  (`outstanding_amounts.py:233-256`).
- `neft_limits.lock_reference` locks `bank_statement_api` rows by resolved primary key, in sorted order, to
  make concurrent overlapping-UTR requests acquire in the same order (deadlock avoidance) — and deliberately
  avoids a single `WHERE transaction_number = :ref ... FOR UPDATE` because that would take a gap lock and stall
  unrelated bank-statement ingestion (`v2/neft_limits.py:88-99, 176-192`).
- Several CBM cashier-verification code paths take `.with_for_update()` on the payment/collection rows before
  mutating status, with in-line comments explaining the exact race being closed
  (`functions/cashier_functions.py:908-913, 985-1030, 1222-1298`).

---

## 5. Async / Distributed Mechanisms

- **Claim-based work queues, not a broker**, for both background jobs: `scanned_cheques` (OCR) and
  `cheque_suspense` (PDC recon) are polled tables, claimed with `SELECT ... FOR UPDATE SKIP LOCKED`
  (`cheque_ocr/worker.py:24-48`; `outstanding_amounts.py:465-469`) so multiple Flask replicas running the same
  in-process scheduler never process the same row twice.
- **Crash recovery via a timeout janitor**: `fail_stuck_processing` flips scans stuck in `PROCESSING` back to
  `FAILED` after a timeout, computed from the **database clock** on MySQL (`func.now() - INTERVAL ... SECOND`)
  specifically to avoid app-server/DB clock skew, falling back to a Python clock only on SQLite in tests
  (`cheque_ocr/worker.py:95-117`).
- **Per-item failure isolation**: `run_pending_batch` and `process_one` each wrap a single scan's processing so
  one bad image/DB hiccup can't abort the rest of the batch, and the FAILED-marking itself is wrapped again so a
  failure *while recording a failure* can't propagate (`cheque_ocr/worker.py:51-92, 120-141`).
- **Idempotent registration under a race**: `register_scan` does an owner-scoped read, then an insert, and on
  a `UNIQUE(s3_key)` `IntegrityError` (a concurrent retry that raced past the pre-check) rolls back and returns
  the row that won — never raises a duplicate error to the client (`cheque_scan.py:85-152`).
- **Exactly-once realization across independent triggers**: a cheque can leave `PendingRealization` via the
  cron, the bounce endpoint, or the void endpoint; because all three gate on the *current* `pdc_status` via
  `next_pdc_state`, and the cron's SQL filter only ever selects `PendingRealization` rows, a cheque already
  moved out by one path is structurally invisible to the others (`outstanding_amounts.py:30-96, 437-520`).
- **Declarative illegal-transition handling**: `next_pdc_state` returns `(None, "silent"|"warn"|"critical")`
  for a disallowed `(event, state)` pair instead of raising — repeat calls and cross-mechanism races degrade to
  a logged no-op rather than a 500 (`outstanding_amounts.py:84-96`).
- **Derived, never-materialized budgets**: `neft_limits.py` computes a UTR's spend budget as
  `bank_statement_api.credit (MAX across duplicate ingestion feeds) − SUM(consuming, non-released payments)`
  on every check, rather than maintaining a running counter — "an unverified payment row IS the reservation"
  (`neft_limits.py:1-39, 126-236`), and a locking read is used specifically because MySQL's default
  REPEATABLE READ would otherwise serve a stale snapshot from before a competing verification committed
  (`neft_limits.py:253-256`).
- **Kafka**: idempotent producer (`enable.idempotence: True`, `acks: all`, `retries: 3`,
  `kafka_utils/producer.py:67-78`) with a non-blocking `poll_nowait`/blocking `poll_n_flush` pair so the
  scheduler/request thread doesn't stall on delivery; consumer runs `auto.offset.reset=earliest`,
  `group.id=whatsapp-consumer-group`, dispatches by message key. **Gap**: the consumer's except-branch commits
  the offset anyway (see §8/§12) — so today this is at-most-once, not at-least-once with retry, despite the
  in-line comment implying the latter.
- **Cross-service invariant, not just cross-process**: the `unverified_amount`/`cheque_pdc_amount` invariant is
  maintained independently by this Python service and a sibling Node.js service (`cdms-one`) against the *same*
  MySQL rows; consistency is achieved by both sides recomputing the full value under lock rather than
  exchanging messages (`outstanding_amounts.py:1-16`).

---

## 6. Infrastructure

- **Containers**: 4 Dockerfiles in `v2/`, 3 of them serving this feature set: `Dockerfile` (main Flask app —
  `python:3.8-slim`, installs `libgl1 libglib2.0-0 libxcb1 libgomp1` for OpenCV/onnxruntime, `OMP_NUM_THREADS=2`,
  port 5000), `Dockerfile.consumer` (`python:3.9-slim`, runs `kafka_utils/consumer.py`, port 8005 +
  `/healthcheck/consumer`), `Dockerfile.merge-quid` (`python:3.8-slim`, runs the Streamlit
  `merge_quid_stores.py` tool on port 8501). `Dockerfile.dms-consumer` serves an unrelated integration and was
  not analyzed. ECS is the stated deployment target (ports/health-check pattern match an ALB/ECS service, not
  independently verified against AWS).
- **Config**: `.config.toml` (gitignored, existence-only) exposes 24 top-level sections including
  `[mysqlConnection]` / `[mysqlConnection.master]` / `[mysqlConnection.stage]` (config-level provision for a
  read/default/master split), `[s3]`, `[aws]`, `[sentry]`, `[jwt]`, `[auth]`, `[cheque_bounce]`
  (order-blocking base URL), `[cleartax]`, `[wati_api]`, `[kaleyra]`, `[kafkaConnections]`,
  `[quid_store_merge]`, `[outstanding_ledger]`, `[pdc_recon]`, `[neft_partial_consumption]` — the last three are
  the feature flags gating the outstanding/PDC/NEFT-budget rollouts, each `enabled=false`-by-default in code
  (`outstanding_amounts.py:97-101`, `neft_limits.py:102-110`). Section names only; values not read.
- **Observability**: Prometheus via `prometheus-flask-exporter` (`metrics = PrometheusMetrics(app)`,
  `v2/main.py:183`, exposing `/metrics`), Sentry APM (`init_sentry()`, `v2/main.py:186`,
  `sentry-sdk==1.35.0`).
- **Object storage**: S3 with Object Lock (cheque scans, store-visit selfies) — presigned PUT requires
  `content_md5`; presigned GET is short-lived, generated per-request rather than stored.
- **Security note (infrastructure, not attribution)**: `v2/settlement_cron.py:17-19` hardcodes a production
  RDS username/password/host directly in source rather than reading it from config/secrets. This is a pre-existing
  issue in the repository worth flagging for rotation; the credential value is intentionally not reproduced here.

---

## 7. Reliability and Performance Mechanisms (with evidence)

| Mechanism | Where | Why it matters |
|---|---|---|
| `FOR UPDATE SKIP LOCKED` claim queues | `cheque_ocr/worker.py:39`, `outstanding_amounts.py:469` | multiple replicas of the same in-process scheduler never double-process a row |
| DB-clock-based stuck-row janitor | `cheque_ocr/worker.py:95-117` | crash mid-OCR self-heals without a human, without app/DB clock-skew bugs |
| Per-item exception isolation | `cheque_ocr/worker.py:51-92, 120-141` | one poisoned image can't stall or fail the whole batch |
| UNIQUE-constraint idempotent insert | `cheque_scan.py:85-152` | client retries under a flaky mobile network are safe by construction |
| Recompute-under-row-lock (not delta-patch) | `outstanding_amounts.py:128-165` | resubmits physically delete+recreate `payments` rows; delta bookkeeping would drift, recompute self-heals |
| Declarative transition table + no-op classification | `outstanding_amounts.py:30-96` | illegal/duplicate events across independent call sites degrade to logged no-ops, not exceptions |
| Append-only audit ledger, one row per delta | `outstanding_amounts.py:157-233`, `model.py:5461` | full point-in-time reconstruction of "why is this balance X" |
| Deadlock-safe sorted-order locking | `neft_limits.py:176-192` | two requests naming overlapping UTRs can't deadlock each other |
| Gap-lock avoidance by locking resolved PKs | `neft_limits.py:88-99` | prevents a common-case "UTR not yet seen" lookup from stalling bank-statement ingestion |
| MAX-not-SUM de-duplication of bank credit | `neft_limits.py:207-236` | same wire transfer is ingested twice (two feeds); MAX can only under-allow, never over-allow |
| Batched (not per-row) budget lookup | `neft_limits.py:365-433` | removes an N+1 query from the cashier verification-list render |
| Night-window + CPU-thread capping for OCR | `scheduler.py:208-224`, `cheque_ocr/engine.py:26-51`, `Dockerfile` | eliminates a documented daytime 99% CPU spike from multiple OCR containers each grabbing every core |
| Orientation-aware OCR retry, fast-pathed | `cheque_ocr/engine.py:65-87` | only pays for 2 extra OCR passes when the photo is actually detected as sideways |
| Accountability-lock primitive (generic) | `repositories/common.py:299-410` | reused unmodified at two different handoff points in the pipeline |
| Explicit trust exceptions on reset | `functions/sales_officer.py:589-627` | prevents a resubmit from silently un-trusting a bank-confirmed UPI/NEFT payment |
| Two-flow disambiguation by `user_type` | `cheque_scan.py`, `response_mappers.py`, `common_functions.py` | one shared table, two independent writers, overlapping id-spaces — never cross-matches |

---

## 8. Design Decisions, Trade-offs, Alternatives, Known Gaps

- **Recompute over delta-patch** (outstanding amounts): the documented alternative (incrementing/decrementing
  on each event) was rejected because `colections_v2`'s resubmit path deletes and re-inserts `payments` rows
  with new ids — a delta approach has no stable identity to reverse against. The trade-off is cost (a full
  subquery recompute per touched invoice on every event) for correctness/self-healing.
- **Deny-list, not allow-list, for NEFT-released statuses**: `NEFT_RELEASED_STATUSES` is explicitly a deny-list
  so that any *new* status added later still counts against the budget by default — the conservative direction
  given the invariant "total verified must never exceed the bank-received amount" (`neft_limits.py:52-60`).
- **`INCLUDE_CBM_PAYMENTS = False`** in `neft_limits.py:76` is a documented, deliberate half-finished state:
  Sales-Officer NEFT lives in a separate table (`cbm_payments`) and it is not yet confirmed whether those rows
  are also mirrored into `payments` as `CBM_NEFT` — turning it on before that's confirmed risks double-counting
  and wrongly blocking a legitimate collection. The module's own docstring calls wiring it into the CBM gate
  (`_get_neft_verification_info`, `repositories/common.py:570`) "a separate change" — i.e. the budget module
  and the CBM gate are not yet connected.
- **Two different scheduler idioms in the same codebase**: `AutoCloseScheduler`/`ChequeOcrScheduler`/
  `PdcReconScheduler` share a `BaseScheduler` ABC (`scheduler.py:22`); `StoreVisitResetScheduler`
  (`store_visit_cron.py:44`) is a standalone `BackgroundScheduler` wrapper with its own job-wrapper logic,
  not built on the ABC. Worth being able to explain in an interview (likely just sequencing — one predates the
  refactor) but it is a real, visible inconsistency in the code as it stands today.
- **`SalesOfficerEditMode[payment.curr_state]`** (`utils/utils.py:171`) is a dict-style enum lookup with no
  explicit `try/except` at the call site; an unrecognized `curr_state` would raise `KeyError`. In practice this
  surfaces as a 400 through the enclosing `try/except Exception` in `validate_and_update_existing_payments`
  (`functions/sales_officer.py:478`) rather than a 500 — but it relies on that outer handler existing; it is not
  defended locally.
- **Kafka consumer commit-on-failure** (`kafka_utils/consumer.py:130-138`): the code comments the happy path
  "commit only after success" and the except branch "don't commit here if you want retries" — but then commits
  the offset in *both* branches. As written, a failed WhatsApp/quid-collection/auto-close message is silently
  dropped, not retried, contradicting the stated intent. This is a genuine correctness gap worth being ready to
  discuss (see §12).
- **Duplicated DB-connection idioms**: `model.py:get_session_factory` builds its engine from `.config.toml`
  (`Box(read_toml_file(...))`); `transaction_flow_cron.py:14` builds a *separate* engine straight from
  `os.getenv(...)` + `python-dotenv`. Two different configuration mechanisms for the same MySQL database in
  the same repository — plausibly because this script runs as an independent cron process with its own
  deployment/secrets path, but that's an assumption, not confirmed in this pass.
- **Ops tools traded strict correctness for iteration speed**: `merge_quid_stores.py`'s `merge_stores()` uses
  broad `except Exception` blocks that return error dictionaries (including a full traceback string) rather than
  raising, and has no dry-run mode — reasonable for a bcrypt-gated internal Streamlit tool used by a small
  number of ops users, less so if it were ever exposed more broadly.
- **`cbm_migration.py`'s `/migrate`** is a genuine bulk-import API (Excel/CSV via pandas) rather than a one-off
  script — it is idempotent per row (mapping-exists check before creating a new `CBMChequeInvoiceMapping`) but
  has no transaction-per-chunk boundary visible in the read portion; a mid-loop failure's blast radius (whole
  request vs. partial commit) would be worth confirming against the full function body before citing a specific
  atomicity guarantee.

---

## 9. Numbers

**(a) Derivable from code, with source:**
- 232 total table classes in `v2/model.py`; **26** are CBM/scan/suspense-specific (method: grep
  `__tablename__`, filter to `cheque_`/`cbm_` prefixes + `scanned_cheques` + `champ_outstanding_suspense_logs`;
  full list in §4).
- CBM blueprint tree: **65 routes across 9 blueprints** (grep `_bp\.route(` per file; per-file breakdown in §3),
  mounted at `/v1/cbm` (`cbm.py:34-49`, `main.py:4266`).
- `v2/main.py`: **81** `@app.route` decorators (grep count). A small number of these are test/debug endpoints
  (e.g. `/v2/test-kafka`, `/v2/test-auto-close-scheduler`, both visible near `main.py:4270-4300`) that a
  narrower "active" count would likely exclude.
- `ChequeStates`: 11 members; `RecoveryStatus`: 4; `SalesOfficerEditMode`: 7 (`constants.py:356-368, 385-389,
  416-424`); `ChequeBounceCharge.BOUNCE_CHARGE = 500` (₹), `SGST=CGST=9` (%) (`constants.py:379-382`);
  `BlockUser.TIMEOUT = 30` (minutes) (`constants.py:425-427`).
- Scheduler defaults **as currently coded** (some differ from earlier documentation of this feature — using the
  code as the source of truth): `AutoCloseScheduler` — `auto_close_days_threshold=30`,
  `auto_close_amount_threshold=500`, default run time `02:30` (`scheduler.py:73-79`,
  `main.py:` scheduler init block). `ChequeOcrScheduler` — `poll_interval_seconds=2`, **`batch_size=5`**,
  **`stuck_timeout_seconds=300`**, `is_cheque_min_signals=2`, night window `23:00–05:00 Asia/Kolkata`
  (`scheduler.py:199-216`). `PdcReconScheduler` — `poll_interval_seconds=600`, `batch_size=200`
  (`scheduler.py:304-309`).
- Test functions (grep `def test_`, per directory, method noted since basenames collide across v1/v2): v2 tree
  **345** (includes `cheque_bounce_management/tests/` 9, `cheque_ocr/` tests, `dms_integration/` tests), root
  `tests/` **144**, v1 **95** — **584 total**.
- `requirements.txt` pins (exact versions as declared): Flask 2.3.2, SQLAlchemy 2.0.18, PyMySQL 1.1.0,
  PyJWT 2.7.0, boto3 1.28.52, sentry-sdk 1.35.0, prometheus-flask-exporter 0.23.1, APScheduler 3.10.4,
  kafka-python 2.0.2, confluent-kafka 2.3.0, pymongo 4.3.3, rapidocr-onnxruntime>=1.3.0, numpy>=1.24,
  bcrypt>=4.0.0, streamlit>=1.28.0.
- 4 Dockerfiles in `v2/` total; 3 map to this feature set (main app, Kafka consumer, Streamlit merge tool).
- 24 top-level sections in `.config.toml` (grep `^\[`; names only, no values read).
- Row-lock (`FOR UPDATE` / `with_for_update`) call sites in the CBM/outstanding/NEFT/OCR code: at least 15
  distinct sites (grep count across `outstanding_amounts.py`, `neft_limits.py`, `cheque_ocr/worker.py`,
  `cheque_bounce_management/functions/cashier_functions.py`).
- Documented CPU impact: the `Dockerfile` and `scheduler.py` comments state the OCR thread-capping fix targets
  "the daytime 99% CPU spike" — a number stated in the code's own comments, not independently benchmarked here.

**(b) Numbers only the user can supply — each framed as the exact question to ask, and which bullet it strengthens:**
1. "Do you have before/after p99 latency numbers (Sentry/APM) for the cashier verification-list endpoint
   before and after the batched `available_map_for_references` lookup went in?" — strengthens **bullet 5**
   (N+1 elimination) and directly supports the old resume's "p99 3s→800ms" claim with a *current, concrete*
   example instead of a vague one.
2. "Roughly how many cheque scans does `ChequeOcrScheduler` process per night, and what's the real-world
   accuracy/false-positive rate of the `is_cheque` signal check?" — strengthens **bullets 6–7** (OCR worker).
3. "What's the current volume — cheques bounced per month, and the split between fully-recovered vs.
   short-closed?" — strengthens the overall CBM narrative in interview framing (§11).
4. "How many rows/what's the growth rate of `cheque_suspense` and `champ_outstanding_suspense_logs` in
   production, and has the cron ever fallen behind (batch_size=200 every 600s)?" — strengthens **bullets 1–3**
   (suspense state machine, recompute-under-lock, recon cron) with a scale figure.
5. "For the QUID store-merge tool and the `cbm_migration.py` Excel importer — roughly how many stores were
   merged / how many legacy bounce records were backfilled?" — strengthens **bullets 14–15**.
6. "Is there a measured number for how often the Kafka consumer's silent-drop-on-exception (see §8) has
   actually lost a notification in production, or has this not surfaced yet?" — informs how (or whether) to
   raise this in an interview if asked about reliability.

---

## 10. Candidate Resume Bullets

1. **Declarative Suspense State Machine:** Modeled the cheque-suspense lifecycle (PendingRealization/Rejected/Bounced/Realized/Void) as a data-driven transition table instead of branching logic, classifying every illegal call as a silent or critical no-op so four independent call sites can never double-subtract the same cheque.
   Evidence: `v2/outstanding_amounts.py:30-96` (TRANSITIONS, `next_pdc_state`), `275-357` (`suspense_transition`)

2. **Recompute-Under-Lock Bookkeeping:** Architected outstanding-amount bookkeeping to recompute-under-row-lock rather than delta-patch, because resubmits delete and re-insert payment rows with new ids; every hook locks the invoice row, recomputes both columns from a subquery, and appends a signed-delta audit row.
   Evidence: `v2/outstanding_amounts.py:128-165` (`lock_and_recompute`); `v2/model.py:5461` (`champ_outstanding_suspense_logs`)

3. **Exactly-Once Reconciliation Cron:** Automated a 10-minute reconciliation cron that claims pending cheques with FOR UPDATE SKIP LOCKED, joins each to its latest automation-log row via a correlated MAX subquery, and realizes exactly once across cron, bounce, and void paths through state-filter exclusion.
   Evidence: `v2/outstanding_amounts.py:437-520` (`run_pdc_recon_tick`); `v2/scheduler.py:294-333`

4. **Derived Per-UTR NEFT Budget:** Engineered a per-UTR NEFT budget as a derived value instead of a stored counter: MAX (not SUM) credit across two duplicate bank-ingestion feeds, sorted-order row locks to avoid cross-request deadlock, and a REPEATABLE-READ-aware locking read for the consuming sum.
   Evidence: `v2/neft_limits.py:176-236, 239-321`

5. **N+1 Elimination in Verification Rendering:** Optimized the cashier verification-list render by replacing a per-payment budget lookup with two batched GROUP-BY queries — one for credits, one for committed amounts — covering every reference number on the page in constant round-trips instead of N+1.
   Evidence: `v2/neft_limits.py:365-433` (`available_map_for_references`)

6. **Crash-Safe OCR Worker:** Hardened the OCR worker with FOR UPDATE SKIP LOCKED claiming so parallel replicas never grab the same scan, a stuck-in-PROCESSING janitor keyed to the database clock to survive worker crashes, and per-scan exception isolation so one bad image can't halt a batch.
   Evidence: `v2/cheque_ocr/worker.py:24-48` (`claim_pending`), `95-117` (`fail_stuck_processing`), `120-141` (`run_pending_batch`)

7. **Orientation-Correcting OCR + CPU Throttling:** Designed an OCR pass that retries a cheque photo at ±90° only when a MICR/signal heuristic flags it as sideways, paired with onnxruntime thread-capping and a night-only execution window that eliminated a documented daytime 99% CPU spike.
   Evidence: `v2/cheque_ocr/engine.py:26-51, 65-87`; `v2/scheduler.py:208-224, 230-247`; `v2/Dockerfile`

8. **Idempotent Two-Flow Scan Pipeline:** Built an idempotent S3 cheque-scan pipeline shared by two independent upload flows (Salesman, Sales-Officer) writing the same table with overlapping id-spaces disambiguated by a user_type column; presigned PUT/GET, UNIQUE(s3_key) idempotent registration, and re-scan lineage preserving an existing payment link.
   Evidence: `v2/cheque_scan.py:39-65` (`build_scan_s3_key`, `get_upload_url`), `85-152` (`register_scan`)

9. **Multi-Scheduler Orchestration Framework:** Orchestrated a shared BackgroundScheduler ABC (job-wrapper, error isolation, structured logging) specialized into three in-process workers — 30-day auto short-close, OCR polling, PDC reconciliation — each independently toggled through TOML feature flags without redeploying the others.
   Evidence: `v2/scheduler.py:22-70` (`BaseScheduler`), `73`/`189`/`294` (subclasses); `v2/main.py:197-244`

10. **Reusable Accountability-Lock Primitive:** Devised a generic accountability-lock primitive, parameterized by initiator/target rather than hardcoded to one handoff, that blocks the assigner (not the assignee) when a cheque handoff sits unacknowledged past 30 minutes — applied identically at both the cashier-to-segregator and segregator-to-officer stages.
    Evidence: `v2/cheque_bounce_management/repositories/common.py:299-347, 383-407`; `v2/constants.py:425-427` (`BlockUser.TIMEOUT`)

11. **Two-Dimensional Editability Model:** Formalized payment editability as a function of collection-verification state AND per-payment state rather than a boolean, reusing the pre-existing payment state-machine names as lookup keys into a Sales-Officer-specific permission enum, with amount and reference edits gated independently.
    Evidence: `v2/cheque_bounce_management/utils/utils.py:155-174`; `v2/cheque_bounce_management/functions/sales_officer.py:486-497`

12. **Selective Verification Reset:** Reinforced the collection-resubmit path so editing previously-verified money resets its verification status, while explicitly exempting UPI/NEFT payments already confirmed by an automated bank match — a three-status exception list that stops re-trusting unconfirmed cash or cheque edits.
    Evidence: `v2/cheque_bounce_management/functions/sales_officer.py:589-627`

13. **Idempotent Kafka Producer Wrapper:** Integrated a production Kafka producer wrapper over confluent-kafka with idempotent delivery (enable.idempotence), bounded retries with backoff, per-message trace headers, and a non-blocking poll/flush pattern so request handlers and cron jobs never stall on broker acknowledgement.
    Evidence: `v2/kafka_utils/producer.py:37-89, 131-163`

14. **Excel/CSV Bulk-Migration API:** Shipped a pandas-driven bulk-migration endpoint that backfills legacy cheque-bounce records into the relational schema with per-row idempotency (mapping-exists checks) and skip/create counters, plus companion endpoints that regenerate proforma, tax, and e-invoices for migrated rows on demand.
    Evidence: `v2/cheque_bounce_management/cbm_migration.py:46-254`

15. **Standalone Internal Ops Tool:** Delivered a standalone internal Streamlit admin tool for merging duplicate store identities across three tables (Store/GstStore/BnplStore) with bcrypt-gated login and an audit-log table, deployed as its own containerized service with a dedicated Dockerfile and port.
    Evidence: `v2/merge_quid_stores.py:11-168`; `v2/Dockerfile.merge-quid`

---

## 11. Interview Material

**Hard problems (reasoning / failure scenarios / alternatives):**

1. *Two Flask replicas both run `ChequeOcrScheduler` and `PdcReconScheduler` in-process. Walk through exactly
   what stops them double-processing the same row, and what happens if a worker is killed mid-OCR.*
   Answer shape: `FOR UPDATE SKIP LOCKED` claim (flips PENDING→PROCESSING and commits immediately, so the row
   is visibly "owned" the instant it's claimed); a killed worker just leaves the row in PROCESSING, which the
   next tick's `fail_stuck_processing` reclaims as FAILED once `updated_at` is older than the timeout — nothing
   is silently lost, and the fallback to a plain `SELECT` is intentionally restricted to SQLite so a bug can
   never silently double-process on real MySQL (`cheque_ocr/worker.py:24-48`).

2. *A salesman resubmit deletes and reinserts `payments` rows with brand-new ids. How does suspense/outstanding
   bookkeeping avoid drifting when the row identity it was tracking no longer exists?*
   Answer shape: nothing is delta-patched — `lock_and_recompute` always recomputes both columns from scratch
   under a row lock, so there is no running total to lose sync with; `_find_suspense` falls back to the natural
   key `(collection_invoice_id, cheque_number, bank_id)` when `payment_id` no longer resolves
   (`outstanding_amounts.py:233-256`). Known edge, by design not yet closed: `cheque_automation_logs.payment_id`
   itself goes stale on a resubmit and isn't re-pointed.

3. *Why is `SalesOfficerEditMode[payment.curr_state]` a dict-style enum lookup instead of an if/elif chain, and
   what happens if a new `curr_state` value is introduced without updating this enum?*
   Answer shape: it's a deliberate re-use of the pre-existing `StateMachine` member names as the CBM
   permission enum's keys, so a payment's persisted state doubles as the permission lookup with zero extra
   storage. An unmapped value raises `KeyError`, which is not caught locally — it propagates to the
   caller's `try/except Exception` (`functions/sales_officer.py:478`) and surfaces as a 400, not a crash — but
   that safety is incidental to the outer handler, not defended at the lookup site.

4. *How is `unverified_amount`/`cheque_pdc_amount` kept consistent when a sibling Node.js service maintains the
   same invariant against the same MySQL rows?*
   Answer shape: both sides recompute the *full* value from source rows under lock rather than exchanging
   deltas or events, so there's no ordering/message-loss problem to solve — whichever side runs last simply
   produces the correct total. Rollout was staged and reversible: migration first, flags off, backfill via
   `outstanding_backfill.py --dry-run`, then flags on (`outstanding_amounts.py:1-16`, `is_enabled` gate).

5. *What actually happens if a Sales Officer photographs a cheque and the OCR pass fails or never completes
   before they submit the collection?*
   Answer shape: submission doesn't wait on `ocr_status` at all — `link_scanned_cheque` is called with the
   client-supplied `scanned_cheque_id` regardless of OCR outcome (`functions/sales_officer.py:278`), so a
   FAILED/NOT_A_CHEQUE/still-PENDING scan still gets linked to the payment; the OCR-extracted fields are just
   an assist for manual entry, not a gate.

**Likely follow-ups (with technically accurate answers):**

- *Why MAX and not SUM when resolving a UTR's credit?* Two ingestion feeds (InstaAlert + StatementAPI) can both
  record the same wire transfer; SUM would double the available budget, MAX can only under-allow — the safe
  direction (`neft_limits.py:207-236`).
- *Why is `DROP` from `PendingRealization` flagged CRITICAL even though the transition table allows it?*
  Because a verified-and-still-pending cheque being dropped (rather than bounced or realized) is legal
  mechanically but operationally suspicious — it's logged loudly for a human to review, not blocked outright
  (`outstanding_amounts.py:79-81`, `CRITICAL_TRANSITIONS`).
- *Why cap onnxruntime threads only at first engine build, with no way to change it later?* The OCR engine is a
  process-level singleton (model load is the expensive part), so thread configuration is a one-time
  initialization concern, not a per-request one (`cheque_ocr/engine.py:15-37`).
- *Why is `available_map_for_references` non-locking while `available_for_reference` supports a locking read?*
  The batched version serves read-only list rendering (staleness is acceptable for a display), while the
  single-reference version is used at the point of actually consuming budget, where a locking read is
  load-bearing (`neft_limits.py:239-362`).
- *Why store `ocr_raw_json` on every outcome, including FAILED/NOT_A_CHEQUE, not just DONE?* Debuggability —
  it's the only way to inspect what RapidOCR actually saw on a scan that didn't parse as a cheque, without
  re-fetching and re-running OCR on the original image (`cheque_ocr/worker.py:62-63`).
- *Why does `register_scan` check for an existing `(s3_key, user_id)` row before inserting, if the UNIQUE
  constraint would catch a duplicate anyway?* The pre-check makes the common re-POST-to-poll case a cheap read
  with no write/rollback at all; the UNIQUE constraint is the correctness backstop for the race the pre-check
  can't close (`cheque_scan.py:107-116` vs. `137-152`).
- *What's the difference between the two Salesman/Sales-Officer upload flows sharing one table?* Same
  `scanned_cheques` table, disambiguated entirely by `user_type`, because `master_pid` is drawn from two
  different (overlapping) autoincrement id-spaces (`master_payments.id` vs `cbm_payments.id`) — every read is
  scoped by `user_type` so the spaces can never cross-match.
- *Why does the 30-day auto-close scheduler require `VERIFIED_BY_CASHIER` in addition to the amount/age
  thresholds?* So an unverified (possibly disputed or wrong) collection can't silently short-close a cheque
  just by sitting untouched for 30 days — the amount has to have actually been confirmed
  (`scheduler.py:147-158`).

---

## 12. Red Flags (claim-accuracy only)

- **GST rounding claim vs. what an interviewer will actually probe.** `e_invoice_service.py`'s
  `_derive_tax_from_inclusive_amount` is genuinely intricate — a candidate search across ROUND_HALF_UP/FLOOR/
  CEILING base values with ±0.01/±0.02 deltas until `taxable + tax == gross`. If the story leads with "I derived
  a GST-inclusive breakup that satisfies government rounding to the paise," be ready to explain *why* those
  specific three roundings and that specific delta search, not just that it works — this is the single most
  probeable piece of math in the whole feature. If that explanation isn't fluent, lead with the
  eligibility-gate/persistence-guarantee side of the same file instead (bullet-11-adjacent material: intrastate
  vs. interstate gating, never-null persistence fallback), which is more defensible as a stand-alone story.
- **"3 bounces in 3 months blocks new orders."** The closest matching code (`main.py:~3895-3925`) checks
  "≥2 bounced cheques in the last 90 days" and sets a `bad_pay_remaining` counter to 3 — not a direct
  3-strikes block, and the actual order-blocking decision appears to live in an external service this repo
  only calls (`order_blocking_base_url`). Before repeating "3 bounces / 3 months" as a precise number in an
  interview, either confirm that's genuinely how the counter is consumed downstream, or reframe the story
  around what's directly verifiable here: the CBM verify/recovery flow calls an unblock API for a store's
  cheques once they're marked recovered (`cashier_functions.py:651-706`, `functions/sales_officer.py`
  call sites into it).
- **Kafka consumer reliability.** If asked "what happens when message processing throws," the honest answer
  from the code is: the offset is committed anyway (`kafka_utils/consumer.py:130-138`), so the message is not
  retried — despite an in-line comment suggesting it shouldn't commit on failure. Don't claim guaranteed
  at-least-once/retry semantics for this consumer if pressed on it.
- **Scheduler defaults.** If asked for exact OCR-scheduler numbers, use what's in the code today:
  `batch_size=5`, `stuck_timeout_seconds=300` (not 1 / 120, which appear in some earlier internal notes on this
  feature) — `scheduler.py:204-205`.
- **NEFT budget module is shipped but not wired into CBM.** `neft_limits.py` is complete and tested, but its own
  docstring says wiring it into the CBM verification gate is "a separate change" not yet done
  (`neft_limits.py:37-39`; confirmed the CBM gate `_get_neft_verification_info` at
  `repositories/common.py:570` doesn't reference it). If asked "is this live," the accurate answer is
  "built and flagged off, not yet integrated into the CBM path."

---

## 13. Tech Stack Evidenced in This Code

- **Language/runtime**: Python, containers built on `python:3.8-slim` (main app, Streamlit tool) and
  `python:3.9-slim` (Kafka consumer).
- **Web framework**: Flask 2.3.2 + Flask-Cors 4.0.0, Blueprint-per-module routing (9 blueprints for CBM alone),
  `prometheus-flask-exporter` 0.23.1 for `/metrics`.
- **ORM / DB access**: SQLAlchemy 2.0.18 (declarative models + raw `text()` SQL for the hot bookkeeping paths),
  PyMySQL 1.1.0 driver, `mysql-connector-python` used directly in a couple of standalone scripts
  (`settlement_cron.py`, `merge_quid_stores.py`'s underlying `model.get_session_factory`). Datastore: MySQL
  (`cdms` schema, shared with a Node.js sibling service); MongoDB via `pymongo` 4.3.3 is imported in `main.py`
  for other parts of the monolith.
- **Auth/crypto**: PyJWT 2.7.0 (HS256 access tokens), stdlib `hashlib` SHA-512 + salt for OTP/PIN, `bcrypt`
  ≥4.0.0 for the Streamlit tool's login.
- **Validation**: `pydantic` (CBM request validators), `marshmallow` 3.20.1 elsewhere in the service.
- **Scheduling**: APScheduler 3.10.4 — `BackgroundScheduler` with both `CronTrigger` (daily/monthly jobs) and
  `IntervalTrigger` (polling workers).
- **Messaging**: `confluent-kafka` 2.3.0 (producer + consumer used here) and `kafka-python` 2.0.2 also pinned;
  WhatsApp Business via Wati (`[wati_api]`) and SMS/WhatsApp via Kaleyra (`[kaleyra]`), dispatched
  asynchronously off Kafka rather than inline in the request path.
- **OCR/CV**: `rapidocr-onnxruntime` ≥1.3.0 (ONNX runtime, CPU), OpenCV native libs installed at the container
  level (`libgl1`, `libglib2.0-0`, `libxcb1`, `libgomp1`), `numpy` ≥1.24.
- **Cloud**: AWS S3 (`boto3` 1.28.52/`botocore`) with presigned PUT/GET and Object Lock; ECS is the stated
  deployment target for the containerized services (Dockerfiles present; not independently verified against
  live AWS).
- **Observability**: `sentry-sdk` 1.35.0 (APM/error tracking), Prometheus scrape endpoint via
  `prometheus-flask-exporter`.
- **Testing**: `pytest` 7.4.0, ~584 test functions across the repo (see §9), DB-free stub-session unit tests for
  the pure-logic modules (`next_pdc_state`, `neft_limits` math, the e-invoice gate).
- **Internal tooling**: `streamlit` ≥1.28.0 (QUID-store-merge admin tool), `pandas` (both the merge tool and the
  `cbm_migration.py` Excel/CSV importer), `openpyxl` ≥3.1.2, `qrcode` 7.4.2.
- **Third-party integrations**: ClearTax (GST e-invoicing HTTP API), Wati and Kaleyra (WhatsApp/SMS).
- **Config/packaging**: `python-box` 7.0.1 + `toml` 0.10.2 (`Box(read_toml_file(...))` pattern throughout),
  `python-dotenv` in the standalone `transaction_flow_cron.py`; Docker for all deployable units.
