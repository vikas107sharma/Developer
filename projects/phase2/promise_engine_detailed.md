<!-- ➕ added:start -->

# Delivery Promise Engine

> Formatted from `promise_engine` (the original notes file, left untouched). Every original line is kept word for word. Blocks labelled **➕ Added diagram** are new.

## Contents

- [1. First understand the actual problem](#1-first-understand-the-actual-problem)
- [2. Lesson 1 — Finding where the customer can be served](#2-lesson-1--finding-where-the-customer-can-be-served)
- [3. Why H3 exists](#3-why-h3-exists)
- [4. Polygon preprocessing](#4-polygon-preprocessing)
- [5. H3 trade-off](#5-h3-trade-off)
- [6. Why fallback exists](#6-why-fallback-exists)
- [7. Lesson 2 — Finding inventory](#7-lesson-2--finding-inventory)
- [8. Why the inventory ledger is necessary](#8-why-the-inventory-ledger-is-necessary)
- [9. The per-request ledger](#9-the-per-request-ledger)
- [10. Very important: this is NOT a reservation](#10-very-important-this-is-not-a-reservation)
- [11. All-or-nothing inventory](#11-all-or-nothing-inventory)
- [12. Product page vs cart](#12-product-page-vs-cart)
- [13. Lesson 3 — Creating parcels](#13-lesson-3--creating-parcels)
- [14. Parcel weight limits](#14-parcel-weight-limits)
- [16. Free gifts](#16-free-gifts)
- [17. Lesson 4 — Calculating delivery time](#17-lesson-4--calculating-delivery-time)
- [18. The most important concept: ADD vs SET](#18-the-most-important-concept-add-vs-set)
- [20. Rule 1 — Weight determines delivery type](#20-rule-1--weight-determines-delivery-type)
- [21. Rule 2 — Cutoff](#21-rule-2--cutoff)
- [22. Hyperlocal is different](#22-hyperlocal-is-different)
- [23. Why hyperlocal cutoff doesn't add SLA twice](#23-why-hyperlocal-cutoff-doesnt-add-sla-twice)
- [24. Rule 3 — Delays](#24-rule-3--delays)
- [25. Rain delay](#25-rain-delay)
- [26. Capacity delay](#26-capacity-delay)
- [27. Product tag delay](#27-product-tag-delay)
- [28. Rule 4 — Add SLA](#28-rule-4--add-sla)
- [29. Two clocks — extremely important](#29-two-clocks--extremely-important)
- [30. Pickup clock](#30-pickup-clock)
- [31. Delivery clock](#31-delivery-clock)
- [32. Non-pickup day example](#32-non-pickup-day-example)
- [33. Why reset the time after a day skip?](#33-why-reset-the-time-after-a-day-skip)
- [34. Rule 6 — Final time of day](#34-rule-6--final-time-of-day)
- [35. The 11:30 PM rule](#35-the-1130-pm-rule)
- [36. Complete delivery calculation example](#36-complete-delivery-calculation-example)
- [37. Now add a warehouse holiday](#37-now-add-a-warehouse-holiday)
- [➕ The 8-stage buffer pipeline (what the resume means)](#the-8-stage-buffer-pipeline-what-the-resume-means)
- [38. What if the item comes from two warehouses?](#38-what-if-the-item-comes-from-two-warehouses)
- [39. Lesson 5 — Capacity feedback loop](#39-lesson-5--capacity-feedback-loop)
- [40. Why the counter update must be atomic](#40-why-the-counter-update-must-be-atomic)
- [41. Overflow](#41-overflow)
- [42. The cache creates an important problem](#42-the-cache-creates-an-important-problem)
- [43. Lesson 6 — Rain](#43-lesson-6--rain)
- [44. Why don't we just directly use weather API on every request?](#44-why-dont-we-just-directly-use-weather-api-on-every-request)
- [45. Human approval loop](#45-human-approval-loop)
- [46. Manual delay beats rain](#46-manual-delay-beats-rain)
- [47. Lesson 7 — Caching architecture](#47-lesson-7--caching-architecture)
- [48. Why not cache everything?](#48-why-not-cache-everything)
- [49. Failure modes](#49-failure-modes)
- [50. Redis failure](#50-redis-failure)
- [51. Capacity update failure](#51-capacity-update-failure)
- [52. Weather service failure](#52-weather-service-failure)
- [53. Most dangerous failure: rules unavailable](#53-most-dangerous-failure-rules-unavailable)
- [54. Better failure strategy](#54-better-failure-strategy)
- [55. Why rain/tag failures are closed](#55-why-raintag-failures-are-closed)
- [56. Lesson 8 — Why this differs from 10-minute delivery](#56-lesson-8--why-this-differs-from-10-minute-delivery)
- [57. Traditional model vs quick-commerce model](#57-traditional-model-vs-quick-commerce-model)
- [58. Now combine everything into one example](#58-now-combine-everything-into-one-example)
- [59. Step 3 — Parcelization](#59-step-3--parcelization)
- [60. Step 4 — Delivery calculation](#60-step-4--delivery-calculation)
- [61. What does the customer see?](#61-what-does-the-customer-see)
- [62. After order placement](#62-after-order-placement)
- [63. The complete mental model](#63-the-complete-mental-model)
- [64. The most important backend concepts hidden inside this design](#64-the-most-important-backend-concepts-hidden-inside-this-design)
- [65. One final diagram to memorize](#65-one-final-diagram-to-memorize)

<!-- ➕ added:end -->

This document describes a Delivery Promise Engine: a backend system that answers:

> “Given this customer's location and cart, which warehouses will fulfill the order, how will we split it into parcels, and when will each parcel arrive?”

The easiest way to understand it is as a pipeline:

```text
                    CUSTOMER REQUEST
                          │
             Location + SKUs + quantities
                          │
                          ▼
              ┌─────────────────────┐
              │ 1. SERVICEABILITY   │
              │ Where can we ship?  │
              └──────────┬──────────┘
                         │
                         ▼
              ┌─────────────────────┐
              │ 2. INVENTORY        │
              │ Which warehouse?    │
              └──────────┬──────────┘
                         │
                         ▼
              ┌─────────────────────┐
              │ 3. PACKING          │
              │ How many parcels?   │
              └──────────┬──────────┘
                         │
                         ▼
              ┌─────────────────────┐
              │ 4. PROMISE          │
              │ When will it arrive?│
              └──────────┬──────────┘
                         │
                         ▼
                 DELIVERY PROMISE
                  "Sunday, 10 PM"
                         │
                         │ order placed
                         ▼
              ┌─────────────────────┐
              │ 5. CAPACITY         │
              │ Update warehouse    │
              │ workload            │
              └─────────────────────┘
```

I'll explain each stage from a backend/system-design perspective, including what data is involved, why the rule exists, and a concrete example.

## 1. First understand the actual problem

Suppose the customer has:

```text
Location:
Gurugram, Pincode 122018

Cart:
    SKU-A × 2
    SKU-B × 1
    SKU-C × 3
```

The customer sees:

```text
SKU-A → Delivery by Today 10 PM
SKU-B → Delivery by Tomorrow 10 PM
SKU-C → Delivery by Sunday 10 PM
```

It looks simple.

It isn't.

The system must determine:

```text
             Customer
                │
                ▼
       Where can we serve?
                │
                ▼
       Which warehouse(s)?
                │
                ▼
       Which SKU from which WH?
                │
                ▼
        How many parcels?
                │
                ▼
        Weight of each parcel
                │
                ▼
      Delivery type / SLA
                │
                ▼
     Cutoff + delays + holidays
                │
                ▼
       Final delivery time
```

The critical point is:

**You cannot calculate delivery time before knowing the fulfillment warehouse and parcel weight.**

Because:

```text
Warehouse A:
    0–5 kg → Hyperlocal → 2 hours

Warehouse B:
    0–5 kg → Next-day → 1 day
```

Same product.

Same customer.

Different warehouse.

Therefore:

**Delivery promise depends on fulfillment decision.**

## 2. Lesson 1 — Finding where the customer can be served

The first question is:

Which delivery zones contain this customer?

There are four levels:

```text
Polygon
   ↓
Pincode
   ↓
City
   ↓
State
```

Think of them as increasingly broad service areas.

### 2.1 Why do we need zones?

Imagine:

```text
                  Gurugram
        ┌─────────────────────────┐
        │                         │
        │       Polygon A         │
        │      ┌──────────┐       │
        │      │          │       │
        │      │ Customer │       │
        │      │    ●     │       │
        │      │          │       │
        │      └──────────┘       │
        │                         │
        └─────────────────────────┘
```

Polygon A might be served by:

```text
1. Darkstore-A
2. Darkstore-B
3. Warehouse-C
```

The polygon itself doesn't contain stock.

It contains warehouse serviceability information.

Conceptually:

```text
Zone
 ├── geography
 └── warehouse priorities
       ├── WH-A priority 1
       ├── WH-B priority 2
       └── WH-C priority 3
```

**Zone does NOT mean warehouse**

Instead:

```text
->
Zone = geographical/serviceability definition

Warehouse = physical location containing inventory
```

The zone only gave the engine the candidate warehouses and their priority.

```text
            Zone
             ↓
       Warehouses + priority

                 ZONE
                  │
        ┌─────────┴─────────┐
        │                   │
   Geographic area     Warehouse priority
        │                   │
   "Who is here?"       "Who can serve?"
        │                   │
        └─────────┬─────────┘
                  ↓
          Candidate warehouses
                  ↓
             Check stock
```

So when you see:

> “Polygon A is served by Darkstore-A, Darkstore-B, Warehouse-C”

```text
read it as:
```

> “Any customer whose location falls inside Polygon A can potentially receive their order from A, B, or C, and we prefer them in that order.”

## 3. Why H3 exists

The obvious implementation would be:

```text
customer lat/lng
       │
       ▼
check polygon 1
       │
       ▼
point-in-polygon?
       │
       ▼
check polygon 2
       │
       ▼
check polygon 3
       │
       ▼
...
```

This becomes expensive if you have many polygons and millions of requests.

Instead, the system uses H3.

H3 divides geography into cells.

Conceptually:

```text
      /\    /\    /\
     /  \__/  \__/  \
     \  /  \  /  \  /
      \/____\/____\/
      /\    /\    /\
     /  \__/  \__/  \
     \  /  \  /  \  /
      \/____\/____\/
```

Each location belongs to one H3 cell.

For example:

```text
lat = 28.4595
lng = 77.0266

        │
        ▼
     H3 index
        │
        ▼
   8a2a1072b59ffff
```

### Why H3 exists

The problem is that checking whether a customer's location is inside many polygons is expensive.

Without H3:

```text
Customer lat/lng
      ↓
Check Polygon 1
      ↓
inside?
      ↓
Check Polygon 2
      ↓
inside?
      ↓
Check Polygon 3
      ↓
...
```

If there are many polygons and millions of requests, this becomes costly.

### What H3 does

H3 divides the map into small cells.

So instead of doing geometry calculations every time:

```text
Customer lat/lng
       ↓
   H3 cell
       ↓
    lookup
```

For example:

```text
28.4595, 77.0266
       ↓
H3
       ↓
8a2a1072b59ffff
```

The important idea is:

**lat/lng → H3 cell is cheap.**

```text
->
```

### Why this helps

The expensive polygon calculation is moved to zone creation/update time.

When polygon is saved:

```text
Polygon
   ↓
Find H3 cells inside it
   ↓
Store those cells


At request time:

Customer lat/lng
   ↓
H3 cell
   ↓
Database lookup
   ↓
Which polygon/zone?
```

So the system does the expensive work once, rather than for every customer request.

**Mental model:**

> H3 converts “Is this point inside this shape?” into “Which cell is this point in, and is that cell associated with a zone?”

## 4. Polygon preprocessing

Suppose operations creates:

```text
Polygon P1
```

Instead of repeatedly asking:

Is customer point X inside polygon P1?

the system processes the polygon once.

```text
             Polygon P1
                  │
                  ▼
             H3 covering
                  │
        ┌─────────┼─────────┐
        ▼         ▼         ▼
       H1        H2        H3
        │         │         │
        └─────────┼─────────┘
                  ▼
             store mapping
```

Database might conceptually contain:

```text
polygon_id | h3_cell
-----------+---------
P1         | H1
P1         | H2
P1         | H3
P1         | H4

At request time:

Customer lat/lng
      │
      ▼
    H3 cell
      │
      ▼
 database lookup
      │
      ▼
 polygons containing this cell
      │
      ▼
 delivery zones
```

So instead of doing expensive geometry repeatedly:

```text
point-in-polygon
point-in-polygon
point-in-polygon
...

we do:

lat/lng
   ↓
H3
   ↓
indexed lookup
```

That's the main architectural optimization.

```text
->
```

### 1. When operations creates Polygon P1

Instead of storing only:

```text
P1 = some geographic shape
```

the system converts the polygon into the H3 cells that belong to it:

```text
Polygon P1
    ↓
H3 covering
    ↓
H1, H2, H3, H4...
```

And stores:

```text
polygon_id   h3_cell
P1           H1
P1           H2
P1           H3
P1           H4
```

This preprocessing happens when the polygon is created/updated, not on every customer request.

### 2. When a customer makes a request

Suppose:

```text
Customer lat/lng
       ↓
    H2 cell
```

The system asks the database:

Which polygons contain H2?

```text
Database quickly returns:

P1
```

Then:

```text
P1
 ↓
Zone
 ↓
Warehouses serving this zone
```

## 5. H3 trade-off

This isn't mathematically perfect.

Suppose:

```text
Polygon boundary
─────────────────────────
             /\
            /  \
           / ●  \
          /______\
```

The H3 cell may partially overlap the polygon.

The system says:

A cell belongs to the polygon if the cell center lies inside it.

Therefore the actual boundary is approximated.

Think:

```text
Actual polygon:

       /────────\
      /          \
     /            \
    /______________\


H3 approximation:

    [] [] [] [] []
    [] [] [] [] []
    [] [] [] [] []
       [] [] []
```

So someone near the boundary could theoretically be classified differently.

This is an intentional trade-off:

```text
                  Accuracy
                     ▲
                     │
                     │
                     │
                     └──────────────► Performance
```

The system accepts a small geographical approximation in exchange for much faster request-time lookups.

```text
->
```

### What happens?

Suppose the real polygon boundary looks like:

```text
       /────────\
      /          \
     /     ●      \
    /______________\
```

H3 divides the map into fixed cells:

```text
    [] [] [] [] []
    [] [] [] [] []
    [] [] [] [] []
       [] [] []
```

Some H3 cells will cross the polygon boundary.

The system uses this rule:

If the center of an H3 cell is inside the polygon, consider that cell part of the polygon.

### Why does this create approximation?

Imagine:

```text
Polygon boundary
────────────────────
        ┌─────┐
        │  ●  │  ← cell center inside
        └─────┘
```

That whole H3 cell is treated as belonging to the polygon, even though part of the cell might actually be outside the polygon.

Similarly:

```text
Polygon boundary
────────────────────
   ┌─────┐
   │  ●  │  ← center outside
   └─────┘
```

The cell is not considered part of the polygon, even if some of it overlaps the polygon.

### Why accept this?

Because the alternative is doing expensive geometric calculations for every request.

So the system chooses:

```text
Small geographic approximation
          +
Fast request-time lookup
          ↓
       Acceptable
```

For delivery zones, this is considered an acceptable trade-off. If the polygon changes, the H3 mapping is rebuilt.

**Interview answer:**

> “H3 trades a small amount of boundary accuracy for much faster request-time serviceability lookups. We preprocess polygons into H3 cells and then resolve a customer's location through an indexed cell lookup instead of doing point-in-polygon calculations on every request.”

## 6. Why fallback exists

What if the customer isn't inside a polygon?

You still want to know whether they can be served.

So:

```text
Polygon
   ↓
Pincode
   ↓
City
   ↓
State
   ↓
Not serviceable
```

Example:

```text
Customer
Pincode = 122018
City = Gurugram
State = Haryana
```

Suppose:

```text
Polygon:
SKU-A available
SKU-B available
SKU-C unavailable
```

Then the engine does not restart the whole search.

It continues only for SKU-C:

```text
Polygon
  │
  ├── SKU-A ✓
  ├── SKU-B ✓
  └── SKU-C ✗
          │
          ▼
       Pincode
          │
          ▼
        SKU-C ✓
```

This is important.

**The system tracks unresolved demand, not just unresolved locations.**

```text
->
```

### 1. Why fallback exists

A customer may not fall inside any polygon.

But you may still have a broader serviceability rule:

```text
Polygon
   ↓
Pincode
   ↓
City
   ↓
State
   ↓
Out of stock
```

So the system starts with the most specific location rule and progressively becomes broader.

### 2. Example

```text
Customer:

Pincode: 122018
City: Gurugram
State: Haryana

Cart:

SKU-A
SKU-B
SKU-C

Polygon search finds:

SKU-A → ✓
SKU-B → ✓
SKU-C → ✗
```

The engine does not do this:

```text
❌ Restart entire cart at Pincode

SKU-A → search again
SKU-B → search again
SKU-C → search again
```

Instead:

```text
SKU-A → DONE
SKU-B → DONE
SKU-C → still needed
```

Only SKU-C moves to the next level:

```text
Polygon
   │
   ├── SKU-A ✓
   ├── SKU-B ✓
   └── SKU-C ✗
          ↓
       Pincode
          ↓
       SKU-C ✓
```

### 3. Why this matters

Think of the engine as maintaining:

```text
required quantity
        -
quantity already found
        =
remaining demand
```

So after each zone level:

```text
Polygon
   ↓
What is still missing?
   ↓
Pincode
   ↓
What is still missing?
   ↓
City
   ↓
...
```

The document calls this rule:

> “Only what's still missing moves on.”

So the important mental model is:

**The fallback operates on unresolved SKU demand, not on the entire customer/cart.**

## 7. Lesson 2 — Finding inventory

Now we know which zones can serve the customer.

Next:

Which warehouse supplies each SKU?

Suppose:

```text
SKU-A × 2

and warehouses are:

             Stock
WH-A           1
WH-B           5
WH-C           10
```

The engine searches according to zone priority.

Example:

```text
Polygon
  │
  ├── WH-A priority 1
  ├── WH-B priority 2
  └── WH-C priority 3
```

It takes inventory nearest/priority-first.

## 8. Why the inventory ledger is necessary

This is one of the most important parts of the architecture.

Suppose:

```text
SKU-A required = 2
```

And:

```text
WH-A stock = 1

WH-A appears in:

Polygon zone
AND
Pincode zone
```

Without a ledger:

```text
Polygon:
    WH-A → take 1

Pincode:
    WH-A → sees stock 1
           take another 1
```

Now the engine thinks:

```text
1 + 1 = 2
```

But reality is:

```text
WH-A has only 1
```

It has double-counted the same inventory.

```text
->
```

The stock table says:

> "What does this warehouse physically have?"

The ledger says:

> "How much of that stock have I already allocated during this request?"

So:

```text
Available
=
Stock on hand
-
Already allocated in this request
```

## 9. The per-request ledger

The engine maintains something like:

```text
ledger:

SKU-A
  WH-A → 1 already promised
```

Then:

```text
available =
    actual_stock
    -
    already_used_in_this_request
```

Example:

```text
Actual WH-A stock = 1

Already allocated = 1

Available = 1 - 1
          = 0
```

Therefore:

```text
Pincode search:

WH-A → 0 available → skip
WH-B → available → take 1
```

Final:

```text
SKU-A × 2

WH-A → 1
WH-B → 1
```

<!-- ➕ added:start -->

**➕ Added diagram — the per-request ledger for the SKU-A example**

| Level | Warehouse | Stock on hand | Already allocated in this request | Available | Take | SKU-A still needed |
|---|---|---|---|---|---|---|
| Polygon | WH-A | 1 | 0 | 1 | 1 | 1 |
| Pincode | WH-A | 1 | 1 | 0 | 0 → skip | 1 |
| Pincode | WH-B | 5 | 0 | 5 | 1 | 0 ✓ |

`Available = Stock on hand − Already allocated in this request` (SKU-A required = 2)

<!-- ➕ added:end -->

## 10. Very important: this is NOT a reservation

This distinction matters a lot in interviews.

The ledger only exists during one request.

Imagine:

```text
WH-A stock = 1
```

Two customers simultaneously request it.

```text
Customer A request
        │
        └── sees stock = 1
             promises it


Customer B request
        │
        └── sees stock = 1
             promises it

Both may receive:
```

"Delivery available"

But physically:

```text
stock = 1
demand = 2
```

That's an oversell race condition.

<!-- ➕ added:start -->

**➕ Added diagram — why the ledger can't stop a cross-request oversell**

```text
 time   Customer A request        WH-A stock        Customer B request
 ────   ──────────────────        ──────────        ──────────────────
  t1    sees stock = 1                1             sees stock = 1
  t2    promises it                   1             promises it
  t3    "Delivery available"          1             "Delivery available"
                                      │
                                      ▼
                          stock = 1, demand = 2  →  oversell

 Each request has its own ledger, and neither ledger sees the other.
```

<!-- ➕ added:end -->

The ledger doesn't solve cross-request concurrency.

A true reservation mechanism would need something like:

```text
checkout
   │
   ▼
reserve stock
   │
   ▼
TTL = 5 minutes
   │
   ├── payment succeeds → consume
   │
   └── payment fails → release
```

That's fundamentally different.

## 11. All-or-nothing inventory

Suppose:

```text
Customer requests:

SKU-A × 3

Available:

WH-A = 1
WH-B = 1
WH-C = 0

Total:

1 + 1 = 2

Required:

3
```

Therefore:

```text
2 < 3
```

The engine does:

```text
SKU-A → OUT OF STOCK
```

It does not say:

```text
2 available out of 3
```

because the business rule is:

**Either fulfill the requested quantity or don't promise the item.**

The temporary allocations are discarded.

## 12. Product page vs cart

This is another subtle distinction.

### Product page

Suppose:

```text
SKU-A × 2

Warehouses:

WH-A → 1
WH-B → 2

Product page chooses:

WH-B
```

because it can fulfill the entire quantity.

It doesn't split:

```text
WH-A → 1
WH-B → 1
```

Instead:

```text
WH-B → 2
```

This is simpler and faster.

### Cart

Cart can split.

```text
SKU-A × 3

WH-A → 1
WH-B → 2
```

Therefore:

```text
Parcel 1:
    WH-A
    SKU-A × 1

Parcel 2:
    WH-B
    SKU-A × 2
```

Why?

Because the cart is solving the actual fulfillment problem.

### /v2/edd — Product-level

Answers:

> “If I buy this one item, when can I get it?”

```text
1 item
  ↓
Find ONE warehouse with full quantity
  ↓
Calculate promise
```

- No splitting.
- No parcels.
- Uses that item's weight.
- Read-only.
- Used on product/listing pages.

### /v2/cartedd — Cart-level

Answers:

> “If I buy this entire basket, how will it actually be shipped?”

```text
Entire cart
   ↓
Allocate stock
   ↓
Split across warehouses if needed
   ↓
Create parcels
   ↓
Calculate promise for each parcel
```

- Can split quantity across warehouses.
- Uses parcel weight, not individual item weight.
- Handles overlapping-zone inventory using the ledger.
- Determines actual shipment structure.
- Can count the order against warehouse capacity after placement.

### Why can they give different dates?

Example:

Product alone:

```text
4 kg
→ hyperlocal
→ Today 10 PM
```

But cart:

```text
4 kg dog food
+ 5 kg cat litter
= 9 kg parcel
```

Now the parcel weighs 9 kg, potentially changing its delivery type:

```text
→ next-day
→ Tomorrow 10 PM
```

So remember:

**EDD = “When can this item arrive?”**

**Cart EDD = “How will my actual basket be fulfilled, and when will each shipment arrive?”**

## 13. Lesson 3 — Creating parcels

Now we have fulfillment assignments.

Example:

```text
WH-A:
    SKU-A × 1
    SKU-B × 2

WH-B:
    SKU-C × 3
```

## 14. Parcel weight limits

Suppose WH-A has:

```text
Maximum parcel weight = 8 kg

Items:

Sample       0.1 kg
Dog food     4 kg
Cat litter   5 kg

Sort lightest first:

0.1
4
5

Start:

Parcel 1 = 0

Add sample:

0 + 0.1 = 0.1

Parcel 1:
    sample
    0.1 kg

Add dog food:

0.1 + 4 = 4.1

Parcel 1:
    sample
    dog food
    4.1 kg

Try cat litter:

4.1 + 5 = 9.1
```

But:

```text
9.1 > 8
```

So:

```text
close Parcel 1

Parcel 2:
    cat litter
    5 kg
```

Final:

```text
Parcel 1 = 4.1 kg
Parcel 2 = 5 kg
```

<!-- ➕ added:start -->

**➕ Added diagram — the packing walk-through as parcels**

```text
 Maximum parcel weight = 8 kg · sorted lightest first: 0.1 → 4 → 5

 ┌ Parcel 1 ────────────────┐        ┌ Parcel 2 ────────────────┐
 │ Sample          0.1 kg   │        │ Cat litter      5.0 kg   │
 │ Dog food        4.0 kg   │        │                          │
 │                          │        │                          │
 │ total           4.1 kg   │        │ total           5.0 kg   │
 └──────────────────────────┘        └──────────────────────────┘
   + Cat litter → 4.1 + 5 = 9.1 kg > 8 kg ──────────► opens Parcel 2
```

<!-- ➕ added:end -->

## 16. Free gifts

Suppose:

```text
Main order:

SKU-A → WH-A

Free gift:

Gift-G → WH-A
```

Then:

```text
Parcel WH-A
 ├── SKU-A
 └── Gift-G
```

The goal is:

**Don't create another shipment just because of a free gift.**

But the gift is packed after the main items.

This means the main order gets packing priority.

## 17. Lesson 4 — Calculating delivery time

Now we have a parcel.

Suppose:

```text
Warehouse = WH-A
Zone = Polygon-A
Weight = 4 kg
```

Now we ask:

When will this parcel arrive?

This is where most of the complexity lives.

## 18. The most important concept: ADD vs SET

Think of a datetime:

```text
2026-09-29 19:30
```

An operation can either:

```text
ADD
+2 hours

19:30
  ↓
21:30

or:

SET
SET tomorrow 09:00

19:30
  ↓
tomorrow 09:00
```

These are fundamentally different.

## 20. Rule 1 — Weight determines delivery type

Suppose terms are:

```text
WH-A → Polygon-A

0–5 kg:
    Hyperlocal
    SLA = 2 hours

5–10 kg:
    Next-day
    SLA = 1 day

10–20 kg:
    Standard
    SLA = 3 days
```

If parcel weight is:

```text
4 kg

then:

delivery_type = hyperlocal
SLA = 2 hours
```

If:

```text
9 kg

then:

delivery_type = next-day
SLA = 1 day
```

So weight isn't just packing information.

**It directly influences the delivery promise.**

<!-- ➕ added:start -->

**➕ See also:** [§12 — Why can they give different dates?](#why-can-they-give-different-dates). The same 4 kg item is hyperlocal on its own (`/v2/edd`), but next-day inside a 9 kg cart parcel (`/v2/cartedd`).

<!-- ➕ added:end -->

## 21. Rule 2 — Cutoff

Suppose:

```text
Next-day cutoff = 6 PM

Customer orders at:

7:30 PM Friday
```

That's after cutoff.

Therefore the system doesn't start counting SLA from 7:30 PM.

It does:

```text
Friday 7:30 PM
       │
       ▼
after cutoff
       │
       ▼
SET Saturday 9 AM
```

Then:

```text
SLA = +1 day
```

Therefore:

```text
Saturday 9 AM
       +
     1 day
       ↓
Sunday 9 AM
```

Then final non-hyperlocal time:

```text
Sunday 10 PM
```

Final:

```text
Delivery by Sunday, 10 PM
```

## 22. Hyperlocal is different

Suppose:

```text
Hyperlocal operating window:

07:00 → 23:00

Customer orders:

Friday 19:30
```

They are inside the window.

Therefore:

```text
No cutoff shift
```

Then:

```text
Rain = +30 minutes
SLA = +2 hours
```

So:

```text
19:30
 +0:30
 +2:00
------
22:00
```

Result:

```text
Today 10 PM
```

## 23. Why hyperlocal cutoff doesn't add SLA twice

Suppose an order comes after the hyperlocal window.

```text
Friday 23:30
```

The rule might say:

```text
SET Saturday 10 AM
```

That 10 AM is already the promised slot.

If you then also add the normal SLA:

```text
Saturday 10 AM
       +
     2 hours
       ↓
Saturday 12 PM
```

you've potentially counted the transition twice.

Hence:

```text
hyperlocal cutoff selected slot
        ↓
don't add normal SLA again
```

## 24. Rule 3 — Delays

There are four delay sources.

```text
                DELAYS
                  │
     ┌────────────┼─────────────┐
     │            │             │
Operational      Rain        Capacity
     │                            │
     └────────────┬───────────────┘
                  │
              Product tag
```

### Operational delay

Example:

```text
WH-A
Polygon-A
Operational delay = +60 minutes
```

Could be because of:

```text
warehouse issue
staff shortage
festival
maintenance
supply-chain issue
```

## 25. Rain delay

Suppose:

```text
Rain = +30 minutes
```

But the engine has:

```text
Operational delay = +60 minutes
```

The rules say:

```text
Operational delay exists
        ↓
don't apply rain
```

So:

```text
+60 minutes

not:

+60 + 30 = +90
```

This is a precedence rule.

## 26. Capacity delay

Suppose:

```text
WH-A
Hyperlocal
Current slot capacity = full
```

The slot might have:

```text
Capacity = 100 orders
Current = 100
```

Then:

```text
Capacity delay = +30 min
```

The promise gets pushed.

## 27. Product tag delay

A product may have a tag:

```text
TAG = "Fragile"

and:

Fragile → +1 day
```

Or perhaps:

```text
TAG = "Priority"
Priority → -30 min
```

So tag rules can even subtract time.

That's why you should think of them mathematically:

```text
delivery_time += tag_delay

where:

tag_delay

could theoretically be:

+60 min
0
-30 min
```

## 28. Rule 4 — Add SLA

Now apply the normal SLA.

Example:

```text
Current:
Friday 19:30

Rain:
+30 min

Operational:
+0

Capacity:
+0

Tag:
+0

SLA:
+2 hours
```

Therefore:

```text
19:30
 +0:30
 +2:00
------
22:00
```

## 29. Two clocks — extremely important

This is one of the more complicated concepts.

Why not just have:

```text
delivery_time

?
```

Because:

**Pickup and delivery are different events.**

Example:

```text
Warehouse
    │
    │ pickup
    ▼
Courier
    │
    │ transit
    ▼
Customer
    │
    │ delivery
    ▼
```

A warehouse holiday affects:

> Can the warehouse dispatch?

A delivery holiday affects:

> Can the customer receive?

These are different constraints.

Therefore:

```text
Pickup Clock
     │
     └── when warehouse can dispatch

Delivery Clock
     │
     └── when customer can receive
```

## 30. Pickup clock

Pickup clock considers things related to leaving the warehouse:

```text
Now
 ↓
cutoff shift
 ↓
warehouse operational delays
 ↓
capacity
 ↓
pickup non-working days
```

It does not include:

```text
zone-level delivery delays
tag delays
SLA
```

because those affect delivery, not warehouse pickup.

## 31. Delivery clock

The delivery clock eventually considers:

```text
pickup result
+
operational effects
+
rain
+
capacity
+
tags
+
SLA
+
delivery-day restrictions
```

Conceptually:

```text
             NOW
              │
              ▼
       ┌─────────────┐
       │ Pickup Clock│
       └──────┬──────┘
              │
              ▼
        Parcel leaves
              │
              ▼
      ┌────────────────┐
      │ Delivery Clock │
      └───────┬────────┘
              │
              ▼
          Customer
```

<!-- ➕ added:start -->

**➕ Added diagram — what each clock is responsible for**

```text
 PICKUP CLOCK                              DELIVERY CLOCK
 "Can the warehouse dispatch?"             "Can the customer receive?"
 ─────────────────────────────             ───────────────────────────
 Now                                       pickup result
  ↓ cutoff shift                            + operational effects
  ↓ warehouse operational delays            + rain
  ↓ capacity                                + capacity
  ↓ pickup non-working days                 + tags
                                            + SLA
 not here: zone-level delivery delays,      + delivery-day restrictions
           tag delays, SLA
        │                                          ▲
        └────────────── parcel leaves ─────────────┘
```

<!-- ➕ added:end -->

## 32. Non-pickup day example

Suppose:

```text
Current = Friday
Cutoff = passed
Start = Saturday 9 AM
```

But:

```text
Saturday = warehouse holiday
```

So:

```text
Saturday 9 AM
     │
     ▼
blocked
     │
     ▼
Sunday 9 AM
```

That adds one day.

If the original delivery was:

```text
Sunday

then it becomes:

Monday
```

The important thing is:

**The warehouse couldn't dispatch on Saturday, so delivery must move.**

## 33. Why reset the time after a day skip?

Suppose you had:

```text
Saturday 18:47
```

and Saturday is blocked.

You move to:

```text
Sunday 18:47
```

But perhaps the warehouse's configured delivery/pickup anchor is:

```text
09:00
```

So the engine re-anchors:

```text
Sunday 09:00
```

Otherwise you're carrying a time that may no longer make business sense.

## 34. Rule 6 — Final time of day

For non-hyperlocal:

```text
delivery date = Sunday
```

The system promises:

```text
Sunday 10 PM
```

It doesn't promise:

```text
Sunday 09:17 PM
```

because these are essentially:

> “By end of day.”

So:

```text
non-hyperlocal
     ↓
SET 22:00
```

This is another SET operation.

## 35. The 11:30 PM rule

Suppose the calculated result is:

```text
23:45
```

The system says:

```text
>= 23:30
```

Then:

```text
SET next day 13:00
```

So:

```text
Friday 23:45
      ↓
Saturday 13:00
```

Again:

```text
SET

not:

+13 hours
```

## 36. Complete delivery calculation example

Let's do the entire thing.

```text
Customer orders:

Friday 7:30 PM

Parcel:

Weight = 9 kg
Warehouse = WH-B

Terms:

9 kg → Next-day
SLA = 1 day
Cutoff = 6 PM

Current time:

Friday 19:30
```

### Step 1 — Weight

```text
9 kg
 ↓
Next-day
 ↓
SLA = 1 day
```

### Step 2 — Cutoff

```text
19:30 > 18:00
```

Therefore:

```text
SET Saturday 09:00
```

### Step 3 — delays

Assume:

```text
Operational = 0
Rain = 0
Capacity = 0
Tag = 0
```

Nothing changes.

### Step 4 — SLA

```text
Saturday 09:00
+
1 day
=
Sunday 09:00
```

### Step 5 — non-working days

Assume:

```text
Sunday = working
```

No change.

### Step 6 — final time

```text
Non-hyperlocal:

SET 22:00
```

Therefore:

```text
Sunday 22:00
```

Final:

```text
Delivery by Sunday 10 PM
```

## 37. Now add a warehouse holiday

Same scenario.

But:

```text
Saturday = non-pickup day

Pickup clock:

Saturday 09:00
      │
      ▼
blocked
      │
      ▼
Sunday 09:00
```

That causes delivery to move one day:

```text
Sunday
 ↓
Monday
```

Final:

```text
Monday 10 PM
```

This is why the two-clock model matters.

<!-- ➕ added:start -->

**➕ Added diagram — sections 36 and 37 as ADD / SET / WALK steps**

```text
 36. No holiday                            37. Saturday = non-pickup day

 Friday 19:30                              Friday 19:30
      │ SET   (19:30 > 18:00 cutoff)            │ SET   (19:30 > 18:00 cutoff)
      ▼                                         ▼
 Saturday 09:00                            Saturday 09:00
      │ ADD   delays = 0                        │ ADD   delays = 0
      ▼                                         ▼
 Saturday 09:00                            Saturday 09:00   blocked (pickup clock)
      │ ADD   SLA = 1 day                       │ WALK  +1 day
      ▼                                         ▼
 Sunday 09:00    (Sunday = working)        Sunday 09:00
      │ SET   22:00                             │ ADD   SLA = 1 day
      ▼                                         ▼
 Sunday 22:00                              Monday 09:00
 "Delivery by Sunday 10 PM"                     │ SET   22:00
                                                ▼
                                           Monday 22:00
                                           "Monday 10 PM"
```

<!-- ➕ added:end -->

<!-- ➕ added:start -->

## The 8-stage buffer pipeline (what the resume means)

**➕ Added section**, explaining the resume line *"…and an **8-stage** buffer pipeline."*

A **buffer** is extra time added on top of the courier's base delivery time (the SLA).
The **8-stage buffer pipeline** is the fixed order of 8 adjustments that every shipment's delivery time passes through, from "now" to the promised date and time.
Sections 20–35 above explain each stage one at a time. This section is the map that ties them together.

| # | Stage | What it does | Operation | Covered in |
|---|---|---|---|---|
| 1 | **Cutoff** | After the daily cutoff (e.g. 6 PM), or outside the hyperlocal operating window, the start moves to a later day at a fixed time | SET | §21–23 |
| 2 | **Static buffers** | Manual ops delays (warehouse issue, staff shortage, festival, maintenance). Can be set per cluster, per warehouse, or per cluster + warehouse; all are added together | ADD | §24 |
| 3 | **Rain buffer** | Weather-driven delay. Applied only when there is no manual (static) delay | ADD | §25, §43–46 |
| 4 | **Capacity buffer** | The warehouse slot is full (e.g. 100/100 orders), so extra delay is added | ADD | §26, §39–42 |
| 5 | **Tag buffer** | Delay from product tags, e.g. Fragile +1 day or Priority −30 min. Can be negative | ADD | §27 |
| 6 | **SLA** | Base courier time for the weight slab (e.g. hyperlocal 2 hours, next-day 1 day). Skipped if a hyperlocal cutoff already set the slot | ADD | §20, §28 |
| 7 | **Pickup day-skip** | The warehouse can't dispatch that day, so the date moves forward and the time re-anchors | WALK | §29–30, §32–33 |
| 8 | **Delivery day-skip** | The customer side can't receive that day, so the date moves forward | WALK | §31 |

```text
 now
  │ 1  cutoff ............. SET    start = later day, fixed time
  │ 2  static buffers ..... ADD    manual ops delays, summed
  │ 3  rain buffer ........ ADD    only if there is no manual delay
  │ 4  capacity buffer .... ADD    slot full → delay
  │ 5  tag buffer ......... ADD    can be negative
  │ 6  SLA ................ ADD    skipped after a hyperlocal cutoff
  │ 7  pickup day-skip .... WALK   warehouse can't dispatch
  │ 8  delivery day-skip .. WALK   customer can't receive
  ▼
 promise   (then time of day: SET 22:00, or 13:00 next day if ≥ 23:30)
```

### Why it's a "pipeline": the order changes the answer

- **Cutoff comes first.** It sets the start time, and every later stage builds on it.
- **A hyperlocal cutoff replaces the SLA** instead of adding to it (§23).
- **Rain is a fallback, not an addition.** A manual delay beats rain (§25, §46).
- **After a day-skip, the time re-anchors** to the configured start time (§33).

### Example (§36 + §37)

A 9 kg next-day parcel is ordered Friday 19:30. The cutoff is 6 PM and Saturday is a warehouse holiday.

| Stage | Clock |
|---|---|
| Start | Friday 19:30 |
| 1 Cutoff (19:30 > 18:00) | SET → Saturday 09:00 |
| 2–5 Buffers | +0 → Saturday 09:00 |
| 6 SLA (9 kg → next-day, 1 day) | ADD → Sunday 09:00 |
| 7 Pickup day-skip (Saturday = holiday) | WALK → the delivery moves one day, to Monday |
| 8 Delivery day-skip (Monday = working) | no change |
| Final time of day | SET 22:00 → **Monday 10 PM** |

### Be ready for a different count

The code also has 3 steps that aren't buffers:

- **Before stage 1:** a weight-slab match picks the delivery type and the SLA (§20).
- **Applying the summed buffers** is its own step.
- **At the end:** normalise the time of day (§34–35).

So `projects/findings/PROMISE-ENGINE-HLD.md` §4.0 lists 10 rows in execution order. "8" counts only the configurable time adjustments. If an interviewer counts differently, say this.

**Interview answer:**

> "For every shipment, the delivery time runs through eight adjustments in a fixed order: cutoff, static buffers, rain, capacity, tags, SLA, then the pickup and delivery day-skips. The order matters. The cutoff sets the start. A hyperlocal cutoff replaces the SLA instead of adding to it. Rain only applies when there's no manual delay. And after a day-skip we re-anchor the time."

<!-- ➕ added:end -->

## 38. What if the item comes from two warehouses?

Suppose:

```text
SKU-A × 3

Fulfillment:

WH-A → 1
WH-B → 2
```

Then:

```text
Parcel 1
WH-A
SKU-A × 1
Delivery: Saturday 10 PM


Parcel 2
WH-B
SKU-A × 2
Delivery: Sunday 10 PM
```

What should the customer see for SKU-A?

The entire quantity isn't received until:

```text
Sunday
```

Therefore:

```text
SKU-A promise = Sunday 10 PM
```

Mathematically:

```text
item_promise = MAX(parcel_promises)
```

For example:

```text
MAX(
    Saturday 22:00,
    Sunday 22:00
)
=
Sunday 22:00
```

The cart can still show the underlying parcels.

## 39. Lesson 5 — Capacity feedback loop

Now we have another problem.

Suppose warehouse capacity is:

```text
200 orders

for:

Next-day
6 PM–midnight

At 5 PM:

Current count = 190
```

Customer places order.

```text
190 + 1 = 191
```

Still okay.

But eventually:

```text
200
```

Then:

```text
201
```

The slot is overloaded.

The system doesn't necessarily reject the order.

Instead:

```text
Current slot full
       ↓
next shoppers
       ↓
additional delay
       ↓
later delivery promise
```

This is a very important business principle:

**Capacity changes the promise, not necessarily order acceptance.**

## 40. Why the counter update must be atomic

Imagine:

```text
capacity = 100

current = 99
```

Two orders arrive simultaneously.

```text
Bad implementation:

Request A:
    read 99

Request B:
    read 99

Request A:
    write 100

Request B:
    write 100
```

You had two orders, but counter increased only once.

Correct implementation needs an atomic increment:

```sql
UPDATE capacity_counter
SET count = count + 1
WHERE ...;
```

Then:

```text
99
 ↓
100
 ↓
101
```

No lost update.

That's what the document means by:

> “The increment is a single database update.”

## 41. Overflow

Suppose:

```text
Slot A capacity = 100
Slot B capacity = 100
```

Slot A already has:

```text
95
```

Then 10 new orders arrive.

Instead of:

```text
A = 105
B = 0
```

the conceptual model is:

```text
Slot A:
95 + 5 = 100

overflow:
5

Slot B:
5 + 0 = 5
```

So overflow carries forward.

```text
             Slot A
        capacity = 100
             │
        95 existing
             │
        +10 orders
             │
             ▼
      100 + overflow 5
                     │
                     ▼
                  Slot B
                   +5
```

This prevents the next slot from pretending it's empty.

<!-- ➕ added:start -->

**➕ Added diagram — overflow carried into the next slot**

```text
 capacity = 100 per slot · 20 blocks = 100 orders

 Slot A  [███████████████████·]   95  existing
         [████████████████████]  100  after the first 5 of the 10 new orders
                               │
                               │ overflow = 5
                               ▼
 Slot B  [█···················]    5  the other 5 carry forward
```

<!-- ➕ added:end -->

## 42. The cache creates an important problem

Suppose:

```text
Capacity = 100
Current = 99
```

Order arrives.

```text
Database becomes:

100
```

But the promise engine has:

```text
Redis cache:
99
```

for up to five minutes.

Another customer arrives.

The engine may still see:

```text
99
```

and promise the faster slot.

Therefore:

```text
cache
 ↓
performance

but:

cache
 ↓
stale capacity information
```

This is an explicit consistency trade-off.

<!-- ➕ added:start -->

**➕ Added diagram — how the 5-minute cache serves stale capacity**

```text
 time ────────────────────────────────────────────────────────────────►
          t0                     t1                        t0 + 5 min
 DB       99 ─────────────────── 100 (order placed) ───────────────────
 Redis    99 cached ──────────────────── still 99 ──────── expires → 100
                                   ▲
                                   │
                    Customer 2 arrives: engine sees 99
                    → promises the faster slot
```

<!-- ➕ added:end -->

## 43. Lesson 6 — Rain

Rain is treated as a dynamic delay.

Imagine a hyperlocal warehouse:

```text
WH-A

Weather service says:

Rain intensity = moderate
Rain duration = 20 min
```

The system may calculate:

```text
Rain delay = +30 min
```

Then:

```text
Normal SLA = 25 min
Rain = +30 min

Promise = 55 min
```

## 44. Why don't we just directly use weather API on every request?

Because that would be bad architecture.

Imagine:

```text
10,000 promise requests/sec
```

and every request calls:

```text
weather API
```

You get:

```text
Promise Engine
   │
   ├── Weather API
   ├── Weather API
   ├── Weather API
   ├── Weather API
   └── ...
```

Instead, background workers continuously monitor weather.

```text
Weather API
     │
     ▼
Background Job
     │
     ▼
Rain calculation
     │
     ▼
Approval workflow
     │
     ▼
Rain delay state
```

Then request processing is simply:

```text
Request
  │
  ▼
read current rain delay
  │
  ▼
+30 min
```

Much cheaper.

## 45. Human approval loop

The weather system doesn't blindly change operations.

Conceptually:

```text
Weather
   │
   ▼
Algorithm
   │
   ▼
Suggested delay
   │
   ▼
Operations team
   │
   ├── Approve
   │
   └── No response
          │
          ▼
       auto apply
```

For example:

```text
Gurugram

WH-A
Rain: heavy
Suggested delay: +60 min

[Approve]
```

If nobody responds for 10 minutes:

```text
auto-approve

Outside operating hours:

auto-apply immediately
```

## 46. Manual delay beats rain

Suppose:

```text
Operational delay = +45 min
Rain delay = +30 min
```

The engine chooses:

```text
+45 min

not:

+75 min
```

Why?

Because manual operational configuration has higher authority.

This is essentially:

```text
if operational_delay_exists:
    use operational_delay
else:
    use rain_delay
```

## 47. Lesson 7 — Caching architecture

A lot of configuration doesn't change every second.

So Redis caches:

```text
location → zones

zone → warehouses

SKU → stock

warehouse → delivery configuration

for roughly:

5 minutes
```

This makes:

```text
Request
   │
   ▼
Redis
   │
   ├── HIT → fast
   │
   └── MISS → DB
```

## 48. Why not cache everything?

Because some information is too dynamic.

The document explicitly keeps these fresh:

```text
Rain status
Tag rules
```

So:

```text
Mostly static:
    Redis ~5 min

Dynamic:
    fresh read
```

This is a standard consistency decision.

<!-- ➕ added:start -->

**➕ Added diagram — what is cached vs read fresh, and where rain comes from**

```text
                               REQUEST
                                  │
                                  ▼
                         ┌────────────────┐
                         │ Promise Engine │
                         └────────┬───────┘
                 ┌────────────────┴───────────────┐
                 │ mostly static                  │ dynamic
                 ▼                                ▼
      ┌─────────────────────┐          ┌─────────────────────┐
      │ Redis  ~5 min       │          │ fresh read          │
      │                     │          │                     │
      │ location → zones    │          │ Rain status         │
      │ zone → warehouses   │          │ Tag rules           │
      │ SKU → stock         │          └──────────▲──────────┘
      │ warehouse →         │                     │
      │   delivery config   │                     │ rain delay state
      └──────┬───────┬──────┘                     │
         HIT │       │ MISS            ┌──────────┴──────────┐
             ▼       ▼                 │ Background Job      │
          fast   ┌──────────┐          │ Weather API         │
                 │ Database │          │ → Rain calculation  │
                 └──────────┘          │ → Approval workflow │
                                       └─────────────────────┘
```

<!-- ➕ added:end -->

## 49. Failure modes

This is where the architecture becomes interesting.

When something breaks, you have two choices:

**FAIL OPEN**

```text
dependency unavailable
       │
       ▼
still return something

or:
```

**FAIL CLOSED**

```text
dependency unavailable
       │
       ▼
reject/fail request
```

## 50. Redis failure

Suppose:

```text
Redis DOWN
```

The engine can do:

```text
Redis
  │
  X
  │
  ▼
Database
```

It's slower but still produces a result.

```text
That's:

FAIL OPEN
```

Reasonable because the DB is the source of truth.

## 51. Capacity update failure

Suppose:

```text
Order placed
    │
    ▼
capacity increment
    │
    X
```

The system logs the error but doesn't fail the customer response.

Why?

**Because capacity is a feedback mechanism, not the fundamental fulfillment decision.**

So:

```text
FAIL OPEN
```

But you now have potentially inaccurate future promises.

## 52. Weather service failure

Suppose weather service stops responding.

The engine uses:

```text
last known weather state
```

For example:

```text
Last known:
rain = true
delay = 30 min
```

Even though current weather is unknown.

This is:

```text
FAIL OPEN WITH STALE DATA
```

Better than randomly removing a delay.

## 53. Most dangerous failure: rules unavailable

This is the worst design in the document.

Suppose the engine cannot load:

```text
cutoffs
delays
delivery configuration
```

Instead it says:

> I'll just use base SLA.

Suppose actual promise should be:

```text
Monday 10 PM
```

But SLA-only gives:

```text
Sunday 10 PM
```

The shopper sees:

```text
Delivery by Sunday 10 PM
```

Looks perfectly valid.

But it's wrong.

```text
Worse:

wrong answer
    ↓
cached for 5 min
    ↓
many customers receive wrong promise
```

That's why the document calls this:

```text
open but optimistic
```

And that is dangerous.

## 54. Better failure strategy

If delivery rules cannot be loaded, I'd rather do:

```text
Rules unavailable
       │
       ▼
conservative fallback
       │
       ▼
later delivery date
```

For example:

```text
normal:
Sunday 10 PM

fallback:
Monday 10 PM
```

**You don't want to promise something earlier than you can confidently fulfill.**

And importantly:

```text
don't cache fallback
```

because otherwise the failure gets amplified.

## 55. Why rain/tag failures are closed

The document says:

```text
Rain status unavailable → request fails
Tag rules unavailable → request fails
```

This seems stricter because those values directly affect the calculation and there isn't considered to be a safe approximation.

So:

```text
dependency
     │
     ├── safe fallback exists → open
     │
     └── unsafe/no trustworthy fallback → closed
```

That's the general engineering principle.

<!-- ➕ added:start -->

**➕ Added diagram — failure semantics per dependency**

| Dependency unavailable | What the engine does | Semantics |
|---|---|---|
| Redis | reads the Database (slower) | FAIL OPEN |
| Capacity increment | logs the error; customer response unaffected | FAIL OPEN (future promises may be inaccurate) |
| Weather service | uses the last known weather state | FAIL OPEN WITH STALE DATA |
| Rules (cutoffs, delays, delivery configuration) | uses base SLA only; the answer is cached for 5 min | open but optimistic (the dangerous one) |
| Rain status | request fails | FAIL CLOSED |
| Tag rules | request fails | FAIL CLOSED |

Section 54's better strategy for rules: conservative fallback → later delivery date, and don't cache the fallback.

<!-- ➕ added:end -->

## 56. Lesson 8 — Why this differs from 10-minute delivery

This is important because you should not confuse:

```text
traditional e-commerce promise engine

with:

quick-commerce promise engine
```

### Traditional e-commerce

```text
Can tolerate:

hours
days
```

Example:

```text
Delivery by Sunday 10 PM
```

Therefore:

```text
5-minute stale cache
```

may be acceptable in some places.

### 10-minute delivery

Suppose promise is:

```text
10 minutes
```

Then:

```text
5-minute stale inventory
```

is disastrous.

Half your entire promise window has passed.

So you need:

```text
live inventory
+
reservation
+
picker capacity
+
rider availability
+
precise location
+
real-time traffic/weather
```

## 57. Traditional model vs quick-commerce model

Think about the difference:

### Traditional

```text
Customer
   │
   ▼
Multiple warehouses
   │
   ▼
Inventory allocation
   │
   ▼
Parcel creation
   │
   ▼
Courier
   │
   ▼
Customer

Promise can be:

1–3 days
```

### Quick commerce

```text
Customer
   │
   ▼
Nearby darkstore
   │
   ├── Picker available?
   ├── Rider available?
   ├── Inventory available?
   ├── Current queue?
   ├── Traffic?
   └── Weather?
        │
        ▼
     10-minute promise
```

The promise becomes much more dynamic.

## 58. Now combine everything into one example

Let's run a complete request.

```text
Customer:

Location:
lat/lng = X/Y
pincode = 122018

Cart:
SKU-A × 2
SKU-B × 1
```

### Step 1 — Location

```text
lat/lng
  │
  ▼
H3 cell
  │
  ▼
Polygon-A

Polygon-A has:

WH-A priority 1
WH-B priority 2
```

### Step 2 — Inventory

```text
SKU-A:

WH-A = 1
WH-B = 5

Need:

2

Take:

WH-A → 1
WH-B → 1

Ledger:

SKU-A:
    WH-A → 1
    WH-B → 1

SKU-B:

WH-A = 1

Take:

WH-A → 1

Fulfillment:

WH-A:
    SKU-A × 1
    SKU-B × 1

WH-B:
    SKU-A × 1
```

## 59. Step 3 — Parcelization

Suppose:

```text
WH-A parcel limit = 5 kg
WH-B parcel limit = 8 kg

Weights:

SKU-A = 2 kg
SKU-B = 1 kg

WH-A:

2 + 1 = 3 kg
```

So:

```text
Parcel 1
WH-A
SKU-A × 1
SKU-B × 1
Weight = 3 kg

WH-B:

Parcel 2
WH-B
SKU-A × 1
Weight = 2 kg
```

## 60. Step 4 — Delivery calculation

```text
Parcel 1:

WH-A
3 kg
```

Suppose:

```text
3 kg → Hyperlocal
SLA = 2 hours

Current:

19:30

Rain:

+30 min
```

Result:

```text
19:30
+0:30
+2:00
------
22:00

Parcel 1:

Today 10 PM

Parcel 2:

WH-B
2 kg
```

Suppose:

```text
2 kg → Next-day
SLA = 1 day

Cutoff:

6 PM

Current:

19:30
```

So:

```text
SET Saturday 9 AM
```

Then:

```text
+1 day
=
Sunday 9 AM
```

Final:

```text
Sunday 10 PM
```

Therefore:

```text
Parcel 1 → Today 10 PM
Parcel 2 → Sunday 10 PM
```

## 61. What does the customer see?

For individual parcels:

```text
Shipment 1
    Today by 10 PM

Shipment 2
    Sunday by 10 PM
```

For SKU-A:

```text
SKU-A × 2
```

Since one unit arrives today and one Sunday:

```text
SKU-A complete → Sunday 10 PM
```

So the cart may show:

```text
SKU-A × 2
Delivery by Sunday 10 PM

SKU-B × 1
Delivery by Today 10 PM
```

<!-- ➕ added:start -->

**➕ Added diagram — the full worked example (sections 58–62) on one page**

```text
 CUSTOMER   lat/lng = X/Y · pincode = 122018 · cart: SKU-A × 2, SKU-B × 1
                                        │
                                        ▼
           lat/lng → H3 cell → Polygon-A (WH-A priority 1, WH-B priority 2)
                                        │
                                        ▼
                   ┌────────────────────┴────────────────────┐
                   ▼                                         ▼
 ┌────────────────────────────────────┐    ┌────────────────────────────────────┐
 │ WH-A                limit 5 kg     │    │ WH-B                limit 8 kg     │
 │ SKU-A × 1  (2 kg)                  │    │ SKU-A × 1  (2 kg)                  │
 │ SKU-B × 1  (1 kg)                  │    │                                    │
 │ Parcel 1 = 3 kg                    │    │ Parcel 2 = 2 kg                    │
 │ 3 kg → Hyperlocal, SLA = 2 hours   │    │ 2 kg → Next-day, SLA = 1 day       │
 │ 19:30 +0:30 rain +2:00             │    │ 19:30 > 6 PM → SET Saturday 9 AM   │
 │                                    │    │ +1 day → Sunday 9 AM               │
 │                                    │    │ SET 22:00                          │
 │ → Today 10 PM                      │    │ → Sunday 10 PM                     │
 └─────────────────┬──────────────────┘    └─────────────────┬──────────────────┘
                   └────────────────────┬────────────────────┘
                                        ▼
        SKU-A × 2 → MAX(Today 10 PM, Sunday 10 PM) = Sunday 10 PM
        SKU-B × 1 → Today 10 PM
                                        │ order placed
                                        ▼
        WH-A hyperlocal slot → count +1        WH-B next-day slot → count +1
```

<!-- ➕ added:end -->

## 62. After order placement

Now capacity comes into play.

```text
Order uses:

WH-A hyperlocal
WH-B next-day
```

So:

```text
WH-A hyperlocal slot
       ↓
count +1

WH-B next-day slot
       ↓
count +1
```

Suppose WH-B's slot becomes full.

```text
Future request:

Customer 2

will see:

WH-B
next-day
slot full
     ↓
capacity delay
     ↓
later promise
```

So the system forms a feedback loop:

```text
               ┌──────────────────┐
               │  Promise Engine  │
               └────────┬─────────┘
                        │
                        ▼
                    Customer
                        │
                        ▼
                     Order
                        │
                        ▼
                  Capacity count
                        │
                        ▼
               changes future promise
                        │
                        └──────────────┐
                                       │
                                       ▼
                              Promise Engine
```

That's one of the most important architectural ideas in the whole system.

## 63. The complete mental model

You should remember the system as five decisions.

```text
1. WHERE?
   │
   ├── H3
   ├── Polygon
   ├── Pincode
   ├── City
   └── State

        ↓

2. FROM WHERE?
   │
   ├── Warehouse priority
   ├── Inventory
   ├── Per-request ledger
   └── All-or-nothing

        ↓

3. HOW MANY PARCELS?
   │
   ├── Group by warehouse
   ├── Weight limit
   ├── One unit at a time
   └── Free items ride along

        ↓

4. WHEN?
   │
   ├── Weight → delivery type
   ├── Cutoff
   ├── Operational delay
   ├── Rain
   ├── Capacity
   ├── Tags
   ├── SLA
   ├── Pickup calendar
   ├── Delivery calendar
   └── Final time-of-day

        ↓

5. WHAT CHANGES FOR FUTURE ORDERS?
   │
   └── Capacity counters
```

## 64. The most important backend concepts hidden inside this design

If you're preparing to explain this in an interview, don't memorize the prose. Understand these 10 engineering concepts:

### 1. Spatial indexing

```text
lat/lng → H3 → indexed lookup
```

Instead of expensive geometry at request time.

### 2. Hierarchical fallback

```text
Polygon
   ↓
Pincode
   ↓
City
   ↓
State
```

And only unresolved SKUs move to the next level.

### 3. Greedy inventory allocation

```text
nearest/priority warehouse
        ↓
take what you can
        ↓
move to next warehouse
```

### 4. Request-scoped state

```text
inventory
    +
request ledger
```

The ledger prevents duplicate allocation inside one request.

It isn't a distributed reservation.

### 5. Bin packing

Parcelization is essentially a constrained packing problem:

```text
items
  ↓
sort
  ↓
add units
  ↓
weight limit
  ↓
new parcel
```

It isn't sophisticated optimal bin packing; it's a deterministic greedy strategy.

### 6. Temporal rule engine

Delivery calculation is basically:

```text
datetime
   ↓
SET
   ↓
ADD
   ↓
ADD
   ↓
WALK
   ↓
SET
```

The crucial distinction is:

```text
ADD ≠ SET
```

### 7. Multiple clocks

```text
pickup clock
delivery clock
```

because warehouse availability and customer availability are different constraints.

### 8. Feedback loop

```text
orders
  ↓
capacity
  ↓
delay
  ↓
future promise
```

The system isn't purely deterministic from inventory/configuration; previous orders affect future results.

### 9. Cache vs consistency

```text
Redis
 ↓
fast
 ↓
5-min stale
```

You need to decide which data can tolerate that staleness.

### 10. Failure semantics

For every dependency, ask:

```text
Can I safely answer without it?
        │
       / \
     YES   NO
      │     │
   fail-open fail-closed
```

But there's a third category:

```text
fail-open with unsafe optimistic data
```

which is often worse than simply failing.

## 65. One final diagram to memorize

If I had to reduce the entire architecture to one interview diagram, I'd draw this:

```text
                         CUSTOMER
                            │
                 location + cart + qty
                            │
                            ▼
                  ┌──────────────────┐
                  │ SERVICEABILITY   │
                  │                  │
                  │ lat/lng → H3     │
                  │      ↓           │
                  │ Polygon          │
                  │      ↓           │
                  │ Pincode          │
                  │      ↓           │
                  │ City → State     │
                  └────────┬─────────┘
                           │
                           ▼
                  ┌──────────────────┐
                  │ INVENTORY        │
                  │                  │
                  │ zone priority    │
                  │      ↓           │
                  │ warehouse stock  │
                  │      ↓           │
                  │ request ledger   │
                  └────────┬─────────┘
                           │
                           ▼
                  ┌──────────────────┐
                  │ PARCELIZATION    │
                  │                  │
                  │ group by WH      │
                  │      ↓           │
                  │ weight limit     │
                  │      ↓           │
                  │ parcel(s)        │
                  └────────┬─────────┘
                           │
                           ▼
                  ┌──────────────────┐
                  │ PROMISE ENGINE   │
                  │                  │
                  │ weight           │
                  │   ↓              │
                  │ delivery type    │
                  │   ↓              │
                  │ cutoff [SET]     │
                  │   ↓              │
                  │ delays [ADD]     │
                  │   ↓              │
                  │ SLA [ADD]        │
                  │   ↓              │
                  │ calendars        │
                  │   ↓              │
                  │ final time [SET] │
                  └────────┬─────────┘
                           │
                           ▼
                  DELIVERY PROMISE
                           │
                    "Sunday 10 PM"
                           │
                           ▼
                    ORDER PLACED
                           │
                           ▼
                  ┌──────────────────┐
                  │ CAPACITY         │
                  │ counter +1      │
                  └────────┬─────────┘
                           │
                           └──────────────►
                                affects
                           future promises
```

**The single most important thing to understand is that this is not merely a delivery-date calculator.**

It is a chain of four coupled decisions:

```text
Serviceability
      ↓
Inventory allocation
      ↓
Physical fulfillment / parcelization
      ↓
Temporal promise calculation
      ↓
Capacity feedback
```

If you understand why those decisions must happen in that order, you understand the architecture rather than just memorizing its rules.
