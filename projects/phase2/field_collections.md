FIELD COLLECTIONS WORKFLOW — Salesman Collection & Cheque Recovery, Ripplr CDMS

"Everyone assumes rejection is a checkbox that flips back to 'pending.' On this system, who rejects it changes what you're even allowed to edit."

================================================ Step 1 ================================================

Your 90-second answer

"I worked on the field collection system for an FMCG distributor. A salesman visits stores, collects cash, cheque, UPI or NEFT against outstanding invoices, and submits the collection for verification by a segregator and a cashier. Either one can reject it, and that's where the real engineering was.

Rejection isn't a single state. If the segregator rejects, the whole submission reopens — the salesman can add, remove or change anything. If the cashier rejects, only the rejected payment is editable, and even then a reason code decides exactly what field can change: amount only, cheque details only, either, or nothing at all. All of that is enforced server-side, not just hidden in the UI.

Underneath that sits the resubmission problem. One payment can be spread across many invoices, so I don't update payment rows on resubmit — I tear down the set and rebuild it, while carrying forward the cashier's prior verification and versioning every row through a parent link so history survives.

I also closed a real duplicate-payment race with an atomic Redis claim, and I found and fixed a query on the invoice-list endpoint that was taking roughly 330 seconds."

================================================ Step 2 ================================================

The ⭐ strongest card — rejection is not one state

The interviewer asks: "Walk me through what happens after a rejection."

"There are two completely different blast radiuses. A segregator rejection means the submission never got past the first gate, so it reopens fully — new payments, removed payments, changed amounts, all of it.

A cashier rejection is narrower by design, because the cashier may have already verified other payments in the same submission. Only the rejected payment unlocks, and the reason code on it decides the shape of the edit: EDITAMOUNT lets you change the amount but freezes cheque number and bank details, EDITDATA is the mirror image, EDITAMOUNTORDATA allows either, and SETTLE blocks editing entirely.

And I want to be specific about one thing: this isn't a frontend convenience. The backend re-checks the payment's state and the reason code before it accepts the edit. The app can show whatever it wants — the server is the actual gate."

================================================ Step 3 ================================================

Why resubmission deletes and rebuilds instead of updating

The interviewer asks: "Why not just UPDATE the payment row that changed?"

"Because a payment row isn't an independent thing during resubmission — it's one slice of an allocation. A salesman might hand over ₹40,000 cash, two cheques and a UPI transfer against eight invoices in one go. If he changes one amount on resubmit, the allocation across all eight invoices can shift — money can move to a different invoice or split differently than before.

So instead of trying to compute a diff, I mark the old payment rows as deleted and insert a fresh set for the new allocation. The new rows carry a parent_id back to the old ones, so it's versioned, not lost.

The part that took real care was that a resubmit can't blow away work the cashier already did. Before I insert the new row, I copy forward the bank_statement_id, the UPI reference, the payment_verification_status, and the cashier's verified_id and verified_at from the row being replaced — so a payment the cashier already confirmed doesn't silently reset to unverified."

================================================ Step 4 ================================================

The amortization card

"How does one collection get split across multiple invoices?"

"The salesman doesn't pay invoice by invoice. He hands over one bundle of money, and the amortizer walks the assigned invoices in a fixed priority — cash first, then UPI, then cheque, then NEFT — and consumes the available money against each one in turn.

For every invoice it decides one of three outcomes: the amount settles it fully, it partially covers it and creates a bill-back for the remainder, or the allocated amount actually exceeds what's outstanding and the line gets rejected outright.

The constraint that made this interesting: all the money has to be consumed by the end of the walk. If there's anything left over once every invoice has been walked, the whole submission is invalid — you can't collect money and not account for where it went."

================================================ Step 5 ================================================

The duplicate-submit card

"What happens if the salesman's app retries a submission because of a bad network?"

"I hash the payment payload — invoice IDs plus payment type, ID and amount — and claim it in Redis with a single atomic SET NX EX call, 60-second expiry. If an identical claim already exists, the retry gets rejected as already-in-progress instead of creating a second payment set.

