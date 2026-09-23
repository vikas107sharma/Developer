# Technology stack actually evidenced in the code

Everything below was read out of the repositories (package manifests, imports, config, Dockerfiles).
Nothing is aspirational. Versions appear where the code states them.

---

## Ripplr — `Ripplr-fin` (cheque bounce management, collections finance, notifications, GST e-invoicing)

| Layer | What is actually used |
|---|---|
| Language / runtime | Python 3.9 (Docker base) |
| Web framework | Flask 2.3.2 |
| ORM / DB driver | SQLAlchemy 2.0.18, PyMySQL → MySQL on RDS (read/master split) |
| Messaging | confluent-kafka 2.3.0 (consumer), Kafka producers in-app |
| Scheduling | APScheduler 3.10.4 — 3 in-process schedulers on a shared base class |
| Storage | boto3 → S3 (presigned PUT/GET for cheque images, selfies, PDFs) |
| Documents | Pillow (PNG rendering), qrcode 7.4.2, ClearTax e-invoicing API (IRN + signed QR) |
| Messaging provider | WATI (WhatsApp Business API) |
| OCR | onnxruntime / RapidOCR with thread capping |
| Config | python-box + TOML, per-feature flags |
| Testing | pytest 7.4.0 (~584 test functions), Locust load tests |
| Observability | prometheus-flask-exporter `/metrics`, Sentry |
| Deploy | Docker (4 images: API, consumer, DMS consumer), ECS |

## Ripplr — `CDMS/collections` (salesman + delivery app API)

| Layer | What is actually used |
|---|---|
| Language / runtime | Node.js, JavaScript |
| Web framework | Express (17 route groups under `/api/v4`) |
| Datastores | MySQL (write + read pools), Redis (idempotency claims) |
| Realtime | socket.io |
| Testing | Jest |
| Observability | prom-client histograms, express-winston, Sentry |
| Deploy | Dual runtime — AWS Lambda + API Gateway via SAM (legacy), and ECS/PM2 via Bitbucket Pipelines (current) |

## Ripplr — `CDMS/order-adapter` (OBC adjustment ingestion)

| Layer | What is actually used |
|---|---|
| Language | Python |
| Compute | AWS Lambda (S3 ObjectCreated trigger, 600s timeout), ECS consumers |
| Messaging | Kafka — 2 topics, 4 message-key families, `acks=1` |
| Data | pandas (vectorised parsing/aggregation), SQLAlchemy → MySQL, PyMongo → MongoDB |
| Storage | S3 (source files, error reports) |
| Config | 22 per-brand JSON parser configs across 14 brand codes |
| Testing | pytest — 253 tests, 12 CSV fixtures |

## Ripplr — `CDMS/cdms/batch` (report service)

| Layer | What is actually used |
|---|---|
| Language | Node.js |
| Excel | `xlsx` (in-memory), `exceljs` streaming WorkbookWriter (disk), `archiver` (zip level 9) |
| DB | mysql2 — separate write and read pools, connectionLimit 30 each, result streaming with `highWaterMark` |
| Storage | S3 (signatureVersion v4, ap-south-1) |
| Pattern | DB-backed job queue with a global in-progress lock |

## Ripplr — `finService` (bank integrations, online transactions)

| Layer | What is actually used |
|---|---|
| Producer | Node.js, raw `http.createServer`, Node `crypto` (RSA-4096 + AES hybrid envelope), axios-retry, kafkajs |
| Consumer | Python, confluent_kafka, Flask health endpoint on a thread |
| Datastores | MySQL (main + finops pools), MongoDB (error/transaction logs) |
| External | ICICI statement pull + instant-alert push, HDFC, IDFC |
| Push | Firebase Cloud Messaging |
| Idempotency | 4-column unique key + `INSERT IGNORE`, 3 secondary indexes |

---

## Supertails — `promise-engine` (delivery promise / EDD)

