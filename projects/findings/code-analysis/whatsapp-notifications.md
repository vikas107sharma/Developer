# Ripplr WhatsApp Notification Service — Code-Derived Analysis

Repo: `/Users/vikas1141sharma/Developer/ripplr copy/Ripplr-fin/ripplr-fin` (bitbucket `RIPPLR-ADMIN/ripplr-fin`, branch `main` at analysis time).
Subject: Vikas Sharma (git identities `vikas7312sharma`, `Vikas sharma`, email `vikas.sharma@infinitelocus.com`).
Scope note: this is his codebase; the document below focuses entirely on the engineering itself — architecture, mechanisms, numbers, resume bullets, and interview material — rather than on version-control archaeology.

No secrets are reproduced anywhere below. `.config.toml` contains live AWS keys, a WATI bearer token, a ClearTax auth token, and a JWT/OTP salt — their existence and config-section names are noted; values are not.

---

## 1. Ownership

This is his codebase, covered end to end below: the Kafka topic/consumer, the strategy-dispatch skeleton, the collection eligibility engine and cron-sweep fallback, the notification-log coordination, the ClearTax GST e-invoicing integration, document generation, and S3 upload. One practical interview-prep note rather than an ownership claim: the GST paise-exact reconciliation and the ClearTax/proforma image rendering are exactly the kind of mechanism a strong interviewer probes with live follow-ups ("why `ROUND_CEILING` here," "walk me through your first version of this") — know those code paths cold before leaning on them, the same way you would for any code you're about to be questioned on.

---

## 2. Architecture

```
Cashier verifies payment / cheque bounces / bounce charge recovered / auto-close job
        │
        ▼
Kafka producer (kafka_producer.push_to_kafka) ──► topic "whatsapp_notification" (key = template type)
        │
        ▼
Consumer group "whatsapp-consumer-group"  (kafka_utils/consumer.py, confluent-kafka)
        │
        ├─ key ∈ {payment_image_final, no_payment_image_final} ─► send_collection_message()
        ├─ key = cheque_bounce                                  ─► send_cheque_bounce_message()
        ├─ key ∈ {charge_collection, zero_charges}               ─► send_charge_collection_message()
        └─ key = auto_close_invoice                              ─► process_auto_close_invoice_for_cheque() (bypasses NotificationService)
        │
        ▼
NotificationService.notify(template_type, data)  — STRATEGY_MAP dispatch (notification_service.py:27-69)
        │
        ├─ type=collection ─► WhatsappPayloadBuilder.payment_received/no_payment_received ─► ImageProvider.generate_invoice_image (PIL) ─► S3
        └─ type=cheque      ─► WhatsappPayloadBuilder.cheque_bounce/charge_collected/zero_charges
                                   ├─ proforma path  ─► generate_and_save_proforma_invoice_url ─► ImageProvider.generate_proforma_invoice_image ─► S3
                                   └─ tax-invoice path ─► EInvoiceService.generate_e_invoice() ─► ClearTax API (IRN + SignedQRCode)
                                                             ─► save_qr_code() (decode/re-render QR) ─► S3
                                                             ─► generate_and_save_tax_invoice_url ─► ImageProvider.generate_tax_invoice_image (PIL, IRN+QR overlay) ─► S3
        │
        ▼
retry_with_backoff(WatiClient.send_template_message)  ─► WATI BSP (WhatsApp Business API)
        │
        ▼
WhatsappNotificationLogs / cbm_e_invoicing (+ cgst_sgst_values) — outcome persisted
```

External systems: **Kafka** (confluent-kafka client, `requirements.txt:58`), **WATI** (`wati_api.url` in `.config.toml`, e.g. `live-mt-server.wati.io/<tenant>`), **ClearTax** e-invoice API (`cleartax_client.py:35-38`, headers `X-Cleartax-Auth-Token` / `X-Cleartax-Product: Einvoice`), **AWS S3** (boto3, `functions.py:1826`, `download_cheque_pdf.py:242`), **MySQL** (SQLAlchemy 2.0 + PyMySQL, RDS host in `[mysqlConnection]`).

Two independent template-dispatch tables exist for the same purpose: `NotificationService.STRATEGY_MAP` (`notification_service.py:27-48`, actually used) and `WhatsappPayloadBuilder.build()`'s internal `dispatch_map` (`functions.py:639-645`, verified via repo-wide grep to have **zero callers** — dead code). See Section 12.

---

## 3. Producers / consumer / cron / APIs

