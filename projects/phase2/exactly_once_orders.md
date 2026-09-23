EXACTLY-ONCE ORDER CREATION — MyDesignation Backend, Shopify

"Two writers I don't control can both try to create the same order for the same payment, at the same instant — and if I lose that race, a customer gets charged once and billed twice."

================================================ Step 1 ================================================

The 60-second version

"When a customer pays, two completely independent things can try to create the Shopify order for that payment: the app's own verify call, which fires the moment the payment sheet closes, and Razorpay's webhook, which fires from Razorpay's servers whenever it feels like it. Either can arrive first. Both can arrive. They don't know about each other.

A duplicate order here isn't a cosmetic bug — it's a customer charged once by Razorpay and then billed twice by the store, and someone has to notice, refund, and apologize.

So I made one Postgres row per checkout attempt the single source of truth, and I let the database itself decide who wins. Claiming that row is a conditional UPDATE, and the number of rows it actually changes is the entire answer — one means you won and you create the order, zero means someone already did and you walk away. No flags, no read-then-check, no application-level 'if this is still pending.' The database's own row-count is the arbiter."

================================================ Step 2 ================================================

The interviewer asks: "Why trust a rows-affected count instead of, say, a distributed lock?"

"Because a rows-affected count doesn't need a second system to be correct. A conditional `UPDATE ... WHERE status IN (...)` is a single atomic statement — Postgres itself guarantees only one concurrent writer can flip that row's status, and it tells me the outcome for free, in the same round trip. A distributed lock is another moving part that can itself fail, expire, or be held by a dead process. I'd rather have the database's own concurrency control do this than build a second one on top of it."

Then give one concrete example:
"`claimForFulfillment` runs the UPDATE and checks `res.count === 1`. If it's 1, I own this order and I go create it in Shopify. If it's 0, the app's verify call already claimed it — or vice versa — and I return the existing state instead of doing anything."

================================================ Step 3 ================================================

They ask: "What if both writers hit that UPDATE at literally the same instant?"

"The UPDATE already resolves that — only one of them can be the one that actually changes the row, that's what atomicity means. But I don't rely on that alone. The Razorpay payment id and the Shopify order id columns are both `UNIQUE`. So even in the pathological case where the state machine somehow let two writers both think they'd won, the second `INSERT` or `UPDATE` that tries to write the same payment id hits a real constraint violation. I treat that violation as exactly one thing — 'I lost the race' — not as an error to alert on. It's a second, independent line of defense underneath the first one, and it's the database enforcing it, not my code remembering to check."

================================================ Step 4 ================================================

The ⭐ strongest card — the partial unique index for cash-on-delivery

"Prepaid orders have a payment id from Razorpay to key off. Cash-on-delivery doesn't — there's no payment event at all, just the customer tapping 'place order.' If someone double-taps, or the app retries a slow response, I need to stop a second order without a payment id to deduplicate on.

The fix is a partial unique index on the cart id — `WHERE method = 'cod' AND status IN ('created','verified','paid')`. While an attempt is actually live, the cart can only have one row, so a double-tap collides on the index and becomes a safe no-op. But the moment that attempt fails, its status moves outside that WHERE clause, and it drops out of the index entirely — so a genuinely failed attempt doesn't permanently lock the customer out of ordering. It's a uniqueness constraint with a lifetime, which is something MySQL can't express at all. That one line of SQL is the entire reason this schema is on Postgres."

================================================ Step 5 ================================================

They ask: "When exactly does the claim get released?"

"Only on a failure that happens before the order exists. If creating the Shopify order itself throws — network error, Shopify's API rejects it — I release the claim so the row goes back to being claimable and the customer or the webhook can retry cleanly. But once Shopify has actually returned an order back to me, the claim is never released again. At that point releasing it would let a second writer create a second order for a payment that already has one. Getting that boundary right — release before creation, never after — is the one rule the whole protocol hangs on."

================================================ Step 6 ================================================

They ask: "Walk me through the webhook path end to end."

