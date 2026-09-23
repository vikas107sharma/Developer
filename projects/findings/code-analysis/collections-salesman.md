# CDMS `collections` — salesman collection, rejection/resubmission, amortization, UPI auto-verify

Repo: `/Users/vikas1141sharma/Developer/ripplr copy/CDMS/cdms-one` — packages `collections/` (v1, `salesman-app-api`) and `colections_v2/` (v2, the actively-developed line). Cross-repo touchpoints: `cdms/migrations` + `cdms/src/models` (a sibling Sequelize/TypeScript service in the same monorepo) and `upi/` (a sibling Python service). Read-only analysis; no app run, no DB/CloudWatch touched, no secrets printed (`.env` files exist in both packages — contents not read beyond confirming presence).

**Note on Section 1:** per the requester's direction mid-task, this section is kept short and does not gate anything below it. All bullets in Section 10 are backed by commits authored under `vikas7312sharma <vikas.sharma@infinitelocus.com>` (verified via `git log`/`git show` before this direction was given). A small number of foundational primitives that the six claimed mechanisms sit on top of — the base amortization priority-walk, the per-invoice settle/bill-back decision functions in `payment_methods.js`, the `master_payments` state-machine guards, and the base UPI-match skeleton — predate his commits in this area and are shared with other engineers on the service. That distinction isn't a credit dispute; it matters only so an interview follow-up on the base algorithm doesn't land somewhere he hasn't actually touched. Where the write-up below describes "his" endpoint or file, it means he is the top committer of record on that specific file/route.

---

## 1. Ownership map (brief)

| Component | Path | Verdict |
|---|---|---|
| `/complete` submit+resubmit endpoint, Redis dedup wiring, GPS/txn restructuring, 269ST enforcement, payments_deleted derivation, scanned-cheque re-stamp | `colections_v2/src/controllers/invoices/complete-create.js` | His — top committer, and the specific commits cited in §10 are individually his |
| UPI amount-tolerance check | `colections_v2/src/helpers/util.js:951-963` | His (single dated commit, diff verified) |
| Cashier-reject reopen logic (`isPaymentReopenable`/`isInvoiceLockedByCashier`) | `colections_v2/src/helpers/collections.js:165-193` | His (two dated commits, diff verified) |
| Cash-limit-clamp edge case + telemetry in amortizer | `colections_v2/src/helpers/amortize.js:19-22,38-43,85-92,139-159,251-258` | His |
| Actual-OS unverified/PDC ledger (migration, indexes, helper) | `cdms/migrations/20260714060000-champ-outstanding-unverified-pdc.js`, `colections_v2/src/helpers/outstanding_ledger.js` | His |
| Invoice-handover list/count/history + update (assignment engine) | `collections/src/controllers/invoice-handover/{list-v2,update-v2}.js` | His |
| WhatsApp OTP (WATI) | `collections/src/helpers/whatsapp.js` | His |
| `blockWebApp` middleware | `colections_v2/src/middleware/block-web-app.js` | His |
| Base amortization priority loop, per-invoice settle/bill-back decisions | `colections_v2/src/helpers/{amortize.js core loop, payment_methods.js}` | Predates his changes; shared service code he extends |
| `master_payments` versioning guards, EDITAMOUNT/EDITDATA state-machine enforcement | `colections_v2/src/helpers/util.js:~2255-2510` | Predates his changes; shared service code |
| Base UPI bank-statement match + release-on-removal | `colections_v2/src/helpers/util.js:~895-960`, `colections_v2/src/controllers/invoices/clear.js` | Predates his changes; his addition is the amount-tolerance guard layered on it |

---

## 2. Architecture, components, data flows, external systems

`collections`/`colections_v2` is an Express 4 monolith (CommonJS) that is the salesman-facing collection API for a FMCG-distribution back office. Two live copies of the service exist side by side in the same monorepo:

