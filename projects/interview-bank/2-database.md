# Section 2 — Database Design, Indexing & Query Optimization

Targets across the resume: MySQL/InnoDB (Ripplr, Promise Engine), PostgreSQL (MyDesignation), MongoDB
(Supertails), and the ORMs on the skills line — SQLAlchemy, Sequelize, Prisma, Mongoose.

Pattern from every source: **almost every senior DB question is a race condition wearing a domain
costume.** Name the anomaly first (lost update, write skew, phantom, double-booking); the mechanism
(row lock, unique constraint, `ON CONFLICT`, version column) is secondary.

---

## A. InnoDB locking, isolation, concurrency

Targets: *Cheque Bounce* (recompute under row lock, `SKIP LOCKED`), *Field Collections*, *Reporting* (queue claim).

1. ⭐ 🔗 "Logs show two requests both read a seat as AVAILABLE before either committed. Why didn't `@Transactional` prevent it, and how do you redesign so a seat never sells twice?" — https://javabulletin.substack.com/p/spring-boot-interview-question-double · your recompute-under-lock design
2. ⭐ 🔍 "Why recompute the outstanding under `SELECT ... FOR UPDATE` rather than apply a delta? What does it cost per write?" — collections-salesman §11; ripplr-fin-cbm §8 · card `cheque_bounce.md`
3. 🔗 "Gap locks and next-key locks — when does a `FOR UPDATE` on a range block an insert you didn't expect?" — https://www.secondtalent.com/interview-guide/mysql/
4. 🔗 "Describe a deadlock you've actually seen and how you prevented it." — same · ✏️ have one: two recompute paths touching invoices in different orders
5. 🔗 "Isolation levels and the phenomena each prevents — then: 'what isolation level, and what anomaly does that still allow?'" (Razorpay follow-up) — https://usegreenroom.app/blog/razorpay-backend-engineer-interview-questions
6. 🔗 "Write skew with the on-call-doctors example — why snapshot isolation lets both through, and how SERIALIZABLE or `FOR UPDATE` fixes it." — https://pgdash.io/blog/isolation-anomalies-in-postgresql.html · https://www.cockroachlabs.com/blog/what-write-skew-looks-like/
7. 🔗 "Optimistic vs pessimistic under '10,000 users click Buy Now on the last ticket.'" — https://algomaster.io/learn/concurrency-interview/optimistic-vs-pessimistic-locking
8. 🔗 "Prevent overselling with 50 units and 1,000 concurrent attempts: locks vs isolation vs reservation queue vs distributed lock." (Meesho SDE-1) — https://medium.com/@jaydipdey2807/meesho-interview-experience-sde-1-backend-2f3176c6ebe7
9. 🔗 "Pessimistic vs optimistic vs distributed locking; schema follow-ups on scalability and constraints." (Flipkart SDE2) — https://www.geeksforgeeks.org/flipkart-interview-set-2-sde-2/
10. 🔗 "Build a multi-worker job queue on `SELECT ... FOR UPDATE SKIP LOCKED` — why does plain `FOR UPDATE` force single file?" — https://www.prisma.io/blog/you-dont-need-a-job-queue-postgres-already-has-skip-locked
11. 🔍 "Two replicas run the OCR scheduler. `SKIP LOCKED` claim, commit immediately to PROCESSING, reclaim by `updated_at`. Why commit *before* the work?" — ripplr-fin-cbm §11 P1
12. 🔍 "Why is the non-locking fallback restricted to SQLite?" — same: a bug can never silently double-process on MySQL
13. 🔍 "Your report-queue claim has no `FOR UPDATE` at all. When is it safe, and what enforces that?" — reports-and-finservice A.11 #2 ⚠️ nothing enforces it
14. 🔍 "`available_map_for_references` is non-locking, `available_for_reference` supports a locking read. Why the split?" — ripplr-fin-cbm §11: display vs consumption
15. 🔍 "Two services (Python and Node) recompute the same invariant on the same rows under lock. Which one is right if both run?" — §11 P4: both; whichever runs last
16. 🔗 "Advisory locks — when over a row lock, and what's the danger of a session-level one surviving a rollback?" — https://oneuptime.com/blog/post/2026-01-25-use-advisory-locks-postgresql/view
17. ✏️ "A resubmit deletes and re-inserts `payments` with new ids while the Python cron is mid-recompute on the old ids. Walk through the interleaving."

