# Interview Question Bank

A senior-level technical interview mapped onto your resume — every bullet, every number, every
technology on the skills line. Built 2026-09-26.

## What this is built from

| Input | What it contributed |
|---|---|
| **`../../resume.tex`** (current) | The claims being interrogated — 13 bullets, 22 numbers, ~45 technologies |
| **Ten code analyses** in `../findings/code-analysis/` | The real defects, trade-offs and gaps an interviewer who read your code would find — 🔍 items |
| **Five internet research passes** | 346 real reported questions from Razorpay, PhonePe, Flipkart, Swiggy, Zepto, Meesho, Amazon, Uber, Zomato, CRED, Groww, Atlassian, Coinbase, LinkedIn, New Relic and the major prep sources — 🔗 items, URL on every one |
| **Constructed** | Where a mechanism on your resume has no published question (GST paise search, People-API phone reclaim, staging/prod subscription split), a question built from the documented mechanism — ✏️ items, labelled so you know they're unsourced |

Every project is treated as yours. The questions interrogate the engineering, not the authorship.

## Files

| File | Section | Count |
|---|---|---|
| `5-project-interrogations.md` | **Start here.** Per-bullet drill-downs in resume order, opening question per bullet, known traps, and the **metrics ledger** — every number, its sourcing, the challenge, your defensible answer | 13 openers + 260 drill-downs |
| `1-system-design-lld.md` | Payments, order lifecycle, inventory/EDD, BFF, IAM, ledgers, ingestion, job queues, infra, LLD rounds, "what breaks first at 10x" | 138 |
| `2-database.md` | InnoDB locking, the 330s query, schema design, Postgres specifics, MongoDB, pooling, money math, ORMs | 107 |
| `3-runtime.md` | Event loop, CPU-bound work, streams, memory, Express/TS/Zod, single-flight, Python/GIL/APScheduler/Lambda, retries, crypto | 91 |
| `4-distributed-caching-messaging.md` | Kafka, Pub/Sub, SQS, webhooks, idempotency/outbox, Redis caching, locks, rate limiting, auth across services, cloud/observability | 182 |

Each section numbers its questions from 1. Section 5 numbers restart per bullet.

## Legend

- ⭐ highest-yield — the question an interviewer who read that bullet will open with
- ⚠️ trap — the honest answer exposes a known gap. **These are the ones to prepare hardest.** Volunteering a gap you've diagnosed reads far better than being caught by it.
- 📊 metric challenge — "how did you measure that?"
- 🔗 real source · 🔍 your code analysis · ✏️ constructed
- **Card:** the `../phase2/` card with the worked answer

## How to use it

1. Read the **metrics ledger** at the top of Section 5 first. Every number on the resume, in one table, with the one you cannot currently defend marked.
2. For each bullet, rehearse the ⭐ opener out loud, then the ⚠️ traps. The drill-down questions are what follows if the opener goes well.
3. Sections 1–4 are for the *domain* rounds — the "tell me about caching" or "design a payment system" interviews that don't start from your resume but land on it within five minutes.
4. Section 1-K ("what breaks first at 10x") has a named component per system. Never answer that question with "add servers."

## What interviewers push on — eight patterns from 346 questions

1. **Senior rounds open with a concrete failure scenario, not "design X."** "The bank charged the customer, then your server crashed before writing the row." The scenario is the filter.
2. **"Exactly-once" is a trap word.** The follow-up is always "what does it buy you and where does it stop." Delivery guarantees die at the DB / third-party boundary; your consumer has to be idempotent regardless.
3. **Every senior DB question is a race condition in a domain costume.** Name the anomaly (lost update, write skew, double-booking) before the mechanism.
4. **"Is this mechanism enforced, or merely advisory?"** `highWaterMark` isn't a memory cap. `SET` + `EXPIRE` isn't a lock. The GIL doesn't stop races. A docstring saying "atomic" isn't atomicity. You have examples of each in your own code.
5. **"What if Redis goes down" is never one question.** The answer branches by subsystem — auth fails closed, cache and rate limits fail open — and they push on *why the line is drawn there*.
6. **Distributed-lock and idempotency questions escalate.** Acquire → crash before release → TTL expires mid-work → duplicated side effect → fencing token. "Use SETNX" once is an incomplete answer.
7. **A clean aggregate number is treated as suspicious.** Cache hit ratio, p95, error rate — they want per-family, per-percentile, and the outlier you'd fix. A flat number with no outlier reads as unexamined.
8. **"What breaks first at 10x" is the senior/staff discriminator.** Name a component. Named ones for each of your systems are in Section 1-K.

