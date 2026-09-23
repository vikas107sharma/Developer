# All candidate resume bullets extracted from the codebases

_Every bullet the code analysis produced, grouped by area. 13 of these were selected for the resume;
the rest are here so you can swap any of them in. Each carries file:line evidence in its source analysis._


---

## Ripplr — IAM & RBAC

_Source: `code-analysis/iam-prd.md`_


> All verbs describe **design** unless implementation evidence is produced. Do not write "implemented",
> "shipped" or "delivered" until a repo, deployment or metric backs it. No invented numbers.

1. **Centralized IAM Architecture:** Architected a centralized identity, groups and permissions service
   consolidating nine divergent HS256 auth implementations across DMS and CDMS into one authoring point,
   while leaving every existing user table, user ID and FC scope untouched.
   *Evidence: PRD §1, §2.1, §3.1 / l.3–7, 90–146, 199–243.*

2. **Claims-Based RBAC at Redis Speed:** Modelled authorization as group IDs plus a catalog version in
   a ~210-byte token, resolved per request with a single SISMEMBER against a version-prefixed,
   group-keyed Redis catalog — zero SQL joins and zero IAM calls on the request path.
   *Evidence: PRD §4.1–4.2, §6.10 / l.557–622, 1341.*

3. **Zero-Downtime Token Passthrough:** Designed a token-minting layer issuing each estate's existing
   JWT shape, signed with that estate's own secret, for three audiences (dms, cdms, cdms_collections),
   so unmodified verifiers accept IAM tokens and estates cut over one at a time.
   *Evidence: PRD §3.5, §6.11 / l.416–461, 1409–1412.*

4. **Cross-Domain SSO:** Designed single sign-on across three frontends using an opaque, SHA-256-hashed
   `.ripplr.in` session cookie (12 h) decoupled from per-audience 1 h API tokens, enabling silent
   cross-estate token minting with no password re-prompt and no sticky sessions.
   *Evidence: PRD §3.6, §7.5–7.6 / l.463–536, 1609–1717.*

5. **Event-Driven Catalog Propagation:** Specified grant propagation MySQL → IAM Redis → per-estate
   Redis over a Kafka `iam.catalog.updated` topic, with last-flipped version pointers for atomic swaps
   and a 15-minute ETag reconcile covering at-least-once delivery gaps.
   *Evidence: PRD §4.2 / l.608–619, 673–713.*

6. **Fail-Closed Authorization:** Defined three distinct catalog failure modes — missing version key
   (503), Redis unreachable (last-known-good + alert), unknown group (deny + alert) — so infrastructure
   faults never degrade into allow-all or silent permission loss.
   *Evidence: PRD §4.2, §14, §15 / l.718–740, 2351–2353, 2417–2426.*

7. **Transactional Outbox Provisioning:** Introduced an outbox-backed provisioning worker for user
   creation spanning three databases via two remote HTTP writes, providing retry with exponential
   backoff and per-estate status ("DMS: provisioned / CDMS: failed") instead of half-created identities.
   *Evidence: PRD §7.8, §8.4 / l.1729–1777, 2039–2088.*

8. **Backward-Compatible Migration:** Planned a phase-in with a projection writer mirroring IAM grants
   into legacy `auth_group_permissions` / `r_auth_user_groups`, a nightly read-only drift job and a
   rollback flag, proving claim-derived and Django-derived permission sets equivalent before cutover.
   *Evidence: PRD §1.2, §4.4, §6.11, §15 / l.78–87, 787–804, 1343–1412, 2385–2388.*

9. **Credential Hardening:** Devised a lazy per-user re-salting scheme that retires a shared hardcoded
   pbkdf2 salt on each user's next login — preserving passwords and PINs unchanged while flagging
   never-upgraded accounts for forced reset.
   *Evidence: PRD §2.4, §10.2 / l.193–196, 2214–2232.*

10. **Permission Catalog as Source of Truth:** Established a typed permission catalog
    (model_perm | page | action) where grants reference permission IDs only, replacing ~140 DB-only
    Django codenames and a hardcoded ~60-key frontend role map with runtime-fetched, deploy-free
    permission changes.
    *Evidence: PRD §5.2, §7.3, §10.3 / l.850–895, 1572–1585, 2234–2254.*

---


---

## Ripplr — OBC Adjustment ingestion

_Source: `code-analysis/obc-adjustment.md`_


