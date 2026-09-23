BFF ARCHITECTURE — MyDesignation Backend, Shopify

"The website is a Shopify theme with no backend of its own — every extra feature you see is a third-party app bolted onto the page. A native app can't work that way, so I built the server the app actually needed."

================================================ Step 1 ================================================

The 60-second version

"MyDesignation's website runs on a Shopify Liquid theme. It has no backend — reviews, size charts, bundles, loyalty, tracking, all of it is a Shopify app injected client-side into the page. That's fine for a browser, but a native mobile app can't inject third-party JavaScript into itself. So the app needed a real backend, and I built it — a backend-for-frontend that sits between the app and Shopify.

It's eighteen modules, eighty-four REST endpoints, and it's shipped as one Docker image that runs as two processes — an HTTP API and a queue worker. Shopify stays the system of record for catalog, orders, and customers. Postgres only holds what Shopify doesn't: sessions, OTP codes, payment claims, tracking events. Redis is a pure cache, never a source of truth.

The interesting engineering wasn't CRUD, it was orchestration under someone else's rate limit — six third parties, a cost-based GraphQL API, and a payment webhook that can race the app's own request."

================================================ Step 2 ================================================

The interviewer asks: "What does a BFF actually do here, concretely?"

"Four things, and I can point to code for each one. First, it aggregates — one app screen is one BFF call, and I fan out to Shopify GraphQL and merge the result server-side, so the app never fires six requests to paint a home screen. Second, it orchestrates — Judge.me for reviews, Kiwi for size charts, Easy Bundle, Nector for loyalty, ClickPost for tracking, Razorpay for payments, MSG91 for OTP — all six called from the server, not the app. Third, it owns exactly the data Shopify doesn't: twelve Postgres models, no more. Fourth, it protects the upstream — Shopify's GraphQL API is cost-based, not request-count-based, so caching and batching aren't nice-to-haves, they're what keeps the app inside someone else's quota."

Then give one concrete example:
"The bundle-builder screen needs product data for up to 250 items. Instead of 250 round trips, I batch them into chunked `nodes(ids:)` calls — roughly 195 ids costs about 25 points against Shopify's rate limit. Without batching, that one screen alone could burn the whole budget."

================================================ Step 3 ================================================

The ⭐ strongest card — one image, two processes, one-way pipe

"The API and the worker are the exact same compiled image. Docker Compose just overrides the start command — `node dist/server.js` for the API, `node dist/worker.js` for the worker. Same code, same container registry, same deploy. That means there's no drift between what the API thinks the data shape is and what the worker thinks it is, because there's only one build.

They talk to each other exactly one way — API enqueues to SQS, worker consumes. There's no worker-to-API channel at all. That's deliberate: it means the worker can never block a request, and the API can never be blocked waiting on worker state. If I ever needed the worker to talk back, that's a sign I've put the wrong logic in the wrong process."

================================================ Step 4 ================================================

They ask: "Why Postgres over MySQL for a Shopify-adjacent schema?"

"Because of one specific problem — cash-on-delivery double-submits. I needed a uniqueness constraint that only applies while a payment attempt is actually in flight, and disappears once that attempt fails so the customer can retry. That's a partial unique index — `WHERE status IN ('created','verified','paid')` — and MySQL doesn't have an equivalent. I'd have had to fake it with an extra table and a lock. Once I was on Postgres for that reason, the rest followed: jsonb for raw webhook payloads and frozen address snapshots, real enum types instead of string columns, and transactional DDL so a bad migration rolls back clean instead of leaving the schema half-changed."

================================================ Step 5 ================================================

They ask: "Why a standard SQS queue instead of FIFO?"

"FIFO buys you ordering, and you pay for it in throughput and cost. I don't need ordering here, and I can prove it instead of assuming it. The Razorpay consumer is idempotent — it no-ops on an already-settled order, so a duplicate delivery just does nothing. The ClickPost consumer is append-only with a unique constraint on waybill, status code, and timestamp, so it tolerates events arriving out of order and rejects duplicates as a constraint violation, not a bug. Once both consumers are safe under duplication and reordering, FIFO isn't protecting me from anything — it's just a tax."

================================================ Step 6 ================================================

They ask: "What happens if a required secret is missing when this deploys?"

"It never gets far enough to hurt anyone. The entire environment is validated with a Zod schema at process boot — every required key, database URL, Shopify creds, webhook secrets, cache admin token — and if any of them are missing, the process calls `process.exit(1)` immediately. I'd rather have a container that refuses to start than one that starts fine and then 500s on the first request that happens to need the value nobody set."