## B. Query optimization — the 330-second query and its relatives

Targets: *Field Collections* (the query fix, composite indexes, N+1), *Fan-In API* (N+1), *Reporting*.

18. ⭐ 🔍 "A correlated SUM subquery on an unindexed TEXT column, executed once per outer row. Explain why the cost was linear in result size and catastrophic at scale, and what 'batching' actually replaced it with." — collections-salesman §11 P5 · card `field_collections.md`
19. ⭐ 🔗 "Walk through optimizing a slow query end to end: EXPLAIN → diagnose → fix → verify." — https://www.designgurus.io/answers/detail/what-are-sql-query-optimization-interview-questions · ⚠️ the resume's `9s → 1.1s` has **no measurement** behind it; the ~330s figure is the only sourced number
20. 🔗 "Correlated vs uncorrelated subquery — when does the distinction matter for performance?" (Amazon/Google/Microsoft) — https://datarekha.com/interview/sql/correlated-vs-uncorrelated-subquery/
21. 🔗 "Rewrite a correlated per-row average as a JOIN or window function; show the O(n²) on 5M rows." — https://letsdatascience.com/blog/sql-cte-vs-subquery-interview-guide
22. 🔗 "How would you troubleshoot a slow-running subquery?" — https://interviewprep.org/subquery-sql-interview-questions/
23. 🔗 "Interpret EXPLAIN — which columns matter, and what does `type=ALL` under `Using where` tell you?" — https://www.secondtalent.com/interview-guide/mysql/
24. 🔗 "Composite indexes and column order — why does `(a, b)` not serve a query on `b`?" — same · ✏️ then: "which composite indexes did you add, in what order, and why?"
25. 🔗 "When is a full table scan better than an index?" — same
26. 🔗 "Covering index — what changes in EXPLAIN when the base table is no longer touched?" — designgurus (above)
27. 🔍 "Is your `cheque_suspense (fc_id, brand_id, invoice_no)` index redundant with the invoice uniqueness index?" — collections §11: different tables; the migration reasoned about *not* adding one on `collection_invoices`
28. 🔗 "Spot the N+1 in this ORM snippet and fix it with eager loading or batching." — https://ramakrishna-01.medium.com/top-10-n-1-query-problem-spring-data-jpa-hibernate-interview-questions-every-senior-developer-226eab68ba91
29. 🔗 "If query count scales with rows returned, it's N+1 and the fix is eager loading, not an index. A batch API usually leads to an N+1 on the server unless the RDBMS absorbs it." — https://www.infoq.com/articles/N-Plus-1/
30. 🔗 "Batch N order ids into one query — how does it change when the waybill comes from a different upstream than the order?" — https://thesimplifiedtech.com/blog/orms-and-the-n-plus-1-problem · your fan-in
31. 🔍 "Why can't a query on a TEXT column use an index the way VARCHAR can, and what would you have done instead of the subquery?" — ✏️ prefix index / generated column / denormalise the aggregate
32. 🔗 "Why can't you reference a window-function alias in the same query's WHERE?" — letsdatascience (above)
33. 🔍 "The GPS report multiplies both lat and lng deltas by 111000. Where is that wrong?" — reports A.11 #3 ⚠️ longitude shrinks by `cos(lat)`
34. 🔍 "The ageing `CASE/DATEDIFF` expression is duplicated in WHERE and SELECT. Cost, and fix?" — reports A.8
35. ✏️ "Show me the query plan for the invoice-list page *after* the fix. What's the new dominant cost?"

## C. Schema design — tables, ledgers, versioning, state

Targets: *Cheque Bounce* (26 tables, 11 states), *IAM* (12 tables), *Field Collections* (`master_payments`), *OBC*.

