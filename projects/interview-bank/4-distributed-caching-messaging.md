# Section 4 — Distributed Systems, Caching & Messaging

Kafka (AWS MSK — OBC, notifications, RBAC propagation, finService), Google Cloud Pub/Sub (inventory,
courier tracking), AWS SQS (MyDesignation webhooks), Redis (five distinct uses), and the cloud
infrastructure on the skills line.

Pattern from every source: **"exactly-once" is a trap word.** The follow-up is always "what does it
buy you and where does it stop?" — and the answer is that delivery semantics die at the DB /
third-party boundary. Consumers must be idempotent regardless. You have four consumers; know each one's
exact commit behaviour.

---

## A. Kafka

Targets: *OBC* (constant key, `acks=1`, commit-on-exception), *Notifications* (1s sleep, commit-on-exception, no DLQ), *IAM* (catalog fan-out), *Reporting* (finService producer per-message connect).

1. ⭐ 🔗 "Your consumer updates MySQL, then crashes before committing the offset. What happens next?" — https://medium.com/javarevisited/kafka-interview-questions-the-complete-production-grade-guide-for-senior-backend-engineers-488fb565d467 · then flip it: **yours commits even on exception** — so the answer is the message is *lost*, not duplicated ⚠️ cards `obc_ingestion.md`, `gst_einvoicing.md`
2. ⭐ 🔗 "What happens if a consumer crashes after reading but before committing?" — https://www.hirist.tech/blog/top-25-kafka-interview-questions-and-answers/ · know the difference between your two consumers' behaviour
3. 🔗 "Implement a retry for failed processing — Kafka doesn't give you one." — same ⚠️ you have no DLQ on either consumer; cheaper fix: stop committing on exception
4. 🔗 "20 partitions, 50 consumers. What happens?" — javarevisited (above)
5. 🔗 "12 partitions — what does that number actually control?" — https://www.techinterview.org/post/3233477380/kafka-interview-questions/
6. 🔍 "You key every OBC row with the same constant. What does that do to parallelism, and why did you accept it?" — obc §12 #2 ⚠️ single partition; the completion check depends on it
7. 🔗 "Partitioning key — what happens if you don't specify one?" — hirist (above)
8. 🔗 "Consumer lag grows even after adding consumers. Diagnose." — javarevisited (above) · your constant key is the answer
9. 🔗 "Consumers keep rebalancing and throughput tanks. Debug it." — techinterview.org (above)
10. 🔗 "Walk through a rebalance — which offsets commit, where do consumers resume?" — https://www.geeksforgeeks.org/kafka-interview-questions/
11. 🔗 "How does incremental cooperative rebalance (KIP-429/848) avoid stop-the-world?" — same · https://www.instaclustr.com/blog/rebalance-your-apache-kafka-partitions-with-the-next-generation-consumer-rebalance-protocol/
12. 🔗 "Static membership / cooperative-sticky — which assignor stops every partition being revoked on each rebalance?" — https://rafftechnologies.com/learn/guides/kafka-consumer-groups-lag-rebalances
13. 🔗 "Rebalance time spiked in production. How do you diagnose?" — https://www.confluent.io/blog/debug-apache-kafka-pt-3/
14. 🔗 "`commitSync` vs `commitAsync` — when does a silent async failure hurt you?" — geeksforgeeks (above)
15. 🔗 "`acks=0/1/all` — then the exact failover where `acks=1` loses an acknowledged message." — https://akcoding.com/system-design/messaging-systems/kafka-interview-questions/ · your producer is `acks=1` ⚠️
16. 🔗 "Idempotent producers — why useful?" — hirist (above) · you don't use them
17. 🔗 "Replication factor 3 but ISR of 1 — how?" — geeksforgeeks
18. 🔗 "`unclean.leader.election.enable=false` and no ISR available. What happens?" — same
19. 🔗 "Exactly-once end to end: idempotent producer + transactions + `read_committed`." — same · then: "does that extend to what your consumer writes to MySQL?" — https://app.sourcethread.com/thread/t-opus48-093f1efad18a0b (no)
20. 🔗 "Kafka preserves ordering how, and why not globally?" — javarevisited
21. 🔗 "Consumer slower than producer — implications?" — akcoding
22. 🔗 "Implications of increasing partition count." — https://www.datacamp.com/blog/kafka-interview-questions
23. 🔗 "In librdkafka, offset is stored at `poll()` by default, unlike Java. What does that mean for your handler?" — sourcethread (above) ⚠️ exact library on the resume
24. 🔍 "IAM catalog message arrives out of order — a stale lower version after a newer one. Guard?" — iam-prd §10 gap 1 ⚠️ unspecified
25. 🔍 "IAM consumer sees a duplicate catalog message. Harmless — why?" — §13 Q4: refetches and rewrites the same versioned prefix
26. 🔍 "Why Kafka rather than polling `/catalog` with an ETag every 15 minutes — which you already do?" — §10 #9: "existing rail," not a latency comparison
27. 🔍 "The finService producer connects and disconnects per message. Cost?" — reports B.8 ⚠️
28. 🔗 "Guarantee a payment event is not processed twice." — javarevisited
29. 🔗 "Design a system: 200k events/min, strict per-`orderId` ordering, at-least-once, idempotent fan-out to inventory and dispatch, <1s p95." (Swiggy SDE-2) — https://bitsofanant.medium.com/my-sde-2-interview-experience-at-swiggy-4fc2447789c8

