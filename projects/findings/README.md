# Findings — what went into the resume, what did not, and why

Generated 2026-09-22 from a read-only analysis of every repository path listed in `../../script`.

## What is in this folder

| File | What it holds |
|---|---|
| `README.md` | This file — the included/excluded decision table and the open questions |
| `TECH-STACK.md` | The technology stack actually evidenced in each codebase, plus the consolidated skills line |
| `ALL-CANDIDATE-BULLETS.md` | Every candidate bullet the analysis produced (~130), grouped by area |
| `NUMBERS.md` | Every number used, its source, and the ones I still need from you |
| `code-analysis/` | The 10 full technical analyses, each with file:line evidence, hard problems, interview Q&A and technical red flags |

Deliverables produced from this live elsewhere: the resume at `../../resume.tex` / `resume.pdf`, and the
interview cards in `../phase2/`.

---

## The 13 bullets I put on the resume

| # | Project | Bullet | Drawn from |
|---|---|---|---|
| 1 | Ripplr | Centralized IAM & RBAC | `iam-prd.md` |
| 2 | Ripplr | Financial Ingestion Pipeline (OBC adjustments) | `obc-adjustment.md` |
| 3 | Ripplr | Cheque Bounce Management | `ripplr-fin-cbm.md` |
| 4 | Ripplr | Field Collections Workflow | `collections-salesman.md` |
| 5 | Ripplr | Notifications & GST e-Invoicing | `whatsapp-notifications.md` |
| 6 | Ripplr | Reporting & Bank Reconciliation | `reports-and-finservice.md` |
| 7 | Supertails | Delivery Promise Engine | `promise-engine-edd.md` |
| 8 | Supertails | Realtime Inventory Sync | `promise-engine-inventory.md` |
| 9 | Supertails | Post-Order State Modeling | `supertails-post-order.md` |
| 10 | Supertails | Customer-Facing Fan-In API | `supertails-post-order.md` |
| 11 | MyDesignation | BFF Architecture | `mydesignation.md` |
| 12 | MyDesignation | Exactly-Once Order Creation | `mydesignation.md` |
| 13 | MyDesignation | Caching & Identity | `mydesignation.md` |

Every listed area from your brief is represented. Nothing you pointed me at was dropped.

---

## The 13 interview cards in `../phase2/`

Written in the spoken-card style of your Phase 1 notes: a reframing line, numbered `Step` cards
with first-person answers you say out loud, ASCII diagrams, a marked strongest card, a bug to
volunteer, a "cut these" list, and a numbers list. One card per resume bullet.

| Card | Resume bullet it supports | Strongest card inside |
|---|---|---|
| `iam_rbac.md` | Centralized IAM & RBAC | Why permissions are NOT in the token: header-buffer size plus revocation latency |
| `obc_ingestion.md` | Financial Ingestion Pipeline | The one-rupee phantom at exact half-rupee fractions |
| `cheque_bounce.md` | Cheque Bounce Management | The inverted blocker: block the assigner, not the assignee |
| `field_collections.md` | Field Collections Workflow | The ~330s correlated-subquery fix |
| `gst_einvoicing.md` | Notifications & GST e-Invoicing | Paise-exact GST via a bounded decimal search |
| `reports_and_banking.md` | Reporting & Bank Reconciliation | The ICICI hybrid RSA+AES envelope and the dedup key |
| `promise_engine.md` | Delivery Promise Engine | Why the 8-stage buffer pipeline is order-dependent |
| `inventory_realtime.md` | Realtime Inventory Sync | The delta-clobber bug that silently zeroed unrelated stock |
| `post_order_write.md` | Post-Order State Modeling | The placeholder shipment for SKUs that bill but claim no parcel |
| `post_order_read.md` | Customer-Facing Fan-In API | N+1 avoidance plus the two double-counting traps |
| `bff_architecture.md` | BFF Architecture | One image, two processes, a one-way pipe |
| `exactly_once_orders.md` | Exactly-Once Order Creation | The partial unique index that justifies Postgres over MySQL |
| `caching_and_identity.md` | Caching & Identity | One identifier, one account, enforced by the database |

Each card carries its own `[NEED FROM ME]` numbers. `NUMBERS.md` in this folder consolidates them.

---

## What I cut from the OLD resume, and why

