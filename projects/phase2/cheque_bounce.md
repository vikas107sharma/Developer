CHEQUE BOUNCE MANAGEMENT — Ripplr CDMS

"This isn't a workflow system. It's a custody and accountability system for money that has already been lost — the goods are already delivered, the cheque already bounced, and now the only question is who is responsible for that money at every second until it's recovered."

================================================ Step 1 ================================================

The 30-second skeleton

"A cheque bounces after delivery. It moves through three roles — Cashier, Segregator, Sales Officer — and every handoff between them is a moment where somebody has to be accountable for money that's already gone missing. I modeled the whole thing on two orthogonal state dimensions plus an accountability lock, rather than one big state machine.

The first dimension is the cheque's own recovery state — where it is in the pipeline, eleven states from created through to fully recovered or short-closed. The second is the payment-verification state — cash, cheque, UPI and NEFT are each verified independently, so a single collection can be partially verified at once, and editability has to reflect that instead of being a yes/no flag. On top of both, there's an accountability-lock primitive: whenever one role hands work to another, a clock starts, and if nobody acts, it's the person who handed it off that gets blocked — not the person sitting on it.

Underneath all of that is 26 tables, 65 REST endpoints across nine blueprints, and every outstanding-balance mutation recomputing under a row lock against an append-only audit ledger, never patched by a delta."

================================================ Step 2 ================================================

The interviewer asks: "Walk me through what happens after a cheque bounces."

```
Cheque bounces (upstream, in the order system)
        │
        ▼
   Cashier receives it ──assign──► Segregator
        │  accountability lock opens (cashier=initiator, segregator=target)
        │  30 min unacknowledged → CASHIER gets blocked
        ▼
   Segregator ──assign──► Sales Officer
        │  same lock primitive, reused unmodified, roles shifted one step
        ▼
   Sales Officer visits store, photographs cheque (S3 presigned upload)
   ChequeOcrScheduler OCRs it in the background — never blocks submission
        │
        ▼
   Sales Officer records a collection: cash / cheque / UPI / NEFT
        │  editability gated by collection-state × payment-state matrix
        ▼
   Cashier verifies ──► cheque payment becomes a `cheque_suspense` row
        │  (born HERE, at verify — not at salesman submit)
        ▼
   PdcReconScheduler (every 10 min) realizes it once the bank
   automation service confirms it cleared
        │
        ▼
   fully_recovered  OR  short_closed (≤ ₹500 manual, or 30-day auto-close)
        │
        ▼
   store's blocked orders get unblocked via an external order-blocking service
```

"The lock primitive at the top is the piece I'm proudest of — I built it once, generically parameterized by initiator and target, and reused it unmodified at both handoff points instead of writing two bespoke blocking rules."

================================================ Step 3 ================================================

The ⭐ strongest card — the inverted blocker

They ask: "Why block the person who assigned the work, instead of the person sitting on it?"

"Because incentives run the wrong way if you do it the obvious way. If a Segregator hands a cheque to a Sales Officer and the Sales Officer just doesn't acknowledge it, blocking the Sales Officer accomplishes nothing — they had no urgency to accept it in the first place, so being blocked doesn't change their behavior. But the Segregator has every incentive to get that acknowledgment, because until it happens, the cheque is stuck showing as theirs.

So I inverted it: the assigner gets blocked, not the assignee, after 30 minutes of no acknowledgment. That turns an organizational accountability problem — 'who do I chase to get this moving' — into a database predicate the system enforces on its own, and it's the same primitive at both the cashier-to-segregator and segregator-to-officer handoff."

================================================ Step 4 ================================================

They ask: "How do you decide what a Sales Officer is allowed to edit on a collection?"

"Editability isn't a boolean, it's a matrix: collection-verification state crossed with per-payment state. A collection can have four payment types in it, each verified independently, so 'can this be edited' has to be asked per payment, not per collection.

And there's a trust rule underneath that matrix: if a payment was previously verified and someone edits it, its verification resets — you don't get to quietly change a confirmed number. But UPI and NEFT that were already confirmed by an automated bank match are explicitly exempted from that reset. Bank-confirmed money stays trusted even through a resubmit, because re-verifying something the bank already told you is true just adds friction with no safety benefit — the exemption list is three specific statuses, not a blanket 'don't touch verified payments' rule."

================================================ Step 5 ================================================

They ask: "How is the cheque-suspense lifecycle modeled?"

```
PendingRealization ──cron finds it cleared──► Realized
       │
       ├──bounce endpoint──► Bounced
       ├──void endpoint────► Void (flagged CRITICAL — legal but suspicious)
       └──Rejected
```

"I modeled this as a declarative transition table, not branching if/else logic — every (event, current-state) pair maps to either an allowed next state, or a classification of 'silent no-op' or 'critical no-op' if it's not allowed. That matters because a cheque can leave PendingRealization from three completely independent call sites: the reconciliation cron, the manual bounce endpoint, or the manual void endpoint. Without a shared table, you're one missed check away from two of those paths racing and double-subtracting the same cheque from someone's outstanding. With the table, every path asks the same question against the same current state, and an illegal transition degrades to a logged no-op instead of corrupting the ledger."

================================================ Step 6 ================================================

They ask: "Why recompute balances under a row lock instead of just incrementing or decrementing them?"

"Because the resubmit flow physically deletes and reinserts payment rows with brand-new IDs. A delta approach — add this, subtract that — has no stable identity to reverse against once the row it was tracking no longer exists. So every outstanding-amount mutation takes a row lock on the invoice, recomputes both the unverified amount and the PDC amount from a full subquery over current rows, and writes the result — plus a signed-delta row in an append-only audit ledger, so I can always answer 'why is this balance what it is' after the fact.