## B. Google Cloud Pub/Sub

Targets: *Realtime Inventory Sync*, *Post-Order* (courier tracking, FreshDesk, attribution).

30. ⭐ 🔗 "Ordering key — how does it change delivery, and what happens to later messages under that key if an earlier one keeps failing?" — https://medium.com/google-cloud/understanding-message-ordering-in-google-pubsub-1c5729f09dbd · https://cloud.google.com/pubsub/docs/ordering · you have **no** ordering key; card `inventory_realtime.md`
31. 🔗 "No dead-letter topic by design. What's the failure mode the first time one message can never be processed?" — https://docs.cloud.google.com/pubsub/docs/subscription-properties ⚠️
32. 🔗 "Min and max ack deadline, and what do you do when the handler legitimately needs longer?" — https://docs.cloud.google.com/sdk/gcloud/reference/alpha/pubsub/subscriptions/modify-ack-deadline
33. 🔍 "Staging and prod on one subscription name. How would you even detect messages being split, and how do you prevent it structurally?" — promise-engine-inventory §11 P2 ⚠️ be precise on whether the *topic* was split
34. 🔍 "qty=10 retried after qty=5. What's in the row?" — §11 P5 ⚠️ 10
35. 🔍 "Nack is effectively unreachable for DB failures. Why, and if you fixed it, what new problem appears without a DLQ?" — §11 P4 ⚠️ infinite redelivery
36. 🔍 "`maxMessages: 1` per subscriber client — why, and where does parallelism come from?" — §11.2
37. 🔍 "Why one message per webhook call rather than per item?" — §11.2
38. 🔍 "Why Pub/Sub over RabbitMQ or Kafka here?" — §11.2 · name what each alternative would give you
39. 🔗 "Kafka vs Pub/Sub — when each, and why neither delivers to an endpoint outside your network?" — https://www.svix.com/resources/faq/kafka-vs-pubsub/
40. 🔗 "Pub/Sub engineering lessons from the trenches — the environment-mixing failure pattern." — https://discuss.google.dev/t/mastering-google-cloud-pub-sub-engineering-lessons-from-the-trenches/299498
41. ✏️ "Two App Engine instances, two subscriber clients, one delta each for the same SKU, and a cron snapshot page for that SKU lands between them. Draw the timeline."

## C. AWS SQS

Targets: *Exactly-Once Order Creation* (standard + DLQ, `maxReceiveCount` 5, visibility 30s, long-poll 20s, concurrency 1).