That atomic call replaced an earlier version that did a plain SET followed by a separate EXPIRE with no NX guard — which had a real window where two concurrent identical requests could both pass the check. That gap was tied to an actual production incident before I closed it.

If Redis itself is down, I fail open and let the request through rather than making a financial collection flow hard-depend on Redis being healthy."

"Isn't failing open dangerous?"

"There's a real trade-off, and I made it deliberately. Redis being unavailable raises duplicate risk, but blocking every salesman in the field from submitting collections because a cache is down is worse for this business than a rare duplicate that the database-side validations and transaction boundaries can still catch downstream."

================================================ Step 6 ================================================

The UPI auto-verification card

"Did you automate any of the verification?"

"UPI payments can skip manual cashier verification if they match the bank feed. Before my change, that match was reference-number only — any UTR that matched auto-verified the payment with no check on the amount at all. That's a real financial-integrity gap: a reference match with a wrong amount would sail through.

I added a tolerance check — the salesman-entered amount has to match the bank statement within 10 paise — and if it doesn't match, it fails loud instead of silently accepting it. If the payment is later removed from a submission, I release the bank-statement row so it can be matched again by a future payment."

================================================ Step 7 ================================================

⭐ THE strongest card — the ~330-second query

The interviewer asks: "What's the most impactful performance fix you've shipped?"

"The invoice-list endpoint for segregators was taking roughly 330 seconds on a bad day. I traced it to a correlated SUM subquery against an unindexed text column — it was re-executing once per row in the result set, so it was effectively a full table scan for every single invoice on the page.

I replaced it with one GROUP BY query that aggregates by invoice number for the current page, run once, and merged the results back onto the rows in application code. Same output, one query instead of one-per-row.

I did the same pattern rewrite in a second place in the same file — a per-row ORDER BY … LIMIT 1 correlated subquery for the assigned/unassigned filter — replaced with a single LEFT JOIN against a GROUP BY MAX(id) derived table."

================================================ Step 8 ================================================

The GPS lock-scope card

"Any other reliability work on that endpoint?"

"Yes — GPS capture. The original code validated and wrote the salesman's coordinates inside the same database transaction as the payment writes. That meant the transaction held a row lock on the invoice for the entire request — I measured that at around 30 seconds in the worst case, because location validation was the slow part.

I moved GPS validation and persistence onto its own short-lived connection outside the payment transaction. The lock now releases in milliseconds instead of holding for the life of the request."

================================================ Step 9 ================================================

The statutory compliance card

"Any regulatory logic in here?"

"Section 269ST of the Income Tax Act caps cash transactions at ₹2 lakh per payer per day. The existing check before my rewrite was, honestly, inert — a comment in the code says the subtraction it was doing cancelled out and it only ever bounded the current request, not the day.

I rewrote it to sum actual cash collected at that store on that date, excluding the invoices in the current submission so a resubmit doesn't double-count itself, and added a second cumulative check on the preview endpoint so the salesman sees the block before he even submits."

================================================ Step 10 ================================================

⭐ The bug you SHOULD volunteer

"The cashier-rejection fix didn't work the first time. My first attempt at 'keep a cashier-rejected payment editable' used the payment's edit-state to decide whether to unlock it — but the same state values are shared between 'cashier sent this back for correction' and 'salesman is mid-edit himself.' My fix ended up also unlocking payments the salesman had already edited and submitted, which it should not have touched.

A regression test caught it two days later, tied to a real production invoice. The actual fix was narrower: check the action field specifically for CASHIERREJECT, not just the state. I'd tell an interviewer this straight — it wasn't a clean one-shot fix, and I only trust the state field for permissions when it's paired with the action that put it there."

================================================ Step 11 ================================================

"Here's the shape of the whole problem, if they want the map."

Rejection isn't one state
        ↓
Segregator vs cashier scope differs
        ↓
Cashier scope needs reason-code gating
        ↓
Resubmit can't update — allocation can reshuffle
        ↓