## The fifteen you will definitely get

Cross-section, highest probability given this specific resume:

1. "How did you measure 9s → 1.1s?" — ⚠️ the most exposed number; see the ledger
2. "The bank charged the customer, then your server crashed before writing the row." — Section 1 #1
3. "Your Kafka consumer commits on exception. What happens to a failed message?" — Section 4 #1
4. "Zero written off? Then what were the short-closes?" — Section 5, Cheque bullet
5. "Same warehouse in two clusters — what stops double-promising?" — Section 5, Promise Engine
6. "Your writer zeroed unrelated SKUs and the query succeeded. Why?" — Section 5, Inventory
7. "System-wide hit ratio is 44.81% — why does the resume say 28K calls avoided and not a percentage?" — Section 5, Caching
8. "Why `SET NX EX` and not `SET` then `EXPIRE`?" — Section 4 #121
9. "Why recompute under lock instead of applying deltas?" — Section 2 #2
10. "Two writers race to create the order — why is rows-affected sufficient?" — Section 2 #55
11. "Why does your Kafka event carry only a salesman id and a date?" — Section 5, Notifications
12. "Why is delivery-note matching by `_id` and not `shipmentId`?" — Section 5, Post-order
13. "Why not put permissions in the JWT?" — Section 5, IAM
14. "Three idempotency layers — which one does the database enforce?" — Section 5, OBC
15. "What breaks first at 10x?" — Section 1-K, one named component per system

## Sourcing caveats — read before quoting a source

- All five research passes hit a session-wide cap of 200 web searches. Each completed its required minimum (29–46 searches) before the cap; a handful of planned follow-ups (Atlassian-specific, Amazon SDE2-specific, H3 geospatial, onnxruntime) did not run. Gaps are stated in each agent's notes, not filled with guesses.
- LeetCode Discuss, Medium, Glassdoor and dev.to blocked direct page fetches (HTTP 403) for several items. Those questions are as the search engine extracted them from the page, not independently re-read. They are real URLs; the wording may be paraphrase.
- `github.com/kunj-21/backend-interview-daily` and `app.sourcethread.com` are curated interview-style scenario write-ups by individuals, not confirmed transcripts from a named employer. Used because the questions are genuinely production-shaped; treat "asked at company X" as unverified for those.
- Five claim areas had **no** published interview question despite targeted searches, because they're too specific to your systems: the GST paise bounded search, the 11-state cheque lifecycle, the 3-audience IAM schema, MongoDB `arrayFilters` as an interview topic, and the People-API phone-reclaim rule. Questions on those are ✏️ constructed from the mechanism and the closest real analogue.
- One source stated App Engine F2 = 768 MB, conflicting with the 256 MB figure in your Phase 1 notes. Neither was verified; only the failure mode (paged cron exceeding a small instance's soft limit) is used, which both agree on.
- Reddit r/developersIndia and Hacker News surfaced no individually verifiable question threads. That's a real coverage gap.

## Things this bank deliberately does not contain

- Definition questions ("what is an index", "what is REST", "what is the event loop"). Every source agrees these are not asked at senior level; the ones that resemble them here are the *follow-up* form ("what changed in Express 5", "when is `nextTick` starvation possible").
- Authorship or ownership questions. Every project is yours.
- Answers. The Phase 2 cards carry those; each question points to its card.