| Layer | What is actually used |
|---|---|
| Language / runtime | Node.js ≥22 |
| Web framework | Express 4.18 |
| ORM / drivers | Sequelize 6.37, mysql2 / mysql — 6+ pools, connectionLimit 10 each |
| Cache | Redis 4.7 (per-data-type TTLs, `EDD_CACHE_TTL` 300s default) |
| Geospatial | h3-js (Uber H3 hex indexing), turf.js (polygon boundaries) |
| Messaging | Google Cloud Pub/Sub (inventory deltas) |
| Storage | Google Cloud Storage (raw ERP snapshot archival) |
| Jobs | BullMQ, Cloud Scheduler (external) |
| Docs | Swagger |
| Observability | New Relic, Winston → Loggly |
| Deploy | Google App Engine Standard — `nodejs22`, instance class F2 |
| Testing | none configured (`test/` empty, npm test is a stub) |

## Supertails — `supertails-backend` (post-order journey)

| Layer | What is actually used |
|---|---|
| Language / runtime | Node.js ≥22 |
| Datastores | MongoDB via Mongoose 8.18 (4 order collections), MySQL via Sequelize 6.37 |
| Messaging | @google-cloud/pubsub 4.10 (courier tracking, FreshDesk, attribution) |
| External | Shopify Storefront + Admin GraphQL, ERP (Frappe), ClickPost courier, pricing/pharmacy/returns services |
| Patterns | Positional `arrayFilters` array updates, webhook dedup keys, raw-response archival |
| Testing | home-grown runner, 50+ suites |

---

## MyDesignation — `mydesignation-backend` (D2C commerce BFF)

| Layer | What is actually used |
|---|---|
| Language / runtime | Node 24, TypeScript (strict, ESM) |
| Web framework | Express 5 |
| ORM / driver | Prisma 7 with `@prisma/adapter-pg` driver adapter + `pg` (no Rust engine); DDL hand-applied, Prisma Migrate deliberately unused |
| Database | PostgreSQL on RDS (TLS via `DATABASE_SSL`), 11 models, 5 enums, partial unique index |
| Cache | Redis (ioredis) on ElastiCache |
| Queue | AWS SQS standard + DLQ redrive (maxReceiveCount 5, visibility 30s, long-poll 20s) |
| Storage | AWS S3 presigned PUT/GET (SDK v3) |
| Validation | Zod (environment at boot + request bodies) |
| Auth | `jose` (HS256 access tokens, 15 min; refresh tokens SHA-256 hashed, 180 days) |
| Rate limiting | rate-limiter-flexible, Redis-backed |
| Upstream | graphql-request — 51 `.graphql` documents against Shopify Storefront/Admin `2026-01` |
| Logging | Pino / pino-http with PII redaction |
| Testing | Vitest — 97 files, ~1,233 cases, `fileParallelism: false` |
| Load / security testing | k6 — 6 profiles, 8 security probes |
| Deploy | Docker multi-stage, ECS/Fargate + ALB, CloudWatch Logs, IAM instance roles |
| External services | Razorpay, MSG91, Google OIDC + People API, Apple, ClickPost, Judge.me, Kiwi Sizing, Easy Bundle, Nector, Logisy, GoKwik |
| NOT used | SES (email is MSG91), Secrets Manager (env on host), any IaC, helmet |

---

## Consolidated — what belongs on the resume skills line

- **Languages:** Python, JavaScript, TypeScript, SQL, C++
- **Backend:** Node.js, Express, Flask, REST, GraphQL, Microservices, Event-Driven Architecture, Backend-for-Frontend, RBAC, System Design
- **Databases:** MySQL, PostgreSQL, MongoDB, Redis, Prisma, Sequelize, SQLAlchemy, Mongoose, schema design, indexing, query optimization
- **Messaging & Async:** Apache Kafka (AWS MSK), Google Cloud Pub/Sub, AWS SQS, webhooks, cron/scheduled workers, idempotency, exponential backoff
- **Cloud & DevOps:** AWS (Lambda, S3, ECS/Fargate, SQS, RDS, API Gateway, CloudWatch), GCP (App Engine, Pub/Sub, Cloud Storage), Docker, CI/CD, Linux
- **Testing & Observability:** pytest, Jest, Vitest, k6, Locust, Prometheus, Sentry, New Relic, structured logging

**Deliberately left off the skills line** (real, but weak signal or too niche): socket.io, BullMQ, Swagger,
python-box, archiver, ExcelJS, Pillow, qrcode, onnxruntime, turf.js, FCM, PM2, Bitbucket Pipelines, SAM.
**H3 geospatial indexing** is left off the skills line but kept inside a Promise Engine bullet, where it
carries more weight as evidence than as a keyword.