| Old bullet / claim | Decision | Reason |
|---|---|---|
| "reduce API p99 latency from 3s to 800ms" | **Removed** | No source anywhere in any repository. Replaced with the ~330s invoice-list query fix, which your own commit message documents. |
| "Owned the full MySQL schema (20+ tables)" | **Sharpened** | The cheque-bounce feature set declares 26 tables specifically. 26 is both truer and stronger than "20+". |
| "13+ report types" | **Corrected to 19** | The report service has 21 type branches, 2 commented out, so 19 are active. |
| "cron scheduling" on the report service | **Removed** | There is no cron in that code. It is a one-shot script driven by an external scheduler, with a DB-level queue lock. Saying "cron" invites a question that has no good answer. |
| "sha-512 password hashing" | **Removed** | True but trivial, and it reads as a capability inventory rather than engineering. |
| "JWT + OTP + RBAC enforcing per-persona permissions" | **Reframed** | Replaced with the editability matrix and the declarative state machine, which are the actual engineering. |
| "MyDesignation: stateless auth + two-layer cache" (2 bullets) | **Expanded to 3** | The project was badly undersold. Exactly-once order creation is the strongest correctness story in your entire portfolio and was missing. |
| "Wellbeing — Health Data Platform", "Sammmm" | **Never included** | Those came from the screenshot you shared as a format reference. They are not your projects. |
| Summary paragraph | **Replaced** | A one-line tagline under the name. Summaries rarely earn their vertical space; that space went to a sixth Ripplr bullet. |
| "1,500+ problems solved on LeetCode/Codeforces" in skills | **Removed from skills** | The Achievements section already carries the ratings, which are stronger evidence than a problem count. |

---

## Strong material I found but did NOT put on the resume

All of these are in `ALL-CANDIDATE-BULLETS.md` with evidence if you want to swap any in.

**Ripplr**
- The ~330-second query fix as its own bullet (currently folded into Field Collections)
- Per-UTR NEFT budget derived with a maximum rather than a sum across two duplicate bank feeds, with sorted-order locking to avoid deadlock — built and tested but currently flagged off, so it cannot claim production impact
- The cheque OCR pipeline: skip-locked claiming, a stuck-row janitor, orientation retry, and a night-only window that removed a daytime CPU spike
- The rupee-rounding defect at exact half-rupee fractions, and the bounded settlement rule that replaced an unbounded bypass after it drove a production invoice negative
- The Britannia double-adjustment guard
- Section 269ST statutory cash-limit enforcement
- Moving GPS persistence out of a ~30-second transaction
- A cross-service financial ledger migration with deliberate index design
- The internal Streamlit ops tool and the Excel/CSV migration API

**Supertails**
- The placeholder-shipment mechanism (idempotent via a sorted quantity fingerprint, retired by emptying rather than deleting)
- COD allocation with a fixed whole-order denominator so three displayed figures always sum exactly
- The duplicate-shipment-identifier collision fix
- Returns handling that avoids double-counting when the platform splits a line item across fulfilments
- The 29-test cross-consumer regression suite proving one invariant across five consumers
- The 174-endpoint Control Tower configuration API
- An atomic Redis token-bucket rate limiter driven by a Lua script

**MyDesignation**
- The resilient HTTP client with full-jitter backoff and per-upstream budgets, and zero retries on payment calls to avoid double-charging
- Chunked Shopify batching to stay inside a cost-based rate limit
- The ~2.4s cut from cold product-page load
- The never-cache-a-failure rule adopted after a silent hour-long outage
- The Azure to AWS migration itself
- The k6 performance and security programme

---

## Things you should decide or fix

1. **Job title and start date.** The resume says "SDE-I, Fullstack Developer, Dec 2024 – Present", taken from your brief. An earlier screenshot said Nov 2024 and "Software Development Engineer, Backend". Confirm which is right.
2. ~~**Two numbers I could not source.**~~ **Resolved 2026-09-22.** "17K+ messages/day" is confirmed and now carries its derivation on the resume — one verification message per invoice, ~17K invoices/day. "15K+ rows per upload" was **removed**, not corrected: it appears in no artifact and the largest real brand file on disk is 2,871 rows. It is replaced by the confirmed ~35K adjustment entries/day. See `NUMBERS.md` for the full confirmed table.

   Four further production figures were added at the same time: **~50K requests/day** (Promise Engine), **3–7K events/day** (inventory sync), and **14.6K → 48.7K orders/month** (MyDesignation). The last one is Shopify-wide and **includes web orders**, so the resume states it as volume the backend serves, not growth the app produced — and it is 3.3x, a 234% increase, not 250%. The remaining gap worth closing is the app-only order share.
3. **Login volume for the IAM bullet.** You pointed me at production CloudWatch. I have not run anything. Say the word and I will run one read-only Logs Insights query counting daily and peak-hour requests on the salesman login route, or just tell me the number. Note the design document specifies v5 of that route while your brief says v4.
4. **MyDesignation load-test results.** The polished report quotes clean p95 figures, but all four raw runs breached their own failure threshold and the search-suggest endpoint failed 100% of checks in three of them. Worth understanding before you quote those numbers in an interview.
5. **A live security item, unrelated to the resume.** A rate-limit bypass flag is hardcoded on for one IP address, a returns route authorizes by request parameters rather than session identity, database TLS does not validate the certificate chain, and there are no security headers. Separately, several plaintext key files sit untracked on disk in the finService checkout. I have not touched any of it.