42. ⭐ 🔗 "When FIFO over Standard — name the specific ordering guarantee that would actually break." — https://www.svix.com/resources/faq/sqs-fifo-vs-standard/ · card `exactly_once_orders.md`
43. 🔗 "Dedup the queue's job (FIFO's 5-min content-based window) or the consumer's (idempotency key on Standard)?" — same
44. 🔗 "Scope FIFO ordering with group IDs without bottlenecking behind one key." — same
45. 🔗 "Can a Standard queue have a FIFO DLQ?" — https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-dead-letter-queues.html
46. 🔗 "`maxReceiveCount` 5 — walk one message through receives 1 to 6." — same
47. 🔗 "Handler regularly outlives the visibility timeout. What happens, and the proper fix?" — https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-visibility-timeout.html · https://medium.com/double-pointer/mastering-aws-sqs-top-5-interview-questions-answered-8c2699660fd6
48. 🔗 "Size visibility timeout off p99, not average." — https://oneuptime.com/blog/post/2026-01-27-sqs-message-visibility-timeout/view
49. 🔍 "Delete on success, leave on failure. What's the redelivery count before the DLQ, and has it ever had depth?" — mydesignation §5 ⚠️ DLQ history unknown
50. 🔍 "`SQS_MAX_CONCURRENT_MESSAGES=1`. What breaks at 10?" — §11 follow-up: nothing *should*; untested
51. 🔗 "Autoscale off queue depth — visible vs not-visible counts." — https://adhdecode.com/articles/sqs/sqs-consumer-concurrency-scaling/
52. 🔗 "Design App Event → SQS → workers → delivery → DLQ with idempotency dedup and a 99% SLO; backpressure via visibility timeout." (Amazon-context) — https://www.designgurus.io/blog/system-design-interview-amazon
53. 🔍 "Worker is a separate container from the same image. What does that buy, and what can still go wrong?" — ✏️ shared broken dependency; independent scaling
54. 🔗 "Poison message vs merely too fast — same retry strategy for both?" — https://www.abstractalgorithms.dev/dead-letter-queue-pattern-poison-message-recovery · https://www.cogin.com/articles/SurvivingPoisonMessages.php
55. 🔗 "DLQ policy end to end: max retries, who's paged on depth, how to replay without re-triggering the incident." — https://www.designgurus.io/answers/detail/how-do-you-implement-dlqs-and-handle-poison-messages

## D. Webhooks — reliability and security

Targets: *Exactly-Once* (Razorpay), *Post-Order* (ClickPost, Shopify), *Inventory* (ERP), *Reporting* (ICICI/HDFC), *Caching* (Shopify freshness).

56. ⭐ 🔗 "Design a webhook receiver that's at-least-once, idempotent, stateless, with <200 ms end-to-end." — https://systemdesignschool.io/problems/webhook/solution · your validate → enqueue → 200/202 pattern
57. 🔗 "Why do webhooks arrive more than once even when your handler already succeeded?" — https://www.hooklistener.com/learn/webhook-idempotency-and-deduplication
58. 🔗 "Dedup on the provider's event ID or a body hash — and why does the fallback matter?" — same
59. 🔗 "Handler finishes but is slow enough that the provider times out and retries. What protects you?" — same
60. 🔗 "Crash after claiming the idempotency key, before the side effect. What does the retry find?" — same · your shared notification log; your SQS claim
61. 🔗 "Does an event-ID dedup table alone protect you, or must the side effects themselves be idempotent?" — same
62. 🔗 "HMAC over parsed JSON vs raw bytes." — https://didit.me/blog/webhook-security-hmac-signature-validation/
63. 🔗 "A valid signature doesn't prove freshness — stop a replay." — https://dev.to/roxdavirox/hmac-proves-origin-not-freshness-replay-attacks-against-signed-apis-1e53 · https://www.hooklistener.com/learn/webhook-security-fundamentals
64. 🔗 "Why must the timestamp be *inside* the signed payload?" — https://webhooks.fyi/security/replay-prevention
65. 🔗 "Receiver skips the HMAC or verifies the wrong encoding — forge a request." — https://dev.to/roxdavirox/webhook-signature-bypass-when-the-receiver-skips-the-hmac-check-i1i · HDFC `TODO` ⚠️
66. 🔍 "Raw-log *before* the signature gate. Why?" — mydesignation §11 P4: a forged delivery still leaves a forensic row
67. 🔍 "The live `/edd-actions` idempotency check is commented out. Deliberate?" — supertails-post-order §8 ⚠️
68. 🔍 "The Shopify note update inside the delivery-note webhook is fire-and-forget. Divergence?" — §11 follow-up ⚠️
69. 🔍 "ERP webhook: 202 with a `message_id`. What does the ERP do with it, and what does 200 mean here?" — promise-engine-inventory §11.2
70. 🔗 "Timing attack on signature comparison." — https://github.com/SorobanKit/sorobanKit/issues/74
71. ✏️ "Shopify webhook delivery fails for an hour. Which cached families go stale, and for how long?"

