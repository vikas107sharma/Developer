# Section 1 — System Design & Low-Level Design

Domain-organised. Each question names the resume claim it targets, the Phase 2 card with the worked
answer, and where it came from (🔗 real source · 🔍 your code analysis · ✏️ constructed from a documented
mechanism). ⭐ marks the highest-yield questions; ⚠️ marks ones where the honest answer exposes a known gap.

Recurring pattern across every source: **senior rounds open with a concrete failure scenario, not
"design X."** The scenario *is* the filter. Practise the openers.

---

## A. Payments, checkout, exactly-once

Targets: *Exactly-Once Order Creation*, *Field Collections* (Redis claim), *OBC ingestion* (3-layer idempotency).

1. ⭐ 🔗 "The bank charged the customer, then your server crashed before writing the row. What does the customer see?" (Razorpay) — https://usegreenroom.app/blog/razorpay-backend-engineer-interview-questions · card `exactly_once_orders.md`
2. ⭐ 🔗 "Customer taps Pay, request times out on a flaky network, taps again — the first went through. Design so this can never double-charge." — https://newsletter.pragmaticengineer.com/p/designing-a-payment-system
3. 🔗 "Who owns the truth about whether this operation happened? What happens if two requests perform the check at the same time? What should the second do while the first is still running?" — https://thearchitectsnotebook.substack.com/p/ep-146-just-add-an-idempotency-key
4. 🔗 "Design the idempotency-key store, and say what happens to in-flight requests if that store goes down mid-request." (Razorpay) — https://spacecomplexity.ai/blog/razorpay-system-design-interview · ⚠️ your Redis claim fails open — defend it
5. 🔗 "The order settles exactly once whether the deferred webhook races the AJAX confirm or not — defend that as the core constraint." — https://dev.to/faisal_nadeem_752520c3e03/the-webhook-race-condition-that-changed-how-i-design-backend-state-45ge
6. 🔍 "Why an atomic conditional UPDATE and not a wrapping transaction across the Shopify call?" — mydesignation §8: no lock held across a network round trip; works only because state machine + uniques make each statement's precondition sufficient
7. 🔍 "COD has no payment id to key on. What's the mechanism, and why must a *failed* attempt fall out of it?" — partial unique index on `cart_id`, live-only
8. 🔗 "Two refunds for the same payment arriving simultaneously." (Razorpay) — same greenroom source
9. 🔗 "The bank call times out and you never learn the outcome. What's your reconciliation job?" (Razorpay) — same
10. 🔗 "Design Razorpay: order creation, capture, webhook delivery with retries, refunds, settlement, multi-PSP routing." — https://usegreenroom.app/blog/razorpay-backend-engineer-interview-questions · staff
11. 🔗 "Design a bill-payment flow that charges exactly once: state machine created→submitted→succeeded→failed→refunded, every transition in a never-updated ledger, client-generated idempotency keys." (CRED) — https://www.designgurus.io/answers/detail/what-to-expect-in-the-cred-system-design-interview
12. 🔗 "Design, at the class level, exactly-once semantics on top of an at-least-once transport." — https://www.techinterview.org/post/3233473584/lld-exactly-once-delivery/
13. 🔗 "So what does exactly-once actually buy you, and where does it stop?" — https://www.techinterview.org/post/3233477380/kafka-interview-questions/ · the trap word; know it dies at the DB / third-party boundary
14. 🔗 "A retried payout reusing the same idempotency key books the transfer twice, leaving a phantom. How?" — https://www.formance.com/blog/financial-operations/account-reconciliation-patterns-for-high-volume-fintech
15. ✏️ "Your field-collections claim is keyed on a hash of the payment payload. Two salesmen submit the same amounts against the same invoices at the same second from different phones. Is that a duplicate?" — card `field_collections.md`

## B. Order lifecycle, state machines, workflow engines, sagas

Targets: *Post-Order State Modeling*, *Cheque Bounce* (11-state), *Field Collections* (resubmission).

