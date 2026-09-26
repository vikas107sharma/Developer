# Section 3 — Runtime & Execution Mechanics

Node.js 22/24 (Promise Engine, Supertails, MyDesignation, reports, finService producer), Python 3.9
(Ripplr-fin Flask, OBC Lambda + consumer, finService consumer), and the execution model of Lambda,
ECS/Fargate and App Engine Standard.

Pattern from every source: the senior question is **"what happens when…"** and **"is this mechanism
actually enforced or merely advisory?"** — `highWaterMark` isn't a hard cap, `SETNX` without atomic
`EXPIRE` isn't a lock, the GIL doesn't remove races, `async def` doesn't make code non-blocking.

---

## A. Node event loop and execution order

1. ⭐ 🔗 "Predict the output order of a snippet mixing `setTimeout`, `setImmediate`, a resolved Promise, `process.nextTick` and an `fs` callback — then explain why." — https://github.com/kunj-21/backend-interview-daily/issues/1
2. 🔗 "Why can recursive `process.nextTick` starve the loop indefinitely while recursive `setImmediate` can't?" — same · https://nodejsconsultant.com/articles/expert-node-interview-questions
3. 🔗 "Event loop ↔ thread pool ↔ kernel for async I/O — in detail." — nodejsconsultant (above)
4. 🔗 "`setImmediate` vs `process.nextTick` vs microtasks — actual ordering relative to I/O callbacks." — same
5. 🔗 "Your box has 32 cores but `crypto.pbkdf2` / `fs` calls still queue. What's limiting you?" — https://github.com/mcollina/skills/blob/main/skills/nodejs-core/rules/libuv-thread-pool.md · `jose` HS256, S3 upload paths
6. 🔗 "Why is `process.env.UV_THREADPOOL_SIZE = 8` inside your entry file often silently ineffective?" — same
7. 🔗 "`Promise.all` vs `allSettled` — one slow widget blanks the dashboard?" — https://www.greatfrontend.com/questions/quiz/how-is-promiseall-different-from-promiseallsettled · your fan-in and the EDD `Promise.all` of per-warehouse config
8. ✏️ "Your EDD engine fetches per-warehouse config in one `Promise.all`. One warehouse's cutoff query throws. What does the whole cart get?"

## B. CPU-bound work on the request path

Targets: *Delivery Promise Engine* (H3, bin-packing, 8-stage pipeline at ~50K/day), *Reporting* (Excel generation).

9. ⭐ 🔗 "A heavy synchronous computation in a handler freezes the whole API under load. Why, and compare chunking with `setImmediate` vs a `worker_thread`." — https://medium.com/@moali314/handling-cpu-bound-tasks-in-node-js-part-1-ac34b4b45685 · card `promise_engine.md`
10. 🔗 "Is the bottleneck 'more concurrent requests' (→ `cluster`) or 'one heavy task blocks everything' (→ `worker_threads`)? When `child_process` instead?" — https://dev-aditya.medium.com/in-node-js-there-are-three-common-ways-to-handle-parallelism-and-improve-performance-for-f50ef79a72e3 · https://techinsights.manisuec.com/nodejs/worker-threads-vs-cluster-vs-child-process/
11. 🔍 "H3 lookups + unit-level bin-packing + an 8-stage pipeline per SKU per shipment, inline, at ~50K/day. What's the p99 tail, and where does it come from?" — ✏️ ⚠️ p95 unknown; say what you'd measure
12. 🔍 "`buildSLAMatrix()` runs on every lat/lng request and nobody reads the result. Cost?" — promise-engine-edd §12 #13 ⚠️
13. 🔍 "First-fit over exploded units — for a cart of 200 units, what's the complexity, and is it on the loop?" — §11 P3 ✏️
14. 🔍 "`json_to_sheet` at 300k rows in-process. What happens to the loop and to the task's memory?" — reports A.11 #1
15. ✏️ "Manual IST arithmetic (+5.5h epoch shift, `setHours`) with no tz library. What breaks on the day DST rules change somewhere your customers are?" — §11 P4 · honest: India has no DST; the risk is a non-IST warehouse