- **`collections/` (v1)** — mounts 17 route groups under `/api/v4/*` (`src/routes.js:90-172`) plus one `/api/v2` group (`src/v2_routes.js`). Runs either as a Lambda behind API Gateway (`src/lambda.js` + `@vendia/serverless-express`, `sam-template.yaml`: nodejs12.x/1024MB/30s) or as a long-running process (`app.local.js`) on ECS/PM2, deployed via `bitbucket-pipelines.yml` (SSH + `git pull` + `pm2 restart`).
- **`colections_v2/` (v2, the "blockedit" line)** — same domain, rebuilt: `routes.js` + `v2_routes.js` mount the same shape of route groups but with newer implementations (`complete-create.js`, `complete-update.js`, `collections.js`, `outstanding_ledger.js`). This is where essentially all of the story's six claimed mechanisms actually live, and where his highest-signal, most recent commits are concentrated.

**Data flow for a collection submission:** mobile app (salesman) → `POST /complete` (`complete-create.js:228`) → Redis dedup claim → GPS/location validation (separate short-lived connection) → begin DB transaction → validate payload against `complete_create_schema` → `amortize()` walks invoices in Cash→UPI→Cheque→NEFT priority (`amortize.js`) → per-invoice settle/bill-back/reject decided by `payment_methods.js` → `master_payments` rows written (old rows `is_deleted=1`, new rows carry `parent_id`) via `util.js` (`create_/update_payments_master_entries`) → UPI rows cross-checked against `bank_statement_api` with a 10-paise tolerance → outstanding ledger recomputed under row lock (`outstanding_ledger.js`, feature-flagged) → response.

**External systems touched:** MySQL (`ChampOutstandingInvoices`, `collection_invoices`, `master_payments`, `payments`, `bank_statement_api`, `upi_payments`, `cheque_suspense`, `champ_outstanding_suspense_logs`, `scanned_cheques`), Redis (idempotency lock), WATI (WhatsApp Business API, OTP), AWS S3 (`colections_v2/src/services/v2/S3service.js`, `controllers/s3/upload.js`), Kafka (`kafkajs`, used by `services/v2/market-returns.js` for a PDF-generation trigger — not on the collection-submit path), Sentry (error tracking), Prometheus (`prom-client`), Socket.IO. The Actual-OS ledger feature is genuinely cross-service: a Sequelize/TS migration in the sibling `cdms` service, an `outstanding_invoice.ts` model, and a Python counterpart in the sibling `upi` service (`upi/outstanding_ledger.py`, `upi/verifyPayment.py`).

---

## 3. APIs (his surface)

- **`POST /complete`** (`colections_v2/src/controllers/invoices/complete-create.js:228`, behind `blockWebApp` + `verifyAuthToken`) — the single endpoint for both first submit and resubmit, branching on `data.update`. Reads: invoice rows, existing `master_payments`/`payments` snapshot (for resubmit), `bank_statement_api`, cash-limit aggregates. Writes: `master_payments` (versioned), `payments`, `collection_invoices.coordinates`/status, `bank_statement_api.verification_status`, `scanned_cheques.master_pid`, outstanding-ledger columns. Failure handling: Redis claim failure → fails open (proceeds) with a logged `redis_error` state; validation failure → 422; amount-mismatch on UPI → hard `throw` (500-path, not silently accepted); cash-limit breach → 400 with a specific message; on any thrown error the transaction connection is released in a `finally`.
- **`POST /amortize`** (`complete-create.js:44`) — a preview endpoint: runs the same `amortize()` call and 269ST checks without writing anything, so the app can show settle/bill-back suggestions before the salesman confirms.
- **`POST /invoice-handover/list-v2`** and **`/list-v2-count`** (`collections/src/controllers/invoice-handover/list-v2.js:207,547`) and **`GET /collection-history`** (`:614`) — invoice assignment/reassignment listing for segregators, with SQL `LIMIT`/`OFFSET` pagination (`:139`) and batched adjustment/closure lookups (§10).
- **`PUT /invoice-handover/update-v2`** (`collections/src/controllers/invoice-handover/update-v2.js:1081`, behind `verifyAuthToken` + `checkType(SEGREGATOR)`) — (re)assigns invoices to salesmen, gated by a long list of state checks (cheque-bounce hold, cashier/segregator verification state, same-date re-assign rules) via an array-of-queries transaction helper (`:1242`).
- **`POST /online-transactions/upicallback`** — exists in both versions but is essentially untouched by him (one-line files); not part of his verified surface.

