# MyDesignation Backend — Engineering Analysis

Repo: `/Users/vikas1141sharma/Developer/MyDesignation/mydesignation-backend` (read-only pass; nothing modified, no app run, no DB/AWS touched).

**AWS-only scope note:** this repo migrated from Azure to AWS. Everything below describes the AWS implementation only. Known Azure-era remnants (stale comments/docs/defaults) are catalogued in §12 so they are not mistaken for current behavior — they are not described as current anywhere else in this file.

---

## 1. Ownership

Per the codebase owner's own account, he designed and built the entire MyDesignation BFF. This pass performed no authorship verification (no `git log`/`git blame`) and makes no ownership claim of its own — everything below is a technical analysis of the code as it stands.

---

## 2. Architecture, components, data flows, external systems

**Two processes, one image.** `src/server.ts:1-10` boots the Express API via `createApp(buildContainer())`. `src/worker.ts:1-44` boots a separate SQS-polling process from the *same compiled image* (`docker-compose.yml:19-25` overrides `command` to `node dist/worker.js`). The two communicate **one-way only**, api → worker, via SQS (`src/infrastructure/queue/queue.ts:1-46`); there is no worker → api channel.

**Composition root.** `src/container.ts` is the only file that `new`s concrete classes. `buildContainer():109-269` wires all 18 controllers behind a `Container` interface (`:83-102`); `buildWorker():296-332` is a *separate* root that wires only what the queue processor needs (payments + webhooks services), not the full controller graph. `buildQueue():279-282` picks `InlineQueue` (dev/test, in-process) or `SqsQueue` based on `config.QUEUE`.

**Middleware chain (`src/app.ts:32-118`), in the deliberate order it's written:**
`requestId (:42) → pino-http (:43) → CORS (:50) → express.json({limit:'100kb'}) with a rawBody-capturing verify hook (:51-63) → global rate limit (:64) → [rate-limit-bypass boot warning, :66-76] → /health (:80-82) → /ready (:88-94) → 18 module routers (:96-113) → errorHandler (:115)`.
CORS is deliberately placed before the rate limiter and body parser (comment at `:44-49`): headers survive onto a downstream 429/413, and OPTIONS preflights short-circuit to 204 without burning rate-limit budget. `trust proxy = 1` (`:40`, one hop only, not `true`) is what makes `req.ip` the real client IP rather than the whole X-Forwarded-For chain — load-bearing for both rate limiters.

**Modules mounted (18, `app.ts:96-113`):** product, collection, search, cart, bundle, checkout, payments, coupons, auth, account, returns, loyalty, wishlist, app-logs, tracking, content, webhooks, admin. Confirmed by directory listing of `src/modules/` and by the `Container` interface — 18, not 17 (an easy off-by-one if `checkout` is skimmed past next to `payments`).

**Endpoints:** grepping every `*.routes.ts` for `router.(get|post|put|patch|delete)(` gives **exactly 84** across the 18 modules. Add the two health endpoints defined directly in `app.ts` (`/health`, `/ready`) and the total is **86 HTTP endpoints** — which is exactly the request count in `postman/mydesignation-backend.postman_collection.json` (86 requests, 18 top-level folders: the same 17 module names plus a `health` folder). Three independent counts agree.

**External systems and how each is reached:**