1. **Event-Driven Ingestion Pipeline:** Designed and shipped a brand-adjustment CSV/XLSX ingestion pipeline on S3 → Lambda → Kafka → ECS consumers → MySQL/MongoDB, processing each row as an independent Kafka message and SQL transaction so one bad row never blocks the file. Evidence: `filevalidator.py:131-135`; `adapter.py:1475-1541`; `processor.py:127,419`; `grn_consumer.py:80-85`.
2. **Config-Driven Multi-Brand Parsing:** Built a JSON-driven parser covering 14 brand codes (22 configs) with header detection, cleaning, mandatory-column checks, equality/numeric/OR filters, group-by aggregation, post-aggregation filters, type mapping and split-row expansion — new brands ship as config plus a fixture test. Evidence: `adapter.py:440-596,808-870,639-730,1185-1248`; `config/Ripplr/obc_adjustment/`.
3. **Idempotent Row-Level Dedup:** Engineered a normalised MD5 `unique_key_hash` (brand-prefixed, 2-dp numerics, case/whitespace-insensitive, type-aware for split rows) plus S3-etag file guard and within-file dedup, letting corrected files be re-uploaded without double-applying adjustments. Evidence: `adapter.py:154-162,549-551,1125-1183`; `processor.py:129-139`.
4. **Multi-Table Financial Transaction:** Implemented per-row business validation against live ledger state (invoice exists, RFC/allocation complete, threshold date, already-adjusted guards, tolerance floor) and a single-commit write across obc_adjustment_data, ChampOutstandingInvoices, collection_invoices, payments and audit tables. Evidence: `processor.py:148-190,234-419`.
5. **Salesman Assignment Consistency:** Propagated each adjustment to every uncollected salesman collection assignment and recorded an audit row per decrement, so field collectors see the adjusted outstanding rather than a stale value. Evidence: `processor.py:541-613,647-677`; `cdms_connect.py:106,187`.
6. **Double-Count Guard (Britannia):** Prevented re-applying credit notes already netted at invoicing by categorising credit notes by date versus invoice date before aggregation, summing pre-invoice totals per invoice, and comparing against `Orders.extra_info` in the processor. Evidence: `adapter.py:509-523,732-806`; `processor.py:812-916`; `constants.py:41-48`.
7. **Ledger-Safe Rounding Fix:** Root-caused a ₹1 over-collection at exact .50 fractions caused by rounding adjusted amount and resulting outstanding independently; reworked the write path to derive one `applied_amount` that drives every table. Evidence: `processor.py:248-260,353-358,400`; commit `8ccc3c8c8`.
8. **Bounded Settlement Rule and Audit Log:** Replaced an unbounded No Bill Back bypass that drove an invoice outstanding negative in production with a `-1 <= outstanding <= 0` settlement rule and a new short-close audit table written in the same transaction. Evidence: `processor.py:159-170,263-290,615-645`; `models.py:3463-3477`.
9. **Failure-Tolerant Completion Tracking:** Kept pre-validated failed rows flowing through Kafka with processor short-circuits and `$inc` counters so every file reaches fully_processed / partially_processed / processing_error, then flipped SQL status via Kafka with a UI-triggered self-heal. Evidence: `adapter.py:1484-1503,1576-1614`; `processor.py:110-121,997-1106`.
10. **Resilient Bulk Writes:** Batched MongoDB entry inserts (100 per `insert_many`, unordered) with error-code-aware retry that treats duplicate-key and validation errors as non-retryable and retries transient failures once. Evidence: `adapter.py:1368-1422`; `constants.py:54-59`.
11. **Per-Row Error Reporting:** Delivered operator-facing diagnostics — paginated summary API with counts, `/filestatus` Pass/Fail/In-Progress counters, and a downloadable error report that re-reads the original S3 file and annotates failed rows (CSV or XLSX). Evidence: `files.py:730-816`; `adapter.py:1547-1665`; `get_response_file.py:394-483`.
12. **Strict, Row-Isolated Date Handling:** Inferred the file's date format from the first parseable cell, parsed all rows with coercion and lenient fallback, and failed only the offending rows while enforcing a per-FC-brand go-live cutoff. Evidence: `adapter.py:872-917,1007-1055,1440-1473`.
13. **Authorisation and Feature Gating:** Enforced DB-driven permission checks (`upload_obc_adjustment` via group joins) and per-FC-brand enablement dates, and blocked the legacy OBC upload path once the adjustment feature is enabled for a brand. Evidence: `adapter.py:236-298`; `obc_adapter/adapter.py:401-452`.
14. **Test Suite With Static Guards:** Authored 253 unit and integration tests that stub infrastructure via `sys.modules`, run real brand configs against CSV fixtures, and assert pipeline ordering (filters → aggregation → post-filters) directly against the source. Evidence: `tests/test_adapter.py:19-74,206-241,254-282`; `tests/test_processor.py:32-98`.
15. **End-to-End Feature Wiring:** Wired every touchpoint across Lambda routing, two Kafka consumers, filestatus Lambda, listing/summary/error-report APIs, a Node batch report and React upload/report forms. Evidence: `filevalidator.py:131-135`; `grn_consumer.py:80-85`; `filecreate_consumer.py:49-50`; `wave_app.py:281-287`; `models.py:936-938`; `cdms/batch/report.js:~4060-4230`.

---


---

## Ripplr — Cheque Bounce Management

_Source: `code-analysis/ripplr-fin-cbm.md`_


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


---

## Ripplr — Field collections / salesman

_Source: `code-analysis/collections-salesman.md`_


1. **Eliminated a ~330-second full-table-scan query:** A correlated `SUM` subquery on an unindexed TEXT column ran once per result row on the invoice-list endpoint; replaced it with a single `GROUP BY`-batched query per page merged in application code, per the fix commit's own before-figure of "~330s."
   Evidence: `collections/src/controllers/invoice-handover/list-v2.js:325-360`; commit `12aa60a52`.

2. **Closed a live duplicate-payment race in a financial write path:** Root-caused a production incident to a non-atomic Redis `SET`+`EXPIRE` dedup check and replaced it with a single atomic `SET NX EX 60` claim, removing the window where two concurrent identical submissions could both pass.
   Evidence: `colections_v2/src/helpers/util.js:78-81`; `colections_v2/src/controllers/invoices/complete-create.js:252-281`; commit `93abfad88e`.

3. **Cut a transactional lock's hold time from ~30s to milliseconds:** Moved GPS/location validation and persistence off the main payment transaction onto its own short-lived connection, after identifying that the old in-transaction update held an X-lock on the invoice row for the life of the request.
   Evidence: `colections_v2/src/controllers/invoices/complete-create.js:337-395`; commit `93abfad88e`.

4. **Closed a silent financial-integrity gap in UPI auto-verification:** Discovered that UPI collections were being auto-verified by UTR match alone with no amount check, and added a 10-paise-tolerance comparison against the bank-statement feed that hard-fails a mismatch instead of accepting it.
   Evidence: `colections_v2/src/helpers/util.js:951-963`; commit `3c27483c8cb`.

5. **Replaced an unreliable frontend flag with a backend-derived invariant:** Traced a production invoice-status bug to trusting a client-supplied flag, then implemented a pure set-difference function over payment ids to detect dropped payments server-side, covered by 7 targeted unit tests.
   Evidence: `colections_v2/src/helpers/util.js:145`; `colections_v2/src/controllers/invoices/complete-create.js:603`; commit `78b7ce040`.

6. **Debugged a cashier-rejection permissions bug in two iterations:** Fixed cashier-rejected payments being locked alongside verified ones, then caught via a regression test that the first fix over-corrected and had started unlocking the salesman's own edits too — narrowed the condition and shipped a second fix two days later.
   Evidence: `colections_v2/src/helpers/collections.js:165-193`; `colections_v2/src/__tests__/test_salesman_edit_after_reject.js`; commits `2cd6e02f0`, `4872cdf11`.