---

## 4. Database

**Tables:** `ChampOutstandingInvoices` (brand/FC-scoped outstanding ledger, `unverified_amount`/`cheque_pdc_amount` added by his migration), `collection_invoices` (per-collection-attempt row, `coordinates` as a MySQL `POINT`, `status`), `master_payments` (state-machine payment header: `mode`, `amount`, `curr_state` ∈ {DEFAULT, PERSIST, SETTLE, EDITAMOUNT, EDITDATA, EDITAMOUNTORDATA}, `action` ∈ {CREATE, SEDIT, SEGVERIF, SEGSTARTVERIF, CASHIERREJECT, CASHIERVERIF}, `is_deleted`, `block_edit`, `parent_id`), `payments` (per-invoice payment line, `master_pid`, verification/settlement columns), `bank_statement_api` (`transaction_number`, `verification_status`, `credit`), `upi_payments`, `scanned_cheques` (OCR-linked cheque images, cross-repo with `ripplr-fin`), and his two new tables `cheque_suspense` and `champ_outstanding_suspense_logs`.

**Versioning pattern (master_payments):** a resubmit does not `UPDATE` a payment row — it sets `is_deleted = true` on the old row and `INSERT`s a new one whose `parent_id` points at the old row's id (`util.js:2255-2298`, mirrored at `collections/src/controllers/invoice-handover/list.js:446-477`), copying forward `bank_statement_id`, `upi_unique_id`, `payment_verification_status`, `cashier_verified_id`/`_at`, and settlement ids from the row being replaced (`util.js:~925-934`) so cashier verification history survives the rebuild.

**Indexes (his migration, `cdms/migrations/20260714060000-champ-outstanding-unverified-pdc.js`):** three composite indexes — `idx_cheque_suspense_natural_key (collection_invoice_id, cheque_number, bank_id)`, `idx_cheque_suspense_pdc_status (pdc_status)`, `idx_cheque_suspense_invoice_key (fc_id, brand_id, invoice_no)` — plus `idx_champ_suspense_logs_invoice (outstanding_invoice_id, created_at)` and `idx_champ_suspense_logs_payment (payment_id)`. The migration explicitly documents *skipping* a fourth index on `collection_invoices(invoice_no, fc_id, brand_id)` because the existing `Unique_Collection_Invoices` index already leads with `(brand_id, fc_id, invoice_no)` and covers the recompute join (`:229-231`).

**Transactions/atomic ops:** `/complete` runs its payment writes inside one MySQL transaction (`beginTransaction`/commit/rollback via `transaction_connection`); GPS/location persistence was deliberately pulled onto its own short-lived connection outside that transaction (§7). `update-v2.js` uses an array-of-queries helper (`:1242`) to execute a batch of statements atomically. The outstanding-ledger recompute is explicitly documented as running "under row lock, never delta-patched, because the resubmit flow deletes and re-inserts payments with new ids" (`outstanding_ledger.js:1-18`).

**State fields / lifecycle:** invoice-level `invoice_verification_status` (`RejectedByCashier`/`VerifiedByCashier`/…), payment-level `payment_verification_status` (adds `UPI_AUTO_VERIFIED`), `bill_status` (`Pending`/`Bill Back`/…), and the `master_payments.curr_state`/`action` pair above, which together drive both the rejection-reason edit gating and the cashier-lock logic in `collections.js`.

**Counts, how derived:** all line/commit counts in this document come from `wc -l` on the current file and `git log --format='%an' | sort | uniq -c` / `git show --stat` on the cited commits, run before the ownership-verification step was stood down.

---

## 5. Async / distributed mechanisms