16. ⭐ 🔗 "An OMS is a long-running process manager dominated by the order's state machine and the saga coordinating it, not a CRUD service with a state field. Events are delayed, duplicated, reordered. Design it." — https://medium.com/@umesh382.kushwaha/designing-a-scalable-reliable-order-management-system-65a5646931c5 · card `post_order_write.md`
17. 🔗 "A workflow engine answers three questions at any point — current state, available transitions, side effects on transition. How does yours persist so it resumes after a crash?" — https://workflowengine.io/blog/workflow-engine-vs-state-machine/ · card `cheque_bounce.md`
18. 🔍 "Why model 11 states as a declarative transition table rather than if/else? What's legal-but-suspicious, and how do you surface it?" — ripplr-fin-cbm §11: `DROP` from `PendingRealization` logged CRITICAL, not blocked
19. 🔍 "The same `EDIT*` state values mean 'cashier handed it back' *and* 'salesman is mid-edit', disambiguated only by `action`. What bug did that cause and how would you redesign the state space?" — collections-salesman §8 ⚠️
20. 🔗 "Choreography vs orchestration for a saga. Compensating transactions. When is 2PC actually wrong?" — https://manojknewsletter.substack.com/p/the-saga-pattern-for-distributed · https://medium.com/@charleyjava/system-design-building-blocks-distributed-transactions-saga-outbox-retry-idempotency-and-5618fe7539a3
21. 🔗 "Design a system for order events that arrive out of order, duplicated, or after a failed process." — https://medium.com/double-pointer/system-design-interview-amazon-flipkart-ebay-or-similar-e-commerce-applications-35a0bc764421
22. 🔗 "Broker-grade correctness: a broker cannot lose an order or execute it twice. Idempotency key, order state machine, reconciliation against the exchange as source of truth." (Groww) — https://www.designgurus.io/answers/detail/what-to-expect-in-the-groww-system-design-interview · map to ERP-as-source-of-truth reconciliation
23. 🔍 "ERP delivery notes reconcile against planned shipments in 8 stages. Stage 7 creates a shipment nobody predicted. Stage 8 tombstones. Why tombstone, and what does every reader now have to remember?" — supertails-post-order §8
24. 🔍 "Tombstone-vs-delete forced you to *empty items* on a retired placeholder rather than remove the element. Why?" — §11 #2: positional writes after a re-fetch
25. 🔍 "Segregator rejection reopens everything; cashier rejection reopens one row with a server-decided edit mode. Why two rejection semantics, and where is it enforced?" — phase1 salesman card
26. 🔗 "Design a subscription-based commerce platform: recurring delivery, multiple stores, location constraints; microservices split, sync vs async, SQL vs NoSQL." (Flipkart SDE2) — https://www.geeksforgeeks.org/interview-experiences/flipkart-interview-experience-for-sde2-2-5-yr-exp/
27. 🔗 "Design BookMyShow: seat booking, users, payment flows." (Amazon L5) — https://roundz.substack.com/p/interview-experience-amazon-sde2-l5
28. ✏️ "A cheque goes PendingRealization → Bounced → PartiallyRecovered → Bounced again (second presentation). Does your table allow re-entry into a state? What happens to the ₹500 charge the second time?" — card `cheque_bounce.md`

## C. Inventory, delivery promise, geospatial, dispatch

Targets: *Delivery Promise Engine*, *Realtime Inventory Sync*.

