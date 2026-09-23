DELIVERY PROMISE ENGINE — EDD Computation Service, Supertails

"Everyone assumes promising a delivery date is a lookup. It isn't — it's a constraint-satisfaction problem over inventory, geography, weight, cutoffs and calendars, run fresh on every cart, and if I get the ordering wrong the promise is just wrong, not broken."

================================================ Step 1 ================================================

The 60-second version

"I built the EDD engine that answers one question for every cart at Supertails: what date can we
promise, and out of which warehouse. It sounds like a lookup. It isn't.

First I have to find a warehouse that can actually serve the customer, so I search four levels
deep — lat/lng, then pincode, then city, then state — and stop as soon as every SKU in the cart is
covered. The tricky part is that the same physical warehouse can show up at more than one level, so
I keep a single allocation tracker that spans all four levels. Without that, the same warehouse
could get promised twice for the same stock.

Once I know which warehouse serves which SKU, I have to pack the cart into shipments. A warehouse
has a maximum shipment weight, so I explode every SKU down to individual units and pack them
first-fit — the moment the next unit would blow the weight cap, I close that shipment and start a
new one. So one SKU's quantity can literally split across two shipments.

Then each shipment goes through an eight-stage pipeline — cutoffs, static buffers, rain buffers,
capacity buffers, tag buffers, SLA, then two day-skip passes — and the order of those eight stages
is not arbitrary. Get the order wrong and you get a wrong promise that looks completely normal. And
I do all of the IST time math by hand, with no timezone library, because the process runs in UTC and
I control every conversion myself."

================================================ Step 2 ================================================

The interviewer asks: "Walk me through the geographic fallback and why you need a global tracker."

```
Cart request (SKUs, qty, lat/lng, pincode)
        │
        ▼
 Level 1: lat/lng  ──found all SKUs?──► done
        │ no (or no coords given)
        ▼
 Level 2: pincode   ──found all SKUs?──► done
        │ no
        ▼
 Level 3: city       ──found all SKUs?──► done
        │ no
        ▼
 Level 4: state       ──found all SKUs?──► done / else OOS

  globalWarehouseAllocations{ sku → warehouse → qtyAlreadyPromised }
  threaded BY REFERENCE through all 4 levels
        │
        ▼
  availableQty = totalInventoryQty − globalAllocatedQty
  (never the raw inventory column — always net of what's already promised)
```

"A warehouse doesn't belong to just one cluster. The same physical warehouse can be the closest
match for a pincode-level cluster and also sit inside a city-level cluster. If I checked each level
independently, I could promise the same 10 units in that warehouse to the pincode search and then
promise them again to the city search, because as far as the city-level code knows, nothing's been
taken yet.

So I built one map — SKU to warehouse to quantity already promised — and I pass it by reference
through all four levels. Every time I check if a warehouse has enough stock, I'm checking inventory
minus what this tracker already claims, not the raw number in the database. It has to span all four
levels or it doesn't work at all — a tracker that resets between levels is exactly the bug I'm
avoiding."

"The tracker isn't an optimization. It's the only thing standing between this system and shipping
the same stock to two different warehouses' promises."

================================================ Step 3 ================================================

The interviewer asks: "What happens when one SKU can't be filled by a single warehouse?"

"I don't fail the SKU the moment one warehouse falls short. I decrement the requested quantity
warehouse by warehouse, in priority order, within a level — and whatever's left over carries forward
into the next level. So a SKU can genuinely split: five units from a Bangalore warehouse at the
pincode level, and the remaining five picked up by a city-level warehouse.

But here's the policy decision I made deliberately: a SKU only counts as 'found' when its remaining
quantity hits exactly zero. If I've walked all four levels and there's still a gap — even one unit
short — I don't ship the nine I did find. I mark the entire quantity out of stock and I delete any
partial allocation I'd already recorded for that SKU. It's all-or-nothing per SKU.

That was a real call, not an accident: a partial promise is worse than no promise, because a
customer sees a delivery date for an order that's actually short."

================================================ Step 4 ================================================

