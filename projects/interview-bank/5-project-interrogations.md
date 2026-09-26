# Section 5 — Deep-Dive Project Interrogations

Grouped by resume bullet, in the order they appear. Every project here is yours; the questions
interrogate the engineering, not the authorship.

**Legend**
- ⭐ = the question an interviewer who read this bullet will open with
- ⚠️ = a trap: the honest answer exposes a known gap from the code analysis. Know it before they find it.
- 📊 = a metric challenge on a number that is on the resume
- 🔗 = real question reported from an interview or interview-prep source (URL given)
- 🔍 = derived from the code analysis of your repository (file § given)
- ✏️ = constructed from a documented mechanism; no published interview source found
- **Card:** the Phase 2 card in `../phase2/` that carries the worked answer

---

## 📊 Metrics ledger — every number on the resume, and the question it invites

An interviewer's first move on any number is **"how did you measure that?"** The second is
**"what would change it?"** Know both for every row.

| Number | Bullet | Sourcing | The question you will get | Your defensible answer |
|---|---|---|---|---|
| **9 auth implementations, 2 estates, 12 tables, 3 token audiences** | IAM | Design doc | "Nine? Name a few and why they diverged." | DMS web, CDMS web, salesman PIN app, plus per-service HS256 verifiers; diverged because each estate resolves `user_id` against its own DB (4821 ≠ 7734). |
| **~10,000 employees** | IAM | Design doc estimate | "Active or total? Concurrent?" | Total identities; ~2K logins/day measured; peak ~310/hr. Say "approximately" — it is a stated approximation. |
| **~35K adjustment entries/day** | OBC | Your production observation | "Entries or rows? Per file?" | Kafka messages per day across 14 brands. Daily total, **not** per-file; files are a few thousand rows each. |
| **14 brands** | OBC | Config-file count | "What's brand-specific vs generic?" | 22 JSON parser configs; residual code branches for MRCO/DBR same-day rule, Britannia netting, PRD aggregation key. |
| **3-layer idempotency** | OBC | Code | "Name the three. Which is DB-enforced?" | S3 ETag → in-file `df.duplicated` → MD5 `unique_key_hash` lookup. ⚠️ The third is an application-level SELECT; a DB UNIQUE index on the hash is **not verified in the repo**. Say so. |
| **65 endpoints, 26 tables (card), 11 states** | Cheque | Code counts | "11 states — name the terminal ones and one illegal transition." | fully_recovered / short_closed terminal; DROP from PendingRealization is legal but flagged CRITICAL for review. |
| **100% of principal, zero written off, 4,527 cheques, ₹10.7 Cr** | Cheque | Your DB query | "Zero? Then what were the 2,362 short-closes?" | Short close is capped at the ₹500 bounce charge by code (`sales_officer.py:337`); max residual across all short-closes is exactly ₹500, mean ₹453. Principal is untouched by construction. **Never quote 1,482 vs 2,362 as a ratio.** |
| **₹105 Cr/month, ~16.5K daily outlets** | Collections | Your DB query, 12 months | "Reconciled how? What's a working day?" | `collection_invoices` by `collection_date`; instrument split reconciles to 0.01%; Mon–Sat, n=26 in Aug-26. |
| **9s → 1.1s (87%)** | Collections | ⚠️ **No source in code, commits or docs.** The only measured figure is a ~330s correlated-subquery fix from your commit message, with no after-number. | "How did you measure 9 seconds? p50 or p99? Where's the dashboard?" | This is the single most exposed number on the page. Either produce an APM/slow-log reading, or be ready to say the true story: a correlated SUM subquery on an unindexed TEXT column ran once per row (~330s), replaced by one grouped query per page. |
| **17K+ invoice verifications/day, 5 templates** | Notifications | Your production observation | "Messages or invoices? Ceiling?" | One verification message per invoice, ~17K invoices/day. Single consumer ceiling ~86,400/day because of a 1s sleep after each commit — so ~20% of one instance. |
| **~375 reports/day, 19 report types** | Reporting | `report_queue` table | "Peak? Concurrency?" | Mean over 12 months; peak 642 on 2026-02-19; 192–344 distinct users/month; peaks at 09:30 and 10:30 IST — which is why the global queue lock matters. |
| **₹36 Cr/month reconciled** | Reporting | IDFC Aug-26, deduped | "Coverage? Match rate?" | 55,069 txns; 85% of UPI+NEFT collections; UPI matches at 61%, NEFT 91%, IMPS 93%. ⚠️ **This is IDFC; the RSA+AES envelope on the same bullet is ICICI.** Do not let them fuse. |
| **~50K requests/day** | Promise Engine | Your observation | "All EDD computations?" | Service-wide inbound. The cron/webhook/health split is not confirmed — say "the engine sits behind ~50K a day" and do not decompose it. |
| **130 warehouses, 43.5K SKUs** | Promise Engine | DB query | "Total SKUs or plannable?" | 43,556 = Unicommerce-ACTIVE **and** has an inventory row — the engine's own INNER JOIN. Total rows are 54,366. Quote the join. |
| **4-level, 8-stage** | Promise Engine | Code | "Name the levels in order. Name stage 5." | Levels: pincode → H3/area → cluster → region-style fallback. Stages: SLA add, hyperlocal cutoff (replaces, not adds), static buffers, capacity buffer, tag buffer, rain buffer (fallback, not additive), day-skips, clock reset. |
| **5-minute → near-realtime, 3–7K events/day** | Inventory | Cadence from scheduler config; volume your observation | "Measured lag after?" | ⚠️ No measured post-change latency exists. Say "the cron still runs; the webhook adds a faster path." 3–4K steady, 5–7K upper. |
| **4 MongoDB collections, 8 stages** | Post-order | Code | "Why 4 and not 1?" | orders (lineItems + shipments), orderPromises (raw archive), erpDeliveryNotes (raw dump), plus tracking history. Separation is raw-vs-derived. |
| **12+ sources, 6 route variants** | Fan-in | Code | "Name eight." | Shopify GraphQL, Mongo orders, returns (ClickPost), revised EDD, COD→prepaid, pharmacy Rx, NDR/failed deliveries, pricing service, ERP notes, courier tracking, promise engine, attribution. 3 reads × app/web. |
| **14.6K → 48.7K orders/month** | BFF | Shopify | "App-attributable?" | ⚠️ **Storefront-wide, includes web.** Say "the backend serves a storefront that grew 3.3x." You do not have the app-only split. |
| **18 modules, 84 endpoints, 98 test files, 1,238 cases** | BFF | Counts | "Coverage?" | ⚠️ No coverage tool configured. Say "1,238 cases, in-memory Prisma fake, no DB in tests." Don't claim a percentage. |
| **~4.2K messages/day, zero failures** | Exactly-once | SQS metrics, 26h | "Zero over what window?" | 4,468 received / 4,468 processed / 0 failed over 26h (clickpost 4,494, razorpay 44 enqueued). |
| **~28K Shopify API calls/day** | Caching | Derived: hits × 2.66 calls/miss on 7 Shopify-backed families | "Hit ratio?" | ⚠️ System-wide **44.81%**; a curated 8-family subset is 65%; `product` is 19.6%. Quote the absolute count, never the 65%. Volunteer the 19.6% as the thing you'd fix. |

---

## RIPPLR

### Bullet 1 — Centralized IAM & RBAC

> *Unified 9 auth implementations across 2 estates into 12 tables and 3 token audiences for ~10,000
> employees, collapsing authorization to one Kafka-propagated Redis set check.*

**Card:** `../phase2/iam_rbac.md` · **Analysis:** `../findings/code-analysis/iam-prd.md`

⭐ **Opening:** "One person is `user_id 4821` in DMS and `7734` in CDMS. Walk me through how a
single login produces a token that is correct in both — and what stops a DMS token being
replayed against CDMS." 🔍 iam-prd §13 P1, follow-up 8