## C. Streams and backpressure

Targets: *Reporting* (mysql2 stream → ExcelJS WorkbookWriter → archiver → S3).

16. ⭐ 🔗 "Readable produces faster than the writable consumes. What specifically happens, and why is `highWaterMark` not a hard memory cap?" — https://blog.master.dev/your-node-js-streams-arent-backpressuring-theyre-silently-eating-your-memory/ · card `reports_and_banking.md`
17. 🔗 "You called `.write()` per row and ignored the `false` return. Why is that now an unbounded buffer, and why `stream.pipeline()` not `.pipe()` on client abort?" — same
18. 🔗 "`/export/transactions.csv` OOMs at 500k rows. Refactor to a DB cursor → Transform → HTTP response with proper backpressure." — https://github.com/kunj-21/backend-interview-daily/issues/8
19. 🔗 "Wire `connection.query(...).stream({highWaterMark})` from mysql2 into a Writable so only a bounded window is ever in memory." — https://github.com/sidorares/node-mysql2/issues/677 · https://dev.to/danielevilela/processing-1-million-sql-rows-to-csv-using-nodejs-streams-3in2
20. 🔍 "Stream vs chunk — what decides? Why does the in-memory path still exist for 15 handlers?" — reports A.2, A.8 ⚠️
21. 🔍 "ExcelJS `WorkbookWriter` writes to disk, then archiver zips at level 9, then S3. Where's the memory now, and what's the disk story on Fargate?" — A.2 ✏️
22. 🔗 "Bounded `asyncio.Queue` as backpressure between a producer and a slower consumer coroutine — the Python mirror." — https://www.coprep.ai/blog/python-concurrency-interview-questions-2026
23. ✏️ "The S3 upload fails at 90%. What's on disk, what's in the queue row, and what does the user see?"

## D. Memory — leaks, growth, App Engine

Targets: *Realtime Inventory Sync* (F2 crash under paged cron), *Promise Engine*, long-lived Express services.

24. ⭐ 🔗 "A 5-minute cron pulling paged inventory (thousands of items, tens of MB/page) in a small App Engine instance keeps hitting the soft memory limit and recycling. What accumulates per page, and why does pagination or a realtime webhook fix it rather than a bigger class?" — https://groups.google.com/g/google-appengine/c/LKiKSlqRsB4 · card `inventory_realtime.md` ⚠️ the 256 MB / 4.2 MB / 4,794 / 127 figures are **not in the repo** — verify from App Engine metrics before quoting
25. 🔗 "Memory grows 150 MB → 1.8 GB until OOM. Three candidates — unbounded cache, a `req.on('close')` listener never removed, a closure retaining outer scope. Which leaks and why can't mark-and-sweep collect it?" — https://github.com/kunj-21/backend-interview-daily/issues/5
26. 🔗 "Sawtooth vs ratchet memory graph — which is a leak?" — https://dev.to/axiom_agent/nodejs-memory-leaks-in-production-detection-heap-profiling-and-fix-patterns-5e5i
27. 🔗 "Heap-snapshot diffing against a production process — what do `# Delta` vs `Size Delta` tell you?" — https://medium.com/@amirilovic/how-to-find-production-memory-leaks-in-node-js-applications-a1b363b4884f
28. 🔗 "Why does taking a heap snapshot pause the loop, and when are you allowed to profile production?" — https://nodejs.org/learn/diagnostics/memory/using-heap-snapshot
29. 🔗 "Accumulating `EventEmitter` listeners — why a leak, and the actual prevention." — nodejsconsultant (above)
30. 🔍 "The 'qty resolved to 0' log fires per item × warehouse on snapshot pages. What's that in Loggly lines per page?" — promise-engine-inventory §8 ⚠️
31. 🔍 "One Pub/Sub message per webhook call, 10 MB ceiling, 100 KB body-parser limit upstream. Which limit hits first?" — §11.2
32. 🔍 "Full DataFrame dumps to CloudWatch on every OBC file. Memory, cost, and PII." — obc §12 #5 ⚠️
33. ✏️ "Documents that only grow (tombstones). At what point does a single order document become a memory problem in the fan-in layer?"