29. ⭐ 🔗 "Design dark-store inventory and order routing: data models, store selection, reservation, release/correction, dispatch, traffic peaks." (Zepto) — https://www.designgurus.io/answers/detail/what-to-expect-in-the-zepto-system-design-interview · card `promise_engine.md`
30. ⭐ 🔗 "Design an inventory management system — race conditions and overselling are required discussion points." (Amazon) — https://prepaired.app/interview-questions/design-an-inventory-management-system
31. 🔗 "There's one seat left and Alice and Bob both want it. Pessimistic deadlocks? ABA under optimistic? Everyone wants the same resource?" — https://www.hellointerview.com/learn/system-design/patterns/dealing-with-contention
32. 🔗 "Flash sale: consistency under extreme contention, releasing expired reservations, millions arriving at once, fairness." — https://www.hellointerview.com/learn/system-design/problem-breakdowns/flash-sale
33. 🔗 "10M users, 10K stock, 1000:1 read/write. Redis primary loss, PG slowness, hot key on the SKU, bot waves. If you cannot quote a number, you cannot defend a choice." — https://singhajit.com/flash-sale-system-design/
34. 🔍 "Same warehouse in two clusters, four independent fallback levels. What stops double-promising?" — promise-engine-edd §11 P1: `globalWarehouseAllocations` threaded by reference
35. 🔍 "70% covered after all four levels → treated as fully OOS. Defend 'no partial promise.'" — §11 P2
36. 🔍 "Your writer treated 'warehouse absent from the delta' as 'quantity zero'. Design the writer so it can never do that again — with or without the `source` gate." — promise-engine-inventory §11.2: split `applySnapshot`/`applyDelta`, or per-item column lists
37. 🔗 "Read-modify-write on inventory is a textbook race because it isn't atomic. How did you eliminate it?" — https://medium.com/@chaturvediinitin/how-i-eliminated-inventory-race-conditions-in-a-production-e-commerce-system-2302ba81846b
38. 🔗 "Nearest-warehouse-within-N-km at scale. How do you keep location lookups fast, and what does H3 give you that a bounding box doesn't?" — https://www.systemdesignhandbook.com/guides/uber-system-design-interview/
39. 🔗 "Isodistance vs isochrone geofences for delivery zones; region-specific rule profiles." — https://nextbillion.ai/blog/dynamic-geofencing-for-grocery-deliveries · your 4-level fallback
40. 🔗 "Splitting an order into two cartons can drop each into a cheaper carrier bracket. When is splitting worth it?" — https://www.aaxisdigital.com/insights-blog/optimizing-ecommerce-solving-the-bin-packing-problem
41. 🔗 "First-fit-decreasing is fast but how far from optimal, and when do you accept that?" — https://www.geeksforgeeks.org/dsa/bin-packing-problem-minimize-number-of-used-bins/ · ⚠️ yours is first-fit over exploded units with no over-cap clamp
42. 🔗 "What happens if the dispatch service fails?" — https://www.systemdesignhandbook.com/guides/uber-system-design-interview/
43. 🔗 "Rate limiting and traffic peaks during promotions." (Zepto) — same designgurus/Zepto · map to capacity buffers
44. 🔍 "Rain buffer and manual buffer both want to delay. You made rain a *fallback*, not additive. A customer asks 'what if the manual buffer was 1h and the storm was 2 days?'" — §11 P5
45. ✏️ "A warehouse goes offline mid-day. How fast does the engine stop promising from it, and what promises already made are now wrong?" — card `promise_engine.md`
46. ✏️ "Two carts race for the last unit. Your engine promises both. Where — if anywhere — does the double-promise get caught?" — the tracker is per-request; cross-request is ERP's problem. Say so.

## D. Backend-for-Frontend & aggregation

Targets: *BFF Architecture*, *Customer-Facing Fan-In API*.