================================================ Step 7 ================================================

They ask: "How do you know a deploy actually succeeded?"

"The deploy script doesn't declare victory just because `docker compose up` returned zero. It polls `/health` for up to sixty seconds, and if the queue mode is SQS, it separately polls for up to sixty seconds that the worker container is running and its logs actually contain the worker's startup line. That second check matters — an API that's serving traffic while its worker silently died means every webhook queues up and nothing ever processes it. I wanted a deploy to fail loudly in that scenario, not quietly leave the queue undrained."

================================================ Step 8 ================================================

They ask: "What did your load testing actually show?"

"I ran six k6 profiles against real infrastructure — expected peak, five-times peak, a sudden spike, and a dedicated cart-write stress run. The headline numbers are solid: browse p95 around 186 milliseconds at expected peak, and throughput held around 341 requests a second sustained at five-times load.

But I'll volunteer the part a polished report would leave out — every single one of those four runs breached its own failure-rate threshold. The target was under 1% failed requests; I saw between roughly 9% and 29% depending on the run, and the cart-stress run also missed its own latency threshold. If I stopped at the p95 number, that would be a materially incomplete answer to 'what did your load test show.'"

================================================ Step 9 ================================================

⭐ The bug you SHOULD volunteer — search-suggest failed every single check

"Going through the raw k6 logs myself, not just the summary report, `GET /api/search/suggest` failed one hundred percent of attempts in three of the four runs — zero out of over four thousand in one of them. That's not a degradation curve, that's a hard functional break under whatever conditions the test target was in. I didn't chase down the exact status code in that pass, and that's the honest gap — the right next step is to capture the actual response instead of just the pass/fail check, because a 100%-fail pattern almost always means something structural, not 'the server got slow.'"

================================================ Step 10 ================================================

Cut these from your interview story:

❌ "Our load tests showed the system handles peak traffic cleanly."
Why it's weak: every run breached its own failure threshold — saying "cleanly" contradicts your own k6 logs the moment someone asks to see the report.

❌ "We migrated off Azure so the architecture is AWS-native throughout."
Why it's weak: the repo still has stale Azure references in comments, docs, and a default SSH tunnel host — true in spirit, sloppy if stated as fact without the caveat that cleanup is incomplete.

❌ "The whole system is fully covered by automated tests."
Why it's weak: 97 test files and 1,230 cases is real, but there's no coverage tool or threshold configured — you can't back "fully covered" with a number you don't have.

================================================ Step 11 ================================================

Numbers you must know

- 18 modules, 84 REST endpoints + 2 health endpoints = 86 total, matching the Postman collection exactly
- 97 test files, 1,230 test cases (grep-counted), 276 describe blocks
- 21,591 lines of application source, 17,079 lines of test source
- 51 hand-written GraphQL documents against Shopify Storefront/Admin, API version 2026-01
- 12 Postgres models, 5 enums, 19 Prisma-declared constraints + 2 hand-written partial unique indexes outside Prisma
- Postgres pool: 30 connections per process (raised from a default of 10)
- SQS_MAX_CONCURRENT_MESSAGES defaults to 1, capped at 10; long-poll wait defaults to 20 seconds
- Browse p95 at expected peak: 186ms (median 52ms); throughput at 5x peak: ~341 req/s
- http_req_failed across the four k6 runs: 10.02%, 10.57%, 8.70%, 29.26% — all against a <1% threshold
- Deploy gate: /health polled up to 60s; worker-liveness log check polled up to 60s
- [NEED FROM ME]: "What ECS task CPU/memory allocation and task count run the api and worker services in production today?"
- [NEED FROM ME]: "Has anyone found the root cause of search-suggest failing 100% of requests under load — is there a known fix?"
- [NEED FROM ME]: "What was the actual ECS task CPU/memory utilization during the peak and 5x k6 runs?"
- **Storefront volume: 14,600 → 48,700 orders/month (3.3x).** Confirmed 2026-09-22 from Shopify.
  ⚠️ **This is Shopify-wide and INCLUDES web orders.** Never say the app caused it. Say "the
  backend I built serves a storefront that went from about 14.6K to 48.7K orders a month." If an
  interviewer asks whether the app drove the growth, the honest answer is that you do not have the
  app-only split — which is a better answer than a claim that collapses under one follow-up.
  (Note: this is 3.3x, a 234% increase. It is NOT "250%".)
- [NEED FROM ME]: "What's the app-specific DAU/MAU, request volume, or order share — separate from the whole-store figures above? This is the number that would let me claim impact rather than context."
