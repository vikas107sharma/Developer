NOTIFICATIONS & GST E-INVOICING — WhatsApp Delivery + ClearTax Compliance, Ripplr Fin

"The hard part was never sending the WhatsApp message. It was proving to a government portal that ₹500 minus tax equals exactly ₹500, to the paisa, every single time."

================================================ Step 1 ================================================

Your 90-second answer

"I built the WhatsApp notification pipeline for collections and cheque recovery, and the GST e-invoicing that sits behind part of it. Kafka decouples the decision to notify from actually sending anything — a producer fires an event, a consumer picks a strategy based on the event key, and dispatches to WATI.

Two things made this more than a send-a-message problem. First, eligibility: a collection can be verified payment-by-payment across several days, so I don't trust the event payload to say 'send now.' The event only carries a salesman ID and a date — a signal, not a decision — and the consumer re-derives whether that salesman-day is actually complete from the database at the moment it processes the message. A cron sweep runs the same eligibility check as a fallback.

Second, GST. When a bounced-cheque charge gets recovered, I have to generate a real tax invoice through ClearTax. The charge is GST-inclusive, but the portal validates the individual 9% CGST and SGST components and the total independently — a naive divide-by-1.18 can be off by a single paisa and get the invoice rejected. I built a bounded search over rounding candidates that finds an exact match, proven by a parametrized test suite."

================================================ Step 2 ================================================

⭐ THE strongest card — paise-exact GST reconciliation

The interviewer asks: "Why is rounding even a hard problem here?"

"The bounce charge is a fixed, GST-inclusive number — say ₹500 all-in. To generate a compliant invoice I need to split that into a taxable value plus 9% CGST plus 9% SGST that adds back up to exactly ₹500. The naive way is taxable = gross / 1.18, then round.

The problem is the portal checks two things independently: that CGST + SGST equals the total tax, and that taxable + total tax equals the gross, to the paisa. A single rounding decision — round half-up versus round down versus round up — can satisfy one check and miss the other by ₹0.01. That's enough for ClearTax to reject the invoice.

So instead of picking one rounding rule and hoping, I generate candidates: three rounding modes — half-up, floor, ceiling — around the taxable estimate, each nudged by five small deltas, so up to fifteen candidates total. For each one I compute CGST and SGST independently at 9%, and take the first candidate where taxable plus tax equals the gross exactly. It terminates because the search space is small and finite — fifteen checks, worst case — and I have a deterministic fallback if somehow none of them land exactly. A parametrized test suite locks both invariants down across gross values from a couple of rupees up into the tens of thousands, so this isn't just 'it worked on my test case.'"

================================================ Step 3 ================================================

The second-strongest card — the three-tier fallback resolver

"You mentioned a production incident. What happened?"

"A ClearTax call threw partway through generating a tax invoice, and the row that got persisted had null taxable value and null tax amount — a financially inconsistent record sitting in the table. That's the kind of thing that quietly corrupts downstream reconciliation.

I rebuilt the persistence path as a three-tier fallback: use the live ClearTax response if the call succeeded, otherwise fall back to a value I'd already computed just before making the call, and if even that's unavailable, derive it directly from the gross amount. The row is never left with null tax fields, full stop. I have a regression test that names the specific incident and asserts that invariant."

================================================ Step 4 ================================================

The event-as-signal card

"Why does the Kafka event only carry a salesman ID and a date, not the actual invoices?"

"Because cashier verification is asynchronous and can span multiple days for the same salesman. If I embedded the invoice list in the event at publish time, I'd be trusting a snapshot that can go stale by the time the consumer processes it.

Say there are four payments for one salesman. Two get verified today, two get verified three days later. If I trigger off the individual verification event, I either send a receipt while the collection is half-verified, or I send two receipts for one collection. Neither is right.

So the event is just a pointer — 'something changed for this salesman on this date' — and the consumer re-runs the eligibility query against live state. Today's two verifications fail the all-verified condition and produce nothing. Three days later, the fourth verification makes the salesman-day complete, and one receipt goes out covering all four payments."

================================================ Step 5 ================================================

The dual-producer idempotency card

"You have two things that can trigger the same notification — doesn't that race?"

"It would, if I coordinated the two producers directly. Instead I made the database the coordination point. Before sending, I write a pending row to the notification log. The eligibility query for both the live event path and the cron sweep excludes any salesman-day that already has a successful log row — that's a NOT EXISTS check.

So whichever path gets there first wins the send, and the other path's next eligibility check just returns nothing to do. I don't need a distributed lock between Kafka and a cron job — the log table already is one."

================================================ Step 6 ================================================

The images-not-PDFs card

"Why are the receipts and invoices images instead of PDFs?"

"WhatsApp delivery through WATI is friction-free for an image — it renders inline in the chat. A PDF is a document the retailer has to tap and open separately, which is a worse experience for something they're going to glance at once.