## E. Idempotency, outbox, exactly-once (cross-cutting)

Targets: *OBC* (3-layer), *Notifications* (event-as-signal, shared log), *IAM* (outbox), *Exactly-Once*, *Field Collections*.

72. ⭐ 🔗 "Why not publish to Kafka from the request handler — the dual-write problem?" — https://www.designgurus.io/blog/transactional-outbox-pattern · card `iam_rbac.md`
73. 🔗 "Does the outbox guarantee exactly-once delivery?" — same (no — reliable persistence; delivery is at-least-once)
74. 🔗 "CDC/Debezium instead of polling the outbox — what operational complexity do you trade in?" — same
75. 🔍 "Outbox vs saga vs try/catch for provisioning across three DBs." — iam-prd §13 Q9
76. 🔍 "Estate API succeeds, response lost, retry hits unique-email. Recover the id." — §10 gap 3 ⚠️
77. 🔗 "What makes a consumer safe for at-least-once? (Idempotent handlers + dedup store with bounded retention.)" — https://www.designgurus.io/answers/detail/atleastonce-vs-atmostonce-vs-exactlyonce-where-to-use-each · is your 3-layer OBC dedup sufficient or overkill?
78. 🔗 "Stripe, Kafka, AWS don't do exactly-once by default. What do they rely on?" — same
79. 🔍 "Three layers: ETag, in-file, MD5 lookup. Which is DB-enforced?" — obc §11 Q2 ⚠️ none verified
80. 🔍 "Event carries only a signal; consumer re-derives from DB. What race does that eliminate and what does each message now cost?" — whatsapp §8
81. 🔍 "Two producers, one DB log, no lock. Pending row before send; `NOT EXISTS` on success. Where's the remaining window?" — §11 P2 ✏️ between pending-insert and success-update on a crash
82. 🔗 "Kafka guarantees delivery, not uniqueness. Where's the consumer dedup table and how big does it get?" — https://dev.to/naresh_007/kafka-guarantees-delivery-not-uniqueness-how-to-build-idempotent-systems-1j6d
83. 🔗 "Redis can only be an optimisation for idempotency. Where's the real guarantee, and what happens when Redis is unreachable?" — https://dev.to/amitesh0512/payment-processing-idempotency-why-redis-cache-can-fail-in-production-4159 · your fail-open claim
84. 🔗 "Idempotency key + atomic Redis lock + 409 on concurrent duplicate + cached replay for completed requests." — https://github.com/kunj-21/backend-interview-daily/issues/3
85. 🔗 "Same key, different body." — same
86. 🔍 "Counters not idempotent under redelivery — `processed` can exceed `total`. Fix without a schema change." — obc §12 #7 ⚠️
87. 🔍 "Is the file-completion check race-safe? The docstring says atomic." — obc §11 Q5 ⚠️ no; `find_one_and_update` with a status filter fixes it
88. 🔗 "Events out of order: update before create, cancel after complete." — https://oneuptime.com/blog/post/2026-01-24-message-ordering-event-driven/view
89. 🔗 "`payment.captured` before `payment.authorized`." (Razorpay) — https://spacecomplexity.ai/blog/razorpay-system-design-interview

## F. Redis — caching

Targets: *Caching & Identity* (two-layer, version counter, negative-cache bug, hit ratios), *IAM* (group sets), *Promise Engine* (EDD cache, warehouse mapping), *Field Collections* (claim).

