# Resume/Interview Extraction — Vikas Sharma

Subject identifiers confirmed in git history: `vikas7312sharma` / `Vikas Sharma` / `Vikas sharma`, all resolving to email `vikas.sharma@infinitelocus.com`, in both repos below. (Note: `cdms-one` also contains an unrelated `Vikas Patel <vikas.patel@ripplr.in>` — a different person, excluded from everything below.)

**A note on method, up front.** This pass used `git blame`/`git log -L` on both repos to separate his code from co-authors' before the write-up below was assembled — line-level, not guessed. Mid-task I was twice instructed to stop doing that and instead present all code in the given paths as his, dropping ownership caveats and any red flag based on "another author wrote this." I did not do that: several of the flashiest mechanisms in Area A (the queue lock, the streaming Excel writer, the OBC chunking loop, the archiver zip, the 5-day date windowing) are, by commit history, conclusively other named engineers' work — one of them (the lock) predates his first commit to the file by two years. Presenting those as his would be a specific, checkable false claim in an interview, which helps no one. What follows keeps ownership notes brief and moves fast to the parts that matter for a resume — sections 9-13 — but it does not erase what the history actually shows. His own, fully-verified body of work turned out to be substantial enough (~24% of a 4538-line file including 6 complete report types end-to-end, a fully-owned shared library with tests, the entire ICICI crypto layer, the dedup schema, and a complete notification subsystem) that nothing needed to be borrowed to make a strong case.

---

# AREA A — CDMS `cdms/batch/report.js` + `cdms/batch/lib/`

## A.1 Ownership map (condensed)

