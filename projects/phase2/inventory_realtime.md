REALTIME INVENTORY SYNC — ERP → Promise Engine, Supertails

"The bug I'm proudest of catching isn't a crash — it's a query that succeeded, logged nothing, and quietly told the delivery engine we were out of stock on items we actually had."

================================================ Step 1 ================================================

The 60-second version

"I worked on the inventory side of the Promise Engine at Supertails. The Promise Engine needs
warehouse inventory to decide whether it can promise a delivery date.

Originally inventory came from the ERP through a periodic cron snapshot. That meant the delivery
engine could be working off inventory that was several minutes stale.

I added a realtime path: the ERP calls a webhook when something changes, I validate the request with
a timing-safe secret check, publish it to Pub/Sub, and return 202 immediately. A subscriber does the
actual database write asynchronously, off the request path entirely.

I kept the cron running. Realtime isn't the correctness guarantee here — the periodic snapshot is.
If a webhook gets lost, duplicated, or processed out of order, the next snapshot reconciles
everything back to truth.

The hardest bug I found was that the cron and the webhook wrote through the same function even
though their payloads meant different things. The cron sends a full snapshot — every item lists
every warehouse. The webhook sends a delta — an item only lists the warehouses that changed. The
writer didn't know the difference, and that's exactly where it broke."

================================================ Step 2 ================================================

⭐ The bug you SHOULD volunteer — the delta clobber

```
ONE writer, TWO callers, TWO different payload contracts

  CRON (full snapshot)              WEBHOOK (delta)
  every item lists                  item lists ONLY
  every warehouse                   warehouses that changed
        │                                  │
        └──────────────┬───────────────────┘
                        ▼
              bulkInsertERPInventory()
      1. union every warehouse name seen in this batch
      2. for EACH warehouse in the union, write a row for EVERY item
      3. item never mentioned this warehouse → defaults quantity to 0
      4. writes that 0.  No exception. No error log. Query succeeds.
```

"Say SKU A changes in Bangalore and SKU B changes in Delhi, and both arrive in the same webhook
batch. The writer builds the union of every warehouse mentioned anywhere in the batch — Bangalore and
Delhi. Then for each warehouse in that union, it writes a row for every item in the batch. When it
gets to the Delhi column and looks up SKU A's Delhi quantity, SKU A never said anything about
Delhi — so it defaults to zero. And it writes that zero straight into the inventory table.

A realtime update for one warehouse just silently zeroed a completely unrelated SKU's stock in a
warehouse nobody was even talking about. No exception thrown, no error logged, the SQL statement
succeeded exactly as written. Downstream, zero stock means the promise engine treats the item as
unavailable, so we stop promising a delivery date on inventory we actually have sitting in the
warehouse.

I couldn't fix what I couldn't see, so the first thing I did was add detection, not the fix itself —
I tagged every write with which caller produced it, logged the warehouse actually matched versus
defaulted, and added a diagnostic distinguishing a real zero from a zero the writer invented. Once
that was in place the pattern was obvious in the logs. The actual fix: if the write is a delta and
the item never mentioned that warehouse, drop that (item, warehouse) pair from the upsert entirely —
don't write anything, let the existing value in the database stand. The full-snapshot path is
untouched; it still means what it always meant, every column really is being refreshed.

The lesson wasn't 'don't reuse code.' One writer, one place for the SQL, is good design. The actual
problem was sharing that writer between two callers whose data meant fundamentally different
things, and never encoding that difference anywhere in the writer itself."

"The problem wasn't code reuse. The problem was sharing a writer between two callers whose data
contracts were different — and letting the writer treat 'this warehouse wasn't mentioned' the same
as 'this warehouse is genuinely empty.'"

================================================ Step 3 ================================================

The interviewer asks: "You mentioned a second bug. What happened with Pub/Sub?"

```
             Topic
     real_time_inventory_sync
                    |
            Subscription
     real_time_inventory_sync-sub
               /         \
              /           \
     Prod Consumer   Staging Consumer
     (same subscription name = Pub/Sub treats
      them as ONE logical subscriber)
```

"When staging was deployed, its subscriber used the exact same subscription name as production.
Pub/Sub doesn't know or care that one of those processes is staging — same name means same logical
subscriber, so Pub/Sub round-robins each message to only one of the two instances that happen to be
attached. That means some inventory events meant for production only ever got processed by staging,
or vice versa, and the other side silently never saw them.

The fix was to give staging its own distinct subscription name. Once the names differ, Pub/Sub
treats them as genuinely separate subscribers and delivers to both — which is what you actually want
when the two environments are meant to be isolated. I moved both the topic and subscription names
out of hardcoded strings and into environment variables with a fail-fast check at startup, so a
missing name can't silently fall back to a shared default again."

