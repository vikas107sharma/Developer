# Supertails Backend — Post-Order Journey: Resume & Interview Analysis

Subject: Vikas Sharma. Repo: `/Users/vikas1141sharma/Developer/supertails-backend` (branch `production`, HEAD `5d9e449c` at analysis time). Read-only analysis; no writes, no app/DB execution, no secrets printed (`.env`, `gcloud-service-account.json` referenced by `constants.GCP_FILE_PATH` confirmed to exist, not opened).

---

## 1. Ownership (condensed)

**Sole-authored (own file, no other contributor in git history):** `webhook/postOrder/completeOrder/placeholderShipment.js`, `order/Functions/shipmentCodAllocation.js`, `webhook/postOrder/paidTcbTicket.js`, `test/placeholder-shipment.test.js`. Near-sole: `helperFunctions/consignmentMetafield.js`.

**Dominant author, whole v3 read-side stack:** `order/post.order.controller.js`, `order/Functions/postOrderFunctions.js` (every function cited below), `repository/order-management-repository.js`, `graphQL/ordersV2.js`, `selfServeAndReturns/Functions/returnsV2.js`.

**Shared files** (`webhook/postOrder/completeOrder/eddActions.js`, `webhook/deliveryNote/deliveryNoteWebhook.js`, `models/orderManagement/*`, `order/Functions/orderFunctionv3.js`, `order/Functions/GetOrderTrackingTileData.js`, `PUB-SUB/ClickPost/*`) — colleagues named Sachin, Ankit Singh, Shubham Rauthan and Akash Sahu contribute substantially to these files' overall history. His specifically-traceable additions inside them: the placeholder-shipment integration hooks in both `eddActions.js` and `deliveryNoteWebhook.js`; the `_id`-based shipment-match fix in the delivery-note webhook; the write-once consignment metafield; the `isWebOrder`/`displayFinancialStatus`/promise-enrichment fields on the Mongo schema; and the Mongo-backed `GetOrderTrackingTileDataV3`. Worth knowing before an interview: the bulk of `EddActionsV2`'s own scaffolding (the Promise Engine call, the archival-on-success/failure, the shipments-map construction) predates his five commits to that file — be ready to describe *his* additions precisely rather than the whole function. One number in the original brief for this task didn't hold up against the repo's history (`PUB-SUB/ClickPost/*` combined authorship looked far more evenly split than "Rakesh 15 / him 7") — noted so it isn't repeated as fact.

