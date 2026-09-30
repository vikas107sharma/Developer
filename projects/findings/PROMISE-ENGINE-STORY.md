# The Delivery Promise Engine: the story, end to end

One cart, followed from the moment the shopper opens it to the moment their order changes the promise for the next shopper. The rules are the engine's real rules. **The numbers in the example are made up.**

---

## The 60-second version

Every time a shopper opens a product page or a cart, we have to answer three questions:

- **Where** will this ship from?
- **How** will the order split?
- **When** will each part arrive?

It looks like a lookup, but it's really a pipeline.

1. **Find the shopper.** We start with the shopper's exact location and turn it into a hexagonal map cell. That cell tells us which delivery zones they're in.
2. **Find the stock.** We search for stock from the nearest warehouses outward: first the zone, then the pincode, then the city, then the state. A small ledger stops us counting the same warehouse's stock twice.
3. **Pack the parcels.** Whatever we can source gets packed into parcels under each warehouse's weight limit.
4. **Date each parcel.** Each parcel goes through a fixed sequence of rules to reach a delivery time:
   - the base SLA for its weight
   - the warehouse's cutoff
   - operational delays
   - rain
   - capacity
   - product tags
   - non-working days
   - a final time-of-day rule

The order of those rules matters, because several of them *set* the clock rather than add to it. Finally, when an order is actually placed, it feeds back into capacity counters, which slows down promises for the next shoppers if a warehouse is overloaded.

---

## 1. The big picture

The Promise Engine is a single Node.js service on Google App Engine. It keeps its data in MySQL, and Redis sits in front as a cache.

**Who asks it for promises.** The storefront backend asks at four moments:
- the product page
- the cart (whose answer also carries the checkout message)
- right after an order is placed
- when a warehouse raises the delivery note for a packed order, to re-date it from the warehouse that's actually shipping it

**What it owns.** Everything needed to compute a promise:
- The delivery zones: map polygons, pincodes, cities, states.
- Which warehouses serve which zones, and at what priority.
- The SLA for each warehouse–zone–weight combination.
- Cutoff times and delays.
- Capacity counters.
- Rain status.

The operations team manages all of this through an admin console, the **Control Tower**, built into the same service.

**Where the stock comes from.** The ERP is the source of truth for stock. Whenever stock changes, the ERP pushes the change to a webhook. The webhook drops it on a Pub/Sub queue, and a subscriber applies it one message at a time. Scheduled full snapshots re-sync everything and refresh the item master (weights, bundle definitions). Bundle stock is pre-computed by a job: a bundle's stock is how many complete bundles its scarcest component allows.

**Weather.** Background jobs poll a weather service for each hyperlocal warehouse and decide whether a rain delay should apply. The operations team gets a chance to approve it before it goes live (Section 8).

```
                 storefront backend
   product page · cart · order placed · delivery note
                          │
                          ▼
   ┌───────────────── PROMISE ENGINE ─────────────────┐
   │  promise calculation  ◄── Redis cache ◄── MySQL  │
   │  Control Tower: zones, SLAs, cutoffs, buffers,   │
   │                 capacity, rain rules             │
   │  stock sync  ◄── ERP webhook → queue, snapshots  │
   │  weather jobs ◄── forecasts → approval (Telegram) │
   └──────────────────────────────────────────────────┘
```

---

## 2. Our example

**When and what.** It's Friday, 7:30 PM. A shopper in Gurgaon has their location turned on, and their cart holds:

| Item | Qty | Weight per unit |
|---|---|---|
| Dog food | 2 | 4 kg |
| Cat litter | 1 | 5 kg |
| Treat sample (a free item) | 1 | 0.1 kg |

**Where the stock is:**
- **Darkstore D** sits inside a delivery polygon that covers the shopper, *and* is part of the shopper's pincode zone. It has 1 dog food and nothing else.
- **Warehouse W** is part of the pincode zone, at a lower priority than D. It has plenty of all three items. Its parcel weight limit is 10 kg.

---

## 3. Where is the shopper? (Serviceability)

**Why H3 cells, not polygon tests.** The obvious approach is to test the shopper's point against every delivery polygon, but that's geometry work on every request. Instead, we do the geometry once, when the polygon is saved. We fill it with **H3 hexagonal cells** at resolution 10 (cells a little over 100 metres across) and store which cells belong to which polygon.

At request time, the engine turns the shopper's latitude/longitude into its one cell and looks that cell up. It's a single indexed lookup, with no geometry at all.

