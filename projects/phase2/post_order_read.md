CUSTOMER-FACING FAN-IN API — Post-Order Read Path, Supertails

"Writing the order document was the easy half. The hard half was answering one screen's worth of questions when the truth about that order lives in twelve different systems that don't agree on vocabulary."

================================================ Step 1 ================================================

The 60-second version

"On the read side, I built the layer that powers everything a customer sees about their order —
list, details, and shipment tracking, each in an app and a web variant, so six routes in total.

The hard part was never fetching from Mongo. Mongo gives me the shipment and tracking skeleton, but
a real customer-facing response needs data from more than a dozen sources: Shopify for product
info and fulfillments, our returns system for refund status, a revised-EDD table for updated
delivery dates, pharmacy for prescription-item status, a failed-delivery table for missed-attempt
details, and a pricing service for dynamic fee names — and that's not the full list.

So I built a fan-in layer that collects all of that and turns technical status codes into one human
sentence — 'Arriving by Tomorrow 10PM' or 'Missed delivery on Wednesday' — instead of a dozen
half-answers.

The performance discipline that mattered most was avoiding N+1 queries. I collect every order ID or
waybill in the batch first, then make exactly one query per downstream source for the whole page,
not one query per order.

And there were real business cases with teeth: when Shopify splits one line item across multiple
fulfillments, a return can't double-count it. When an order splits into several shipments, the COD
amount due has to divide across them and still add up to the order total exactly. I'd rather talk
about those than pretend the read side was just a database read — it's closer to systems
integration than to a CRUD endpoint."

================================================ Step 2 ================================================

The interviewer asks: "Draw the fan-in."

```
   /post-order/list          /post-order/details        /post-order/shipment
   (+ /list/web, /details/web, /shipment/web  — six routes total)
        │                          │                          │
        └──────────────┴──────────────────────────┴──────────┘
                                   │
                   formatPostOrderShipmentData()  ← ~1900-line fan-in layer
                                   │
  ┌──────────┬──────────┬─────────┼─────────┬──────────┬──────────┬─────────┬──────────┐
Shopify    Mongo     Returns   revised_edd  COD→      Pharmacy   failed_   Pricing   journey_
GraphQL    orders   (Clickpost)             prepaid   (Rx)      deliveries service   tracking
   │          │          │          │          │        │      /ndr       │          │
header,   shipments,  per-SKU    override   payment   hide     reschedule dynamic   delivery-
variants, promise,    return     the        mode      unreleased inputs  fee        partner
images,   tracking,   status,    promised   flip      Rx items  + attempt titles +   contact,
fees,     history     refunds    date                          history   tooltips  tracking
fulfil-                                                                  (ocv gate) tile flags
ments
                                   │
                                   ▼
                    ONE response — every field a human sentence
                    "Arriving by Tomorrow 10PM"
                    "Delivered on Tue, 3rd Sep"
                    "Missed delivery on Wed, 4th Sep"
                    + rider name/phone, cancellable flag, fee rows,
                      per-shipment COD amount due
```

"I draw this every time — it does half the explaining for me. Twelve-plus sources feeding one
response is the whole story of why this layer exists."

================================================ Step 3 ================================================

The interviewer asks: "What are the twelve-plus sources, really, and what does each one own?"

"Shopify Admin GraphQL owns the product truth — title, image, variant, price, and the fulfillment
records themselves. Mongo owns the shipment and tracking state I wrote on the write side — promise,
courier, waybill, tracking history. Four separate MySQL tables sit alongside that: revised_edd for
delivery dates that changed after the original promise, failed_deliveries for missed-attempt and
NDR detail, journey_tracking and delivery_partner_contact for rider-level tracking tile data.

Then there are three service integrations: the returns system tells me per-SKU return status and
refund amounts; pharmacy tells me whether prescription items should even be shown yet; pricing
gives me dynamic fee names and tooltips gated behind a rollout flag, versus a legacy fixed fee
triplet for clients that haven't migrated. And a COD-to-prepaid source flips payment mode display
when an order's payment method changed after placement.

Every one of those is a different system's opinion about a different slice of the same order's
life. My job is making sure the customer never has to know that."

================================================ Step 4 ================================================

The interviewer asks: "How do you turn technical statuses into one sentence?"

"There's a chain of functions that takes raw courier status codes, Shopify's fulfillment state, and
whatever delay calculation applies, and collapses all of it into a single sentence — 'Arriving by
Tomorrow 10PM,' 'Delivered on Tue, 3rd Sep,' 'Missed delivery on Wed, 4th Sep.' Nobody wants status
code 9 with a sub-reason enum; they want one line they can read in half a second.

One specific piece of that I'd bring up unprompted: our quick-commerce delivery flow has three
distinct courier failure codes that all mean roughly the same thing to a customer, so I remapped all
three of them down to one 'Delivery failed' status. The courier's granularity is useful for ops;
it's noise for the person checking their order."

================================================ Step 5 ================================================

⭐ The strongest card — N+1 avoidance and the two real double-counting traps