**Consumer** — `kafka_utils/consumer.py:61-151`. Single long-running thread (`consumer_thread`), plus a Flask healthcheck (`/healthcheck/consumer`, port 8005) on a daemon thread (`consumer.py:47-58`). Config: `auto.offset.reset=earliest`, `acks=all`, `group.id=whatsapp-consumer-group` (`consumer.py:33-40`). Polls every 100ms (`consumer.poll(0.1)`, line 80); routes by message key against `WhatsappNotificationTemplateType` values (lines 94-124); on any successful branch, commits asynchronously and then **sleeps 1 second** (lines 130-133) — see Section 7 for the throughput implication. On exception, logs and **still commits** (lines 135-138) — see Section 8/12.

**Producers** (all publish to topic `"whatsapp_notification"`):
- `POST /cheque-bounce/push-to-kafka` — cheque bounce, payload `{"cheque_id"}` (`main.py:420-468`).
- `POST /cheque-bounce/charge-collection/push-to-kafka` — charge collection, payload `{"cheque_id"}` (`main.py:471-506`).
- `GET /v2/send-whatsapp-notification` (`@verify_secret`) — the cron-sweep producer, described below (`main.py:943-974`, his).
- `scheduler.py:104-116` — auto-close job pushes `{"cheque_id"}` per eligible cheque, key `auto_close_invoice`.
- Additional cheque-bounce/reversal push sites exist per the prior survey; not re-verified in this pass given the scope pivot.

**Cron sweep** — `whatsapp_cron.py` (17 lines, entirely his) is a standalone script that does a bare `GET` against `/v2/send-whatsapp-notification` with a static `X-Secret-Key` header (value not reproduced). It is meant to be invoked on a schedule (crontab/ECS scheduled task — not visible from this repo). The endpoint it hits (`main.py:943-974`, entirely his) calls `get_remaining_collections()` (the same eligibility query the event path would eventually satisfy), then **re-publishes to Kafka** — one message per eligible salesman-day, payload `{"collected_person_id": salesman_id, "collection_date": "YYYY-MM-DD"}` (`main.py:955-964`). This is a precise, code-confirmed detail: the fallback does not call WATI directly — it re-injects the identical signal shape into the same topic/key, so it is served by the same consumer code path as the real-time event.

**Document retry APIs** — `cbm_migration.py`, blueprint `cbm_migration_bp`, all four routes 100% his (`680b595a`, "create retry apis"):
- `POST /proforma-generation` (`cbm_migration.py:254-363`) — regenerate proforma image(s) by cheque ID, optional `force_update`.
- `POST /tax-invoice-generation` (`:364-473`) — same for the GST tax-invoice image.
- `POST /e-invoice-generation` (`:474-575`) — re-drive the ClearTax e-invoice call itself.
- `POST /whatsapp-notification` (`:576-650`) — retry the WATI send.

This is a genuinely complete, self-contained ops feature: every stage of the document pipeline (image render, ClearTax call, WhatsApp send) can be independently re-triggered for a cheque without touching the primary Kafka path.

---

## 4. Database

Four tables specific to this service (found via `class ... __tablename__` grep in `model.py`, so this count is exhaustive for this repo):

**`whatsapp_notification_logs`** (`model.py:5638-5654`) — the collection/cheque notification-log table.
- `entity_type` (nullable string), `entity_id` (**`nullable=False, unique=True`** — a single global uniqueness constraint across all entity types; see Section 12), `wati_id`, `store_id`, `template_name`, `s3_url`, `status` (`Enum('pending','success','failed','sent')`, **indexed**, `model.py:5648`), timestamps.
- Written by `insert_collection_notification_logs` (`repository.py:1037-1095`, his) as `status="pending"` rows *before* the WATI call, then by `update_collection_notification_logs` (`:1368-1387`, his) with the final status *after* the call — the "pending row before, update after" pattern.
- Cheque-side logging (`insert_cheque_notification_log`, `:1319-1367`) instead does a single post-hoc insert with the final status already known — no separate pending phase, because the cheque flows have no cron-sweep race to coordinate against.