**The trade-off.** The polygon's edge becomes slightly "pixelated". A cell counts as inside if its centre is inside, so a shopper right on a boundary can land either way. For delivery zones, that precision is acceptable, and the speed and simplicity win.

**From cell to warehouses.** The cell gives us polygons. Polygons belong to **clusters**, which are the delivery zones. A cluster has a ranked list of warehouses, each with its own SLAs.

**The fallback chain.** Not every shopper shares their location, and not every location is inside a polygon. So there's a four-level chain, from most local to least:

```
 location → polygon zone ──► pincode zone ──► city zone ──► state zone ──► out of stock
```

- **Each level only searches for what's still missing.** In our example, the polygon level finds 1 dog food at D. Everything else moves on to the pincode level.
- **City and state come from the pincode**, so the chain works even without a location.

**How zones are maintained.** The operations team draws or uploads polygons in the Control Tower. Saving a polygon rebuilds its cells. Zones only change when someone edits them; nothing redraws them automatically.

---

## 4. Who has the stock? (Allocation)

**The problem.** The same physical warehouse can belong to several zones. In our example, darkstore D is in both the polygon zone and the pincode zone. If each level checked stock independently, the polygon level would promise D's one dog food, and then the pincode level would promise it *again*.

**The ledger.** For the duration of one request, the engine keeps a record of every unit it has already promised from every warehouse. At each warehouse:

```
 available here = stock on hand − already promised in this request
 take           = min(available, still needed)
```

**Walking the example through it:**

```
 Dog food needs 2
   polygon level : D   available 1 − 0 = 1  → take 1    still needed 1
   pincode level : D   available 1 − 1 = 0  → skip       ← the ledger at work
                   W   available plenty      → take 1    still needed 0 ✓
 Cat litter needs 1
   pincode level : D   has none → W takes 1 ✓
 Treat sample needs 1
   pincode level : W takes 1 ✓
```

**All-or-nothing per item.** If, after all four levels, an item still can't be fully covered, the *whole* item is marked out of stock, and the partial units are released. We never promise 2 out of 3.

**What the ledger doesn't do.** It lives for one request. Two shoppers checking out at the same moment can both be promised the last unit, because nothing is reserved. Stock corrects itself when the ERP pushes the sale back. It's a deliberate, simple design, and it's the first thing I'd revisit for high-demand items.

**The product page uses a simpler rule.** On a product page, the answer has to be quick and about one item. So there's no splitting: the first warehouse, in the same search order, that can supply the full quantity wins.

---

## 5. How does it ship? (Packing)

**Group by warehouse.** Allocated units are grouped by the warehouse (and zone) they come from. In the example:

- **From D:** 1 dog food (4 kg).
- **From W:** 1 dog food, 1 cat litter, and the sample.

**The free sample goes last.** Gifts and samples are placed after the main items. If a warehouse that is already shipping a main item has the gift in stock, the gift rides along in that parcel. That way a free sample never causes an extra shipment. Here, it joins W's parcel.

**Pack against the weight limit.** Within each warehouse, items are sorted lightest first and added **one unit at a time**. The moment the next unit would push the parcel past the warehouse's weight limit, the parcel is closed and a new one starts.

- **W's parcel:** 0.1 + 4 + 5 = 9.1 kg, under the 10 kg limit, so it's one parcel.
- **If W's limit were 8 kg:** the cat litter would go into a second parcel.

Packing is deliberately simple, and by weight only.

We now have **two shipments**: D (4 kg) and W (9.1 kg).

---

## 6. When does it arrive? (The promise pipeline)

Each shipment goes through the same sequence, starting from *now* in Indian time. Here are the steps, followed by both shipments run through them.

**Step 1: Match the weight slab.** The operations team maintains an SLA table keyed by zone, warehouse and weight range. The shipment's total weight picks the row. That row fixes two things:
- **the delivery type:** one of ten, from hyperlocal through same-day and next-day to standard
- **the base SLA:** in minutes, hours or days

Everything after this depends on the delivery type.

**Step 2: Apply the cutoff.** Each warehouse has cutoff rules per delivery type.

| | Hyperlocal (fast local delivery) | All other delivery types |
|---|---|---|
| Rule | An operating window, e.g. 7 AM–11 PM | A daily cutoff, e.g. 6 PM |
| Missed when | You order outside the window | You order after the cutoff |
| If missed | The promise jumps to a configured later day and time | The start moves to a later day and time, and the SLA counts from there |

If you order before the hyperlocal window opens in the morning, you get the same day's configured slot. If you order after it closes, you get the next day's.