36. ⭐ 🔗 "Design a MySQL schema live for an open-ended business scenario." (Mindtickle) — https://leetcode.com/discuss/post/5411198/ · expect the cheque domain or IAM
37. 🔗 "Schema for an Uber-like rider/order system, with indexing follow-ups." (Zepto SE-2 / SDE-3) — https://leetcode.com/discuss/interview-experience/5710176/Zepto-se-2-backend-interview/ · https://enginebogie.com/interview/experience/zepto-software-development-engineer-3/209
38. 🔍 "26 tables for cheque bounce. Draw the five that carry the money. Which is append-only?" — ripplr-fin-cbm §4 · card `cheque_bounce.md`
39. 🔍 "12 tables for IAM. Which three matter, and why is there no scope table?" — iam-prd §3, §10: FC 7/9 and FC 14 are different id spaces
40. 🔍 "A state persisted on the row doubles as the permission lookup key (`SalesOfficerEditMode[curr_state]`). Clever or fragile?" — §8 ⚠️ `KeyError` on an unmapped state
41. 🔍 "`master_payments` is versioned with `parent_id` and `is_deleted`. Why not an audit table?" — collections §11 P1 · ✏️ and: "what's the query for 'current version of payment X'?"
42. 🔍 "You avoided a 7-column unique index by writing `attempted_count = obc_record.id`. What does that overload, and what would you do with a clean slate?" — obc §8 #8 ⚠️
43. 🔍 "`whatsapp_notification_logs.entity_id` is globally unique but invoices and cheques come from different sequences. Fix the key." — whatsapp §12 #3 ⚠️
44. 🔗 "Soft-delete/tombstone patterns — what uniqueness problem does a partial index solve once you soft-delete?" — https://johal.in/soft-delete-patterns-audit-design-guide
45. 🔍 "Ledger columns are `DECIMAL(15,4)` but outstanding is kept in whole rupees. Why?" — obc §11 Q8: to match Node's `Math.round`
46. 🔍 "Two engines, two config mechanisms, one MySQL, one repo. Why?" — ripplr-fin-cbm §8 ⚠️ TOML vs dotenv
47. 🔍 "No versioned DDL; automap models; `unique_key_hash` UNIQUE index unverified. What's the risk?" — obc §8 #10, §12 #9 ⚠️
48. 🔗 "MySQL vs Postgres at scale — the question that stumped a senior candidate. Defend your choice and name what breaks first." — https://shahzeb-shahid.medium.com/mysql-vs-postgresql-at-scale-the-database-question-that-stumped-me-in-a-senior-engineer-interview-74b6cf40114e
49. 🔍 "Why Postgres for MyDesignation but MySQL everywhere else? Name the one feature with no MySQL equivalent." — mydesignation §8: partial unique index
50. 🔍 "No foreign keys in the MyDesignation schema. Defend it." — §8: Shopify ids are the join keys
51. 🔗 "Zero-downtime: add a NOT NULL column with default to a 500M-row table at 8K writes/sec." — https://dev.to/stacknotice/zero-downtime-database-migrations-in-production-2026-51kl
52. ✏️ "Dead tables kept for rollback, Django admin still reads them. How long do you keep them, and who owns the drift job?" — iam §10

## D. PostgreSQL specifics

Targets: *Exactly-Once Order Creation*, *Caching & Identity*, *BFF* (Prisma).

53. ⭐ 🔗 "Partial index — good use case? Then build one so a second near-simultaneous checkout is a no-op." — https://www.secondtalent.com/interview-guide/postgresql/ · https://medium.com/little-programming-joys/unique-partial-indexes-with-postgresql-86e137905c12 · card `exactly_once_orders.md`
54. ⭐ 🔗 "Why doesn't `INSERT ... ON CONFLICT` suffer the SELECT-then-INSERT race, and which of two writers wins?" — https://wiki.postgresql.org/wiki/UPSERT · your conditional-UPDATE-rows-affected arbiter
55. 🔍 "Conditional UPDATE's rows-affected count as the sole arbiter. Why is that sufficient, and what's the second line on an exact tie?" — mydesignation §11 P1: `@unique` on payment id and Shopify order id; P2002 = lost
56. 🔗 "Two requests, same idempotency key, same instant — why does a UNIQUE constraint make it race-free where check-then-insert isn't?" — https://algomaster.io/learn/system-design/idempotency
57. 🔗 "Same key, different body the second time — what should the server do, and why store a hash of the original?" — https://brandur.org/idempotency-keys
58. 🔍 "Attach-or-block on a verified identifier via a UNIQUE constraint, not read-then-write. Walk the race it closes." — mydesignation §11 P3
59. 🔗 "REPEATABLE READ and phantoms in Postgres — how does it differ from MySQL's?" — secondtalent/postgresql (above)
60. 🔗 "Exclusion constraints — a use case." — same · ✏️ overlapping reservations
61. 🔗 "`FOR UPDATE` vs `FOR SHARE`." — same
62. 🔗 "You store raw webhook bodies for signature re-verification. Why might `jsonb` silently break that, and when do you keep `json`?" — https://thecodeforge.io/database/postgresql-json-support/ · https://unixy.io/blog/postgres-jsonb-trap/ ⚠️ jsonb normalises key order and whitespace
63. 🔗 "Prisma 7 with the pg adapter, Migrate deliberately unused, DDL hand-applied. What drift risk, and how do you detect it?" — https://github.com/prisma/orm/discussions/24571 ⚠️
64. 🔍 "Transactional DDL — why did that matter for hand-applied migrations?" — §8
65. 🔍 "`rejectUnauthorized: false` on RDS TLS. What is and isn't protected?" — §12 ⚠️
66. 🔗 "PgBouncer — role, and when N app-level pools should be consolidated." — https://www.secondtalent.com/interview-guide/postgresql/
67. ✏️ "The partial unique index is on `cart_id WHERE status IN ('created','verified')`. A customer's attempt fails, they retry, the old row is still `created` because the failure was a timeout. What happens?"

