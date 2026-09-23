# Numbers — what is on the resume, where each came from, and what I still need

## On the resume, verified from code or documents

| Number | Bullet | Source |
|---|---|---|
| 9 auth implementations, 2 estates | IAM | Design doc §2.1 — nine separate HS256 implementations enumerated |
| 12 tables, 3 token audiences | IAM | Design doc §5.1 table listing; audiences dms / cdms / cdms_collections |
| ~10,000 employees, ~30 group catalogs | IAM | Design doc §4.2 — the stated rationale for group-keyed over user-keyed caching |
| 14 brands, 22 parser configs | OBC ingestion | Count of JSON config files: 14 credit-adjustment + 8 cash-discount across 14 brand codes |
| 253 tests | OBC ingestion | `def test_` count across the three test files (102 + 143 + 8) |
| 26 tables | Cheque bounce | Feature-scoped `__tablename__` count (of 232 in the shared model file) |
| 65 REST endpoints, 9 blueprints | Cheque bounce | Route count across the blueprint tree mounted at `/v1/cbm` |
| 11-state lifecycle | Cheque bounce | The cheque-state enum |
| ~330s | Field collections | The prior cost recorded in your own fix commit message |
| 5 templates | Notifications | Wired entries in the strategy map (the enum has 7; 2 are unwired) |
| 19 report types | Reporting | 21 type branches in the report service, 2 commented out |
| 4-level fallback, 8-stage pipeline, 29 config models | Promise Engine | The geo search levels, buffer/cutoff stages, and registered config models |
| 5-minute cron baseline | Inventory sync | The pre-existing ERP snapshot interval (`projects/phase1/inventory_sync`). Replaced the weaker "202 status" figure on the resume. |
| 4 MongoDB collections, 8 reconciliation stages | Post-order | The order-management model index; the delivery-note handler's stages |
| 12+ sources, 6 route variants | Fan-in API | Distinct upstreams traced through the composition layer; 6 post-order routes |
| 18 modules, 84 REST endpoints | MyDesignation | Grep count; matches the 86 requests in your Postman collection (84 + 2 health) |
| 97 test files, 1,233 cases | MyDesignation | Vitest file and case count |

## Confirmed by you, 2026-09-22 — production observation, not code-derived

These are on the resume on your authority. None is derivable from the repositories, so if an
interviewer asks "where does that number come from?", the answer is your own production
observation — not a dashboard screenshot you can produce on the spot. Know that before you quote them.

| Number | Bullet | What it actually measures | Watch out for |
|---|---|---|---|
| **~35K adjustment entries/day** | OBC ingestion | Daily total of `obc_adjustment_entry` messages across all brands | It is a **daily total, not a per-file count**. Largest sample file on disk is 2,871 rows. |
| **17K+ invoice verifications/day** | Notifications | One verification message per invoice, ~17K invoices/day | Lead with the **derivation**, not the count. Sits at ~20% of a single consumer's 86,400/day ceiling. |
| **~50K requests/day** | Promise Engine | Inbound traffic to the EDD service | Worded as **service traffic**, not 50K delivery-promise computations. The split is unconfirmed. |
| **~7K events/day** | Inventory sync | ERP inventory webhook events (3–4K steady, 5–7K upper) | ⚠️ Resume quotes the **upper bound**. Steady state is 3–4K. Pair it with the 5-minute→realtime delta; the volume alone is modest. |
| **14.6K → 48.7K orders/month** | MyDesignation BFF | Shopify storefront orders, monthly | ⚠️ **Includes web orders.** Phrased as the volume the backend serves, never as growth the app caused. It is **3.3x / +234%**, not 250%. |
| **₹105 Cr/month** | Field collections | Collected via `collection_invoices`, 12 months Sep-25–Aug-26 (₹1,260 Cr total) | Reconciles to the instrument-level split within 0.01%. ₹3.93 Cr/working day. |
| **~16.5K daily outlets** | Field collections | Distinct outlets collected from per working day | 63.8K–82.7K distinct outlets/month. ~550 unique salesmen/day. |
| **100% of principal, ₹10.7 Cr** | Cheque bounce | 3,844 of 3,844 resolved cheques recovered full principal; zero written off | ⚠️ **Never quote "1,482 recovered vs 2,362 short-closed" — that reads as 39% and is wrong.** Short closes are capped at the ₹500 bounce charge by code. See `phase2/cheque_bounce.md`. |
| **~375 reports/day** | Reporting | `report_queue`, 12-month mean; range 333–452, peak 642 | 146,430 reports in 12.7 months, 192–344 distinct users/month. |
| ~~₹36 Cr/month, 55K transactions~~ *(pulled off the resume 2026-09-23 — three rupee figures competed; kept for interviews)* | Bank reconciliation | IDFC credit lines, Aug 2026, deduped by `transaction_number` | ⚠️ **IDFC, not ICICI** — the RSA+AES envelope on the same bullet is ICICI. Resume says "bank integrations" to avoid conflating them. Deduped: 11,775 duplicated UTRs in August. |
| **130 warehouses, 43.5K SKUs** | Promise Engine | Distinct active `serving_entities`; SKUs both Unicommerce-ACTIVE and present in `EdditemInventory` | The 43,556 is the engine's own INNER JOIN, not the 54,366 total rows. |
| **~2K logins/day, peak ~310/hr** | IAM | `logger.info(access_data)` at `user.ts:1462`, both estates | CDMS measured at 978–964/day, peak 155/hr; doubled to include DMS. The login route itself emits no log line. |