**`cbm_e_invoicing`** (`model.py:5775-5803`) — one row per e-invoice *attempt* per cheque (docstring confirms multiple rows are expected). Columns: `proforma_invoice_number`, `tax_invoice_number`, `bounce_charges_collected`, `taxable_value`/`tax_amount` (**both `nullable=False`** — the never-zero invariant his test suite enforces), `tax_type` (`Enum('CGST_SGST','IGST')`), `irn`, `qr_code_url`, `cleartax_response` (JSON). Children `cbm_cgst_sgst_values` / `cbm_igst_values` (`:5753-5772`) hold the per-rate breakdown, 1:1, cascade-deleted with the parent.
- `cbm_cheques.proforma_invoice_url` / `.tax_invoice_url` (`model.py:5747-5748`) cache the last-generated image URL so repeat sends reuse it (`functions.py:311-321`, `repository.py:1445-1447`) instead of re-rendering.

**The collection eligibility query** (`get_remaining_collections`, `repository.py:613-704`, his) — the mechanism his interview story calls "one eligibility query":
```python
~exists().where(and_(
    WhatsappNotificationLogs.entity_id == CollectionInvoice.id,
    WhatsappNotificationLogs.entity_type == 'invoice',
    WhatsappNotificationLogs.status.in_(["success", "sent"])
))
```
combined with a `HAVING count(invoices) == count(invoices WHERE verification_status='VerifiedByCashier')` (`:695-699`) — a salesman-day is eligible only when every invoice for that salesman on that date is cashier-verified *and* no invoice in the set already has a successful log row. This is a real `NOT EXISTS` (SQLAlchemy `~exists()` compiles to `NOT (EXISTS (...))`), confirmed by reading the compiled query structure, not just the docstring.

**Transactions**: each repository function opens its own `with Session() as session: ... session.commit()` block (context-manager scoped); no cross-request transaction spans the Kafka consume + DB write + WATI call — a crash between DB commit and WATI send is possible in principle but is exactly what the pending/update log split is designed to make visible (a stuck `"pending"` row is the observable symptom).

**Dedicated DMS session factory** (`repository.py:47-67`, his) — a second SQLAlchemy engine with `pool_pre_ping=True`, `pool_recycle=300` built lazily only for the long-lived DMS Kafka consumer path, to survive a MySQL/NAT idle-connection timeout (~350s) that a normal pooled connection would hit. Good defensive-infra instinct, cited with its own reasoning comment in the code.

---

## 5. Async / distributed