"Razorpay POSTs a payment event. Before I even check the signature, I log the raw delivery — that way even a forged or malformed request leaves a forensic row I can look at later. Then I verify the HMAC signature over the raw request bytes, not the parsed JSON, because re-serializing JSON can change byte-for-byte content and break the signature. A mismatch is a 401. If it checks out, I enqueue the event to SQS and return in single-digit milliseconds. The only time I return a server error is if the enqueue itself fails — because that's the one case where I genuinely haven't processed the event and I want Razorpay to retry it. Everything else — actually creating or updating the order — happens later, in the worker, off the request path entirely."

================================================ Step 7 ================================================

They ask: "What decides whether a queued message gets deleted or redelivered?"

"It's explicit, not automatic. If the handler returns successfully, I delete the message from SQS myself. If it throws, or the body isn't even valid JSON, I do nothing — the message stays and SQS redelivers it after the visibility timeout, and eventually it dead-letters after the retry count is exhausted. But I split those two failure cases on purpose: a malformed ClickPost payload gets logged and completed without retry, because it will never parse no matter how many times it's redelivered — retrying it just delays the DLQ for no benefit. An unknown message type, on the other hand, throws deliberately, so it dead-letters and stays visible instead of silently vanishing. One is 'this will never succeed, stop wasting redeliveries.' The other is 'something's wrong upstream, don't let this disappear quietly.'"

================================================ Step 8 ================================================

The race, drawn out

```
   App verify call                                Razorpay webhook
        |                                                 |
        |  UPDATE payment_orders                          |  UPDATE payment_orders
        |  SET status='verified'                          |  SET status='verified'
        |  WHERE status='created'                         |  WHERE status='created'
        |  AND id = :id                                   |  AND id = :id
        v                                                 v
   +---------------------------------------------------------------+
   |                     single Postgres row                       |
   |          only ONE of these UPDATEs can affect a row            |
   +---------------------------------------------------------------+
        |                                                 |
   count == 1 -> "I won"                          count == 0 -> "already claimed"
        |                                                 |
        v                                                 v
   create Shopify order                          read existing order state
   (unique payment/order columns                  return it, do nothing else
    catch any true tie as a
    constraint violation = "lost")
```

================================================ Step 9 ================================================

A gap worth naming yourself

"The whole protocol assumes the worker processes messages with limited, well-understood concurrency — the concurrency knob defaults to 1, capped at 10. Raising it shouldn't break anything, because both consumers are idempotent by construction, not by luck. But 'shouldn't break' and 'measured to not break' are different claims, and I haven't load-tested the claim protocol at higher worker concurrency. If I were pushing that number up, I'd want a dedicated test proving it before I'd trust it in production."

================================================ Step 10 ================================================

Cut these from your interview story:

❌ "I used a database transaction to make this atomic."
Why it's weak: it's deliberately not a multi-statement transaction — holding one open across a network call to Shopify would mean a long-held lock during a slow upstream call. It's a single-statement conditional UPDATE plus constraints, which is a different and more deliberate trade-off.

❌ "The queue guarantees exactly-once delivery so duplicates can't happen."
Why it's weak: SQS standard queues are at-least-once by design — the guarantee comes from the consumers being idempotent, not from the queue. Saying the queue guarantees it gets the mechanism backwards.

================================================ Step 11 ================================================

Numbers you must know

- 3 UNIQUE columns on the payment-order row: razorpayOrderId, razorpayPaymentId, shopifyOrderId
- 2 hand-written partial unique indexes outside the ORM: one for COD, one for zero-payable/store-credit carts, both scoped to `WHERE status IN ('created','verified','paid')`
- Razorpay outbound calls: 8-second timeout, zero retries — a deliberate correctness choice, not a latency one
- SQS DLQ redrive: maxReceiveCount of roughly 5
- Webhook response time on the happy path: single-digit milliseconds; 5xx returned only when the enqueue call itself fails
- [NEED FROM ME]: "In production, how often has the webhook path actually won the claim race versus the app's own verify call?"
- [NEED FROM ME]: "What's the current SQS DLQ depth, and how many messages have ever actually landed there?"