## E. Express 4 vs 5, TypeScript strict, Zod, Pino

Targets: *BFF* (Express 5 / TS strict / ESM / Node 24), *Promise Engine* (Express 4.18).

34. ⭐ 🔗 "In Express 4, why doesn't a rejected promise in an `async` handler reach your error middleware — and what changed in 5?" — https://betterstack.com/community/guides/scaling-nodejs/error-handling-express/ · https://medium.com/@priyanshu0dubey/express-js-version-5-a-detailed-comparison-with-version-4-71c46c269082 · you run both
35. 🔍 "`/v2/warehouse-edd` does `res.send(e)` on throw with no status. What leaks and what's the status?" — promise-engine-edd §12 #14 ⚠️
36. 🔍 "Missing pincode → HTTP 500. What does that do to your alerting?" — §12 #9 ⚠️
37. 🔗 "Why validate all of `process.env` against a Zod schema at boot and `process.exit(1)`, instead of failing lazily mid-request?" — https://sergiodxa.com/articles/using-zod-to-safely-read-env-variables · https://catalins.tech/validate-environment-variables-with-zod/
38. 🔗 "What does `strict` actually turn on, and why does `strictNullChecks` alone force touching so much unrelated code?" — https://www.greatfrontend.com/blog/typescript-interview-questions-for-senior-frontend-developers · https://www.datacamp.com/blog/typescript-interview-questions
39. ✏️ "ESM on Node 24 — what broke when you moved off CommonJS? `__dirname`? Top-level await? The `require('newrelic')` on line 2?"
40. ✏️ "Pino with PII redaction — what paths are redacted, and what happens to a field the redaction config doesn't know about yet?"
41. 🔍 "`require('../../../dbPromiseEngine')` but the file is `dbpromiseengine.js`. Where does it work and where does it break?" — promise-engine-edd §12 #4 ⚠️ case-sensitive filesystems
42. ✏️ "Express 5 path-to-regexp changes — did any route pattern break on upgrade?"

## F. Single-flight / promise coalescing

Targets: *Caching & Identity* (in-process coalescing + cross-container SET NX).

43. ⭐ 🔗 "A single celebrity key gets a million reads a second. What breaks and what do you do?" — https://www.techinterview.org/post/3233476816/caching-patterns-system-design-interview-cheat-sheet/ · card `caching_and_identity.md`
44. 🔗 "The cache cluster restarts cold at peak. Walk through the next thirty seconds." — same
45. 🔍 "Layer 1: concurrent misses in one container share one in-flight promise. What happens to callers 2..N if the loader rejects? Do they all reject, or retry?" — ✏️ from mydesignation §11 P2 — know what `loadWithLock` does
46. 🔍 "Layer 2: `SET NX` so one container runs the loader. What do the *other* containers do — spin, sleep, or serve stale?" — ✏️ same
47. 🔗 "Your critical section outlives the TTL, another process takes the lock, you finish and `DEL`. What did you just do?" — https://adhdecode.com/distributed-systems/distributed-locking-and-concurrency/lock-implementation-redis/
48. ✏️ "The in-flight promise map is per-process. With 4 API containers, worst case how many loader calls for one key on a cold miss?"

## G. Python — GIL, Flask, APScheduler, Kafka loop, pandas, Lambda

Targets: *Cheque Bounce* (3 in-process schedulers, onnxruntime), *Notifications* (consumer loop), *OBC* (pandas in Lambda, 600s).