- **Topic**: `whatsapp_notification` (single topic, keyed by template type — used as a coarse routing key, not a partition key contract that's ever inspected).
- **Consumer group**: `whatsapp-consumer-group` (`consumer.py:39`).
- **Commit semantics**: `consumer.commit(message=msg, asynchronous=True)` on both the success path (`:132`) and — this is the known bug — the exception path (`:138`), immediately below a comment that says the opposite (`# ❌ don't commit here if you want retries`, `:137`) and was never acted on. Net effect: **every message is committed exactly once regardless of processing outcome**; a failure is logged and then permanently forgotten from Kafka's perspective.
- **Retries**: only inside `retry_with_backoff` (`helper.py:17-55`, his) — 3 attempts, sleeping `min(0.5 × 2^(attempt-1), 3)` between attempts (0.5s, then 1.0s; the 3s cap is unreachable at the default `retries=3` — it would only bind at `retries≥5`). This retries the *WATI call itself*, not Kafka redelivery.
- **Idempotency / dedup**: two layers. (1) DB-level: the `NOT EXISTS ... status IN (success, sent)` gate (Section 4) means re-processing the same salesman-day is a no-op once a log row is marked successful. (2) Document-level, for partial cheque recovery: `_generate_and_process_e_invoice` (`cashier_functions.py:1914-2099`) computes `incremental_bounce_gross = current_bounce_gross − SUM(bounce_charges_collected WHERE irn IS NOT NULL)` and skips generation entirely when the increment is ≤ ₹1.00 (`:1958-1966`), preventing double-invoicing across multiple partial recoveries of the same cheque. Invoice-number collisions are avoided by counting prior ClearTax attempts matching the same base pattern and suffixing (`TAX-2026-3879`, `TAX-2026-3879-1`, …, `:1972-1987`).
- **Failure recovery**: the cron sweep (`whatsapp_cron.py` → `main.py:943-974` → `get_remaining_collections`) is the *only* recovery path, and it only covers collection notifications. There is no DLQ and no cheque-side equivalent — a cheque-bounce or charge-collection message that throws inside the consumer is gone for good (this is exactly the bug the subject volunteers in his own interview prep notes at `/Users/vikas1141sharma/Developement/Developer/projects/phase1/whatsapp_notification`, Step 5, and it matches the code precisely).

---

## 6. Infrastructure

- **Container**: `v2/Dockerfile.consumer` — `FROM python:3.9-slim`, installs `requirements.txt`, `EXPOSE 8005`, `CMD ["python", "kafka_utils/consumer.py"]`. `PYTHONUNBUFFERED=1` so logs stream immediately (important for a process whose only observability is stdout logging).
- **Config**: `.config.toml` (Box/tomllib-parsed via `model.read_toml_file`), sections confirmed present: `[wati_api]`, `[cleartax]`, `[aws]`, `[s3]`, `[kafkaConnections]`, `[mysqlConnection]` (+ `.master`/`.stage`), `[challan]` (PDF branding), `[sentry]`. ClearTax additionally supports env-var override (`CLEARTAX_URL`, `CLEARTAX_TOKEN`, env takes priority — `cleartax_client.py:24-25`).
- **Healthcheck**: `/healthcheck/consumer` on the same port the container exposes, served from a daemon thread separate from the poll loop — a standard container-orchestrator liveness probe pattern (ECS/K8s), though the orchestration layer itself isn't visible from this repo.
- **Storage**: AWS S3 for every generated artifact (payment-receipt PNG, proforma PNG, tax-invoice PNG, decoded QR PNG) — all via `boto3.client("s3", ...)` constructed per-call rather than a shared client.

---

## 7. Reliability + performance mechanisms (with evidence)

1. **Exponential backoff with a cap**, isolating WATI flakiness from the rest of the pipeline — `helper.py:17-55`. Success is judged either by HTTP 200 or, for the S3-shaped dict case, `ResponseMetadata.HTTPStatusCode==200`, or WATI's own `result: true` — one retry helper reused for both an HTTP client and an S3 boto3 call.
2. **Self-throttled consumer**: `time.sleep(1)` after every successful commit (`consumer.py:133`) puts a hard ceiling of **~86,400 messages/day** on a single consumer instance, independent of Kafka lag. This is the one piece of code-derivable math relevant to a "17K+ messages/day" throughput claim — see Section 9.
3. **Idle-connection defense**: `pool_pre_ping=True` + `pool_recycle=300` on the DMS-only session factory (`repository.py:58-67`), specifically to avoid `(2013, 'Lost connection during query')` after the consumer sits idle past MySQL's ~350s NAT timeout.
4. **Paise-exact GST reconciliation**: given a GST-inclusive gross amount, the government e-invoice portal validates CGST/SGST independently *and* the total; naive `gross / 1.18` rounding can miss by ₹0.01. The fix (`e_invoice_service.py:244-294`, mirrored in `repository.py:69-141`) builds three rounding candidates (`ROUND_HALF_UP`/`ROUND_FLOOR`/`ROUND_CEILING`) × five deltas (`0, ±0.01, ±0.02`) — up to 15 candidate taxable values — and accepts the first one where `taxable + tax == gross` exactly, with a deterministic fallback if none match. A 24-case pytest suite (`test_e_invoice_cgst_gate.py:240-251`) locks its invariants down: `cgst + sgst == total_tax` and `taxable + total_tax == gross` for every gross value tested.
5. **Never-null persistence invariant**: `_resolve_einvoice_persist_values` (`repository.py:154-217`, his) guarantees `cbm_e_invoicing.taxable_value`/`tax_amount` are always populated — from the live ClearTax response, else a pre-call computed snapshot, else derived from the gross amount — so a ClearTax outage never produces a row with null/zero tax fields (the `cheque_id=3879` incident this fixes, per `test_e_invoice_cgst_gate.py:199-211`).
6. **Defensive QR decoding**: `save_qr_code` (`e_invoice_service.py:615-684`) normalizes ClearTax's base64 (strips a `data:` URI prefix, fixes URL-safe `-`/`_` alternates, repairs missing `=` padding), then tries to decode it as an already-rendered image; if `PIL.UnidentifiedImageError` is raised, it instead treats the payload as raw QR *text* and re-renders a QR code locally via the `qrcode` library. Handles two different real-world ClearTax response shapes with one function.
7. **Incremental/idempotent partial recovery** and **invoice-number collision avoidance** — Section 5.
8. **Existing-artifact reuse**: proforma/tax-invoice URLs are cached on `cbm_cheques` and only regenerated on `force_update`/`force_regenerate` (`repository.py:1445-1447, 1611`), avoiding redundant S3 writes and PIL renders on repeat sends.

---

## 8. Design decisions, trade-offs, alternatives, known bugs

- **Event-as-signal vs. event-as-payload** (his design, collection path): the Kafka message carries only `{"collected_person_id", "collection_date"}` (`main.py:955-964`) or `{"cheque_id"}` — never invoice IDs or amounts. Verified directly in the producer code, not just inferred. Trade-off: every consumed message costs a DB round-trip to re-derive eligibility, but it eliminates a whole class of race bugs where a payload computed at publish-time goes stale by consume-time (cashier verification is asynchronous and multi-day per `get_eligible_salesman_ids`, `repository.py:593-610`). The alternative (embed the invoice list in the event) would be faster per-message but reintroduces exactly the "partial verification" bug the design note in his interview prep calls out.
- **Cron sweep as the only failure-recovery mechanism, and only for collections**: a legitimate, working design for the collection flow (same eligibility query, re-published through the same topic) but structurally asymmetric — nothing plays the same role for `cheque_bounce`/`charge_collection`/`zero_charges`. This is a real architectural gap, not a hypothetical one.
- **No DLQ**: `consumer.commit()` runs on both the success and exception paths (`consumer.py:132,138`). A comment sitting directly above the offending line (`# ❌ don't commit here if you want retries`, `consumer.py:137`) already flags this as wrong, yet the commit call beneath it was never changed. Whether a DLQ is *worth adding* is a legitimate trade-off discussion (see Section 11) rather than an obvious yes.
- **Strategy pattern, applied twice**: `NotificationService.STRATEGY_MAP` (used) and `WhatsappPayloadBuilder.build()`'s `dispatch_map` (unused, zero callers — Section 2/12) implement the same idea independently. Extending the system by template type genuinely is a one-line `STRATEGY_MAP` addition plus a new builder — the design goal is real — but the duplicate, dead implementation suggests the pattern was implemented twice, in two different files, without the second copy ever being wired up.
- **IGST disabled by design**: `tax_type` is hard-pinned to `"CGST_SGST"` for all new rows (`repository.py:167`, `get_cbm_cheque_bounce_data` comment at `:953-954`) even though the schema and `EInvoiceConstants` still support IGST — a deliberate simplification (all counterparties are presumably intrastate in practice) rather than a genuine interstate tax computation.
- **Fixed vs. dynamic GST**: the proforma invoice for the flat ₹500 bounce charge uses **hardcoded** constants (`PROFORMA_TAX_AMOUNT=76.24`, `PROFORMA_TAXABLE_VALUE=423.33`, `constants.py:481-484`) rather than running the decimal search, because ₹500 is fixed and its breakdown never changes; the *tax invoice* (actual recovered amount, which varies with partial payments) is where the dynamic paise-exact search is actually needed. This split is a sensible, evidence-backed design choice, not an inconsistency.

---

## 9. Numbers

**(a) Derivable from code, with source:**
- 5 templates wired end-to-end through `STRATEGY_MAP` (`notification_service.py:27-47`); 7 enum values total, 2 unwired into that map (`constants.py:262-268`).
- 4 independent document-retry endpoints (`cbm_migration.py`), all his.
- 4 DB tables specific to this service (`model.py` — exhaustive `__tablename__` grep).
- Retry policy: 3 attempts, backoff 0.5s → 1.0s, 3s cap (unreachable at default retry count) (`helper.py:17-55`).
- Consumer self-throttle: 1 explicit second of sleep per successfully committed message (`consumer.py:133`) ⇒ a **hard architectural ceiling of ~86,400 messages/day per running consumer instance**, before accounting for per-message DB/S3/HTTP latency. A claimed rate of "17K+ messages/day" is comfortably inside that ceiling (≈1 message every 5 seconds on average) — i.e., architecturally plausible — but the 17K figure itself does not appear anywhere in this codebase (no logs, no metrics, no comments), and cannot be derived, only bounded.
- GST decimal search checks up to 15 candidate values per calculation (3 roundings × 5 deltas) (`e_invoice_service.py:253-259`).
- 24 test cases (17 test functions, 2 parametrized ×5 and ×4) in `test_e_invoice_cgst_gate.py`, all passing-by-construction unit tests (DB-free, stub sessions) — his.
- Service has 72 commits touching `v2/whatsapp_notification/` between 2025-08-13 and 2026-09-02 (`git log --oneline -- v2/whatsapp_notification`).
- `CHEQUE_BOUNCE_REVERSAL` (`constants.py:266`) has no producer or consumer anywhere in this repo (repo-wide grep) — contradicts the "produced but unwired" framing this task started from; it appears fully unused here (possibly wired in a different repo/service not in scope).

**(b) Missing metrics — exact questions to ask, and which bullet each strengthens:**
1. "How many WhatsApp notifications does this service actually send per day/month in production (from WATI's dashboard or your own metrics/CloudWatch), and over what measurement window?" — needed to support any "N messages/day" resume claim; the only thing code proves is a ~86K/day ceiling per instance.
2. "How many consumer instances/replicas run in production, and is the topic partitioned (so multiple consumers actually parallelize), or does everything funnel through one instance?" — without this, the throughput ceiling in 9(a) is a single-instance number, not a system number.
3. "Do you have an incident ticket or Slack thread for the `cheque_id=3879` ClearTax failure?" — would let the "fixed a production bug" bullet cite a real date/impact instead of just the code evidence.
4. "How often does the cron sweep actually catch something the event path missed — do you have logs/counts of sweep-recovered notifications vs. event-path notifications?" — would quantify the value of the fallback design rather than describing it qualitatively.
5. "Roughly how many cheques per month go through the bounce → proforma → recovery → tax-invoice chain?" — would size the retry-API and document-generation work in section 10.
6. "Is there a metrics/alerting system (Sentry is a dependency — `requirements.txt:40`) actually wired up for this service's failures, or just available in the codebase?" — affects how confidently "observability" can be claimed.

---

## 10. Candidate resume bullets

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

## 11. Interview material

**Hard problems (3-5), with technically accurate answers:**

1. *"Walk me through how you'd generate a GST-compliant invoice for a fixed, tax-inclusive amount without violating the portal's rounding rules."* — Answer: derive an approximate taxable value via `gross / (1+rate)`, round it three ways (half-up/floor/ceiling), then probe a small neighborhood (±0.01, ±0.02) of each candidate; for each, compute CGST/SGST at 9% independently (rounded to 2dp) and check `taxable + cgst + sgst == gross` exactly; return the first match; fall back to a deterministic best-effort split if none match. This bounds an otherwise open-ended rounding search to ≤15 checks and guarantees termination. (`e_invoice_service.py:244-294`)

2. *"Two independent triggers — a live event and a cron sweep — can both try to send the same notification. How do you guarantee exactly-once delivery without a distributed lock?"* — Answer: don't coordinate the producers directly; make the *database* the lock. A pending log row is written before the send attempt; the eligibility query for both paths excludes anything with an existing successful row (`NOT EXISTS ... status IN (success, sent)`); whichever path's send finishes first "wins" and the other's next eligibility check simply returns nothing. (`repository.py:613-704`, `1037-1095`, `1368-1387`)

3. *"A message throws inside your consumer. What actually happens to it, and why is that a problem?"* — Answer: it's logged and the offset is committed anyway (`consumer.py:135-138`), so Kafka considers it fully processed; there is no DLQ, so the message and its side effects (a WhatsApp notification, a document) are permanently lost from that code path. The collection flow has a structural safety net (the cron sweep re-derives eligibility from DB state, independent of the lost message); the cheque flows do not, so a lost `cheque_bounce` or `charge_collection` message is unrecoverable without a manual retry via the `cbm_migration.py` endpoints.

4. *"A cheque bounce charge gets partially recovered over three separate payments. How do you avoid invoicing the same money twice?"* — Answer: don't invoice the payment event, invoice the *delta*. Compute `current_bounce_gross` from the cheque's current `collected_amount − cheque_amount`, subtract the sum of `bounce_charges_collected` from all prior e-invoices that actually succeeded (`irn IS NOT NULL`), and only generate a new e-invoice if that remainder exceeds a ₹1 noise threshold. (`cashier_functions.py:1935-1966`)

5. *"Why carry only a salesman ID and a date in the Kafka event instead of the invoice IDs that changed?"* — Answer: cashier verification is asynchronous and can span multiple days per salesman; if the event carried a payload computed at publish time, a race between two verification events for the same salesman-day could send a receipt showing an incomplete outstanding balance, or send two receipts. Treating the event as a pure signal and re-deriving eligibility from current DB state at consume time makes the query itself the source of truth, and makes the design naturally idempotent against replay.

**Follow-up questions (required + additional), with accurate answers:**

- **"Which design patterns does the notification system use?"** — Strategy pattern: `NotificationService.STRATEGY_MAP` maps a template-type key to a `{type, payload_builder}` strategy, so `notify()` doesn't need per-template conditionals (`notification_service.py:27-69`). (Note, if asked to go deeper: a second, unused Strategy implementation exists in `WhatsappPayloadBuilder.build()`'s `dispatch_map` — worth mentioning proactively as "we actually have this twice, and one copy is dead code," which reads as more self-aware than pretending it doesn't exist.) Arguably a light Facade in `NotificationService` itself (one `notify()` entry point hiding WATI/S3/DB details from the consumer), and a Template-Method flavor in the four nearly-identical `WhatsappPayloadBuilder.*` builders. Not a formal Factory — the dispatch maps are plain dicts, not a factory class.
- **"Do we really need a DLQ here?"** — Defensible "it depends" answer: for the collection flow, arguably *not urgently* — the cron sweep already re-derives eligibility from DB state on a schedule, so a lost event is self-healing within one sweep interval. For the cheque flows, yes — there is currently zero recovery path, so a DLQ (or, cheaper, extending the sweep pattern to cheques by re-scanning `cbm_cheques`/`ChequeBounceDetail` for un-notified rows) would close a real gap. The cheaper fix that doesn't require new infrastructure: stop committing on the exception path at all and let Kafka's own redelivery-on-no-commit handle transient failures, reserving a DLQ for poison messages that fail repeatedly.
- **"What happens if ClearTax is down when a tax invoice needs generating?"** — The call fails, `_resolve_einvoice_persist_values` still derives and persists taxable/tax values from the gross amount so the row is never left null, `irn`/`qr_code_url`/`cleartax_response` stay null, and the `/e-invoice-generation` retry endpoint can re-drive it later once ClearTax is back.
- **"Why is IGST support still in the schema if it's disabled?"** — Backward compatibility / hedge: the tables and constants still model IGST, but `tax_type` is pinned to `CGST_SGST` for all new rows (`repository.py:167`), so it's a soft feature flag rather than a code path that would need a schema migration to re-enable.
- **"How would you add a sixth WhatsApp template?"** — Add the enum value, a new `WhatsappPayloadBuilder` method, and one `STRATEGY_MAP` entry; no consumer or producer changes needed unless the new template needs a new Kafka key routing branch in `consumer.py`'s if/elif chain (which is itself a minor design wart — the consumer's routing and the strategy map are two separate places that both need to know about a template).
- **"What's the actual message-processing throughput ceiling, and why?"** — `time.sleep(1)` after every commit caps a single consumer instance at roughly one message per second — ~86,400/day — regardless of Kafka lag; real throughput is lower once DB/S3/WATI latency per message is added.