## E. MongoDB

Targets: *Post-Order State Modeling*, *Fan-In API*, *OBC* (Mongo entries).

68. ⭐ 🔗 "Order with line items and shipments moving through states — embed or reference, and what breaks first: 16 MB cap or unbounded arrays?" — https://oneuptime.com/blog/post/2025-12-15-how-to-choose-between-embedding-and-referencing-in-mongodb/view · card `post_order_write.md`
69. 🔍 "Why 4 collections and not one document?" — raw-vs-derived: `orders`, `orderPromises` (raw archive on success *and* failure), `erpDeliveryNotes` (raw dump), tracking
70. 🔍 "Positional `arrayFilters` targeting one shipment — why over a document rewrite, and what race does it *not* close?" — supertails-post-order §8, §11 #5 ⚠️ check-then-`$push` on same `uniqueKey`
71. 🔍 "Delivery-note match by `_id` not `shipmentId`. What bug returns if you revert?" — §11 #1: `SHIPMENT_<wh>_<n>` isn't unique after redelivery
72. 🔍 "`orderId` is indexed but not unique; new-order path is `findOne` then insert. Two concurrent deliveries?" — §12 ⚠️
73. 🔍 "Tombstones mean the document only grows. When does that bite, and what's the compaction story?" — §8 ✏️
74. 🔗 "'Reads and writes both get faster when you add secondaries.' True or false, why?" — https://www.toptal.com/mongodb/interview-questions
75. 🔗 "`$lookup` — the JOIN equivalent, and its limitations." — same
76. 🔗 "A candidate proposes `w:1` for speed. How do they recover an acknowledged write lost to rollback?" — https://dev.to/visualeaf/advanced-mongodb-interview-questions-for-senior-developers-in-2026-2hep
77. 🔗 "Unordered batches of 100 with one retry vs one large ordered `insertMany` — how does error handling change?" — https://www.mongodb.com/docs/manual/core/bulk-write-operations/ · obc §9: `insert_many` batched 100, unordered
78. 🔍 "No Mongo indexes declared in the OBC repo. What does the per-row `file_id` lookup cost at 35K/day?" — obc §12 #9, #12 ⚠️
79. 🔍 "`ensureOrderExists` sleeps a fixed 2000 ms after calling its own service. What replaces the sleep?" — post-order §12 ⚠️
80. 🔗 "Why Mongo instead of MySQL for this service?" (Zomato) — https://leetcode.com/discuss/post/6023375/Zomato-or-SDE-Backend-Intern-or-Nov-2024/
81. ✏️ "Mongoose 8 — what does `strict` mode do to a field the ERP started sending last week?"

## F. Connection pooling, read/write splitting, replica lag

Targets: *Promise Engine* (6+ pools), *Reporting* (write/read pools ×30), *Cheque Bounce* (SQLAlchemy read/master).