7. **Implemented a statutory cash-transaction limit end-to-end:** Enforced Section 269ST of the Income Tax Act's cash ceiling across both the submit and preview endpoints, rewriting a store-level daily check that a code comment says was "inert," and adding a new per-invoice cumulative check, with a 183-line test suite.
   Evidence: `colections_v2/src/controllers/invoices/complete-create.js:91-119,451-470`; `colections_v2/src/helpers/collections.js`; commit `9dff451f0`.

8. **Built a cross-service financial ledger with deliberate index design:** Added `unverified_amount`/`cheque_pdc_amount` tracking spanning a new migration (2 tables, 5 indexes), a 347-line recompute helper run under row lock, and hooks in five endpoints, gated behind a feature flag; explicitly skipped one index after confirming an existing unique index already covered the join.
   Evidence: `cdms/migrations/20260714060000-champ-outstanding-unverified-pdc.js:127-231`; `colections_v2/src/helpers/outstanding_ledger.js:1-70`; commit `5fdcc134b`.

9. **Rewrote a correlated subquery into a derived-table JOIN:** Replaced a per-row `ORDER BY id DESC LIMIT 1` correlated subquery in an invoice-filter builder with a single `LEFT JOIN` against a `GROUP BY MAX(id)` derived table, alongside removing two other now-redundant subquery filters.
   Evidence: `collections/src/helpers/invoice_functions-v2.js` (`add_assigned_status_filter`); commit `77af874af`.

10. **Bounded a report endpoint's DB round-trips independent of result size:** Added payment-level detail to a collection-history endpoint via one `IN(...)`-batched query joined against `Banks`, keeping the endpoint at roughly two round trips regardless of how many historical rows are returned.
    Evidence: `collections/src/controllers/invoice-handover/list-v2.js` (`GET /collection-history`); commit `a482c9601`.

11. **Preserved OCR-linked cheque images across a destructive resubmit:** Re-stamped `scanned_cheques` records onto the new `master_payments` id after a resubmit deletes and recreates payment rows, since the resubmit payload carries only the stale master id, not the scan id needed to find the record.
    Evidence: `colections_v2/src/controllers/invoices/complete-create.js:1061-1120`; commits `b533fb327`, `c314fef7b`, `bbe8e97e8`.

12. **Fixed a misleading amortization error via edge-case detection:** Added detection for cash clamped by a per-invoice (not store-wide) limit so the amortizer surfaces the actual blocking constraint instead of a generic "amount exceeds outstanding" message, plus structured diagnostic logging on the zero-payment and exhausted-payment paths.
    Evidence: `colections_v2/src/helpers/amortize.js:19-22,38-43,139-159,251-258`.

13. **Added channel-based write restrictions to sensitive endpoints:** Built middleware that blocks the web-app channel from calling the collection-submit and invoice-list endpoints, restricting them to the mobile app, backed by a dedicated 107-line test file.
    Evidence: `colections_v2/src/middleware/block-web-app.js`; `colections_v2/src/__tests__/test_block_web_app.js`; commit `46a7c2ff2`.

14. **Owns the invoice-assignment engine's largest, most-tested surface:** Built the list/count/history and update endpoints segregators use to assign and reassign invoices to salesmen, including SQL `LIMIT`/`OFFSET` pagination and an array-of-queries atomic-transaction helper, backed by the service's two largest Jest suites (656 and 1321 lines).
    Evidence: `collections/src/controllers/invoice-handover/list-v2.js:139,207,547,614`; `update-v2.js:1081,1242`.

15. **Integrated WhatsApp OTP delivery around a misleading vendor API:** Wired OTP delivery through WATI's template-message API after establishing that it returns HTTP 200 even on rejection, gating success on an application-level `result` field rather than the transport status code.
    Evidence: `collections/src/helpers/whatsapp.js:13-40`.

---


---

## Ripplr — WhatsApp + GST e-invoicing

_Source: `code-analysis/whatsapp-notifications.md`_


1. **Paise-exact GST reconciliation for government e-invoicing:** Locked down a bounded Decimal-search reconciliation that turns a GST-inclusive gross amount into a taxable value + CGST/SGST split satisfying both the individual 9%/9% tax formulas and the total exactly, closing off the single-paisa rounding mismatches that get an e-invoice rejected by ClearTax/the government portal, with a parametrized test suite proving the invariant across gross values from ₹2 to ₹25,518.
Evidence: `v2/cheque_bounce_management/services/e_invoice_service.py:244-294`; invariant asserted in `v2/test_e_invoice_cgst_gate.py:240-251` (`cgst + sgst == total_tax`, `taxable + total_tax == gross`).

2. **Fixed a live ClearTax data-integrity incident (cheque 3879) with a progressive-fallback resolver:** Diagnosed a production bug where an exception inside the ClearTax call left `cbm_e_invoicing` rows with null tax values, then built a three-tier fallback (live ClearTax response → pre-call computed snapshot → derived from gross) guaranteeing the row is always financially consistent, and shipped a 24-case pytest suite proving the invariant.
Evidence: `v2/whatsapp_notification/repository.py:144-217`; regression named directly in `v2/test_e_invoice_cgst_gate.py:199-211`; commit `bf99125a7`.

3. **Designed the collection-notification eligibility engine from first principles:** Built the all-or-nothing verification check (a salesman-day is only "complete" once every invoice on it is cashier-verified) entirely in SQL/ORM aggregation, avoiding partial or duplicate payment-receipt notifications across a multi-day verification process.
Evidence: `v2/whatsapp_notification/repository.py:593-610` (`get_eligible_salesman_ids`), `:421-545` (`get_todays_verified_collections`).

4. **Built a Kafka-fed, DB-gated cron fallback that re-publishes into the same pipeline it's backing up:** Instead of a parallel send path, the fallback runs the identical eligibility query and re-injects the same signal shape into the same Kafka topic/key, so one consumer code path serves both the real-time and recovered cases.
Evidence: `v2/main.py:943-974`, `v2/whatsapp_notification/repository.py:613-704`, `v2/whatsapp_notification/whatsapp_cron.py`.

5. **Implemented the `NOT EXISTS`-based dedup that makes dual producers safe:** A cron sweep and a live Kafka event can both try to trigger the same notification; a `~exists()` subquery against successful log rows plus a pending-log-row-then-update lifecycle makes the database log, not the message broker, the actual coordination point.
Evidence: `v2/whatsapp_notification/repository.py:683-699` (query), `:1037-1095` + `:1368-1387` (pending/update pair).