---

## 12. Red flags

1. **The consumer commits on failure** (`consumer.py:135-138`) — a comment directly above the line (`:137`) already says not to do this, and it's still there. This is the single most concrete, fixable reliability bug in the service.
2. **No DLQ, asymmetric recovery** — the cron sweep only exists for collection notifications; cheque-side messages that fail have no recovery path at all.
3. **`whatsapp_notification_logs.entity_id` is globally `unique=True`** with no compound uniqueness against `entity_type` (`model.py:5643`) — an invoice ID and a cheque ID are drawn from different sequences but share one ID space in this table; if they ever overlap numerically, inserting a log row for one would collide with an existing row for the other. Worth a real check against production data before calling it safe.
4. **Two parallel strategy-dispatch implementations**, one entirely dead (`functions.py:621-651`, zero callers) — low risk today, but a maintenance trap if someone edits the unused copy expecting it to take effect.
5. **The consumer's `time.sleep(1)`** is a blunt, undocumented throughput throttle with no comment explaining why it's there — worth understanding (rate-limiting WATI? avoiding tight-loop CPU spin?) before an interviewer asks and gets a shrug.
6. **`CHEQUE_BOUNCE_REVERSAL`** is defined (`constants.py:266`) but has no producer or consumer anywhere in this repository — either dead, or wired in a system outside this repo; worth confirming which before mentioning it as a "wired" template.
7. **The "17K+ messages/day" resume claim is not falsifiable from this codebase** — it's architecturally plausible (well under the ~86K/day single-instance ceiling) but not measured anywhere in logs, metrics, or code. Don't present it as code-derived.
8. **Live secrets in `.config.toml`** — AWS access key/secret, a WATI bearer token, a ClearTax auth token, and a JWT/OTP salt all sit in plaintext config in this repo checkout. Not this task's to fix, but worth flagging to whoever owns secret rotation if this checkout is at all shared.