- **Idempotency (claim 5, confirmed in this repo):** `complete-create.js:252-281` hashes an extraction of the payload (`extract_colln_payments` + `generatehash`, `util.js:66,95`) and claims it in Redis via `put_hashkey` (`util.js:78-81`), now `SET key value NX EX 60` — a single atomic call. If the claim already exists (`claimResult === null`), the request is rejected with `Request Under Process, Please Wait`. If Redis itself errors, `redisAvailable=false` and the code **falls through and proceeds** — i.e. fails open rather than blocking collection on Redis availability, exactly as the story describes.
- **Retry/race history:** the atomic `SET NX EX` replaced a prior `SET` followed by a separate `EXPIRE` call with no `NX` guard — a real window where two concurrent identical requests could both pass the check. Commit message ties this to a named prod incident (HYP10477).
- **Failure recovery:** on any exception in `/complete`, the transaction is rolled back and the DB connection released in a `finally`; the Redis key still expires after 60s so a genuinely failed request can be retried.
- **Dedup granularity:** the hash is over `{invoiceIds, paymentDetails: [{paymentType, id, amount}]}` — two different payloads for the same invoices (e.g. an edited amount) hash differently and are *not* deduped against each other; only byte-identical resubmits within the 60s window are caught.
- **UPI verification as async-adjacent reconciliation:** the bank-statement feed (`bank_statement_api`, populated by an external "Instaalert" feed — filtered by `updated_by = 'Instaalert'`, `util.js:655`) is polled/matched at submit time rather than pushed; a mismatch throws rather than queuing for later reconciliation.

---

## 6. Infrastructure

- **v1 (`collections/`):** Lambda + API Gateway (legacy, `sam-template.yaml`, nodejs12.x/1024MB/30s) or PM2-on-a-box via `app.local.js`, deployed by `bitbucket-pipelines.yml` (SSH + `git pull` + `pm2 restart`). A separate `Dockerfile.collection.aws` builds from a private ECR base (`collections_basenode`) and pulls its runtime `.env` from **AWS Secrets Manager** (`collection-staging-env`) at build time.
- **v2 (`colections_v2/`):** deployed via **Jenkins** pipelines (`colections_v2/jenkins_pipeline/{stage,preprod}/*.groovy`) that `git pull` on an EC2 host, build a Docker image with `Dockerfile.server`, push/pull through **AWS ECR** (`985173291048.dkr.ecr.ap-south-1.amazonaws.com`), and run it as a named Docker container (`docker stop`/`rm`/`run`), with a **second, parallel container line** (`block_edits_collection` / `IMAGE_NAME=block_edits_collections`) for the `blockedit_preprod` branch he merges into repeatedly — i.e. a dedicated preprod variant for testing the block-edit-after-reject work before it reaches the main preprod/stage line. Logs ship to **Grafana Loki** (`LOKI_URL=https://prod-loki.ripplr.in`), not mentioned in the v1 pipeline.
- **cron:** `node-cron` (`* * * * *`) in `src/cron/index.js`, gated by `CRON_ENV`, running `rejectExpiredDelegateInvoice`; `createCollectionInvoice` present but commented out. `colections_v2/src/cron/` mirrors the same three files.

---

## 7. Reliability + performance mechanisms (with evidence)