6. **Wrote the retry-with-backoff layer that isolates WATI's flakiness from the send path:** A single reusable helper applies exponential backoff (3 attempts, 0.5s/1.0s, capped) across two structurally different response shapes (a WATI JSON body and a raw boto3 S3 response), so one upstream failure mode doesn't need its own bespoke handler.
Evidence: `v2/whatsapp_notification/helper.py:17-55`.

7. **Shipped a complete, four-endpoint retry/backfill API for the entire document pipeline:** Added independent retry endpoints for proforma generation, tax-invoice generation, ClearTax e-invoice generation, and the WhatsApp send itself, so any single stage of a cheque's document chain can be re-driven without replaying the original Kafka event.
Evidence: `v2/cheque_bounce_management/cbm_migration.py:254-650`; commit `680b595a` "create retry apis".

8. **Built the payment-receipt image generator with dynamic layout:** A PIL-based renderer that computes canvas height from the actual number of payment lines per invoice, lays out a running "Outstanding vs. Total collected" per invoice, and picks one of three closing messages (fully paid / partially paid / nothing collected) based on the aggregated totals.
Evidence: `v2/whatsapp_notification/functions.py:717-853`.

9. **Understood and can defend the incremental/idempotent partial-recovery logic for cheque bounce charges:** Recognized that a bounce charge can be recovered across multiple partial payments, requiring the invoicing logic to invoice only the *incremental* amount not yet covered by a successful e-invoice, with invoice-number collision handled by suffixing.
Evidence: `v2/cheque_bounce_management/functions/cashier_functions.py:1935-1987`.

10. **Traced and can explain the full ClearTax IRN/signed-QR integration**, including the defensive QR decoder that normalizes ClearTax's base64 encoding and falls back from "decode as image" to "re-render from raw text via the `qrcode` library" depending on which shape ClearTax actually returned.
Evidence: `v2/cheque_bounce_management/services/e_invoice_service.py:615-684`; API client in `v2/cheque_bounce_management/utils/cleartax_client.py:43-134`.

11. **Owns the original strategy-pattern dispatch design for the notification service:** Built `NotificationService.notify()`'s `STRATEGY_MAP`-driven dispatch so a new WhatsApp template requires only a new map entry and payload builder — no changes to the Kafka producer/consumer wiring.
Evidence: `v2/whatsapp_notification/notification_service.py:26-69`.

12. **Hardened a MySQL idle-connection failure mode specific to a long-lived Kafka consumer:** Diagnosed that the shared connection pool could return connections MySQL/NAT had silently dropped after ~350s of consumer idle time, and built a dedicated `pool_pre_ping` + `pool_recycle=300` session factory scoped only to that consumer path.
Evidence: `v2/whatsapp_notification/repository.py:47-67`.

13. **Identified and can speak to a live reliability gap of his own making:** Found that the Kafka consumer commits the offset on the exception path as well as the success path, meaning a processing failure is silently permanent with no DLQ — and that the cron-sweep fallback only covers half the template types.
Evidence: `v2/kafka_utils/consumer.py:130-138`.

14. **Found a redundant, dead strategy-dispatch implementation before it became a maintenance trap:** Identified that two independent strategy-map implementations exist for the same template-routing problem — one live, one with zero callers anywhere in the repo — the kind of latent bug where someone edits the dead copy expecting it to take effect.
Evidence: `v2/whatsapp_notification/functions.py:621-651` vs. `v2/whatsapp_notification/notification_service.py:27-48`; zero callers confirmed via repo-wide grep.

15. **Deployed a standalone Kafka consumer as its own container service** with an independent health endpoint for orchestrator liveness checks, decoupling notification delivery from the main API process.
Evidence: `v2/Dockerfile.consumer`, `v2/kafka_utils/consumer.py:44-58`.