47. ⭐ 🔗 "Any downstream failure in a BFF's fan-out can take down the whole BFF. What's your isolation, and what does the customer see when pharmacy is down?" — https://aws.amazon.com/blogs/mobile/backends-for-frontends-pattern/ · cards `bff_architecture.md`, `post_order_read.md`
48. 🔗 "A BFF doubles cost when teams re-implement similar things, and adds a hop. Why was it still right here?" — same
49. 🔗 "BFF is most valuable with multiple distinct clients and frontend teams that need contract control. Does that describe your situation?" — https://www.scaler.com/blog/what-is-backend-for-frontend-bff-pattern-use-cases/
50. 🔍 "Shopify already has an API. What does the app need a backend for?" — phase1: aggregate, orchestrate third parties, own app-only data, protect Shopify's cost-based quota
51. 🔍 "Shopify's quota is cost-based. How does that change your batching?" — `nodes(ids:)` ≤250, "195 ids ≈ cost 25"
52. 🔗 "If query count scales with rows returned, it's N+1 and the fix is eager loading, not an index. Where was yours?" — https://www.infoq.com/articles/N-Plus-1/
53. 🔗 "A dashboard fans out to independent widgets. Should one slow widget blank the page? `Promise.all` or `allSettled`?" — https://www.greatfrontend.com/questions/quiz/how-is-promiseall-different-from-promiseallsettled
54. ✏️ "Twelve sources, batched per source, still twelve round trips. What's the critical path, and what would you parallelise vs serialise?"
55. ✏️ "The message layer turns `DELIVERED` into 'Delivered on Tue, 3rd Sep'. Why server-side and not in the app?"

## E. IAM, RBAC, authentication architecture

Targets: *Centralized IAM & RBAC*, *Caching & Identity*.

56. ⭐ 🔍 "One human, three incompatible user-id spaces, ids can't change (thousands of FKs). Design the token model." — iam-prd §13 P1 · card `iam_rbac.md`
57. 🔍 "Fresh permissions without an IAM call per request, revocation in seconds not a day, 8k header limit. Design it." — §13 P2: group ids + version in token; group-keyed Redis sets; Kafka fan-out + 15-min reconcile
58. 🔗 "Centralized auth service issuing tokens with roles; each microservice validates locally. How do you keep them fresh?" — https://www.pomerium.com/blog/iam-interview-questions-and-answers
59. 🔗 "Security is a layered authorization model where each layer answers a different question." — https://www.pegahelp.com/2026/09/pega-security-architecture-interview.html · 3 token audiences
60. 🔗 "Role explosion. How do you keep it from becoming 40 tables?" — https://climbtheladder.com/role-based-access-control-rbac-interview-questions/
61. 🔍 "Creating one person across three DBs with no distributed transaction. Outbox vs saga vs try/catch — why outbox?" — §13 Q9
62. 🔍 "Cut over without touching 700+ frontend gating references and five backend enforcement functions." — §13 P5: passthrough tokens, projection writer, equivalence test, rollback flag, drift job
63. 🔍 "Remove a shared hardcoded salt with no plaintext." — §13 P4
64. 🔗 "You need to add a NOT NULL column to a 500M-row table at 8K writes/sec with no maintenance window." — https://dev.to/stacknotice/zero-downtime-database-migrations-in-production-2026-51kl · map to backward-compatible IAM migration
65. 🔗 "Stateless has a 'database tax' — every request round-trips for context. When do you deliberately choose stateful?" — https://systemdr.systemdrd.com/p/stateless-vs-stateful-services-scaling · your MySQL-backed sessions
66. 🔗 "Senior engineers push all session data into Redis. Describe the 10% of cases where that's wrong." — same
67. 🔍 "Passwordless: phone OTP, email OTP, Google, Apple. Never merge. Design attach-or-block so it's race-free without read-then-write." — mydesignation §11 P3 · card `caching_and_identity.md`
68. 🔗 "Walk through everything between clicking 'Login with Google' and landing back. Where can an attacker intervene?" — https://www.techinterview.org/post/3233477260/revoke-jwt-oauth-interview-questions/
69. 🔗 "Design the OTP service end to end: code, Redis TTL, resend cooldown, attempt lockout — and what breaks if the check order is wrong." — https://github.com/kunj-21/backend-interview-daily/issues/7
70. 🔗 "Mobile and web share one API. Same auth for both?" — techinterview.org (above)
71. 🔗 "'Log out of all devices' via a per-user version counter in Redis — implement it, then do it for stateless JWTs." — https://oneuptime.com/blog/post/2026-03-31-redis-session-revocation-logout-all-devices/view

## F. Fintech ledgers, collections, reconciliation

Targets: *Cheque Bounce*, *Field Collections*, *Reporting & Bank Reconciliation*, *OBC*.