- **Atomic idempotency lock** — `SET NX EX 60` replacing a non-atomic `SET`+`EXPIRE` pair, closing a real duplicate-payment race (`util.js:78-81`, commit `93abfad88e`).
- **Lock-scope reduction** — GPS/location validation and `UPDATE collection_invoices SET coordinates=...` moved onto a dedicated connection *outside* the main payment transaction. The code comment states the old in-transaction version "held an X-lock on `collection_invoices` for the entire remainder of the request (~30s typical)"; the new version "releases in ms" (`complete-create.js:337-395`, same commit).
- **~330-second query eliminated** — a correlated `SUM` subquery on `obc_adjustment_data.adjusted_bill_no` (an unindexed TEXT column) ran once per result row in `list-v2`; commit `12aa60a52` states this "made list-v2 take ~330s" and replaces it with one `GROUP BY`-batched query per page, merged in JS (`collections/src/controllers/invoice-handover/list-v2.js`).
- **Correlated-subquery → JOIN rewrite** — the assigned/unassigned invoice filter previously ran a `SELECT … ORDER BY id DESC LIMIT 1` correlated subquery per row; rewritten to a `LEFT JOIN` against a `GROUP BY … MAX(id)` derived table (commit `77af874af`, `invoice_functions-v2.js`).
- **Bounded round-trips** — `GET /collection-history` batches its payment detail fetch into one `IN(...)`-query joined to `Banks`, described in the commit as running "at most 2 DB round-trips regardless of history length" (commit `a482c9601`).
- **Fail-loud UPI verification** — a mismatch between salesman-entered amount and the bank feed throws rather than defaulting to either auto-verify or silent manual-review fallback (`util.js:961-963`).
- **269ST compliance as a reliability control** — the store-level daily cash check is documented as having been "inert" before his rewrite ("subtraction cancelled and only bounded the current request"); rewritten to sum actual store cash at `(store_id, collection_date)` excluding the invoices in the current submission, plus a new per-invoice cumulative check on `/amortize` (commit `9dff451f0`).
- **Composite indexing** for the new suspense tables, with an explicit decision *not* to add a redundant index where an existing one already covers the query (§4).
- **Test coverage as a reliability signal:** `test_complete_endpoint.js` (763 lines), `test_cash_limit_269st.js` (183 lines), `test_salesman_edit_after_reject.js` (125 lines), `test_block_web_app.js` (107 lines), plus the two largest suites in the service, `list-v2.test.js` (656 lines) and `update-v2.test.js` (1321 lines).

---

## 8. Design decisions, trade-offs, alternatives, known bugs/gaps

- **Delete-and-recreate over update, by design.** `outstanding_ledger.js:1-18` states the recompute is deliberately non-incremental "because the resubmit flow deletes and re-inserts payments with new ids" — the same trade-off the interview story describes, and it forced a second, independent design decision (recompute-under-lock) elsewhere in the codebase.
- **Fail-open Redis, by design.** Explicit trade-off: a financial write path chose availability over strict dedup guarantee when the cache is down, on the reasoning that blocking all collections on Redis health is worse than a rare duplicate that downstream DB validation can still catch.
- **Frontend flags are not trusted.** `compute_payments_deleted` (`util.js:145`) exists specifically because the app's `payments_deleted` flag was unreliable — the backend now derives the same fact from a set-difference over `master_pid`s rather than trusting the client.
- **Known gap — dead code:** `colections_v2/src/helpers/master_payments.js` defines `create_master_payment`/`update_master_payment` (with a documented is-deleted-then-insert algorithm) but only exports `get_master_payment` (`:80-82`); the real versioning path in production is the separate, inline implementation in `util.js`. Anyone reading this file alone would get a misleading picture of where the mechanism actually lives.
- **Known inconsistency:** both `redis` (^3.1.2) and `ioredis` (1.0.11) are declared dependencies in `colections_v2/package.json`; the dedup lock goes through `req.app.get('redis')`, so confirming which client that resolves to matters before reasoning confidently about connection pooling/retry behavior under load.
- **Iterative, not one-shot, correctness on the cashier-reject fix.** The first attempt at "keep a cashier-rejected payment editable" (`2cd6e02f0`) over-corrected and also unlocked the salesman's own `SEDIT` edits; a second commit two days later (`4872cdf11`) narrowed the condition to `action === CASHIERREJECT` specifically, with a regression test tied to a named prod invoice (38370569). Worth knowing as a real debugging story, not a clean first-try fix.
- **Two parallel implementations of the same domain** (`collections/` v1 and `colections_v2/` v2) exist in the repo simultaneously with different deployment pipelines; `payment_methods.js`/`amortize.js` each have a v1 and a v2 copy that have diverged.

---

## 9. Numbers

