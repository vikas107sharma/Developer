# How the Post-Order System Works — Explained Step by Step

A lesson, not a reference manual. Each part starts with the problem, explains the idea that solves it, and shows a small example. The rules are the system's real rules; **the example numbers are made up**.

It covers two halves of the same system:

- **The write side.** Three webhooks that build and update the order record:
  - order placed
  - warehouse delivery note
  - courier tracking
- **The read side.** Three customer screens that explain that record:
  - order list
  - order details
  - shipment details

Each screen exists as an app route and a web route. They currently run the same code.

---

## Lesson 0 — What problem are we solving?

Placing an order isn't one event. The facts about it arrive over several days, from four different systems:

```
 Day 0   Shopify          "The customer bought these items"
 Day 0   Promise Engine   "Here is how we plan to ship them, and when"
 Day 1   Warehouse (ERP)  "Here is what we actually packed, and from where"
 Day 1+  Courier          "Picked up… in transit… out for delivery… delivered"
```

The system has two jobs:

1. **Write:** keep **one record per order** that is always truthful about what is current, as these facts arrive out of order and sometimes twice.
2. **Read:** turn that record, plus a few other sources, into **one plain sentence** for the customer, such as *"Arriving by Tomorrow 10PM"* or *"Missed delivery on Wed, 4th Sep"*.

```
  Shopify ─┐                                   ┌─► order list
  Promise ─┤                                   │
  Engine   ├─► WRITE ─► one order record ─► READ ├─► order details
  ERP ─────┤          (MongoDB)                │
  Courier ─┘                                   └─► shipment details
```

---

## Lesson 1 — The order record: line items vs. shipments

### The key modelling idea

The order record keeps two lists that look similar but mean different things:

| | Line items | Shipments |
|---|---|---|
| Means | **What the customer bought** | **How it actually travels** |
| Comes from | Shopify | The Promise Engine's plan, later corrected by the warehouse |
| Changes? | Fixed at order time | Changes as the warehouse and courier report back |

**Why keep them separate?** A single item can split across two parcels, and a parcel can carry several items. Mixing the two lists would make both wrong.

### Each shipment has two halves

- **Promise:** the plan. Which warehouse, the delivery type, the promised date, the cutoff, and the delivery-message style.
- **Tracking:** the reality. Delivery note number, waybill, courier, current status, delivery time, rider details and a history of events.

When a shipment is first created, the promise is filled in and the tracking is **empty**, because no courier or waybill exists yet.

### The "tombstone" flag

Plans go stale. The warehouse might pack from a different warehouse than planned, or a delivery note might be cancelled. When that happens, the system **doesn't delete** the old shipment. It marks it **mismatched**, which works like a tombstone: kept in the record, hidden from the customer.

There are two reasons:

1. **History.** You can always see what was originally promised.
2. **Safety.** Later steps of the same process re-read the shipment list and write back by **position in the list**. Deleting an entry would shift every later position, and the next write would land on the wrong parcel.

> **Key idea:** line items say what was bought, shipments say how it travels. A promise is the plan, tracking is reality, and stale plans are tombstoned, never deleted.

---

## Lesson 2 — Order placed: creating the plan

**The trigger:** Shopify notifies the backend that an order was placed.

### Step by step