The honest tradeoff is cost — a full recompute on every single event instead of a cheap increment. I took that cost deliberately because the alternative drifts the moment identity changes underneath it, and this is money — self-healing correctness mattered more than shaving a query."

================================================ Step 7 ================================================

They ask: "Tell me about the reconciliation cron."

"It runs every ten minutes and claims pending cheques with FOR UPDATE SKIP LOCKED — that matters because there are multiple replicas of the same process running this scheduler in-process, and skip-locked means they never grab the same row twice; a row that's already claimed is just invisible to the other replica's SELECT, not something it waits on. Each claimed cheque joins to its latest bank-automation-log row and realizes it if the bank says it cleared. It's exactly-once by construction, not by luck — because the transition table's state filter means a cheque already moved out of PendingRealization by the bounce or void endpoint simply isn't selected by the cron's query anymore. Three independent triggers, one shared gate."

================================================ Step 8 ================================================

They ask: "What about the OCR worker — anything interesting operationally?"

"Two things. First, crash safety: the worker claims rows with the same FOR UPDATE SKIP LOCKED pattern, and if it dies mid-OCR, a janitor flips anything stuck in PROCESSING back to FAILED once it's been sitting past a timeout — measured off the database clock specifically, not the app server's clock, so clock skew between machines can't leave a row stuck forever.

Second — and this is the one I actually got called out for by an infra metric — running OCR across multiple containers all day was producing a genuine, documented 99% daytime CPU spike, because every container was grabbing every core for onnxruntime. I capped the thread count per process and restricted the worker to a night-only window. That's a pure ops win: same throughput, because nothing depends on OCR finishing during business hours, and the daytime CPU spike disappeared."

================================================ Step 9 ================================================

Correcting the record on order blocking

"I want to be precise about this one, because I've stated it wrong before: it's not three bounces in three months. It's two or more bounced cheques within ninety days that triggers a store's new orders getting blocked. And the blocking decision itself doesn't happen in this service at all — this service is the one that calls an external order-blocking service once a store's cheques are marked recovered, to trigger the unblock. I own the recovery and the unblock trigger; the actual block predicate lives outside my system, and I'd rather say that clearly than have it come out as a guess under a follow-up question."

Cut these from your interview story:

❌ "I created 20+ tables."
Nobody cares about the count, and it's imprecise — it's 26. It invites "why 26" and now you're defending schema size instead of demonstrating design judgment.

❌ "I built a state machine."
Too vague, and this system actually has two orthogonal ones plus a separate lock primitive layered on top — say that instead, it's a much stronger answer.

❌ "I implemented JWT, OTP and RBAC for three roles."
That's a capability inventory, not a story. Nobody follows up on this productively.

❌ "There's order blocking after 3 bounces in 3 months."
This is the exact number I got wrong before. The real rule is 2+ bounces in 90 days, and the block decision lives in an external service I only call into — correct this proactively rather than have it surface as a gotcha.

Numbers you must know:

- 26 tables in the CBM/scan/suspense domain (cheque_/cbm_ prefixed, plus scanned_cheques and the outstanding-suspense audit log).
- 65 REST routes across 9 blueprints, mounted under one prefix.
- 11-state cheque lifecycle; 4-state recovery status; 7-value Sales-Officer edit-mode enum.
- Bounce charge ₹500; short-close threshold ≤ ₹500 remaining; accountability-lock timeout 30 minutes.
- Reconciliation cron: 10-minute interval, batch size 200.
- OCR scheduler: 2-second poll, batch size 5, stuck-row timeout 300 seconds, night window 23:00–05:00 IST.
- Auto-close: 30 days unverified-but-cashier-confirmed, amount ≤ ₹500.
- Order blocking trigger: 2 or more bounced cheques within a rolling 90-day window (not 3-in-3-months) — block decision itself lives in an external service.
- **4,527 cheques handled since 2025-12-19**; 380–600 bounces/month in steady state (Feb–Sep 2026), ₹0.95–1.5 Cr/month, ₹10.69 Cr lifetime bounce value.
- **100% principal recovery — 3,844 of 3,844 resolved cheques recovered the full principal. Zero principal written off.** 98.87% including the bounce charge (₹9.38 Cr of ₹9.49 Cr).

⚠️ **NEVER quote "1,482 fully_recovered vs 2,362 short_closed."** By count that reads as a 39% success
rate and it is simply wrong. Here is why, and you should be able to say this from memory because it is
the best thing in this card:

> "A short close isn't a write-off. `cbm_migration.py:177` sets initial outstanding to principal plus a
> ₹500 bounce charge, and `sales_officer.py:337` rejects a short close outright if the shortfall exceeds
> that ₹500. `AutoCloseScheduler` at `scheduler.py:155` only auto-closes below ₹500 after 30 days. So the
> maximum a short close can ever leave behind is the bounce fee — never a rupee of principal. I checked
> it in the data: max residual across every short-closed cheque is exactly ₹500, mean ₹453. The
> ₹10.7 L that looks written off is entirely uncollected bounce charge — 44% of charges were collected
> and the rest waived, 2,257 of them logged as 'Customer did not agree'."

That answer turns what sounds like a 39% failure into a design property you can prove three ways: the
code path, the threshold, and the data. If an interviewer has already seen the 39% number, this is how
you take it apart.
- [NEED FROM ME]: "Roughly how many cheque scans does the OCR worker process per night, and what's the real accuracy rate on the is-a-cheque signal check?"
- [NEED FROM ME]: "Do we have before/after p99 latency on the cashier verification-list endpoint from the batched budget-lookup change?"
- [NEED FROM ME]: "What's the current row count and growth rate on the suspense table and the audit ledger — has the 10-minute cron ever fallen behind?"