### (a) Derivable from code/commits, with source
- `list-v2.js`: 733 lines; `update-v2.js`: 1292 lines (`wc -l`).
- Test suites: `list-v2.test.js` 656 lines, `update-v2.test.js` 1321 lines, `test_complete_endpoint.js` 763 lines, `test_cash_limit_269st.js` 183 lines, `test_salesman_edit_after_reject.js` 125 lines, `test_block_web_app.js` 107 lines (`wc -l`).
- `complete-create.js`: 1176 lines (`wc -l`).
- Pre-fix query cost, per commit message `12aa60a52`: the unbatched `obc_adjustment_data` correlated subquery "made list-v2 take ~330s."
- Redis lock: reduced from 2 non-atomic Redis calls (`SET` then `EXPIRE`, no `NX`) to 1 atomic call (`SET NX EX 60`) — from the diff in commit `93abfad88e`.
- Actual-OS ledger commit (`5fdcc134b`): 20 files changed, 2,026 insertions, 6 deletions (`git show --stat`), spanning 2 new DB tables, 2 new columns, 5 composite/simple indexes, and endpoints in 5 files.
- 269ST commit (`9dff451f0`): 5 files changed, 373 insertions, including a 183-line dedicated test file.
- Migration file: 252 current lines, 3 composite indexes + 2 simple indexes across 2 new tables (`cdms/migrations/20260714060000-...js`).
- Dependency versions from `package.json`: v1 `mysql2 ^2.3.2` vs v2 `mysql2 ^3.12.0`; both `ioredis 1.0.11`; v2 adds `kafkajs ^2.2.4`, `@aws-sdk/client-s3 ^3.956.0`; `jest ^29.5.0` in both.

### (b) Missing metrics — exact questions, and which bullet each strengthens
1. "Do you have a measured P50/P95/P99 for `/complete` or `list-v2` before vs. after the Redis-lock fix and the ~330s query fix — from Prometheus/CloudWatch/APM, in your own words? The commit message gives the *before* number for the query fix (~330s) but not an *after* number." → strengthens the ~330s bullet and the Redis race-fix bullet.
2. "Roughly what request volume (submissions/day, or concurrent salesmen at peak) was flowing through `/complete` when the HYP10477 duplicate-payment race and the NMB06530 payments_deleted bug were live in production?" → strengthens the Redis-fix and payments_deleted bullets.
3. "What's the rough transaction volume (₹ amount/day or count/day) through the collection pipeline — useful to size the 269ST compliance feature and the Actual-OS ledger?" → strengthens the 269ST and ledger bullets.
4. "Was the UPI amount-check gap ever observed producing an incorrect auto-verification in production before your fix, and do you know how many/what amount?" → strengthens the UPI-tolerance bullet.
5. "Across `colections_v2` as a whole, do you have (or can you pull) a total commit/PR count and lines-changed figure attributable to you, to cite as a scale statement alongside the per-file figures here?" → strengthens the invoice-handover/overall-ownership framing in §10.