1. **Drop service items.** Vet consultations and grooming don't ship anything. If nothing shippable remains, stop.
2. **Need a pincode.** If the order has no delivery pincode, stop.
3. **Ask the Promise Engine for the plan.** Send the whole basket (the shopper's location too, if the order carries it). The answer says how the basket splits into shipments, from which warehouse, and each item's promised date.
   - This call only asks for the plan. It doesn't count the order against warehouse capacity.
4. **Archive the raw answer.** The engine's exact reply is saved in a separate promise archive, whether the call **succeeded or failed**. Weeks later, it answers "what exactly did we promise at 2 AM on Tuesday?" without guessing.
5. **Build the shipments** from the plan:
   - promise filled
   - tracking empty
   - each item's quantity grouped into its shipment
6. **Add a placeholder** for any item the plan left out (Lesson 3).
7. **Save** the order record.
8. **Tell the ERP** each item's promised date. This runs in the background, and its failures don't affect the order.

### What if the Promise Engine is down?

The error is archived, and the order is **still saved, with no shipments**, unless a retry already created it. The order is never lost. Until shipments exist, the screens fall back to showing Shopify's line items.

### What if Shopify sends the same webhook twice?

There's no "already processed" check on this route; the old version had one, and the current one has it switched off. So a repeat builds the plan again. But when the order already exists, the newly built shipments are added **already tombstoned**, so the customer never sees them twice.

### Example

A customer buys dog food ×2 and cat litter ×1. The plan says both ship together from warehouse W, arriving Sunday:

```
 line items : dog food ×2, cat litter ×1
 shipments  : [ W — dog food ×2, cat litter ×1
                promise: W, next-day, Sunday 10 PM
                tracking: (empty) ]
```

> **Key idea:** the order-placed step turns Shopify's purchase into a shipping plan. It always saves the order and always keeps a copy of what the engine said.

---

## Lesson 3 — The placeholder: items the plan forgot

### The problem

If the Promise Engine can't plan an item, for example because it's out of stock everywhere, it quietly leaves that item out of the shipment plan. The item is still a line item, and the order total still bills for it. But the app builds its item list **from shipments**, so the item simply vanishes from the screen.

Two real orders showed this: one listed 2 of 3 items, and another charged for 4 items while showing 3.

### The solution: one placeholder shipment

The system keeps **at most one** extra "placeholder" shipment per order. It holds every bought item that no real shipment covers.

| Rule | Why |
|---|---|
| **One per order** | It's recalculated each time, never added again |
| **No promise, no tracking: truly empty, not blank** | A blank-but-present promise makes the screen invent "within 2-3 days". An empty one gives an honest "Arriving soon" |
| **Marked like a tombstone** | Every other part of the system (delivery checks, rewards, tracking tile) ignores it automatically. Only the customer screens deliberately let it through. |
| **Always added at the end of the list** | It must not shift the positions of real shipments |
| **Retired by emptying it, not deleting it** | Same reason: positions stay stable |
| **Skips writing if nothing changed** | It compares a sorted "item:quantity" fingerprint |
| **Not created when no real shipment exists** | The screens already show all line items in that case, so it would duplicate them |

Both the order-placed step and the delivery-note step call it. Because it's idempotent, calling it twice is harmless.

> **Key idea:** the placeholder keeps an unplanned item visible without pretending it has a delivery date. It's added once and retired by emptying.

---

## Lesson 4 — The warehouse packs: reconciling plan vs. reality

### The problem

The plan is a prediction. When the warehouse actually packs, the ERP sends **delivery notes**: what was packed, from which warehouse, in what quantity. Sometimes that matches the plan exactly. Sometimes the warehouse is different, a quantity is off, or a note is cancelled. The record has to end up matching reality, without losing history.

### Before matching

1. **Archive the raw delivery-note message.**
2. **Translate warehouse names** from the ERP's naming to the naming the rest of the system uses.
3. **Refresh the customer-facing note on the Shopify order.** This runs in the background. For each active delivery note, the system asks the Promise Engine for a fresh, warehouse-specific promise and writes "Consignment 1: … arriving …". The **original promise from order time is preserved separately**, and the latest one goes in its own field.
4. **Make sure the order exists.** If the delivery note arrives before the order record, the system rebuilds the order from Shopify through its own order-placed step, waits 2 seconds and reads again. If it's still missing, it fails.

### The matching steps, in order

| Step | What happens |
|---|---|
| 1. Cancelled notes | Any shipment tied to a cancelled delivery note is tombstoned |
| 2. Exact match | A note matches a shipment when **warehouse, items and quantities** are all identical. The note number is attached to that shipment. |
| 3. Second exact pass | Shipments that still have no note get one more exact-match attempt against the notes left over |
| 4. Tombstone leftovers | Any shipment from before this message that matched nothing is tombstoned |
| 5. Unpredicted notes | For a note that matched nothing, ask the Promise Engine for a promise **pinned to that warehouse**, and create new shipment(s) carrying the note number |
| 6. Placeholder | Re-sync the placeholder, which retires it if a real shipment now covers its items |

**A detail worth knowing:** generated shipment ids aren't guaranteed unique once retries have added entries. So when matching, the system finds the shipment by the **database's own unique id**. Otherwise a note could attach to the wrong parcel.

### Example

The plan said warehouse W ships dog food ×2 and cat litter ×1. The warehouse actually packs from **W2**:

```
 delivery note DN1: W2 — dog food ×2, cat litter ×1
 step 2  exact match?  warehouse W ≠ W2 → no
 step 4  plan from W matched nothing → tombstoned (kept, hidden)
 step 5  DN1 matched nothing → ask Promise Engine "from W2?" → new shipment
         [ W2 — dog food ×2, cat litter ×1, promise from W2, note DN1 ]
```

The customer now sees one parcel, from W2, with an honest new date. The original W plan is still in the record.

**One gap to be aware of:** if the warehouse-pinned promise call fails in step 5, the note is still treated as handled and no shipment is created for it.

> **Key idea:** reconcile the plan against what was really packed. Match exactly, tombstone what didn't happen, create what wasn't predicted, and never delete.

---

## Lesson 5 — The courier reports: tracking updates

### The flow

```
 courier update (via Clickpost)
     │
     ▼
 webhook ─► queued on Pub/Sub (absorbs bursts; retried on failure)
     │
     ▼
 consumer:  save the raw event · forward it to ERP
            is this a status we track?  ── no ──► stop
                     │ yes
                     ▼
            update ONE shipment ── the one whose delivery note number matches
```

### What gets updated on that shipment

- **Identity:** waybill and courier details.
- **Current status:** the code, its name, the time, the location and remarks.
- **Delivery:** the delivered time, when the status is "delivered".
- **Rider:** name and phone, when the courier sends them.
- **History:** a new history entry is added at the top, newest first. A failed delivery attempt also records the failure reason.

### Updating just one parcel safely

The database update targets **only the shipment inside the order whose delivery note matches**. Two parcels of the same order can be updated by two courier events at the same time without stepping on each other.

### Avoiding duplicate history

Each history entry gets a key: *waybill + status code + time*. Before adding an entry, the system checks whether that key already exists.

There are two limitations to know:

- **It isn't atomic.** It's "check, then add", so two events processed at the same instant could both pass the check.
- **The time in the key is when the event entered our queue, not the courier's scan time.** So the check mainly protects against the queue re-delivering the same message.

> **Key idea:** every courier event is archived, then applied to exactly one parcel, found by its delivery note, with a history row added newest-first.

---

## Lesson 6 — The read side: three screens, many sources

### The screens

| Screen | What it answers |
|---|---|
| Order list | "What have I ordered?" Shows the customer's orders, newest first, paged |
| Order details | "Tell me everything about this order" (status, parcels, fees, totals) |
| Shipment details | "Where is this one parcel?" (status, rider, cash to pay, returns) |

### Where the facts come from

| Source | What it contributes |
|---|---|
| Shopify | The orders themselves: products, prices, fulfilments, fees, totals, cancellation |
| The order record (MongoDB) | Shipments, promises, tracking status and history, rider details |
| Return requests table | Which items are being returned, their status and refund amounts |
| Revised-EDD table | A delivery date that changed after the original promise |
| COD-to-prepaid table | Orders whose payment switched from cash to prepaid after placing |
| Pharmacy (prescriptions) | Whether prescription items are verified and can be shown |
| Fee titles and tooltips | Display names and help text for fee rows |

### Batching: one query per source, not per order

A page of the order list can have 10 orders. The naive way asks every source once **per order**, which is 10 times each. Instead, the system first collects every order id and waybill on the page, then asks each source **once for the whole page**: the order record, return requests, revised dates and COD conversions.

**The honest exception:** the pharmacy lookup still runs **per order**, so it grows with the page size.

### When something fails

- **List and details:** if building the response fails, the screen retries up to 4 more times, one second apart. After that it returns an error status with an empty but well-formed body, so the app doesn't crash.
- **Soft sources:** most of them fall back to "nothing" (no returns, no revised date, no prescription data, a generic "Fees" title). A soft source that's down loses one detail, not the whole screen.

> **Key idea:** the read side is integration. It gathers facts from several systems, batches them per page, and degrades one field at a time.

---

## Lesson 7 — Turning facts into one sentence

This is the heart of the read side. For each shipment, the status is decided by a ladder in which **later rules override earlier ones**:

```
 1. Not yet with a courier
      no promised date or no waybill  ─► "Order Placed"
      promised within 6 hours         ─► "Packing Items"
 2. Courier status code               ─► customer label (separate table for quick-commerce)
      quick-commerce codes 12/13/14 (returning to origin) ─► shown as "Delivery failed"
 3. Shopify says cancelled            ─► "Cancelled"
    Delivery time recorded            ─► "Delivered"
 4. A revised delivery date exists    ─► "running delayed", with the new date
 5. Delivered                         ─► early / late; quick-commerce: "Delivered in 18 minutes"
 6. Delivery failed                   ─► "Missed delivery"; if rescheduled, the new date and address
```

**Then one sentence is built from the result:**

| Situation | Sentence |
|---|---|
| Delivered | "Delivered on Tue, 3rd Sep" |
| Missed delivery | "Missed delivery on Wed, 4th Sep" |
| Cancelled / returns | "Cancelled on …", "Refunded on …" |
| Revised date | "Arriving by Tomorrow 10PM ⚡️" |
| Normal, from the promise's message style | "Arriving in 25 mins ⚡️" · "Arriving by Today, 1PM" · "Arriving by Wed, 27th Nov, 10PM" |
| Nothing reliable to say | "Arriving soon ⚡️" |

**Why the remap?** For quick commerce, the courier has several "returning to origin" codes. To the customer they all mean one thing: the delivery didn't happen. So they're shown as one status.

**The rider block.** When a parcel is out for delivery or has reached the customer's location, the screen also shows the rider's name and phone number, with lines like *"I'm Ravi, I'm bringing your items safely to your doorstep"*. If the parcel is delayed, the second line becomes *"Your order is delayed. It will arrive later than expected."*

> **Key idea:** a ladder of rules collapses courier codes, cancellations, revised dates and failures into one status, then one human sentence.

---

## Lesson 8 — Returns on the screen

When an item is being returned, the screen has to show **two things**: less of it in the original parcel, and a new "return" entry with its own status.

1. **Reduce the original quantity.** In the forward parcel, the item's quantity is reduced by the returned quantity. Lines that reach zero, and parcels left empty, are hidden.
2. **Add a return entry** per return request, with:
   - its status, such as "Return item picked up" or "Refunded", plus the date
   - the refunded amount
   - the original parcel's waybill

**The double-counting trap.** When Shopify splits an order across fulfilments, it can list the same item in more than one fulfilment. If the system built a return entry every time it saw the item, one return would appear twice, with double the refund. So a return entry is built **once per (return request, item)** pair, tracked in a set. The quantity reduction is applied to every fulfilment that lists the item.

**Return window.** An item can be returned for **10 days from its delivery time**.

> **Key idea:** a return reduces what's shown in the original parcel and adds one return entry per request, built once even when Shopify repeats the item.

---

## Lesson 9 — Prescription (pharmacy) items

Some items need a vet to verify a prescription before they ship.

- **Until the prescription is released**, and while the order is neither delivered nor cancelled, those items are **removed from the normal parcels**. They're shown instead as a separate **"verification" shipment**.
- **Its status** is Pending, Attempted or Verified, with a vet message such as *"Vet will call in 30 mins to verify your order"*. After several missed calls it becomes *"We made a call to connect with you, but couldn't reach you."*
- **Once released, delivered or cancelled**, the items appear in their normal parcels.

> **Key idea:** the customer never sees a delivery date for an item that might not be allowed to ship yet.

---

## Lesson 10 — Money: fees and cash on delivery

### Fee rows (order details)

- **Web orders:** three fixed rows (COD fee, delivery fee, platform fee) from the order's fee lines.
- **App orders:** depends on the app version.
  - Newer app versions send a rollout marker. They get one row per fee line, with its display title and tooltip.
  - Older versions get the fixed three rows.
  - The amounts always come from the order itself. The marker only changes how the rows are labelled.

### Splitting cash on delivery across parcels

**The problem:** a COD order split into two parcels is collected by two delivery agents. Each agent must collect the right part, and the parts must add up **exactly** to the order total.

**The method:**

- **Fixed denominator.** Each parcel's share is its items' value divided by the **whole order's** item value, counting items that haven't shipped yet. That way a parcel's amount doesn't change when another parcel appears later.
- **Two figures computed, the third derived.** The cash to collect and the fee portion are computed from the share. The item portion is cash minus fee. If all three were rounded separately, "items + fee = cash" could break by a rupee.
- **Whole rupees.** Once every item is shipped, the last parcel takes the leftover rounding, so the parcels sum exactly to the order total.

**Example.** A ₹900 item and a ₹100 item ship separately, with a ₹50 fee, so the order total is ₹1,050.

```
 parcel A (₹900 of ₹1,000 → 90%):  cash 945 = items 900 + fee 45
 parcel B (last, takes the rest):   cash 105 = items 100 + fee  5
 total collected: 1,050 ✓
```

The screen shows *"Pay ₹945 in cash for this delivery"*.

> **Key idea:** split COD by each parcel's share of the whole order, derive one figure from the other two, and let the last parcel absorb rounding.

---

## Lesson 11 — Can this order still be cancelled?

An order is cancellable only if **none** of these blockers is true:

- Shopify already has any fulfilment for it.
- Any parcel is quick-commerce (hyperlocal).
- Any parcel already has a courier status.
- It contains service items, such as a consultation.
- It's already cancelled.

The shipment-details screen computes its own version of the same idea for the parcel being viewed.

> **Key idea:** cancellation is blocked as soon as anything has physically started moving, or the order is fast delivery.

---

## Recap — the whole system on one page

```
 WRITE
  order placed    ─► ask Promise Engine for the plan · archive its answer · save
                     line items + shipments (promise filled, tracking empty)
                     · placeholder for unplanned items
  delivery notes  ─► archive · translate warehouse names · ensure order exists
                     · tombstone cancelled · exact match · tombstone leftovers
                     · create shipments for unpredicted notes · re-sync placeholder
  courier events  ─► queue · archive · update ONE shipment by its delivery note
                     · history newest-first, de-duplicated by key

 READ
  list · details · shipment
     ─► Shopify + order record + returns + revised dates + COD conversions
        + pharmacy + fee titles (batched per page; pharmacy per order)
     ─► status ladder ─► one sentence · returns · Rx shipment · fees
        · COD split · cancellable
```

**Five things to remember:**

1. Line items are what was bought; shipments are how it travels.
2. Stale plans are tombstoned, never deleted, because history and list positions both matter.
3. The placeholder keeps unplanned items visible without inventing a date.
4. Each courier event updates exactly one parcel, found by its delivery note.
5. The read side batches every source except pharmacy per page, and turns everything into one sentence.

---

## Check your understanding — questions an interviewer might ask

**Why separate line items from shipments?**
Because they answer different questions. What was bought never changes. How it ships changes as the warehouse and courier report back, and one item can split across parcels.

**Why tombstone instead of delete?**
To keep the history of what was promised. Also, later steps re-read the list and write back by position, so a deletion would shift positions and corrupt the next write.

**What happens if the Promise Engine is down when an order is placed?**
The error is archived, and the order is still saved without shipments, so it's never lost. The screens fall back to Shopify's line items.

**What if the warehouse packs from a different warehouse than planned?**
The exact match fails, so the old plan is tombstoned. A new shipment is created with a fresh promise pinned to the warehouse that actually packed.

**How do two courier updates for the same order not clash?**
Each update targets only the parcel whose delivery note matches, so two parcels can be updated at the same time.

**How do you avoid the N+1 problem on the order list?**
Collect every order id and waybill on the page first, then query each source once for the whole page. Pharmacy is the exception; it's still looked up per order, and it's the next thing to batch.

**How does COD split across parcels and still add up?**
Each parcel's share is based on the whole order's value. Cash and fee are computed from that share, and the item portion is derived from them. The last parcel absorbs the rounding.

**What would you improve?**
1. **Duplicate webhooks.** Turn the "already processed" check back on for the order-placed webhook.
2. **Tracking history.** Make the history de-duplication a single atomic operation, and key it on the courier's own scan time.
3. **Pharmacy.** Batch the pharmacy lookup per page.
4. **Unpredicted notes.** When the warehouse-pinned promise fails for an unpredicted delivery note, retry it or flag it, rather than marking the note handled with no shipment.
5. **Self-heal.** Replace the fixed 2-second wait with a proper wait-until-present.
6. **Access control.** Verify that the caller actually owns the customer or order on the read screens.