---

## 13. Tech stack evidenced in this code

Versions below are read directly from `v2/requirements.txt` and `v2/Dockerfile.consumer`; "used by this service" is confirmed by an actual `import` in one of the files this analysis covers, not just presence in the shared requirements file (this repo is a monolith — `v2/requirements.txt` covers the whole Flask app, not only the notification service).

**Language / runtime**
- Python 3.9 (`Dockerfile.consumer:2`, `FROM python:3.9-slim`).

**Web framework**
- Flask 2.3.2 — the healthcheck app in the consumer container (`consumer.py:46-50`) and the producer endpoints in `main.py`. Flask-Cors 4.0.0 also present at the app level.

**Messaging**
- confluent-kafka 2.3.0 — actual import in `kafka_utils/consumer.py:3` (`from confluent_kafka import Consumer`); this is the client library the consumer runs on.
- kafka-python 2.0.2 is also in `requirements.txt` but is not imported anywhere in the files this analysis covers — likely used by the producer-side `kafka_producer` helper elsewhere in the app, not confirmed in this pass.

**Database / ORM**
- SQLAlchemy 2.0.18 (`repository.py`, `model.py` — declarative `Base`, `Session`, `exists()`, `case()`).
- PyMySQL 1.1.0 as the MySQL DB-API driver; `mysql-connector-python` also present in requirements (redundant driver, not confirmed which one is active at the engine-creation call in this pass).
- MySQL (AWS RDS — `[mysqlConnection]` host is an `*.rds.amazonaws.com` endpoint in `.config.toml`).