72. ⭐ 🔗 "Design a bank-account ledger service: deposits, withdrawals, transfers, real-time and historical balance, statements; immutable double-entry." (Coinbase) — https://prachub.com/interview-questions/design-a-bank-account-ledger · cards `cheque_bounce.md`, `field_collections.md`
73. 🔗 "Follow-ups: 100x write volume? What breaks first under region failure mid-transfer? Prove the books are correct after an incident. A dispute and an ACH return for the same funds in flight." — same · staff
74. 🔗 "When a company uses double-entry, what elements of a ledger must be equal?" (OnDeck) — https://www.glassdoor.com/Interview/When-a-company-is-using-double-entry-accounting-what-elements-of-a-given-ledger-must-be-equal-QTN_1980117.htm
75. 🔗 "Defend a ledger on immutability, idempotency, concurrency-safety, derived-vs-stored balance, consistency model." — https://github.com/Rinil-Parmar/finledger · https://www.freecodecamp.org/news/build-a-bank-ledger-in-go-with-postgresql-using-the-double-entry-accounting-principle/
76. 🔍 "Recompute the outstanding under a row lock vs apply deltas. Why recompute, and what does it cost per write?" — ripplr-fin-cbm §8 · collections-salesman §11
77. 🔍 "A sibling Node service maintains the same invariant on the same rows. No events, no ordering problem — how?" — ripplr-fin-cbm §11 P4: both recompute full value under lock
78. 🔍 "Payment rows are deleted and re-inserted on resubmit. Where does history live?" — `master_payments` versioned via `parent_id`; copy-forward of verification state
79. 🔍 "Invoice amortization: cash → UPI → cheque → NEFT in order; a payment can split across invoices; leftover money invalidates. Why that order?" — phase1 salesman
80. 🔗 "Two PSPs, three settlement accounts, a payout provider — four external sources that must agree with the internal record. Design reconciliation." — https://www.formance.com/blog/financial-operations/account-reconciliation-patterns-for-high-volume-fintech
81. 🔗 "Captured tonight, lands in the settlement file T+2. Handle the asymmetry." — same
82. 🔍 "The bank feed carries each UPI transaction twice under one UTR. How did you find it, and what's your dedup key?" — NUMBERS: 11,775 dup UTRs; key excludes `TRAN_ID` because the schema says it repeats
83. 🔍 "The regulatory cash ceiling (269ST) is cumulative per payer per day. Why do you need both a per-store-day and a per-invoice check?" — collections-salesman §11 P4
84. 🔍 "Why `MAX` not `SUM` when two feeds can both record one wire?" — ripplr-fin-cbm §11
85. 🔗 "A stock exchange where a trade happens when bid and ask match." (Groww machine coding) — https://www.designgurus.io/answers/detail/what-to-expect-in-the-groww-system-design-interview · analogous to UPI auto-verify within 10 paise
86. 🔗 "Real-time transaction scoring for fraud." (Razorpay HLD) — https://spacecomplexity.ai/blog/razorpay-system-design-interview
87. ✏️ "Bounce charge recovered over three payments. Invoice the delta, not the event — walk through the ₹1 noise floor and what happens if ClearTax is down on payment two." — card `gst_einvoicing.md`

## G. Ingestion pipelines & notification systems

Targets: *Financial Ingestion Pipeline*, *Notifications & GST*.