| System | Direction | Mechanism |
|---|---|---|
| Shopify Storefront + Admin GraphQL (API version `2026-01`, `config.ts:98`) | outbound | `graphql-request` clients, 51 `.graphql` documents in `src/gateways/shopify/queries/`, routed through the shared `resilientFetch` (`shopify.client.ts:6-8`) |
| Razorpay | outbound (create/fetch order+payment) + inbound webhook | `gateways/razorpay/razorpay.gateway.ts` (HMAC via `timingSafeEqual`); webhook at `POST /webhooks/razorpay` |
| MSG91 | outbound | phone OTP via a widget gateway (MSG91 generates/sends/verifies); email OTP + transactional email via a separate email gateway (backend generates/verifies, MSG91 only delivers) |
| Google | outbound | OIDC id-token verification + People API phone enrichment (two different gateways, two different tokens — `container.ts:144-146,205,216`) |
| Apple | outbound | Sign in with Apple id-token verification |
| ClickPost | outbound (poll) + inbound webhook | `gateways/clickpost/clickpost.gateway.ts` for `GET /api/tracking/:waybill`; webhook at `POST /webhooks/clickpost`, shared-secret token, timing-safe compare |
| Judge.me | outbound | reviews REST API, read-through cached |
| Kiwi Sizing | outbound | public, unauthenticated size-chart REST endpoint |
| Easy Bundle / Giftbox | outbound | bundle-builder config REST API, batched product hydration (see §10 bullet 10) |
| Nector | outbound | loyalty/coin-balance REST API |
| Logisy | outbound | returns presigned-URL proxy |
| GoKwik | outbound (checkout) — webhook is **mounted but unimplemented** (`webhooks.controller.ts:119-121` throws `NotImplementedError`; confirms the perf/security doc's own S-10 finding is still true today) |
| MST (iWishlist) | outbound | wishlist proxy — the actual wishlist third party (README's "Swym" claim is stale, see §12) |
| CleverTap | none — `src/gateways/clevertap/clevertap.gateway.ts` exists but both methods `throw new Error('TODO: implement …')` and the class is **never constructed in `container.ts`**. Dead code today, not a live integration. |
| AWS SQS, S3, RDS, ElastiCache | infra | see §6 |

**Data flow shape** (his own framing, verified against the code): Shopify is the system of record for catalog/orders/customers; Postgres holds only what Shopify doesn't (sessions, verified identifiers, OTP codes, payment/order correlation, tracking events, wishlist preference, app config, pincodes — 12 models, §4); Redis is a pure cache/rate-limit layer, never a source of truth.

---

## 3. APIs by module

| Module | Endpoints | Purpose | Key dependencies (from `container.ts`) | Failure posture |
|---|---|---|---|---|
| product | 6 | PDP aggregate, standalone size-chart, recently-viewed card hydration | Shopify, Judge.me, ShopifyCustomer, S3, Kiwi | PDP throws `NotFoundError` on a missing/variant-less product; size-chart is best-effort, always `{}` on any failure (`product.service.ts:68-80`, `kiwi.gateway.ts:71-115`) |
| collection | 3 | PLP / collection page, collections list | Shopify | — |
| search | 4 | full search (facet/sort/paginated), predictive suggest, recently-viewed, popular searches | Shopify, ProductService | both `search()` and `suggest()` are read-through cached on the normalized query (`search.service.ts:63-90`) — see §9 for a live discrepancy found in the suggest path under load |
| cart | 10 | cart CRUD, line mutations, coupon/discount codes, attributes | Shopify, CartRepository, CartSyncService, ShopifyCustomer, CouponSource | writes to live Shopify cart mutations; `CartRepository` persists the customer→cart anchor (`CustomerCart` model) |
| bundle | 2 | Easy Bundle Builder config + hydrated products | EasyBundle gateway, Shopify | batched `nodes(ids:)` hydration, chunked at 250 (§10 bullet 10) — no dedicated Postman folder (§12) |
| checkout | 1 | GoKwik checkout config | GoKwik, Shopify | — |
| payments | 5 | Razorpay create/verify, COD place, order status poll | Razorpay, Shopify, ShopifyOrder, PaymentOrderRepository, ContentRepository, ShopifyCustomer, CartRepository, AuditLogRepository | the exactly-once claim protocol — see §4/§10 bullet 1 |
| coupons | 2 | applicable coupons, milestone/stepper | CartService (composed, no separate Shopify call) | coupon catalogue is 100% Shopify-metaobject-sourced, no DB table (`schema.prisma:186-191`) |
| auth | 13 | OTP request/verify (phone+email), Google/Apple login, refresh, logout, profile | LoginStrategyRegistry, IdentityResolverService, SessionService, Msg91Otp, EmailOtpService, ShopifyCustomer, Nector, GooglePeople | see §10 bullets 4-5 |
| account | 8 | profile, address book, orders, order detail (embeds tracking) | Shopify, ShopifyCustomer, TrackingService, PincodeRepository, AddressMetaRepository | depends on TrackingService — order-detail responses carry per-shipment tracking |
| returns | 1 | Logisy presigned return URL | Logisy gateway | **`contact`/`order_number` come from query params, not the session** — self-documented in `returns.routes.ts:8-9` (see §12, SEC-5) |
| loyalty | 2 | Nector coin balance / ledger | Nector gateway | — |
| wishlist | 10 | wishlist CRUD, default-list preference | MstWishlist gateway, Prisma | MST is the sole source of truth for wishlist *items*; Postgres holds only the one-row-per-customer default-list preference (`WishlistPreference`) |
| app-logs | 1 | client-side log ingestion | Pino logger only | **unauthenticated** by design — rate-limited + size-capped, not client-keyed (matches the perf doc's S-3, still open) |
| tracking | 1 | live ClickPost poll for Track My Order | ShipmentTrackingRepository, ClickPost gateway | customer id is taken from `req.customer.shopifyCustomerId` (JWT-derived), not a request param — ownership-scoped correctly (`tracking.controller.ts:8,28`) |
| content | 10 | home, config, menus, stores, blog, pages, trust-badges | Shopify, ContentRepository | heaviest read-through cache user; catalog webhooks invalidate these keys (§4) |
| webhooks | 4 | Shopify (cache-bust), Razorpay (payment settlement), ClickPost (tracking), GoKwik (unimplemented stub) | WebhooksService, QueueProducer, RazorpayGateway, RazorpayWebhookLogRepository | see §5 |
| admin | 1 | manual cache invalidation (ops escape hatch) | AdminCacheService | fail-closed 503/401/400/200 contract, timing-safe token (`admin.controller.ts:16-25`, `admin-cache.service.ts:32-55`) |

**Worker (`src/worker.ts` + `WebhookProcessor`, `webhook-processor.ts:24-83`):** consumes exactly two message types — `razorpay` (routes to `PaymentsService.fulfilFromWebhook`, idempotent no-op on unknown/settled orders) and `clickpost` (routes to `WebhooksService.handleClickpostEvent`, append-only, dedup on a unique constraint). A malformed ClickPost payload is logged and **completed without retry** (`:67-71`, it would never parse on redelivery); an unknown message-type **throws** so it dead-letters visibly (`:76-81`) rather than vanishing.

---

## 4. Database

**Schema (`prisma/schema.prisma`, 350 lines): 12 models, not 11.** `CustomerSession`, `VerifiedIdentifier`, `OtpCode`, `AppAddressMeta`, `WishlistPreference`, `AppConfig`, `AuditLog`, `CustomerCart`, `PaymentOrder`, `RazorpayWebhookLog`, `ShipmentTracking`, `Pincode`. `AppAddressMeta` was added later, by hand, via `prisma/sql/002-app-address-meta.sql` — it postdates the 11-table baseline DDL (`000-baseline-schema.sql`), which is why an 11-count is an easy (and now stale) thing to have carried forward. **5 enums:** `IdentifierKind`, `VerificationMethod`, `IdentifierSource`, `PaymentOrderStatus`, `PaymentMethod`.

**No foreign keys anywhere, by design** — Shopify ids (customer, cart, order) are the join keys across every table; the schema comment at the top (`schema.prisma:1-2`) states Shopify remains the system of record and the app owns nothing else.

**Constraint count, precisely reconciled:**
- The hand-generated baseline (`prisma/sql/000-baseline-schema.sql`, pre-`AppAddressMeta`) contains **11 `PRIMARY KEY` + 18 `CREATE [UNIQUE] INDEX` statements = 29 constraints total.**
- Today's `schema.prisma` (12 tables) declares **12 primary keys + 19 `@unique`/`@@unique`/`@@index` constraints** (`CustomerSession` refreshTokenHash-unique + 2 indexes; `VerifiedIdentifier` `@@unique([kind,value])` `:110` + 1 index; `OtpCode` `@@unique([channel,identifier])` `:127`; `AppAddressMeta` 1 index; `AuditLog`/`CustomerCart` 1 index each; `PaymentOrder` 3 unique columns (`razorpayOrderId`, `razorpayPaymentId`, `shopifyOrderId`, all `:246-258`) + 1 index; `RazorpayWebhookLog` 1 unique + 2 indexes; `ShipmentTracking` `@@unique([waybill,clickpostStatusCode,statusTimestamp])` `:329` + 2 indexes).
- **Two more unique indexes exist only as hand-written SQL, never expressible in Prisma at all:** `payment_orders_cod_cart_claim` and `payment_orders_store_credit_cart_claim`, both partial unique indexes on `payment_orders(cart_id)` scoped `WHERE method = <m> AND status IN ('created','verified','paid')` (definition quoted in `prisma/sql/001-zero-payable-store-credit.sql:107-115`). Their existence on **both prod and staging** was verified read-only via a pre-deploy gate query in that same file (`:14-32`, dated 2026-09-02, "ALL PRESENT"). These are the actual DB-side mechanism behind `PaymentOrderRepository.createClaim` (`payment-order.repository.ts:71-80`) treating a `P2002` as "lost the race" rather than a real error.

**Atomic conditional updates, not multi-statement transactions.** The payment claim protocol (§10 bullet 1) never wraps multiple statements in a `BEGIN...COMMIT`. It relies entirely on **single-statement conditional `UPDATE ... WHERE status IN (...)`**, reading the driver's affected-row count as the race decision (`claimForFulfillment`, `payment-order.repository.ts:148-162`: `res.count === 1` means "I won"). This is a deliberate simplicity/lock-contention trade-off over holding a transaction open across a network call to Shopify — see §8.

**jsonb usage (5 columns):** `AppConfig.value`, `PaymentOrder.shippingAddress` (a frozen address-book snapshot fulfilment reads from, never a live lookup), `RazorpayWebhookLog.payload` (the entire raw webhook body — the model's own comment flags this as PII: shipping address, name, email, phone in plaintext, and asks for a retention purge before it's more than "a debugging aid in production," `schema.prisma:277-281`), `ShipmentTracking.rawPayload`, `AuditLog.metadata`.

**DDL strategy: Prisma Migrate is deliberately not used.** `prisma.config.ts:9-21` states it plainly: no `prisma/migrations` directory, no `_prisma_migrations` table, schema changes are hand-written SQL applied to each database individually. The two migrations that exist (`prisma/sql/001`, `prisma/sql/002`) are not migration-runner scripts — they are **deploy runbooks**: a pre-deploy gate query, the DDL itself (idempotent, `IF NOT EXISTS`/`CONCURRENTLY`), a post-deploy smoke test, and — for `002` — an explicit "confirm this is not prod by accident" query (`002-app-address-meta.sql:47-52`) before the `BEGIN;...COMMIT;` block. That is a materially more disciplined DDL process than "run migrate deploy."

---

## 5. Async (SQS)

**Settlement is explicit, not automatic** (`sqs.queue.ts:36-44,168-224`): handler returns → `DeleteMessageCommand`; handler throws, or the body isn't valid JSON → nothing is deleted, and the message is left for redelivery after the queue's visibility timeout, eventually dead-lettering via the redrive policy. A JSON-parse failure is deliberately **never deleted** (`:174-190`) — a producer bug stays visible in the DLQ instead of silently vanishing.

**Standard queue, not FIFO — a proven, not assumed, safety property.** The reasoning is written into both the queue driver's own docstring (`sqs.queue.ts:41-43`) and the migration write-up (`docs/2026-08-01.md`): Razorpay fulfilment **no-ops on an already-settled order** (idempotent) and ClickPost events are **append-only with a unique-constraint dedupe** (`ShipmentTracking @@unique([waybill, clickpostStatusCode, statusTimestamp])`) that also tolerates arriving out of order. A standard queue's at-least-once delivery and occasional reordering are therefore harmless by construction, and the design gets to skip FIFO's throughput ceiling and cost.

**Concurrency knob defaults to 1.** `SQS_MAX_CONCURRENT_MESSAGES` defaults to `1` and is capped at 10 (`config.ts:65`) — the receive loop (`sqs.queue.ts:135-166`) processes up to that many messages in parallel per poll, long-polling for `SQS_WAIT_TIME_SECONDS` (default 20, capped at 20) so an idle worker costs roughly 3 requests/minute instead of hot-looping.

**Per-message isolation:** `Promise.all(messages.map(...))` (`sqs.queue.ts:164`) means one bad message in a batch never blocks or fails the others.

**Idempotency in one sentence per path:** Razorpay — `claimForFulfillment`'s conditional `UPDATE` (§4) makes a duplicate webhook delivery a no-op after the first success. ClickPost — the `@@unique` on `(waybill, clickpostStatusCode, statusTimestamp)` makes a retried delivery a duplicate-key no-op, not a duplicate row.

---

## 6. Infrastructure — what is and is not used

**Actually used (AWS):**
- **SQS** — one standard queue + a DLQ, redrive `maxReceiveCount` ≈ 5 (`docs/2026-08-01.md`), visibility timeout sized above the slowest handler.
- **S3** — presigned `PutObject`/`GetObject` for review images (`s3.gateway.ts:51-101`); `S3_PUBLIC_READ` switches between a permanent public URL and a short-lived presigned GET (`readUrl`, `:84-101`).
- **RDS Postgres** — reached with TLS forced on (`DATABASE_SSL`, `config.ts:17-27`); `rejectUnauthorized: false` (chain not validated against the AWS CA bundle — a real, still-open gap, §12).
- **ElastiCache Redis.**
- **ECS/Fargate behind an ALB** (prod) — per `docs/2026-08-31.md`/`2026-09-02.md`; **no ECS task definition or CI config exists in this repo**, so the exact task/service shape is documented, not IaC-verifiable from the checkout.
- **EC2** — one all-in-one staging box (per `docs/2026-08-31.md`: 4 containers — app, worker, postgres, redis — on bridge networking) and a separate bastion/jump host for RDS/SSH access. Prod deliberately keeps a *different, split* topology (ECS + RDS + ElastiCache behind an ALB) from staging's single-box shape — a real, documented divergence between environments, not an oversight.
- **IAM instance roles** — the SQS and S3 SDK clients use the default credential chain (`config.ts:41-50`); least privilege is an IAM-policy concern (`sqs:SendMessage` for the API, `sqs:ReceiveMessage`+`sqs:DeleteMessage` for the worker), not a per-role connection string, unlike the Azure Service Bus predecessor.
- **CloudWatch Logs** — pino JSON lines shipped from ECS task stdout.

**Deliberately not used:** SES (email goes through MSG91), Secrets Manager (secrets live in `.env` on the host — see §12), any IaC tool (no Terraform/CDK/CloudFormation anywhere in the repo), BullMQ (a stale docker-compose comment aside, §12), Prisma Migrate (§4).

**Three Docker Compose topologies, one image:**
| File | Shape | Networking |
|---|---|---|
| `docker-compose.yml` | prod-shaped: `app` + `worker` only, datastores external | `network_mode: host` |
| `docker-compose.dev.yml` | laptop: an SSH-tunnel sidecar + bind-mounted source, `npm install && prisma generate && npm run dev` on start | tunnel netns shared with `app` |
| `docker-compose.staging.yml` | all-in-one: `app`, `worker`, `postgres`, `redis` as containers, log rotation capped (`max-size: 10m`, `max-file: 3`) so unbounded pino output can't fill a 19GB disk | bridge, service-name DNS |

**Multi-stage Dockerfile** (`Dockerfile:1-51`): builder stage on `node:24-slim` runs `prisma generate && npm run build`; runner stage does `npm ci --omit=dev`, copies only `dist/` (which carries the generated, **Rust-engine-free** Prisma 7 client along with it, `:40-43`), runs as non-root `USER node` (`:47`), bakes `NODE_ENV=production` in (`:28-34`, explicitly to avoid a forgotten `-e NODE_ENV=production` silently booting prod in dev mode). No `HEALTHCHECK` instruction in the image itself — liveness is delegated to the orchestrator (`deploy/deploy.sh`'s own curl loop on staging/EC2, presumably the ALB target-group check on ECS).

**`deploy/deploy.sh`, gated in exact order** (`:93-161`): `git fetch/pull --ff-only` → `docker compose build` → `docker compose up -d` → **poll `/health` for up to 60s** (`:120-135`) → **if `QUEUE=sqs`, poll for up to 60s that the worker container is `running` AND its logs contain `"mydesignation-worker started"`** (`:137-161`) — a deploy cannot report success while the queue is silently going undrained. The script explicitly never runs a migration (`:24-27,115-116`), and fails fast with actionable messages when `COMPOSE_FILE`, `.env`, `.env.postgres`, or `SQS_QUEUE_URL`/`AWS_REGION` are missing (`:57-91`).

---

## 7. Reliability + performance mechanisms, with evidence

- **Resilient HTTP client** (`resilient-client.ts:16-77`): per-attempt `AbortSignal.timeout`, exponential backoff **with full jitter** (`backoffMs`, `:17-19`: `base * 2^attempt + random(0,base)`, preventing synchronized retry storms), retrying only 5xx/network errors — a 4xx returns immediately and never burns the retry budget. Budgets are centralized and reasoned-about per upstream (`constants/index.ts:297-344`): Shopify/Logisy/Easy Bundle get 8s×2 retries; Judge.me/MSG91/MST get 5s×2; Google People and Kiwi get short, low/no-retry budgets because both have a working fallback; **Razorpay gets 8s and *zero* retries**, called out explicitly as a correctness requirement, not a latency choice — a blind retry after Razorpay has already created an order would mint a duplicate.
- **pg pool raised from 10 to 30 connections per process** — confirmed both in current config (`config.ts:31`, default `PG_POOL_MAX=30`) and in the performance report's own account of *why* (`docs/MyDesignation-Performance-Security-Report.md §5`: "sized up (from 10 to 30 connections per process)... to give more headroom for concurrent checkout at a sale-day peak").
- **TLS-on-RDS incident, documented in the code itself** (`prisma.ts:15-24`): a 2026-08-01 production incident where `pg`'s default `ssl=false` against RDS produced a misleading "User was denied access on the database" error, dead-lettering every webhook — not a credentials problem at all. `DATABASE_SSL` now forces TLS.
- **Webhook body-parser edge case turned into a 200, not a 500** (`error-handler.ts:12-20`): a non-JSON body on `/webhooks/*` is answered 200 so ClickPost/Razorpay/Shopify stop retrying a payload that will never parse.
- **Fail-fast env validation** (`config.ts:260-287`): a Zod `superRefine` enforces a curated `REQUIRED_ENV_KEYS` list (DB, Redis, Shopify creds+webhook secret, cache admin token, Logisy/ClickPost/MSG91 keys) in every environment except `test`, and `process.exit(1)`s on failure at boot rather than at the first request that needs the missing value.
- **PII redaction in logs** (`logger.ts:7-17`): `req.headers.authorization`, `req.headers.cookie`, and any `password`/`token`/`accessToken`/`refreshToken`/`phone` field, redacted at the Pino config level for every log call.
- **Two-layer cache stampede guard** and **structural never-cache-a-failure guarantee** — detailed in §10 bullets 6-7 with full mechanism.
- **k6 performance program** — 6 profiles (`smoke`, `load`, `stress`, `stress-readonly`, `spike`, `cart-stress`) plus 8 non-destructive security probes (`perf/security/probes.ts`: OTP brute-force, rate-limit reality check, IDOR, security headers, body size, unauthenticated writes, JWT TTL, webhook signature). All exact measured numbers are in §9.

---

## 8. Design decisions, trade-offs, alternatives, known gaps

**Postgres over MySQL** — his own stated reasoning (`docs/… project story`), verified against real schema features in use: partial unique indexes (the COD/store-credit claim guard, §4, has no MySQL equivalent), `jsonb` columns (5 of them, §4), native enum types (5 enums), and transactional DDL for the hand-applied migrations.

**SQS standard vs FIFO** — covered in §5. The trade is explicit and load-bearing: FIFO's ordering guarantee is paid for in throughput and cost, and this design doesn't need it because both consumers are idempotent and order-tolerant by construction, not by luck.

**No Prisma Migrate, no foreign keys** — both covered in §4. The FK decision is really "Shopify ids are the join keys, and Shopify — not this Postgres instance — is the system of record," which is a coherent single design stance, not two separate ad-hoc calls.

**Atomic conditional `UPDATE` over a database transaction for the payment claim** (§4) — trades the safety net of a wrapping transaction for avoiding a long-held lock/transaction across a network round trip to Shopify. This only works because the state machine (`created → verified → paid/failed/superseded`) and the unique constraints together make every individual statement's precondition sufficient on its own.

**Fail-open vs fail-closed, deliberately split by blast radius**, not applied uniformly:
| Fails **open** (availability > strictness) | Fails **closed** (safety > availability) |
|---|---|
| Global rate limiter (`rate-limit.ts:54-59`) | Shopify webhook HMAC when the secret is unset — 503, never accepts unsigned (`webhooks.controller.ts:82-86`) |
| Auth rate limiter (`auth-rate-limit.ts:43-48`) | Admin cache-invalidate endpoint when its token is unset — 503 (`admin-cache.service.ts:32-42`, `admin.controller.ts:27-31`) |
| OTP resend cooldown (`redis.ts:271-288`) | Razorpay webhook signature mismatch — 401 |
| OTP verify-attempt counter (`redis.ts:302-311`) | Env validation at boot — hard `process.exit(1)` |
| The read-through cache itself (any Redis error → call the loader) | |

**Known gaps, verified against current code (not the stale doc — see §12 for what's stale):**
- **`SQS_MAX_CONCURRENT_MESSAGES` defaults to 1** (`config.ts:65`) — the simplest, most conservative choice; raising it is a one-line config change but changes the concurrency assumptions the worker's idempotency was designed against and hasn't been load-tested at a higher value in the k6 results reviewed here.
- **The rate-limit bypass file is live in the current source tree.** `src/middleware/rate-limit-bypass.ts:20`: `const BYPASS_ENABLED = true;`, unconditional, no environment gate, no expiry mechanism — matched against one hardcoded IPv4 address (`:26`, withheld here per task instructions) that skips **both** the global and the auth rate limiter (`rate-limit.ts:46-49`, `auth-rate-limit.ts:30-33`). The file's own comment explicitly warns against exactly this state ("Do NOT leave `BYPASS_ENABLED = true` in a build that stays on production") and `app.ts:66-76` logs a loud boot warning whenever it's on — but the warning is a mitigation for visibility, not a control that turns it off. **Not verified in this pass:** whether this exact file state is what's actually deployed to the running production container (that would require inspecting the live ECS task image, which is out of scope for a read-only repo pass).
- **`rejectUnauthorized: false` on the RDS TLS connection** (`prisma.ts:31-36`) — the transport is encrypted but the server certificate chain is not validated against a trusted CA bundle.
- **No `helmet`, no security-header middleware anywhere** (`grep -r helmet` across `src/` and `package.json` returns nothing) — no HSTS, `X-Content-Type-Options`, `X-Frame-Options`, or CSP on any response.
- **`GET,POST /api/returns/presigned-url` authorizes off request query params, not the session** — `returns.routes.ts:8-9` says so in its own comment ("contact/order_number come from the request, not the session"); `returns.controller.ts:9-11` passes them straight through with no cross-check against `req.customer`. The route does require a valid JWT (`requireAuth`, `:15`), so it isn't anonymous — but a logged-in customer can query another customer's return-URL if they know or guess their phone/email and order number.
- **`/api/app-logs` accepts writes with no client key**, bounded only by the global rate limit and the 100kb body cap.
- **No test-coverage tool/thresholds configured** — `vitest.config.ts` sets only `fileParallelism: false`; there is no `coverage` block and no CI config in the repo to enforce one.
- **No IaC** for the ECS/ALB/RDS/ElastiCache topology that prod docs describe — it exists only as narrative in `docs/*.md`, not as a reviewable/diffable template in this repo.

---

## 9. Numbers

### (a) Derivable from code/docs, with source

**Scale**
- App source: **21,591 LOC** (`src/`, excluding `src/generated/`, excluding `*.test.ts`).
- Test source: **17,079 LOC**, **97 files** (`*.test.ts` under `src/`) — his own story states "~93 test files"; the current, directly-counted figure is 97 (a small, harmless drift worth updating in the story, not a real discrepancy).
- **276** `describe(` blocks, **1,230** `it(`/`test(` cases (grep count; close to a previously-cited "~1,233" estimate).
- **18** modules mounted (`app.ts:96-113`), **84** REST endpoints across their route files, **+2** health endpoints (`/health`, `/ready`) = **86** total — matching the Postman collection's **86** requests across **18** folders exactly.
- **51** `.graphql` query/mutation documents (`src/gateways/shopify/queries/`, 52 files minus one `.gitkeep`).
- **12** Prisma models, **5** enums, **19** `@unique`/`@@unique`/`@@index` constraints declared in `schema.prisma` + **12** primary keys; the pre-`AppAddressMeta` baseline SQL has **11 PRIMARY KEY + 18 CREATE INDEX = 29** constraints; **2 additional** hand-written partial unique indexes exist outside Prisma entirely (§4).
- **6** k6 load profiles, **8** k6 security probes.

**Timings / limits (all from `src/shared/constants/index.ts` and `src/config/config.ts` unless noted)**
- Cache TTLs: catalog (HOME/COLLECTION_PAGE/PRODUCT/DOOM_SCROLL_FEED/PRODUCT_CARDS) **900s**; near-static (COLLECTIONS_LIST/CATEGORIES/MENUS/POPULAR_SEARCHES/STORES/TRUST_BADGES/EASY_BUNDLE) **1800s**; SIZE_CHART **3600s**; SEARCH/SUGGEST **120s**; APP_CONFIG **60s**; CUSTOMER/REVIEWS **300s**; WISHLIST/WISHLIST_INDEX **120s**; OTP_COOLDOWN **30s** (`:273-295`).
- Global rate limit: **100 requests / 60s per IP** (`:180`). Auth rate limit: **20 requests / 60s per IP** (`auth.routes.ts:20-21`).
- OTP verify attempt cap: **5** wrong guesses invalidate the code (`:171`). OTP expiry default: **10 minutes** (`config.ts:202`).
- Access token TTL default: **900s (15 min)**; refresh token TTL default: **15,552,000s (180 days)** (`config.ts:77-78`).
- Postgres pool: `PG_POOL_MAX` default **30** (raised from 10, per the performance report's own §5 — `config.ts:31`), idle timeout **30,000ms**, connect timeout **5,000ms**.
- SQS: `SQS_MAX_CONCURRENT_MESSAGES` default **1** (max 10), `SQS_WAIT_TIME_SECONDS` default **20** (max 20) (`config.ts:65-68`).
- Global JSON body cap: **100kb** (`app.ts:56`).
- Review images: max **5** per review, upload-URL TTL **15 min**, read-URL TTL **72h** (`:356-366`).

**Measured k6 results — quoted exactly from `docs/MyDesignation-Performance-Security-Report.md` and cross-checked against the raw `perf/results/*.log`:**

| Run | Requests | Throughput | Browse p95 | Search p95 | Cart p95 | Payment-methods p95 |
|---|---|---|---|---|---|---|
| Expected peak | 41,146 | ~72 req/s | 186ms (median 52ms) | 557ms | 2.3s | 1.21s |
| 5× peak (read stress) | 204,876 | ~341 req/s | 239ms | 479ms | n/a (see cart-stress row) | not run |
| Sudden spike (120 max VUs, instant 3× jump) | 24,490 | — | 216ms (215.95ms exact), worst single response **840.1ms** | 423ms (423.11ms exact) | not run | not run |
| Cart-stress (200 max VUs, dedicated 5× write run) | 44,167 total HTTP requests | — | n/a | n/a | **2.35s**, worst response **10.29s** | n/a |

- Cart-stress **check** success: **99.98%** (29,441 / 29,446 `checks_total`) — the two named checks are "cart create 2xx/3xx" (14,721/14,725 ok) and "cart add-line 2xx/3xx" (14,720/14,721 ok). VUs confirmed **200 max** directly from `perf/results/cart-stress-run.log`'s own k6 banner.
- Spike run VUs confirmed **120 max** directly from `perf/results/spike-run.log`'s own k6 banner (`PEAK_VUS × 3`, i.e. `PEAK_VUS=40` was the configured peak for that run).
- Readiness probe during testing: **Postgres ~22ms, Redis ~1ms** (report §4).
- Sizing input: **~951,000** unique visitors/month (trailing 12 months) and a busiest month (Aug 2025) of **42,564 orders** — the report is explicit that this is the **whole Shopify store** (web + app combined), not BFF-specific traffic, used only to derive an assumed sale-day peak of **~300 concurrent users**.

**A finding the polished report does not surface, found by reading the raw k6 logs directly (not invented, not extrapolated — quoted from `perf/results/*-run.log`):** every one of the four captured k6 runs **breached its own `http_req_failed < 1%` threshold**, and each log ends with k6's own `"thresholds ... have been crossed"` error line.
| Run | `http_req_failed` (threshold: <1%) |
|---|---|
| Expected peak | **10.02%** (4,124 / 41,146) |
| 5× stress | **10.57%** (21,674 / 204,876) |
| Spike | **8.70%** (2,133 / 24,490) |
| Cart-stress | **29.26%** (12,924 / 44,167) — this run *also* breached its own `p(95)<1500ms` cart-latency threshold at the actual 2.35s |

In three of the four runs (peak, 5×, spike) this is driven substantially by the `GET /api/search/suggest` check ("suggest 2xx/3xx"), which failed **100% of attempts** — 0/4,095, 0/21,670, and 0/2,133 respectively. A 100%-fail-every-single-time pattern (not a degradation curve) suggests a functional break in the suggest path under the test target, not ordinary load-induced errors — but the root cause (exact status code / response body of a failing call) was **not captured in these logs** and is not established in this pass. The narrative report's "Error rate: effectively near-zero on every path" and its framing of the cart-stress run as an unqualified pass do not mention either the threshold breaches or the suggest failures. See §12.

### (b) Missing metrics — exact questions, and which bullet/claim each strengthens

1. *"What ECS task CPU/memory allocation (vCPU/GB) and task count run the api and worker services in production today?"* — strengthens the infrastructure bullet (§10 #12) and closes the "no ECS task-def in repo" gap in §6.
2. *"Has anyone looked at why `GET /api/search/suggest` failed 100% of requests in the peak, 5×, and spike k6 runs — is there a known root cause or fix?"* — needed to responsibly finish the k6 bullet (§10 #14) and the §9 finding above.
3. *"What was the actual ECS task CPU/memory utilization during the peak and 5× k6 runs?"* — the performance report itself says this was not captured ("best pulled from the server's own metrics dashboard") — strengthens the same k6 bullet with a real resource number instead of only latency.
4. *"How many rows are in `verified_identifiers` today, and how many refresh-token-family revocations (reuse detections) have actually fired in production?"* — turns the identity/session bullets (§10 #4-5) from "the mechanism exists" into "the mechanism has done real work N times."
5. *"In production, how often has the Razorpay **webhook** path actually won the `claimForFulfillment` race (created the order) versus the app's own verify call?"* — quantifies how load-bearing the exactly-once protocol (§10 #1) really is, versus being a guard that's never actually needed in practice.
6. *"What is the current SQS DLQ depth, and how many messages have ever landed there in production?"* — strengthens the async-reliability bullet (§10 #3) with a real number instead of a designed-for-but-unobserved property.
7. *"Do you have a real Redis cache-hit-ratio sample (e.g., `INFO stats` keyspace hits/misses) from production?"* — replaces the qualitative "read performance stayed flat" claim in the cache bullets (§10 #6-8) with a measured hit rate.
8. *"What is the actual mobile-app DAU/MAU or app-specific request volume, as opposed to the whole-store visitor/order figures used for peak sizing?"* — the 42,564-orders figure is store-wide by the report's own admission (§9a); a real app-only number would make the sizing assumption behind the entire performance bullet (§10 #14) far more credible.
9. *"Is the hardcoded IP in `rate-limit-bypass.ts` still needed, and is `BYPASS_ENABLED` actually `false` in whatever is currently deployed to production?"* — needed to close out the §8/§12 finding with a factual answer rather than "not verified in this pass."

---

## 10. Candidate resume bullets

Ordered by resume relevance. No invented numbers — every figure is quoted or arithmetically derived from a cited source.

1. **Engineered exactly-once order creation across a payment/webhook race condition:** modeled each checkout attempt as a single Postgres row claimed via a conditional `UPDATE` whose affected-row count decides the winner, backed by `UNIQUE` payment/order columns and a hand-written partial index that makes a COD double-tap a safe no-op.
Evidence: `src/modules/payments/payment-order.repository.ts:148-162,71-80`; `src/modules/payments/payments.service.ts:565-680`

2. **Took webhook processing off the request-response path:** verified Razorpay/Shopify/ClickPost signatures against the raw request bytes, logged every delivery before the auth gate for forensics, then enqueued to SQS and returned 200 in single-digit milliseconds — reserving a 5xx for the one case that actually needs a retry, the enqueue call itself failing.
Evidence: `src/modules/webhooks/webhooks.controller.ts:78-117,129-140,158-228`

3. **Designed the SQS consumer's settlement contract from first principles:** explicit delete-on-success / leave-for-redelivery-on-throw semantics on a standard (non-FIFO) queue, proved safe by making both downstream processors idempotent and order-tolerant rather than paying for ordering guarantees they didn't need.
Evidence: `src/infrastructure/queue/sqs.queue.ts:45-225`; `src/modules/webhooks/webhook-processor.ts:24-83`

4. **Built a race-free identity ledger for passwordless login across four providers:** a database unique constraint, not a read-then-write check, decides attach-vs-block for phone/email OTP, Google, and Apple sign-in, with one narrow, audited exception letting a genuine OTP reclaim a phone number Google's People API only guessed at.
Evidence: `src/modules/auth/identity-resolver.service.ts:31-94`; `src/modules/auth/strategies/`

5. **Hardened session security with rotation-on-use and blast-radius containment:** refresh tokens persist only as SHA-256 hashes, rotate on every use, and a replayed (already-consumed) token revokes every token in its family, not just itself.
Evidence: `src/modules/auth/session.service.ts:19-97`; `src/modules/auth/access-token.ts:36-59`

6. **Built a two-layer stampede guard for a shared Redis cache:** in-process request coalescing collapses every concurrent miss in one container into a single loader call, and a cross-container `SET NX` lock keeps only one container hitting Shopify when a hot key expires while the rest briefly wait on its result.
Evidence: `src/infrastructure/cache/redis.ts:36,73-160`

7. **Closed a null-caching outage at the architecture level instead of the call site:** after a transient upstream failure got cached as "no data" for a full TTL, rewrote the shared cache helper so a null/undefined loader result can never be written to Redis by *any* caller, by construction, rather than trusting each call site to remember the rule.
Evidence: `src/infrastructure/cache/redis.ts:67-71,141-143`; `src/gateways/kiwi/kiwi.gateway.ts:58-64`

8. **Replaced per-key deletes with a version-counter invalidation scheme, and swept the rest with non-blocking `SCAN`/`UNLINK`:** one write bumps a counter to orphan an entire cached family at once, while webhook-driven catalog purges use a cursor-based scan instead of a blocking `KEYS` sweep that would stall every cart/OTP/session read on the shared instance.
Evidence: `src/infrastructure/cache/redis.ts:170-186,243-260`

9. **Wrote the resilient HTTP client every outbound gateway shares:** per-upstream timeout and retry budgets with full-jitter exponential backoff, retrying only 5xx/network failures, and a deliberate zero-retry policy on the one call — Razorpay order creation — where a blind retry could mint a duplicate charge.
Evidence: `src/infrastructure/http/resilient-client.ts:16-77`; `src/shared/constants/index.ts:297-344`

10. **Cut roughly 2.4 seconds off a cold product-page load** (~1.4s + ~1s, per the code's own comment) by pulling two live third-party calls off the request entirely, and kept Shopify's cost-based GraphQL limit from becoming a bottleneck by batching bundle-product lookups into chunked `nodes(ids:)` calls instead of one round trip per item.
Evidence: `src/modules/product/product.service.ts:33-52`; `src/gateways/shopify/shopify.gateway.ts:621-651`

11. **Split every security control into fail-open or fail-closed by design, not by accident:** rate limiters and OTP gates degrade open so a Redis outage never locks out real customers, while webhook signature checks and the admin cache-purge endpoint refuse outright the moment their secret is unconfigured.
Evidence: `src/middleware/rate-limit.ts:43-64`; `src/modules/webhooks/webhooks.controller.ts:82-86`; `src/modules/admin/admin-cache.service.ts:32-55`

12. **Migrated the async queue and image storage off Azure onto AWS SQS and S3** behind the same producer/consumer and storage interfaces the rest of the app already coded against, shipping the swap with zero endpoint, request, or response-shape changes for the mobile app.
Evidence: `src/infrastructure/queue/sqs.queue.ts:1-45`; `src/gateways/s3/s3.gateway.ts:1-30`; `docs/2026-08-01.md`

13. **Chose hand-applied DDL over an ORM migration tool for a payments schema** so a partial unique index inexpressible in Prisma could guard against a double-submitted COD order — every schema change ships with its own pre-deploy gate query and post-deploy smoke test instead of relying on a migration runner's assumptions about the target database.
Evidence: `prisma.config.ts:9-21`; `prisma/sql/001-zero-payable-store-credit.sql:14-32,107-115`; `prisma/sql/002-app-address-meta.sql:36-89`

14. **Ran a six-profile k6 load-testing program directly against production infrastructure**, covering expected peak, 5× peak, and a sudden 3× spike, to quantify p95 latency per user journey, sustained throughput, and the cache stampede guard's behavior under a cold-key thundering herd instead of estimating capacity.
Evidence: `perf/k6/profiles/` (`load.js`, `stress.js`, `spike.js`, `cart-stress.js`); `docs/MyDesignation-Performance-Security-Report.md`

15. **Reverse-engineered the store's GST tax computation from live order data and reproduced it exactly**, including a one-paisa rounding artifact that independent per-line rounding produces on intra-state orders, so app-created orders file the same CGST/SGST/IGST split as every other Shopify sales channel.
Evidence: `src/core/gst.ts:1-37`

---

## 11. Interview material

### Hard problems (walk through the mechanism, not just the outcome)

**1. Exactly-once order creation.** Two independent writers — the app's own `/verify` call and Razorpay's webhook — can both try to create the same Shopify order for the same payment, in either order, or at the same instant. Walk through: why a conditional `UPDATE`'s row count is sufficient as the sole arbiter; why `razorpayPaymentId`/`shopifyOrderId` are also `@unique` as a second line of defense against a true tie; why the claim is released on a *pre-create* failure but never after Shopify actually returns an order (`payments.service.ts:640-680`); why COD needs a *different* mechanism (a partial unique index on `cart_id`) instead of the same claim column.

**2. Caching that can't lie.** The rule "never cache a failure, and negative caching needs an explicit sentinel" is stated in a code comment (`redis.ts:67-71`) — but is the *first half* actually enforced, or just documented? (It's enforced structurally in `loadWithLock`, `redis.ts:141-143`, for every caller, not left to convention.) Is the *second half* — an explicit sentinel for legitimate negative caching — actually used anywhere today? (No: a `grep` for "sentinel" across `src/` finds only the doc comment itself and one unrelated `content.defaults.ts` usage; there is no live call site exercising deliberate negative caching yet. Good interview honesty: the guarantee that matters — never silently cache a transient failure — is real and structural; the sentinel half is a stated convention with no current example.)

**3. One account per human.** Walk through what happens when a Google sign-in's email matches a phone-OTP account's email exactly (blocked, never merged) versus when a phone number was only ever seen via Google's People API and someone later proves it by real OTP (reclaimed, not blocked) — and why that asymmetry is deliberate (`identity-resolver.service.ts:77-88`: Google never *proved* ownership of a People-API phone, so a real OTP outranks it).

**4. Webhooks off the request path.** Trace a Razorpay `payment.captured` event end to end: raw-log write before the signature gate (so even a forged delivery leaves a forensic row) → HMAC-SHA256 over the *raw* body with a webhook secret that is deliberately different from the API key secret → 401 on mismatch → filter to only `payment.captured`/`order.paid` → enqueue → 200. Then: what happens if the enqueue itself throws (503, Razorpay retries, nothing was processed) versus if the *worker's* processing throws after a successful enqueue (message stays in-flight, redelivers after the visibility timeout, dead-letters after `maxReceiveCount`).

**5. Keeping the app inside someone else's rate limit.** Shopify's GraphQL API is cost-based, not request-count-based. Walk through why the bundle-hydration path batches up to 250 product ids per `nodes(ids:)` call instead of one call per item (`shopify.gateway.ts:621-651`, "195 ids ≈ cost 25"), and why the PDP was deliberately stripped of two *working* live upstream calls (Judge.me count, Kiwi chart) rather than just caching them harder.

### Follow-up questions with technically accurate answers

- **"Why store refresh tokens as a hash instead of just issuing a second, longer-lived stateless JWT?"** A stateless refresh JWT can't be revoked before it expires — there's no server-side row to delete. Storing a hash (`session.service.ts:99-100`, SHA-256) means logout, remote logout, and reuse-detection-triggered family revocation are all a single `UPDATE ... SET revokedAt = now()`, which a pure JWT design can't offer without a separate denylist that duplicates the same state anyway.
- **"What happens if Redis is completely down during a traffic spike?"** Every cache call degrades to calling the loader directly (`redis.ts:89-92,118-122`) — correctness is unaffected, but every request now pays Shopify's full latency with no stampede protection, since the `SET NX` lock itself needs Redis. The rate limiters also fail open in the same outage, so there's no throttling backstop either. It's a real, acknowledged risk (Performance report §6, item 3: "Cache dependency... Low-Medium").
- **"Why does the OTP verify-attempt cap fail open on a Redis error?"** Because the alternative — failing closed — would lock every user out of login during a Redis blip, which is a worse outage than a temporarily-uncapped brute-force window on a code that also expires in 10 minutes and is single-use. It's a deliberate defense-in-depth layering choice, not the only protection (`redis.ts:297-301`).
- **"Why is the access token 15 minutes, not 5 minutes or 24 hours?"** It's a config default (`config.ts:77`), not hardcoded — but 15 minutes bounds the blast radius of a leaked stateless token (it can't be revoked directly) to a short, known window, while staying long enough that the app isn't silently refreshing on every other request.
- **"What would break if `SQS_MAX_CONCURRENT_MESSAGES` were raised from 1 to 10?"** Nothing *should* break, because both processors are idempotent — but it hasn't been exercised at that concurrency in the k6 results reviewed here, and it's the kind of change that deserves its own load test before shipping, precisely because "should be fine" and "measured to be fine" are different claims.
- **"Walk me through what a customer sees if Razorpay is unreachable for 30 seconds during checkout."** `resilientFetch` gives it 8 seconds and zero retries (`constants/index.ts:343`) — the create-order call fails, the app surfaces an error, and the customer can retry with a fresh `internalOrderRef` (a new row, no partial state to reconcile) because nothing was claimed or charged yet.
- **"Why timing-safe compares in four different places (Razorpay signature, ClickPost token, admin token, email OTP code) instead of one shared helper?"** They're not fully unified — `webhooks.service.ts`, `admin-cache.service.ts`, `email-otp.service.ts`, and `razorpay.gateway.ts` each implement their own length-check-then-`timingSafeEqual` wrapper. A fair follow-up push: this is duplicated logic that could be one shared utility; worth asking why it wasn't factored out.
- **"How do you know the standard (non-FIFO) SQS queue is actually safe, rather than just probably safe?"** Because the two consumers were built idempotent *first*, as a property that's independently true regardless of delivery order or duplication (P2002-guarded claim; unique-constraint-guarded append), and the queue choice is a consequence of that property, not a bet made in place of it.

---

## 12. Red flags

Genuine, current, code-verified issues only — no ownership content.

**Live in the current source, not fixed:**
- `src/middleware/rate-limit-bypass.ts:20` — `BYPASS_ENABLED = true`, hardcoded, unconditional, matched against one real IPv4 address (`:26`, withheld here). No environment gate exists to turn it off short of editing this file and redeploying. If this exact code is what's running in production right now, that one IP is exempt from both rate limiters. The file's own comments explicitly warn against this exact state. **Not established in this pass** whether it's actually deployed live today — see §9(b) question 9.
- `src/modules/returns/returns.routes.ts:8-9` — self-documented: the returns-presigned-URL endpoint authorizes by `contact`/`order_number` request parameters, not the authenticated session. Requires a valid JWT, but not necessarily *your own* JWT for the return you're looking up.
- `src/modules/applogs/` — accepts writes with no client key, bounded only by the global rate limit + body-size cap.
- No `helmet` / security-header middleware anywhere in `src/` (confirmed by grep) — no HSTS/CSP/X-Frame-Options on any response.
- `prisma.ts:31-36` — RDS TLS connection uses `rejectUnauthorized: false`; encrypted in transit, but the certificate chain isn't validated.
- `POST /webhooks/gokwik` is routed (`webhooks.routes.ts:12`) but its handler throws `NotImplementedError` (`webhooks.controller.ts:119-121`) — a live 501 on a mounted route.
- `src/gateways/clevertap/clevertap.gateway.ts` — both methods are `throw new Error('TODO: implement …')`, and the class is never constructed in `container.ts`. Present in the tree, not part of the running system.

**Stale documentation / comments — describe the pre-migration (Azure) or pre-fix state, not current behavior:**
- `README.md` — claims the stack includes "BullMQ" (actual: AWS SQS), lists "Swym" as the wishlist third party (actual: MST/iWishlist, `container.ts:117,234`), and says auth/account/loyalty/checkout/webhooks are "scaffolded... return 501" — all five are fully implemented, as documented throughout this file.
- `docs/perf-security/SECURITY-ASSESSMENT.md` — carries a "CONDITIONAL GO" framing and, even accounting for its own 2026-08-10 "five findings fixed" update note, still lists SEC-4 (access token "7 days and non-revocable") as open — current code has a 15-minute default TTL with a fully revocable, rotating refresh-token family (`config.ts:77`, `session.service.ts`). The doc is stale beyond even its own last update.
- `docs/MyDesignation-Performance-Security-Report.md` — the newer, business-facing performance doc — is largely accurate on the numbers (§9 confirms them against raw logs) but its framing overstates reliability: it reports "Error rate: effectively near-zero on every path" and calls the cart-stress run a clean, stable pass, while the raw k6 logs for that same run show `http_req_failed` at 8.7-29.3% across all four runs and two breached pass/fail thresholds. See §9(a) for the exact numbers.
- `config.ts:256-258` — lists "Service Bus" and "Azure Blob" as still-relevant context for why some env vars stay optional; both no longer exist in the codebase.
- `webhooks.controller.ts:149,217,237,265` — four separate comments describe a 503 as meaning "Service Bus unreachable"; the code underneath enqueues to SQS.
- `s3.gateway.ts:12-13` — references "the Azure Blob gateway it replaced," accurate only as history.
- `docker-compose.dev.yml:9,55` — default SSH tunnel target is `azureuser@20.235.158.80`, a dead Azure host (overridable via `STAGING_SSH_USER`/`STAGING_SSH_HOST`, so likely harmless in practice, but a stale default). The same file's line 14 comment also says Redis is "only needed when `QUEUE=bullmq` in .env" — `bullmq` isn't a valid `QUEUE` value in the current schema (`config.ts:39`: only `'inline' | 'sqs'`).

**Worth him clarifying in his own words before an interview, not confidently callable as a mismatch from the code alone:**
- His project-story doc says he "pivoted to the native [Razorpay] SDK flow after Magic Checkout was dropped," but the current code's comments (`schema.prisma:229-240`, `payments.service.ts:551-560`) describe "Razorpay Magic Checkout" in the present tense as the live design, with no legacy/deprecated framing anywhere. This may simply mean "native" describes the mobile SDK integration surface *within* Magic Checkout rather than a replacement of it — the code alone doesn't resolve which reading is correct.
- His story states "~93 test files"; the current, directly counted figure is 97. Trivial, but worth a quick correction so a number he states out loud matches what a reviewer would find.

**Postman collection completeness (minor):** 86 requests across 18 folders match the 86 live endpoints exactly, but there is no dedicated `bundle` folder despite `bundle` being a live, 2-endpoint module — a documentation gap, not a functional one.

---

## 13. Tech stack evidenced in this code

**Runtime & language**
- Node.js **≥24** (`package.json:"engines"`, `.nvmrc: 24`, `Dockerfile:6,26` — `node:24-slim` for both build and runtime stages).
- TypeScript **5.8.3**, `strict: true`, target `ES2022`, `module`/`moduleResolution: NodeNext` (native ESM, `tsconfig.json`), package itself `"type": "module"`.

**Web framework**
- Express **5.1.0** — the v5 major, not the still-common v4 (new async-error-handling semantics, updated router).

**Data layer**
- PostgreSQL, accessed via **Prisma 7.8.0** as the typed query layer over **`@prisma/adapter-pg` 7.8.0** — a driver adapter, not Prisma's traditional Rust query-engine binary (`prisma.ts:11`, confirmed by the generated client having no engine binary). Underlying driver: **`pg` 8.22.0**, pooled (max 30, `config.ts:31`).
- Redis via **`ioredis` 5.6.0** — cache, distributed lock, rate-limit store, OTP cooldown/attempt counters.

**Messaging & storage (AWS)**
- **AWS SQS** via `@aws-sdk/client-sqs` **3.1101.0** — standard queue + DLQ, no broker to operate.
- **AWS S3** via `@aws-sdk/client-s3` **3.1101.0** + `@aws-sdk/s3-request-presigner` **3.1101.0** — presigned PUT/GET only, no image bytes through the API.

**Auth & crypto**
- **`jose` 6.0.10** — HS256 JWT sign/verify for the stateless access token.
- Node's built-in `node:crypto` — `timingSafeEqual` (4 independent call sites: Razorpay signature, ClickPost token, admin token, email-OTP code), `randomBytes`/`createHash` (refresh-token hashing), `randomInt` (OTP generation).

**Validation, HTTP plumbing, resilience**
- **Zod 3.24.2** — the entire environment schema plus nearly every request body/query.
- **`rate-limiter-flexible` 7.1.0** — `RateLimiterRedis`, two independently-tuned instances (global, auth).
- A hand-written resilient-fetch wrapper (no retry/circuit-breaker library) — per-upstream timeout + full-jitter backoff, built on the native `fetch`/`AbortSignal.timeout`.

**Shopify integration**
- **`graphql-request` 7.1.2** + **`graphql` 16.10.0** against Storefront **and** Admin GraphQL, API version **2026-01**; 51 hand-maintained `.graphql` documents, no codegen tool in the dependency list.

**Observability**
- **`pino` 9.6.0** + **`pino-http` 10.4.0** — structured JSON logs with field-level PII redaction, shipped to CloudWatch Logs from ECS task stdout in production.

**Testing**
- **Vitest 3.1.1** — 97 files, ~17.1k LOC, 276 `describe` blocks, 1,230 cases; no coverage tool/thresholds configured.
- **k6** (external CLI, not an npm dependency) — 6 load profiles + a bespoke TypeScript security-probe harness (`perf/security/`, run via `tsx`), not a packaged security-scanning tool.

**Build & tooling**
- **`tsx` 4.19.3** (dev watch mode + one-off scripts), **`typescript` 5.8.3`** (prod build via `tsc`), **`husky` 9.1.7`** (git hooks).

**Infrastructure**
- Docker (multi-stage, `docker/dockerfile:1` syntax) + Docker Compose (three topologies, §6), deployed onto **AWS**: RDS Postgres, ElastiCache Redis, SQS+DLQ, S3, ECS/Fargate+ALB (prod, per docs — no in-repo IaC), EC2 (staging all-in-one + bastion), IAM instance-role credentials, CloudWatch Logs. Account and region are consistent across every environment referenced in the docs (one AWS account, `ap-south-1`).

**Present in the repo/deps but demonstrably not the live design** (see §12 for citations): BullMQ, Swym, Azure Service Bus, Azure Blob Storage, AWS Secrets Manager, SES, and any IaC tool — none of these are what the current code actually runs on.