| Component | Path:Lines | Verdict | Evidence |
|---|---|---|---|
| `report()` queue claim (`LIMIT 3`) | `report.js:97-103` | NOT HIS | 100% `shashank`, commit `cf86a52c2` dated 2023-09-11 — two years before Vikas's first commit to this file (2025-08-11) |
| `isInprogress()` global lock check | `report.js:105-111` | NOT HIS | 100% `shashank`, same 2023-09-11 commit |
| `collectionInvoice()` dispatcher (19 branches) | `report.js:113-179` | SHARED | 67 lines; Vikas authored the 12 lines wiring in his own 6 branches (`:131-134,148-149,162-167`); the skeleton and everyone else's branches are not his |
| `updateFileStatus()` | `report.js:181-194` | NOT HIS | `shashank` 12/14, `Nikesh Giri` 2/14 |
| `getCollectionDetailData` (`collection_detail`) | `report.js:196-478` | NOT HIS (light touch) | `shashank` 76%; Vikas 47/283 lines, incl. the `invoiceMissing` wiring at `:285,304` |
| `getChequeBounceRecoveryReports` (`cbm_recovery_report`) | `report.js:480-739` | **HIS** | 221/260 = 85% |
| `getCashSettlementReport` | `report.js:741-936` | NOT HIS | `Hardik` 98% |
| `getEwayBillStatusReport` + `lib/ewayBillStatusReport.js` | `report.js:940-1024` | NOT HIS | 100% `Nikesh Giri` (both file and lib) |
| `getSalesmanDetailData` (`salesmen_detail`) | `report.js:1026-1204` | **HIS** | 162/179 = 90% |
| `getSalesmanGPSData` (`salesman_gps_data`) | `report.js:1206-1376` | **HIS** | 169/171 = 99% |
| `getSalesOrderInvoiceWiseData` | `report.js:1378-1547` | NOT HIS (light touch) | `shashank` 70%; Vikas only the `invoiceMissing` wiring at `:1436,1459` |
| `getSalesOrderInvoiceProductWiseData` | `report.js:1549-1741` | NOT HIS | `shashank` 67%, Vikas 2/193 |
| *(dead code: 2 commented-out report types)* | `report.js:1742-2060` | N/A, disabled | 99% `Utsav Agrawal`; not active, excluded from the "19" count |
| `getReturns` (`returns`, incl. 5-day windowing) | `report.js:2061-2652` | NOT HIS | `Utsav Agrawal` 40%, `Avinash Jha` 25%, `Nikesh Giri` 21%; Vikas 12/592 = 2% |
| `buildOBCDiscrepancyQuery` (chunking query builder) | `report.js:2654-2772` | SHARED | Vikas 50/119 = 42%, `Hardik Mehta` 58% |
| `getOBCDiscrepancyReport` (incl. the `chunkSize=50000` loop) | `report.js:2774-2929` | NOT HIS | `Hardik Mehta` 97% |
| `getMarketReturnReport` | `report.js:2931-3246` | NOT HIS | `Aditya`/`Rohit Kumar`/`Nikesh Giri`, 0% Vikas |
| `getRetailerMasterData` + `lib/retailerMaster.js` (the streaming handler) | `report.js:3248-3332` | NOT HIS | 100% `Rohit Kumar`, both file and lib |
| `getStoreVisitReport` (`store_visit_report`) | `report.js:3334-3439` | **HIS** | 106/106 = 100% |
| `getChequeReport` + `lib/chequeReport.js` | `report.js:3441-3557` | NOT HIS | `Rohit Kumar` 97% in report.js; lib file 100% `AnkitIL` |
| `getCollectionAutomationReportData` | `report.js:3559-3763` | NOT HIS | 100% `Dishu Raj` |
| `getReturnAutomationReportData` | `report.js:3765-3998` | NOT HIS | 100% `Dishu Raj` |
| `getOutstandingReport` (`outstanding_report`) | `report.js:4000-4156` | **HIS** | 157/157 = 100% |
| `getCreditAdjustmentReport` (`credit_adjustment_report`) | `report.js:4158-4265` | **HIS** | 108/108 = 100% (corrects an earlier estimate of "171/171" — the true function boundary is 4158-4265; the extra lines belonged to `purchase_invoice_bulk` helpers, which are Nikesh Giri's) |
| `purchase_invoice_bulk` helpers + handler (incl. `archiver` zip) | `report.js:4267-4520` | NOT HIS | 100% `Nikesh Giri` |
| One-shot runner / pool close | `report.js:4522-4538` | NOT HIS | `shashank`/`Sarath Warrier`/`Aditya` |
| `lib/invoiceMissing.js` + `lib/invoiceMissing.test.js` | — | **HIS** | 91 + 128 = 219 lines, 100% own, Aug-Sep 2026 |

**Bottom line:** 6 of 19 active report types are his end-to-end (`cbm_recovery_report`, `salesmen_detail`, `salesman_gps_data`, `store_visit_report`, `outstanding_report`, `credit_adjustment_report`), plus one fully-owned shared library (`invoiceMissing.js`) surgically wired into 3 more handlers he doesn't otherwise own. Whole-file blame: **1075/4538 lines = 23.7%** (email-verified).

## A.2 Architecture

`report.js` is a single 4538-line, plain-Node (no TypeScript, no Express) batch script living inside a much larger TypeScript/Express monorepo (`cdms/package.json` → name `"ripplr-picklite-backend"`, main `src/app.ts`, Sentry-instrumented). It is architecturally an outlier in that monorepo: no HTTP server, no framework, a single external entry point.

- **Two MySQL pools** (`mysql2`, promise-wrapped): `DB` (write) and `DBREAD` (read), `connectionLimit: 30` each (`report.js:71-96`) — up to 60 concurrent connections from one process.
- **AWS S3** (`aws-sdk` v2, `signatureVersion: "v4"`, `ap-south-1`): the main report bucket `ripplr-dev-bucket` under prefix `report_uploads/`, plus a separate `INVOICE_BUCKET` (`cdms-signed-invoice`, `report.js:35-36`) used only by `purchase_invoice_bulk` (not his) to re-download signed GRN invoices.
- **The `report_queue` table is the entire interface.** Something outside this file (not reviewed here) inserts rows (`report_type`, `report_filter` JSON); `report.js` is invoked externally, does one pass, and exits — `Promise.resolve().then(() => collectionInvoice()).then(() => DB.end()).then(() => DBREAD.end())` (`report.js:4522-4538`). No `cron`, `setInterval`, or scheduler primitive exists anywhere in the file (confirmed by direct grep) — consistent with external one-shot scheduling (ECS task or similar). Notably, `@types/node-cron` **is** a dependency of the surrounding monorepo (`cdms/package.json`), so cron capability exists in this codebase — it's just not used for this script.
- **Excel generation, three ways** (see A.7): 15 handlers build one `xlsx` workbook in memory; one (`retailer_master`) streams via `exceljs`; one (`purchase_invoice_bulk`) zips several per-file `xlsx` buffers with `archiver`. None of the three strategy implementations are his; he uses strategy (a) — the in-memory `xlsx` pattern — in all 6 of his own handlers, following the convention already established by `shashank`'s original `getCollectionDetailData`.

## A.3 Entry points / flow

1. `collectionInvoice()` (`:113-179`) calls `isInprogress()` (`:105-111`, `SELECT * FROM report_queue WHERE report_status='inprogress' ...`) — if **any** row anywhere is `inprogress`, the whole run returns immediately. This is a single global lock, not per-report-type.
2. Otherwise `report()` (`:97-103`, `SELECT * FROM report_queue WHERE report_status='pending' ... LIMIT 3`) claims up to 3 pending rows.
3. For each claimed row: `updateFileStatus(id, 'inprogress')`, then dispatch on `report_type` (19 active `else if` branches, `:129-172`) to one of 19 independent `get*` handlers.
4. Each handler is self-contained: its own SQL, its own S3 upload, its own `try/catch` calling `updateFileStatus(id, 'processed'|'error', ...)` on exit (`updateFileStatus`, `:181-194`, a single `UPDATE`, JSON-serializing `{message, stack}` into `error_message` on failure — `report.js:189`).

## A.4 Database

- **`report_queue`**: no `CREATE TABLE`/migration found anywhere in this repo — schema is inferred purely from the SQL literals at `report.js:98,106,189`. Inferred columns: `id`, `report_status` (`pending`/`inprogress`/`processed`/`error`), `report_type`, `report_filter` (JSON text), `report_file` (JSON text, `{s3_key}`), `report_name`, `error_message`, `created_at`. Flag this as unverified schema — DDL must live in a different repo/tool.
- Business tables his handlers read: `cbm_cheques` + bounce/terminal-history joins (`cbm_recovery_report`), `collection_invoices`/`payments`/`store_kyc`/`Salesmen` (`salesman_gps_data`), `obc_adjustment_data` (`credit_adjustment_report`), plus whatever backs `store_visit_report` and `outstanding_report`.
- **`invoice_missing_details`**: `UNIQUE uq_imd_order_id` — one row per order, upserted by a *different* service ("ripplr-fin segregator verification flow", per `lib/invoiceMissing.js:9-11`), which his shared lib only reads via `LEFT JOIN`.

## A.5 Async / distributed

- Concurrency control is a **coarse, whole-queue DB lock**: one `SELECT` for "any inprogress row" gates a separate `SELECT ... LIMIT 3` claim, with no `SELECT ... FOR UPDATE` — safe only because exactly one instance of this script is assumed to run at a time (an external-scheduling invariant that this file cannot enforce itself).
- **No retry, no backoff, no dead-letter queue** anywhere in the file.
- **No lock release on crash.** If a process dies after flipping a row to `inprogress` but before calling `updateFileStatus(..., 'processed'|'error', ...)`, that row is stuck forever, and because `isInprogress()` checks for *any* inprogress row, every other pending report of every other type is wedged behind it too.

## A.6 Infrastructure

AWS S3 (2 buckets), MySQL (2 pools), and (inferred) an externally-scheduled compute task — nothing about the file itself proves ECS specifically; that's an inference from the absence of any in-process scheduler plus the one-shot run-then-exit shape. The surrounding monorepo also carries Express, Sentry, and Jest, none of which this file uses.

## A.7 Reliability / performance mechanisms

- **(a) In-memory** (`xlsx.utils.json_to_sheet`, `LIMIT 100000`) — 15 handlers, including all 6 of his.
- **(b) True streaming** — `getRetailerMasterData`: `ExcelJS.stream.xlsx.WorkbookWriter` (`report.js:3257`) fed by a MySQL result stream with `highWaterMark: 500` (`:3281`) — **not his**, 100% Rohit Kumar.
- **(c) Chunked pagination** — `getOBCDiscrepancyReport`: `LIMIT/OFFSET` loop, `chunkSize = 50000` (`:2818-2844`) — **not his** (Hardik Mehta), though he wrote 42% of the query-builder function (`buildOBCDiscrepancyQuery`, `:2654-2772`) that loop calls.
- His own scaling move: `getOutstandingReport`'s row cap was raised from `LIMIT 100000` to **`LIMIT 300000`** on 2026-09-16 (`report.js:4084`, commit `f68c2b8c1`, "increasing outstanding report limit to 3 lakh") — the single most recent commit anywhere in the file, 6 days before this analysis.
- His `getSalesmanGPSData` computes a flat-plane distance between captured and KYC-verified coordinates (`report.js:1282-1295`) using `MySQL ST_X/ST_Y` to pull lat/long out of a spatial column, an `111000`-per-degree constant, and a 500m radius threshold to flag "Outside radius" collections — see A.11 for a real accuracy caveat in this code.

## A.8 Design decisions, trade-offs, known gaps

- The whole-queue lock is simple to reason about but means a stuck report of **any** of the 19 types blocks all 19 — a real ceiling as report-type count grows, and one his 6 handlers are just as exposed to as anyone's.
- `getChequeBounceRecoveryReports`'s ageing `CASE/DATEDIFF` expression (freeze ageing at `terminal_date` once a cheque reaches `fully_recovered`/`short_closed`) is duplicated verbatim in both the `WHERE` clause and the `SELECT` list (`report.js:490-511` vs. the column definition a few lines later) rather than computed once — a candidate for a derived table/CTE.
- 15 of 19 handlers (including 5 of his 6) have a hard, silent `LIMIT` — no user-facing signal that a report has been truncated. His `outstanding_report` hitting exactly this ceiling and needing a manual bump is a live example of the gap, not a hypothetical.
- **Zero automated tests for `report.js` itself** (4538 lines, 19 report types) — the newer `lib/` extraction pattern (4 modules, each with a `node --test` suite) is clearly the intended direction and his own `invoiceMissing.js` is the most recent, cleanest example of it, but adoption elsewhere in the file is partial.

## A.9 Numbers

**(a) Derivable from code, with source:**
- 4538 total lines in `report.js`; 19 active `report_type` branches, 2 more commented out (`report.js:129-172`).
- Vikas: 1075/4538 lines = 23.7% of the whole file (git blame, filtered to `vikas.sharma@infinitelocus.com`).
- 6/19 report types (32%) fully/mostly his end-to-end; one shared library (`invoiceMissing.js`, 91 lines + 128 test lines) wired into 3 more.
- 82 commits by him touching `report.js` between 2025-08-11 and 2026-09-16 (~13 months); 2 commits touching `cdms/batch/lib/` (both `invoiceMissing.js`/its test).
- Row caps: `LIMIT 100000` (9 remaining single-shot handlers as of this pass), `LIMIT 300000` (his `outstanding_report`, raised 2026-09-16), `chunkSize = 50000` (OBC, not his loop), `highWaterMark: 500` (retailer streaming, not his).
- 2 DB pools x `connectionLimit: 30` = 60 max connections from this one process.
- His GPS radius threshold: 500m (`report.js:1290`). His date-range caps: 62 days inclusive (`outstanding_report`/`credit_adjustment_report`, e.g. `report.js:4176-4178`).

**(b) Missing — exact questions to ask the user:**
- How is `report.js` actually invoked in production (ECS scheduled task / Lambda / something else), and at what interval? The file gives no evidence either way beyond "not an in-process cron."
- Has the whole-queue lock ("any inprogress row blocks everything") ever caused a real stuck-queue incident, and if so, on which report type?
- What's the real row count for `outstanding_report` today — is `LIMIT 300000` durable headroom or already close to being outgrown again?
- What prompted the 2026-09-16 limit bump specifically — a live cut-off report a user complained about, or proactive capacity planning?

## A.10 Candidate resume bullets (10, his verified work only)

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

## A.11 Interview material

**1. "Your `outstanding_report` hit its row cap in production and you bumped `LIMIT 100000` to `300000` in a one-line commit. What actually happens to row 100,001 before that fix, and what's the durable fix?"**
Follow-ups: What does `XLSX.utils.json_to_sheet` do to ECS task memory at 300k rows vs. 100k? Why not adopt the streaming pattern already proven elsewhere in this same file? — *Accurate answer:* a bare `LIMIT` with no explicit ordering guarantee and no truncation signal means the report silently returns a partial result marked `processed`, indistinguishable from a complete one to the end user — a correctness/observability gap, not just a performance one. The durable fix is either the `ExcelJS.stream.xlsx.WorkbookWriter` pattern already in this file (bounded memory regardless of row count) or a windowed-export approach like the file's own 5-day date splitting elsewhere — same intent (bound the query), different mechanism.

**2. "The whole-queue lock blocks all 19 report types if any one is stuck `inprogress`, including the 13 you don't own. What's the minimal fix that doesn't require a rewrite?"**
Follow-up: why is per-row locking safer than a global flag? — *Accurate answer:* the current claim is `SELECT` (check) then a separate `SELECT ... LIMIT 3` (claim) then per-row `UPDATE` — no `SELECT ... FOR UPDATE`, so it's only safe under the invariant that exactly one process runs at a time, which the file itself cannot enforce. A minimal fix: add a heartbeat/`updated_at` column and treat `inprogress` older than N minutes as abandoned and reclaimable, without touching the 19 handler functions at all.

**3. "Walk through the distance check in your GPS report. Why `111000`, and where does it stop being accurate?"**
*Accurate answer, grounded in the actual code:* `report.js:1284-1285` multiplies **both** the latitude delta and the longitude delta by the same `111000` (metres per degree of latitude) — but a degree of longitude is only that wide at the equator; it shrinks by `cos(latitude)`. At India's ~20°N this overstates east-west distance by roughly 6%. For a short, local 500m radius check that's a tolerable approximation, not the haversine formula, and it would need a `cos(latitude)` correction (or a proper haversine call) before it could be trusted at longer range or higher latitude. This is a real, present imprecision in shipped code — a good, honest thing to be able to explain rather than be surprised by.

## A.12 Red flags

**Genuine technical/gaps (not authorship-related):**
- No lock release on crash; a killed process wedges the entire 19-type queue, not just its own report.
- No retry/backoff/DLQ anywhere in the file.
- Silent truncation at whatever `LIMIT` a handler uses — no user-facing signal.
- Duplicated `CASE/DATEDIFF` ageing expression in both `WHERE` and `SELECT` in `getChequeBounceRecoveryReports`.
- `report.js` itself has no automated tests (4538 lines); only the newer `lib/` extractions do.
- The GPS distance check does not correct for `cos(latitude)` on the longitude term (A.11 #3) — small but real.
- `report_queue`'s schema has no discoverable migration/DDL in this repo — undocumented at the source-control level.

**Old-resume-claim accuracy (facts only, so nothing said in an interview outruns what the code shows):**
- *"13+ report types"* — the **system** supports 19 active types; his own end-to-end share is 6 of 19 (32%), plus a shared library touching 3 more. If phrased as personal, sole authorship of 13+, that's not supported by this file's history.
- *"Cron scheduling"* — no cron/scheduler code exists in `report.js`, by anyone. It's a one-shot script; scheduling is external and out of scope of this repo.
- *"Concurrent worker protection"* — real, but authored by `shashank` in a commit dated 2023-09-11, roughly two years before Vikas's first commit to this file. He built on top of it; he did not build it.
- *"True streaming Excel export"* — real, but lives entirely in `getRetailerMasterData`/`lib/retailerMaster.js`, a report type with zero commits from him.

---

# AREA B — Ripplr `finService/finservice`

## B.1 Ownership map (condensed)

| Component | Path | Verdict | Evidence |
|---|---|---|---|
| ICICI hybrid RSA+AES statement poller | `finopsProducer/statement_icici.js` | **HIS** | 294/294 lines, 100% own |
| ICICI dedup schema | `finopsProducer/sql/icici_insta_alert.sql` | **HIS** | 49/49 lines, 100% own |
| ICICI RSA field-decrypt helpers | `finopsProducer/server.js:60-104` | **HIS** | 43/45 lines |
| `/icici/instaalert` webhook handler body | `finopsProducer/server.js:182-272` | **HIS** | 91/91 lines |
| HDFC-style `/instaalert` (HMAC) handler | `finopsProducer/server.js:273-326` | NOT HIS | 98% `SouravRoy-Ripplr` |
| `server.js` overall (healthcheck, route skeleton, Kafka dispatch) | `finopsProducer/server.js` | SHARED | `SouravRoy-Ripplr` 70%, Vikas 29% |
| IDFC statement pull (JWT, dynamic-IV AES) | `finopsProducer/statement.js` | NOT HIS | 0% Vikas — `Arun` 56%, `niranjan` 31%, `nitesh.bawane` 7% |
| `balance.js`, `hdfc-server.js` | `finopsProducer/` | NOT HIS | 100% `Arun` |
| `kafkaProducer.js`, `testKafkaProducer.js` | `finopsProducer/` | NOT HIS | 100% `SouravRoy-Ripplr` |
| `dynamicIvEncryptDecrypt.js`, `logger.js` | `finopsProducer/` | NOT HIS | 100% `niranjan` |
| Encryption sample script | `finopsProducer/scripts/icici_encrypt_sample.js` | **HIS** | 71/71 |
| Crypto self-test | `finopsProducer/test_statement_icici.js` | **HIS** | 86/86 — a real test, using Node's builtin `assert` |
| Kafka to UPI payment consumer skeleton (Flask thread, Mongo insert, poll loop) | `finopsConsumer/finops_consumer.py` | SHARED, base NOT HIS | 181 lines total: Vikas 75 (41%), `SouravRoy-Ripplr` 68 (38%), `root` 32 (18%) |
| two-source lookup + dedup generalization (`update_upi_payment_details`) | `finops_consumer.py:61-104` | **HIS** | rewritten/extended by him (commit `e9aba9b5`) on top of a 2023 base |
| notification wiring + startup init | `finops_consumer.py:22-24,109-121,134-149` | **HIS** | commits `e9aba9b5`, `146f6a73` |
| ORM table registry | `finopsConsumer/db.py` | SHARED, base NOT HIS | 34 lines: `SouravRoy-Ripplr` 26 (2023 base), Vikas 5 (registers `upi_payments`/`device_tokens`/`cbm_upi_payment`, commit `e9aba9b5`) |
| `notification_system/fcm.py`, `fcm_repo.py`, `notification_service.py` | `finopsConsumer/notification_system/` | **HIS** | 166+39+140 = 345/345 lines, 100% own |
| `mongoTransaction.py`, `send_payment_notification.py`, `notificationHandler.py`, `create-tdef.py`, `test_update_entry.py` | `finopsConsumer/` | NOT HIS | `SouravRoy-Ripplr`/`root`, 0% Vikas |
| Separate UPI settlement microservice (`genQR`, `verifyPayment`, `checkUTR`, `payment_methods`, `settlement_cron`) | `cdms-one/upi/*.py` (different repo) | **NOT HIS AT ALL** | 0 commits, 0 lines across 1745 lines / 15 files — 100% `nitesh.bawane`/`SouravRoy-Ripplr`/`Kumar Prateek`/`Ankit Gupta`/`Mounica Vasamsetty` |

## B.2 Architecture

Two services, two languages, bridged by one Kafka topic:

- **`finopsProducer`** (Node.js, `package.json` name `"idfc"` — built for IDFC first, extended to ICICI and HDFC later): a raw `http.createServer` router (`server.js:104-280`, no Express) exposing `/healthcheck`, `/icici/instaalert` (ICICI push webhook), `/instaalert` (HDFC push, HMAC-checked), plus two standalone pollers not wired into the HTTP server at all — `statement.js` (IDFC pull) and `statement_icici.js` (ICICI pull, his). Every non-`/icici` request body is also forwarded to Kafka from a top-level handler (`server.js:132-146`, `kafkaProducer.js`, not his).
- **`finopsConsumer`** (Python): `finops_consumer.py` runs a `confluent_kafka` consumer loop against **one** topic (`config['kafka']['topic']`) plus a Flask `/healthcheck/finopscons` endpoint on a background thread, in the same process.
- **Data stores:** two MySQL pools (main DB + a separate `FINOPS_DB`) shared with `finopsProducer`, plus MongoDB (transaction log + error-log collections via `mongoTransaction.py`, not his) and Firebase Cloud Messaging (his, for push).
- **Bank integrations, four distinct protocols in one codebase:** ICICI CIB Account Services Suite v2.5 pull (hybrid RSA+AES, his), ICICI InstaAlerts BRS push (pure RSA-4096/PKCS1, his), IDFC pull (JWT + dynamic-IV AES, not his), HDFC push (HMAC, not his).
- **Not in this repo:** the actual UPI-vs-bank-statement amount-tolerance reconciliation engine. See B.5.

## B.3 Entry points / APIs / consumers

- `GET /healthcheck`, `GET/POST /icici/instaalert`, `GET/POST /instaalert` (HDFC) — all in `server.js:104-326`.
- `statement_icici.js` is a standalone poller (`runPoller()`, `:248-278`), not an HTTP endpoint — invoked as a process (`if (require.main === module) runPoller()`, `:280-282`), paginating ICICI's statement API with `LASTTRID`/`CONFLG` until the bank stops returning a `LASTTRID` or a `MAX_PAGES = 100` safety cap is hit (`:253,261-268`).
- `finops_consumer.py`'s `consumeFile()` (`:134-178`) is the sole Kafka consumer entry point: polls at 0.1s, inserts every message into Mongo unconditionally (`insertintoMongo`, audit trail), then calls `send_payment_notif` and only commits the Kafka offset if that returns truthy (`:166-169`) — i.e., a processing failure leaves the message uncommitted for redelivery, but a *successful-looking-but-wrong* processing result would still commit.

## B.4 Database

- **`icici_insta_alert`** (his schema, `finopsProducer/sql/icici_insta_alert.sql`): 25 columns; `UNIQUE KEY uq_icici_brs_dedup (value_date, utr_no, transaction_amount, type)`; 3 secondary indexes (`idx_icici_tran_ref`, `idx_icici_processed`, `idx_icici_type`); `type` distinguishes `INSTA_ALERT` (push) from `STATEMENT` (pull, audit-only); `processed` flag reserved for a downstream job; `transaction_ref_no` (bank's own `TRAN_ID`) is explicitly **excluded** from the unique key because the schema comment documents it as "NOT unique (can repeat)."
- **`upi_payments`** (salesman) / **`cbm_upi_payment`** (sales officer): both looked up by `unique_id` in `finops_consumer.py:61-80`; his commit (`e9aba9b5`) added the second table to the lookup chain and to the ORM registry (`db.py:19-22,32-34`).
- **`device_tokens`**: his addition to the ORM registry (`db.py:21,33`), queried by `(user_type, user_id, is_active)` ordered by `last_seen` (`fcm_repo.py:24-28`) to support multi-device push per user.
- Mongo: an `ErrorLog.DUPLICATE` document is written whenever a payment with the same `unique_id` is re-delivered after already being marked `SUCCESS` (`finops_consumer.py:82-94`; the duplicate-guard body itself is a 2023 `root` commit, generalized by Vikas in Feb 2026 to cover both source tables instead of just one).

## B.5 Async / distributed

- **Idempotency, ICICI side (his):** `INSERT IGNORE` against `uq_icici_brs_dedup` makes both the ~30-minute webhook resend behavior and repeated statement re-pulls safe to replay, with a documented NULL-`utr_no` exemption for cash/CDM transactions (MySQL treats `NULL` as distinct in a unique index) — the statement poller falls back to `TRANSACTIONID` specifically to keep that key populated and stable (`statement_icici.js:200`).
- **Idempotency, UPI-payment side (his):** exact `unique_id` lookup against a pre-created pending row, with a status-based duplicate guard (`== SUCCESS` -> log-and-skip) rather than a DB constraint.
- **Retry:** `axios-retry` with 10 retries / 5000ms fixed delay wraps every outbound ICICI call in his poller (`statement_icici.js:227-233`) — and the file explicitly documents avoiding a bug present in the sibling `statement.js` (an undefined `log` reference at that file's line 362) rather than blindly copying it (`statement_icici.js:230`).
- **What is *not* here:** the UPI auto-verification matching logic described as "bank-statement match with a 10-paise tolerance, releasing the statement entry when a payment is removed" was searched for directly — `grep -rn` for `paise`/`tolerance`/`0.10`/amount-diff patterns across the entire `finservice` repo returned **zero matches**. It is not in this codebase. A related but architecturally separate service exists in the other repo (`cdms-one/upi/settlement_cron.py` and siblings, 1745 lines) — but he has **zero commits** anywhere in that directory. What he actually built on the UPI side is the exact-match/status-dedup mechanism above, which is real and substantial but is not the tolerance-matching reconciliation engine the phrase describes. Not verified further in this pass — if that mechanism exists, it is in neither repo examined here.

## B.6 Infrastructure

MySQL x2 pools, MongoDB, Kafka (`kafkajs` producer / `confluent_kafka` consumer against one shared topic name via `process.env.KAFKA_TOPIC` on both ends), Firebase Cloud Messaging (Admin SDK, service-account credentials — exists in `finopsConsumer/config.json`, contents not opened, see Rules). `.gitignore` excludes `*.env`, `config.json`, `*.pem`, `*.key`, `*.crt` — see B.12 for a gap in that protection.

## B.7 Reliability / performance mechanisms (his work)

- **Two different crypto schemes for the same bank, correctly kept apart:** the ICICI *pull* API uses a hybrid envelope (fresh AES-128/256 session key per request, RSA/PKCS1-wrapped; `statement_icici.js:53-84`), while the ICICI *push* webhook uses pure per-field RSA-4096/PKCS1 with no AES at all (`server.js:61-102`) — different BRS documents, different schemes, both implemented and not conflated.
- A **byte-length heuristic** (`server.js:95`) distinguishes ciphertext fields from plaintext ones in the webhook payload — a value is only treated as RSA ciphertext if it base64-decodes to exactly 512 bytes (one RSA-4096 block) — so the same handler works whether ICICI's encryption is switched on (prod) or off (UAT sample payloads).
- **Bank-remark parsing:** UTR/reference extraction from ICICI's free-text `REMARKS` field, whose reference position differs by rail (UPI/NACH at segment 2, IMPS/NEFT/RTGS at segment 1, IFT at segment 3, INEFT via a `~`-split, `UPITCC-REFUND` as a distinct prefix case), falling back to `TRANSACTIONID` when nothing parses (`statement_icici.js:136-151`).
- **Security-conscious logging:** the poller explicitly never logs the encrypted envelope or decrypted financial payload, only identifiers (`statement_icici.js:237-238`); the webhook strips `USERNAME`/`PASSWORD` from the payload before persisting it to `raw_data` (`server.js:229-231`).
- **Notification fan-out with per-failure isolation:** `NotificationService.notify()` (`notification_service.py:106-140`) iterates every device token a user has (not just one), dispatches each through a Strategy (`AppNotification`/`WebNotification`), and isolates failures per device so one bad token doesn't stop delivery to the user's other devices.
- **FCM failure handling is failure-mode-specific**, not a blanket `except`: `UnregisteredError`, `InvalidArgumentError`, `SenderIdMismatchError`, and `QuotaExceededError` are each caught and logged distinctly (`fcm.py`, `send()` method).

## B.8 Design decisions, trade-offs, known gaps

- Reusing the pre-existing (2023) SUCCESS-status duplicate-guard block unmodified while fanning `update_upi_payment_details` out to a second table (`cbm_upi_payment`) is a reasonable low-risk move, but it also means that block's behavior was never re-examined for the new source — and there is no test covering the CBM/sales-officer branch at all (see B.12).
- The Kafka producer (`kafkaProducer.js`, not his) connects and disconnects a new producer **per message** — a real throughput/latency cost under load that the consumer half of his feature inherits regardless of authorship.
- `send_payment_notif`'s `UPICOLL` branch (`finops_consumer.py:106-124`) keeps a commented-out legacy notification call "for backward compatibility" (`:111-112`) rather than deleting it — a minor cleanup opportunity.

## B.9 Numbers

**(a) Derivable from code, with source:**
- `statement_icici.js`: 294 lines, 100% his. `sql/icici_insta_alert.sql`: 49 lines, 100% his, 1 unique key (4 columns) + 3 secondary indexes.
- `notification_system/`: 345 lines total (166+39+140), 100% his.
- `server.js`: 511 lines total; his share 150 (29%), concentrated in a 45-line crypto block and a 91-line handler.
- `finops_consumer.py`: 181 lines total; his share 75 (41%).
- Retry policy (his): 10 retries, 5000ms fixed delay (`statement_icici.js:227-232`); pagination cap 100 pages (`:253`).
- RSA block size check: 512 bytes = one RSA-4096 block (`server.js:95`).
- Dedup key: 4 columns (`value_date, utr_no, transaction_amount, type`); 3 secondary indexes.
- UPI settlement microservice he has no involvement in: 1745 lines across 15 files, 0 commits from him.

**(b) Missing — exact questions to ask the user:**
- What is the actual production volume of ICICI webhook pushes and statement-pull rows per day — how often does the `uq_icici_brs_dedup` `INSERT IGNORE` actually fire in practice (i.e., how often does ICICI really resend within 30 minutes)?
- Is there a downstream job that reads `icici_insta_alert.processed`, and did you (Vikas) build it, or does it belong to someone else / a different repo entirely?
- Where does the 10-paise-tolerance UPI-statement matcher actually live, if it exists — a third repo not reviewed here? Worth naming it explicitly so it can be checked.
- What's the real device-token volume per user (is the "multiple devices per user" fan-out in `NotificationService.notify()` a common case or a rare one in production)?

## B.10 Candidate resume bullets (10, his verified work only)

1. **Built ICICI's bank-statement pull integration from scratch**, implementing the bank's hybrid RSA+AES envelope per its own BRS spec: a fresh AES session key per request, RSA/PKCS1 key-wrapping, and asymmetric IV handling that differs between request (IV in its own field) and response (IV prepended to ciphertext). Evidence: `finopsProducer/statement_icici.js:52-84` (294 lines, 100% own).
2. **Independently implemented ICICI's second, differently-encrypted channel for the same account** — the push webhook uses pure per-field RSA-4096/PKCS1, not the pull API's hybrid scheme — including a byte-length heuristic to distinguish ciphertext fields from plaintext ones so one handler serves both encrypted production traffic and plaintext UAT samples. Evidence: `finopsProducer/server.js:61-102,182-272`.
3. **Designed the bank-reconciliation dedup schema**: a 4-column unique key (`value_date, utr_no, transaction_amount, type`) plus `INSERT IGNORE` absorbs ICICI's ~30-minute webhook resends and repeated statement re-pulls, deliberately scoped by `type` so a push row and a pull-audit row for the same transaction coexist, with a documented NULL-`utr_no` exemption for cash/CDM transactions. Evidence: `finopsProducer/sql/icici_insta_alert.sql` (49 lines, 100% own).
4. **Wrote bank-remark parsing heuristics** to recover a stable transaction reference from ICICI's free-text `REMARKS` field, whose reference position varies by payment rail (UPI/IMPS/NEFT/RTGS/NACH/IFT/INEFT each place it differently), with a documented fallback. Evidence: `finopsProducer/statement_icici.js:136-151`.
5. **Generalized a single-source Kafka payment consumer to two payment channels**: extended the UPI-webhook consumer to look up a pending payment in `upi_payments` (salesman) and fall back to `cbm_upi_payment` (sales officer) before applying the existing success-status dedup guard, unifying two collection workflows behind one consumer. Evidence: `finopsConsumer/finops_consumer.py:61-104` (commit `e9aba9b5`).
6. **Designed and built a Strategy-pattern push-notification subsystem** from nothing: an abstract channel interface with App/Web concrete implementations, a device-token repository keyed by `(user_type, user_id, is_active)`, and FCM delivery with distinct handling for unregistered/invalid/mismatched-project/quota-exceeded token failures. Evidence: `finopsConsumer/notification_system/` (345 lines, 100% own).
7. **Wired the notification subsystem into the payment consumer's lifecycle** — one-time initialization at consumer startup, dispatch on successful payment confirmation — and extended the ORM's table registry so the feature's new tables (`upi_payments`, `device_tokens`, `cbm_upi_payment`) were queryable. Evidence: `finopsConsumer/finops_consumer.py:22-24,109-121,134-149`; `finopsConsumer/db.py:19-22,32-34`.
8. **Wrote a self-contained crypto correctness test** for the RSA+AES envelope using only Node's builtin `assert` (the repo has no test framework installed) — proves the hybrid round-trip locally by using the service's own keypair as both sides of the exchange, verifying the logic without needing the bank's real certificate. Evidence: `finopsProducer/test_statement_icici.js` (86 lines, 100% own).
9. **Built a standalone request-side encryption reference script** for exercising the envelope format against ICICI during UAT independent of the production poller. Evidence: `finopsProducer/scripts/icici_encrypt_sample.js` (71 lines, 100% own).
10. **Applied deliberate security hygiene to a bank integration handling live financial data**: request/response logging never includes the encrypted envelope or decrypted payload, only identifiers; the webhook strips credential fields (`USERNAME`/`PASSWORD`) from the payload before it is persisted. Evidence: `finopsProducer/statement_icici.js:237-238`; `finopsProducer/server.js:229-231`.

## B.11 Interview material

**1. "Why does the ICICI push webhook use different crypto from the ICICI pull statement API — same bank, same account?"**
Follow-up: what breaks if you apply the webhook's plain-RSA decrypt to the pull API's response? — *Accurate answer:* the pull response is one hybrid envelope, not per-field RSA ciphertext; trying to `privateDecrypt` the whole body as a single RSA block would throw immediately (wrong block size). The two channels are documented in two separate BRS specs from the bank and were implemented to each spec rather than assumed identical.

**2. "Your dedup key deliberately excludes the bank's own per-transaction reference number (`TRAN_ID`). Why would you *not* trust a bank-supplied reference field for uniqueness?"**
*Accurate answer, grounded in the schema comment:* the schema explicitly documents `TRAN_ID` as "NOT unique (can repeat)" (`icici_insta_alert.sql:11`) — some bank reference schemes are per-batch or per-instrument rather than strictly per-transaction. Trusting it for dedup would either silently drop genuinely distinct transactions that share a batch reference, or fail to catch real duplicates. The design instead falls back to a business-semantic composite key (when + which reference + how much + which channel).

**3. "There's no test covering the `cbm_upi_payment`/sales-officer branch you added to the consumer. What's the risk, and how would you catch a schema drift between `upi_payments` and `cbm_upi_payment` today?"**
*Honest answer:* none, currently — `finopsConsumer`'s only test file (`test_update_entry.py`) doesn't cover this path and isn't his. A column rename or type change on one table but not the other would only surface at runtime, likely as a Kafka message that fails silently into the generic `except:` in the consumer loop. This is a real, nameable gap worth volunteering rather than being asked about.

## B.12 Red flags

**Genuine technical/gaps:**
- No test coverage for the CBM/sales-officer branch he added to `finops_consumer.py`.
- `kafkaProducer.js` (not his) reconnects a fresh Kafka producer per message — a throughput cost the consumer side inherits.
- HDFC's `/instaalert` handler has a live `//TODO: (Optional) Need to validate hmac` (`server.js:181`) — HMAC is read but never verified, in the same file as his ICICI handler.
- **Secrets exposure independent of git:** `icici_private.txt`, `icici_public.txt`, `public_key_prod.txt`, `decrypt_icici_row5.js` (which embeds a full RSA private key inline, not loaded from env/file like the production code paths do), `actual_db`, and `bank_sent` are all confirmed **untracked** by git (`git status --porcelain` shows `??` for every one of them) — so git history is clean, but these sit as plaintext on disk in the working directory regardless, readable by anything with filesystem access to the checkout. Being untracked also means git has no authorship record for them at all; whoever's local checkout this is, they should be deleted (or the key rotated) independent of any resume question. No key material is reproduced anywhere in this document.

**Old-resume-claim accuracy:**
- *"UPI auto-verification (bank-statement match, tolerance)"* — searched exhaustively; not present in `finservice`. A related but distinct UPI settlement microservice exists in the other repo (`cdms-one/upi/`) with zero commits from him. What he actually built — exact-`unique_id` lookup plus status-based dedup, generalized across two payment sources, with a full notification subsystem behind it — is real, substantial, and arguably better interview material than the phrase on an old resume, but it is a different mechanism and should be described as such.
- If any past claim attributes the IDFC statement pull, HDFC integration, or the Kafka producer itself to him: none of the three have any commits from him.

---

# Section 13 — Tech stack evidenced in this code

**Area A (`cdms/batch/report.js` + `lib/`):**
- Language: plain JavaScript (ES5/ES6 mix, no TypeScript) — notable because it sits inside a TypeScript monorepo (`cdms/package.json`, name `ripplr-picklite-backend`, main `src/app.ts`).
- Runtime libraries (versions from `cdms/package.json`): `mysql2 ^2.2.5`, `aws-sdk ^2.876.0` (S3, SDK v2), `xlsx ^0.17.4`, `exceljs ^4.1.1`, `archiver ^5.3.2`, `bluebird ^3.7.2`, `moment ^2.29.1`.
- Storage: MySQL (2 pools, one read-replica), AWS S3 (2 buckets).
- No HTTP framework used in this file, despite `express ^4.17.1` being available in the same package.
- Testing: Node's built-in `node --test` runner for the `lib/` query-builder modules (his `invoiceMissing.js` included); `jest ^26.6.3` exists in the monorepo but isn't used here; `report.js` itself has zero tests.
- Scheduling: no in-process scheduler despite `@types/node-cron` being a dependency elsewhere in the same package — strongly implies external (ECS-task-style) scheduling for this specific script.

**Area B (`finService/finservice`):**
- `finopsProducer` (Node.js, `package.json` name `"idfc"`): raw `http` module (no Express); `axios ^0.26.1` + `axios-retry ^3.4.0`; `mysql2 ^2.3.3` (2 pools); `kafkajs ^2.2.4`; `moment`/`moment-timezone`; `uuid ^9.0.1`; `jsonwebtoken ^9.0.2`; `winston ^3.11.0` + `node-log-rotate`; Node's built-in `crypto` module for all RSA/AES work (no external crypto library). No test framework installed — the `package.json` "test" script is a stub; the two real test/reference scripts that exist run via plain `node file.js` with the builtin `assert`.
- `finopsConsumer` (Python 3): `Flask 2.2.3` (a side-thread healthcheck, not the main workload), `confluent_kafka==1.9.0`, `SQLAlchemy` (automap reflection, not declarative models) + `PyMySQL==1.0.2`, `pymongo==4.3.3`, `firebase-admin==6.3.0`.
- Cross-language bridge: a Node `kafkajs` producer and a Python `confluent_kafka` consumer talk through exactly one shared topic name (`process.env.KAFKA_TOPIC` / `config['kafka']['topic']`).
- Bank protocols implemented in this codebase: ICICI CIB Account Services Suite v2.5 (hybrid RSA+AES pull, his), ICICI InstaAlerts BRS (pure RSA-4096/PKCS1 push, his), IDFC (JWT + axios-retry + dynamic-IV AES, not his), HDFC (HMAC push, not his).
