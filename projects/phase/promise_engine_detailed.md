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
- [66. The database — every table behind the promise](#66-the-database--every-table-behind-the-promise)

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

<!-- ➕ added:start -->

## 66. The database — every table behind the promise

**➕ Added — complete database diagram, and why each table exists**

Everything lives in **MySQL**. There are two kinds of tables:

- **Configuration tables.** The operations team manages these through the Control Tower: zones, warehouses, SLAs, cutoffs, buffers, capacity and rain. The engine reads them through its ORM models.
- **Inventory and pincode tables.** These are older, hold data synced from the ERP, and are read with plain SQL in the `promiseEngine` schema.

Redis sits in front of most reads as a 5-minute cache. It is a cache, not a store of record, so it's not in the diagram.

### 66.1 The whole picture — how the tables connect

Two tables are the hubs: **`clusters`** (delivery zones) and **`serving_entities`** (warehouses and darkstores). Almost everything else hangs off one of them.

```text
                                  ┌───────────────────────┐
                                  │ polygon_h3_indexes    │
                                  └──────────▲────────────┘
                                             │ many cells per polygon
  ┌───────────────────┐           ┌──────────┴────────────┐
  │ cluster_pincodes  │           │ geo_polygons          │
  │ cluster_cities    │           └──────────▲────────────┘
  │ cluster_states    │                      │
  └─────────┬─────────┘           ┌──────────┴────────────┐
            │ many                │ cluster_polygons      │  (zone ⇄ polygon, many-to-many)
            ▼                     └──────────┬────────────┘
  ┌──────────────────────────────────────────▼──────────────┐
  │                        clusters                         │   ← HUB 1: delivery zones
  └──────┬───────────────────────────────────────────┬──────┘
         │ many                                      │ many (cluster-scoped delays)
         ▼                                           ▼
  ┌───────────────────────────┐            ┌───────────────────────────┐
  │ cluster_warehouse_matrix  │            │ static_buffers            │──< static_buffer_areas
  │ (zone × warehouse ×       │            │                           │──< day_skip_buffer
  │  weight → type + SLA)     │            └─────────────▲─────────────┘
  └──────────────┬────────────┘                          │ many (warehouse-scoped delays)
                 │ many                                  │
                 ▼                                       │
  ┌──────────────────────────────────────────────────────┴──┐
  │                    serving_entities                     │   ← HUB 2: warehouses & darkstores
  └──┬────────────┬────────────┬────────────────────────────┘
     │ many       │ many       │ rain tables (66.5)
     ▼            ▼            ▼
  warehouse_   capacity_    rain_status · rain_buffer_matrix · rain_intensities_buffers
  cutoffs      buffers      rain_hourly_intensity · rain_accuweather_locations
                            rain_buffer_alerts · rain_buffer_approvals

  ─── not linked by keys, joined by name or by value ───────────────────────────
  EDDItemMaster ══ EdditemInventory      one column per warehouse, named after the warehouse
  warehouse_mapping                      ERP warehouse name → that column name
  cpinDataV2                             pincode → city, state (feeds the city/state levels)
  tag_buffers                            matched against EDDItemMaster.tags by text
```

`──<` means "one to many". The dotted section at the bottom holds tables that aren't connected by foreign keys. They're matched by a name or a value instead.

### 66.2 Serviceability — "where is the shopper, which zones?"

```text
 geo_polygons                     polygon_h3_indexes
 ┌───────────────────────┐        ┌──────────────────────┐
 │ id                    │◄──────┤ polygon_id            │
 │ name                  │        │ h3_index (indexed)   │
 │ geometry (polygon)    │        │ resolution (10)      │
 │ boundary_type         │        └──────────────────────┘
 │ status ACTIVE/…       │
 └──────────▲────────────┘
            │
 cluster_polygons                 clusters
 ┌───────────────────────┐        ┌──────────────────────┐
 │ polygon_id            │        │ id                   │
 │ cluster_id ───────────┼───────►│ name                 │
 └───────────────────────┘        │ type: polygon /      │
                                  │   pincode / city /   │
 cluster_pincodes  (cluster_id, pincode)  ───►│   state              │
 cluster_cities    (cluster_id, city_code)───►│ status (on/off)      │
 cluster_states    (cluster_id, state_code)──►└──────────────────────┘

 cpinDataV2:  cPin · city · state · stateFullName · required_sla_minutes · (feature flags)
```

| Table | Why it exists | Used at |
|---|---|---|
| `geo_polygons` | Stores each delivery polygon as a real map shape (WGS84). It is the source the hexagons are generated from. | Polygon save and re-index |
| `polygon_h3_indexes` | One row per (polygon, H3 cell) at resolution 10. A request turns lat/lng into one cell and looks it up here. **This is what makes the location lookup a single indexed query instead of a geometry test.** | Every request that has a location |
| `clusters` | A delivery zone. Its type is polygon, pincode, city or state. A zone is what links to warehouses. | Every level of the search |
| `cluster_polygons` | Links polygons to polygon zones, many-to-many | Lat/lng level |
| `cluster_pincodes` / `cluster_cities` / `cluster_states` | List which pincodes, cities or states make up a zone | Pincode, city and state levels |
| `cpinDataV2` | Turns a pincode into a city and state, which feed the city and state levels. It also stores the pincode's "required SLA minutes", used for the quick-delivery flag. No pincode row means the request is rejected. | Start of every request |

### 66.3 Sourcing and SLA — "which warehouse, which delivery type, how fast?"

```text
 serving_entities                         cluster_warehouse_matrix
 ┌──────────────────────────┐             ┌──────────────────────────────────┐
 │ id                       │◄────────────┤ warehouse_id                     │
 │ name  (= stock column)   │             │ cluster_id ──────► clusters      │
 │ type: warehouse/darkstore│             │ min_weight · max_weight (kg)     │
 │ location (point)         │             │ delivery_type (10 values)        │
 │ max_shipment_weight (g)  │             │ sla_value · sla_unit (min/hr/day)│
 │ capacity                 │             │ priority                         │
 │ status active/inactive/  │             │ UNIQUE (cluster, warehouse,      │
 │        maintenance       │             │         min_weight, max_weight)  │
 └──────────────────────────┘             └──────────────────────────────────┘
```

| Table | Why it exists | Used at |
|---|---|---|
| `serving_entities` | The warehouses and darkstores. Its **name** is also the column name in the stock table. Its **parcel weight limit** drives packing. Only active ones are considered. | Search, packing |
| `cluster_warehouse_matrix` | **The heart of the configuration.** For each zone and warehouse pair, it gives the **priority** used to rank warehouses in the search. It also gives each **weight slab's delivery type and SLA**. The unique key stops the same slab being defined twice for a pair (it does not catch two slabs whose ranges overlap). | Warehouse ranking (Lesson 2), weight lookup (Rule 1) |

### 66.4 Delivery-time rules — "cutoffs, delays, capacity, tags, non-working days"

```text
 serving_entities ──< warehouse_cutoffs
                      warehouse_id · delivery_type
                      start_time · end_time        (hyperlocal window)
                      cutoff_time                  (other types)
                      days_to_add · time           (where the clock is SET)
                      is_active

 serving_entities ──< capacity_buffers
                      warehouse_id · delivery_type
                      time_frame_start · time_frame_end   (one row = one slot)
                      capacity · buffer_value · buffer_unit
                      order_count · spill · breach_time   (live counters)
                      UNIQUE (warehouse, delivery_type, slot)

 clusters / serving_entities ──< static_buffers
                      buffer_scope: cluster_warehouse / warehouse / cluster
                      buffer_nature: time_addition / day_skip
                      cluster_id · warehouse_id
                      min_weight · max_weight · area_selection
                      buffer_value · buffer_unit · start_datetime · end_datetime
                         │
                         ├──< static_buffer_areas   area_type (polygon/pincode/city/state) · area_value
                         └──< day_skip_buffer       pickup_skip · delivery_skip          (weekdays)
                                                    pickup_date_skip · delivery_date_skip (dates)

 tag_buffers           tag · buffer_value (can be negative) · buffer_unit · active window
```

| Table | Why it exists | Pipeline step |
|---|---|---|
| `warehouse_cutoffs` | When a warehouse stops taking work for a delivery type: an operating window for hyperlocal, a daily cutoff for the rest. It also says **where to SET the clock** when the cutoff is missed (days to add, reset time). | Rule 2 (cutoff), and the day-skip re-anchor |
| `static_buffers` | The supply-chain team's planned delays, scoped to a zone, a warehouse or a pair. They can be limited by weight, area and date range. There are two natures: **time additions** and **non-working days**. | Rule 3 (delays) and the day-skip walks |
| `static_buffer_areas` | Restricts a delay to specific polygons, pincodes, cities or states | Rule 3 |
| `day_skip_buffer` | The non-pickup and non-delivery weekdays and dates belonging to a day-skip delay, one value per row | The two calendar walks |
| `capacity_buffers` | **The only table the promise flow writes to.** Each row is one time slot for one warehouse and delivery type, holding a capacity and live counters. When orders plus carried-over spill reach capacity, the slot's delay is added. | Rule 3 (capacity), and the order-count feedback loop (Lesson 5) |
| `tag_buffers` | Extra time (or less time) for products carrying a given tag. They're matched by text against the item master's tags. | Rule 3 (tags) |

### 66.5 Rain — "watch the weather, decide, approve, apply"

```text
 serving_entities ──1 rain_accuweather_locations   accuweather_location_key       (which forecast point)
                  ──1 rain_buffer_matrix           pre_rain_lead_minutes ·
                  │                                post_rain_cooldown_minutes · is_active
                  │        └──< rain_intensities_buffers   rain_intensity_label · duration ·
                  │                                       buffer_value   (the lookup table)
                  ──< rain_hourly_intensity        hour_start_at · precipitation intensity
                  ──1 rain_status                  is_raining · intensity · spell start/end ·
                  │                                buffer_active · buffer_value_minutes ·
                  │                                manual_override · last_checked_at
                  │        └──► rain_buffer_approvals (active approval)
                  ──< rain_buffer_alerts           activated / deactivated / updated events

 rain_buffer_approval_batches ──< rain_buffer_approvals ──► serving_entities
   (one batch per city, Telegram message, expiry)   (suggested vs applied minutes, who responded)

 rain_buffer_approval_settings   approval on/off · timeout minutes · timeout action ·
                                 active hours · outside-hours action
```

| Table | Why it exists |
|---|---|
| `rain_accuweather_locations` | Maps a warehouse to its weather-service location key, so the poll knows where to ask |
| `rain_buffer_matrix` | Turns rain buffering on for a warehouse, and sets how early to start before rain and how long to keep the delay after it stops. Only warehouses with an active row are polled. |
| `rain_intensities_buffers` | The lookup table: intensity label × how long it has rained → delay minutes |
| `rain_hourly_intensity` | The hourly intensity forecast per warehouse. The frequent poll reads the previous hour's value to know *how hard* it's raining. |
| `rain_status` | **The one rain table the promise engine reads on every request.** It holds the current decision per warehouse: is it raining, is a delay active, and how many minutes. |
| `rain_buffer_approval_batches` / `rain_buffer_approvals` | The human-approval workflow. Each batch is one Telegram message per city, and each approval row records one warehouse's suggested and applied delay and who responded. |
| `rain_buffer_approval_settings` | The knobs: whether approval is needed, the timeout (default 10 min, then auto-approve), and the active hours |
| `rain_buffer_alerts` | An audit trail of rain delays being switched on, changed or off |

### 66.6 Inventory — "who has the stock?" (ERP-synced, plain SQL)

```text
 EDDItemMaster                          EdditemInventory
 ┌──────────────────────────────┐       ┌───────────────────────────────────────────┐
 │ skuId          ══════════════╪══════►│ skuCode                                   │
 │ weight (kg)                  │ inner │ WH_A  WH_B  DKS_C  …  (one column per     │
 │ Type: SIMPLE / BUNDLE        │ join  │                        warehouse, holding │
 │ componentSkusData (bundles)  │       │                        its quantity)      │
 │ status                       │       └───────────────────────────────────────────┘
 │ tags   ──► matched by tag_buffers   ▲
 └──────────────────────────────┘                     │ column chosen via
                                        warehouse_mapping (erpWarehouseName → ucWarehouseName)
```

| Table | Why it exists | Who writes it |
|---|---|---|
| `EDDItemMaster` | Per SKU: **weight** (for SLA slabs and parcel packing), simple or bundle, bundle components, and **tags** (for tag delays). The engine **inner-joins** it to stock, so a SKU with no master row is invisible and shows as out of stock. | ERP full snapshots, and the bundle sync job. Realtime stock deltas never touch it. |
| `EdditemInventory` | Stock per SKU. It's a **wide table**: one column per warehouse. One read returns a SKU's stock everywhere, but every new warehouse needs a new column. | ERP realtime webhook (only the warehouses in the message), full snapshots, and the bundle job (bundle stock = the scarcest component's complete bundles) |
| `warehouse_mapping` | Translates the ERP's warehouse names into the names used as stock columns and on the warehouse records. Ingestion reads it through a one-hour Redis cache. The warehouse-pinned promise also reads it. | Only read in this codebase |

### 66.7 Admin and protection (not part of the promise math)

| Table | Why it exists |
|---|---|
| `rate_limit_endpoints` | Which API endpoints are rate-limited. The live limiter keeps its token buckets in Redis; this table only says which endpoints are enrolled. |
| `rate_limit_tracking` | Per-IP counters. Only the admin cache screens use it; the live limiter doesn't. |
| `control_panel_users` | Who can use the Control Tower admin console, and their role |
| `audit_logs` | A record of admin operations made through the Control Tower |

### 66.8 How one cart request walks the tables

```text
 cpinDataV2 ─► (polygon_h3_indexes ─► geo_polygons ─► cluster_polygons)
           ─► cluster_pincodes / cluster_cities / cluster_states ─► clusters
           ─► cluster_warehouse_matrix + serving_entities          (ranked warehouses)
           ─► EDDItemMaster ⋈ EdditemInventory                     (stock per warehouse)
           ─► cluster_warehouse_matrix                             (weight → type + SLA)
           ─► warehouse_cutoffs · static_buffers (+ areas, day skips)
              · capacity_buffers · tag_buffers · rain_status        (delivery-time rules)
           ─► promise
 order placed ─► capacity_buffers  (order_count + 1, spill → next slot)   ← the only write
```

### 66.9 How values get into each table (inserts and updates)

Rows arrive through six different paths. Knowing which path owns a table tells you how fresh it is and who to blame when it's wrong.

```text
  ① Admin console (Control Tower API) ── one row at a time: create · edit · delete
  ② Bulk upload (CSV / KML files)      ── many new rows at once, inside one transaction
  ③ Derived automatically              ── regenerated whenever its source row changes
  ④ ERP data sync                      ── upserts from webhooks and scheduled snapshots
  ⑤ Live order flow                    ── counters bumped when an order is counted
  ⑥ Weather jobs                       ── rain decisions written on every poll
```

**Configuration tables (written by people)**

| Table | Inserted by | Updated by | How |
|---|---|---|---|
| `clusters` | ① | ① | Single-row create and edit |
| `cluster_pincodes` / `cluster_cities` / `cluster_states` / `cluster_polygons` | ① when a zone is built or edited | ① (add or remove members) | One row per pincode, city, state or polygon in the zone |
| `geo_polygons` | ① (a drawn GeoJSON shape) or ② (CSV / KML; multi-part shapes are merged into one) | ① | Saving a polygon also regenerates its H3 cells (③) |
| `serving_entities` | ① | ① | Single-row create and edit |
| `cluster_warehouse_matrix` | ① or ② | ① | Each row is one weight slab for a zone–warehouse pair |
| `warehouse_cutoffs` | ① or ② | ① | Hyperlocal rows must have a window; other rows must have a cutoff time |
| `static_buffers` | ① or ② | ① | Created together with its areas and day-skip rows |
| `static_buffer_areas` | With its buffer (① or ②) | ① **replaces** the list: delete old rows, insert new ones | |
| `day_skip_buffer` | With its buffer (① or ②) | ① (rows added or removed) | One weekday or date per row |
| `capacity_buffers` | ① or ② (**one row per future time slot**, created in advance) | ① for settings; ⑤ for the live counters | No job resets counters; a new slot is simply a new row starting at zero |
| `tag_buffers` | ① or ② | ① | Tags are trimmed and upper-cased on save |
| `rain_buffer_matrix` | ① | ① | Turns rain buffering on for a warehouse |
| `rain_intensities_buffers` | ① with its matrix | ① **replaces** the lookup rows: delete, then insert | |
| `rain_buffer_approval_settings` | Created with defaults when none exist | ① | A single settings row |
| `rain_accuweather_locations` | An admin-triggered sync that finds the weather location key for each hyperlocal warehouse | The same sync | |
| `control_panel_users` | ① | ① | |

**Derived, synced and live tables (written by the system)**

| Table | Inserted by | Updated by | How |
|---|---|---|---|
| `polygon_h3_indexes` | ③ on polygon save, plus a full re-index endpoint | Never edited in place | **Delete all of that polygon's cells, then re-insert** them in batches. There is no transaction, so a lookup during a rebuild can briefly miss the polygon. |
| `EDDItemMaster` | ④ ERP full snapshots, the bundle sync job, and an item-status job | The same jobs | Upsert (insert, or update if the SKU exists). **Realtime webhook deltas never write here**, so a brand-new SKU waits for a snapshot. |
| `EdditemInventory` | ④ ERP realtime webhook (through Pub/Sub), full snapshots, and the bundle job | The same | Upsert **one warehouse column at a time**. Webhook deltas touch only the warehouses in the message. Snapshots write every warehouse, including zeros. The bundle job writes each bundle's buildable count. |
| `capacity_buffers` (counters) | — | ⑤ when the order-complete flow asks for a counted promise | One **atomic** `order_count + 1`, with a breach time stamped once. The overflow is then written to the next slot's `spill` (a separate read-then-write). |
| `rain_status` | ⑥ created the first time a warehouse is polled | ⑥ every poll; approvals and auto-approvals | Holds the current decision: raining?, buffer active?, minutes |
| `rain_hourly_intensity` | ⑥ hourly job | ⑥ | **Upsert by (warehouse, hour)** |
| `rain_buffer_approval_batches` / `rain_buffer_approvals` | ⑥ when a delay needs approval (one batch per city) | Approve link, or the timeout job (default: auto-approve after 10 min) | Approving also writes the delay into `rain_status` |
| `rain_buffer_alerts` | ⑥ on each switch-on, change or switch-off | Never | Append-only history |
| `audit_logs` | Every admin request, through middleware | Never | Append-only |

**Tables this service only reads**

| Table | Note |
|---|---|
| `cpinDataV2` | Pincode → city, state and required SLA minutes. Nothing in this codebase writes it. |
| `warehouse_mapping` | ERP warehouse name → engine warehouse name. Nothing in this codebase writes it. |
| `rate_limit_endpoints` | Which endpoints are rate-limited. There's no create path in the code, so rows are added outside the application. |

**One consequence to remember:** no admin write clears the promise engine's cache. A change made in the Control Tower, such as a new cutoff, buffer or SLA row, starts affecting promises when the cached copy expires, which is within about 5 minutes by default.

**Things to remember about the database:**

1. **Two hubs.** `clusters` (zones) and `serving_entities` (warehouses) hold almost everything else together.
2. **The SLA matrix is the centre of the configuration.** It ranks warehouses and turns weight into a delivery type and SLA.
3. **H3 cells are pre-computed into a table**, so a location lookup is a single indexed query.
4. **Stock is a wide table**, one column per warehouse. Reads are fast, but every new warehouse means a schema change.
5. **Only `capacity_buffers` is written by the promise flow**, and only when an order is counted. Everything else is configuration or synced data.
6. **Six write paths:** admin edits, bulk uploads, derived H3 cells, ERP sync, order counting and weather jobs. Admin changes reach promises only after the ~5-minute cache expires.

<!-- ➕ added:end -->



<!-- ➕ DB schema:start -->

// Promise Engine — complete MySQL schema
// Paste this whole file into https://dbdiagram.io/d
//
// Sources: the 29 Control Tower ORM models and the warehouse_mapping model (columns, types,
// defaults, unique keys), plus the plain SQL for EDDItemMaster and EdditemInventory (no model).
// Single-column helper indexes are left out; every unique / composite key is kept.
//
// Line colours:
//   default (dark)  = foreign key or ORM association declared in code
//   grey  #9E9E9E   = no key; the code matches these columns by value

Project promise_engine {
  database_type: 'MySQL'
  Note: '''
  Two hubs hold the configuration together: clusters (delivery zones) and serving_entities (warehouses and darkstores).
  Configuration tables are written by people through the Control Tower. Stock tables are written by ERP sync jobs.
  The promise flow itself writes only capacity_buffers counters. Redis caches reads for about 5 minutes and is not shown.
  '''
}

// ─────────────────────────────────────────── Enums

Enum cluster_type {
  "polygon"
  "pincode"
  "city"
  "state"
}

Enum delivery_type {
  "hyperlocal"
  "hyperlocal B"
  "SDD A"
  "SDD B"
  "SDD C"
  "NDD A"
  "NDD B"
  "NDD C"
  "Standard A"
  "Standard B"
}

Enum buffer_unit {
  "minutes"
  "hours"
  "days"
}

Enum rain_label_forecast {
  "light"
  "moderate"
  "heavy"
}

Enum rain_label_status {
  "none"
  "light"
  "moderate"
  "heavy"
  "extreme"
}

Enum timeout_action {
  "auto_approve"
  "auto_reject"
}

// ─────────────────────────────────────────── 1. Serviceability — "where is the shopper, which zones?"

Table geo_polygons [headercolor: #1E88E5] {
  id bigint [pk, increment]
  name varchar(255) [not null, unique]
  description text
  geometry geometry [not null, note: 'POLYGON, SRID 4326 (WGS84)']
  boundary_type varchar [not null, default: 'CUSTOM', note: 'CUSTOM / PINCODE / CITY / STATE']
  status varchar [not null, default: 'ACTIVE', note: 'ACTIVE / INACTIVE / DRAFT']
  metadata json
  created_by varchar(100) [not null]
  updated_by varchar(100)
  created_at datetime
  updated_at datetime

  Note: '''
  WHY: each delivery polygon stored as a real map shape. It is the source the H3 cells are generated from.
  WRITTEN BY: admin console (drawn GeoJSON) or bulk upload (CSV / KML; multi-part shapes merged into one).
  Saving a polygon regenerates its rows in polygon_h3_indexes.
  '''
}

Table polygon_h3_indexes [headercolor: #1E88E5] {
  id bigint [pk, increment]
  polygon_id bigint [not null]
  h3_index varchar(20) [not null, note: 'indexed — the lookup column']
  resolution int [not null, note: '0–15; the engine uses 10']
  created_at datetime [not null]
  updated_at datetime [not null]

  indexes {
    h3_index
    (polygon_id, h3_index) [unique, name: 'unique_polygon_h3_index']
  }

  Note: '''
  WHY: one row per (polygon, H3 cell). A request turns lat/lng into one cell and looks it up here,
  so finding the shopper's polygon is one indexed query, not a geometry test.
  WRITTEN BY: derived on polygon save, plus a full re-index endpoint.
  HOW: delete all of that polygon's cells, then re-insert in batches (no transaction).
  '''
}

Table clusters [headercolor: #1E88E5] {
  id bigint [pk, increment]
  name varchar(255) [not null, unique]
  type cluster_type [not null]
  status boolean [not null, default: true, note: 'zone on / off']
  description varchar(1000)
  metadata json
  created_at datetime [not null]
  updated_at datetime [not null]

  Note: '''
  HUB 1 — a delivery zone. Its type says which member table defines it (polygons, pincodes, cities or states).
  A zone is what gets linked to warehouses in cluster_warehouse_matrix.
  WRITTEN BY: admin console, one row at a time.
  '''
}

Table cluster_polygons [headercolor: #1E88E5] {
  id bigint [pk, increment]
  cluster_id bigint [not null]
  polygon_id bigint [not null]
  created_at datetime [not null]
  updated_at datetime [not null]

  indexes {
    (cluster_id, polygon_id) [unique, name: 'unique_cluster_polygon']
  }

  Note: '''
  WHY: links polygons to polygon-type zones (many-to-many). Used at the lat/lng search level.
  WRITTEN BY: admin console when a zone is built or edited.
  '''
}

Table cluster_pincodes [headercolor: #1E88E5] {
  id bigint [pk, increment]
  cluster_id bigint [not null]
  pincode varchar(10) [not null]
  created_at datetime [not null]
  updated_at datetime [not null]

  indexes {
    (cluster_id, pincode) [unique, name: 'unique_cluster_pincode']
  }

  Note: '''
  WHY: the pincodes that make up a pincode-type zone. Used at the pincode search level.
  WRITTEN BY: admin console (add / remove members) or bulk upload.
  '''
}

Table cluster_cities [headercolor: #1E88E5] {
  id bigint [pk, increment]
  cluster_id bigint [not null]
  city_code varchar(50) [not null, note: 'matched against cpinDataV2.city']
  created_at datetime [not null]
  updated_at datetime [not null]

  indexes {
    (cluster_id, city_code) [unique, name: 'unique_cluster_city']
  }

  Note: '''
  WHY: the cities that make up a city-type zone. Used at the city search level.
  WRITTEN BY: admin console or bulk upload.
  '''
}

Table cluster_states [headercolor: #1E88E5] {
  id bigint [pk, increment]
  cluster_id bigint [not null]
  state_code varchar(50) [not null, note: 'matched against cpinDataV2.state']
  created_at datetime [not null]
  updated_at datetime [not null]

  indexes {
    (cluster_id, state_code) [unique, name: 'unique_cluster_state']
  }

  Note: '''
  WHY: the states that make up a state-type zone. Used at the state search level (the last fallback).
  WRITTEN BY: admin console or bulk upload.
  '''
}

Table cpinDataV2 [headercolor: #1E88E5] {
  id bigint [pk, increment]
  cPin int [not null, unique]
  city varchar(45)
  state varchar(45)
  stateFullName varchar(45)
  required_sla_minutes int [note: 'not declared in the model; read by the engine for the quick-delivery flag']
  is_ucj boolean [default: false]
  is_ucj_web boolean [default: false]
  is_ucj_web_gift_applicable boolean [default: false]
  is_ucj_gift_applicable boolean [default: false]
  is_serviceable_for_healthcare boolean [default: false]

  Note: '''
  WHY: turns a pincode into a city and state, which feed the city and state search levels.
  No row for the pincode means the request is rejected.
  WRITTEN BY: nothing in this codebase — read only.
  '''
}

// ─────────────────────────────────────────── 2. Sourcing and SLA — "which warehouse, which type, how fast?"

Table serving_entities [headercolor: #8E24AA] {
  id bigint [pk, increment]
  name varchar(255) [not null, note: 'also the column name for this warehouse in EdditemInventory']
  type varchar [not null, note: 'warehouse / darkstore']
  location geometry [not null, note: 'POINT, SRID 4326']
  address varchar(500)
  contact_person varchar(100)
  contact_phone varchar(20)
  contact_email varchar(100)
  capacity int
  max_shipment_weight int [not null, default: 1000, note: 'grams — parcel weight limit used by packing']
  status varchar [not null, default: 'active', note: 'active / inactive / maintenance; only active is considered']
  metadata json
  created_at datetime [not null]
  updated_at datetime [not null]

  Note: '''
  HUB 2 — the warehouses and darkstores.
  WHY: its name is the stock column; its max_shipment_weight drives parcel packing.
  WRITTEN BY: admin console, one row at a time.
  '''
}

Table cluster_warehouse_matrix [headercolor: #8E24AA] {
  id bigint [pk, increment]
  cluster_id bigint [not null]
  warehouse_id bigint [not null]
  min_weight float [not null, note: 'kg']
  max_weight float [not null, note: 'kg; must be > min_weight']
  delivery_type delivery_type [not null]
  sla_value int [not null]
  sla_unit varchar [not null, note: 'min / hour / day']
  priority int [not null, note: '>= 1; ranks warehouses for a zone']
  created_at datetime [not null]
  updated_at datetime [not null]

  indexes {
    (cluster_id, priority)
    (cluster_id, warehouse_id) [name: 'idx_cluster_warehouse_lookup']
    (cluster_id, warehouse_id, min_weight, max_weight) [unique, name: 'unique_cluster_warehouse_weight']
  }

  Note: '''
  THE HEART OF THE CONFIGURATION. For each zone + warehouse pair:
  - priority ranks the warehouses in the search;
  - each weight slab gives the delivery type and SLA.
  The unique key stops an identical slab twice; it does not catch overlapping ranges.
  WRITTEN BY: admin console or bulk upload.
  '''
}

// ─────────────────────────────────────────── 3. Delivery-time rules — cutoffs, delays, capacity, tags, day skips

Table warehouse_cutoffs [headercolor: #FB8C00] {
  id bigint [pk, increment]
  warehouse_id bigint [not null]
  delivery_type delivery_type [not null]
  start_time time [note: 'hyperlocal window start (required for hyperlocal types)']
  end_time time [note: 'hyperlocal window end (required for hyperlocal types)']
  cutoff_time time [note: 'daily cutoff (required for non-hyperlocal types)']
  days_to_add int [not null, default: 0, note: 'after cutoff: days to move forward']
  time time [note: 'after cutoff: the time the clock is SET to']
  is_active boolean [not null, default: true]
  created_at datetime [not null]
  updated_at datetime [not null]

  indexes {
    (warehouse_id, delivery_type, is_active)
  }

  Note: '''
  WHY: when a warehouse stops taking work for a delivery type, and where to SET the clock when that cutoff is missed.
  Pipeline: Rule 2 (cutoff) and the day-skip re-anchor.
  WRITTEN BY: admin console or bulk upload.
  '''
}

Table static_buffers [headercolor: #FB8C00] {
  id bigint [pk, increment]
  cluster_id bigint [note: 'required for cluster and cluster_warehouse scope']
  warehouse_id bigint [note: 'required for warehouse and cluster_warehouse scope']
  buffer_scope varchar [not null, note: 'cluster_warehouse / warehouse / cluster']
  buffer_nature varchar [not null, note: 'time_addition / day_skip']
  min_weight decimal(10,3) [note: 'kg']
  max_weight decimal(10,3) [note: 'kg']
  area_selection varchar [not null, default: 'all_areas', note: 'all_areas / specific_areas']
  buffer_unit buffer_unit [not null, default: 'days']
  buffer_value int [not null, default: 0, note: '0–365']
  start_datetime datetime [not null]
  end_datetime datetime [not null]
  is_active boolean [not null, default: true]
  created_at datetime [not null]
  updated_at datetime [not null]

  indexes {
    (warehouse_id, buffer_scope)
    (cluster_id, buffer_scope)
    (warehouse_id, is_active)
    (cluster_id, is_active)
    (min_weight, max_weight)
  }

  Note: '''
  WHY: the supply-chain team planned delays, scoped to a zone, a warehouse or a pair,
  optionally limited by weight, area and date range. Two natures: time additions and non-working days.
  Pipeline: Rule 3 (delays) and the two day-skip walks.
  WRITTEN BY: admin console or bulk upload, together with its areas and day-skip rows.
  '''
}

Table static_buffer_areas [headercolor: #FB8C00] {
  id bigint [pk, increment]
  static_buffer_id bigint [not null]
  area_type cluster_type [not null]
  area_value varchar(255) [not null, note: 'polygon id, pincode, city or state, depending on area_type']
  created_at datetime [not null]
  updated_at datetime [not null]

  indexes {
    (area_type, area_value)
    (static_buffer_id, area_type, area_value) [unique]
  }

  Note: '''
  WHY: restricts a static buffer to specific polygons, pincodes, cities or states.
  WRITTEN BY: with its buffer. An edit REPLACES the list: delete old rows, insert new ones.
  '''
}

Table day_skip_buffer [headercolor: #FB8C00] {
  id bigint [pk, increment]
  static_buffer_id bigint [not null]
  pickup_skip varchar(10) [note: 'a weekday with no pickup']
  delivery_skip varchar(10) [note: 'a weekday with no delivery']
  pickup_date_skip date [note: 'a specific date with no pickup']
  delivery_date_skip date [note: 'a specific date with no delivery']
  created_at datetime [not null]
  updated_at datetime [not null]

  Note: '''
  WHY: the non-pickup and non-delivery weekdays and dates of a day_skip static buffer, one value per row.
  Pipeline: the pickup-day walk and the delivery-day walk.
  WRITTEN BY: with its buffer (admin console or bulk upload).
  '''
}

Table capacity_buffers [headercolor: #FB8C00] {
  id bigint [pk, increment]
  warehouse_id bigint [not null]
  delivery_type delivery_type [not null]
  time_frame_start datetime [not null, note: 'one row = one time slot']
  time_frame_end datetime [not null]
  capacity int [not null, note: '>= 1; max orders in the slot']
  buffer_unit buffer_unit [not null, default: 'days']
  buffer_value int [not null, default: 0, note: 'delay added once the slot is breached']
  is_active boolean [not null, default: true]
  order_count bigint [not null, default: 0, note: 'LIVE counter: atomic +1 per counted order']
  spill bigint [not null, default: 0, note: 'LIVE: overflow carried in from the previous slot']
  breach_time datetime [note: 'stamped once, when the slot first breaches']
  created_at datetime [not null]
  updated_at datetime [not null]

  indexes {
    (warehouse_id, delivery_type, time_frame_start, time_frame_end) [unique, name: 'unique_warehouse_delivery_timeframe']
    (warehouse_id, is_active)
    (delivery_type, is_active)
  }

  Note: '''
  WHY: per-slot order capacity. Breached when order_count + spill >= capacity; then buffer_value is added.
  THE ONLY TABLE THE PROMISE FLOW WRITES.
  WRITTEN BY: admin console or bulk upload create the slots in advance (no job resets counters;
  a new slot is a new row starting at zero). The order-complete flow bumps order_count and writes spill to the next slot.
  '''
}

Table tag_buffers [headercolor: #FB8C00] {
  id bigint [pk, increment]
  tag varchar(255) [not null, note: 'trimmed and upper-cased on save']
  buffer_unit buffer_unit [not null, default: 'minutes']
  buffer_value int [not null, note: 'can be negative (less time); cannot be zero']
  description text
  is_active boolean [not null, default: true]
  start_date_time datetime
  end_date_time datetime
  created_at datetime [not null]
  updated_at datetime [not null]

  indexes {
    (tag, is_active)
    (start_date_time, end_date_time)
  }

  Note: '''
  WHY: extra (or less) time for products carrying a tag. Matched by text against EDDItemMaster.tags.
  Pipeline: Rule 3 (tags).
  WRITTEN BY: admin console or bulk upload.
  '''
}

// ─────────────────────────────────────────── 4. Rain — watch the weather, decide, approve, apply

Table rain_accuweather_locations [headercolor: #00897B] {
  warehouse_id bigint [pk]
  accuweather_location_key varchar(32) [not null]
  created_at datetime [not null]
  updated_at datetime [not null]

  Note: '''
  WHY: maps a warehouse to its weather-service location key, so the poll knows where to ask.
  WRITTEN BY: an admin-triggered sync over hyperlocal warehouses.
  '''
}

Table rain_buffer_matrix [headercolor: #00897B] {
  id bigint [pk, increment]
  warehouse_id bigint [not null]
  pre_rain_lead_minutes int [not null, default: 15]
  post_rain_cooldown_minutes int [not null, default: 20]
  is_active boolean [not null, default: true]
  created_at datetime [not null]
  updated_at datetime [not null]

  indexes {
    (warehouse_id, is_active)
  }

  Note: '''
  WHY: turns rain buffering on for a warehouse; sets how early to start before rain and how long to hold after it stops.
  Only warehouses with an active row are polled.
  WRITTEN BY: admin console.
  '''
}

Table rain_intensities_buffers [headercolor: #00897B] {
  warehouse_id bigint [not null]
  rain_intensity_label rain_label_forecast [not null]
  duration int [not null, note: 'duration bucket, minutes']
  buffer_value int [not null, default: 0, note: 'delay minutes to add']

  indexes {
    (warehouse_id, rain_intensity_label, duration) [pk]
  }

  Note: '''
  WHY: the lookup table — intensity label x how long it has rained -> delay minutes.
  WRITTEN BY: admin console with its matrix. An edit REPLACES the rows: delete, then insert.
  '''
}

Table rain_hourly_intensity [headercolor: #00897B] {
  id bigint [pk, increment]
  warehouse_id bigint [not null]
  hour_start_at datetime [not null]
  has_precipitation boolean [not null, default: false]
  precipitation_type varchar(32)
  precipitation_intensity rain_label_forecast
  raw json
  created_at datetime [not null]
  updated_at datetime [not null]

  indexes {
    (warehouse_id, hour_start_at) [unique]
    hour_start_at
  }

  Note: '''
  WHY: hourly forecast per warehouse. The frequent poll reads the previous hour to know HOW HARD it is raining.
  WRITTEN BY: hourly weather job — upsert by (warehouse, hour).
  '''
}

Table rain_status [headercolor: #00897B] {
  id bigint [pk, increment]
  warehouse_id bigint [not null, unique]
  location_name varchar(255)
  lat double [not null]
  lng double [not null]
  is_raining boolean [not null, default: false]
  rain_intensity double [note: 'mm/hour']
  rain_intensity_label rain_label_status [not null, default: 'none']
  rain_started_at datetime
  rain_ended_at datetime
  rain_duration_minutes int
  rain_summary varchar(500)
  rain_expected_at datetime
  rain_expected_end_at datetime
  buffer_active boolean [not null, default: false]
  buffer_value_minutes int [not null, default: 0, note: 'the delay the promise engine adds']
  buffer_activated_at datetime
  last_digest_sent_at datetime
  manual_override boolean [not null, default: false]
  approved_cooldown_minutes int [note: 'overrides the matrix cooldown while this buffer is live']
  active_approval_id bigint
  last_checked_at datetime
  created_at datetime [not null]
  updated_at datetime [not null]

  indexes {
    buffer_active
  }

  Note: '''
  WHY: THE ONE RAIN TABLE THE PROMISE ENGINE READS ON EVERY REQUEST.
  The current decision per warehouse: raining? delay active? how many minutes?
  WRITTEN BY: weather jobs (created on the first poll, updated every poll), approvals and auto-approvals.
  '''
}

Table rain_buffer_approval_batches [headercolor: #00897B] {
  id varchar(64) [pk]
  city varchar(128) [not null]
  status varchar [not null, default: 'pending', note: 'pending / partially_actioned / completed / expired']
  warehouse_count int [not null, default: 0]
  pending_count int [not null, default: 0]
  timeout_action timeout_action [not null, default: 'auto_approve']
  timeout_minutes int [not null, default: 10]
  telegram_message_id varchar(64)
  expires_at datetime [not null]
  completed_at datetime
  created_at datetime [not null]
  updated_at datetime [not null]

  indexes {
    (status, expires_at)
  }

  Note: '''
  WHY: one approval request per city — one Telegram message — with an expiry.
  WRITTEN BY: weather job when a delay needs approval; closed by the approve link or the timeout job.
  '''
}

Table rain_buffer_approvals [headercolor: #00897B] {
  id bigint [pk, increment]
  batch_id varchar(64) [not null]
  warehouse_id bigint [not null]
  warehouse_name varchar(255)
  city varchar(128) [not null]
  intensity_label varchar(32) [not null]
  intensity_mm_hr double
  rain_duration_minutes int
  rain_summary varchar(500)
  buffer_value_suggested int [not null]
  cooldown_suggested int [not null]
  buffer_value_applied int
  cooldown_applied int
  status varchar [not null, default: 'pending', note: 'pending / approved / rejected / expired / cancelled']
  responded_by varchar(255)
  responded_at datetime
  response_source varchar [note: 'web_approval / auto_timeout / auto_outside_hours / rain_stopped']
  re_eligible_at datetime
  cancellation_reason varchar(64)
  buffer_applied_at datetime
  buffer_removed_at datetime
  created_at datetime [not null]
  updated_at datetime [not null]

  indexes {
    (warehouse_id, status)
    (status, re_eligible_at)
  }

  Note: '''
  WHY: one warehouse's suggested vs applied delay inside a batch, and who responded.
  WRITTEN BY: weather job; updated by the approve link or the timeout job (default: auto-approve after 10 min).
  Approving also writes the delay into rain_status.
  '''
}

Table rain_buffer_approval_settings [headercolor: #00897B] {
  id bigint [pk, increment]
  approval_enabled boolean [not null, default: true]
  approval_timeout_minutes int [not null, default: 10]
  timeout_action timeout_action [not null, default: 'auto_approve']
  rejection_cooldown_minutes int [not null, default: 30]
  active_hours_start varchar(5) [not null, default: '06:00']
  active_hours_end varchar(5) [not null, default: '23:00']
  outside_hours_action timeout_action [not null, default: 'auto_approve']
  escalation_needs_approval boolean [not null, default: true]
  page_poll_interval_seconds int [not null, default: 10]
  created_at datetime [not null]
  updated_at datetime [not null]

  Note: '''
  WHY: the knobs of the approval workflow. A single settings row.
  WRITTEN BY: created with defaults when missing; edited through the admin console.
  '''
}

Table rain_buffer_alerts [headercolor: #00897B] {
  id bigint [pk, increment]
  warehouse_id bigint [not null]
  location_name varchar(255)
  event_type varchar [not null, note: 'activated / deactivated / buffer_updated / digest']
  buffer_minutes_before int [not null, default: 0]
  buffer_minutes_after int [not null, default: 0]
  decision_case tinyint
  rain_summary varchar(500)
  rain_intensity double
  rain_intensity_label rain_label_status
  email_sent boolean [not null, default: false]
  email_error text
  metadata json
  created_at datetime [not null]

  indexes {
    (warehouse_id, created_at)
    (event_type, created_at)
  }

  Note: '''
  WHY: audit trail of rain delays being switched on, changed or off.
  WRITTEN BY: weather jobs. Append-only, never updated.
  '''
}

// ─────────────────────────────────────────── 5. Inventory — "who has the stock?" (ERP-synced, plain SQL)

Table EDDItemMaster [headercolor: #43A047] {
  skuId varchar [unique, note: 'upsert key (ON DUPLICATE KEY)']
  weight decimal [note: 'kg (ERP grams / 1000); drives SLA slabs and parcel packing']
  Type varchar [note: 'SIMPLE / BUNDLE']
  componentSkusData json [note: 'bundle components; for SIMPLE, the SKU itself']
  status int [note: '1 = active, 2 = inactive']
  tags varchar [note: 'comma-separated; read by the engine, written by no job in this codebase']

  Note: '''
  WHY: per-SKU weight, simple vs bundle, bundle components and tags.
  The engine INNER-JOINS it to EdditemInventory, so a SKU with no master row is invisible (shows out of stock).
  WRITTEN BY: ERP full snapshots, the bundle sync job and an item-status job — all upserts.
  Realtime webhook deltas never write here.
  No ORM model: column types are not declared in this codebase; names come from the SQL.
  '''
}

Table EdditemInventory [headercolor: #43A047] {
  skuCode varchar [unique, note: 'upsert key (ON DUPLICATE KEY)']
  "<warehouse name>" int [note: 'ONE COLUMN PER WAREHOUSE, named exactly as serving_entities.name; holds the quantity']

  Note: '''
  WHY: stock per SKU, as a WIDE table — one read returns a SKU stock in every warehouse;
  every new warehouse needs a new column.
  WRITTEN BY: ERP realtime webhook via Pub/Sub (only the warehouses in the message), full snapshots
  (every warehouse, including zeros) and the bundle job (buildable bundle count).
  HOW: upsert one warehouse column at a time.
  No ORM model: column types are not declared in this codebase.
  '''
}

Table warehouse_mapping [headercolor: #43A047] {
  id int [pk, increment]
  ucWarehouseName varchar(255) [not null, note: 'engine name = stock column = serving_entities.name']
  erpWarehouseName varchar(255) [not null, note: 'name the ERP sends']
  createdAt datetime
  updatedAt datetime

  Note: '''
  WHY: translates ERP warehouse names into the engine names (stock columns, warehouse records).
  Several ERP names can map to the same engine name.
  Read by ingestion (through a one-hour Redis cache) and by the warehouse-pinned promise.
  WRITTEN BY: nothing in this codebase — read only.
  '''
}

// ─────────────────────────────────────────── 6. Admin and protection (not part of the promise math)

Table rate_limit_endpoints [headercolor: #757575] {
  id bigint [pk, increment]
  endpoint varchar(500) [not null, unique]
  method varchar [not null, default: 'ALL', note: 'GET / POST / PUT / PATCH / DELETE / ALL']
  is_active boolean [not null, default: true]
  created_at datetime [not null]
  updated_at datetime [not null]

  indexes {
    (endpoint, method) [unique, name: 'unique_endpoint_method']
  }

  Note: '''
  WHY: which API endpoints are rate-limited. The live limiter keeps its token buckets in Redis.
  WRITTEN BY: no create path in the code — rows are added outside the application.
  '''
}

Table rate_limit_tracking [headercolor: #757575] {
  id bigint [pk, increment]
  ip_address varchar(45) [not null]
  endpoint_id bigint [not null]
  method varchar(10) [not null]
  remaining_count int [not null, default: 100]
  last_request_at datetime [not null]
  created_at datetime [not null]
  updated_at datetime [not null]

  indexes {
    (ip_address, endpoint_id, method) [unique, name: 'unique_ip_endpoint_method']
  }

  Note: '''
  WHY: per-IP counters. Used only by the admin cache screens; the live limiter does not use it.
  '''
}

Table control_panel_users [headercolor: #757575] {
  id "bigint unsigned" [pk, increment]
  email varchar(255) [not null, unique]
  role varchar(50) [not null]
  created_at datetime [not null]
  updated_at datetime [not null]

  Note: '''
  WHY: who can use the Control Tower admin console, and their role.
  WRITTEN BY: admin console.
  '''
}

Table audit_logs [headercolor: #757575] {
  id bigint [pk, increment]
  user varchar(255) [not null, default: '']
  operation varchar(255) [not null, default: '']
  request varchar(500) [not null, default: '', note: 'e.g. POST /clusters']
  req_body json
  created_at datetime [not null]
  updated_at datetime [not null]

  Note: '''
  WHY: a record of admin operations made through the Control Tower.
  WRITTEN BY: middleware on every admin request. Append-only.
  '''
}

// ─────────────────────────────────────────── Groups (coloured boxes on the canvas)

TableGroup serviceability [color: #1E88E5] {
  geo_polygons
  polygon_h3_indexes
  clusters
  cluster_polygons
  cluster_pincodes
  cluster_cities
  cluster_states
  cpinDataV2
}

TableGroup sourcing_and_sla [color: #8E24AA] {
  serving_entities
  cluster_warehouse_matrix
}

TableGroup delivery_time_rules [color: #FB8C00] {
  warehouse_cutoffs
  static_buffers
  static_buffer_areas
  day_skip_buffer
  capacity_buffers
  tag_buffers
}

TableGroup rain [color: #00897B] {
  rain_accuweather_locations
  rain_buffer_matrix
  rain_intensities_buffers
  rain_hourly_intensity
  rain_status
  rain_buffer_approval_batches
  rain_buffer_approvals
  rain_buffer_approval_settings
  rain_buffer_alerts
}

TableGroup inventory_erp [color: #43A047] {
  EDDItemMaster
  EdditemInventory
  warehouse_mapping
}

TableGroup admin [color: #757575] {
  rate_limit_endpoints
  rate_limit_tracking
  control_panel_users
  audit_logs
}

// ─────────────────────────────────────────── Relationships declared in code (FK or ORM association)

// serviceability
Ref: polygon_h3_indexes.polygon_id > geo_polygons.id [delete: cascade]
Ref: cluster_polygons.polygon_id > geo_polygons.id [delete: cascade]
Ref: cluster_polygons.cluster_id > clusters.id [delete: cascade]
Ref: cluster_pincodes.cluster_id > clusters.id [delete: cascade]
Ref: cluster_cities.cluster_id > clusters.id [delete: cascade]
Ref: cluster_states.cluster_id > clusters.id [delete: cascade]

// sourcing and SLA
Ref: cluster_warehouse_matrix.cluster_id > clusters.id [delete: cascade]
Ref: cluster_warehouse_matrix.warehouse_id > serving_entities.id [delete: cascade]

// delivery-time rules
Ref: warehouse_cutoffs.warehouse_id > serving_entities.id [delete: cascade]
Ref: static_buffers.cluster_id > clusters.id [delete: cascade]
Ref: static_buffers.warehouse_id > serving_entities.id [delete: cascade]
Ref: static_buffer_areas.static_buffer_id > static_buffers.id [delete: cascade]
Ref: day_skip_buffer.static_buffer_id > static_buffers.id // ORM association only (no FK declared)
Ref: capacity_buffers.warehouse_id > serving_entities.id [delete: cascade]

// rain
Ref: rain_accuweather_locations.warehouse_id - serving_entities.id
Ref: rain_buffer_matrix.warehouse_id > serving_entities.id
Ref: rain_intensities_buffers.warehouse_id > serving_entities.id
Ref: rain_intensities_buffers.warehouse_id > rain_buffer_matrix.warehouse_id // ORM association (matrix has many lookup rows)
Ref: rain_hourly_intensity.warehouse_id > serving_entities.id
Ref: rain_status.warehouse_id - serving_entities.id
Ref: rain_status.active_approval_id > rain_buffer_approvals.id // ORM association only
Ref: rain_buffer_alerts.warehouse_id > serving_entities.id
Ref: rain_buffer_approvals.batch_id > rain_buffer_approval_batches.id
Ref: rain_buffer_approvals.warehouse_id > serving_entities.id

// admin
Ref: rate_limit_tracking.endpoint_id > rate_limit_endpoints.id

// ─────────────────────────────────────────── Matched by value in code (no key) — grey lines

Ref: EdditemInventory.skuCode - EDDItemMaster.skuId [color: #9E9E9E] // INNER JOIN in the promise query
Ref: warehouse_mapping.ucWarehouseName > serving_entities.name [color: #9E9E9E]
Ref: cluster_cities.city_code <> cpinDataV2.city [color: #9E9E9E]
Ref: cluster_states.state_code <> cpinDataV2.state [color: #9E9E9E]
Ref: tag_buffers.tag <> EDDItemMaster.tags [color: #9E9E9E] // text match against the comma-separated tags


<!-- ➕ DB schema:end -->