**Object storage**
- AWS S3 via boto3 1.28.52 / botocore 1.31.52 / s3transfer 0.6.2 — every generated image (payment receipt, proforma, tax invoice, decoded QR) is uploaded through a per-call `boto3.client("s3", ...)` (`functions.py:1826-1852`, `download_cheque_pdf.py:242-260`).

**Document / image generation**
- Pillow (`Pillow>=10.0.0`) — `PIL.Image`, `ImageDraw`, `ImageFont` drive every WhatsApp-bound document as a rendered PNG, not a true PDF (`functions.py`).
- qrcode 7.4.2 — local QR re-rendering when ClearTax returns raw QR text instead of an image (`e_invoice_service.py:661-670`).
- fpdf2 2.7.5 — used only for the unrelated bank-challan PDF (`download_cheque_pdf.py`), not the WhatsApp notification documents.

**HTTP / external APIs**
- requests 2.31.0 — the only HTTP client used against both WATI (`helper.py`) and ClearTax (`cleartax_client.py:70-75`); no retry/backoff library (e.g. `urllib3.Retry`, `tenacity`) is used — backoff is hand-rolled (`helper.py:17-55`).

**Config / serialization**
- python-box 7.0.1 + `toml`/`tomli` — `.config.toml` is parsed into an attribute-accessible `Box` (`model.read_toml_file`, used throughout `helper.py`, `cleartax_client.py`, `functions.py`).
- marshmallow 3.20.1 — request schema validation (`schemas.py`), not in the notification path itself but in the same Flask app.