90. ⭐ 🔍 "Size chart showed 'no chart' for an hour. Bug, and the rule?" — mydesignation §11 P2 · card `caching_and_identity.md`
91. ⭐ 🔗 "Downstream times out; your code treats 'no result' the same as 'genuinely absent'. What production bug, and how does a sentinel fix it?" — https://www.geeksforgeeks.org/system-design/negative-caching-system-design/
92. 🔗 "The common mistake caching nullable values, and what happens when the real record shows up while the negative entry is alive." — https://blog.jooq.org/a-common-mistake-developers-make-when-caching-nullable-values/
93. 🔗 "When cache a 404 at all, and what's the exposure window?" — https://www.designgurus.io/course-play/grokking-scalable-systems-for-interviews/doc/what-is-negative-caching-and-when-should-you-cache-404-or-empty-results
94. 🔍 "Is the sentinel actually used anywhere?" — §11 P2 ⚠️ no
95. 🔗 "Stop a stampede on a hot key — inside one process and across hosts." — https://bugfree.ai/knowledge-hub/dealing-with-cache-stampede-and-thundering-herd
96. 🔗 "Most common real trigger for a thundering herd, and first line of defence?" — https://adhdecode.com/system-design/caching-strategies/cache-stampede-thundering-herd/
97. 🔗 "Justify your invalidation strategy — then: what does on-call see at 3 a.m. when it breaks, and what does the runbook say?" — https://www.designgurus.io/blog/cache-invalidation-strategies
98. 🔗 "Event-driven invalidation plus TTL safety net — why both?" — same
99. 🔗 "Write-through still has the dual-write problem. Why read-through + webhooks instead?" — https://levelop.dev/blog/caching-strategies-system-design-four-patterns-failure-modes
100. 🔗 "Every Redis call falls through on error. What should worry you *more* than 'down', and how is ioredis tuned?" — https://www.newsbreak.com/news/4896650140630-redis-goes-down-should-the-application-fail
101. 🔍 "Redis completely down during a spike — correctness, latency, rate limits, stampede guard." — §11 follow-up
102. 🔗 "Redis as system of record — how async replication makes a granted claim vanish on failover." — https://www.hellointerview.com/learn/system-design/deep-dives/redis
103. 🔗 "`KEYS` against millions of keys — what does the server look like while blocked?" — https://openillumi.com/en/en-redis-keys-danger-scan-use/ · your SCAN + UNLINK
104. 🔍 "Version-counter invalidation — why bump instead of delete, and what happens to the old keys?" — ✏️ they expire by TTL; SCAN + UNLINK sweeps
105. 🔗 "~20% hit ratio despite a 15-min TTL from a long tail of one-off views — LFU over LRU?" — https://redis.io/blog/cache-eviction-strategies/ · your `product` family at 19.6%
106. 🔗 "Increasing hit ratio can *hurt* throughput for some algorithms. Why isn't 'maximise hit ratio' the target?" — https://redis.io/blog/why-your-cache-hit-ratio-strategy-needs-an-update/ · defending 44.81% system-wide
107. 🔗 "Aggregate hit ratio hides a hot keyspace that misses badly. Measure per family; then what?" — https://www.debugbear.com/docs/metrics/cache-hit-rate
108. 🔗 "Hit ratio dips after every deploy and recovers in an hour. What, and worth fixing?" — redis.io (above)
109. 🔗 "Hot key — one node spikes; why don't read replicas help if it's being written?" — hellointerview (above)
110. 🔗 "Cache and DB disagree. How did it happen, how do you bound it?" — https://www.techinterview.org/post/3233476816/caching-patterns-system-design-interview-cheat-sheet/
111. 🔗 "Sentinel vs Cluster — and the minimum primaries for a failover majority." — https://oneuptime.com/blog/post/2026-03-31-redis-redis-cluster-vs-redis-sentinel-when-to-use-which/view
112. 🔗 "Multi-key Lua against a sharded Cluster — what breaks?" — hellointerview (above) · your atomic check-and-set scripts
113. 🔗 "Redis clusters: scaling, replication, node failure, consistency." (Flipkart SDE2) — https://www.geeksforgeeks.org/flipkart-interview-for-sde2-backend/
114. 🔗 "Menus and prices change mid-order — how do you avoid serving a stale cached price at checkout?" (Zomato) — https://www.designgurus.io/answers/detail/what-to-expect-in-the-zomato-system-design-interview
115. 🔗 "Cache invalidation, TTL selection, cache-aside in an event-driven context." (Swiggy) — https://www.placementpreparation.io/blog/swiggy-interview-questions-and-experience/
116. 🔗 "Redis internals, eviction, consistency, failure handling." (PeopleStrong SDE-2) — https://leetcode.com/discuss/post/7483809/
117. 🔗 "Hot-key scenarios." (LinkedIn Staff) — https://leetcode.com/discuss/post/6858262/linkedin-staff-software-engineer-intervi-mg5c/
118. 🔍 "Warehouse-mapping cache: Redis-first, 1h TTL, DB fallback on *miss* — but on *error* it returns `{}` with no DB fallback. Consequence on a delta?" — promise-engine-inventory §11.2 ⚠️ silent no-op
119. 🔍 "Group-keyed sets, `SISMEMBER`, one byte back, vs a 45 KB JSON blob per check. Show the arithmetic." — iam-prd §10
120. 🔍 "Versioned prefix, pointer flipped last, grace period. What if a reader pipelines `GET v` + `SISMEMBER` and the flip lands between them?" — §13 Q3 ✏️

