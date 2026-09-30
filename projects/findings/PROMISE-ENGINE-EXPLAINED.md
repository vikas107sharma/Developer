# How the Delivery Promise Engine Works: Explained Step by Step

This is a lesson, not a reference manual. Each part starts with the problem, explains the idea that solves it, and shows a small example. The rules are the engine's real rules; **the example numbers are made up**.

---

## Lesson 0: What question are we answering?

When a shopper looks at a product or a cart, the site shows something like *"Delivery by Sunday, 10 PM"*. Behind that one line are three separate questions:

1. **Where** will each item ship from?
2. **How** will the order be split into parcels?
3. **When** will each parcel arrive?

They have to be answered in that order. You can't date a parcel until you know which warehouse it leaves from and how heavy it is. So the engine is a pipeline:

```
 shopper's location + cart
        │
        ▼
 ① find the delivery zones for this location          (Lesson 1)
        │
        ▼
 ② pick warehouses that have the stock                  (Lesson 2)
        │
        ▼
 ③ pack the items into parcels                          (Lesson 3)
        │
        ▼
 ④ compute a delivery time for each parcel              (Lesson 4)
        │
        ▼
 promise shown to the shopper
        │  (after the order is placed)
        ▼
 ⑤ count the order, which can slow later promises       (Lesson 5)
```

Keep this picture in mind. Every lesson below is one box.

---

## Lesson 1: From a location to a delivery zone

### The idea of a zone

The engine never asks "can warehouse X deliver to this address?" directly. Instead, the operations team defines **zones**. Each zone lists which warehouses serve it, in priority order.

A zone can be one of four kinds:

| Zone type | Defined by | How local |
|---|---|---|
| Polygon | A shape drawn on the map | Most local |
| Pincode | A list of pincodes | |
| City | A city | |
| State | A state | Least local |

For every zone–warehouse pair, the team also sets delivery terms by parcel weight. For example: *"from this warehouse to this zone, parcels of 0–5 kg go hyperlocal in 2 hours"*. We'll use those terms in Lesson 4.

### The problem: testing a point against polygons is expensive

The natural way to check whether a shopper's location lies inside a delivery polygon is a geometry test, point-in-polygon. Doing that on every request, against many polygons, is slow work repeated millions of times.

### The solution: do the geometry once, in advance, with H3

H3 divides the whole map into a grid of hexagons. At the size this engine uses, resolution 10, each hexagon is a little over 100 metres across.

- **When a polygon is saved:** the engine works out which hexagons fall inside it (a hexagon counts if its centre is inside) and stores that list.
- **When a shopper arrives:** the engine turns the shopper's latitude/longitude into its one hexagon, then simply looks that hexagon up. No geometry happens at request time. It's a single indexed lookup.

```
 save time:     polygon ──► list of hexagons inside it ──► stored
 request time:  lat/lng ──► its hexagon ──► lookup ──► polygons ──► zones
```

**Analogy:** instead of measuring whether a coin lies inside a drawn shape every time, you shade the squares of graph paper once. Then you just ask "is the coin's square shaded?"

**The trade-off:** the polygon's edge becomes slightly "pixelated". A shopper right on the boundary can fall on either side, depending on their hexagon. For delivery zones that's acceptable, and in return every request gets fast, simple lookups. When the team edits a polygon, its hexagons are rebuilt.

### Falling back when the location doesn't help

Not every shopper shares a location, and not every location falls inside a polygon. So the engine searches from most local to least local:

```
 polygon zones ──► pincode zones ──► city zones ──► state zones ──► out of stock
```

Two rules make this work:

- **Only what's still missing moves on.** If the polygon level finds stock for two of three items, only the third item goes to the pincode level.
- **The pincode is always known.** City and state come from the pincode, so the chain works even without a location.

> **Key idea:** zones turn "can this warehouse deliver here?" into a lookup. H3 makes the most local lookup cheap, and the fallback chain makes sure every shopper gets an answer.

---

## Lesson 2: Choosing which warehouse's stock to use

### Where stock data comes from

