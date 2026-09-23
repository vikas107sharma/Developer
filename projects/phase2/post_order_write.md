POST-ORDER STATE MODELING — Order Lifecycle Write Path, Supertails

"An order isn't one fact, it's a sequence of facts arriving from four different systems over days — and my job on the write side was making sure the document never lies about which fact is current."

================================================ Step 1 ================================================

The 60-second version

"When an order is placed, Shopify fires a webhook at us. I skip service-only orders — vet or
grooming bookings don't ship anything — then call our Promise Engine, which tells me how to split
the order into shipments: which items travel together, which warehouse handles them, and the
expected delivery date.

I store all of that as one MongoDB document per order. The key modeling decision is that line items
and shipments are not the same thing. Line items are what the customer bought. Shipments are how it
actually ships. At creation, the shipment already has the promise information — warehouse, delivery
date, cutoff — but tracking is empty, because I don't know the courier or waybill yet. That only
shows up later.

As the order moves through the warehouse, the ERP sends delivery notes telling me what was actually
packed, and I reconcile that against what I originally planned in eight steps. If something doesn't
match — different warehouse, different quantity — I don't delete the old shipment plan. I tombstone
it as mismatched, so the history stays but the customer never sees a stale promise.

Then courier webhooks come in continuously and update tracking for exactly one shipment at a time,
using positional array filters so I never touch a sibling shipment by accident.

The part I'd want to talk about longest is a bug I found: the promise engine can silently drop a
SKU it couldn't plan for. That SKU still shows up in what the customer bought, but no shipment ever
claims it — invisible to anything that only renders shipment items, while the order total still
bills for it."

================================================ Step 2 ================================================

The interviewer asks: "Draw the pipeline."

```
  Shopify order webhook  ──►  POST /webhook/post-order/edd-actions
                                │   EddActionsV2()
                                │   guard: service-only orders (vet/grooming) skipped
                                │
                                ├──GET /v2/cartedd──►  PROMISE ENGINE (separate microservice)
                                │◄── shipmentInfo[] + per-SKU EDD ──┘
                                │
                                ├──►  orderPromises collection
                                │     (raw response archived — on SUCCESS *and* FAILURE)
                                ▼
                          orders document (one per order)
                            lineItems[]   ← Shopify         (what was bought)
                            shipments[]   ← promise engine  (how it ships)
                               promise{}   [FILLED]   warehouse, deliveryType,
                                                      deliveryDateTime, dayCount, cutoff
                               tracking{}  [ALL NULL]  waybill, courier, deliveryNote,
                                                      status, trackingHistory: []
                                │
                                ▼
  ERP delivery note  ──────►  POST /webhook/delivery-notes
                              handleDeliveryNoteWebhook()  → 8-STEP RECONCILE vs planned shipments
                                                          fills deliveryNoteNumber
                                                          creates unpredicted shipments
                                                          tombstones stale plans (mismatched:true)
                                ▼
  Clickpost courier webhooks ►  updateTrackingStatus()
                                fills tracking.status, appends trackingHistory[]
                                targets ONE shipment via positional arrayFilters
```

"I keep this diagram in my head every time someone asks how the order model works — it does half the
explaining for me."

================================================ Step 3 ================================================

The interviewer asks: "Why archive the raw Promise Engine response even when the call fails?"

"Because when something downstream looks wrong three weeks later, I need to know exactly what the
Promise Engine told me at the moment the order was placed — not what I think it probably said. I
archive that raw response into a separate collection on both success and failure. On failure, I
still insert the order document behind an existence guard, so a webhook retry after a transient EDD
failure can't double-insert the same order.

That archive has paid for itself more than once — it's the only way to answer 'what did we actually
promise this customer at 2am on a Tuesday' without guessing."

================================================ Step 4 ================================================

The interviewer asks: "Walk me through the eight-step delivery-note reconciliation, and why tombstone instead of delete?"

```
1. Archive raw DN payload; map ERP warehouse names → internal names
2. Fire-and-forget: refresh the Shopify order note with the latest EDD
3. Self-heal: if the order doesn't exist yet, call our own webhook and re-check
4. Tombstone shipments matching a CANCELLED delivery note (mismatched:true, never deleted)
5. Exact-match: DN ↔ shipment by warehouse + SKU + quantity, looked up by Mongo _id
6. Match remaining shipments with no DN yet against remaining DNs (same _id discipline)
7. Tombstone everything still left over — skip anything already processed or the placeholder
8. For any DN nothing predicted: call Promise Engine for a warehouse-pinned EDD,
   create the shipment, and re-sync the placeholder shipment last
```

"The warehouse doesn't always pack exactly what I planned. Maybe it substitutes a warehouse, maybe
the quantity's off. When that happens I never delete the shipment I originally planned — I mark it
mismatched and leave it in the array. Two reasons. First, I want the history: if a customer disputes
what was promised, I want to be able to show the original plan even though it didn't hold. Second,
other steps in this same reconciliation snapshot the shipments array, do work, and write back using
the original array index. If I deleted an element, every later shipment's index would shift between
the snapshot and the write-back, and I'd end up mutating the wrong shipment. Tombstoning keeps the
array stable.

I found a real collision doing this: shipment IDs get generated as SHIPMENT_<warehouse>_<n>, and
they're not guaranteed unique once a webhook redelivery has appended new shipments to the array. If
the exact-match step looked shipments up by that generated ID, a delivery note could silently patch
the wrong parcel — the first match a naive findIndex hits, not necessarily the right one. I switched
that lookup to Mongo's own _id, which is genuinely unique, so a delivery note can never land on the
wrong shipment by accident."