88. ⭐ 🔗 "Design a notification system: guarantee an accepted notification is never dropped; high-priority within 5s during a campaign blast; no duplicates on top of at-least-once." — https://www.hellointerview.com/learn/system-design/problem-breakdowns/notification-system · card `gst_einvoicing.md`
89. 🔗 "Design a notification service supporting email, SMS, push." (Razorpay HLD) — https://www.designgurus.io/answers/detail/what-to-expect-in-the-razorpay-system-design-interview
90. 🔗 "One merchant's endpoint errors constantly — stop it blocking everyone else's queue." (Razorpay) — https://spacecomplexity.ai/blog/razorpay-system-design-interview
91. 🔗 "Design a Jira-updates notification system reaching thousands of users: queuing, batching, retries, monitoring." (Atlassian) — https://www.interviewquery.com/interview-guides/atlassian-software-engineer
92. 🔗 "Decouple triggering from delivery — the senior way." — https://designgurus.substack.com/p/the-senior-way-to-design-a-notification
93. 🔍 "Event-as-signal vs event-as-payload. Why carry only a salesman id and a date?" — whatsapp-notifications §8
94. 🔍 "Two producers (event + cron sweep), one notification, no distributed lock. How?" — §11 P2: the DB is the lock
95. 🔍 "Row as unit of work in a file pipeline: isolation vs N round trips vs a constant Kafka key serialising everything. Redesign for parallelism." — obc-adjustment §11 Q1: key by `file_id`, batch, module-level user cache
96. 🔗 "Document arrival and processing should be decoupled — a state machine controls flow, uploads run in parallel." — https://builder.aws.com/content/3JKDrIvfeuGRfy6gHC0KISP0yQq/building-a-rag-document-ingestion-pipeline-with-amazon-s3-and-aws-lambda
97. 🔗 "If the S3 notification also fires on the object you write back, what happens?" — https://medium.com/analytics-vidhya/bulk-data-ingestion-from-s3-into-dynamodb-via-aws-lambda-b5bdc30bd5cd
98. 🔗 "Design a catalog with variants, add-ons, price variation, fallback for failures." (Swiggy SDE-2) — https://www.geeksforgeeks.org/interview-experiences/swiggy-interview-experience-set-3-sde-2/ · analogous to 14-brand config-driven parsers
99. 🔍 "Config-driven brand parsing: what stayed in code, and why? What's a silent no-op in your filter engine?" — obc §8 #2, §12 #3 ⚠️
100. ✏️ "A file has 5,000 rows; row 2,300 has a bad invoice number. What does the operator see, when, and how does the file reach 100%?" — card `obc_ingestion.md`

## H. Job queues, schedulers, reporting

Targets: *Reporting & Bank Reconciliation*, *Cheque Bounce* (schedulers).

101. ⭐ 🔗 "Design a distributed job scheduler: exactly-once vs at-least-once execution, fault tolerance, priority." — https://www.designgurus.io/answers/detail/what-to-expect-in-the-openai-system-design-interview · card `reports_and_banking.md`
102. 🔗 "Distributed job scheduler with per-shard leadership and fenced enqueue." — https://prachub.com/resources/distributed-lock-interview-questions-leases-fencing-tokens-and-failure-modes
103. 🔗 "Job scheduler and a load balancer with endpoints to manage backend configs." (Razorpay Lead SWE LLD) — https://leetcode.com/discuss/post/7360702/razorpay-lead-software-engineer-bangalor-qkqi/
104. 🔍 "A DB-backed queue with a global in-progress lock. A stuck report blocks all 19 types. Minimal fix?" — reports-and-finservice A.11 #2 ⚠️
105. 🔍 "Your claim is SELECT, SELECT LIMIT 3, per-row UPDATE — no FOR UPDATE. When is it safe? Redesign with `SKIP LOCKED`." — A.11 #2
106. 🔍 "Two Flask replicas run the same in-process scheduler. What stops double-processing?" — ripplr-fin-cbm §11 P1: `FOR UPDATE SKIP LOCKED`, immediate commit, stuck-row reclaim
107. 🔗 "N worker processes each boot their own scheduler for the same jobs. What happens, and how do you stop it?" — https://github.com/agronholm/apscheduler/discussions/765
108. 🔗 "Scheduler down for an hour, job every 5 minutes. Replay all 12? `misfire_grace_time` vs `coalescing`." — https://apscheduler.readthedocs.io/en/3.x/faq.html
109. 🔍 "Streamed vs chunked export strategies. What decides which a report gets?" — A.2
110. 🔍 "Silent `LIMIT` on 15 of 19 handlers. What does the user see, and what's the durable fix?" — A.8, A.11 #1 ⚠️
111. ✏️ "375 reports/day peaking at 09:30 and 10:30. Three concurrent 300k-row exports at 09:31 — what happens to the ECS task and to the queue?"