**Not his:** `order-management/Functions/backfillEddClickpostTracking.js`, `models/orderManagement/migrateOrders.js`, the legacy v1/v2 post-order routes in `order/order.controller.js` (that file's retry-with-backoff convention, which the v3 controller below reuses, originates there). `controllers/functions/ControlTower/*` does not exist anywhere in this repository (checked across branches) — could not verify.

**His interview story, verified claim-by-claim** (source: `/Users/vikas1141sharma/Developement/Developer/projects/phase1/post_order`): every factual claim in the 2-minute version is SUPPORTED by code — the webhook trigger, the service-only skip, the Promise Engine call, the Mongo document with empty `tracking{}` at creation, the delivery-note reconciliation with mismatch-tombstoning, the ClickPost tracking updates, the ~10-source fan-in, the N+1-avoidance-by-batching, the returns double-counting fix, and the COD-allocation-must-sum-exactly claim are all precisely matched by real code (evidence throughout this document). Two corrections: he undersells the API surface ("three APIs" — it's six routes, three read operations × app/web variants), and the write-side architecture he describes in general terms is shared infrastructure he extended rather than built from zero.

---

## 2. Architecture

The module is two asymmetric pipelines sharing one MongoDB collection (`orders`):

**Write side** (webhook-driven, ~4 external triggers → 1 document): Shopify order webhook → EDD/shipment planning → ERP delivery-note reconciliation → ClickPost tracking updates. Each stage is a separate webhook handler that reads-modifies-writes (or positionally patches) the same `orders` document, never a synchronous chain.

**Read side** (request-driven, 1 request → N backend calls → 1 response): this is the more technically significant half. `getPostOrderShipmentDetails` / `formatPostOrderShipmentData` (`order/Functions/postOrderFunctions.js:243-1119`) function as a **backend-for-frontend response-composition gateway**, not a thin read wrapper:

- **API fan-in / multi-source aggregation** — at least 10 distinct upstreams are called from this one layer: Shopify Admin GraphQL (`graphQL/ordersV2.js`, hand-built query strings + cursor pagination), MongoDB `orders` (`repository/order-management-repository.js:getOrdersByIds`), four independent MySQL/Sequelize tables (`revised_edd`, `failed_deliveries`, `journey_tracking`, `delivery_partner_contact`), Returns/ClickPost (`selfServeAndReturns/Functions/returnsV2.js`), Pharmacy (`pharmacy/Functions/getPharmacyItemsFromOrderId.js`, `getPharmacyStatus.js`), Pricing (`pricing/services/feeResolver.js:loadFeeTypeNameMap`), and a COD→prepaid conversion source (`codToPrepaidOrders`).
- **Backend-for-frontend behaviour** — `order/post.order.controller.js` exposes six routes, not three: `/list`, `/details`, `/shipment` and `/list/web`, `/details/web`, `/shipment/web`. Inside `getPostOrderDataById` (`postOrderFunctions.js:104-240`), web orders get one fee-breakdown shape (`:161-181`, top-level `cod_fee`/`platform_fee`/`delivery_fee`) while app orders get a *different* shape gated by an `ocv` rollout marker (`:182-211`) — dynamic pricing-service titles when present, a legacy fixed COD/DELIVERY/PLATFORM triplet when absent. (The gate itself, `pricing/services/rolloutGate.js:usePricingV2`, is a separate pricing-team module; his code is the consumption/branching on it.)
- **Response orchestration** — `formatPostOrderShipmentData` (`:656-1119`) runs a fixed pipeline per request: build Shopify SKU map → build a Mongo-shipment map that **excludes tombstoned (`mismatched`) shipments but re-admits an active placeholder** (`:696-710`) → group returns (`processReturnOrdersv3`, `:713`) → batch-collect every AWB across every order → one revised-EDD lookup, one COD-to-prepaid lookup for the whole batch (`:715-738`) → per-order status/message computation → returns pass (`processShipmentsQcV3`) → pharmacy override pass → COD-to-prepaid final pass → shipment-total pass.
- **Conditional business rules** — cancellability is computed from four independent, order-dependent signals (any Shopify fulfilment exists; QC/hyperlocal delivery type with any tracking status; superfast delivery within 6 hours, `:766`; Services line items present) and is recomputed slightly differently in three separate call sites (`getPostOrderDataById:121-134`, `getPostOrderShipmentDetails:270-280`/`:300-302`, `formatPostOrderShipmentData:745-772`).
- **Data normalization** — a SKU-keyed map (`shopifyLineItemsMap`, `:659-673`) merges Shopify fields (title/image/price/variant/tags) with Mongo fields (quantity actually shipped, promise, tracking) into one line-item shape, and re-nests `variant.node.{id,sku}` so callers see one consistent shape regardless of which upstream produced the base record.
- **Failure isolation** — optional chaining throughout; every MySQL lookup (`getRevisedEDDData:1185-1203`, `getPostOrderRevisedEDD:1442-1466`, `getPostOrderTrackingDetails:1468-1495`, `getPostOrderNdrStatus:1497-1522`) is independently try/caught, degrading to `[]`/`false`/`null` rather than throwing, so one dead upstream drops one field, not the response.
- **Consistency handling** — the placeholder-shipment mechanism (below) keeps the MRP total and the rendered item list from disagreeing; the COD-allocation invariant keeps three displayed numbers from disagreeing; `mismatched`-as-tombstone keeps one document as the single source of truth without destructive deletes.
- **Domain-specific state transformation** — a chain of six functions (`getFromattedEDD → getEddMessage → computeEddMessage`, `getDeliveryPartnerMessage`, `applyDelayedSupplementaryStatus`, `formatRescheduledEDD`, all `postOrderFunctions.js:1205-1414` and `:1815-1956`) turns raw ClickPost status codes + Shopify fulfilment state + Mongo tracking into one human sentence ("Arriving by Tomorrow 10PM⚡️", "Missed delivery on Wed, 4th Sep"), including a QC-specific remap of status codes 12/13/14 → 9 "Delivery failed" (`:405-408`, `:840-842`).

**External systems touched:** Shopify Admin GraphQL, ClickPost (courier aggregator, webhook + Pub/Sub), a separate "Promise Engine" microservice (its own GCP App Engine app, `*.appspot.com`, used for both EDD-at-placement and warehouse-reallocation-at-delivery-note), an ERP (Frappe/ERPNext-shaped API: `supertails.api.update_sales_order`), Nugget (support ticketing), and internal Pricing/Pharmacy/Returns services.

---

## 3. Webhooks, routes, subscribers

| Endpoint | Handler | Purpose |
|---|---|---|
| `POST /webhook/post-order/edd-actions` | `EddActionsV2` (`eddActions.js:81-432`) | Order placed → skip service-only orders (`IsVendorServicesOnly`, `webhook.controller.js:315-320`) → fire-and-forget paid-TCB ticket (`:323-329`) → call Promise Engine → write `orders` doc |
| `POST /webhook/post-order/edd-actions-old` | `EddActions` (legacy v1) | Same skip/idempotency shape, kept for rollback; **has** the idempotency check that `/edd-actions` lacks |
| `POST /webhook/delivery-notes` | `handleDeliveryNoteWebhook` (`deliveryNoteWebhook.js:990-1139`) | ERP packs an order → reconcile against planned shipments |
| ClickPost webhook → Pub/Sub `clickpost_tracking` → subscriber | `updateTrackingStatus` (`repository/order-management-repository.js:21-157`) | Courier scan → positional tracking update |
| `GET/POST /post-order/*` ×6 (`post.order.controller.js`) | `getPostOrderListForCustomer`, `getPostOrderDataById`, `getPostOrderShipmentDetails` | Customer-facing read APIs, app + web |

**Write-side detail.** `EddActionsV2` filters `vendor.includes("Services")` line items (`:99`), extracts `LATITUDE`/`LONGITUDE` from `note_attributes` (`:119-129`), requires a zip (`:107-113`), calls `GET .../v2/cartedd` with comma-joined SKUs+quantities and `updateOrderCount:false`, 30s timeout (`:176-201`), archives the raw Promise Engine response into `orderPromises` on **both** success (`:205-212`) and failure (`:216-224`), and — even on EDD failure — still inserts the `orders` doc behind an existence guard so a webhook retry can't double-insert (`:227-252`). Shipments are keyed by `shipmentKey || SHIPMENT_<warehouseId>_<n>` (`:304`); a re-delivered webhook **appends** new shipments to the existing array and marks them `mismatched:true` (`:392-399`) rather than overwriting. `sendEddToERP` (`webhook/postOrder/completeOrder/helper.js:645-684`) posts to the ERP with a 10s timeout and swallows all errors into the logger.

**Delivery-note detail — the reconciliation algorithm** (`handleDeliveryNoteWebhook`, `:990-1139`), 8 steps:
1. Archive the raw DN payload to `erpDeliveryNotes` (`:1014-1020`); map ERP warehouse names to internal names.
2. Fire-and-forget a Shopify order-note refresh with the latest EDD (`updateShopifyNotesWithLatestEDD`, `:1027-1031`).
3. `ensureOrderExists` (`:448-493`) self-heals a missing order by POSTing back to its own `/webhook/post-order/edd-actions` and polling Mongo after a fixed 2s sleep.
4. `handleCancelledDeliveryNotes` (`:502-556`) tombstones shipments matching a cancelled DN (`mismatched:true`, `isUpdated:false`), never deletes them.
5. `matchExactDeliveryNotes` (`:566-636`) matches DN↔shipment on warehouse+SKU+quantity (`isExactMatch`, `:20-65`), looking shipments up by **Mongo `_id`, not `shipmentId`** (`:602-606`) — `shipmentId` is not guaranteed unique once re-delivery has appended shipments, so `shipmentId`-based lookup could silently patch the wrong row.
6. `matchEmptyDnShipments` (`:648-720`) matches remaining shipments that have no DN yet against remaining DNs, same `_id` discipline.
7. `markRemainingShipmentsMismatched` (`:729-765`) tombstones everything left over, explicitly skipping the placeholder (already `mismatched:true`) and anything already processed.
8. `createShipmentsForRemainingDNs` (`:774-826`) calls the Promise Engine (`GET .../v2/warehouse-edd`, 30s timeout, `:122-190`) for any DN nothing predicted, then re-syncs the placeholder shipment (`:1112-1123`).

A `processedDnNumbers` Set gives within-run DN dedup across all 8 steps (`:1038`, threaded through every step).

**Tracking detail.** `updateTrackingStatus` targets exactly one shipment via positional `arrayFilters` on `deliveryNoteNumber` (`:72-76`, `:132-144`); sets `delivered_at` only on status `8` (`:59-61`); attaches NDR info only on status `9` (`:91-99`); dedups on `uniqueKey = waybill-statusCode-timestamp` via an `$elemMatch` pre-check before the write (`:87`, `:108-126`); pushes with `$position:0` so history reads newest-first (`:136-141`); and returns `false` + logs on any failure instead of throwing (`:149-156`) — callers never crash on a bad ClickPost payload. A second, more defensive variant exists in the same file, `updateLatestCPStatusCodeInPostOrderRes` (`:159-220`), which additionally refuses to overwrite eight "protected" terminal-ish status codes — worth confirming with the team whether this Mongo-targeted version is the one actually wired up, since the only call sites found in this checkout import a same-named function from `webhook/helper.js` instead.

---

## 4. Database

**MongoDB** — 4 collections (`models/orderManagement/index.js`): `orders`, `orderPromises`, `erpDeliveryNotes`, `trackingStatusLogs`. `orders` (`orders.js`) is `strict:false` (allows dynamic fields) with `timestamps:true`; top-level `orderId`/`email`/`orderName`/`customerId`(indexed)/`orderDate`/`cancelled_at`/`displayFinancialStatus`/`isWebOrder`/`lineItems[]`; `shipments[]` sub-documents each carry `shipmentId`, `items[]`, a `promise{}` sub-doc (warehouse, deliveryType, deliveryDateTime, dayCount, deliveryInMinutes, cutoffTime, `messages{}`), a `tracking{}` sub-doc (ids, `status{}`, `trackingHistory[]` with per-entry `uniqueKey` and `failedDeliveryInfo{}`), plus `isUpdated`, `mismatched`, `isPlaceholderShipment`, `delayCommSent`, `dispatchDelayCommSent`. Indexes: `orderId`, `orderName`, `customerId`, `createdAt:-1` (four explicit `.index()` calls, plus `customerId` also carries a field-level `index:true` — a small, harmless redundancy: the same index is effectively declared twice).

**Array-update semantics.** Every tracking/status write uses positional `arrayFilters` (`shipments.$[shipment]...`) rather than document rewrite — atomic at the document level, so two shipments in the same order can be updated independently without a read-modify-write race against each other.

**MySQL (Sequelize)** side tables read by the post-order layer: `revised_edd`, `failed_deliveries`, `journey_tracking`, `delivery_partner_contact`, plus (via `orderFunctions.js`) a legacy `postOrderRes` table and, via `GetOrderTrackingTileData.js`, `order_tracking_flags` and `features`.

**Connection config** (`config/database/order-management.js`): Mongoose pool `maxPoolSize:50`, `minPoolSize:10`, `maxIdleTimeMS:30000`, `serverSelectionTimeoutMS:5000`, `socketTimeoutMS:45000`, with connect/error/disconnect handlers and a SIGINT graceful-close.

---

## 5. Async / distributed

**Pub/Sub.** GCP `@google-cloud/pubsub`, topics `clickpost_tracking` / `clickpost_communication` (`PUB-SUB/ClickPost/publisher.js`), subscriptions with `flowControl.maxMessages:5` (`subscriber.js:15-18`), manual `message.ack()` on success / `message.nack()` on any thrown error (`:148`, `:158`). A 60s heartbeat log reports listener liveness (`:200-208`). The subscriber refuses to start outside `GAE_ENV=standard` via a top-level `return` (`:20-25`).

**Idempotency / dedup, three different mechanisms across three layers:**
- Route-level: `HasEventOccurred(id, "POST_ORDER::EDD_ACTIONS")` is **commented out** on the live `/post-order/edd-actions` route (`webhook.controller.js:307-314`) but still enforced on `/edd-actions-old` (`:339-343`) — the current production path has no route-level replay guard.
- Write-level: `EddActionsV2` guards only the EDD-*failure* insert path with an existence check (`:227-252`); the success path instead **appends** shipments and flags them `mismatched:true` on redelivery, which is a reconciliation strategy, not a replay guard.
- Tracking-level: `updateTrackingStatus`'s `uniqueKey` dedup (`waybill-statusCode-timestamp`) is a genuine idempotency key, checked before every history push.

**Ordering / replay safety.** The delivery-note webhook is explicitly designed to be safe to replay: `processedDnNumbers` prevents re-processing a DN within one run, and `mismatched` tombstoning (never delete) means a stale plan simply stops being shown rather than corrupting state. The tracking-history `$position:0` push plus per-entry `uniqueKey` similarly tolerates duplicate ClickPost deliveries.

---

## 6. Infrastructure

Google Cloud Platform, deployed as **App Engine** services (`package.json`: `gcloud app deploy --project=supertails-backend`, plus `deploy:staging`/`deploy:knp`/`deploy:pre-check` variants; `GAE_ENV` checked at runtime). The Promise Engine is a **separate** App Engine app called over HTTP (`https://promise-engine-371111.el.r.appspot.com`). GCP Pub/Sub for async courier events; GCP Secret Manager and GCP Storage present as dependencies; a service-account key file is referenced via `constants.GCP_FILE_PATH` (existence only noted, never opened). Logging fans out to Loggly (`winston-loggly-bulk`) through a central `logger/logger.js`, with New Relic APM also wired in. A git-based preview-environment workflow exists (`preview:push`/`preview:pr` npm scripts push to `preview/<branch>` and open a GitHub PR via `gh`).

---

## 7. Reliability & performance mechanisms (with evidence)

- **N+1 avoidance by batching.** `getPostOrderListForCustomer` collects every order ID first (`postOrderFunctions.js:75`), then makes exactly one `getOrdersByIds` call (`:80`) and one `getReturnedOrders` call (`:83`) for the whole page — not one query per order. Inside `formatPostOrderShipmentData`, every AWB across every order in the batch is collected first (`:715-725`), then **one** `getRevisedEDDData(allAwbs)` call (`:728`) and **one** `codToPrepaidOrders(...)` call (`:738`) cover the entire batch.
- **Retry + safe fallback on reads.** `order/post.order.controller.js`'s `/list`, `/details`, `/list/web`, `/details/web` handlers retry their data call up to 4 times with a 1000ms delay between attempts, falling back to a typed empty payload (`{"orderData":[],"pageData":{...}}` or `{}`) instead of a 500 after the last retry (e.g. `:8-44`).
- **Failure isolation.** Every MySQL lookup used by the read side is individually try/caught and degrades to `[]`/`false`/`null` (`postOrderFunctions.js:1185-1522`); optional chaining is used pervasively so one missing upstream field never throws.
- **Non-blocking side effects.** The paid-TCB ticket creation (`webhook.controller.js:323-329`), the Shopify note refresh (`deliveryNoteWebhook.js:1027-1031`), and `sendEddToERP` are all fire-and-forget or independently caught, so a slow/broken downstream (Nugget, Shopify, ERP) never blocks the primary write.
- **Map-based indexing over repeated scans.** SKU→line-item, SKU→EDD, AWB→tracking-URL and AWB→fulfilment-ID lookups all build a `Map` once per request (e.g. `:659-692`, `:785-801`) rather than re-scanning arrays per shipment.
- **Timeouts on every outbound HTTP call**: Promise Engine 30s (`eddActions.js:200`, `deliveryNoteWebhook.js:168`), ERP 10s (`helper.js:660`), self-heal edd-actions call 60s (`deliveryNoteWebhook.js:471`) — no call in this module is unbounded.

---

## 8. Design decisions, trade-offs, known gaps

- **Tombstone (`mismatched:true`) over delete.** Every reconciliation step marks shipments as stale rather than removing them: history is preserved, array indices stay stable for the positional matching that depends on them, and a "delivered" check can still be computed correctly later. Trade-off: the `orders` document only grows, and every reader must remember to filter `mismatched`.
- **Placeholder-shipment design** (`placeholderShipment.js`, full file, sole-authored). The Promise Engine silently drops any SKU it can't plan (`deliveryFormat: "Out of Stock"`) from `shipmentInfo[]`, so that SKU reaches `lineItems` but no shipment — invisible to an app that renders only shipment items, while `totalMrp` still bills it. The file's own comments cite two real order IDs this happened on (`ST334763112507`, `ST338428212507`). The fix keeps exactly one `SHIPMENT_PLACEHOLDER_<orderId>` row holding whatever SKUs no real shipment covers, computed via a sorted `sku:qty` fingerprint (`:83-88`) so an unchanged placeholder is never rewritten; retirement **empties `items`** rather than deleting the row (`:107-114`) because later steps carry positional array indices across a re-fetch and a delete would shift every subsequent shipment's index; `promise` and `tracking` are `null` (not `{}`) specifically because a truthy-but-empty `promise` would make the message layer render a committed-sounding "within 2-3 days" for an item that isn't even shipping; the row is always appended **last** because the delivery-note webhook carries positional indices from an earlier snapshot. It is called from both write paths (`EddActionsV2` and the DN webhook's STEP 8) and is idempotent by design, so both can call it freely.
- **`arrayFilters` over document rewrite** for tracking updates: smaller network payload, atomic per-shipment, and avoids a full read-modify-write race between two ClickPost webhooks for two different shipments of the same order. Residual gap: two *concurrent* webhooks carrying the *same* `uniqueKey` could both pass the `$elemMatch` pre-check before either executes its `$push`, producing a duplicate history entry — the pre-check-then-write is two round trips, not one atomic operation.
- **Returns: reduce quantity everywhere, build the return shipment once** (`processShipmentsQcV3`, `postOrderFunctions.js:1531-1807`). Shopify can report the same line item across multiple fulfilments when an order is split (`:1542-1543`, verbatim in the code's own comment), so the algorithm subtracts the returned quantity from **every** matching line-item instance for display consistency (`:1566`), while building the **separate return-shipment entry exactly once per `(clickpostReturnId, sku)`** via a dedicated `Set` (`:1568-1573`) and a parallel `skuReturnedQuantityMap` (`:1576-1578`) — decoupling "how many places show the reduced quantity" from "how many times a returned-item record is created."
- **COD allocation: proportional by net item value, fixed denominator, remainder to the last shipment only once fully shipped** (`shipmentCodAllocation.js`, full file, sole-authored). The denominator is the *whole order's* item value (all line items, shipped or not, `:108`) rather than only the shipments seen so far, so a shipment's collectable amount never shifts as later fulfilments appear. `item_total` is derived as `amount_to_collect - fee_component` (`:170`) rather than independently rounded, which is what guarantees the three displayed numbers always sum exactly. Fees are capped at the order total (`:112`) so a bad fee row can never ask for more cash than the order is worth; a real bug this replaced is documented in the file's own comment (order `ST332418412507`: COD+platform fees of 44 against a 30-rupee coupon, where an `orderTotal - itemValue` residual approach under-reported the fee by 30).
- **Server-side fan-in over client fan-out.** All ~10 sources are merged once, server-side, into one response per route; the alternative (client calling 10 endpoints and merging) was not chosen — consistent with the stated read-side design goal of "one screen, ten sources."
- **Known gap, by design choice not oversight:** the live `/post-order/edd-actions` route has its idempotency check commented out (`webhook.controller.js:307-314`) while the `-old` route still enforces it — worth being able to explain in an interview why that trade was made (likely: the append+`mismatched` reconciliation strategy in `EddActionsV2` was judged sufficient replacement, given it tolerates redelivery structurally rather than by blocking it).

---

## 9. Numbers

**(a) Derivable from code, with source:**
- 29 named regression tests across 7 labelled categories (H=hole/root-cause, R=render, C=COD, G=cross-consumer guard, E=EddActionsV2 write path, D=delivery-note steps, P=pharmacy interaction) in `test/placeholder-shipment.test.js`, run via a hand-rolled `runTest()` harness (pass/fail/total counters, non-zero exit on failure) — no Jest/Mocha/Sinon in this repo; mocking is done by directly swapping entries in Node's `require.cache` (`stubModule`, test file `:55-70`).
- 6 customer-facing read routes (`order/post.order.controller.js`, 223 lines), retry×4 / 1000ms backoff each.
- 1975 lines in `order/Functions/postOrderFunctions.js`; 234 lines in `shipmentCodAllocation.js`; 185 lines in `placeholderShipment.js`; 106 lines in `paidTcbTicket.js`; 1253 lines in `graphQL/ordersV2.js`.
- 4 MongoDB collections; `orders` has 4 explicit indexes + 1 field-level index (customerId, declared twice).
- Timeouts: Promise Engine calls 30000ms; ERP push 10000ms; delivery-note self-heal 60000ms; Mongo `serverSelectionTimeoutMS` 5000ms, `socketTimeoutMS` 45000ms; Mongoose pool 10–50 connections.
- Pub/Sub subscriber `flowControl.maxMessages: 5`; heartbeat log every 60000ms.
- Return window: 10 days from delivery (`postOrderFunctions.js:848`); superfast cancellability cutoff: 6 hours before delivery (`:766`).
- Node engine `>=22.0.0`; key dependency versions in Section 13.

**(b) Missing metrics — exact questions, and which bullet each strengthens:**
1. *(Strengthens the placeholder-shipment bullet.)* Roughly how many orders were affected by the out-of-stock-item-invisible bug before the fix shipped — do you have a count, an error-rate, or a support-ticket count tied to `ST334763112507`/`ST338428212507`-style cases?
2. *(Strengthens the COD-allocation bullet.)* What fraction of COD orders split into more than one shipment, or do you have a rupee figure for the under-collection the old `orderTotal - itemValue` residual approach caused on `ST332418412507`-style orders?
3. *(Strengthens the read-side fan-in / N+1 bullet.)* Do you have before/after latency numbers (p50/p95) or a query-count reduction for the post-order list/details endpoints after the batched-fan-out pattern was applied?
4. *(Strengthens the returns bullet.)* Roughly what volume of returns involve a Shopify order split across multiple fulfilments — i.e., how often would the double-counting bug actually have fired?
5. *(Strengthens the delivery-note reconciliation bullet.)* How often does STEP 7 (create-shipment-for-unpredicted-DN) actually fire versus exact-match — i.e., what fraction of orders ship differently than originally promised?
6. *(Strengthens the paid-TCB-ticket bullet.)* Roughly how many Nugget tickets has `createPaidTcbTicketIfEligible` created since it shipped?
7. *(General scale, for framing any bullet.)* Approximate daily order volume / request volume through `/post-order/*` — this is the kind of "at scale" qualifier that turns several of the bullets below into much stronger resume lines, and only you can supply it.

---

## 10. Candidate resume bullets

Ordered by resume relevance. Each cites file:line evidence; for shared files, only mechanisms with direct evidence of his authorship are claimed.

1. **Backend-for-frontend order-aggregation gateway:** Built the server-side response-composition layer powering `/post-order/*`, fanning out to Shopify GraphQL, MongoDB, four MySQL tables, and Returns/Pharmacy/Pricing services to assemble one consistent customer response across six app/web route variants with per-client fee shapes.
   Evidence: `order/Functions/postOrderFunctions.js:243-1119`, `order/post.order.controller.js:1-224`.

2. **Placeholder-shipment reconciliation system:** Designed and shipped an idempotent mechanism keeping exactly one "held item" shipment row per order for SKUs the promise engine can't plan, using a sorted quantity fingerprint to avoid redundant writes and emptying rather than deleting the row so positional array-index matching elsewhere stays intact.
   Evidence: `webhook/postOrder/completeOrder/placeholderShipment.js:1-185` (sole-authored), wired into `eddActions.js:397,404` and `deliveryNoteWebhook.js:1112-1123`.

3. **Returns handling without double-counting:** Built the shipment-reformatting step that reduces outbound quantity across every matching Shopify line-item instance while constructing the corresponding return-shipment record exactly once per return request, specifically handling Shopify's habit of repeating one line item across multiple fulfilments on a split order.
   Evidence: `order/Functions/postOrderFunctions.js:1531-1807` (`processShipmentsQcV3`), esp. `:1542-1543`, `:1566`, `:1568-1578`.

4. **Proportional COD-allocation engine:** Engineered the algorithm splitting a COD order's item value and fees across however many shipments it becomes, using a fixed whole-order denominator so a shipment's collectable amount never shifts as later fulfilments appear, and deriving one of the three displayed figures from the other two so they always sum exactly.
   Evidence: `order/Functions/shipmentCodAllocation.js:1-234` (sole-authored), esp. `:108`, `:141-161`, `:170`.

5. **Shipment-matching correctness fix in ERP delivery-note reconciliation:** Diagnosed and fixed a collision in the delivery-note↔shipment matching step where duplicate `shipmentId`s (created when a webhook redelivery appends shipments) could let a delivery note silently update the wrong parcel; replaced the lookup key with MongoDB's own unique `_id`.
   Evidence: `webhook/deliveryNote/deliveryNoteWebhook.js:602-606`, `:679-682`.

6. **Positional, dedup-safe courier-tracking writes:** Own the MongoDB update path translating ClickPost webhooks into shipment state — targets exactly one shipment via positional `arrayFilters` on delivery-note number, prepends new tracking-history entries, and dedups on a `waybill-statusCode-timestamp` key via a pre-write existence check.
   Evidence: `repository/order-management-repository.js:21-157`, esp. `:72-76`, `:87`, `:108-144`.

7. **N+1-safe multi-source read pipeline:** Eliminated per-order query fan-out on the order-list and order-details reads by collecting every order ID or waybill across the whole batch first, then issuing exactly one downstream query per data source for the entire page.
   Evidence: `order/Functions/postOrderFunctions.js:75-83`, `:715-738`.

8. **Domain status-translation layer:** Built the chain turning raw courier status codes, Shopify fulfilment state, and delay calculations into single customer-facing sentences ("Arriving by Tomorrow 10PM⚡️", "Missed delivery on Wed, 4th Sep"), including a quick-commerce-specific remap of three otherwise-generic failure codes to one "Delivery failed" state.
   Evidence: `order/Functions/postOrderFunctions.js:1205-1414`, `:1815-1956`.

9. **Cross-consumer regression suite without a mocking framework:** Wrote 29 categorized regression tests proving the placeholder-shipment invariant holds consistently across five independent consumers — COD splitting, referral-reward delivery status, refund evidence, the tracking tile, and the shipment-detail read path — using direct `require.cache` substitution since the repo ships no Jest/Mocha/Sinon.
   Evidence: `test/placeholder-shipment.test.js:1-1028` (sole-authored).

10. **Idempotent, SKU-triggered support automation:** Shipped a fire-and-forget handler that opens a formatted Nugget support ticket whenever a specific SKU appears on a confirmed order, deduplicated through the same event-occurrence log used elsewhere in the write path so a webhook replay never double-files a ticket.
    Evidence: `webhook/postOrder/paidTcbTicket.js:1-106` (sole-authored), wired at `webhook/webhook.controller.js:323-329`.

11. **Write-once audit trail for a mutable Shopify attribute:** Designed a metafield pair separating an immutable order-creation snapshot from a live-refreshed "latest EDD" value, plus a merge-not-replace write helper, so Shopify's destructive whole-attribute-list update semantics can no longer erase either the audit history or unrelated order attributes.
    Evidence: `helperFunctions/consignmentMetafield.js:1-255`, called from `webhook/deliveryNote/deliveryNoteWebhook.js:934-946`.

12. **Multi-signal cancellability engine:** Implemented order/shipment cancellability as a conjunction of four independent signals — existing Shopify fulfilment, quick-commerce delivery type with any tracking status, imminent superfast delivery, and service-only line items — recomputed consistently across three separate read endpoints.
    Evidence: `order/Functions/postOrderFunctions.js:121-134`, `:270-280`, `:745-772`.

13. **Backward-compatible API evolution for pricing rollout:** Built the response-shape switch letting the order-details endpoint serve either dynamic, pricing-service-driven fee titles or the legacy fixed fee triplet from one code path, gated on a client-supplied rollout marker, so older app builds keep working unmodified during a live pricing migration.
    Evidence: `order/Functions/postOrderFunctions.js:182-211`.

14. **Shopify GraphQL query layer for the v3 read side:** Own the hand-built, cursor-paginated GraphQL query surface (order list, order detail, shipment-by-AWB) that the entire post-order read pipeline is built on, including the quick-commerce-specific query variants it consumes today.
    Evidence: `graphQL/ordersV2.js:1-1253`, consumed at `order/Functions/postOrderFunctions.js:66,106,297,521`.

15. **Migrated the customer order-tracking tile off MySQL onto the Mongo-based pipeline:** Added a MongoDB-backed version of the in-app tracking-tile feature that reuses the existing multi-source formatter instead of duplicating its logic, and added mismatched-shipment filtering so a tombstoned or placeholder row can't keep a delivered order's tile alive.
    Evidence: `order/Functions/GetOrderTrackingTileData.js:186-253` (`GetOrderTrackingTileDataV3`), `:412-417`.

---

## 11. Interview material

**Hard problems**

1. *Why does the delivery-note exact-match step look shipments up by MongoDB `_id` instead of `shipmentId`, and what bug would return if you reverted it?* — `shipmentId` is generated as `SHIPMENT_<warehouseId>_<n>` and is **not guaranteed unique**: a redelivered webhook appends new shipments to the array without checking for a collision against an existing key. A naive `findIndex(s => s.shipmentId == x)` returns the *first* match, so a delivery note could silently patch a stale or unrelated shipment instead of the one it actually belongs to, while the real target stays un-reconciled forever. `_id` is Mongo's own guaranteed-unique key, so it can't collide (`deliveryNoteWebhook.js:602-606`).

2. *Walk through why `syncPlaceholderShipment` empties `items` on retirement instead of deleting the shipment.* — Two other functions (`matchExactDeliveryNotes`, `matchEmptyDnShipments`) snapshot `order.shipments` into a plain array, do work, then re-fetch the document and use the **original array index** to write back (`freshOrder.shipments[shipmentIndex] = ...`). If retirement removed an element, every subsequent shipment's index would shift by one between the snapshot and the write-back, and the wrong shipment would be mutated. Emptying `items` keeps `_id` and index stable while `processShipmentsQcV3` naturally drops any shipment with zero line items from the rendered response.

3. *Why is COD allocation keyed by a sorted `shipmentId` string rather than array order, and why does only the "fully shipped" branch let the last shipment absorb the rounding remainder?* — Two different endpoints (`getPostOrderShipmentDetails`'s SKU-based and AWB-based branches) build the shipments array in different orders but must agree on *which single shipment* absorbs the leftover paisa, because each request only reads out one shipment's slice of a Map computed fresh every time. Sorting by `shipmentId` makes that choice deterministic regardless of caller. Restricting remainder-absorption to `fullyShipped` (`shippedValue ≈ orderItemValue`) matters because on a *partially* fulfilled order, letting an existing shipment silently swallow the value of a not-yet-created shipment would make that shipment's price change again the moment the next fulfilment appears.

4. *How does the returns mechanism avoid double-counting when Shopify reports the same line item across multiple fulfilments?* — Two separate counters exist on purpose: the *display* quantity is decremented on every matching line-item instance the loop encounters (so every rendered copy is consistent), but the *return-shipment record* is only created once per `(clickpostReturnId, sku)` pair via a `Set` guard, and the *tracked-for-later-use* returned quantity is likewise accumulated once per pair via a separate map. Decoupling "how many places show it" from "how many times we record it" is what prevents a doubled refund total.

5. *`updateTrackingStatus` does a pre-check query then a separate `$push` — what race does that still allow, and how would you close it?* — Two ClickPost webhooks carrying the identical `uniqueKey` could both execute the `$elemMatch` existence check before either has pushed, both see "not present," and both push, producing a duplicate history entry. Closing it fully would need either a single atomic `updateOne` with an `$elemMatch`-in-filter + `$addToSet`-style guard (harder to express for a subdocument-array uniqueness check across nested fields) or a unique compound index enforced at the database layer.

**Follow-up questions**

- Why `null` and not `{}` for a placeholder's `promise`/`tracking` fields? (A truthy-but-field-less `promise` makes the message layer fall through to a committed-sounding default rather than "Arriving soon.")
- What happens if two `/post-order/edd-actions` webhook deliveries for the same order race on the EDD-failure existence guard? (It's a plain `findOne` then conditional `insert` — not atomic; true concurrency, not just sequential retries, could still double-insert.)
- Why derive `item_total` instead of computing and rounding it independently? (Rounding three numbers independently can break `a + b = c` by a rupee; deriving the third from the other two rounded values makes the invariant unconditional.)
- What's the consistency model between the fire-and-forget Shopify note update and the MongoDB write in the same delivery-note webhook run — can they diverge? (Yes; the Shopify call is best-effort and only logged on failure, never retried or surfaced, so a persistent Shopify outage silently drifts the note away from Mongo's state.)
- Why does `getPostOrderShipmentDetails` capture `allMongoShipments` before narrowing `mongoOrder.shipments` down to one AWB? (The COD split needs every sibling shipment to compute its ratio; by the time the AWB branch has narrowed the array, the siblings needed for the denominator are gone.)
- The commented-out idempotency check on the live `/edd-actions` route, versus the still-enforced one on `/edd-actions-old` — what's the argument for that being intentional rather than a regression? (The append+`mismatched` strategy in `EddActionsV2` tolerates redelivery structurally, so a route-level block became redundant — but be ready to defend that this is a deliberate trade, not an oversight.)
- If asked to extend this toward exactly-once semantics end-to-end, what would you add? (A durable idempotency key per webhook delivery, checked and recorded atomically with the write — the current `uniqueKey`/existence-check patterns are close but each has a check-then-act gap.)

---

## 12. Red flags (genuine technical issues only)

- The live `/webhook/post-order/edd-actions` route has its replay-dedup check commented out (`webhook.controller.js:307-314`) while the same check is still enforced on `/edd-actions-old` (`:339-343`) — be ready to explain why the newer path is considered safe without it.
- `ensureOrderExists` self-heals a missing order by making an HTTP call back to its own service and then sleeping a fixed 2000ms before re-reading Mongo (`deliveryNoteWebhook.js:462-483`) — a fixed sleep as the only synchronization is fragile under load; a slower-than-2s downstream Promise Engine call would make this return an order that still doesn't exist.
- `updateTrackingStatus`'s dedup is check-then-act, not atomic — two concurrent identical webhooks can both pass the pre-check and both push, producing a duplicate `trackingHistory` entry (see interview problem 5 above).
- The Mongoose `orders` schema indexes `orderId` but does not mark it `unique`, and `EddActionsV2`'s new-order path is a plain `findOne` existence check before insert — under true concurrent webhook delivery (not just sequential retries) this does not fully prevent two documents for the same order.
- `order/Functions/orderFunctionv3.js` still exports what looks like an earlier generation of the whole read pipeline (`getOrderListForCustomerv3`, `getPostOrderShipmentDetailsv3`, `formatShipmentDataV3`, `getOrderDataByIdV3`) alongside the currently-wired `processShipments`/`processReturnOrdersv3`/`formatDateTimeWithAmPm` — worth confirming whether the older four are genuinely dead code before an interviewer asks which version is live.
- `repository/order-management-repository.js` defines and exports a Mongo-targeted `updateLatestCPStatusCodeInPostOrderRes` (`:159-220`) with a protected-status-code list, but no caller of *that specific copy* was found in this checkout — the live ClickPost handlers import a same-named function from `webhook/helper.js` instead. Confirm which one is actually authoritative before citing the protected-status-code behaviour as live.
- Six near-identical route handlers (three read operations × app/web) each carry their own copy of the retry-with-backoff wrapper rather than one parameterized implementation — real duplication that becomes a maintenance cost the moment the retry policy needs to change.

---

## 13. Tech stack evidenced in this code

- **Runtime:** Node.js `>=22.0.0` (`package.json engines`), using Node's native `--env-file` flag for local dev.
- **Web framework:** Express `^4.18.3`, one `express.Router()` per module, mounted centrally in `server.js`.
- **Databases:** MongoDB via Mongoose `^8.18.2` (the entire post-order write/read model); MySQL via Sequelize `^6.37.1` + `mysql2 ^3.9.2` (a legacy `mysql ^2.18.1` driver is also still a dependency) for `revised_edd`, `failed_deliveries`, `journey_tracking`, `delivery_partner_contact`, `postOrderRes`, `order_tracking_flags`, `features`, `fee_defaults`, `pincode_fees`.
- **Messaging:** Google Cloud Pub/Sub `^4.10.0` — topic/subscription pairs for ClickPost tracking and communications, client-side flow control, manual ack/nack.
- **Cloud platform:** Google App Engine (deploy via `gcloud app deploy`, `GAE_ENV` runtime checks, the Promise Engine as a sibling App Engine service), Google Cloud Storage `^7.11.0`, Google Secret Manager `^6.1.1`.
- **HTTP clients:** `axios ^1.9.0` (current code); the deprecated `request` package is still used in some GraphQL/legacy files (`graphQL/ordersV2.js`, `GetOrderTrackingTileData.js`).
- **Observability:** Winston `^3.10.0` + `winston-loggly-bulk ^3.2.1` (Loggly) behind a central `logger/logger.js`, alongside a separate legacy `Utils/logglyUtil.js` convention (two logging conventions coexist in this module); New Relic APM `^13.8.1`.
- **Caching:** Redis `^5.8.0` client and `memjs ^1.3.2` (Memcached, typical of App Engine standard environment).
- **Validation:** both Joi `^17.13.3` and Zod `^4.3.5` are dependencies (two validation libraries coexist repo-wide).
- **Auth/security:** `jsonwebtoken ^9.0.2`, `helmet ^7.1.0`, `cors ^2.8.5`, `nocache ^4.0.0`.
- **Payments:** `razorpay ^2.9.5`.
- **Dates/misc:** `moment ^2.30.1` + `moment-timezone ^0.6.0`, alongside hand-rolled IST-offset arithmetic in the post-order code itself (`+ 5.5*60*60*1000`-style adjustments throughout `postOrderFunctions.js`); `lodash ^4.17.21`; `uuid ^9.0.1`; `mjml ^5.1.0` (email templating); `exceljs`/`xlsx` (spreadsheet export); `h3-js` (geospatial hex indexing, used elsewhere in the delivery stack).
- **Testing:** no Jest/Mocha/Sinon anywhere in `package.json`. A bespoke runner (`npm test` → `node test/run-tests.js`) with hand-rolled `assert`-based test functions and manual `require.cache` substitution for dependency injection (`test/placeholder-shipment.test.js`).
- **Dev tooling:** `nodemon ^3.0.1`, `dotenv ^16.4.5`, a dedicated `scripts/validate-env.js`.
- **External APIs integrated by this module specifically:** Shopify Admin GraphQL, ClickPost, a bespoke Promise Engine microservice, an ERP with a Frappe/ERPNext-shaped method API, Nugget support ticketing.

---

*Output file: `/private/tmp/claude-501/-Users-vikas1141sharma-Developement-Developer/b40aed2b-9830-454e-b727-6e2138f29d5e/scratchpad/analysis/supertails-post-order.md`*