**Step 3: Add operational delays (the SCM team's buffers).** The supply-chain team can add delays scoped to a warehouse, a zone, or one warehouse–zone pair. These can be limited to weight ranges or specific areas and to a date range, for example a festival week. Every delay that applies is added up.

**Step 4: Add rain, but only if the team hasn't already set a delay.** A warehouse with a manually configured delay keeps it. Rain never stacks on top.

**Step 5: Add a capacity delay.** This applies if the warehouse's current time slot is already full for that delivery type (Section 7).

**Step 6: Adjust for product tags.** Tag rules can add time for certain products. They can also subtract it.

**Step 7: Add the base SLA.** The one exception: a hyperlocal promise that was moved by its cutoff doesn't get the SLA on top, because the cutoff already chose the slot.

**Step 8: Skip non-working days.** Two kinds are walked separately.
- **Non-pickup days.** These are days the warehouse can't hand over to couriers. They're checked on a separate *pickup clock*: when the parcel actually leaves, after cutoff and warehouse-level delays.
- **Non-delivery days.** These are checked on the final delivery date.

In both cases, the clock walks forward until it lands on a working day. When a skip moves the date, the time of day resets to the warehouse's configured delivery time.

**Step 9: Set the final time of day.**
- **Non-hyperlocal promises** are end-of-day: the time is set to **10 PM** on the delivery date, which makes them "by 10 PM" promises.
- **Late-night roll-over:** anything landing at **11:30 PM or later**, of any type, rolls to **1 PM the next day**.

**The output.** The result is a delivery time and a day count. It also comes with a customer message, such as "Arriving in 25 mins", "Delivery by Today 10PM" or "Delivery by Sunday, 10PM", plus a breakdown of every rule that contributed.

### Our two shipments through the pipeline

**Shipment from darkstore D (4 kg), ordered at 7:30 PM:**

| Step | What happens | Clock |
|---|---|---|
| 1 Slab | 0–5 kg → hyperlocal, 2 hours | |
| 2 Cutoff | 7:30 PM is inside the 7 AM–11 PM window, so no change | 7:30 PM |
| 4 Rain | It's raining. D has no manual delay, so +30 min applies | |
| 7 SLA | +2 hours | |
| 9 Final | Hyperlocal keeps its exact time; not past 11:30 PM | **10:00 PM today** |

**Shipment from warehouse W (9.1 kg), ordered at 7:30 PM:**

| Step | What happens | Clock |
|---|---|---|
| 1 Slab | 5–15 kg → next-day, 1 day | |
| 2 Cutoff | 7:30 PM is past the 6 PM cutoff, so start = Saturday 9 AM | Sat 9:00 AM |
| 7 SLA | +1 day | Sun 9:00 AM |
| 8 Days | No skip days configured | |
| 9 Final | Not hyperlocal, so the end of that day | **Sunday 10:00 PM** |

**What the shopper sees.** Dog food is split across both shipments, so its promise is the **later** one, Sunday, because you haven't received your dog food until the last part arrives. Cat litter and the sample show Sunday too. The cart also shows the two shipments separately: one tonight, one Sunday.

**A variation.** Suppose W doesn't hand parcels to couriers on Saturdays. The pickup clock lands on Saturday 9 AM, a skip day, and walks to Sunday, which adds a day. Delivery moves to Monday, and the time resets to the warehouse's delivery time, giving "by Monday 9 AM".

### Why the order is fixed

- **Weight first.** It decides the delivery type, and the delivery type decides which cutoff and capacity rules apply.
- **Cutoff before any delay.** It *sets* a clock time. Anything added before it would be wiped out.
- **Hyperlocal cutoffs replace the SLA.** They pick the slot directly, so adding the SLA as well would double-count.
- **Pickup-day skipping on its own clock.** It has to reflect when the parcel leaves the warehouse, not when it reaches the customer.
- **Delivery-day skipping after all additions.** It has to test the final date.
- **The time-of-day rule last.** It overwrites the time.

Getting this order wrong doesn't crash anything. It just produces a plausible-looking wrong date, which is why the order matters so much.

---

## 7. What happens after the order? (The capacity feedback loop)

The shopper places the order. The storefront then asks the engine for the promise one more time, with a flag that says "count this order". It recomputes the shipments and adds one order to the current time slot of each warehouse and delivery type involved. In our example, that's D's hyperlocal slot and W's next-day slot.

**How the counter works.** Each slot has a capacity, for example 200 next-day orders between 6 PM and midnight.

- **Atomic increment.** The count goes up in a single database update, so concurrent orders don't lose counts.
- **Spill.** Once a slot is over capacity, the overflow carries into the next slot, so the next slot starts partly full.
- **The delay.** When *orders plus overflow ≥ capacity*, every new promise for that warehouse and delivery type gets that slot's configured delay.

**Why this matters.** Surges slow the promise down instead of breaking it. Nothing is blocked or rerouted; the dates just get honest.

**The catch.** The engine reads these counters through its 5-minute cache, so a slot that fills up takes up to 5 minutes to start slowing promises. That's a conscious trade: cache hits on most requests, in exchange for a small lag.

---

## 8. The rain story

1. **Watch.** For each hyperlocal warehouse, background jobs poll minute-level precipitation, plus an hourly intensity forecast.
2. **Decide.** A decision step looks at the situation:
   - **Raining now:** look up the delay for this intensity and how long it has been raining, and never lower it mid-rain.
   - **Rain expected soon:** switch the delay on early.
   - **Just stopped:** hold the delay through a cool-down.
   - **Cool-down over:** switch it off.
3. **Approve.** A suggested delay goes to the operations team on Telegram, grouped by city, with an approve link.
   - By default, if nobody responds in 10 minutes, it's applied automatically.
   - Outside working hours, it's applied immediately.
4. **Apply.** The promise engine reads the approved rain delay for each warehouse on every request, fresh, never cached, and adds it as minutes. The response also tells the app whether it's raining, so the UI can explain the delay.

If the weather service goes down, the last known status stays in place, and the team gets an alert after 15 minutes of silence.

---

## 9. Making it fast and keeping it standing

**Caching.** Almost every lookup is cached in Redis for 5 minutes by default:
- the location-to-zone result
- the zones and their warehouses
- stock for a set of items
- the whole bundle of cutoffs, delays, capacity and SLA rules for a set of warehouses

Two things are read fresh on every request: rain status and tag rules.

The cost of this design is staleness. Stock, configuration edits and capacity breaches can each take up to 5 minutes to show.

**If Redis dies.** Every cache read falls back to MySQL. Promises keep flowing, just slower.

**If the configuration can't be loaded.** The cart doesn't fail. It falls back to a promise built from the SLA alone: no cutoffs, no delays. That keeps checkout working, but that promise is *optimistic*, and it gets cached for 5 minutes too. This is the failure mode I'd fix first. I'd rather show a safe, conservative date than a fast one we can't keep.

**Measure latency.** Nothing in the engine tracks latency today. The one cart call we have a measurement for took about 1.4 seconds. The four zone levels are searched one after another, which is the obvious first place to look.

---

## 10. How this differs from 10-minute delivery

This engine is built for an e-commerce promise: hours to days, several warehouses, split parcels. A 10-minute, single-darkstore model changes the priorities. The right-hand column below is reasoning about that model, not a description of any specific company.

| | This engine | 10-minute delivery would need |
|---|---|---|
| Serviceability | A generous four-level fallback. Outside every polygon, the pincode, city or state still serves you. | The polygon *is* the service area. Outside it, there's no service. |
| Sourcing | Several warehouses, split quantities | One darkstore that either has everything or doesn't |
| Stock freshness | ERP pushes + up to 5 minutes of cache; no reservation | Live darkstore stock and a hold at checkout. A 5-minute-old count is half the promise. |
| Capacity | Order counts per time slot add delay after the fact | Live picker and rider availability as an *input* to the promise |
| Time precision | Mostly end-of-day ("by 10 PM") promises that absorb small delays | Every minute counts, and every delay lands in the promise |

**Where the engine already leans that way:**
- Hyperlocal delivery types, with operating windows and minute-level SLAs.
- Messages like "Arriving in 25 mins" for promises under 30 and 60 minutes.
- Rain delays, set up for the hyperlocal warehouses.

---

## 11. What I'd improve

1. **Reserve stock at checkout.** A short-lived hold would stop two shoppers being promised the same last unit.
2. **Fail safe, not optimistic.** When configuration can't load, serve a conservative promise and don't cache it.
3. **Make capacity near-instant.** Read the capacity counters outside the 5-minute cache, since they're the one thing that changes with every order.
4. **Parallelise and measure.** Run the zone levels concurrently, and add latency metrics, since there's no target or dashboard today.
5. **Tighten zones.** Enforce non-overlapping polygons, and check exact boundaries for shoppers near an edge.