I render everything with PIL — the payment receipt computes its canvas height from the actual number of payment lines so it doesn't waste space or clip content, and picks one of three closing messages depending on whether the invoice ended up fully paid, partially paid, or nothing collected. The tax invoice does the same thing but overlays the IRN and the signed QR code from ClearTax onto the rendered image."

================================================ Step 7 ================================================

⭐ The bug you SHOULD volunteer

"There's a real reliability gap in my own consumer, and I'd rather bring it up than have it found. The Kafka consumer commits the offset on both the success path and the exception path — there's actually a comment directly above the commit call on the failure branch that says 'don't commit here if you want retries,' and the line beneath it does it anyway. It was flagged and never fixed.

The practical effect: a processing failure is logged and then permanently forgotten from Kafka's point of view. There's no dead-letter queue, so that message and whatever it was supposed to trigger — a WhatsApp send, a document — is just gone.

It's partially covered for collections, because the cron sweep re-derives eligibility from the database independent of whether the original message survived. It is not covered at all for cheque-bounce and charge-collection notifications — those have no sweep, so a lost message there is genuinely unrecoverable without someone manually hitting one of my retry endpoints. I'd fix it by not committing on the exception path at all, and adding a DLQ for messages that fail repeatedly rather than transiently."

================================================ Step 8 ================================================

Q&A — design patterns

"What design patterns does this system actually use?"

"Strategy, mainly — NotificationService.notify() dispatches on a template-type key against a strategy map, so adding a sixth template is a new map entry and a payload builder, not a new conditional branch. I'll volunteer something most people wouldn't: there's a second, independent implementation of the exact same strategy-map idea elsewhere in the payload builder that has zero callers anywhere in the codebase — dead code duplicating a live pattern. I'd rather flag that myself than have someone find it and wonder if I know my own system.

There's also a light Facade in NotificationService itself — one entry point hiding the WATI call, the S3 upload and the log writes from the consumer — and something close to Template Method across the four payload-builder methods, which all follow the same build-then-render-then-upload shape with different fill-in steps."

================================================ Step 9 ================================================

Q&A — do we actually need a dead-letter queue?

"Given the bug you just described, do you think a DLQ is necessary?"

"It depends on which half of the system you're asking about. For collections, arguably not urgently — the cron sweep already re-derives eligibility from the database on a schedule, so a lost event self-heals within one sweep interval regardless of whether I add a DLQ.

For the cheque flows, yes, because there is currently zero recovery path — a lost cheque-bounce message just stays lost. The honestly cheaper fix that doesn't require new infrastructure is to stop committing on the exception path and let Kafka's normal redelivery-on-no-commit handle transient failures, and reserve an actual DLQ for messages that fail repeatedly — a poison-message problem, not a first-failure problem."

Cut these from your interview story:

❌ "We send 17,000+ messages a day."
A bare volume number invites "how do you know?" and sounds like something you read off a slide. Say what the number *is* instead: **one verification message per invoice, and we do about 17,000 invoices a day.** Same figure, but now it is a derivation an interviewer can follow, and it tells them the send volume is bounded by invoice volume rather than by anything in my control. If they push on headroom, the one-second sleep after each commit caps a single consumer instance near 86,000/day — so we are running at roughly a fifth of one instance's ceiling.

❌ "The system has zero downtime and never loses a message."
It loses cheque-side messages on any processing exception, with no recovery path today. That's a known gap I'd rather own than paper over.

❌ "I built the whole ClearTax integration alone from day one."
True I own it end to end today, but I'd rather lead with the specific mechanism — the rounding search, the fallback resolver — than a broad ownership claim that invites "prove it."

Numbers you must know

- GST decimal search: 3 rounding modes × 5 deltas = up to 15 candidates checked per calculation; a parametrized test suite asserts taxable+tax==gross and cgst+sgst==total_tax across gross values from a couple of rupees to the tens of thousands.
- Templates: 5 wired end-to-end through the live strategy map; 2 enum values exist but aren't wired to it.
- Retry policy on the WATI call: 3 attempts, backoff roughly 0.5s then 1.0s.
- Consumer self-throttle: a fixed 1-second sleep after every successful commit — a hard ceiling around 86,400 messages/day per running instance, before any per-message latency.
- **~17,000 messages/day, derived: one verification message per invoice at ~17,000 invoices/day.** Confirmed 2026-09-22 from your own production observation. Lead with the derivation, not the raw count — and note it sits at ~20% of a single instance's 86,400/day ceiling, which is the natural follow-up.
- [NEED FROM ME: how many consumer instances run in production, and is the topic partitioned, or does everything funnel through one instance? Changes whether the 86K/day ceiling is a system number or a single-instance number.]
- [NEED FROM ME: do we have an incident ticket or thread for the ClearTax null-tax-value incident, so I can cite a real date/impact instead of just the code fix?]