1. "Why not put the permissions in the JWT?" 🔍 §13 Q1 — expect the header-size answer (~7.6 KB vs nginx 8k) *and* the revocation-latency answer.
2. "Why group-keyed Redis sets rather than user-keyed? Do the math for 10,000 users." 🔍 §13 Q2
3. "How does a reader never see a half-written permission catalog during a version bump?" 🔍 §13 Q3 — versioned prefix, pointer flipped last, grace period.
4. "Kafka is at-least-once. A stale, lower-version catalog message arrives after a newer one. What happens?" ⚠️ 🔍 §10 gap 1 — the PRD does not specify a monotonic guard. Say what you'd add.
5. "IAM goes down at 11 a.m. What stops working, and what keeps working?" 🔍 §13 Q5
6. "Why MySQL-backed sessions instead of a stateless signed cookie or Redis?" 🔍 §13 Q6 — revocation is the only lever; no `jti`.
7. "You revoke a per-person `extra_perms` grant. How long until it takes effect?" ⚠️ 🔍 §10 gap 2 — it waits for token expiry unless the session is also revoked.
8. "How does SSO cross `dms.ripplr.in` → `cdms.ripplr.in` when localStorage is per-origin?" 🔍 §13 Q7 — `Domain=.ripplr.in` cookie, `SameSite=Lax`, CORS with credentials.
9. "Creating one person across three databases with no distributed transaction — walk through the outbox." 🔍 §13 P3, Q9
10. "The estate API succeeds but the response is lost. The worker retries and hits the estate's unique-email constraint. How does it recover the id?" ⚠️ 🔍 §10 gap 3 — unspecified. Design it on the spot.
11. "You had a shared hardcoded salt and no plaintext. How did you migrate hashes?" 🔍 §13 P4 — lazy re-salt on login, `legacy_salt` flag doubles as the coverage query.
12. "How did you cut over without touching 700+ hardcoded frontend gating references?" 🔍 §13 P5, Q12 — passthrough tokens, projection writer, equivalence test, rollback flag.
13. "Why HS256 passthrough with the estates' own secrets instead of RS256/JWKS?" 🔍 §10 — deferred; requires estate changes. Know it's a deferral, not a preference.
14. "IAM holds both estates' signing secrets. What's the rotation procedure?" ⚠️ 🔍 §10 gap 6 — none specified.
15. "A 4-digit PIN with no lockout policy. What's the brute-force exposure?" ⚠️ 🔍 §10 gap 8
16. 🔗 "How do you integrate RBAC with microservices so each service can validate without calling IAM?" https://www.pomerium.com/blog/iam-interview-questions-and-answers
17. 🔗 "RBAC leads to role explosion. How do you keep 12 tables from becoming 40?" https://climbtheladder.com/role-based-access-control-rbac-interview-questions/
18. 🔗 "A teammate reports session revocation is a no-op — the UI flips a column nothing reads. How do you test that revoke is enforced on the read path?" https://github.com/Senthil455/Atlas-Workforce-System/issues/170

📊 **Metric challenges:** "9 implementations — were they all HS256?" (yes, with different secrets); "12 tables — draw the three that matter"; "~2K logins/day — how did you count without request logging?" (`logger.info(access_data)` at `user.ts:1462`, the only call that fires per success; the route itself emits nothing).

---

### Bullet 2 — Financial Ingestion Pipeline (OBC adjustments)

> *Built an S3 → Lambda → Kafka → MySQL/MongoDB pipeline ingesting ~35K adjustment entries/day across
> 14 brands, with per-row transactions and 3-layer idempotency so partial failures never block a file.*

**Card:** `../phase2/obc_ingestion.md` · **Analysis:** `../findings/code-analysis/obc-adjustment.md`

⭐ **Opening:** "Every row is a financial write across four to seven tables. Why is the *row* the
unit of work and not the file — and what does that cost you?" 🔍 §11 Q1

1. "What stops the same adjustment being applied twice? Name all three layers and say which one the database enforces." ⚠️ 🔍 §11 Q2 — only the ETag and hash lookup are real gates; the SQL check is an application SELECT.
2. "Your MD5 hash normalises `9`, `9.0` and `9.00` to the same thing. Why, and what does it *not* normalise that it should?" 🔍 §11 Q3
3. "The consumer crashes mid-row. Walk through redelivery. Are your counters idempotent?" ⚠️ 🔍 §11 Q4, §12 #7 — `processed` can exceed `total`.
4. "An exception escapes `process_entry`. Is the offset committed?" ⚠️ 🔍 §12 #6 — yes, and the row stays `pending` with no DLQ.
5. "Is the file-completion check race-safe under parallel consumers?" ⚠️ 🔍 §11 Q5 — read-then-set; holds only because the constant key serialises on one partition.
6. "You use one Kafka key for every row. What does that do to your parallelism?" ⚠️ 🔍 §12 #2 — single partition, sequential. Say "isolated per row," not "parallel."
7. "Producer is `acks=1`, not idempotent. Describe the exact failover where an acknowledged message is lost." 🔍 §12 #8 🔗 https://akcoding.com/system-design/messaging-systems/kafka-interview-questions/
8. "Tell me about the ₹1 phantom." 🔍 §11 P1 — half-up rounding twice at exactly .50; fix was to derive `applied_amount` from two rounded values.
9. "Invoice `DIBL319092605708` went to −328 outstanding in production. Root cause?" 🔍 §11 P2 — the `Order.status == 'PD'` bypass predicate, not rounding. Bounded rule `-1 ≤ new_outstanding ≤ 0` replaced it.
10. "Britannia nets credit notes at invoicing. How did that double-adjust, and why did you fix it in code rather than config?" 🔍 §11 P3 — hash stability: changing `uniqueness_columns` would invalidate historical hashes.
11. "The salesman still sees the old outstanding after an adjustment. Why, and what did you have to do to the assignment rows?" 🔍 §11 P4 — and the 7-column unique index workaround via `attempted_count = obc_record.id`.
12. "Files stuck at 99%. What was the redesign?" 🔍 §11 P5 — failed/duplicate rows still flow through Kafka so counters converge.
13. "Why pandas for a 100-column brand export with a 9-line preamble and five columns named `Unit`?" 🔍 §11 Q6
14. "How do you add a brand? Which brand quirks needed code, not config?" 🔍 §11 Q7
15. "Why Decimal and half-up, and why is outstanding kept in whole rupees?" 🔍 §11 Q8 — to match the Node side's `Math.round`.
16. "How did you test a Lambda + Kafka + Mongo + MySQL pipeline with no infrastructure?" 🔍 §11 Q10 — `sys.modules` stubs, real brand JSON fixtures, static guard tests on pipeline order.
17. "Lambda has a 600s timeout. What's the largest file that fits, and what happens to row 1 if row 5,000 pushes you past it?" ✏️
18. "The `not_empty` filter operator is in a brand config. Is it implemented?" ⚠️ 🔍 §12 #3 — no; silent no-op.
19. "You log full DataFrames to CloudWatch. What's in them?" ⚠️ 🔍 §12 #5 — customer names and codes.
20. 🔗 "If the S3 notification also fires on the processed object you write back, what happens?" https://medium.com/analytics-vidhya/bulk-data-ingestion-from-s3-into-dynamodb-via-aws-lambda-b5bdc30bd5cd
21. 🔗 "Kafka guarantees delivery, not uniqueness — where does the consumer-side dedup table live and how big does it get?" https://dev.to/naresh_007/kafka-guarantees-delivery-not-uniqueness-how-to-build-idempotent-systems-1j6d