## G. Redis — distributed locks and claims

Targets: *Field Collections* (`SET NX EX 60`, fails open), *Caching & Identity* (cross-container lock).

121. ⭐ 🔗 "`SET key val NX EX ttl` as one call vs `SET` then `EXPIRE` — what race does the two-call version open?" — https://redis.io/docs/latest/develop/clients/patterns/distributed-locks/ · your own earlier non-atomic version ⚠️ card `field_collections.md`
122. 🔗 "Process holding the lock crashes without releasing. What stops a permanent deadlock?" — https://adhdecode.com/distributed-systems/distributed-locking-and-concurrency/lock-implementation-redis/
123. 🔗 "Critical section outlives the TTL; another process acquires; you blindly `DEL`. What did you do?" — same
124. 🔗 "Release only a lock you still own — why does `DEL` become a Lua check-and-delete?" — same
125. 🔗 "GC pause lets the lock expire mid-work. Correctness without a fencing token?" — https://martin.kleppmann.com/2016/02/08/how-to-do-distributed-locking.html
126. 🔗 "Efficiency lock vs correctness lock — which is yours?" — same · the collections claim is efficiency-flavoured; the DB is the backstop
127. 🔗 "Is Redlock safe? Kleppmann vs antirez — which side, and what does that change about what you'd trust Redis for vs etcd/ZooKeeper?" — https://antirez.com/news/101 · https://medium.com/@ayushpro111/distributed-locks-in-redis-and-the-redlock-argument-nobody-fully-agrees-on-9f96a9a3d4ac
128. 🔗 "Redlock has no fencing tokens — why still unsafe for strict mutual exclusion?" — https://hackernoon.com/the-fencing-gap-why-your-distributed-lock-isnt-safe-and-how-to-fix-it
129. 🔗 "'Use Redis SETNX' is an incomplete answer — define the invariant, the authority model, the stale-owner failure." — https://prachub.com/resources/distributed-lock-interview-questions-leases-fencing-tokens-and-failure-modes
130. 🔗 "Build `withLock(key, ttlMs, fn)` safe against GC pauses; explain the fencing-token fix." — https://github.com/kunj-21/backend-interview-daily/issues/6
131. 🔍 "Redis unavailable → request allowed through. Defend failing open on a ₹3.9 Cr/day path." — collections §8
132. 🔍 "A `/complete` takes 70s, key expires at 60. Retry?" — §11 follow-up
133. 🔍 "Two *different* payloads for the same invoice at once — deduped?" — §11 follow-up (no)
134. 🔍 "Both `redis` and `ioredis` in `package.json`. Which backs the lock, and what differs under load?" — §12 ⚠️

## H. Rate limiting

Targets: *Caching & Identity* (rate-limiter-flexible, OTP counters, fail-open), *BFF* (bypass flag).