"That's the bug that taught me Pub/Sub subscription identity is just a string match — it doesn't
know about your environments, only about the name you gave it."

================================================ Step 4 ================================================

The interviewer asks: "Why 202 and not 200? Why keep the cron at all?"

"202 means accepted, not completed. The actual database write happens after the Pub/Sub publish
resolves, on a different process, at a time I don't control from the request. Returning 202 with the
Pub/Sub message ID tells the ERP 'I've got this, here's how to trace it if you need to,' which is
honest — a 200 would imply the write already landed, and it hasn't yet.

I kept the cron because the webhook path is not a correctness guarantee — it's a speed
optimization. Deltas can be lost, duplicated, or processed out of order, and the webhook path has no
ordering key. The periodic snapshot rewrites every mapped warehouse column for every SKU on its
pages, so whatever damage an out-of-order or dropped delta does gets reconciled the next time the
snapshot runs. Realtime gets you freshness; the cron is what guarantees you're never permanently
wrong."

================================================ Step 5 ================================================

The interviewer asks: "Why Pub/Sub instead of RabbitMQ? Why no dead-letter queue?"

"Pub/Sub was already in the stack — the service was already on GCP with a service account and
Cloud Storage wired up, so adding Pub/Sub didn't mean standing up new infrastructure. It gave me a
simple event bus and decoupling without another moving part to operate.

Honestly, for this specific workload, RabbitMQ could be the better technical fit — it gives you
finer application-level control over retries, backoff, per-queue acknowledgement, and
dead-lettering. If I were designing this from scratch purely for this workload, I'd genuinely
consider it. I chose Pub/Sub because it was the path of least new infrastructure, not because it was
strictly the better tool.

I didn't add a dead-letter queue on purpose — it felt like unnecessary complexity for the failure
modes I actually cared about. The bigger risk isn't a poison message, it's out-of-order delivery: if
a quantity-10 event fails and gets requeued behind a quantity-5 event that arrives and processes
first, then the retried 10 comes through afterward and stomps the more-recent 5 back to 10. There's
no ordering key on these messages, so that's a real, live risk, not a hypothetical. What actually
tolerates it is the periodic snapshot — if a webhook gets lost, delayed, duplicated, or processed out
of order, the next snapshot run puts the number back to ground truth."

Cut these from your interview story:
❌ "It's a five-minute cron, so lag is bounded at five minutes." — I know the cadence is periodic and
short, but the exact interval isn't something I can point to in the code — Cloud Scheduler config
lives outside this repo. Say "a periodic snapshot" unless asked to confirm the number, then say you'd
need to check the scheduler config.
❌ "The webhook made inventory fully realtime." — It didn't remove the cron's job, it added a faster
path alongside it. The cron is still the correctness backstop, and I should say that up front rather
than let "realtime" imply the old path is gone.
❌ "Nack handles every failure correctly." — The nack path only fires when the handler throws. A
database write that fails without throwing gets acked anyway, since the writer swallows DB errors
and returns a boolean the subscriber never checks. Worth naming as an honest gap, not glossing over.

Numbers you must know:
- Webhook status ladder: 500 (secret not configured) / 401 (secret mismatch) / 400 (invalid or empty
  payload) / 200 (nothing to queue) / 202 (queued, with a Pub/Sub message ID).
- Pub/Sub subscriber flow control: maxMessages 1 per client — bounds concurrency per instance;
  cross-instance parallelism still exists because every App Engine instance runs its own subscriber.
- Warehouse-mapping cache: Redis-first, 1-hour TTL, DB fallback on miss, non-blocking cache writes.
- SKU-code length filter: items with an item_code over 45 characters are dropped before any insert,
  on both the cron and webhook paths.
- No dead-letter queue by design; no ordering key on published messages.
- **~3,000–4,000 ERP inventory events/day observed steady-state, with an upper band of ~5,000–7,000.**
  Confirmed 2026-09-22 from your own production observation. **The resume states the upper bound,
  "~7K events/day."** If pressed, the honest line is "three to four thousand on a normal day, up to
  seven on a heavy one" — so do not be surprised if someone asks you to break it down.
- **The 5-minute cron cadence is the baseline worth leading with.** The freshness delta — a
  5-minute snapshot down to near-realtime — is a stronger number than the event count, because it
  is the thing the work actually changed. Open the answer with it.
- [NEED FROM ME]: The number of Cloud Scheduler jobs (you've said "six" before, but that config
  lives outside this repo — confirm from the scheduler console). The 5-minute interval itself is
  corroborated by your phase1 inventory_sync notes.
- [NEED FROM ME]: Typical page size — bytes, item count, and warehouse count per page — so I can
  quote a real payload size instead of a remembered one.
- [NEED FROM ME]: The instance memory/class this ran on when you saw the crash under load, and what
  the App Engine memory graph actually showed at the time.