```
NAIVE (N+1):                          WHAT I BUILT:
for each order:                       collect ALL order IDs / waybills first
  query returns                              │
  query revised_edd                          ▼
  query COD→prepaid                   ONE getOrdersByIds() call
  ...                                 ONE getReturnedOrders() call
= N queries per source                ONE getRevisedEDDData(allAwbs) call
= slow, scales with page size         ONE codToPrepaidOrders(...) call
                                     = one query per SOURCE, not per order
```

"The obvious way to write this is a loop: for each order in the page, ask returns, ask revised EDD,
ask COD-to-prepaid. That's N+1 for every source, and it gets worse as page size grows. Instead I
collect every order ID and every waybill across the whole batch up front, and make exactly one call
per downstream source for the entire page. It's a small discipline, but multiplied across twelve
sources and a page of orders, it's the difference between a response that scales and one that
doesn't.

The two business cases where this actually got tricky both come from the same root cause: an order
splitting into more than one fulfillment.

First, returns. Shopify can report the exact same line item across multiple fulfillments when an
order ships split. If I naively summed return quantity per line item occurrence, I'd double-count
the same return. So I decoupled two things that look like they should be the same: the *display*
quantity gets reduced on every matching line-item instance the loop finds, so what renders is
consistent everywhere — but the *return-shipment record itself* only gets created once per
return-ID-and-SKU pair, guarded by a set. How many places show the reduced quantity and how many
times I record the return are deliberately different counters.

Second, COD. If one order becomes three shipments, the payable amount has to split across all three
and still add up to the order total to the rupee. I use the whole order's item value as a fixed
denominator so a shipment's amount never shifts just because a later fulfillment shows up, and I
derive one of the three displayed numbers from the other two instead of rounding all three
independently — because rounding three numbers separately is exactly how 'a + b = c' quietly breaks
by a rupee."

================================================ Step 6 ================================================

The interviewer asks: "What signals decide if an order is cancellable?"

"Cancellability isn't one flag — it's a conjunction of independent signals: whether any Shopify
fulfillment already exists, whether the delivery type is quick-commerce with any tracking status at
all, whether a superfast delivery is imminent within a short cutoff window, and whether the order
contains service-only line items. All four get checked, and I compute that same logic consistently
across the different read endpoints so list, details, and shipment views never disagree about
whether an order can still be cancelled."

================================================ Step 7 ================================================

The interviewer asks: "What happens when one of those twelve sources is down?"

"It degrades one field, not the whole response. Every one of those MySQL lookups and service calls
is independently try/caught and falls back to an empty array, false, or null rather than throwing,
and I use optional chaining everywhere downstream so a missing field never crashes response
construction. If pharmacy is down, you lose the prescription-status field. You don't lose the order.

That's a deliberate trade — I'd rather ship a customer a response missing one soft field than fail
the whole page because one of twelve integrations had a bad five minutes."

================================================ Step 8 ================================================

The honest maintainability card

"The fan-in function itself is close to nineteen hundred lines. That's a real cost, not a badge of
honor — it's harder to onboard someone into, harder to test in isolation, and every new source makes
the next person's diff bigger before it's smaller.

If I were decomposing it today, I'd split it by source-adapter: one small module per upstream that
owns fetching and normalizing that source's contribution, and a thin orchestrator that just
sequences the batched calls and merges the results. The batching discipline — collect all IDs first,
one call per source — would move into each adapter's interface so it's enforced by the shape of the
code, not by convention. I haven't done that refactor; I'd want to do it behind the existing
regression coverage before touching the wiring, not as a rewrite."

Cut these from your interview story:
❌ "It's three APIs." — It's six routes: three read operations, each with an app and a web variant
with different fee shapes. Undercounting this makes the backend-for-frontend story sound smaller
than it is.
❌ "Every source is equally critical." — They're not; pharmacy, NDR, and pricing tooltips are allowed
to degrade silently, while Mongo and Shopify are load-bearing. Be ready to say which sources are
which.
❌ "I built the whole read pipeline alone from day one." — I'm the dominant author of the current v3
read stack, but the batching pattern, retry wrapper, and some shared files carry other people's
groundwork. Speak to what I specifically built: the fan-in composition, the N+1 batching, the returns
double-count fix, and the COD split — not every line in the file.

Numbers you must know:
- Six customer-facing read routes: list, details, shipment × app/web.
- Twelve-plus distinct upstream sources feeding one response.
- Fan-in composition layer is roughly nineteen hundred lines.
- Read handlers retry up to four times with a fixed delay before falling back to a typed empty
  payload instead of a 500.
- Return window used in eligibility logic: ten days from delivery; superfast cancellability cutoff:
  a short fixed window before delivery.
- [NEED FROM ME]: Before/after latency numbers — p50/p95 — for the list or details endpoint once the
  batched fan-out replaced any earlier per-order pattern, if you have them.
- [NEED FROM ME]: What fraction of returns actually involve a Shopify order split across multiple
  fulfillments — i.e., how often the double-counting bug would have fired in practice.
- [NEED FROM ME]: Daily request volume through /post-order/* so I can frame the batching win at real
  scale.