**Scheduling**
- APScheduler 3.10.4 — drives `scheduler.py`'s in-process jobs, including the auto-close-invoice Kafka producer (`scheduler.py:104-116`). The collection-notification cron sweep (`whatsapp_cron.py`) is a separate, external-cron-invoked script, not APScheduler-managed.

**Testing**
- pytest 7.4.0 — `test_e_invoice_cgst_gate.py` (DB-free, `SimpleNamespace`/dict test doubles, no live DB or network dependency), plus several other `test_*.py` files at the `v2/` root for adjacent features.

**Observability**
- sentry-sdk 1.35.0 and prometheus-flask-exporter 0.23.1 are both dependencies of the wider app (`[sentry]` section present in `.config.toml`); this service's own error handling is otherwise plain `logging` (module-level loggers in every file, e.g. `consumer.py:22-25`, `helper.py:7-15`) — no structured/JSON logging, no correlation IDs tying a Kafka message to its eventual WATI call across log lines.

**Auth (adjacent, not in this service directly)**
- PyJWT 2.7.0, bcrypt — used by the wider Flask app's auth layer, not by the notification pipeline itself.

**Not part of this service** (present in `requirements.txt` for other parts of the monorepo — noted so they aren't mistakenly attributed to this pipeline): `rapidocr-onnxruntime`/`numpy` (cheque-image OCR feature), `streamlit` (an internal tool), `pymongo`/`mmh3`/`faker` (unrelated data tooling).