The interviewer asks: "Tell me about the weight-based shipment packer."

```
Cart items for one cluster+warehouse
   sorted ascending by weight
        │
        ▼
   explode to individual UNITS  (not SKU-level, unit-level)
        │
        ▼
   add unit → currentShipment.totalWeight += unitWeight
        │
   would adding the NEXT unit exceed maxWeightLimit?
        │
       yes ──► close currentShipment, start a new one
        │
       no ──► keep packing
```

"A warehouse has a maximum shipment weight — say a courier truck slot caps at 10 kg. I don't pack at
the SKU level, because if I did, a single 10-unit SKU order could just get rejected as 'too heavy.'
Instead I explode everything down to individual units, sort them by weight, and pack first-fit — the
moment adding the next unit would tip the shipment over the cap, I seal that shipment and open a new
one.

So it's genuinely possible for one SKU's order quantity to end up split across two shipments with
two different delivery dates, because the second half physically can't ride in the same box as the
first. That surprises people the first time they see it in a cart response, but it's exactly what
has to happen if the truck has a weight limit."

"It's not weight-optimal bin-packing — it's simple first-fit. I chose that on purpose because the
alternative is more compute for a marginal packing gain on a request that has to return in
milliseconds."

================================================ Step 5 ================================================

⭐ The strongest card — the eight-stage buffer pipeline, and why order is everything

```
1. CUTOFFS            (hyperlocal: outside time window | others: past daily cutoff time)
        │  if hyperlocal cutoff fires → REPLACES the SLA-addition step below, doesn't add to it
2. STATIC BUFFERS      (cluster_warehouse > warehouse > cluster priority; area/weight gated)
        │  rain buffer is injected HERE, but only if no static buffer already exists —
        │  rain and configured buffers must never stack
3. CAPACITY BUFFERS    (only fires once order_count + spill >= configured capacity)
4. TAG BUFFERS         (per-SKU tag-driven delay)
5. SLA TIME ADDITION   (weight-slab matched, hour/day/min)
6. PICKUP DAY-SKIP     (walks forward on a separate "pickup" clock)
7. DELIVERY DAY-SKIP   (walks forward on the real delivery clock)
8. TIME-OF-DAY RESET   (re-anchor after a day-skip, else default 22:00, else ≥23:30 rolls to next-day 13:00)
```

"This is the part of the system where I have to be precise about order, because every stage is
config-driven and every stage can silently change what the next stage does.

Take the cutoff stage. For hyperlocal delivery, if I'm outside the serviceable time window, that
cutoff doesn't add extra time on top of the SLA — it *replaces* the SLA-addition step entirely. If I
ran both, I'd double-count the delay.

Take the rain buffer. It's injected into the same array as the manually configured static buffers,
before that stage's loop runs — but only if no genuine static buffer already exists for that
warehouse. If I let both apply, a warehouse with its own configured delay would get hit twice, once
for the weather and once for the manual buffer, and the promise would blow out further than either
buffer was designed for.

And take day-skip. A day-skip advances the *date* — walk forward past a holiday, say — but it
doesn't touch the *time*. If I don't explicitly re-anchor the clock after a day-skip, I end up with
a date that jumped forward correctly but a time-of-day that's stale from before the skip. I built a
small helper specifically to reset the time back to the configured cutoff time after every pickup
and delivery day-skip, because I'd already seen that bug happen without it."

"None of these eight stages is hard on its own. What's hard is that every one of them can silently
change the meaning of the stage after it, and there's no compiler that catches you running them in
the wrong order — you just get a wrong date that looks completely plausible."

================================================ Step 6 ================================================

The interviewer asks: "Why hand-roll IST time math instead of using a timezone library?"

"The whole service runs in UTC. There's no timezone library in this codebase for the date math I
own — no moment-timezone, no luxon. So to get an IST wall-clock time, I take the current UTC epoch,
add five and a half hours in milliseconds, and then read hours/minutes off that shifted Date as if
it were local time. It works because I know the process itself is UTC, so the shift is consistent
every time.

