<!-- ➕ added:start -->

# Post-Order Tracking System

> Formatted from `post_order_detailed.txt` (left untouched). Every original line is kept. Blocks labelled **➕ Added** are new.

## Contents

- [1. First understand the big picture](#1-first-understand-the-big-picture)
- [2. The most important concept: Line Item vs Shipment](#2-the-most-important-concept-line-item-vs-shipment)
- [3. A shipment has two different concepts: Promise and Tracking](#3-a-shipment-has-two-different-concepts-promise-and-tracking)
- [4. Why don't we delete old shipments?](#4-why-dont-we-delete-old-shipments)
- [5. Order Placed — what happens?](#5-order-placed--what-happens)
- [6. What if Promise Engine is down?](#6-what-if-promise-engine-is-down)
- [7. What is the placeholder shipment?](#7-what-is-the-placeholder-shipment)
- [8. Warehouse delivery note — reality arrives](#8-warehouse-delivery-note--reality-arrives)
- [9. Why ask Promise Engine again?](#9-why-ask-promise-engine-again)
- [10. Courier tracking](#10-courier-tracking)
- [11. Tracking history](#11-tracking-history)
- [12. Now the READ side](#12-now-the-read-side)
- [13. How does it avoid N+1 queries?](#13-how-does-it-avoid-n1-queries)
- [14. The status ladder](#14-the-status-ladder)
- [15. Returns](#15-returns)
- [16. Pharmacy items](#16-pharmacy-items)
- [17. COD splitting](#17-cod-splitting)
- [18. Cancellation](#18-cancellation)
- [19. The complete lifecycle](#19-the-complete-lifecycle)
- [20. What you should say in an interview](#20-what-you-should-say-in-an-interview)

<!-- ➕ added:end -->

This document describes a Post-Order Tracking System. The easiest way to understand it is:

An order starts as a plan, then becomes reality as the warehouse and courier report what actually happened. The system keeps both the original plan and current reality, and the read APIs convert all of that into customer-friendly statuses. <!-- Pasted markdown -->

## 1. First understand the big picture

There are 4 systems producing information:

```text
Shopify
   │
   │ "Customer bought these items"
   ▼
Post-Order System
   ▲
   │
Promise Engine
   │ "How we plan to ship them"

ERP / Warehouse
   │ "What we actually packed"

Courier
   │ "What is happening to the parcel"
```

The Post-Order system has two responsibilities:

```text
WRITE SIDE                         READ SIDE
──────────                         ─────────
Order placed                       Order List
Delivery note                      Order Details
Courier tracking                   Shipment Details
     │                                   │
     ▼                                   ▼
MongoDB order record              Customer response
```

**The important architectural idea is that MongoDB becomes the central order/shipment state, while Shopify, ERP, courier, returns, pharmacy, etc. remain sources of additional facts.** <!-- Pasted markdown -->

<!-- ➕ added:start -->

**➕ Added — diagram: the four sources, the write side, MongoDB and the read side**

```text
      Shopify           Promise Engine        ERP / Warehouse           Courier
  what was bought     how we plan to ship     what we packed       what's happening
         │                     │                     │                     │
   ORDER_CREATED        plan (archived)        delivery note       webhook → Pub/Sub
         │                     │                     │                     │
         └─────────────────────┴──────────┬──────────┴─────────────────────┘
                                          ▼
                             ┌────────────────────────┐
                             │ Post-Order  WRITE side │
                             └────────────┬───────────┘
                                          ▼
                             ┌────────────────────────┐
                             │ MongoDB order record   │
                             │ line items + shipments │
                             └────────────┬───────────┘
                                          ▼
                             ┌────────────────────────┐
                             │ Post-Order  READ side  │
                             │ Order List             │◄── Shopify · Returns · Revised EDD
                             │ Order Details          │    COD · Pharmacy · Fees
                             │ Shipment Details       │
                             └────────────┬───────────┘
                                          ▼
                                  Customer response
```

<!-- ➕ added:end -->

## 2. The most important concept: Line Item vs Shipment

This is the part you absolutely need to understand for an interview.

Suppose the customer buys:

```text
Dog Food × 2
Cat Food × 1
```

These are line items.

They answer:

> What did the customer buy?

A shipment answers a different question:

> How is the order actually travelling?

For example:

```text
Shipment 1
Warehouse W1
    Dog Food × 2
    Cat Food × 1
```

But it could also become:

```text
Shipment 1
Warehouse W1
    Dog Food × 2

Shipment 2
Warehouse W2
    Cat Food × 1
```

So:

```text
LINE ITEMS
    ↓
What customer purchased

SHIPMENTS
    ↓
How those items are physically delivered
```

**One product can therefore appear in multiple shipments, and one shipment can contain multiple products.** <!-- Pasted markdown -->

## 3. A shipment has two different concepts: Promise and Tracking

This distinction is also critical.

### Promise = PLAN

Before anything is shipped:

```text
Warehouse: W1
Delivery type: Next Day
Expected: Sunday 10 PM
```

This comes from the Promise Engine.

### Tracking = REALITY

Later:

```text
Delivery Note: DN123
Courier: Delhivery
Waybill: WB456
Status: In Transit
```

This comes from the warehouse/courier side.

So:

```text
Shipment
├── Promise
│   ├── warehouse
│   ├── promised date
│   ├── cutoff
│   └── delivery message
│
└── Tracking
    ├── delivery note
    ├── waybill
    ├── courier
    ├── current status
    ├── rider
    └── history
```

Initially:

```text
Promise = populated
Tracking = empty
```

because the customer has ordered but the courier doesn't have the parcel yet. <!-- Pasted markdown -->

<!-- ➕ added:start -->

**➕ Added — diagram: what one order record holds**

```text
 order   (one MongoDB order record, conceptual shape)
 │
 ├── line items                  ← "What did the customer buy?"
 │     Dog Food × 2
 │     Cat Food × 1
 │
 └── shipments[]                 ← "How is the order actually travelling?"
       │
       ├── [0]  Warehouse W1 · Dog Food × 2
       │      ├── promise    warehouse · promised date · cutoff · delivery message     PLAN
       │      └── tracking   delivery note · waybill · courier · status · rider · history   REALITY
       │
       └── [1]  Warehouse W2 · Cat Food × 1
              ├── promise    …
              └── tracking   …

 At order placement:  promise = populated,  tracking = empty
```

<!-- ➕ added:end -->

## 4. Why don't we delete old shipments?

This is the tombstone concept.

Imagine Promise Engine says:

```text
Shipment A
Warehouse W1
Dog Food × 2
```

But warehouse actually packs from W2.

You now have:

```text
OLD PLAN
W1 → Dog Food × 2

REALITY
W2 → Dog Food × 2
```

You might think:

> Delete W1 and create W2.

But the system deliberately does:

```text
W1 shipment
    ↓
mismatched = true

and then creates:
W2 shipment
    ↓
active
```

The old shipment remains in MongoDB but is hidden from the customer.

Why?

### Reason 1 — History

You can still answer:

> What did we originally promise?

### Reason 2 — Array positions

This system sometimes writes back to shipments using their position in the array.

Suppose:

```text
shipments[0] = W1
shipments[1] = W3
shipments[2] = W4
```

If you delete shipments[0]:

```text
shipments[0] = W3
shipments[1] = W4
```

Now an operation expecting position 1 could accidentally modify W4 instead of W3.

So:

**Tombstone means "keep the object but make it inactive/hidden."**

Don't confuse this with database deletion. <!-- Pasted markdown -->

## 5. Order Placed — what happens?

When Shopify sends:

```text
ORDER_CREATED
```

the system roughly does this:

```text
Shopify
   ↓
Remove service items
   ↓
Check pincode
   ↓
Call Promise Engine
   ↓
Archive Promise Engine response
   ↓
Create shipments
   ↓
Add placeholder if required
   ↓
Save MongoDB order
   ↓
Notify ERP asynchronously
```

The Promise Engine tells the system:

```text
Order
 ├── Shipment 1
 │      ├── Warehouse W1
 │      ├── Dog Food × 2
 │      └── Sunday
 │
 └── Shipment 2
        ├── Warehouse W2
        ├── Cat Food × 1
        └── Monday
```

Importantly, the Promise Engine call is only asking:

> "How would you ship this?"

**It doesn't actually reserve warehouse capacity.** <!-- Pasted markdown -->

## 6. What if Promise Engine is down?

This is an important reliability decision.

```text
Bad design:
Promise Engine down
      ↓
Order creation fails
```

This system does:

```text
Promise Engine down
      ↓
Archive error
      ↓
Save order anyway
      ↓
No shipments
```

So the order is not lost.

Later the UI can fall back to Shopify's line items.

**That's an example of graceful degradation.** <!-- Pasted markdown -->

## 7. What is the placeholder shipment?

This solves a subtle problem.

Suppose customer bought:

```text
Dog Food × 2
Cat Food × 1
Medicine × 1
```

But Promise Engine only plans:

```text
Dog Food × 2
Cat Food × 1
```

Medicine isn't planned.

If the frontend builds its display from shipments, Medicine disappears.

That's obviously wrong.

So the system creates:

```text
Shipment 1
Dog Food × 2
Cat Food × 1

Shipment 2
PLACEHOLDER
Medicine × 1
```

But placeholder has:

```text
promise = empty
tracking = empty
```

Therefore the UI can say:

```text
Medicine
Arriving soon
```

rather than falsely saying:

```text
Medicine
Arriving tomorrow
```

The placeholder is also tombstoned/ignored by most backend logic so it doesn't behave like a real shipment. <!-- Pasted markdown -->

## 8. Warehouse delivery note — reality arrives

Now the warehouse sends:

```text
Delivery Note:

DN1
Warehouse W2
Dog Food × 2
Cat Food × 1
```

But our original Promise was:

```text
W1
Dog Food × 2
Cat Food × 1
```

So the system compares them.

Matching requires:

```text
warehouse
+
items
+
quantities
```

to be identical. <!-- Pasted markdown -->

Here:

```text
W1 != W2
```

Therefore:

```text
Original W1 shipment
        ↓
      TOMBSTONE

DN1 / W2
        ↓
Create new shipment
        ↓
Ask Promise Engine:
"Give me promise specifically for W2"
```

Final state:

```text
shipments:

[0]
W1
mismatched = true

[1]
W2
DN = DN1
promise = fresh W2 promise
```

Customer sees only W2.

But the system retains W1 for history.

<!-- ➕ added:start -->

**➕ Added — diagram: how a delivery note is matched against the plan**

```text
                        Delivery note arrives
           DN1 · Warehouse W2 · Dog Food × 2, Cat Food × 1
                                  │
                                  ▼
               Active shipment with the SAME warehouse
                        + items + quantities?
                 ┌────────────────┴────────────────┐
                YES                               NO
                 │                                 │
                 ▼                                 ▼
         attach DN1 to it                old planned shipment
         tracking fills in                 mismatched = true
                                       (tombstone: kept, hidden)
                                                   │
                                                   ▼
                                       new shipment for DN1 / W2
                                    Promise Engine → promise for W2

 shipments[] before                      shipments[] after
 [0] W1  promise ✓  tracking empty       [0] W1  mismatched = true             hidden
                                         [1] W2  DN = DN1 · fresh W2 promise   shown
```

<!-- ➕ added:end -->

## 9. Why ask Promise Engine again?

Because the original promise was based on:

```text
W1

but reality is:
W2
```

Delivery time can therefore change.

So:

```text
Original:
W1 → Sunday 10 PM

Actual:
W2 → Monday 8 PM
```

**The customer should get the promise corresponding to the warehouse actually shipping the order, not the warehouse the system originally expected.**

## 10. Courier tracking

Now the courier starts sending events:

```text
Picked Up
In Transit
Out For Delivery
Delivered
```

The system doesn't process all of this synchronously.

It does:

```text
Courier
   ↓
Webhook
   ↓
Pub/Sub
   ↓
Consumer
   ↓
MongoDB
```

Pub/Sub provides buffering and retry behavior.

The important part is:

**A courier event updates one specific shipment, identified by its delivery-note number.** <!-- Pasted markdown -->

For example:

```text
Order O123

Shipment 1 → DN001 → Delivered
Shipment 2 → DN002 → In Transit
```

If courier sends:

```text
DN002 = Out For Delivery
```

only Shipment 2 is updated.

Shipment 1 remains Delivered.

## 11. Tracking history

Every courier update also gets added to:

```text
tracking.history[]
```

For example:

```text
[
  Delivered
  Out For Delivery
  In Transit
  Picked Up
]
```

Newest first.

The system attempts to prevent duplicates using:

```text
waybill + status + time
```

But the document explicitly identifies a weakness:

```text
check exists
     ↓
add history
```

This isn't atomic.

Two concurrent consumers could both do:

```text
check → doesn't exist
check → doesn't exist

add
add
```

and create duplicates.

The document therefore recommends making this an atomic operation. <!-- Pasted markdown -->

<!-- ➕ added:start -->

**➕ Added — diagram: how the non-atomic check creates duplicates, and the fix**

```text
 TODAY: check, then add (two steps)           RECOMMENDED: one atomic step
 ──────────────────────────────────           ────────────────────────────
 Consumer A            Consumer B             Consumer A or B:
 check → not there                            "add this entry only if
                       check → not there       waybill + status + time
 add                                           isn't already in history"
                       add  ← duplicate        → the second consumer changes nothing
```

<!-- ➕ added:end -->

## 12. Now the READ side

The customer doesn't see MongoDB directly.

There are three screens:

```text
Order List
    ↓
"What have I ordered?"

Order Details
    ↓
"Tell me everything about this order"

Shipment Details
    ↓
"Where is this parcel?"
```

The response isn't generated from one database.

It combines:

```text
Shopify
MongoDB order record
Returns
Revised EDD
COD conversion
Pharmacy
Fee metadata
```

So this is essentially an aggregation/integration layer. <!-- Pasted markdown -->

## 13. How does it avoid N+1 queries?

Suppose the order list contains:

```text
10 orders

Bad implementation:
Order 1 → query Mongo
Order 2 → query Mongo
Order 3 → query Mongo
...
Order 10 → query Mongo
```

That's N+1 style behavior.

Instead:

```text
Collect all order IDs
        ↓
One Mongo query
        ↓
10 orders
```

Similarly:

```text
All order IDs
     ↓
One Returns query

All order IDs
     ↓
One Revised EDD query

All order IDs
     ↓
One COD query
```

So:

```text
10 orders
```

Instead of:

```text
10 × Mongo
10 × Returns
10 × Revised EDD
10 × COD
```

Do:

```text
1 × Mongo
1 × Returns
1 × Revised EDD
1 × COD
```

The document says pharmacy is still queried per order, so that remains an N+1-type problem. <!-- Pasted markdown -->

## 14. The status ladder

This is probably the most important part of the read logic.

The system has multiple facts:

```text
Promise
Courier status
Cancellation
Delivery timestamp
Revised EDD
Return status
```

It needs to collapse all of that into:

```text
ONE customer-facing status
+
ONE sentence
```

For example:

> "Arriving by Tomorrow 10 PM"

The status rules are evaluated as a ladder, where later rules can override earlier ones. <!-- Pasted markdown -->

Conceptually:

```text
                Shipment
                   │
                   ▼
          Is there a courier?
             /          \
           No            Yes
           │              │
     Check promise      courier status
           │              │
           ▼              ▼
      Order Placed    Out for Delivery
      Packing Items   Delivered
                      Failed
                      etc.
                           │
                           ▼
                   Check cancellation
                           │
                           ▼
                   Check delivery time
                           │
                           ▼
                   Check revised EDD
                           │
                           ▼
                   Final customer status
```

For example:

```text
Courier status = Delivered

produces:
Delivered on Tue, 3rd Sep
```

Whereas:

```text
No courier
Promise within 6 hours

might produce:
Packing Items
```

And:

```text
No reliable date

becomes:
Arriving soon
```

**The key is that the backend is not simply returning the raw courier status. It is applying business rules to generate a customer-facing interpretation.**

## 15. Returns

Returns are interesting because the system has to show both:

### Original shipment

If:

```text
Dog Food × 2

and customer returns:
Dog Food × 1
```

the forward shipment becomes:

```text
Dog Food × 1
```

### Return shipment/status

And separately:

```text
Return
Dog Food × 1
Status: Refund initiated
Refund: ₹500
```

So the UI represents:

```text
FORWARD FLOW
Original shipment
    ↓
quantity reduced

RETURN FLOW
Return request
    ↓
status
    ↓
refund
```

The system also has protection against Shopify showing the same item across multiple fulfilments, which could otherwise cause the return/refund to be counted twice. <!-- Pasted markdown -->

## 16. Pharmacy items

Prescription items have another special state.

Normally:

```text
Product
   ↓
Shipment
   ↓
Delivery
```

But prescription products have:

```text
Product
   ↓
Prescription verification
   ↓
Released?
   ├── No → verification shipment
   └── Yes → normal shipment
```

Until verification succeeds, the system deliberately doesn't show a delivery promise.

Instead:

```text
Prescription verification

Pending
"Vet will call in 30 mins..."

Once released:
Normal shipment
    ↓
Normal delivery tracking
```

This prevents the UI from promising delivery for something that legally/operationally cannot yet ship. <!-- Pasted markdown -->

## 17. COD splitting

Suppose:

```text
Product A = ₹900
Product B = ₹100
Fee       = ₹50

Order total = ₹1,050
```

And:

```text
Shipment 1 → Product A
Shipment 2 → Product B
```

The system needs to tell each delivery agent how much cash to collect.

It calculates based on the whole order's item value:

```text
Total item value = ₹1,000

Shipment 1:
900 / 1000 = 90%

Shipment 2:
100 / 1000 = 10%
```

Then:

```text
Shipment 1:
90% × ₹1,050 = ₹945

Shipment 2:
remaining = ₹105
```

Therefore:

```text
₹945 + ₹105 = ₹1,050
```

The important engineering detail is that the last shipment absorbs rounding differences, ensuring:

```text
sum(shipment COD amounts) == order total
```

exactly. <!-- Pasted markdown -->

<!-- ➕ added:start -->

**➕ Added — diagram: the COD split, and the rule behind it**

```text
 Order total = ₹1,050        items ₹1,000 + fee ₹50

 Shipment 1   Product A   ₹900   share 90%   →  90% × ₹1,050       = ₹945
 Shipment 2   Product B   ₹100   share 10%   →  ₹1,050 − ₹945      = ₹105   ← last one takes the remainder
                                                                    ──────
                                                                    ₹1,050   exact

 ₹1,050 [█████████████████████████████████████████████░░░░░]
         Shipment 1 = ₹945 (45 blocks)            Shipment 2 = ₹105 (5)

 every shipment except the last:  order total × (its item value ÷ total item value), rounded
 last shipment:                   order total − sum of all earlier shipments
```

<!-- ➕ added:end -->

## 18. Cancellation

An order can be cancelled only if none of the blockers exists.

For example:

```text
Shopify already fulfilled?
        ↓
      BLOCK

Quick-commerce shipment?
        ↓
      BLOCK

Courier status exists?
        ↓
      BLOCK

Service item?
        ↓
      BLOCK

Already cancelled?
        ↓
      BLOCK
```

So the basic business idea is:

**Once physical fulfilment/delivery activity has started, cancellation becomes unavailable.** <!-- Pasted markdown -->

## 19. The complete lifecycle

If you remember only one diagram, remember this:

```text
                 ORDER PLACED
                      │
                      ▼
                 Shopify
                      │
                      ▼
              Promise Engine
                      │
                      ▼
             Initial shipments
             Promise = filled
             Tracking = empty
                      │
                      ▼
                MongoDB
                      │
          ┌───────────┴───────────┐
          │                       │
          ▼                       ▼
     Warehouse                 Customer
     Delivery Note             reads order
          │
          ▼
     Compare with plan
          │
     ┌────┴─────┐
     │          │
   Match    Doesn't match
     │          │
     │       Tombstone old
     │       Create new
     │       shipment
     │
     ▼
   Shipment
     │
     ▼
   Courier
     │
     ▼
   Pub/Sub
     │
     ▼
   Tracking update
     │
     ▼
   Update shipment
     │
     ▼
   Tracking history
     │
     ▼
   READ API
     │
     ├── Shopify
     ├── MongoDB
     ├── Returns
     ├── Revised EDD
     ├── COD
     ├── Pharmacy
     └── Fees
          │
          ▼
   Status ladder
          │
          ▼
"Arriving by Tomorrow 10 PM"
```

## 20. What you should say in an interview

A concise explanation would be:

> "The post-order system maintains the lifecycle of an order after checkout. Shopify tells us what was purchased, the Promise Engine tells us how we initially expect to fulfil it, ERP delivery notes tell us what was actually packed, and courier events tell us the real-time delivery status. We maintain line items separately from shipments because one item can be split across multiple parcels. Each shipment has a promise section representing the plan and a tracking section representing reality. When warehouse reality differs from the original promise, we tombstone the old shipment rather than deleting it and create a new shipment based on the actual warehouse. Courier events are asynchronously consumed through Pub/Sub and update exactly one shipment using the delivery-note number. On the read side, we aggregate Shopify, MongoDB, returns, revised EDD, COD, pharmacy and other sources, batch queries to avoid N+1 calls, and finally apply a status-priority ladder to convert all these facts into a single customer-facing delivery message." <!-- Pasted markdown -->

That is the core architecture.