49. ⭐ 🔗 "Two threads doing pure CPU work take the same wall-clock as one. Why, mechanically?" — https://www.techinterview.org/post/3233474450/python-interview-questions-2025-generators-decorators-async-await-type-hints-dataclasses-concurrency-gil-memory-management/ · onnxruntime OCR sharing a process with Flask threads
50. 🔗 "Can races still occur in CPython despite the GIL?" — https://www.coprep.ai/blog/python-concurrency-interview-questions-2026 · three schedulers on a shared base class
51. 🔗 "`asyncio` vs `threading` vs `multiprocessing` — and why the decision hinges on the GIL." — techinterview.org (above)
52. 🔗 "`ThreadPoolExecutor` or `ProcessPoolExecutor` for onnxruntime inference or pandas parsing?" — coprep (above)
53. 🔍 "Why cap onnxruntime threads only at first engine build?" — ripplr-fin-cbm §11: process singleton
54. 🔗 "Flask's `g` is per app-context. You memoise there and it 'stops working' in production. Why?" — https://testdriven.io/blog/flask-contexts-advanced/
55. 🔗 "How can `request`/`g`/`current_app` look like globals in a multi-threaded WSGI server?" — https://testdriven.io/blog/flask-contexts/
56. 🔗 "N processes each boot their own `BackgroundScheduler` for the same jobs. What happens?" — https://github.com/agronholm/apscheduler/discussions/765 · your 3 in-process schedulers ⚠️ answer: `SKIP LOCKED` claim, not APScheduler
57. 🔗 "Scheduler down an hour, job every 5 min — replay 12? `misfire_grace_time` vs `coalesce`." — https://apscheduler.readthedocs.io/en/3.x/faq.html · https://github.com/agronholm/apscheduler/issues/559
58. 🔍 "Two scheduler idioms in one repo — `BaseScheduler` ABC vs a bare `BackgroundScheduler` wrapper. Why?" — ripplr-fin-cbm §8 ⚠️
59. 🔗 "In `confluent-kafka`, when is the offset *stored* — at `poll()` (`enable.auto.offset.store=true`) or after your handler?" — https://app.sourcethread.com/thread/t-opus48-093f1efad18a0b · ⚠️ the exact library on the resume; know your config
60. 🔗 "Handler blocks past `session.timeout.ms` without `poll()`. Still declared dead post-KIP-62?" — same
61. 🔗 "`session.timeout.ms` vs `max.poll.interval.ms` — what happens when each is exceeded?" — same
62. 🔍 "`time.sleep(1)` after every commit. Why is it there?" — whatsapp §12 #5 ⚠️ undocumented; decide before the interview
63. 🔗 "Lambda init phase — what determines cold start, and why does more memory sometimes fix a slow cold start that isn't memory-bound?" — https://www.datacamp.com/blog/aws-lambda-interview-questions
64. 🔗 "Function C gets throttled though its traffic didn't change — the 1000-execution shared pool — and how reserved concurrency both fixes and creates risk." — https://repost.aws/questions/QU7NV9YgI3RGaqVOFdrZYnSQ/concurrency-limits-for-lambda-does-not-allow-to-reserve · https://www.dash0.com/knowledge/aws-lambda-concurrency
65. 🔗 "pandas in a 600s Lambda — where does memory go (dtype inference, `object` strings, chained intermediates), and how do `chunksize`/`dtype`/`usecols` move the ceiling?" — https://pythonspeed.com/articles/chunking-pandas/ · https://pandas.pydata.org/docs/user_guide/scale.html
66. 🔍 "HUL files have a 9-line preamble; Britannia has five columns named `Unit`. How does pandas cope, and where do you still loop row-wise?" — obc §11 Q6
67. 🔗 "Circular references with `__del__` — why can't the cyclic GC always collect them?" — techinterview.org (above)
68. 🔗 "`asyncio.gather` vs `TaskGroup` on exception and sibling cancellation." — coprep (above)
69. 🔗 "How should cancellation of an in-flight asyncio task work, and what goes wrong?" — same
70. 🔗 "Debug a mysteriously slow Python async service — what do you look at first?" — same
71. 🔍 "`datetime.utcnow()` for entry `created_at`, `datetime.now()` elsewhere. Consequence?" — obc §12 #14 ⚠️
72. ✏️ "The Kafka consumer is its own process with a Flask health endpoint on a thread. What does 'healthy' mean if the consumer loop is stuck on a poison message?"