*(The old resume's specific "p99 3s → 800ms" figure has no source anywhere in this codebase — see §12.)*

---

## 10. Candidate resume bullets

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

## 11. Interview material

### Hard problems

**P1 — Delete-and-recreate on resubmit.** *"Why rebuild `master_payments` instead of updating it, and how do you avoid losing the cashier's prior verification state?"* Because one submission's money can be re-split across a different set of invoices on resubmit (a payment can move or divide differently), there's no stable 1:1 row to update. The system marks the old row `is_deleted=1` and inserts a new one with `parent_id` pointing at it; before inserting, it copies forward `bank_statement_id`, `upi_unique_id`, `payment_verification_status`, `cashier_verified_id/_at`, and settlement ids from the row being replaced, so a payment the cashier already verified doesn't silently reset. His verified, adjacent contribution: the backend now independently *detects* whether a resubmit actually dropped a payment (`compute_payments_deleted`), rather than trusting the app to say so, and he re-links OCR cheque-scan records across exactly this same rebuild.

**P2 — Why `SET NX EX` and not GET-then-SET.** A plain `SET` followed by a separate `EXPIRE` has a window between the two calls, and a `GET`-then-`SET` has an even larger check-then-act race; two concurrent identical requests can both observe "not present" and both proceed. `SET key value NX EX 60` is a single atomic Redis command: only one caller can ever get an OK. Follow-up: this is a Redis-level lock, not a DB-level one — the DB transaction and business validations behind it are the second line of defense if a duplicate ever does get through.

**P3 — Why 10 paise, and why fail loud.** Bank feeds and salesman-entered amounts can differ by rounding at the paisa level; a strict equality check would reject good matches. `Math.abs(a - b) <= 0.1` absorbs that noise without opening the door to real mismatches. The fail-loud choice (`throw`) instead of silently leaving it for manual review reflects that silent acceptance was the actual bug being fixed — before this change, any UTR match auto-verified regardless of amount.

**P4 — 269ST: why both a per-store-day check and a per-invoice check.** The regulatory limit is a *cumulative* cash ceiling per payer per day, not a per-transaction cap, so a check scoped to only the current request's invoices could be gamed by splitting a submission; the store-day sum has to include prior invoices already collected that day (excluding the ones in the current submission, to avoid double-counting on resubmit) as well as a per-invoice cumulative check on the preview endpoint.

**P5 — The 330-second query.** A correlated subquery re-executes for every outer row; on an unindexed TEXT column (`adjusted_bill_no`) that's a full table scan per row, which is why the cost was roughly linear in result-set size and catastrophic at scale. Batching means running the aggregate once for the distinct invoice numbers on the current page and joining the results in memory — bounded by page size, not table size.

### Follow-up questions with accurate answers

- *What happens to a `/complete` request that legitimately takes longer than 60 seconds?* The Redis key expires and a retried/duplicate request would be treated as new — the TTL is a heuristic tied to expected request duration, not a hard correctness guarantee.
- *Does the Redis lock protect against two different payloads for the same invoice arriving concurrently?* No — the hash is over the specific payment payload, so an edited amount produces a different hash and is not deduped against the original.
- *Why hash an extracted subset of the payload rather than the raw request body?* So logically-identical resubmits that differ only in irrelevant fields (ordering, metadata) still collide on the same hash; `extract_colln_payments` pulls just invoice ids and payment type/id/amount.
- *Why does an `SEDIT` (salesman edit) action also leave a payment in an `EDIT*` state, and why did that break the first cashier-reject fix?* The state machine uses the same `EDITAMOUNT`/`EDITDATA`/`EDITAMOUNTORDATA` values to represent both "cashier handed this back for a specific kind of correction" and "salesman is mid-edit," disambiguated only by the `action` field — the first fix checked state without checking that `action === CASHIERREJECT`, so it also reopened SEDIT rows.
- *Why recompute the outstanding ledger under a row lock instead of applying deltas?* Because the resubmit flow deletes and reinserts payment rows with new ids, there's no stable row to apply a delta against; recomputing from source under a lock is simpler and correct by construction, at the cost of doing more work per write.
- *Why are both `redis` and `ioredis` present as dependencies in `colections_v2`?* Only one is actually the client the dedup lock uses (`req.app.get('redis')`); the other is either legacy or used by a different subsystem — worth confirming which, since they have different connection-pooling and cluster-mode behavior.
- *Is the new `cheque_suspense` composite index on `(fc_id, brand_id, invoice_no)` redundant with the existing invoice uniqueness index?* No — they're on different tables; the migration explicitly reasoned about *not* duplicating a similarly-shaped index on `collection_invoices` because an existing index already led with the same columns there.
- *What's the operational difference between the v1 Lambda path and the v2 Jenkins/Docker/EC2 path?* Lambda is cold-start-sensitive and capped at 30s/1024MB per the SAM template; the v2 Docker-on-EC2 path via Jenkins has no such per-request ceiling and ships logs to Loki, which is likely why the newer, more complex endpoints (with multi-step transactions and ledger recomputation) live there.

---

## 12. Red flags (technical only)

- **The old resume's "p99 3s → 800ms" figure has no source anywhere in this codebase** — not in code, comments, commit messages, or docs. The ~330s→batched-query fix (§10.1) is a real, sourced, and considerably more dramatic number from a commit message; it should replace the unsourced figure rather than coexist with it unless an external dashboard genuinely backs the original claim.
- **`master_payments.js` is misleading if read in isolation.** It defines a clean `create_master_payment`/`update_master_payment` pair with a documented versioning algorithm, but only `get_master_payment` is actually exported and used; the real versioning logic in production is a separate, inline implementation in `util.js`. Don't cite this file as "the" mechanism in an interview — it's dead code next to the real one.
- **Two Redis clients declared, one presumably unused** (`redis` + `ioredis` both in `colections_v2/package.json`) — worth resolving which one backs the idempotency lock before fielding a deep question on its failure modes.
- **The cashier-reject fix shipped in two passes**, the first of which had a real over-broad bug (unlocking `SEDIT` edits) caught by a regression test rather than in review — an honest, tellable debugging story, but not a one-shot fix if asked directly "did it work the first time?"
- **His longest-tenured, best-tested code (`list-v2.js`/`update-v2.js`, invoice-handover) is the invoice *assignment/reassignment* engine, not the collection-submission/rejection/amortization domain** the interview story centers on. Both are real and both are his — they're just different features, and conflating them in an answer risks a follow-up question landing on the wrong file.
- **The UPI "release the bank-statement entry when a payment is removed" behavior exists in this codebase** (`clear.js` calling `update_bank_statement_api_set_verification_status_as_null`) but his verified, dated contribution to UPI auto-verification specifically is the amount-tolerance guard — know the boundary between "the system does this" and "I added this line" before a probing follow-up.

---

## 13. Tech stack evidenced in this code

- **Language/runtime:** JavaScript (Node.js), CommonJS modules throughout both `collections/` and `colections_v2/`. A separate sibling service (`cdms/`) uses TypeScript + Sequelize migrations/models. A separate sibling service (`upi/`) is Python.
- **Web framework:** Express `^4.17.1` (both packages); `express-winston` (v1 request logging), `express-validator ^7.1.0` and `express-fileupload ^1.5.2` (v2 only).
- **Database:** MySQL via `mysql2` (`^2.3.2` in v1, `^3.12.0` in v2) with predominantly raw parameterized queries; `sequelize ^6.31.0` present in both (used for the `cdms` migrations); `knex ^2.4.2` as a dev dependency.
- **Cache / idempotency:** Redis, via both `ioredis 1.0.11` and `redis ^3.1.2` (both packages declare both clients — see §12); used for `SET NX EX` request-dedup locks.
- **Messaging:** `kafkajs ^2.2.4` (v2 only), used in `services/v2/market-returns.js` for a PDF-generation trigger.
- **Cloud (AWS):** Lambda + API Gateway (`@vendia/serverless-express ^4.3.0`, `sam-template.yaml`, v1 legacy runtime); S3 (`@aws-sdk/client-s3 ^3.956.0` + `s3-request-presigner`, v2); Secrets Manager (pulled into `.env` at Docker build time, v1); ECR (both Docker deploy paths); EC2 (Docker-container-on-host deploy target for v2's Jenkins pipeline).
- **Scheduling:** `node-cron ^3.0.0` (both), one-minute tick gated by `CRON_ENV`.
- **Observability:** `prom-client ^15.1.3` (Prometheus metrics, including event-loop-lag p99 gauges), `@sentry/node ^7.102.0` (error tracking), `winston ^3.3.3` (v1) / `log4js ^6.9.1` (v2) for logging, Grafana Loki (v2 deploy pipeline only), `socket.io ^4.4.0`.
- **Auth/validation:** `jsonwebtoken ^8.5.1`, `bcryptjs ^2.4.3`, `validatorjs ^3.22.1`.
- **Testing:** `jest ^29.5.0` + `supertest ^6.3.3` (route-level tests), plus a Python `pytest` suite in the sibling `upi` service for the cross-service ledger feature.
- **Other libraries in active use:** `lodash`, `moment`/`moment-timezone`, `exceljs` (report export), `axios` (WATI HTTP calls).
- **Deployment tooling:** Bitbucket Pipelines (v1), Jenkins Groovy pipelines (v2, separate `stage`/`preprod` and normal/`blockedit` variants), Docker (`Dockerfile.server`, `Dockerfile.collection.aws`, `Dockerfile.rnode.collection`, `Dockerfile.rserver.collection`), PM2 (v1 process manager).