================================================ Step 5 ================================================

⭐ The strongest card — the placeholder shipment

```
Promise Engine silently drops a SKU it can't plan for
        │
        ▼
  SKU reaches lineItems[]  (customer bought it, order total bills for it)
  but NO shipment claims it  (invisible to anything that renders shipment items)
        │
        ▼
  ONE row: SHIPMENT_PLACEHOLDER_<orderId>
    - holds every SKU no real shipment covers
    - idempotency key = sorted "sku:qty" fingerprint → unchanged placeholder never rewritten
    - promise = null, tracking = null   (NOT {} — see below)
    - always appended LAST (later steps carry positional indices from an earlier snapshot)
    - called from BOTH write paths — safe because it's idempotent either way
    - retired by EMPTYING items, never deleting the row
      (deleting would shift every later shipment's array index)
```

"I found this because two real orders showed the customer a total that included an item that never
appeared anywhere in their shipment list — the Promise Engine had quietly dropped that SKU from
`shipmentInfo` as unplannable, but the line item and the total still counted it. Nothing crashed.
Nothing errored. The order just silently under-shipped from the customer's point of view.

The fix holds exactly one placeholder shipment per order for whatever the Promise Engine couldn't
plan. It has to be idempotent, because both the initial order webhook and the later delivery-note
reconciliation call it, and I don't want either call creating a second placeholder or rewriting an
unchanged one. I fingerprint the held SKUs as a sorted 'sku:qty' string — if the fingerprint hasn't
changed, I skip the write entirely.

One detail I'd volunteer without being asked: promise and tracking on the placeholder are `null`,
not `{}`. An empty object is still truthy, and the message-rendering layer would read a
truthy-but-empty promise as 'we have a plan' and render something like 'arriving in 2-3 days' for an
item that isn't shipping at all. Null forces it to fall through to an honest 'arriving soon' instead.

And retirement empties the items array rather than deleting the row, for the same reason the
delivery-note tombstoning does — later reconciliation steps carry positional array indices across a
document re-fetch, and a delete would shift every index after it."

================================================ Step 6 ================================================

The interviewer asks: "How does courier tracking safely update just one shipment?"

"Every tracking write uses positional arrayFilters keyed on the delivery note number — I target
exactly one shipment inside the array without touching its siblings, and Mongo does that update
atomically at the document level. That means two different shipments in the same order can be
updated by two different courier webhooks at the same time with no read-modify-write race between
them.

For dedup, I key each tracking-history entry on waybill plus status code plus timestamp, and I check
for that key's existence before I push a new history entry, so a duplicate courier callback doesn't
create a duplicate history row. I'll be upfront that this is check-then-act, not one atomic
operation — two truly concurrent webhooks carrying the identical key could both pass the check before
either one pushes, and you'd get one duplicate entry. Closing that fully would need either a single
atomic update expressing the uniqueness guard in one round trip, or a database-level unique
constraint on the subdocument fields — I haven't done either, and I'd say so if asked."

================================================ Step 7 ================================================

The interviewer asks: "How does COD allocation work across multiple shipments?"

"If an order splits into more than one shipment, the COD amount due has to split with it — and the
numbers absolutely have to add up to the order total, or a customer sees a support-ticket-shaped
discrepancy.

I use the whole order's total item value as a fixed denominator, not just the shipments that exist
so far — that way a shipment's collectable amount never shifts just because a later fulfilment shows
up. And I derive one of the three displayed figures — the item total — from the other two instead of
rounding all three independently. If I round three numbers independently, 'a + b = c' can break by a
rupee. Deriving the third figure from the other two makes that invariant hold unconditionally,
by construction, not by hoping the rounding works out."

Cut these from your interview story:
❌ "I built the whole write-side pipeline from scratch." — I extended shared infrastructure —
the Promise Engine call, the archival pattern, the shipments-map construction predate my specific
additions. Be precise about what's mine: the placeholder mechanism, the COD allocation engine, the
_id-based shipment-match fix, and the reconciliation hooks — not the whole scaffold.
❌ "Replay safety is fully handled." — The live edd-actions route has its replay-dedup check
commented out; only the older route still enforces it. I should be able to explain that trade, not
imply the newer path is bulletproof.
❌ "The self-heal step is bulletproof." — It sleeps a fixed 2 seconds and re-checks Mongo. Under load,
or if the Promise Engine call it depends on is slow, that fixed sleep isn't long enough and the
self-heal can return before the order actually exists.

Numbers you must know:
- 4 MongoDB collections: orders, orderPromises, erpDeliveryNotes, trackingStatusLogs.
- 8-step delivery-note reconciliation, in the fixed order above.
- Tracking dedup key: waybill + status code + timestamp.
- Placeholder idempotency key: sorted "sku:qty" fingerprint.
- Timeouts on every outbound call: Promise Engine 30s, ERP push 10s, self-heal edd-actions call 60s.
- Honest gaps to volunteer: replay-dedup check commented out on the live edd-actions route (still
  enforced on the old route); fixed 2-second sleep as the only synchronization in the self-heal step;
  tracking dedup is check-then-act, not atomic.
- [NEED FROM ME]: Roughly how many orders were affected by the placeholder-shipment bug before the
  fix shipped — do you have a count or a support-ticket tally?
- [NEED FROM ME]: What fraction of orders actually hit step 7 of the reconciliation (unpredicted
  delivery notes) versus a clean exact match?
- [NEED FROM ME]: Daily order volume through this write path, so I can frame scale honestly.