135. ⭐ 🔗 "Fixed window, sliding log, sliding counter, token bucket in Redis — which handles bursts and which has boundary problems?" — https://redis.io/tutorials/howtos/ratelimiting/
136. 🔗 "Even inside `MULTI/EXEC`, check-then-increment has a race — where, and how does Lua close it?" — https://www.hellointerview.com/learn/system-design/problem-breakdowns/distributed-rate-limiter
137. 🔗 "A fixed-window counter behind an Nginx sidecar has a boundary burst. Would you have chosen differently?" (Razorpay) — https://spacecomplexity.ai/blog/razorpay-system-design-interview
138. 🔗 "Per-request Redis call on every hit across hundreds of thousands of hosts doesn't work. Redesign." (Uber) — https://www.uber.com/us/en/blog/ubers-rate-limiting-system/
139. 🔗 "1M req/s, HA, hot keys, dynamic rules." — hellointerview (above)
140. 🔗 "Stripe says a limiter that can't reach its store should let requests through. Right for you? What data proves it?" — https://github.com/HweyTH/limigo/issues/4 · your `0 cache_degraded` is the shape of evidence wanted
141. 🔗 "Rate limits fail open, auth fails closed — where's the line, and would you fail a payment claim open?" — https://nerdleveltech.com/fail-open-vs-fail-closed-hono-middleware-redis-tutorial
142. 🔍 "A bypass flag hardcoded on for one IP skips both limiters. Deployed?" — mydesignation §12 ⚠️ **know before the interview**
143. 🔗 "Missing rate limit on OTP-verify → 6-digit code brute-forced → account takeover. Walk it." — https://www.comolho.com/post/otp-brute-force-attack-rate-limiting-account-takeover
144. 🔗 "Per-phone, per-IP, global counters — interaction so IP rotation can't bypass." — https://undercodetesting.com/the-silent-otp-killer-how-missing-rate-limits-are-burning-down-your-authentication-walls-video/
145. 🔗 "Rate limiter with and without Redis, sliding window." (Flipkart) — https://www.designgurus.io/answers/detail/what-to-expect-in-the-flipkart-system-design-interview
146. 🔗 "Fixed window, sliding window, token bucket, distributed, Redis, locks." (Amazon SDE2, Aug 2026) — https://leetcode.com/discuss/post/8512004/
147. 🔍 "4-digit PIN, no lockout policy." — iam-prd §10 gap 8 ⚠️

## I. Auth and session across services

Targets: *IAM* (Redis sets + Kafka + reconcile, MySQL sessions), *Caching & Identity* (refresh families).

148. ⭐ 🔗 "A spent refresh token is presented again. What does that mean, and what happens to the rest of the lineage?" — https://codesignal.com/learn/courses/jwt-security-attacks-defenses-1/lessons/refresh-tokens-and-secure-token-rotation · https://nhimg.org/glossary/refresh-token-reuse-detection/
149. 🔗 "Account accessed after a password change — how, with issued JWTs, and how do you shrink the window?" — https://www.techinterview.org/post/3233477260/revoke-jwt-oauth-interview-questions/ · 15-minute access token
150. 🔗 "Attacker has a valid access token — what, and for exactly how long?" — same
151. 🔗 "Silent rejection of a reused token isn't enough — what distinguishes theft from an admin revoke?" — https://github.com/Uuriko/project-room/pull/1022
152. 🔗 "One family exchanged from diverse IPs in an hour — caught before a literal reuse?" — https://auth0.com/blog/refresh-token-security-detecting-hijacking-and-misuse-with-auth0/ ✏️ honest: probably not
153. 🔗 "RFC 9700 / BCP 240 — sender-constrained or rotated on every use for public clients. Comply?" — https://csharpstack.dev/09-security/refresh-token-rotation-and-revocation.html
154. 🔍 "Why hash refresh tokens rather than a longer-lived stateless JWT?" — mydesignation §11 follow-up
155. 🔗 "Per-user version counter in Redis for 'log out everywhere'; then for stateless JWTs." — https://oneuptime.com/blog/post/2026-03-31-redis-session-revocation-logout-all-devices/view · same idea as your family revocation and IAM catalog version
156. 🔗 "Session revocation is a no-op — the UI flips a column nothing reads. Test that revoke is enforced on the read path." — https://github.com/Senthil455/Atlas-Workforce-System/issues/170
157. 🔍 "IAM goes down. What stops, what continues, for how long?" — iam-prd §13 Q5
158. 🔍 "Kafka drops the catalog message. Worst-case staleness?" — §13 Q4: 15 min via ETag reconcile
159. 🔍 "`extra_perms` baked into the token. Revocation latency?" — §10 gap 2 ⚠️ token expiry
160. 🔍 "Any `*.ripplr.in` origin can mint a token for any audience with the cookie. Blast radius of one XSS?" — §10 gap 4 ⚠️
161. 🔍 "IAM holds both estates' secrets. Rotate one." — §10 gap 6 ⚠️
162. 🔗 "OTP resend cooldown + verify-attempt counter in Redis — what breaks if the check order is wrong?" — https://github.com/kunj-21/backend-interview-daily/issues/7
163. 🔍 "OTP verify cap fails open on Redis error. Why?" — mydesignation §11 follow-up
164. 🔍 "Google People API phone vs a verified OTP — why does a real OTP outrank it?" — §11 P3 ✏️ recycled numbers