## I. Cloud infrastructure choices

Targets: skills line (AWS/GCP), *BFF* (one image), *OBC* (Lambda), *Promise Engine* (App Engine).

112. ⭐ 🔗 "I migrated 40 Lambdas to containers and the bill dropped 73% — compute was only 22% of it. Where did the rest go, and what was your number?" — https://medium.com/lets-code-future/i-migrated-40-lambdas-to-containers-aws-bill-went-down-73-6dc0c17de3fb · your Lambda+API Gateway → ECS/Fargate+ALB move
113. 🔗 "Migrate to containers at >50K/day, 5–20 MB per invocation, or long-running. Where were you on each axis?" — https://dev.to/alanwest/aws-lambdas-hidden-costs-when-to-migrate-to-containers-and-how-2h1n
114. 🔗 "Lambda caps at 10 GB / 6 vCPU; cold start vs always-warm. What was the concrete trigger?" — https://medium.com/@nabindebnath_5126/lambda-vs-ecs-fargate-when-to-make-the-jump-and-when-not-to-4d8d57fad2f1
115. 🔍 "v1 Lambda at 30s/1024 MB vs v2 Docker on EC2. Which endpoints moved, and why those?" — collections-salesman §11 follow-up
116. 🔗 "Presigned URLs are bearer tokens. What constraints make them safe?" — https://insecurity.blog/2021/03/06/securing-amazon-s3-presigned-urls/
117. 🔗 "5–15 min expiry for uploads, server-generated key from user id + UUID, checksum on the object. Which of these do you do?" — https://docs.aws.amazon.com/prescriptive-guidance/latest/presigned-url-best-practices/introduction.html ✏️
118. 🔗 "One image, `ENTRYPOINT` vs `CMD`, override at deploy — how do you run it as API or worker?" — https://www.adaface.com/blog/docker-interview-questions/
119. 🔍 "`app.yaml` is two lines. What happens to the Promise Engine under a spike?" — promise-engine-edd §12 #11 ⚠️
120. 🔍 "6+ MySQL pools × 10 on App Engine, no coordination against `max_connections`. What breaks first?" — §12 #6 ⚠️ 🔗 https://cloud.google.com/sql/docs/mysql/quotas
121. 🔗 "Why is a Pub/Sub or Kafka broker not a delivery mechanism for events *leaving* your network?" — https://www.svix.com/resources/faq/kafka-vs-pubsub/
122. 🔗 "Walk me through your monitoring strategy. How do you know this is production-ready?" — https://logit.io/blog/post/observability-interview-questions/ · Prometheus (`/metrics`), Sentry, New Relic (`server.js:2`)
123. 🔗 "Monitoring and observability are different; SLOs change how teams operate. What are your SLOs?" — https://www.secondtalent.com/interview-guide/observability/ ✏️ — honest answer: none formally defined; say what they'd be
124. 🔗 "Design a distributed compute cluster with job monitoring, log streaming, dashboards, health." (PhonePe HM round) — https://roundz.substack.com/p/interview-experience-130-phonepe-sde2

## J. LLD / machine-coding rounds you should expect