📊 **Metric challenges:** "35K per day — files per day? Rows per file?" (daily Kafka-message total; per-file average is **not** confirmed; largest sample on disk ~2,900 rows); "How long does one file take end to end?" (bounded by the single partition — be ready to say you'd key by `file_id`).

---

### Bullet 3 — Cheque Bounce Management

> *Built a 65-endpoint cheque-recovery platform that recovered 100% of principal with zero written off
> across 4,527 bounced cheques (₹10.7 Cr), modelling an 11-state lifecycle as declarative transition
> tables and recomputing balances under row lock against an append-only ledger.*

**Card:** `../phase2/cheque_bounce.md` · **Analysis:** `../findings/code-analysis/ripplr-fin-cbm.md`

⭐ **Opening:** "A salesman resubmits, and the payment rows are deleted and re-inserted with new ids.
Your ledger was tracking the old ids. How does the outstanding not drift?" 🔍 §11 P2

1. "Why recompute under a row lock rather than apply deltas?" 🔍 §8 — no stable identity to reverse a delta against; recompute is correct by construction.
2. "Two Flask replicas both run the OCR scheduler. What stops them double-processing a row, and what happens if one is killed mid-OCR?" 🔍 §11 P1 — `FOR UPDATE SKIP LOCKED`, immediate commit to PROCESSING, `fail_stuck_processing` reclaims by `updated_at`.
3. "Why is the plain-`SELECT` fallback restricted to SQLite?" 🔍 §11 P1 — so a bug can never silently double-process on real MySQL.
4. "Walk me through the 11 states. Which transitions are illegal? Which are legal but suspicious?" 🔍 §11 follow-up — `DROP` from `PendingRealization` is flagged CRITICAL, not blocked.
5. "`SalesOfficerEditMode[payment.curr_state]` — what happens on an unknown state?" ⚠️ 🔍 §8 — `KeyError` caught only by an outer handler; surfaces as 400 by accident.
6. "A sibling Node service maintains the same outstanding invariant on the same rows. How do the two stay consistent?" 🔍 §11 P4 — both recompute full values under lock; whichever runs last is correct; staged, flagged rollout.
7. "Sales Officer photographs a cheque, OCR fails. What happens to the submission?" 🔍 §11 P5 — OCR is an assist, never a gate.
8. "Why `MAX` not `SUM` when resolving a UTR's credit across two bank feeds?" 🔍 §11 follow-up — two feeds can record one wire; SUM doubles the budget.
9. "Your NEFT budget module is built and tested. Is it live?" ⚠️ 🔍 §12 — flagged off, not wired into the CBM gate. Say so.
10. "Why deny-list the released NEFT statuses instead of allow-listing?" 🔍 §8 — a new status counts against the budget by default; conservative direction.
11. "Why cap onnxruntime threads only at first engine build?" 🔍 §11 follow-up — process-level singleton.
12. "Why store `ocr_raw_json` on FAILED and NOT_A_CHEQUE, not just DONE?" 🔍 §11 follow-up
13. "`register_scan` pre-checks for an existing `(s3_key, user_id)` before insert. Why, if the UNIQUE constraint would catch it?" 🔍 §11 follow-up — cheap read for the poll-by-repost case; constraint is the backstop for the race.
14. "Two upload flows share `scanned_cheques`, and `master_pid` comes from two overlapping autoincrement spaces. How do reads never cross-match?" 🔍 §11 follow-up — every read scoped by `user_type`.
15. "Why does 30-day auto-close require `VERIFIED_BY_CASHIER`?" 🔍 §11 follow-up
16. "Your Kafka consumer commits the offset in the exception path. What happens to a failed cheque-bounce message?" ⚠️ 🔍 §8, §12 — it's lost; no DLQ; no cron fallback for cheque flows. **The single most concrete bug in the service. Own it.**
17. "Two scheduler idioms in one codebase — `BaseScheduler` ABC vs a standalone `BackgroundScheduler`. Why?" ⚠️ 🔍 §8 — sequencing; one predates the refactor.
18. "'3 bounces in 3 months blocks orders' — is that what the code does?" ⚠️ 🔍 §12 — code checks ≥2 in 90 days and calls an external blocking service. Don't quote 3/3.
19. 🔗 "Two refunds for the same payment arriving simultaneously — how do you handle it?" (Razorpay) https://usegreenroom.app/blog/razorpay-backend-engineer-interview-questions
20. 🔗 "Design a bill-payment flow that charges exactly once, with every transition written to a never-updated ledger table." (CRED) https://www.designgurus.io/answers/detail/what-to-expect-in-the-cred-system-design-interview
21. 🔗 "A workflow engine answers three questions at any point: current state, available transitions, and side effects on transition. How does yours persist so it resumes after a crash?" https://workflowengine.io/blog/workflow-engine-vs-state-machine/

📊 **Metric challenges:** the recovery-rate framing is the whole game — see the ledger row above. Also: "4,527 since when?" (2025-12-19); "monthly?" (380–600, ₹0.95–1.5 Cr); "how many principal rupees written off?" (zero — 3,844 of 3,844 resolved recovered full principal).

---

### Bullet 4 — Field Collections Workflow

> *Engineered collection resubmission with role-scoped verification and rejection rules and invoice
> amortization for ₹105 Cr/month collected across ~16.5K daily outlets; closed a duplicate-payment
> race with a Redis claim and reduced invoice dashboard latency from 9s to 1.1s (87%) by eliminating
> N+1 queries via batching and adding composite indexes.*

**Card:** `../phase2/field_collections.md` · **Analysis:** `../findings/code-analysis/collections-salesman.md`

⭐ **Opening:** "A cashier rejects one payment out of four. Why can't the salesman just edit and
resubmit that one row — and why does the backend rebuild the whole payment set?" 🔍 §11 P1

1. "Why delete-and-insert `master_payments` instead of update? How do you not lose the cashier's verification on the other three?" 🔍 §11 P1 — `parent_id` chain; copy-forward of `bank_statement_id`, `upi_unique_id`, verification status, settlement ids.
2. "Segregator rejection vs cashier rejection — what's the difference in what the salesman may edit, and where is it enforced?" 🔍 phase1 salesman card — `EDITAMOUNT` / `EDITDATA` / `EDITAMOUNTORDATA` / `SETTLE`; backend validates state, not the app.
3. "Your first cashier-reject fix also unlocked salesman edits. Why?" ⚠️ 🔍 §8, §12 — the same `EDIT*` states mean two things, disambiguated only by `action`; a regression test on invoice 38370569 caught it. Tell it as a debugging story.
4. "Why `SET NX EX` and not `SET` then `EXPIRE`?" 🔍 §11 P2 🔗 https://redis.io/docs/latest/develop/clients/patterns/distributed-locks/
5. "Redis is unavailable. What does `/complete` do?" 🔍 §8 — fails open. Defend it: blocking ₹3.9 Cr/day of collections on cache health is worse than a rare duplicate the DB catches.
6. "A `/complete` legitimately takes 70 seconds. Your key expires at 60. What happens to a retry?" 🔍 §11 follow-up — treated as new; the TTL is a heuristic, not a guarantee.
7. "Does the Redis claim dedupe two *different* payloads for the same invoice?" 🔍 §11 follow-up — no; the hash is over the payload.
8. "Why hash an extracted subset of the payload rather than the raw body?" 🔍 §11 follow-up
9. "Walk me through amortization. ₹40,000 cash, two cheques, one UPI, eight invoices — in what order is money consumed, and what makes a submission invalid?" 🔍 phase1 — cash → UPI → cheque → NEFT; leftover money invalidates.
10. "Why a 10-paise tolerance on UPI auto-verify, and why throw rather than leave it for manual review?" 🔍 §11 P3 — the silent-accept was the bug.
11. "The 269ST cash ceiling is cumulative per payer per day. Why do you need both a per-store-day check and a per-invoice check?" 🔍 §11 P4
12. "Both `redis` and `ioredis` are in `package.json`. Which one backs the lock?" ⚠️ 🔍 §12 — resolve before the interview.
13. "You have v1 and v2 of amortize.js side by side with different deploy pipelines. Which is live?" ⚠️ 🔍 §8
14. "The old path was Lambda at 30s/1024MB; the new one is Docker on EC2. Which endpoints moved and why?" 🔍 §11 follow-up
15. 🔗 "Mobile clients retry POST on timeout. Design the endpoint so a retry can never double-post: idempotency key, atomic Redis lock, 409 on concurrent duplicate, cached replay for a completed request." https://github.com/kunj-21/backend-interview-daily/issues/3
16. 🔗 "Redis can only be an optimization for idempotency, never the guarantee. Where does the real guarantee live?" https://dev.to/amitesh0512/payment-processing-idempotency-why-redis-cache-can-fail-in-production-4159
17. 🔗 "Is a `SET NX` lock an efficiency lock or a correctness lock, and does that match how you use it?" https://martin.kleppmann.com/2016/02/08/how-to-do-distributed-locking.html

📊 **Metric challenges — the latency number is the one to prepare for:**
- ⚠️ "**9 seconds to 1.1 — how did you measure it? Which percentile? Show me.**" There is no measurement of either figure in the repository, commits or documents. The only sourced fact is a ~330-second correlated-subquery fix in your own commit message, with no after-number. If you cannot produce an APM or slow-query-log reading, the defensible story is the mechanism: "a correlated SUM subquery on an unindexed TEXT column (`adjusted_bill_no`) executed once per outer row — linear in result size, catastrophic at scale — replaced with one grouped aggregate per page." 🔍 §11 P5, §12 #1
- "Which composite indexes, on which columns, and why that column order?" 🔍 §11 follow-up — the `cheque_suspense (fc_id, brand_id, invoice_no)` index, and why a similar one was *not* added on `collection_invoices`.
- "N+1 where, exactly?" — be specific about the loop.
- "₹105 Cr/month — what's the day-to-day range?" (₹1.71–5.11 Cr; Aug-26 avg ₹3.93 Cr/working day).
- "~550 salesmen and 16.5K outlets a day — how did you count?" (`COMPLETE_CREATE_REQUEST` log filter, unique `userId`; distinct outlets from `collection_invoices`).

---

### Bullet 5 — Notifications & GST e-Invoicing

> *Delivered a Kafka-driven WhatsApp service pushing 17K+ invoice verifications/day via WATI across 5
> templates, and solved paise-exact GST reconciliation with a bounded Decimal search clearing ClearTax
> IRN validation.*

**Card:** `../phase2/gst_einvoicing.md` · **Analysis:** `../findings/code-analysis/whatsapp-notifications.md`

⭐ **Opening:** "Your Kafka event carries only a salesman id and a date — no invoice ids, no amounts.
Why would you deliberately leave the payload empty?" 🔍 §11 P5

1. "Cashier verification spans days. Two verification events for one salesman-day race. What goes wrong if the event carries the invoice list?" 🔍 §8 — a receipt with incomplete outstanding, or two receipts.
2. "A live event and a cron sweep can both try to send the same receipt. How is it exactly-once without a distributed lock?" 🔍 §11 P2 — the DB is the lock: pending log row before send, `NOT EXISTS ... status IN (success, sent)` in both paths.
3. "A message throws inside your consumer. What actually happens to it?" ⚠️ 🔍 §11 P3, §12 #1 — offset is committed anyway; there's a comment saying not to. Collections self-heal via the sweep; **cheque flows do not**.
4. "Do you really need a DLQ?" 🔍 §11 follow-up — "it depends" answer: not urgently for collections; yes for cheques; cheaper fix is stop-committing-on-exception.
5. "Why does the consumer sleep 1 second after every commit?" ⚠️ 🔍 §12 #5 — undocumented. Know whether it's WATI rate-limiting or tight-loop avoidance before you're asked.
6. "What's the throughput ceiling, and why?" 🔍 §11 follow-up — ~86,400/day per instance from the sleep alone.
7. "Which design patterns are in the notification system?" 🔍 §11 — Strategy via `STRATEGY_MAP`; a light Facade. ⚠️ A second, dead Strategy implementation exists — mention it yourself.
8. "How do you add a sixth template?" 🔍 §11 follow-up — and the wart: routing lives in two places.
9. "Derive a GST-inclusive ₹500 into taxable + CGST + SGST that the portal accepts to the paisa." 🔍 §11 P1 — three roundings × ±0.01/±0.02 deltas, ≤15 candidates, `taxable + tax == gross` exactly.
10. "Why those three roundings and that delta range? What's the proof it terminates?" ⚠️ 🔍 ripplr-fin-cbm §12 — the single most probeable piece of math on the resume. If you can't explain the *why*, lead with the eligibility-gate side instead.
11. "Why is the ₹500 proforma hardcoded but the tax invoice computed?" 🔍 §8 — fixed amount vs varying partial recovery.
12. "A bounce charge is recovered over three payments. How do you not invoice the same money twice?" 🔍 §11 P4 — invoice the delta net of prior successful IRNs, above a ₹1 noise floor.
13. "ClearTax is down when a tax invoice is due. What's persisted, what's null, how do you retry?" 🔍 §11 follow-up
14. "Why is IGST still in the schema if it's disabled?" 🔍 §11 follow-up
15. "`whatsapp_notification_logs.entity_id` is globally unique with no `entity_type` in the key. Invoice and cheque ids come from different sequences. What happens on a collision?" ⚠️ 🔍 §12 #3
16. 🔗 "How do we prevent duplicate notifications on top of at-least-once delivery?" https://www.hellointerview.com/learn/system-design/problem-breakdowns/notification-system
17. 🔗 "One merchant's endpoint errors constantly — how do you stop that blocking every other merchant's queue?" (Razorpay) https://spacecomplexity.ai/blog/razorpay-system-design-interview
18. 🔗 "Why does `round(2.675, 2)` give `2.67`, and why is that dangerous for money specifically?" https://www.evanjones.ca/floating-point-money.html

📊 **Metric challenges:** "17K messages — measured where?" (one per invoice; ~17K invoices/day; your observation, no WATI export yet); "5 templates — the enum has 7." (two are unwired; say five wired).

---

### Bullet 6 — Reporting & Bank Reconciliation

> *Shipped a reporting platform serving ~375 reports/day across 19 report types, streaming and
> chunking writes to S3, and bank integrations reconciling ₹36 Cr/month over an RSA+AES envelope with
> a dedup key making resends idempotent.*

**Card:** `../phase2/reports_and_banking.md` · **Analysis:** `../findings/code-analysis/reports-and-finservice.md`

⭐ **Opening:** "Your outstanding report hit `LIMIT 100000` in production and you bumped it to
300000. What happened to row 100,001 before that, and what's the durable fix?" 🔍 A.11 #1

1. "What does an in-memory `json_to_sheet` do to task memory at 300k rows vs 100k?" 🔍 A.11 #1 — and why the streaming `WorkbookWriter` bounds memory regardless.
2. "When do you stream and when do you chunk? What decides?" 🔍 A.2 — streaming for unbounded row counts; chunking (5-day windows) when the query itself must be bounded.
3. "A stuck `inprogress` report of any of the 19 types blocks all 19. Minimal fix without a rewrite?" 🔍 A.11 #2 — heartbeat/`updated_at`, reclaim after N minutes.
4. "Your queue claim is `SELECT` then `SELECT LIMIT 3` then per-row `UPDATE` — no `FOR UPDATE`. When is that safe?" ⚠️ 🔍 A.11 #2 — only under the invariant of one running process, which the code can't enforce.
5. "A worker is killed mid-report. What's the blast radius?" ⚠️ 🔍 A.12 — the entire queue wedges; no lock release on crash.
6. "15 of 19 handlers have a silent `LIMIT`. What does the user see?" ⚠️ 🔍 A.8 — a partial report marked processed, indistinguishable from complete.
7. "Walk through the GPS distance check. Why `111000`, and where does it stop being accurate?" ⚠️ 🔍 A.11 #3 — longitude shrinks by `cos(latitude)`; ~6% overstated at 20°N; fine for 500m, not beyond.
8. "Why does the ICICI push webhook use different crypto from the ICICI pull API — same bank, same account?" 🔍 B.11 #1 — two BRS specs; hybrid envelope vs per-field RSA; applying one to the other throws on block size.
9. "Your dedup key deliberately excludes the bank's own `TRAN_ID`. Why wouldn't you trust a bank reference for uniqueness?" 🔍 B.11 #2 — schema comment: "NOT unique (can repeat)"; composite of when + reference + amount + channel instead.
10. "The IDFC feed carries each UPI transaction twice — bank line and virtual-account line sharing a UTR. How did you find that and what did it do to your numbers?" 🔍 NUMBERS — 11,775 duplicated UTRs in August; always quote deduped.
11. "UPI matches at 61% but NEFT at 91%. Why the gap, and what would close it?" ✏️ — be ready with a hypothesis (UTR format variance, timing, partial amounts).
12. "IFT, Cash and blank-type rows never match. Should they be in the denominator?" 🔍 NUMBERS — no; ₹15.5 Cr of non-collections.
13. "HDFC's handler has a `TODO: validate hmac` and reads the HMAC without verifying it. What's the exposure?" ⚠️ 🔍 B.12
14. "The Kafka producer connects and disconnects per message. What does that cost under load?" ⚠️ 🔍 B.8
15. "There's no test on the sales-officer branch you added to the consumer. How would a schema drift between `upi_payments` and `cbm_upi_payment` surface?" ⚠️ 🔍 B.11 #3 — at runtime, silently, into a bare `except:`.
16. 🔗 "Refactor a 500k-row CSV export from OOM to a streamed DB-cursor pipeline with proper backpressure." https://github.com/kunj-21/backend-interview-daily/issues/8
17. 🔗 "Ignoring `.write()`'s `false` return quietly turns streaming into an unbounded buffer. Why does `stream.pipeline()` matter on client abort?" https://blog.master.dev/your-node-js-streams-arent-backpressuring-theyre-silently-eating-your-memory/
18. 🔗 "A card payment shows captured tonight but doesn't land in the settlement file until T+2. How does your reconciliation handle the asymmetry?" https://www.formance.com/blog/financial-operations/account-reconciliation-patterns-for-high-volume-fintech
19. 🔗 "Prove the books are correct after an incident — detect silent drift between the aggregate and the ledger." (Coinbase) https://prachub.com/interview-questions/design-a-bank-account-ledger

📊 **Metric challenges:** "375/day — how scheduled?" (⚠️ no cron in the code; it's a one-shot script with a DB-level queue lock; scheduling is external); "largest report row count?" (unknown — open item); "₹36 Cr — which bank?" (IDFC; the envelope is ICICI — **keep them apart**).

---

## SUPERTAILS

### Bullet 7 — Delivery Promise Engine

> *Architected the EDD service behind ~50K requests/day across 130 warehouses and a 43.5K-SKU
> catalogue, with a 4-level geographic fallback, a cross-cluster tracker preventing double-promised
> stock, weight-based bin-packing, and an 8-stage buffer pipeline.*

**Card:** `../phase2/promise_engine.md` · **Analysis:** `../findings/code-analysis/promise-engine-edd.md`

⭐ **Opening:** "The same warehouse appears in two clusters for one request. Each level of your
fallback fetches its own warehouse list. What stops one warehouse's stock being promised twice?" 🔍 §11 P1

1. "Walk through `globalWarehouseAllocations`. What's threaded by reference, and what does `availableQty` subtract?" 🔍 §11 Q2
2. "A SKU is 70% covered after all four levels. What does the customer see?" 🔍 §11 P2 — fully OOS, by policy. Defend "no partial promise."
3. "How do you split one SKU's quantity across warehouses without losing or duplicating a unit?" 🔍 §11 P2 — `remainingQty` in priority order; leftovers via `updatedSkuVsQty`; found only at exactly zero.
4. "Your bin-packing is first-fit over exploded units. How far from optimal can that be, and what about a single unit heavier than the cap?" ⚠️ 🔍 §11 P3 🔗 https://www.geeksforgeeks.org/dsa/bin-packing-problem-minimize-number-of-used-bins/ — no clamp for an over-cap unit.
5. "A cutoff crosses midnight IST and you have no timezone library. How?" 🔍 §11 P4 — +5.5h epoch shift, compare time-of-day string, hard-pin the clock with `setHours`.
6. "Rain buffer and a manual static buffer both apply. Additive?" 🔍 §11 P5 — no; rain is a fallback. Defend it against "what if the manual buffer was small and the storm was huge."
7. "Name the 8 stages in order. Which one *replaces* rather than *adds*?" 🔍 §11 Q1 — hyperlocal cutoff replaces SLA addition; day-skips need a post-hoc clock reset.
8. "Static buffer vs capacity buffer — which is written to per order?" 🔍 §11 Q7
9. "How does a shipment pick its cutoff?" 🔍 §11 Q8 — weight → SLA row → `delivery_type` → cutoff.
10. "How do you keep query count bounded across a 20-item cart?" 🔍 §11 Q11 — one `Promise.all` of per-warehouse config; `calculateSingleEDD` only filters in memory.
11. "A SKU's weight matches no SLA row. What does the caller see?" ⚠️ 🔍 §12 #8 — nothing; it silently disappears.
12. "Missing pincode returns HTTP 500. Why, and what does that do to your alerting?" ⚠️ 🔍 §12 #9
13. "`/v2/warehouse-edd` does `res.send(e)` on throw. What leaks?" ⚠️ 🔍 §12 #14
14. "How many MySQL pools does this service open, and against what `max_connections`?" ⚠️ 🔍 §12 #6 — 6+ pools × 10, no coordination. 🔗 https://cloud.google.com/sql/docs/mysql/quotas
15. "There are zero automated tests on a pipeline whose branches multiply. What's the regression story?" ⚠️ 🔍 §12 #10 — own it; say what you'd test first.
16. "Same warehouse, two clusters, different priorities — dedupe or keep?" 🔍 §11 Q9 — keep; dedupe only on exact warehouse+cluster.
17. "Legacy callers need the old response shape. How do you serve it without two engines?" 🔍 §11 P6 — strangler: same v2 functions, pure field mapping.
18. "`H3IndexingService.buildSLAMatrix()` runs on every lat/lng request. Does anyone read the result?" ⚠️ 🔍 §12 #13 — no.
19. "`ServingEntity.max_shipment_weight` defaults to 1000g in the DB and 10000g in code. Which wins?" ⚠️ 🔍 §12 #12
20. "`app.yaml` is two lines. What happens under a traffic spike?" ⚠️ 🔍 §12 #11 — no `automatic_scaling` block.
21. 🔗 "Design dark-store inventory and order routing: data models, store selection, reservation, release, dispatch, peaks." (Zepto) https://www.designgurus.io/answers/detail/what-to-expect-in-the-zepto-system-design-interview
22. 🔗 "Design a quick-commerce platform focusing on inventory and delivery routing." (Razorpay HLD) https://spacecomplexity.ai/blog/razorpay-system-design-interview
23. 🔗 "What happens if the dispatch service fails?" (Uber-style) https://www.systemdesignhandbook.com/guides/uber-system-design-interview/
24. 🔗 "10M users, 10K stock, 1000:1 read/write — if you cannot quote a number, you cannot defend a choice." https://singhajit.com/flash-sale-system-design/
25. 🔗 "Identify what breaks first at the new scale rather than 'add more servers.'" https://www.designgurus.io/answers/detail/what-to-expect-in-the-databricks-system-design-interview

📊 **Metric challenges:** "50K/day — EDD calls or everything?" (service-wide; don't decompose); "130 — active?" (distinct active `serving_entities` after removing a test row and two dups; 129 reconcile to inventory columns); "43.5K vs the 54K in the table?" (the engine's own INNER JOIN — plannable only); "p95 for a 5-shipment cart?" (⚠️ unknown — open item).

---

### Bullet 8 — Realtime Inventory Sync

> *Cut ERP inventory lag from a 5-minute cron snapshot to near-realtime over 3–7K events/day via a
> Pub/Sub webhook, and fixed silent stock corruption by separating absent-from-delta from genuinely-zero.*

**Card:** `../phase2/inventory_realtime.md` · **Analysis:** `../findings/code-analysis/promise-engine-inventory.md`

⭐ **Opening:** "SKU A changed in Bangalore, SKU B changed in Delhi, one webhook. Your writer zeroed
SKU A's Delhi stock. Walk me through exactly why the query succeeded with no error." 🔍 §11 P1

1. "Why was sharing one writer between the cron and the webhook the bug, not the reuse?" 🔍 §11 P1 — different data contracts: snapshot carries every warehouse, delta carries only changed ones.
2. "How did you *detect* it before you fixed it?" 🔍 §11 P1 — `source` tag, `matchedWarehouseName`, "real zero vs defaulted zero" diagnostic, same day.
3. "Why 202 and not 200?" 🔍 §11.2 — accepted, not completed; `message_id` returned for tracing.
4. "Why keep the cron at all?" 🔍 §11.2 — deltas can be lost, duplicated, reordered; the snapshot is the correctness reconciler and refreshes weights.
5. "qty=10 is retried and lands after qty=5. What does the row say?" ⚠️ 🔍 §11 P5 — 10. No ordering key. Say what you'd add: ordering key per SKU or a version compare-and-set. 🔗 https://cloud.google.com/pubsub/docs/ordering
6. "Staging and prod shared a subscription name. What did you see, and how did you find it?" 🔍 §11 P2 — Pub/Sub load-balanced each message to exactly one environment. ⚠️ Be precise on whether the *topic* was also split.
7. "Why no dead-letter topic?" 🔍 §11.2 — deliberate simplicity; the snapshot bounds the blast radius. Say what a poison message does today.
8. "Your ack/nack — is nack reachable for a DB failure?" ⚠️ 🔍 §11 P4 — no; the writer swallows DB errors and acks. Say "ack/nack wiring" and own the gap.
9. "You replaced `if (erpInventoryData)` with `erpInventoryData.message.data.filter(...)`. What happened on the next ERP 401?" ⚠️ 🔍 §11 P3 — `TypeError`, page crash. Introduced by you, replicated once, fixed on an unmerged branch. **Best "what did you get wrong" answer on the resume.**
10. "Redis is down. What does the mapping lookup return, and what does the delta path do with it?" ⚠️ 🔍 §11.2 — `{}`; the delta excludes everything (silent no-op); no DB fallback in that branch.
11. "Why `maxMessages: 1` per subscriber?" 🔍 §11.2
12. "Why one Pub/Sub message per webhook call rather than per item?" 🔍 §11.2 — simplicity; cost is the 100 KB body-parser limit upstream and no per-SKU ordering key.
13. "Multiple App Engine instances each run a subscriber. Cron pages interleave with deltas. How does it converge?" 🔍 §11 P5 — the snapshot; a stale page can regress a fresher delta until the next run.
14. "Why Pub/Sub rather than RabbitMQ or Kafka?" 🔍 §11.2 — already in the GCP stack, managed, no broker. Name what RabbitMQ would give you (per-queue retry/DLQ control) and what Kafka would (partition ordering).
15. "A 4.2 MB page of ~4,800 items × ~127 warehouses crashed an F2 instance. Where did the memory go?" 🔗 https://groups.google.com/g/google-appengine/c/LKiKSlqRsB4 ⚠️ the 256 MB / page-size figures are **not in the repo** — verify from App Engine metrics before quoting.
16. "The 'qty resolved to 0' diagnostic fires per item × warehouse on snapshot pages too. What does that do to Loggly?" ⚠️ 🔍 §8
17. 🔗 "Events arrive out of order — an update before its create, a cancellation after a completion. How do you prevent it?" https://oneuptime.com/blog/post/2026-01-24-message-ordering-event-driven/view
18. 🔗 "'Eventually consistent' is not an answer; it is the beginning of one." https://designgurus.substack.com/p/why-eventually-consistent-is-the

📊 **Metric challenges:** "5 minutes — where's that configured?" (Cloud Scheduler, outside the repo); "near-realtime — measured?" (⚠️ no; say the cron still runs and the webhook adds a faster path); "3–7K — steady or peak?" (3–4K steady, 5–7K upper).

---

### Bullet 9 — Post-Order State Modeling

> *Modelled the order lifecycle across 4 MongoDB collections, reconciling ERP delivery notes in 8
> stages that tombstone stale plans, courier webhooks targeting one shipment via positional arrayFilters.*

**Card:** `../phase2/post_order_write.md` · **Analysis:** `../findings/code-analysis/supertails-post-order.md`

⭐ **Opening:** "Why does your delivery-note exact-match look shipments up by Mongo `_id` and not by
`shipmentId`? What bug returns if you revert it?" 🔍 §11 #1

1. "Why tombstone with `mismatched:true` instead of delete?" 🔍 §8 — history, stable array indices for positional writes, later delivered-check. Cost: documents only grow; every reader must filter.
2. "Why does retiring a placeholder shipment empty `items` instead of removing the element?" 🔍 §11 #2 — two functions snapshot `order.shipments`, re-fetch, and write back by original index.
3. "The Promise Engine silently drops a SKU it can't plan. The app renders only shipment items, but `totalMrp` still bills it. What did you build?" 🔍 §8 — placeholder shipment via sorted `sku:qty` fingerprint; `promise`/`tracking` are `null` not `{}`; always appended last.
4. "Why `null` and not `{}` for the placeholder's promise?" 🔍 §11 follow-up — a truthy empty promise renders "within 2-3 days" for an item that isn't shipping.
5. "Two ClickPost webhooks for two different shipments of one order arrive together. Why `arrayFilters` over a document rewrite?" 🔍 §8 — atomic per-shipment; no full read-modify-write race.
6. "Two ClickPost webhooks with the *same* `uniqueKey` arrive together. What happens?" ⚠️ 🔍 §11 #5 — both pass the `$elemMatch` pre-check, both push; duplicate history entry. Say how you'd close it (atomic filter + `$addToSet`, or a unique compound index).
7. "`orderId` is indexed but not unique, and the new-order path is `findOne` then insert. Two concurrent Shopify deliveries?" ⚠️ 🔍 §12 — two documents. Own it.
8. "The live `/edd-actions` route has its idempotency check commented out; the `-old` route enforces it. Deliberate?" ⚠️ 🔍 §8, §12 — the append + `mismatched` strategy tolerates redelivery structurally. Be ready to defend that as a trade, not an oversight.
9. "`ensureOrderExists` calls back into its own service and sleeps a fixed 2000 ms. What's fragile?" ⚠️ 🔍 §12
10. "COD on a split order: how do you allocate the payable across shipments so the three displayed numbers always sum exactly?" 🔍 §8 — proportional by net item value, fixed whole-order denominator, `item_total = amount_to_collect − fee_component`, remainder to the last shipment only once fully shipped.
11. "Why key the COD remainder on a *sorted* `shipmentId`?" 🔍 §11 #3 — two endpoints build the array in different orders; the absorber must be deterministic.
12. "Shopify reports one line item across multiple fulfilments. How do returns not double-count?" 🔍 §11 #4 — display quantity decremented everywhere; return-shipment record created once per `(clickpostReturnId, sku)` via a `Set`.
13. "Order `ST332418412507`: COD + platform fees of 44 against a 30-rupee coupon. What went wrong in the old residual approach?" 🔍 §8 — under-reported the fee by 30; fees now capped at order total.
14. "The Shopify note update in the delivery-note webhook is fire-and-forget. Can Shopify and Mongo diverge?" ⚠️ 🔍 §11 follow-up — yes, silently, on a persistent Shopify outage.
15. "Six near-identical route handlers each carry their own retry wrapper. Why?" ⚠️ 🔍 §12
16. "Extend this to exactly-once end to end. What's the one thing you'd add?" 🔍 §11 follow-up — a durable idempotency key per delivery, checked and recorded atomically with the write.
17. 🔗 "An OMS is a long-running process manager dominated by a state machine and a saga, not a CRUD service with a state field. Events are delayed, duplicated, reordered." https://medium.com/@umesh382.kushwaha/designing-a-scalable-reliable-order-management-system-65a5646931c5
18. 🔗 "Embed or reference an order's shipments — and what breaks first at scale: the 16 MB cap or unbounded arrays?" https://oneuptime.com/blog/post/2025-12-15-how-to-choose-between-embedding-and-referencing-in-mongodb/view
19. 🔗 "Design a system for order events that arrive out of order, duplicated, or after a failed process." https://medium.com/double-pointer/system-design-interview-amazon-flipkart-ebay-or-similar-e-commerce-applications-35a0bc764421

📊 **Metric challenges:** "orders/day through this path?" (⚠️ unknown — open item); "how often does stage 7 create an unpredicted shipment vs exact-match?" (⚠️ unknown); "8 stages — name stage 7." (unpredicted-shipment creation).

---

### Bullet 10 — Customer-Facing Fan-In API

> *Built the backend-for-frontend composing 12+ sources into one response across 6 route variants,
> eliminating N+1 by batching order IDs and waybills into one query per source.*

**Card:** `../phase2/post_order_read.md` · **Analysis:** `../findings/code-analysis/supertails-post-order.md`

⭐ **Opening:** "One screen, twelve sources. One of them — say pharmacy — is down. What does the
customer see, and what decided that?" ✏️ 🔗 https://aws.amazon.com/blogs/mobile/backends-for-frontends-pattern/

1. "Where exactly was the N+1? Per shipment, per waybill, per what?" 🔍 phase1 — collect all order IDs / waybills first; one batched query per source.
2. "Batching per source still means 12 round trips. Why not one?" ✏️ — different upstreams, different keys; you batch *within* a source.
3. "How do you turn `DELIVERED` + a timestamp into 'Delivered on Tue, 3rd Sep'? Where does that logic live and why server-side?" 🔍 phase1 — one fan-in layer, six routes, message layer.
4. "Why server-side fan-in instead of letting the app call ten endpoints?" 🔍 §8 — consistency, one merge, Shopify quota.
5. "The AWB branch narrows `mongoOrder.shipments` to one. Why capture `allMongoShipments` first?" 🔍 §11 follow-up — the COD split needs every sibling for the denominator.
6. "Which of `formatShipmentDataV3` and `processShipments` is live?" ⚠️ 🔍 §12 — an older generation of the whole read pipeline is still exported. Confirm before you're asked.
7. "`updateLatestCPStatusCodeInPostOrderRes` exists in two files. Which is authoritative?" ⚠️ 🔍 §12
8. "How does 'Arriving by Tomorrow 10 PM' get its time — promise, revised EDD, or courier?" ✏️ — precedence order; be able to state it.
9. "Revised EDD overrides the promised date. What if the revision is *earlier* than the promise?" ✏️
10. "Pharmacy hides unreleased Rx items. If the Rx service times out, do you hide or show?" ✏️ — fail-open vs fail-closed on a customer-facing read.
11. "The pricing service supplies dynamic fee titles. If it's down, do you show a fee row with no title?" ✏️
12. "Same three reads exist as app and web variants. What differs?" 🔍 §12 — and why the retry wrapper is copied six times.
13. "p95 before and after the batching change?" ⚠️ 📊 — unknown; open item. Say what you'd measure and where.
14. 🔗 "If the query count scales with rows returned it's N+1, and the fix is eager loading, not an index." https://www.infoq.com/articles/N-Plus-1/
15. 🔗 "A dashboard fans out to independent widgets — should one slow widget blank the dashboard? `Promise.all` or `allSettled`?" https://www.greatfrontend.com/questions/quiz/how-is-promiseall-different-from-promiseallsettled
16. 🔗 "Name the failure cases before the interviewer asks, and say what you'd measure in production." https://medium.com/@umesh382.kushwaha/designing-a-scalable-reliable-order-management-system-65a5646931c5
17. 🔗 "A BFF's fan-out means any downstream failure can take down the whole BFF. What's your isolation?" https://aws.amazon.com/blogs/mobile/backends-for-frontends-pattern/

📊 **Metric challenges:** "12+ — name them" (see ledger); "requests/day?" (⚠️ unknown); "how many round trips per list page after the fix?" (one per source — be exact).

---

## MYDESIGNATION

### Bullet 11 — BFF Architecture

> *Built the entire backend powering a native app on a Shopify storefront scaling 14.6K → 48.7K
> orders/month — 18 modules, 84 REST endpoints, API and worker containers from one image. 98 test
> files, 1,238 cases.*

**Card:** `../phase2/bff_architecture.md` · **Analysis:** `../findings/code-analysis/mydesignation.md`

⭐ **Opening:** "Shopify already has an API. Why does the app need a backend at all?" 🔍 phase1 §2

1. "What does the BFF own that Shopify doesn't, and what did you refuse to duplicate?" 🔍 phase1 §2 — sessions, identifiers, OTP, payment correlation, tracking, wishlist, config, pincodes. Nothing Shopify stores.
2. "Shopify's GraphQL is cost-based, not request-based. How does that change how you batch?" 🔍 §11 P5 — `nodes(ids:)` up to 250 per call, "195 ids ≈ cost 25."
3. "You stripped two *working* live calls (Judge.me count, Kiwi chart) from the PDP instead of caching them harder. Why?" 🔍 §11 P5
4. "Why Postgres over MySQL for this schema specifically?" 🔍 §8 — partial unique indexes, jsonb, real enums, transactional DDL. Name the one feature with no MySQL equivalent.
5. "No foreign keys. Defend it." 🔍 §8 — Shopify ids are the join keys; Shopify is the system of record.
6. "No Prisma Migrate, DDL hand-applied. What drift risk does that create and how do you detect it?" ⚠️ 🔗 https://github.com/prisma/orm/discussions/24571
7. "One image, two commands. What's the failure mode when API and worker scale independently but share a broken dependency?" 🔗 https://www.adaface.com/blog/docker-interview-questions/ ✏️
8. "Why Vitest with `fileParallelism: false`?" ✏️ — and the story behind "tests never touch a real database" (a staging DB was once wiped by a test).
9. "1,238 cases and no coverage tool. What's your actual coverage?" ⚠️ 🔍 §8 — none configured. Don't guess a number.
10. "Zod validates the whole environment at boot and `process.exit(1)`. Why not fail lazily?" 🔗 https://sergiodxa.com/articles/using-zod-to-safely-read-env-variables
11. "`rejectUnauthorized: false` on the RDS TLS connection. What does that actually protect against?" ⚠️ 🔍 §12 — encryption without chain validation.
12. "No `helmet`. What headers are you not sending?" ⚠️ 🔍 §12
13. "The returns presigned-URL route authorises off request params, not the session. What can a logged-in customer do?" ⚠️ 🔍 §12 — query another customer's return URL with a guessed phone + order number.
14. "There's a rate-limit bypass hardcoded on for one IP. Is it deployed?" ⚠️ 🔍 §12 — the file's own comment warns against it; deployed state **not verified**. Know the answer before the interview.
15. "`/webhooks/gokwik` is routed but throws `NotImplementedError`. Why is it mounted?" ⚠️ 🔍 §12
16. "Your k6 runs all breached the `<1%` failure threshold and search-suggest failed 100% of checks. What happened?" ⚠️ 🔍 §12 — the polished report says "near-zero errors." Investigate before quoting any p95.
17. "Magic Checkout or native Razorpay SDK — which is live?" ⚠️ 🔍 §12 — your story and the code comments disagree; resolve it in your own words.
18. 🔗 "Most valuable when there are multiple distinct clients and frontend teams that need control over API contracts — does that describe you?" https://www.scaler.com/blog/what-is-backend-for-frontend-bff-pattern-use-cases/
19. 🔗 "A BFF doubles development cost when teams re-implement similar capabilities, and adds a hop. Why was it still right?" https://aws.amazon.com/blogs/mobile/backends-for-frontends-pattern/
20. 🔗 "Lambda to containers — migrate when >50K/day, 5–20 MB per invocation, or long-running. Where were you?" https://dev.to/alanwest/aws-lambdas-hidden-costs-when-to-migrate-to-containers-and-how-2h1n

📊 **Metric challenges:** "48.7K — app orders?" (⚠️ storefront-wide; say so); "84 endpoints — Postman has 86" (84 + 2 health); "18 modules — name six and the layering" (routes → controller → service → gateway; vendor SDKs quarantined in `gateways/`).

---

### Bullet 12 — Exactly-Once Order Creation

> *Guaranteed one order when the app's verify call and the payment webhook race, using a conditional
> UPDATE's rows-affected count plus a partial unique index; HMAC-verified webhooks settle off the
> request path at ~4.2K messages/day with zero processing failures, with DLQ redrive.*

**Card:** `../phase2/exactly_once_orders.md` · **Analysis:** `../findings/code-analysis/mydesignation.md`

⭐ **Opening:** 🔗 "The bank charged the customer, then your server crashed before writing the row.
What does the customer see?" (Razorpay) https://usegreenroom.app/blog/razorpay-backend-engineer-interview-questions

1. "Two writers, either order, or the same instant. Why is a conditional `UPDATE`'s rows-affected count sufficient as the sole arbiter?" 🔍 §11 P1
2. "What's the second line of defence on an exact tie?" 🔍 §11 P1 — `razorpayPaymentId` / `shopifyOrderId` are `@unique`; P2002 is treated as "lost the claim."
3. "Why is the claim released on a pre-create failure but *never* after Shopify returns an order?" 🔍 §11 P1
4. "Why does COD need a different mechanism than the claim column?" 🔍 §11 P1 — partial unique index on `cart_id`, unique only while the attempt is live; a failed attempt falls out so the customer can retry. 🔗 https://www.secondtalent.com/interview-guide/postgresql/
5. "Why an atomic conditional UPDATE instead of wrapping the whole thing in a transaction?" 🔍 §8 — avoids holding a lock across a network round trip to Shopify; works only because the state machine + uniques make each statement's precondition sufficient.
6. "Trace a Razorpay `payment.captured` end to end." 🔍 §11 P4 — raw-log before the signature gate, HMAC over raw bytes with a secret distinct from the API key, 401 on mismatch, filter, enqueue, 200.
7. "Enqueue throws. What do you return and why?" 🔍 §11 P4 — 503; Razorpay retries; nothing was processed.
8. "Worker throws after a successful enqueue. Walk receive attempts 1 through 6." 🔍 §11 P4 🔗 https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-dead-letter-queues.html
9. "Why a standard queue and not FIFO?" 🔍 §11 follow-up — consumers were built idempotent *first*; ordering was made unnecessary, not bet against. 🔗 https://www.svix.com/resources/faq/sqs-fifo-vs-standard/
10. "Name the specific ordering guarantee that would break if it *weren't* idempotent." 🔗 same
11. "Visibility timeout is 30s. Your handler takes 45s. What happens?" 🔗 https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-visibility-timeout.html
12. "`SQS_MAX_CONCURRENT_MESSAGES` defaults to 1. What would break at 10?" 🔍 §11 follow-up — nothing *should*; it's untested at that concurrency. "Should be fine" ≠ "measured to be fine."
13. "Why HMAC over the raw body and not the parsed JSON?" 🔗 https://didit.me/blog/webhook-security-hmac-signature-validation/
14. "A valid signature doesn't prove freshness. How do you stop a replay?" 🔗 https://dev.to/roxdavirox/hmac-proves-origin-not-freshness-replay-attacks-against-signed-apis-1e53 ✏️ — be honest about whether you check a timestamp.
15. "Razorpay is unreachable for 30s during checkout. What does the customer see?" 🔍 §11 follow-up — 8s timeout, zero retries, fresh `internalOrderRef` on retry, nothing charged.
16. "Timing-safe compares in four places, no shared helper. Why?" ⚠️ 🔍 §11 follow-up — duplicated; fair push.
17. "A handler crashes after claiming the idempotency key but before the side effect. What does the retry find?" 🔗 https://www.hooklistener.com/learn/webhook-idempotency-and-deduplication
18. 🔗 "What if the webhook is delivered twice?" / "What if two requests arrive at once?" (Razorpay) https://usegreenroom.app/blog/razorpay-backend-engineer-interview-questions
19. 🔗 "Your idempotency check is SELECT then INSERT. What breaks under two concurrent retries?" https://www.hooklistener.com/learn/webhook-idempotency-and-deduplication
20. 🔗 "The user tapped Pay twice on a flaky network. Does the system proceed with two payments?" https://hackernoon.com/system-design-interview-designing-payment-systems-follow-up-questions-and-probable-issues

📊 **Metric challenges:** "4.2K/day — what's in it?" (clickpost ~4,494, razorpay ~44 over 26h; ~174/h); "zero failures — over what window, and has the DLQ ever had depth?" (26h; ⚠️ DLQ history unknown).

---

### Bullet 13 — Caching & Identity

> *Built a two-layer read-through Redis cache with version-counter invalidation, cutting ~28K Shopify
> API calls/day, and a passwordless identity ledger where a unique constraint makes attach-or-block
> race-free and replay revokes the family.*

**Card:** `../phase2/caching_and_identity.md` · **Analysis:** `../findings/code-analysis/mydesignation.md`

⭐ **Opening:** "A size chart showed 'no chart' for an hour on a product that had one. Walk me
through the bug and the rule you wrote afterwards." 🔍 §11 P2

1. "Is 'never cache a failure' enforced, or just documented?" 🔍 §11 P2 — structurally, in `loadWithLock`, for every caller.
2. "Is the explicit negative-caching sentinel used anywhere?" ⚠️ 🔍 §11 P2 — no live call site. Say it plainly; it reads as self-aware.
3. "Two layers — what does each one stop, and why isn't one enough?" 🔗 https://bugfree.ai/knowledge-hub/dealing-with-cache-stampede-and-thundering-herd
4. "Redis is completely down during a spike. What happens to correctness, latency, and rate limits?" 🔍 §11 follow-up — correctness fine; every request pays Shopify latency with no stampede guard (the lock needs Redis); rate limiters fail open too.
5. "A *hanging* Redis vs an absent one — which is worse and how is the client tuned?" 🔗 https://www.newsbreak.com/news/4896650140630-redis-goes-down-should-the-application-fail
6. "Rate limits and OTP counters fail open; webhook HMAC and env validation fail closed. Where's the line?" 🔍 §8 table 🔗 https://nerdleveltech.com/fail-open-vs-fail-closed-hono-middleware-redis-tutorial
7. "Stripe says a rate limiter that can't reach its store should let requests through. Would you make a *payment* claim fail open?" 🔗 https://github.com/HweyTH/limigo/issues/4
8. "Version-counter invalidation — why bump a version instead of deleting keys, and why SCAN + UNLINK never KEYS?" 🔗 https://openillumi.com/en/en-redis-keys-danger-scan-use/
9. "Freshness comes from Shopify webhooks; TTL is a safety net. What's the exposure window if a webhook delivery fails?" 🔗 https://www.designgurus.io/blog/cache-invalidation-strategies
10. "Why read-through + webhook invalidation over write-through?" 🔗 https://levelop.dev/blog/caching-strategies-system-design-four-patterns-failure-modes
11. "System-wide hit ratio is 44.81%. A curated subset is 65%. Which do you quote and why?" ⚠️ 📊 — the absolute call count; the subset is cherry-picked and the excluded families hold 62% of misses. 🔗 https://redis.io/blog/why-your-cache-hit-ratio-strategy-needs-an-update/
12. "`product` sits at 19.6% despite a 900s TTL. Why, and would LFU help?" 🔗 https://redis.io/blog/cache-eviction-strategies/ — long tail of one-off PDP views; key spread, not TTL length.
13. "A viral product page — what's the hot-key story inside an otherwise healthy aggregate?" 🔗 https://www.hellointerview.com/learn/system-design/deep-dives/redis
14. "~28K calls avoided — how is that derived, and what's the denominator trap?" 📊 — hits × 2.66 calls-per-miss on the 7 Shopify-backed families; the "66% drop" is algebraically the hit ratio, so only the absolute count is defensible.
15. "Google sign-in email matches a phone-OTP account exactly. Merge?" 🔍 §11 P3 — never; blocked. "And a phone number seen only via People API?" — reclaimable by a real OTP, because Google never *proved* it.
16. "Why is that asymmetry deliberate?" ⚠️ ✏️ — no published question found; construct the answer: a recycled number would otherwise lock out its real owner.
17. "A spent refresh token is presented again. What happens to the rest of the family, and what does the user see?" 🔗 https://nhimg.org/glossary/refresh-token-reuse-detection/
18. "Why hash refresh tokens instead of issuing a longer-lived stateless JWT?" 🔍 §11 follow-up 🔗 https://www.techinterview.org/post/3233477260/revoke-jwt-oauth-interview-questions/
19. "Why 15 minutes for the access token?" 🔍 §11 follow-up
20. "RFC 9700 requires refresh tokens for public clients to be sender-constrained or rotated on every use. Do you comply?" 🔗 https://csharpstack.dev/09-security/refresh-token-rotation-and-revocation.html
21. "One family exchanged from a globally diverse set of IPs in an hour — would you catch it before a literal reuse happens?" 🔗 https://auth0.com/blog/refresh-token-security-detecting-hijacking-and-misuse-with-auth0/ ✏️ — honest answer likely "no."
22. "Why does the OTP verify-attempt cap fail open?" 🔍 §11 follow-up — failing closed locks everyone out on a Redis blip; the code is 10-minute, single-use.
23. "OTP counters: per phone, per IP, global — how do they interact so IP rotation doesn't bypass?" 🔗 https://undercodetesting.com/the-silent-otp-killer-how-missing-rate-limits-are-burning-down-your-authentication-walls-video/
24. "Store the OTP or a hash? Does it matter if someone gets an RDB dump?" 🔗 https://arkesel.com/securing-transactions-with-otp-apis-10-best-practices/
25. "The JWT header names its own algorithm. Why is trusting it dangerous?" 🔗 https://qaskills.sh/blog/security-testing-jwt-algorithm-confusion
26. "Same API for mobile and web. Should the refresh flow differ?" 🔗 https://www.techinterview.org/post/3233477260/revoke-jwt-oauth-interview-questions/

📊 **Metric challenges:** the hit-ratio trap (item 11) and the derivation (item 14) are the ones to rehearse. Also "0 `cache_degraded` over 26h — what does that event mean?" (Redis error → loader fallback fired).