## J. Cloud infrastructure and observability

Targets: skills line — AWS (Lambda, S3, ECS/Fargate, SQS, RDS, API Gateway, CloudWatch), GCP (App Engine, Pub/Sub, GCS), Docker, CI/CD; Prometheus, Sentry, New Relic.

165. ⭐ 🔗 "Lambda → containers: compute was 22% of the bill; data transfer, CloudWatch, NAT, provisioned concurrency were the rest. What was *your* breakdown?" — https://medium.com/lets-code-future/i-migrated-40-lambdas-to-containers-aws-bill-went-down-73-6dc0c17de3fb ✏️ have a number or say you don't
166. 🔗 "When to migrate: >50K/day, 5–20 MB/invocation, long-running." — https://dev.to/alanwest/aws-lambdas-hidden-costs-when-to-migrate-to-containers-and-how-2h1n
167. 🔗 "Cold start vs always-warm as the concrete trigger." — https://medium.com/@nabindebnath_5126/lambda-vs-ecs-fargate-when-to-make-the-jump-and-when-not-to-4d8d57fad2f1
168. 🔗 "Lambda cold start — init phase, and why more memory helps a non-memory-bound function." — https://www.datacamp.com/blog/aws-lambda-interview-questions
169. 🔗 "Account-wide concurrency pool and reserved concurrency's double edge." — https://www.dash0.com/knowledge/aws-lambda-concurrency
170. 🔗 "Presigned URLs are bearer tokens." — https://insecurity.blog/2021/03/06/securing-amazon-s3-presigned-urls/ · https://docs.aws.amazon.com/prescriptive-guidance/latest/presigned-url-best-practices/introduction.html
171. 🔗 "`ENTRYPOINT` vs `CMD`, one image two roles." — https://www.adaface.com/blog/docker-interview-questions/
172. 🔍 "App Engine `app.yaml` with no scaling block; 6+ pools per instance. First thing that breaks under a spike?" — promise-engine-edd §12 #6, #11 ⚠️
173. 🔍 "No IaC for ECS/ALB/RDS/ElastiCache — it exists only as narrative. Risk?" — mydesignation §12 ⚠️
174. 🔍 "No `helmet`, `rejectUnauthorized: false`, a returns route authorising off params. Which would you fix first and why?" — §12 ⚠️
175. 🔗 "Monitoring strategy; production-ready?" — https://logit.io/blog/post/observability-interview-questions/
176. 🔗 "Monitoring ≠ observability; SLOs change operations." — https://www.secondtalent.com/interview-guide/observability/
177. 🔍 "Prometheus at `/metrics` on Flask, Sentry init, `require('newrelic')` on line 2 — what does each catch that the others don't, and where's the gap?" — TECH-STACK ✏️
178. 🔍 "You measured logins by filtering `token_type` in one `logger.info(access_data)` call because the route emits nothing. What would you add so the next person doesn't have to?" — iam_rbac card ✏️
179. 🔍 "Loggly lines O(items × warehouses) per snapshot page. Cost and signal-to-noise fix?" — promise-engine-inventory §8 ⚠️
180. 🔍 "Full DataFrame + customer PII into CloudWatch. Retention, redaction, cost." — obc §12 #5 ⚠️
181. 🔗 "Distributed compute cluster with job monitoring, log streaming, dashboards, health." (PhonePe) — https://roundz.substack.com/p/interview-experience-130-phonepe-sde2
182. ✏️ "Which of your services has a health check that would still report healthy while doing no useful work? (Kafka consumer on a poison message; report worker with a wedged queue; App Engine subscriber with an empty mapping.)"