125. ⭐ 🔗 "Design a rate limiter, define its interface, say exactly where in the request path it sits." (New Relic) — https://www.glassdoor.com/Interview/Round-1-DSA-i-Asked-about-projects-I-answered-Redis-Followup-questions-on-Redis-like-how-it-is-implemented-how-can-we-s-QTN_8309436.htm
126. 🔗 "'Design a rate limiter' is a trap — the real test is shared state across 50 API servers." — https://blog.stackademic.com/design-a-rate-limiter-is-not-a-system-design-question-its-a-trap-12115b974c9f
127. 🔗 "Rate limiter machine-coding." (Atlassian) — https://interviewing.io/atlassian-interview-questions
128. 🔗 "Sliding window, with and without Redis." (Flipkart) — https://www.designgurus.io/answers/detail/what-to-expect-in-the-flipkart-system-design-interview
129. 🔗 "Design a pub/sub queue with persistent delivery guarantees and ordering." (Razorpay LLD) — https://spacecomplexity.ai/blog/razorpay-system-design-interview
130. 🔗 "Multithreaded queue like Kafka — publishers and subscribers must not block each other." (Uber L5a) — https://leetcode.com/discuss/interview-question/1091960/Uber-L5a-Interview-or-Machine-coding%3A-Multithreaded-Queue-like-Kafka
131. 🔗 "Design Kafka: topics, partitioned ordered storage, durability, consumer groups, at-least-once." (Uber L5) — https://leetcode.com/discuss/post/7548356/
132. 🔗 "Pub/sub where a message is lost if no subscriber is listening." (Roblox) — https://www.hellointerview.com/community/questions/pub-sub-system/cmaiqpcyu00zuad08tagl4bon · notice the constraint changes the design
133. 🔗 "Auction system: concurrent auctions, P&L, preferred-buyer tie-break." (Flipkart SDE2) — https://www.geeksforgeeks.org/interview-experiences/flipkart-interview-experience-for-sde2-2-5-yr-exp/
134. 🔗 "Design a KV distributed cache; then Dropbox — with constraints changed mid-round." (CRED) — https://www.glassdoor.co.in/Interview/CRED-Backend-Developer-Interview-Questions-EI_IE3050300.0,4_KO5,22.htm
135. 🔗 "Leader election using Redis leases: renewal, split-brain, fencing." — https://prachub.com/resources/distributed-lock-interview-questions-leases-fencing-tokens-and-failure-modes
136. ✏️ "Implement the 11-state transition table as a class. Add a transition. Add an audit hook. Make an illegal transition throw." — you already have this; write it from memory
137. ✏️ "Implement `withLock(key, ttl, fn)` that's safe when `fn` outlives the TTL." — https://github.com/kunj-21/backend-interview-daily/issues/6 · fencing token

## K. "What breaks first at 10x?" — one per system

Every staff-level source converges on this question. Have a *specific component* for each, never "add servers."

138. ⭐ 🔗 "Identify what breaks first at the new scale and address it specifically." — https://www.designgurus.io/answers/detail/what-to-expect-in-the-databricks-system-design-interview
- **OBC ingestion:** the constant Kafka key → one partition → one consumer. Then per-row Mongo/SQL round trips. — obc §12 #2, #12
- **Cheque bounce:** the global recompute per touched invoice per event; then the shared-queue lock on reports.
- **Field collections:** the fail-open Redis claim becomes a real duplicate rate; then the delete+insert rebuild under contention.
- **Notifications:** the 1s sleep → 86,400/day hard ceiling per instance. — whatsapp §11
- **Reporting:** the global in-progress lock; then in-memory `json_to_sheet` handlers. — reports A.8
- **Promise Engine:** 6+ uncoordinated pools against one MySQL; no autoscaling block; CPU-bound pipeline on the loop. — edd §12
- **Inventory sync:** no ordering keys + multiple subscribers + interleaved snapshot pages → convergence lag grows. — inventory §11 P5
- **Post-order:** documents that only grow (tombstones); check-then-act dedup on tracking pushes. — post-order §8, §12
- **Fan-in:** twelve serialised upstreams on the critical path; no circuit breakers named.
- **BFF:** Shopify's cost-based quota; `SQS_MAX_CONCURRENT_MESSAGES=1`. — mydesignation §8
- **Cache:** the `product` family at 19.6% and a hot-key during a viral drop; Redis lock needs Redis.
- **Identity:** OTP counters fail open — brute-force window during a Redis blip.
- **IAM:** `extra_perms` revocation waits for token expiry; Kafka out-of-order catalog version. — iam §10