## H. Retries, backoff, timeouts

Targets: skills line (Exponential Backoff), *Notifications* (WATI retry), *BFF* (`resilientFetch` 8s zero retries), *Fan-In* (6 copied retry wrappers).

73. ⭐ 🔗 "1,000 clients fail at once and retry on exponential backoff with no jitter. What happens to the recovering service, and why does full jitter fix it?" — https://oneuptime.com/blog/post/2026-01-06-nodejs-retry-exponential-backoff/view
74. 🔗 "Why is retrying a non-idempotent write on timeout dangerous even with correct backoff, unless the call carries an idempotency key?" — same · https://www.interviewsvector.com/javascript/auto-retry-for-promises · WATI sends, Razorpay create-order
75. 🔍 "WATI: 3 attempts, ~0.5s then 1.0s. Jitter? What if WATI is down for 10 minutes?" — gst_einvoicing card ✏️
76. 🔍 "`resilientFetch` gives Razorpay 8 seconds and zero retries. Why zero?" — mydesignation §11 follow-up
77. 🔍 "Six route handlers each carry their own retry-with-backoff. What happens when the policy needs to change?" — supertails-post-order §12 ⚠️
78. 🔗 "Visibility timeout equal to average processing time — why wrong, and why size off p99?" — https://oneuptime.com/blog/post/2026-01-27-sqs-message-visibility-timeout/view
79. 🔗 "Statically sized worker fleet on SQS — the two failure modes, and an observe→decide→act loop off queue depth." — https://adhdecode.com/articles/sqs/sqs-consumer-concurrency-scaling/
80. 🔗 "`ApproximateNumberOfMessagesVisible` vs `NotVisible` — mixing them up breaks autoscaling how?" — same
81. ✏️ "Kafka producer connects and disconnects per message. Under a 10x burst, what's the first symptom?" — reports-and-finservice B.8 ⚠️

## I. Crypto and security at runtime

Targets: *Exactly-Once* (HMAC raw bytes, timing-safe), *Caching & Identity* (jose HS256, OTP), *Reporting* (RSA-4096 + AES).

82. ⭐ 🔗 "Why does `signature === computed` create a timing attack, and what do you use in Node, Python, Go?" — https://gec.dev/articles/jwt-and-hmac-explained/ · https://github.com/SorobanKit/sorobanKit/issues/74
83. 🔗 "HMAC over the parsed/re-serialised JSON instead of the raw bytes — what's wrong?" — https://didit.me/blog/webhook-security-hmac-signature-validation/
84. 🔗 "The JWT header names its own `alg`. Why is trusting it dangerous; what's the RFC 8725 fix?" — https://qaskills.sh/blog/security-testing-jwt-algorithm-confusion
85. 🔍 "Timing-safe compares in four places, no shared helper." — mydesignation §11 follow-up ⚠️
86. 🔍 "Why is the ICICI webhook's crypto different from the pull API's? What throws if you swap them?" — reports B.11 #1: hybrid envelope vs per-field RSA; wrong block size
87. 🔍 "HDFC handler reads the HMAC and never verifies it (`TODO`). Exposure?" — B.12 ⚠️
88. 🔍 "Webhook HMAC secret unset → 503, never accept unsigned. Admin token unset → 503. Why fail closed here and open elsewhere?" — mydesignation §8 table
89. 🔗 "Store the OTP or a hash — does an RDB dump change the answer?" — https://arkesel.com/securing-transactions-with-otp-apis-10-best-practices/
90. ✏️ "RSA-4096 + AES hybrid envelope — why not RSA alone? What's the max plaintext for RSA-4096 with OAEP?"
91. ✏️ "Private key files sat untracked on disk in a checkout. What's the rotation procedure, and how do you find every place the old key was used?" — B.12 ⚠️ (values never reproduced anywhere)