## Removed, not corrected

| Number | Was on | Why it is gone |
|---|---|---|
| ~~15K+ rows per upload~~ | OBC ingestion | Appeared in no artifact; largest real brand file on disk is 2,871 rows. Replaced by the confirmed ~35K/day, which you can stand behind. Also scrubbed from `phase2/obc_ingestion.md`, where it had been woven into the card's narrative in three places. |

## Numbers I need from you — these would materially strengthen bullets

_Five were answered on 2026-09-22 and are struck through below. Four of those are only **partly**
answered — the residual ask is spelled out on each._

**Ripplr**
1. ~~OBC: uploads per day.~~ **Partly answered:** ~35K entries/day confirmed. Still open — average and p95 rows per *single* upload, and files per day. (Query text I can give you; I will not run it.)
2. OBC: how many brands and distribution centres are live on the feature today?
3. ~~Cheque bounce: monthly volume and recovery split.~~ **Answered, and the framing was corrected:** 380–600 bounces/month, ₹0.95–1.5 Cr/month, **100% principal recovery** across ₹10.7 Cr. The count-based "recovered vs short-closed" ratio is misleading and must not be used.
4. Cheque bounce: nightly OCR scan volume, and real-world accuracy.
5. Field collections: measured p50/p95/p99 on the collection and invoice-list endpoints, before and after your fixes.
6. ~~Field collections: daily rupee volume.~~ **Answered:** ₹3.93 Cr/working day, ₹105 Cr/month, ₹1,260 Cr over 12 months. 21,900 invoices and ~10,500 payment transactions per working day.
7. ~~Notifications: actual WhatsApp send volume.~~ **Answered:** ~17K/day, one verification message per invoice at ~17K invoices/day. A WATI dashboard export would still turn this from your word into evidence.
8. Reporting: how is the report service actually scheduled in production, and at what interval?
9. **Partly answered:** ~375 reports/day, peak 642. Still open — production **row counts** for the largest report types, which is what would size the streaming-vs-chunking decision.
10. ~~IAM: logins per day and peak per hour.~~ **Answered without touching production myself — you ran it:** ~2K/day across both estates, peak ~310/hour. Note the route path emits no log line; the usable signal is `logger.info(access_data)` at `user.ts:1462`.

**Supertails**
11. ~~Promise Engine: calls per day.~~ **Partly answered:** ~50K requests/day confirmed as service traffic. Still open — the EDD-versus-cron-versus-healthcheck split, and p95/p99 on the cart endpoint.
12. ~~Promise Engine: warehouse count and SKU catalogue size.~~ **Answered:** 130 active warehouses/darkstores, 43,556 plannable SKUs.
13. Promise Engine: average and p95 shipments per order, and the out-of-stock rate.
14. Inventory sync: measured staleness before and after the realtime path. This is the headline number for that bullet and it is nowhere in code.
15. ~~Inventory sync: webhook calls per day.~~ **Answered:** 3–4K/day steady, 5–7K upper. Still open — snapshot page size and count, and the Cloud Scheduler job count.
16. Post-order: daily order volume through the pipeline, and how often unpredicted-shipment creation fires versus an exact match.
17. Fan-in API: requests per day and p95 latency on the post-order routes.

**MyDesignation**
18. Real production p95/p99 from CloudWatch or the load balancer, as opposed to the k6 figures.
19. Redis cache hit ratio — never measured, and the performance report leaves it blank.
20. ~~Monthly orders.~~ **Partly answered:** storefront grew 14.6K → 48.7K orders/month (Shopify, includes web). Still open, and this is the important one — **orders and MAU placed specifically through the app.** Without it the resume figure is context the backend serves, not impact it produced.
21. SQS volume per day, and whether the dead-letter queue has ever had depth.
22. Whether the rate-limit bypass flag is live in the deployed production image right now.

## Numbers deliberately kept OFF the resume

- MyDesignation k6 p95 figures (186ms browse, 341 req/s). Every run breached its own failure threshold, and the search-suggest endpoint failed 100% of checks in three runs. Quoting the clean numbers invites a question with a bad answer.
- "1,500+ problems solved." The Achievements section carries your ratings, which are stronger evidence.
- Line counts, commit counts and pull-request counts. They measure volume, not engineering.