The place this actually gets dangerous is around midnight. When a cutoff fires, I don't add hours
incrementally — I add whole days via a days-to-add config value, and then I hard-set the clock to
the configured target time with setHours/setMinutes/setSeconds. I don't do
'currentTime + cutoffHours' arithmetic, because that's exactly the kind of thing that rolls over a
day boundary wrong. Hard-setting the target time avoids that whole class of bug.

The cost is that every date operation in this file is more verbose than it would be with a real
timezone library, and I'm the only guard against a rollover mistake — there's no test suite forcing
me to get it right at 11:58 PM."

================================================ Step 7 ================================================

The interviewer asks: "What's the second-guessable design decision in here?"

"Capacity buffers only apply once a warehouse's order count plus spill has already breached its
configured capacity for that time window — the database query itself filters to only-already-breached
rows. So capacity buffering is reactive, not predictive. If a warehouse is about to breach in the
next five minutes but hasn't yet, this request doesn't see any buffer. I chose reactive because
predictive capacity forecasting is a much bigger, noisier problem, and reactive buffering is
correct as soon as the next request comes in a few seconds later."

Cut these from your interview story:
❌ "I owned the entire promise engine end-to-end." — This is the one place I'd overreach if I wasn't
careful. Say what I actually built: the geographic search, allocation tracker, weight packer, and
the buffer/day-skip pipeline ordering — not every route or every config table in the system.
❌ "It's realtime and always accurate." — There's no promise-accuracy metric wired into this service;
the pipeline is deterministic given its config, but I have no measured number for delivered-vs-promised
drift and shouldn't imply I do.
❌ "It's optimal bin-packing." — It's first-fit, explicitly chosen for speed over optimality. Don't
let "weight-based packer" get inflated into an algorithms flex it isn't.

Numbers you must know:
- Four-level geographic fallback: lat/lng → pincode → city → state.
- Eight buffer/cutoff stages, in the fixed order above.
- Ten delivery-type values in the current config (hyperlocal, hyperlocal B, SDD A/B/C, NDD A/B/C,
  Standard A/B).
- **130 active warehouses and darkstores, and a 43,556-SKU plannable catalogue.** Confirmed
  2026-09-22 from the promiseEngine DB. The 130 is distinct active `serving_entities` after removing a
  `Testtt` test row and 2 duplicates from a raw 133; it cross-checks against 133 warehouse columns on
  `EdditemInventory`, 129 reconciling on both sides. The 43,556 is SKUs that are Unicommerce-ACTIVE
  **and** have an `EdditemInventory` row — the same INNER JOIN the engine itself uses, so it is what the
  engine can actually plan against, not the 54,366 total rows. Quote the join, not the row count: it is
  the difference between a number you read and a number you understand.
- 29 config models behind the pipeline (clusters, warehouses, cutoffs, static/capacity/tag buffers,
  day-skips, plus a 9-model rain-buffer subsystem).
- Nine SKU-suffix patterns sanitized before inventory lookup (promo/bundle variants collapsing to
  one base SKU).
- Non-hyperlocal deliveries default to 22:00 IST unless a day-skip re-anchors the time; anything
  landing at 23:30 or later rolls to next-day 13:00.
- [NEED FROM ME]: What's the measured out-of-stock rate — the fraction of SKU requests that end up
  all-or-nothing OOS after all four levels are exhausted?
- [NEED FROM ME]: Do you have a promise-accuracy number — delivered date vs. promised date — from
  any downstream dashboard, even a rough one?
- **~50,000 requests/day** served by the Promise Engine. Confirmed 2026-09-22 from your own
  production observation. Quote it as service traffic ("the engine sits behind about 50K requests a
  day"), NOT as 50K delivery-promise computations — the split between EDD calls, crons and health
  checks is not confirmed, so do not let it get pinned to one.
- [NEED FROM ME]: The breakdown of that 50K — how much is genuine cart/EDD traffic versus crons,
  webhooks and health checks? Worth knowing before someone asks you to decompose it.
- [NEED FROM ME]: The p95 latency you've seen for a cart with several shipments.