Delete + versioned insert, verification carried forward
        ↓
Amortization has to fully consume the money
        ↓
Idempotency needed against double-submit
        ↓
UPI auto-verify needed an amount check, not just a reference match

Cut these from your interview story:

❌ "I built the amortization engine."
The core priority-walk and per-invoice settle/bill-back logic predate my work on this service — I extended it (cash-limit clamping, diagnostics) but didn't originate it. Say "I work in and extend" for that layer, not "I built."

❌ "I made collections instant."
The 330s fix was one endpoint, not the whole flow, and I don't have a measured after-number yet — see below.

❌ "Redis makes duplicate payments impossible."
It fails open. It reduces the window, it doesn't guarantee it — the DB-side validation is the actual backstop.

Numbers you must know

- Query fix: correlated SUM subquery on an unindexed TEXT column, ~330s before, replaced by one grouped query per page. [NEED FROM ME: do you have a measured after-latency, e.g. from Prometheus/APM, for list-v2 post-fix?]
- Redis lock: went from 2 non-atomic calls (SET then EXPIRE, no NX) to 1 atomic SET NX EX 60.
- UPI tolerance: 10 paise (Math.abs(a-b) <= 0.1).
- GPS lock hold: ~30s in-transaction (code comment estimate) down to milliseconds on its own connection.
- Cashier-reject fix: two commits, two days apart, tied to one named production invoice.
**Scale — confirmed 2026-09-22 from production. These are your strongest numbers; lead with them.**

- **₹1,260 Cr collected over 12 months** (Sep 2025 – Aug 2026), **~₹105 Cr/month** (range ₹91.7–113.7 Cr), **~₹3.93 Cr per working day**.
- **7.11 M invoices** over the same window — ~592K/month, **~21,900 per working day**.
- **274,093 payment transactions in Aug-26** alone, ~10,500 per working day.
- Instrument mix by value (Aug-26): Cheque 27.9%, Cash 27.1%, NEFT 23.0%, UPI 18.7%, Credit Adjustment 3.3%. Reconciles to the invoice-level total within 0.01%, so both sources agree — worth saying if challenged on where the figure comes from.
- **~550 unique salesmen/day** hitting `/complete` (446 Mon 2026-09-21, 563 Tue 2026-09-22), across **8,401 and 10,844 calls** respectively.
- **~16,500 distinct outlets collected from per working day**; 63,800–82,700 distinct outlets/month.

Why this matters in the room: every design decision in this card — the Redis claim, the per-row
transaction boundary, the amortization ordering — costs something. At ₹105 Cr/month and ~10,500
payment transactions a day, a duplicate-payment race is not a theoretical bug. Open with the money,
then the mechanism.
- [NEED FROM ME: was the UPI amount gap ever observed producing a wrong auto-verification in prod before your fix, and do you know how many / what amount?]
**Cashier verification backlog — real, but do NOT claim credit for it.**

| | Sep–Nov 2024 | Jun–Aug 2025 | Jun–Aug 2026 |
|---|---|---|---|
| Collected/month | 627,225 | 623,687 | 575,846 |
| Eventually verified | 90.7% | 94.4% | 96.7% |
| Same-day | 64.6% | 67.8% | 73.7% |
| Within 24h | 77.8% | 80.6% | 88.0% |
| Average lag | 56.5 h | 63.6 h | **13.8 h** |
| Never verified | 58,493/mo | 34,830/mo | **18,866/mo** |

Latest months are better still — 9.6 h in Jul-26, 9.4 h in Aug-26.

⚠️ **This is deliberately NOT on the resume, and you should not volunteer it as your result.** The
block-edit log groups were created 2024-12-10 and average lag actually got *worse* through 2025
(63.6 h) before collapsing in 2026. Whatever caused the drop happened well after the cashier-v2
rollout. If it comes up, quote the delta and stop: *"average verification lag went from 56 hours to
14, and the unverified tail from 58K to 19K invoices a month — I can't attribute that to one change,
the timeline doesn't support it."* Saying that is a stronger signal than claiming it.