82. ⭐ 🔗 "Backend interview scenario: connection-pool exhaustion. Diagnose from active/idle/waiting counts." — https://www.newsbreak.com/news/4896648548367-backend-interview-scenario-database-connection-pool-exhaustion
83. 🔗 "Size a pool with `(cores × 2) + spindles` for a 4-core box; when does PgBouncer beat N app pools?" — https://www.techinterview.org/post/3233474194/system-design-database-connection-pooling-pgbouncer-hikaricp-pool-sizing-connection-limits-idle-timeout-performance/
84. 🔍 "6+ pools × 10 on App Engine, each instance opens all of them, no `max_connections` coordination. Do the arithmetic at 20 instances." — promise-engine-edd §12 #6 ⚠️ 🔗 https://cloud.google.com/sql/docs/mysql/quotas
85. 🔗 "`ConnectionAcquireTimeoutError` under load — in-flight transactions holding a connection across a network call, pool vs concurrency, multi-instance sharing. Tune it." — https://github.com/sequelize/sequelize/issues/17535 · https://sequelize.org/docs/v7/other-topics/connection-pool/
86. 🔗 "Writes to primary, reads to replicas via separate pools. A read lands on a lagging replica right after a write. What breaks?" — https://oneuptime.com/blog/post/2026-03-31-mysql-read-write-splitting-application-code/view · your write/read pool split
87. 🔗 "Route SQLAlchemy by HTTP verb. A POST redirects into a GET on a lagging replica." — https://medium.com/@gastaminza.aitor/a-master-slave-story-with-sqlalchemy-df8f8c84b786
88. 🔍 "Report service: write pool 30 + read pool 30, streaming with `highWaterMark`. Three 300k-row exports at once — what's held?" — reports A.4, A.7 ✏️
89. ✏️ "The salesman submits, then immediately lists — and the list reads from the replica. Do they see their submission?"

## G. Money, rounding, precision

Targets: *OBC* (₹1 phantom), *Notifications & GST* (Decimal bounded search), *Field Collections* (10 paise), *Post-Order* (COD split).

90. ⭐ 🔗 "`0.1 + 0.2 === 0.3`?" then "why not double for currency?" — https://github.com/30-seconds/30-seconds-of-interviews/blob/master/questions/floating-point.md · https://codemia.io/knowledge-hub/path/why_not_use_double_or_float_to_represent_currency
91. 🔗 "`round(2.675, 2)` → `2.67`. Why, and why dangerous for money specifically?" — https://www.evanjones.ca/floating-point-money.html
92. 🔍 "The ₹1 phantom at exactly .50 — where did it come from, and why is the fix 'derive the third from the other two'?" — obc §11 P1 · post-order §11 follow-up (`item_total = amount_to_collect − fee_component`)
93. 🔍 "Gross ÷ 1.18 gives a 1-paisa mismatch the portal rejects. Bounded search: three roundings, ±0.01/±0.02, ≤15 candidates. *Why those three, why that range, prove termination.*" — whatsapp §11 P1 ⚠️ the most probeable math on the resume
94. 🔍 "Why is the ₹500 proforma hardcoded but the tax invoice computed?" — whatsapp §8
95. 🔍 "10-paise UPI tolerance — why not exact, why not 1 rupee?" — collections §11 P3
96. 🔍 "COD split across shipments: proportional by net value, fixed denominator, remainder to the last shipment only when fully shipped. Why each of those three choices?" — post-order §8, §11 #3
97. 🔍 "Half-up rounds toward +∞. Banker's rounding? Why did you keep half-up?" — obc §11 Q8 ✏️
98. ✏️ "GST at 18% on ₹1. Show me the split to the paisa."

## H. ORM specifics

Targets: skills line — SQLAlchemy 2.0, Sequelize 6, Prisma 7, Mongoose 8.

99. 🔗 "Session vs Connection in SQLAlchemy." — https://interviewprep.org/sqlalchemy-interview-questions/
100. 🔗 "Lazy loading, then `selectinload` / `joinedload` to kill N+1." — same
101. 🔗 "Transactions and rollbacks in SQLAlchemy — where does the session boundary sit in a Flask request?" — same ✏️
102. 🔍 "Automap models over hand-applied DDL. What's not versioned?" — obc §8 #10 ⚠️
103. 🔗 "Prisma vs TypeORM vs Sequelize — why Prisma for a small, well-known schema?" — ✏️ from mydesignation §8: typed queries; adapter-pg, no Rust engine
104. 🔍 "Prisma P2002 — what is it, and why is it 'lost the claim' not 'error'?" — mydesignation §11 P1
105. 🔗 "Sequelize pool tuning: `max`, `idle`, `acquire`, `evict`." — https://sequelize.org/docs/v7/other-topics/connection-pool/
106. ✏️ "A Sequelize model default (1000g) and an application fallback (10000g) disagree. Which wins when?" — promise-engine-edd §12 #12 ⚠️
107. ✏️ "Mongoose 8 `arrayFilters` — write the update that pushes one tracking event onto exactly one shipment by waybill."