*(Bullets 1, 2, 6, 9, 10, 12 lean hardest on material the current/old resume doesn't mention at all — GST reconciliation, the cheque-3879 fix, the retry-backoff abstraction, incremental invoicing, and the ClearTax/QR integration are all stronger and more specific than the existing "5 templates / 17K messages/day" framing.)*

---


---

## Ripplr — Report service + finService banking

_Source: `code-analysis/reports-and-finservice.md`_


1. **Outstanding-ledger report engine:** Owned `getOutstandingReport` end-to-end from its original build through a later "Actual OS" columns/breakdown extension, then raised its row cap from 100,000 to 300,000 after usage outgrew the original ceiling. Evidence: `report.js:4000-4156`, `:4084`; commits `d04005bbe`, `08a525118`, `f68c2b8c1`.
2. **Credit-adjustment/cash-discount reconciliation report:** Designed and shipped a standalone report handler with explicit date-range validation (rejects malformed, reversed, or >62-day ranges) and a typed adjustment-type formatter, delivered via S3. Evidence: `report.js:4158-4265`.
3. **GPS-based field-visit verification:** Built a geo-fencing check that compares a salesman's captured collection coordinates against a store's admin-verified KYC coordinates and flags collections outside a 500m radius, short-circuiting to "not verified" when the store itself lacks KYC approval. Evidence: `report.js:1206-1376`, distance calc at `:1282-1295`.
4. **Cheque-bounce recovery/ageing report:** Shipped an ageing model that counts days-since-bounce for open cheques but freezes the count at the resolution date once a cheque reaches a terminal state, with configurable ageing-range filters added in a follow-up iteration. Evidence: `report.js:480-739`; commits `82e6ae378`, `0b7cc1ef1`, `b7af84c46`.
5. **Cross-report shared library, "invoice missing" tracking:** Extracted a reusable query-builder module (`invoiceMissingJoins`/`invoiceMissingSelects`/`mapInvoiceMissingColumns`) and wired it into three independently-owned report handlers without touching the other 90%+ of code in two of them, backed by a 128-line `node --test` suite. Evidence: `lib/invoiceMissing.js` (91 lines, 100% own), used at `report.js:285,304,1436,1459,4061,4081`.
6. **Diagnosed and fixed a silent timezone bug** in that same module: a UTC datetime string (from `mysql2`'s `dateStrings:true`) was being parsed in the batch host's local timezone instead of as UTC, corrupting a displayed timestamp; fixed by parsing explicitly as UTC before converting to IST, with a test that pins `process.env.TZ` so the regression can't hide on a different machine. Evidence: `lib/invoiceMissing.js:21-29`; commit `0a695e840`.
7. **Salesman self-service reporting:** Added two new report types (detail export and its GPS companion) end-to-end — dispatcher wiring, query, XLSX generation, S3 delivery, status callback — for a feature that shipped across two pull requests. Evidence: `report.js:1026-1376`; commits `ff0244d4f`, `ac054443e` (PRs #1209, #1574).
8. **Store-visit compliance report**, including a later correction to an overly-strict `is_active` filter that was silently excluding relevant stores from results. Evidence: `report.js:3334-3439`; commit `8ee9e6734`.
9. **Extended a shared, single-process batch pipeline six separate times** (cbm recovery, salesman detail, salesman GPS, store visit, outstanding, credit-adjustment) by following its existing contract — dispatcher branch, independent `try/catch`, S3 upload, status/error callback — without needing to modify the pipeline's queue-claiming or locking code shared by the other 13 report types. Evidence: `report.js:129-172` (his 6 branches), plus each handler above.
10. **Landed targeted correctness fixes inside handlers he doesn't own outright** — e.g., a delivery-side row-exclusion filter and null-safe reason handling inside the `collection_detail`/`salesmen_detail` query paths — without needing to take on the surrounding 200+ lines of someone else's function. Evidence: `report.js:1252`; commits `5d0e4e756`, `2b9871d25`.


---

## Supertails — Promise Engine (EDD)

_Source: `code-analysis/promise-engine-edd.md`_


**1. Architected a multi-tier delivery-promise engine:** Designed and built the EDD computation service running as both a single-SKU and a shipment-aware cart engine, resolving warehouse serviceability through a four-level geographic fallback (lat/lng → pincode → city → state) before any buffer or cutoff logic runs.
Evidence: controllers/functions/ControlTower/cartEddV2ControlTower.js:244-543

**2. Engineered a cross-cluster over-allocation guard:** Built a global warehouse-allocation tracker that follows a SKU across all four search levels so the same physical warehouse can never be double-promised when it serves more than one cluster simultaneously.
Evidence: controllers/functions/ControlTower/cartEddV2ControlTower.js:265,607-626

**3. Designed partial-fulfillment logic for split shipments:** Implemented quantity-level allocation letting one SKU's order quantity divide across multiple warehouses/clusters when no single location can fulfil it alone, carrying remaining quantity forward through each search level.
Evidence: controllers/functions/ControlTower/cartEddV2ControlTower.js:578-680,300-411

**4. Built a unit-level weight bin-packer for shipment consolidation:** Wrote a streaming packer that groups cart items into shipments per cluster-warehouse, splitting mid-SKU by individual unit weight whenever a warehouse's configured maximum shipment weight would be exceeded.
Evidence: controllers/functions/ControlTower/cartEddV2ControlTower.js:707-955,958-1012

**5. Modeled an 8-stage configurable buffer pipeline:** Designed the buffer/cutoff computation order — cutoff, static (cluster/warehouse/cluster-warehouse scoped), weather-driven, capacity, tag, SLA, pickup day-skip, delivery day-skip — each independently tunable through relational config rather than code changes.
Evidence: controllers/functions/ControlTower/cartEddV2ControlTower.js:1659-2359

**6. Integrated a real-time weather buffer without double-counting:** Added logic that injects a rain-driven delivery buffer only when no manually configured static buffer already exists for a warehouse, preventing the two buffer sources from stacking on one promise.
Evidence: control-tower/src/utils/rainBufferEdd.js:54-100

**7. Hardened cutoff handling against day-skip corruption:** Diagnosed and fixed a bug where a day-skip buffer advanced the delivery date but left a stale time-of-day; added a warehouse-cutoff-time reset that re-anchors the clock after every pickup/delivery day-skip.
Evidence: utils/eddDaySkip.js:1-19; controllers/functions/ControlTower/cartEddV2ControlTower.js:2213-2221,2352-2358

**8. Designed a 29-model relational configuration engine (Control Tower):** Modeled cutoffs, static/capacity/tag buffers, cluster-to-warehouse SLA matrices, day-skips, and a full rain-buffer subsystem as versioned Sequelize models with weight/area/time-window scoping, replacing an earlier key-value global-config system.
Evidence: control-tower/src/models/index.js:4-32,119-150; controllers/functions/eddcartV2.js:304-353

**9. Exposed a 174-endpoint configuration API surface:** Built the Control Tower's route layer spanning clusters, warehouses, cutoffs, buffers, capacity, polygons, H3 indexing, bulk upload, rate-limit config, and audit logging across 17 route modules, backed by generated Swagger documentation.
Evidence: control-tower/src/routes/ (17 files, 174 routes); control-tower/src/config/swagger.js

**10. Orchestrated H3 hexagonal geospatial resolution for delivery zones:** Implemented lat/lng-to-serviceability-cluster resolution using Uber's H3 indexing library against stored polygon boundaries, with cached results feeding directly into cart-EDD warehouse search.
Evidence: control-tower/src/services/H3IndexingService.js:161-262; utils/eddCache.js:154-159

**11. Built a fail-open, multi-layer caching strategy for a latency-sensitive read path:** Wrapped every control-tower and inventory lookup in a Redis cache with per-data-type TTLs, deliberately excluding capacity and tag buffers to keep real-time fields fresh, with every cache path falling back to direct DB reads on Redis failure.
Evidence: utils/eddCache.js:41-183

**12. Implemented an atomic Redis token-bucket rate limiter:** Designed a per-IP/per-endpoint/per-method rate limiter using a single Lua script for atomic refill-and-consume, driven by a database-configurable endpoint allowlist cached for 30 days, with a non-atomic fallback path when Lua execution is unavailable.
Evidence: utils/tokenBucket.js:109-201; middleware/dbRateLimiter.js:75-214

**13. Ran two EDD engines and a response-shape adapter in production simultaneously:** Maintained a legacy config-driven EDD engine and a newer Control-Tower-driven engine behind separate route prefixes, plus a dedicated shim that calls the new engine and remaps its response into the legacy contract for callers that had not migrated.
Evidence: controllers/EddMapping.controller.js:1-68; server.js:60-82

**14. Optimized warehouse-allocation lookups by reusing the EDD calculation path:** Added an early-return branch inside the shared single-EDD calculator so a dedicated warehouse-allocation endpoint reuses the full allocation/shipment pipeline while skipping the buffer/cutoff work it doesn't need.
Evidence: controllers/functions/ControlTower/cartEddV2ControlTower.js:1714-1716,161-220

**15. Designed SKU-sanitization for promotional/bundle variants:** Built suffix-stripping logic (CMD, REW, 23NE, FG, BXGY, WBOGO, BBB25, SALE, and a specific GIFT SKU) so promotional SKU variants resolve to the same base inventory row without duplicating master data per variant.
Evidence: controllers/functions/ControlTower/cartEddV2ControlTower.js:1330-1345

---


---

## Supertails — Realtime inventory sync

_Source: `code-analysis/promise-engine-inventory.md`_


1. **Realtime Inventory Webhook:** Designed and shipped an authenticated ERP→Promise-Engine inventory webhook that validates payloads, publishes them to Google Cloud Pub/Sub and acknowledges with HTTP 202 plus the message ID, decoupling ERP request latency from MySQL write time.
   Evidence: `cronjob/cronjobERPInv.js:331-408`; `GCP/inventoryPublisher.js:10-30`; `cronjob/cronjob.controller.js:94-97`.
2. **Delta Clobber Fix:** Diagnosed and fixed a silent data-corruption bug where realtime deltas zeroed unrelated SKUs' warehouse stock, distinguishing "warehouse absent from delta" from "genuinely zero" and preserving untouched columns while keeping snapshot semantics unchanged.
   Evidence: `cronjob/cronjobERPInv.js:128-133, 166-206` (commit `a6c40b0`).
3. **Async Subscriber with Ack/Nack:** Built the in-process Pub/Sub subscriber (flow control `maxMessages=1`) that adapts deltas to the shared writer, surfaces unmapped warehouses, and acks/nacks explicitly for at-least-once processing.
   Evidence: `GCP/inventorySubscriber.js:11-70`; `server.js:101`.
4. **Payload-Semantics Gating:** Introduced a caller `source` tag so one writer safely serves full-snapshot crons and partial webhook deltas, skipping item-master weight updates on deltas.
   Evidence: `cronjob/cronjobERPInv.js:117, 132-133, 233-256`; `GCP/inventorySubscriber.js:56` (commits `12e1260`, `dd0168d`).
5. **Paginated Cron Endpoint:** Added a single-page ERP inventory endpoint enabling per-page scheduler fan-out and isolated reprocessing, acknowledging with 200 on failure to prevent scheduler retry storms.
   Evidence: `cronjob/cronjobERPInv.js:410-439`; `cronjob/cronjob.controller.js:77-92`.
6. **Environment-Isolated Messaging:** Moved Pub/Sub topic and subscription names to environment variables with fail-fast startup checks after staging and production consumers were found sharing one subscription.
   Evidence: `GCP/inventoryPublisher.js:11-14`; `GCP/inventorySubscriber.js:16-20` (commit `a1e7a24`).
7. **Warehouse-Mapping Cache:** Reduced per-run database reads by caching the ERP→UC warehouse mapping in Redis with a 1-hour TTL, DB fallback, and non-blocking cache writes.
   Evidence: `cronjob/cronjobERPInv.js:11-48`.
8. **Timing-Safe Webhook Auth:** Secured the webhook with a shared-secret header verified by constant-time comparison, returning distinct 500/401/400/200/202 statuses for misconfiguration, auth failure, invalid payload, nothing-queued, and queued.
   Evidence: `cronjob/cronjobERPInv.js:323-329, 336-402`.
9. **Write-Path Observability:** Instrumented the writer with pre-write per-SKU logs, `affectedRows` confirmation, skip-reason logs, and a "real zero vs defaulted zero" diagnostic, making a webhook traceable end-to-end by Pub/Sub message ID.
   Evidence: `cronjob/cronjobERPInv.js:152, 179-190, 200-204, 224, 236-239, 259-273`; `GCP/inventorySubscriber.js:30, 49-53, 58, 61`.
10. **Structured Error Serialization:** Corrected a malformed Loggly error field by adding a serializer that captures message and stack for `Error` objects and JSON for plain objects.
    Evidence: `utils/loggly.js:35-42, 51` (commit `5d195a4`).
11. **Data Hygiene Filter:** Filtered ERP items with SKU codes over 45 characters before bulk inserts on both cron and webhook paths, keeping malformed item codes out of inventory writes.
    Evidence: `cronjob/cronjobERPInv.js:308, 358-359, 426` (commit `1f0353d`).
12. **Cart-EDD Enhancements:** Extended the cart delivery-date engine with gift/sample SKU allocation to the earliest-EDD warehouse, weekday/DBD day-skip handling, SBD-aware pickup cutoffs, IST-anchored slot times, and a formatted delivery message.
    Evidence: `controllers/functions/eddcartV2.js` (commits `5ffd56c`, `eeffa68`, `4e021d0`, `eff8d92`, `dae3ca9`, `83f66c6`); `controllers/functions/eddFunctions.js` (created in `eeffa68`).

Optional (label as unmerged if used): **Recently-Updated Delta Cron:** Prototyped a time-windowed ERP "recently updated" delta cron reusing the delta gate with a guarded fetch sentinel. Evidence: commit `0a7a06b` on `feat/erp-recently-updated-inventory-sync` (not on production).

---


---

## Supertails — Post-order write + read

_Source: `code-analysis/supertails-post-order.md`_


Ordered by resume relevance. Each cites file:line evidence; for shared files, only mechanisms with direct evidence of his authorship are claimed.

1. **Backend-for-frontend order-aggregation gateway:** Built the server-side response-composition layer powering `/post-order/*`, fanning out to Shopify GraphQL, MongoDB, four MySQL tables, and Returns/Pharmacy/Pricing services to assemble one consistent customer response across six app/web route variants with per-client fee shapes.
   Evidence: `order/Functions/postOrderFunctions.js:243-1119`, `order/post.order.controller.js:1-224`.

2. **Placeholder-shipment reconciliation system:** Designed and shipped an idempotent mechanism keeping exactly one "held item" shipment row per order for SKUs the promise engine can't plan, using a sorted quantity fingerprint to avoid redundant writes and emptying rather than deleting the row so positional array-index matching elsewhere stays intact.
   Evidence: `webhook/postOrder/completeOrder/placeholderShipment.js:1-185` (sole-authored), wired into `eddActions.js:397,404` and `deliveryNoteWebhook.js:1112-1123`.

3. **Returns handling without double-counting:** Built the shipment-reformatting step that reduces outbound quantity across every matching Shopify line-item instance while constructing the corresponding return-shipment record exactly once per return request, specifically handling Shopify's habit of repeating one line item across multiple fulfilments on a split order.
   Evidence: `order/Functions/postOrderFunctions.js:1531-1807` (`processShipmentsQcV3`), esp. `:1542-1543`, `:1566`, `:1568-1578`.

4. **Proportional COD-allocation engine:** Engineered the algorithm splitting a COD order's item value and fees across however many shipments it becomes, using a fixed whole-order denominator so a shipment's collectable amount never shifts as later fulfilments appear, and deriving one of the three displayed figures from the other two so they always sum exactly.
   Evidence: `order/Functions/shipmentCodAllocation.js:1-234` (sole-authored), esp. `:108`, `:141-161`, `:170`.

5. **Shipment-matching correctness fix in ERP delivery-note reconciliation:** Diagnosed and fixed a collision in the delivery-note↔shipment matching step where duplicate `shipmentId`s (created when a webhook redelivery appends shipments) could let a delivery note silently update the wrong parcel; replaced the lookup key with MongoDB's own unique `_id`.
   Evidence: `webhook/deliveryNote/deliveryNoteWebhook.js:602-606`, `:679-682`.

6. **Positional, dedup-safe courier-tracking writes:** Own the MongoDB update path translating ClickPost webhooks into shipment state — targets exactly one shipment via positional `arrayFilters` on delivery-note number, prepends new tracking-history entries, and dedups on a `waybill-statusCode-timestamp` key via a pre-write existence check.
   Evidence: `repository/order-management-repository.js:21-157`, esp. `:72-76`, `:87`, `:108-144`.

7. **N+1-safe multi-source read pipeline:** Eliminated per-order query fan-out on the order-list and order-details reads by collecting every order ID or waybill across the whole batch first, then issuing exactly one downstream query per data source for the entire page.
   Evidence: `order/Functions/postOrderFunctions.js:75-83`, `:715-738`.

8. **Domain status-translation layer:** Built the chain turning raw courier status codes, Shopify fulfilment state, and delay calculations into single customer-facing sentences ("Arriving by Tomorrow 10PM⚡️", "Missed delivery on Wed, 4th Sep"), including a quick-commerce-specific remap of three otherwise-generic failure codes to one "Delivery failed" state.
   Evidence: `order/Functions/postOrderFunctions.js:1205-1414`, `:1815-1956`.

9. **Cross-consumer regression suite without a mocking framework:** Wrote 29 categorized regression tests proving the placeholder-shipment invariant holds consistently across five independent consumers — COD splitting, referral-reward delivery status, refund evidence, the tracking tile, and the shipment-detail read path — using direct `require.cache` substitution since the repo ships no Jest/Mocha/Sinon.
   Evidence: `test/placeholder-shipment.test.js:1-1028` (sole-authored).

10. **Idempotent, SKU-triggered support automation:** Shipped a fire-and-forget handler that opens a formatted Nugget support ticket whenever a specific SKU appears on a confirmed order, deduplicated through the same event-occurrence log used elsewhere in the write path so a webhook replay never double-files a ticket.
    Evidence: `webhook/postOrder/paidTcbTicket.js:1-106` (sole-authored), wired at `webhook/webhook.controller.js:323-329`.

11. **Write-once audit trail for a mutable Shopify attribute:** Designed a metafield pair separating an immutable order-creation snapshot from a live-refreshed "latest EDD" value, plus a merge-not-replace write helper, so Shopify's destructive whole-attribute-list update semantics can no longer erase either the audit history or unrelated order attributes.
    Evidence: `helperFunctions/consignmentMetafield.js:1-255`, called from `webhook/deliveryNote/deliveryNoteWebhook.js:934-946`.

12. **Multi-signal cancellability engine:** Implemented order/shipment cancellability as a conjunction of four independent signals — existing Shopify fulfilment, quick-commerce delivery type with any tracking status, imminent superfast delivery, and service-only line items — recomputed consistently across three separate read endpoints.
    Evidence: `order/Functions/postOrderFunctions.js:121-134`, `:270-280`, `:745-772`.

13. **Backward-compatible API evolution for pricing rollout:** Built the response-shape switch letting the order-details endpoint serve either dynamic, pricing-service-driven fee titles or the legacy fixed fee triplet from one code path, gated on a client-supplied rollout marker, so older app builds keep working unmodified during a live pricing migration.
    Evidence: `order/Functions/postOrderFunctions.js:182-211`.

14. **Shopify GraphQL query layer for the v3 read side:** Own the hand-built, cursor-paginated GraphQL query surface (order list, order detail, shipment-by-AWB) that the entire post-order read pipeline is built on, including the quick-commerce-specific query variants it consumes today.
    Evidence: `graphQL/ordersV2.js:1-1253`, consumed at `order/Functions/postOrderFunctions.js:66,106,297,521`.

15. **Migrated the customer order-tracking tile off MySQL onto the Mongo-based pipeline:** Added a MongoDB-backed version of the in-app tracking-tile feature that reuses the existing multi-source formatter instead of duplicating its logic, and added mismatched-shipment filtering so a tombstoned or placeholder row can't keep a delivered order's tile alive.
    Evidence: `order/Functions/GetOrderTrackingTileData.js:186-253` (`GetOrderTrackingTileDataV3`), `:412-417`.

---


---

## MyDesignation — BFF

_Source: `code-analysis/mydesignation.md`_


Ordered by resume relevance. No invented numbers — every figure is quoted or arithmetically derived from a cited source.

1. **Engineered exactly-once order creation across a payment/webhook race condition:** modeled each checkout attempt as a single Postgres row claimed via a conditional `UPDATE` whose affected-row count decides the winner, backed by `UNIQUE` payment/order columns and a hand-written partial index that makes a COD double-tap a safe no-op.
Evidence: `src/modules/payments/payment-order.repository.ts:148-162,71-80`; `src/modules/payments/payments.service.ts:565-680`

2. **Took webhook processing off the request-response path:** verified Razorpay/Shopify/ClickPost signatures against the raw request bytes, logged every delivery before the auth gate for forensics, then enqueued to SQS and returned 200 in single-digit milliseconds — reserving a 5xx for the one case that actually needs a retry, the enqueue call itself failing.
Evidence: `src/modules/webhooks/webhooks.controller.ts:78-117,129-140,158-228`

3. **Designed the SQS consumer's settlement contract from first principles:** explicit delete-on-success / leave-for-redelivery-on-throw semantics on a standard (non-FIFO) queue, proved safe by making both downstream processors idempotent and order-tolerant rather than paying for ordering guarantees they didn't need.
Evidence: `src/infrastructure/queue/sqs.queue.ts:45-225`; `src/modules/webhooks/webhook-processor.ts:24-83`

4. **Built a race-free identity ledger for passwordless login across four providers:** a database unique constraint, not a read-then-write check, decides attach-vs-block for phone/email OTP, Google, and Apple sign-in, with one narrow, audited exception letting a genuine OTP reclaim a phone number Google's People API only guessed at.
Evidence: `src/modules/auth/identity-resolver.service.ts:31-94`; `src/modules/auth/strategies/`

5. **Hardened session security with rotation-on-use and blast-radius containment:** refresh tokens persist only as SHA-256 hashes, rotate on every use, and a replayed (already-consumed) token revokes every token in its family, not just itself.
Evidence: `src/modules/auth/session.service.ts:19-97`; `src/modules/auth/access-token.ts:36-59`

6. **Built a two-layer stampede guard for a shared Redis cache:** in-process request coalescing collapses every concurrent miss in one container into a single loader call, and a cross-container `SET NX` lock keeps only one container hitting Shopify when a hot key expires while the rest briefly wait on its result.
Evidence: `src/infrastructure/cache/redis.ts:36,73-160`

7. **Closed a null-caching outage at the architecture level instead of the call site:** after a transient upstream failure got cached as "no data" for a full TTL, rewrote the shared cache helper so a null/undefined loader result can never be written to Redis by *any* caller, by construction, rather than trusting each call site to remember the rule.
Evidence: `src/infrastructure/cache/redis.ts:67-71,141-143`; `src/gateways/kiwi/kiwi.gateway.ts:58-64`

8. **Replaced per-key deletes with a version-counter invalidation scheme, and swept the rest with non-blocking `SCAN`/`UNLINK`:** one write bumps a counter to orphan an entire cached family at once, while webhook-driven catalog purges use a cursor-based scan instead of a blocking `KEYS` sweep that would stall every cart/OTP/session read on the shared instance.
Evidence: `src/infrastructure/cache/redis.ts:170-186,243-260`

9. **Wrote the resilient HTTP client every outbound gateway shares:** per-upstream timeout and retry budgets with full-jitter exponential backoff, retrying only 5xx/network failures, and a deliberate zero-retry policy on the one call — Razorpay order creation — where a blind retry could mint a duplicate charge.
Evidence: `src/infrastructure/http/resilient-client.ts:16-77`; `src/shared/constants/index.ts:297-344`

10. **Cut roughly 2.4 seconds off a cold product-page load** (~1.4s + ~1s, per the code's own comment) by pulling two live third-party calls off the request entirely, and kept Shopify's cost-based GraphQL limit from becoming a bottleneck by batching bundle-product lookups into chunked `nodes(ids:)` calls instead of one round trip per item.
Evidence: `src/modules/product/product.service.ts:33-52`; `src/gateways/shopify/shopify.gateway.ts:621-651`

11. **Split every security control into fail-open or fail-closed by design, not by accident:** rate limiters and OTP gates degrade open so a Redis outage never locks out real customers, while webhook signature checks and the admin cache-purge endpoint refuse outright the moment their secret is unconfigured.
Evidence: `src/middleware/rate-limit.ts:43-64`; `src/modules/webhooks/webhooks.controller.ts:82-86`; `src/modules/admin/admin-cache.service.ts:32-55`

12. **Migrated the async queue and image storage off Azure onto AWS SQS and S3** behind the same producer/consumer and storage interfaces the rest of the app already coded against, shipping the swap with zero endpoint, request, or response-shape changes for the mobile app.
Evidence: `src/infrastructure/queue/sqs.queue.ts:1-45`; `src/gateways/s3/s3.gateway.ts:1-30`; `docs/2026-08-01.md`

13. **Chose hand-applied DDL over an ORM migration tool for a payments schema** so a partial unique index inexpressible in Prisma could guard against a double-submitted COD order — every schema change ships with its own pre-deploy gate query and post-deploy smoke test instead of relying on a migration runner's assumptions about the target database.
Evidence: `prisma.config.ts:9-21`; `prisma/sql/001-zero-payable-store-credit.sql:14-32,107-115`; `prisma/sql/002-app-address-meta.sql:36-89`

14. **Ran a six-profile k6 load-testing program directly against production infrastructure**, covering expected peak, 5× peak, and a sudden 3× spike, to quantify p95 latency per user journey, sustained throughput, and the cache stampede guard's behavior under a cold-key thundering herd instead of estimating capacity.
Evidence: `perf/k6/profiles/` (`load.js`, `stress.js`, `spike.js`, `cart-stress.js`); `docs/MyDesignation-Performance-Security-Report.md`

15. **Reverse-engineered the store's GST tax computation from live order data and reproduced it exactly**, including a one-paisa rounding artifact that independent per-line rounding produces on intra-state orders, so app-created orders file the same CGST/SGST/IGST split as every other Shopify sales channel.
Evidence: `src/core/gst.ts:1-37`

---