The ERP (the company's inventory system of record) owns the true stock numbers. The engine keeps its own copy: for every item, a quantity per warehouse. Two things keep that copy updated:

- **Pushed changes.** Whenever stock changes, the ERP pushes the change. It goes onto a queue and is applied one message at a time.
- **Snapshots.** Scheduled full snapshots re-sync everything.

Two small details:

- **Promo variants share stock.** Promotional versions of an item (a "sale" or "free gift" variant of the same product) are mapped back to the base item, so they share its stock.
- **Bundles are computed in advance.** A bundle's stock is how many complete bundles its scarcest component allows.

### The search order

At each level from Lesson 1, the engine visits zones, and within each zone, warehouses by priority. It takes what it can from each warehouse until the item's quantity is covered.

### The problem: the same warehouse can appear twice

Zones overlap. A darkstore might be listed in a polygon zone *and* in the pincode zone around it. When the search reaches the pincode level, it would see that darkstore again. If it only looked at the stock table, it would promise the same units a second time.

### The solution: a ledger for the request

While answering one request, the engine keeps a small ledger: *"units of item X already promised from warehouse Y"*. Every time it considers a warehouse, it uses:

```
 available = stock on hand − already promised in this request
 take      = the smaller of (available, still needed)
```

**Example.** An item needs 2 units. Darkstore D has 1 unit and belongs to both a polygon zone and the pincode zone. Warehouse W, in the pincode zone, has plenty.

```
 polygon level : D   available = 1 − 0 = 1   → take 1    still needed 1
 pincode level : D   available = 1 − 1 = 0   → skip      (the ledger prevents double-counting)
                 W   available = plenty      → take 1    still needed 0  ✓
```

### All-or-nothing

If, after all four levels, an item still isn't fully covered, the engine marks the **whole item** out of stock and drops the partial units. It never promises 2 units when you asked for 3. A partial promise would be misleading.

### What the ledger does *not* do

The ledger lives only for one request. It doesn't reserve anything. Two shoppers checking out at the same moment can both be promised the last unit. The numbers correct themselves when the ERP pushes the sale back. That's a real limitation, and the first thing to add would be a short hold at checkout.

### Product page vs. cart

The product page is about one item and needs a quick answer, so it uses a simpler rule. There is no splitting: the first warehouse, in the same search order, that can supply the **full** quantity wins. The cart uses the splitting-with-ledger approach above.

> **Key idea:** search nearest-first, take stock warehouse by warehouse, and use a per-request ledger so overlapping zones never count the same stock twice.

---

## Lesson 3: Packing items into parcels

Once the engine knows which warehouse supplies which units, it forms parcels.

1. **Group by warehouse.** Units from different warehouses always travel separately.
2. **Respect the weight limit.** Each warehouse has a maximum parcel weight. Within a group, items are sorted lightest first and added **one unit at a time**. The moment the next unit would push the parcel over the limit, that parcel is closed and a new one begins.

**Example.** A warehouse's limit is 8 kg. The items are a 0.1 kg sample, a 4 kg bag of dog food and a 5 kg bag of cat litter.

```
 0.1 kg → parcel 1 (0.1)
 4 kg   → parcel 1 (4.1)
 5 kg   → 4.1 + 5 = 9.1 > 8 → close parcel 1, start parcel 2 (5)
 result: parcel 1 = sample + dog food, parcel 2 = cat litter
```

**Why one unit at a time?** A single item with a large quantity can then be split across two parcels, instead of being rejected as "too heavy".

**Free gifts and samples.** These are placed *after* the main items. If a warehouse that already ships a main item also has the gift, the gift joins that parcel. A free sample should never create an extra shipment.

Packing is by **weight only**. There is no volume or dimension rule.

> **Key idea:** parcels = warehouse groups, cut by a weight limit, with free items riding along.

---

## Lesson 4: Turning "now" into a delivery time

This is the heart of the engine. Every parcel goes through the same sequence of rules. First, one concept makes the whole sequence easy to understand.

### The key concept: "add time" vs. "set the clock"

Every rule does one of two things to the delivery clock:

- **Add time.** "+2 hours", "+1 day", "+30 minutes". Additions can happen in any order; the total is the same.
- **Set the clock.** "Make it tomorrow at 9 AM", "make it 10 PM". This throws away the previous time of day.

**The order of the pipeline exists because of the "set" rules.** Anything added *before* a "set" rule would be wiped out. So the "set" rules sit at fixed points, and the "add" rules fall in between.

### The rules, one by one

**Rule 1: Look up the delivery terms by weight.**
The parcel's total weight picks a row from the zone–warehouse terms (Lesson 1). That row gives two things:

- **The delivery type.** There are ten, grouped into families: hyperlocal (very fast local delivery), same-day, next-day and standard.
- **The base delivery time (SLA).** For example, 2 hours or 1 day.

Everything else depends on the delivery type, so this comes first.

**Rule 2: The cutoff (a "set" rule).**
Warehouses stop accepting work for a delivery type at certain times.

| | Hyperlocal | Other delivery types |
|---|---|---|
| The rule | An operating window, e.g. 7 AM–11 PM | A daily cutoff, e.g. 6 PM |
| When it applies | You order outside the window | You order after the cutoff |
| What it does | Sets the promise to a configured later slot, e.g. tomorrow 10 AM | Sets the *start* to a later day and time, e.g. tomorrow 9 AM. The SLA then counts from there. |

Two details:
- A hyperlocal order placed *before* the window opens gets the **same** day's slot. One placed after it closes gets the **next** day's.
- When a hyperlocal cutoff has already chosen the slot, the SLA is not added on top. That would double-count.

**Rule 3: Delays (all "add" rules).** Four kinds of delay can apply.

| Delay | Who sets it | When it applies |
|---|---|---|
| Operational | The supply-chain team | Configured per warehouse, per zone or per pair, optionally only for some weights, areas or dates (e.g. a festival week). All that apply are added up. |
| Rain | Weather jobs, approved by the team (Lesson 6) | When it's raining at the warehouse. **Only if the warehouse has no operational delay configured.** The two never stack. |
| Capacity | Order counters (Lesson 5) | When the warehouse's current time slot is already full for that delivery type |
| Product tag | The team, per tag | When the item carries that tag. Can add time, and can even subtract it. |

**Rule 4: Add the SLA** (an "add" rule), unless a hyperlocal cutoff already chose the slot.

**Rule 5: Skip non-working days.** A "walk forward" rule, explained in the next section.

**Rule 6: The final time of day (a "set" rule).**
- Non-hyperlocal promises are set to **10 PM** on the delivery day. They are "by end of day" promises.
- Anything landing at **11:30 PM or later**, of any type, moves to **1 PM the next day**.
- Hyperlocal promises keep their exact time.

### Non-working days: why there are two clocks

Two different kinds of day can be blocked:

- **Non-pickup days.** The warehouse can't hand parcels to couriers, e.g. a warehouse holiday. What matters is **when the parcel leaves**.
- **Non-delivery days.** Deliveries don't happen in that zone. What matters is **when the parcel arrives**.

So the engine keeps two clocks.

- **The pickup clock.** It tracks when the parcel leaves: now, plus the cutoff shift, plus warehouse-level delays and capacity delays. Zone-level delays, tag delays and the SLA don't go on this clock.
- **The delivery clock.** It tracks when the parcel arrives: the full result of all the rules.

For each clock, the engine "walks forward" one step at a time while the clock sits on a blocked day. If the pickup walk had to move, the extra days are added to the delivery.

When a walk moves the date, the time of day is re-set to the warehouse's configured delivery time. Otherwise it would keep a meaningless time from before the skip.

### Why the order is what it is (the rule behind it)

| Step | Why it's here |
|---|---|
| Weight lookup first | It decides the delivery type, which every later rule depends on |
| Cutoff next | It *sets* the start time, so it must come before any additions |
| Delays and SLA | Just additions; their order among themselves doesn't matter |
| Pickup walk on its own clock | It must reflect when the parcel leaves, not when it arrives |
| Delivery walk after all additions | It must look at the final date |
| Final time-of-day rule last | It *sets* the time, so anything after it would be overwritten |

Getting the order wrong doesn't crash anything. You just get a believable but wrong date. That's why the order is fixed.

### Two worked examples (ordered Friday, 7:30 PM)

**A. A 4 kg parcel from a nearby darkstore.** Terms: hyperlocal, 2 hours; window 7 AM–11 PM; it's raining (+30 min).

```
 weight lookup   → hyperlocal, 2 hours
 cutoff          → 7:30 PM is inside the window, nothing changes
 delays          → rain +30 min
 SLA             → +2 hours                         = 10:00 PM
 final rule      → hyperlocal keeps its exact time; not past 11:30 PM
 promise         → "Delivery by Today 10PM"
```

**B. A 9 kg parcel from a bigger warehouse.** Terms: next-day, 1 day; daily cutoff 6 PM, which moves the start to the next day at 9 AM.

```
 weight lookup   → next-day, 1 day
 cutoff          → 7:30 PM is after 6 PM → start = Saturday 9 AM   (set)
 SLA             → +1 day                            = Sunday 9 AM
 non-working days→ none
 final rule      → not hyperlocal → Sunday 10 PM                    (set)
 promise         → "Delivery by Sunday, 10PM"
```

**If B's warehouse had Saturday as a non-pickup day:** the pickup clock would land on Saturday 9 AM (blocked) and walk to Sunday. That adds a day, so delivery moves to Monday, and the time is re-set to the warehouse's delivery time, e.g. Monday 9 AM.

**When one item is split across A and B:** the item's promise is the **later** one, Sunday, because the shopper hasn't received it until the last part arrives. The cart still shows the two parcels separately.

> **Key idea:** think of the pipeline as "add" rules sitting between a few "set" rules. The "set" rules (cutoff, day-skip re-anchor, final time of day) fix the order; everything else is just adding time.

---

## Lesson 5: How placed orders slow down future promises (capacity)

### The problem

A warehouse can only handle so many orders in a time slot. If every shopper is promised the same fast date, the warehouse falls behind and the promises become false.

### The solution: count orders per slot, and add delay when a slot is full

The team defines time slots per warehouse and delivery type, each with a capacity. For example: *"next-day orders, 6 PM to midnight, capacity 200"*.

1. **Count the order.** When an order is placed, the storefront asks the engine for the promise one last time, with an instruction to **count this order**. The engine adds one to the current slot of each warehouse and delivery type the order uses. The increment is a single database update, so simultaneous orders don't lose counts.
2. **Carry the overflow.** If a slot goes over capacity, the overflow carries into the next slot, so the next slot starts partly full.
3. **Apply the delay.** When a slot's orders plus the overflow carried in reach its capacity, every new promise for that warehouse and delivery type gets that slot's configured delay.

```
 order placed ──► count +1 in current slot ──► slot full?
                                                  │ yes
                                                  ▼
                       next shoppers get the slot's extra delay
```

**What this does and doesn't do:** it doesn't block orders or send them elsewhere. It makes the promise honest by moving the date out.

**One nuance to be aware of:** the engine reads these counters through its 5-minute cache (Lesson 7). So a slot that fills up can take a few minutes to start slowing promises. It's a trade-off between speed and freshness.

> **Key idea:** a feedback loop. Orders placed now make the promises for the next shoppers more realistic.

---

## Lesson 6: Rain

### The problem

Rain slows last-mile delivery, especially for fast local delivery. But the delay should follow the actual weather, not a guess.

### The solution: watch, decide, get approval, apply

1. **Watch.** For each hyperlocal warehouse, background jobs regularly check minute-level precipitation and an hourly intensity forecast.
2. **Decide.**
   - **Raining now:** pick a delay from a table, based on the rain's intensity and how long it has lasted. Never lower it while it's still raining.
   - **Rain expected soon:** switch the delay on early.
   - **Just stopped:** keep the delay for a cool-down period.
   - **Cool-down over:** switch it off.
3. **Approve.** The suggested delay is sent to the operations team on Telegram, grouped by city, with an approve link.
   - By default, if nobody answers within 10 minutes, it's applied automatically.
   - Outside working hours, it's applied straight away.
4. **Apply.** On every request, the engine reads the current rain delay for the warehouse, fresh (not cached), and adds it as minutes. The response also says whether it's raining, so the app can explain the delay.

**The precedence rule:** if the supply-chain team has already configured an operational delay for that warehouse, rain is not added on top. Manual decisions win, and the two never stack.

**If the weather service fails:** the last known status stays in place, and the team is alerted after 15 minutes without an update.

> **Key idea:** weather feeds a delay through a human-approved loop, and a manual delay always takes precedence over the automatic one.

---

## Lesson 7: Making it fast, and keeping it working when things break

### Caching: fast, but slightly stale

Most of what the engine looks up changes slowly, so it's cached in Redis for about 5 minutes:

- the location → zone result
- each zone's warehouses
- stock for a set of items
- the bundle of cutoffs, delays, capacity and delivery terms for a set of warehouses

Two things are read fresh every time: the **rain status** and the **tag rules**.

**The price of caching is staleness.** A stock change, an edit in the admin console or a full capacity slot can each take up to about 5 minutes to affect promises.

### When things break: open or closed?

A useful way to think about failures: when a dependency breaks, does the system **keep answering** (fail open) or **stop answering** (fail closed)?

| What breaks | What the engine does | Open or closed |
|---|---|---|
| The Redis cache | Goes straight to the database. Slower, but correct. | Open |
| The capacity counter update | Logs the error; the shopper's response is unaffected | Open |
| The weather service | Keeps the last known rain status | Open (stale) |
| Loading the cutoffs and delays, in the cart | Answers using only the base SLA, with no cutoffs or delays, and caches that answer | Open, but **optimistic** |
| Reading the rain status or the tag rules | The request fails | Closed |

The row to remember is the fourth one. When the rules can't load, the cart still shows a date, but that date is **too early**, and it's cached for a few minutes. A too-early promise looks perfectly normal to the shopper, which makes it the riskiest failure. The fix would be to fall back to a *conservative* date and not cache it.

**On speed:** nothing in the engine measures latency today. The one cart call measured took about 1.4 seconds. The four zone levels are searched one after another, which is the obvious first place to look.

> **Key idea:** caching buys speed at the cost of a few minutes of staleness. Deciding what fails open and what fails closed is a design choice, and "open but optimistic" is the dangerous kind.

---

## Lesson 8: How this compares with 10-minute delivery

This engine makes e-commerce promises: hours to days, several warehouses, possibly split parcels. A 10-minute, single-darkstore model has different needs. The right-hand column is reasoning about that model, not a description of any specific company.

| Topic | This engine | What 10-minute delivery would need |
|---|---|---|
| Service area | Generous fallback: outside every polygon, the pincode, city or state still serves you | The polygon *is* the service area; outside it, no service |
| Sourcing | Several warehouses, split quantities | One darkstore that has everything or doesn't |
| Stock freshness | Pushed updates plus up to 5 minutes of cache; no reservation | Live stock and a hold at checkout. Five minutes is half the promise. |
| Capacity | Order counts per slot add delay after the fact | Live picker and rider availability as an input to the promise |
| Precision | Mostly "by 10 PM" promises that absorb small delays | Every minute lands directly in the promise |

The engine already has quick-commerce elements:
- hyperlocal delivery types, with operating windows and minute-level delivery times
- "Arriving in 25 mins"-style messages for promises under 30 or 60 minutes
- rain delays for the hyperlocal warehouses

---

## Recap: the whole engine on one page

```
 ① WHERE     location → H3 hexagon → polygon zones; fallback to pincode → city → state
 ② STOCK     nearest-first, by priority; per-request ledger stops double counting;
             all-or-nothing per item
 ③ PARCELS   group by warehouse; cut by weight limit, one unit at a time; free items ride along
 ④ WHEN      weight → delivery type + SLA
             cutoff (set) → delays: operational or rain, capacity, tags (add) → SLA (add)
             → skip non-working days on two clocks → final time of day (set)
 ⑤ FEEDBACK  placed orders fill capacity slots; full slots add delay for the next shoppers
 CACHE       ~5-minute caching everywhere except rain status and tag rules
```

**Five things to remember:**
1. Zones plus H3 turn serviceability into a lookup.
2. The ledger prevents double-counting inside one request, but nothing reserves stock across requests.
3. Parcels are cut by weight, one unit at a time.
4. The pipeline's order comes from its "set the clock" rules.
5. Capacity is a feedback loop, and it lags by the cache time.

---

## Check your understanding: questions an interviewer might ask

**Why not test the point against the polygon directly?**
Because it's geometry work on every request. With H3, the geometry is done once when the polygon is saved, and each request becomes a single lookup. The cost is a slightly pixelated boundary.

**How do you avoid promising the same stock twice?**
Within a request, a ledger subtracts what's already been promised from each warehouse, so overlapping zones can't double-count. Across concurrent requests, nothing reserves stock today. A short hold at checkout would be the next step.

**Why does the order of the rules matter if most of them just add time?**
Because a few rules *set* the clock (the cutoff, the day-skip re-anchor, the final time of day). Anything added before a "set" is lost, so those rules fix the order.

**How do rain and manual delays interact?**
A manual operational delay takes precedence, and rain is only added when there isn't one. They never stack.

**What happens during a surge?**
Orders fill per-slot capacity counters. Once a slot is full, new promises get that slot's delay. Overflow carries into the next slot. Nothing is blocked; the dates just move out.

**What's the riskiest failure?**
When the delivery rules can't load, the cart shows an SLA-only date that is too early, and caches it. I'd make that fallback conservative instead.

**What would you improve first?**
1. A stock hold at checkout.
2. A conservative fallback when the rules can't load.
3. Reading the capacity counters without the 5-minute cache.
4. Searching the zone levels in parallel, and adding latency metrics.
