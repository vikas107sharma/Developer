# Delivery Promise & EDD Engine: High-Level Design (as built)

**System:** Supertails Promise Engine · **Source of truth:** production branch, commit `4f07b42`, 28 Sep 2026 · **Scope:** the delivery-promise request path, its configuration model, and the jobs that feed it

**Evidence standard.** Every statement here describes what the code does. Nothing comes from the repository's own design documents, which describe several mechanisms the code does not implement. Caller behaviour comes from the storefront backend's code. Where the brief asks for a capability the system lacks, the section says so under **Not in this system**. Inferences are marked **Assumption**.

---

## At a glance

For a delivery pincode (plus the shopper's latitude/longitude, when available) and a list of SKUs with quantities, the engine decides three things:

1. **Where** each unit ships from. It searches for serviceable warehouses from the most local geography outward.
2. **How** the order splits. Units are packed into weight-capped shipments per warehouse.
3. **When** each shipment arrives. Each shipment passes through a configurable pipeline of SLA, cutoff, buffer and calendar rules.

Each answer carries a delivery timestamp, a day count, a delivery-type label, customer-facing copy, and a breakdown of every rule that contributed.

### Brief vs. implementation

| Brief item | What the code does | Status |
|---|---|---|
| Real-time EDD for PDP, cart, checkout | A per-SKU endpoint and a cart endpoint. The cart response carries the web-checkout copy. The cart engine also serves order-completion and delivery-note calls. | Implemented |
| Sub-50 ms latency | No latency target anywhere in code. One captured cart call took 1,443 ms. | **Not supported by evidence** |
| Separate Promise Engine / OMS / Inventory / ERP | One service holds EDD, its configuration admin, a copy of stock, and weather jobs. ERP pushes stock in. No OMS integration. | Partial |
| Point-in-polygon vs. H3 | H3 cell membership only (resolution 10). Exact point-in-polygon exists only in an admin lookup. | H3 only |
| Lat/lng → darkstore polygon → pincode → city → state | Lat/lng (resolved to polygons) → pincode → city → state | 4 levels, not 5 |
| Dynamic geofences, validated under concurrency | Admin-managed polygons, light validation, no locking | Partial |
| Darkstore / RFC / vendor sourcing tiers | Geographic levels plus a per-cluster warehouse priority. Facility type is never read. No vendor tier. | Partial |
| Cross-cluster reservation | A ledger scoped to one request. Nothing is reserved across requests. | Partial |
| All-or-nothing out-of-stock | Per SKU | Implemented |
| Split shipments by weight / dimensions | Weight only | Partial |
| Gift / sample routing | Suffix rules; a gift rides along with a main item's warehouse | Implemented |
| SLA matrix by weight slab | (cluster, warehouse, weight slab) → delivery type + SLA | Implemented |
| Hyperlocal windows vs. daily cutoffs | Both | Implemented |
| Static SCM buffers | Three scopes, summed | Implemented |
| Rain buffers and precedence over SCM buffers | Weather jobs plus an approval flow. Rain applies only when the warehouse has no SCM static buffer. | Implemented |
| Capacity buffers when `order_count + spill ≥ capacity` | Yes. The breach state is read through a cache (5 min by default). | Implemented, near-real-time |
| SKU / category tag buffers | Tag-based; there is no category model. Summed; can be negative. | Implemented (tags) |
| Pickup vs. delivery day-skips | Both | Implemented |
| Midnight, late-night and timezone rules | Fixed +5:30 offset; 22:00 default; 23:30 or later rolls to 13:00 next day | Implemented |
| Spatial, inventory and SLA-config caches | Redis per lookup (5 min default). No response cache on the current endpoints. | Implemented |
| Fail-open on Redis / weather / capacity failure | Redis and capacity writes fail open. Weather data goes stale. A rain-status or tag-buffer read failure fails the whole request. | Mixed |

---

# 1. Executive System Architecture

## 1.1 Core purpose

| Input | Notes |
|---|---|
| Delivery pincode | Required. Resolves the city and state, plus a pincode-level "required SLA minutes" value. |
| Latitude / longitude | Optional. Enables the polygon level of the search. |
| SKUs and quantities | Duplicate SKUs are merged by summing their quantities. |
| Order-count flag | Cart and warehouse-pinned endpoints only. After computing the promise, increments capacity counters for the warehouses and delivery types used. |
| Warehouse | Warehouse-pinned mode only. Computes the promise from one named warehouse. |

| Output | Contents |
|---|---|
| Per SKU | Warehouse, delivery type, delivery timestamp, minutes to delivery, day count, message tier and copy, quick-delivery flag, and a breakdown (SLA, each buffer, cutoffs, pickup time, skipped days and dates). Out-of-stock SKUs appear in the same list, marked "Out of Stock". |
| Per shipment (cart) | Shipment id, warehouse, cluster, polygon name, weight cap, items, total weight and quantity, the shipment's promise and copy, and rain information. |

## 1.2 Surfaces and entry points

Every current entry point is an HTTP GET endpoint on one service.

| Surface | Entry point | Engine | Evidence of caller |
|---|---|---|---|
| Cart | `/v2/cartedd` | Cart engine | The storefront backend's cart orchestrator (its "cart-edd" function) |
| Checkout (web) | The same cart response | Cart engine | The response carries the web-checkout message. There is no separate checkout endpoint. |
| Product level (per SKU, PDP-style) | `/v2/edd` | Product engine | The backend's EDD helper for SKU lists |
| Order completion | `/v2/cartedd` with the order-count flag | Cart engine | The backend's order-complete flow recomputes the placed order's EDD. Its Shopify-update path sets the flag, except for orders from internal email domains. |
| Fulfilment (delivery note) | `/v2/warehouse-edd` | Cart engine, pinned to one warehouse | The backend's delivery-note webhook passes the fulfilling warehouse |
| Allocation only | `/v2/warehouse-allocations` | Cart engine, stopping before any timing | The backend's surprise-gift features |
| Legacy | `/edd`, `/cartedd`, `/warehouse-edd`; `/edd-mapping/*` | An older engine; an adapter over the current engines | Still mounted and called by older paths |

The `/edd-mapping/*` endpoints calculate nothing themselves. They call the current engines and reshape the output into the legacy response format.

## 1.3 Latency: target vs. evidence

**Don't claim the brief's "sub-50 ms" target. The evidence doesn't support it.**

- No latency objective, timer or alert threshold exists anywhere in the code.
- The only "<50 ms" figure in the repository is a design-document target for location-to-cluster lookup. Nothing measures it.
- In one captured production cart request, the calling orchestrator measured the cart EDD call at **1,443 ms** end to end. That is a single sample, not a distribution.
- The orchestrator's per-call budget for this call has been observed at 1,500 ms and 3,000 ms. The backend handler's own HTTP timeout is 10 s.

The code's structure shows where the time goes (these are not measurements):

- **The geographic search is sequential.** Each level waits for the previous one, and each runs a cluster lookup, a warehouse lookup and an inventory read.
- **The configuration bundle is one parallel batch:** cutoffs, static buffers, capacity rows and SLA rows.
- **Some reads are never cached.** Each request reads rain status and tag buffers fresh. The cart engine also reads area lists for day-skip buffers fresh.
- **The current endpoints have no response cache.** Every call recomputes the answer from cached lookups.

## 1.4 Service boundaries

```
 Storefront backend (callers)
 ┌────────────────┬──────────────────┬────────────────────┬──────────────────────┐
 │ Cart           │ SKU-list EDD     │ Order-complete     │ Delivery-note        │
 │ orchestrator   │ helper           │ flow               │ webhook              │
 └───────┬────────┴────────┬─────────┴─────────┬──────────┴──────────┬───────────┘
         │ cart EDD        │ per-SKU EDD       │ cart EDD +          │ warehouse-pinned
         │                 │                   │ order-count flag    │ EDD
         ▼                 ▼                   ▼                     ▼
 ┌──────────────────────── PROMISE ENGINE (one Node.js service) ────────────────────────┐
 │  EDD API ──► cart engine / product engine ──► Redis cache ──► MySQL (primary + read)  │
 │                                                                                       │
 │  Control Tower admin API: clusters, polygons + H3 index, SLA matrix, cutoffs,         │
 │  static / capacity / tag buffers, day-skips, rain matrix and approval settings         │
 │                                                                                       │
 │  Inventory ingestion:  ERP webhook ──► Pub/Sub ──► subscriber ──► stock table          │
 │                        snapshot jobs ──► stock + item-master tables                    │
 │  Weather jobs:         poll ──► rain decision ──► approval ──► rain status             │
 └───────────▲────────────────────────────▲─────────────────────────────┬──────────────┘
             │ stock + item master         │ forecasts                   │ approvals, alerts
       ERP (Frappe)                   AccuWeather                    Telegram
```

| Party | Owns | Does not own |
|---|---|---|
| Promise Engine | Serviceability configuration, a read-optimised copy of stock and item master, EDD computation, capacity counters, rain status | Orders, the stock of record, customer UI |
| ERP (Frappe) | Stock per warehouse; item master (weight, type, bundle components) | Delivery promises |
| Storefront backend | Cart, product and order flows. It decides when to ask for a promise and when to count an order. | EDD rules |
| OMS | Not integrated. The engine makes no OMS calls; the backend calls the engine around order events. | — |
| Inventory service | There isn't a separate one. The engine keeps its own stock table, fed by ERP. | — |

Warehouses are identified by their Unicommerce names. During ingestion, a mapping table translates ERP warehouse names into those names. The current engines make no Unicommerce calls.

## 1.5 Cart request lifecycle

1. **Validate** the input and merge duplicate SKUs.
2. **Resolve the pincode** to a city and state. With no pincode record, the request is rejected.
3. **Search** lat/lng → pincode → city → state for warehouses that can serve the pending SKUs, and allocate quantities (Section 3).
4. **Mark out of stock** every SKU that was not fully allocated.
5. **Pack** the allocated units into weight-capped shipments per cluster–warehouse pair.
6. **Fetch configuration** for the warehouses in play (one parallel batch), then **merge rain buffers**.
7. **Compute each shipment's promise** through the pipeline (Section 4).
8. **Collapse to one promise per SKU.** When a SKU spans several shipments, the latest shipment's promise wins and the quantities are summed.
9. **Count the order**, but only when the order-count flag is set, and **attach rain information**.

## 1.6 Runtime and deployment

- **One Node.js / Express process** on Google App Engine Standard (F2 instance class). The deployment file sets no scaling parameters.
- **Same process:** the EDD API and the Control Tower admin API (mounted as a sub-application). It also runs the inventory Pub/Sub subscriber, which is started right after the HTTP server.
- **Cron endpoints:** the process exposes them, and a scheduler outside the application calls them. The engine contains no scheduler of its own.
- **Queue workers** have a separate entry point and do not run in the web process. The H3-indexing worker is a stub.
- **Data stores:** MySQL, with reads going to a separately configured read connection and writes to the primary. **Assumption:** the read host is a replica; the deployed configuration isn't in the repository. Redis handles caching and rate limiting.
- **No authentication on EDD endpoints.** An authentication module exists but is not wired in. The only gate is a database-configured rate limiter keyed by IP address (Section 6.4). CORS allows every origin.

### Not in this system
- A latency objective, a per-request timeout or a circuit breaker.
- A separate inventory service, an OMS integration, or caller authentication.

---

# 2. Geospatial & Serviceability Engine

## 2.1 Resolution pipeline: H3 cell membership

**The request path uses H3 hexagonal indexing only. It never runs a point-in-polygon test.**

**When a polygon is saved (offline):** the polygon is filled with H3 cells at **resolution 10**. The H3 library includes a cell when the cell's centre lies inside the polygon. Each (polygon, cell) pair is stored, and the cell id is indexed.

**At request time:**
1. Convert the lat/lng to its single resolution-10 cell.
2. Find the active polygons indexed to that exact cell.
3. Find the active clusters linked to those polygons.

There is no neighbouring-cell expansion and no exact geometry re-check. If polygons overlap, the lookup returns all their clusters in database order, with no tie-break.

| | H3 membership (EDD path) | Exact point-in-polygon (admin lookup only) |
|---|---|---|
| Cost per request | One indexed equality lookup | A geometry test; the models define no spatial index on polygon geometry |
| Boundary accuracy | Quantised to the resolution-10 cell; a point near an edge can fall on either side | Exact |
| Cost of editing a polygon | Re-fill the polygon's cells | None |
| Used by | Cart and product engines | The admin "polygons at this location" lookup |

The resolution is fixed at 10. The design documents describe resolutions tiered by SLA (7 to 10); that isn't implemented.

## 2.2 Serviceability hierarchy

The brief's chain has five levels. The code has four:

```
 Brief:  lat/lng (H3 cell) → darkstore polygon → pincode → city → state
 Code:   lat/lng ─(H3 cell → polygons)─► pincode ─► city ─► state ─► out of stock
```

```
 lat/lng sent? ──yes──► H3 cell → polygons → polygon clusters → warehouses ──┐
      │ no                                                                     │ SKUs still pending
      ▼                                                                        ▼
 pincode clusters → warehouses ──► city clusters → warehouses ──► state clusters → warehouses
                                                                               │ still pending
                                                                               ▼
                                                                         Out of Stock
```

- **Each level only handles what is still pending.** It runs only for SKUs not yet found. In the cart engine, it runs only for the quantity not yet allocated.
- **Coordinates are optional; the pincode is not.** The lat/lng level runs only when coordinates are sent.
- **City and state come from the pincode record**, not from the coordinates.
- **Cluster:** a cluster has one of four types: polygon, pincode, city or state. Clusters link to warehouses through the SLA matrix, which carries a priority, a weight slab, a delivery type and an SLA.
- **No separate darkstore-polygon level.** Every polygon is a cluster's geometry. "Darkstore" is a facility-type label, and warehouse selection never reads it.

## 2.3 Polygon rules

| Step | What the code does |
|---|---|
| Create | The admin API accepts a GeoJSON polygon. Bulk CSV and KML uploads are also supported. Bulk paths flatten multi-part shapes into one polygon: a union when the parts touch, otherwise the convex hull of all their points (which also covers the gaps between the parts). |
| Store | A MySQL geometry column, in WGS84. |
| Validate | The ring must be closed and the area non-zero. The overlap check compares bounding boxes only and does not block the save. There is no self-intersection check. Holes are accepted but ignored. |
| Map | Polygons and clusters are many-to-many. Nothing stops one polygon from belonging to two clusters. |
| Index | On create or update, the admin request itself deletes and regenerates the polygon's cells. If indexing fails, the error is logged and the polygon is still saved, but it won't match any lookup until it is re-indexed. Bulk uploads start indexing without waiting for it to finish. A full re-index endpoint refills every active polygon, one at a time. |
| Retire | Only polygons with active status are matched. |

"Dynamic" geofences, meaning boundaries that change on their own with load or weather, don't exist. Polygons change only through admin edits.

## 2.4 High-concurrency reads

- Geo lookups are read-only, use the read connection, and take no locks.
- Two cache layers cover the lat/lng level: the level's list of clusters, and the H3 resolution result. Both use the 5-minute default TTL and are keyed on the coordinates. The H3 key rounds to 8 decimal places, which is effectively exact, so shoppers at different points rarely share an entry.
- There is no in-memory spatial index. The cell-id column is indexed in the database.
- Re-indexing deletes a polygon's cells and then re-inserts them in batches, without a transaction. A lookup during a rebuild can miss that polygon, and falls through to the pincode level.

### Not in this system
- On the request path: exact point-in-polygon, neighbour-cell expansion, or H3 resolutions tiered by SLA.
- Any rule that polygons must not overlap, or that a polygon may belong to only one cluster.
- Geofences that change automatically.
- Queue-based indexing (the worker is a stub).

---

# 3. Inventory Allocation & Over-Promising Prevention

## 3.1 Inventory data model and freshness

- **Stock table:** one row per SKU, one column per warehouse. The column names are the Unicommerce warehouse names.
- **Item master:** weight (kg), type (simple or bundle), bundle components, tags and status.
- **Inner join.** The engine reads the item master joined to stock. A SKU with stock but no item-master row is invisible to the engine, so it comes back out of stock.

| Writer | What it writes |
|---|---|
| ERP webhook (realtime deltas) | Verified with a shared secret, queued on Pub/Sub, and applied one message at a time. Updates only the warehouses in the payload. Never touches the item master. |
| ERP snapshot jobs (paginated) | Every warehouse, including zero quantities, plus the item master. The raw payload is archived to cloud storage. |
| Bundle job | Bundle stock is the minimum, over the bundle's components, of ⌊component stock ÷ units per bundle⌋. It is written under the bundle's own SKU. |

- **No staleness check at request time.** The stock query result is cached per set of SKUs, for 5 minutes by default.
- **SKU normalisation before lookup:** promotional suffixes are stripped so that variants share the base SKU's stock. The suffixes are CMD, REW, 23NE, FG, BXGY, WBOGO, BBB25 and SALE, plus "GIFT" for one specific gift SKU.

## 3.2 Facility selection

- **Tiers are geographic levels**, nearest first, not facility types.
- **Visiting order within a level:** clusters in lookup order; within each cluster, warehouses by ascending priority. Only active warehouses are visited.
- **Facility type isn't used.** The types are "warehouse" and "darkstore", but selection never reads them. The current engines have no vendor or dropship tier.

| | Cart engine | Product engine |
|---|---|---|
| Rule | First-fit in visiting order. One SKU's quantity may split across warehouses and levels. | The first warehouse (level order, then priority) that holds the full quantity and has a matching weight slab |
| Splits a quantity | Yes | No |
| Ledger across clusters and levels | Yes | No |
| Weight used for the SLA slab | The whole shipment's weight | The SKU line's weight |

## 3.3 Cross-cluster allocation ledger (cart engine)

The same physical warehouse can appear under several clusters: a polygon cluster and a city cluster, for example, or two overlapping polygons. If each cluster were checked on its own, that warehouse's stock would be counted twice. The cart engine prevents this with a **ledger that lives for one request**, keyed by SKU and warehouse.

For SKU *s* with remaining need *R*, when it visits warehouse *w*:

- **On hand:** *S(w, s)*, from the stock table.
- **Already promised in this request:** *L(s, w)*, summed across every cluster and level visited so far.
- **Available:** *A = S(w, s) − L(s, w)*.
- **If A > 0:** take *x = min(A, R)*, then set *L(s, w) ← L(s, w) + x* and *R ← R − x*.
- **Carry forward:** any remaining *R* moves on to the next warehouse, and then to the next level.

**Invariant:** within one request, no warehouse is promised more units of a SKU than it holds, however many clusters it appears in.

```
 SKU X needs 8. Warehouse W holds 5 and belongs to both a polygon cluster and a city cluster.
   polygon level : W   A = 5 − 0 = 5 → take 5    L(X,W)  = 5    R = 3
   city level    : W   A = 5 − 5 = 0 → skip
                   W2  A = 4 − 0 = 4 → take 3    L(X,W2) = 3    R = 0  ✓
```

## 3.4 What prevents over-promising, and what does not

| Risk | Handled? | How |
|---|---|---|
| One warehouse's stock counted twice inside one cart | Yes | The ledger (cart engine only) |
| Two concurrent carts promised the same last unit | **No** | No reservation, hold, lock or decrement exists anywhere. The ledger lives for one request only. |
| Stock that has sold but not yet synced | **No** | Freshness depends on ERP pushes plus the 5-minute cache |
| A warehouse overloaded with orders | Partly | Capacity counters slow the promise down (Section 4.5). They count orders, not stock. |

## 3.5 Fulfilment integrity

**All-or-nothing out of stock.** After all four levels, if a SKU's allocated units fall short of the request, the **whole** SKU is marked out of stock. Its partial allocations are discarded, so no shipment carries part of it. The product engine never splits a SKU, so it gets the same result by construction.

**Shipment packing, by weight only:**
1. Group the allocated items by (cluster, warehouse).
2. Sort each group's items by unit weight, lightest first.
3. Expand the items into individual units and add them one at a time.
4. If the next unit would push the shipment past the warehouse's maximum shipment weight, close that shipment and open a new one.

This is sequential first-fit, not optimal bin-packing. A single unit heavier than the cap becomes its own over-cap shipment; it isn't rejected. Each warehouse's cap is stored in grams. When the value is zero or missing, the code falls back to 10 kg; the column's default is 1 kg. **There is no dimensional or volumetric rule.**

**Special items (gifts, samples, rewards).** SKUs ending in FG, SAM or REW, plus one named gift SKU, are placed **after** the main items. If a warehouse that already ships a main item has any positive stock of the gift, the gift joins that warehouse's shipment; the highest-priority such warehouse wins. Otherwise the gift keeps its own allocation.

**Warehouse-pinned mode (delivery note).** The ERP warehouse name is translated to the engine's name, and the search is restricted to that warehouse. **The stock check is bypassed:** the requested quantity is assumed to be available. This endpoint also counts every SKU as one unit.

**One promise per SKU.** When a SKU spans several shipments, its SKU-level promise is the **latest** of those shipments, with the quantities summed. The per-shipment list keeps each shipment's own promise.

### As built: caveats
- The ledger doesn't cover the gift step. A gift is only checked for positive stock at the chosen warehouse.
- Bundles are resolved offline by the bundle job. The request path checks no components.
- Webhook deltas never create item-master rows, so a new SKU stays invisible until a snapshot job runs.

### Not in this system
- Reservations or holds across requests.
- Dimensional packing.
- Vendor or dropship sourcing in the current engines. The same goes for dangerous-goods routing, which only the legacy engine has.

---

# 4. Multi-Tier Buffer & SLA Computation Pipeline

The pipeline runs **once per shipment** in the cart engine and once per SKU in the product engine. It starts from the current time in IST and turns it into a delivery timestamp.

## 4.0 Execution order

The brief lists eight stages. The code runs them in this order:

| # | Stage (brief §) | Rule as coded | Effect on the clock | Data freshness |
|---|---|---|---|---|
| 1 | Weight-slab match (4.1) | The first SLA row, by priority, whose slab contains the weight | None. Fixes the delivery type and the SLA. | Cached, up to 5 min |
| 2 | Cutoff (4.2) | Hyperlocal: now is outside the operating window. Other types: now is after the daily cutoff. | Moves the start day and sets an absolute time | Cached, up to 5 min |
| 3 | Static SCM buffers (4.3) | Every applicable row across three scopes, summed | Adds duration | Cached, up to 5 min |
| 3a | Rain buffer (4.4) | Joins stage 3 only if the warehouse has no SCM static row | Adds minutes | Read live |
| 4 | Capacity buffers (4.5) | Rows breached in the current window, summed | Adds duration | Cached, up to 5 min |
| 5 | Tag buffers (4.6) | Rows whose tag the SKU carries, summed; may be negative | Adds or removes duration | Read live |
| 6 | SLA addition (4.1) | Skipped when a hyperlocal cutoff fired | Adds the SLA duration | — |
| 7 | Pickup day-skip (4.7) | Walks a separate pickup clock past non-pickup days and dates | Adds days to the total | Cached, up to 5 min (area lists read live in the cart engine) |
| 8 | Apply buffers | The total of stages 3–5 and 7 | Adds duration; re-anchors the time if stage 7 moved the date | — |
| 9 | Delivery day-skip (4.7) | Walks the delivery clock past non-delivery days and dates | Adds days; re-anchors the time | Cached, up to 5 min (area lists read live in the cart engine) |
| 10 | Normalise (4.8) | 22:00 default; 23:30 or later moves to 13:00 next day | Sets the time of day | — |

```
 now (IST)
   │ 1   slab match ──────────► delivery type + SLA
   │ 2   cutoff ──────────────► start = a later day, at the reset time (absolute)
   │ 3–5 sum buffers ─────────► static (or rain) + capacity + tag
   │ 6   + SLA ───────────────► skipped when a hyperlocal cutoff fired
   │ 7   pickup-day walk ─────► on a separate pickup clock
   │ 8   + buffers ───────────► re-anchor the time if the pickup walk moved the date
   │ 9   delivery-day walk ───► re-anchor the time if the walk moved the date
   │ 10  normalise ───────────► 22:00 default; 23:30 or later → 13:00 next day
   ▼
 promise: timestamp · day count · delivery type · copy · breakdown
```

## 4.1 Base courier SLA matrix

The matrix maps (destination cluster, source warehouse, weight slab) to a delivery type, an SLA value and unit, and a priority.

- **Slabs:** a minimum and maximum weight in kg. The minimum must be below the maximum, and each (cluster, warehouse, min, max) combination is unique.
- **Matching:** rows are taken in priority order. The first slab that contains the weight wins, and both ends of the range count as inside.
- **Weight:** the whole shipment's weight in the cart engine; the SKU line's weight in the product engine.
- **Delivery types (10):** hyperlocal, hyperlocal B, SDD A/B/C, NDD A/B/C, Standard A/B. Only the two hyperlocal types get special treatment in code; the letter suffixes are configuration labels.
- **SLA units:** minutes, hours or days.
- **No matching slab:** the shipment is left out of the response. It isn't reported as out of stock.

## 4.2 Cutoff engine

Each warehouse and delivery type can have: an operating window (hyperlocal types) or a daily cutoff time (all other types), a number of days to add, and a reset time.

| | Hyperlocal, hyperlocal B | All other types |
|---|---|---|
| Fires when | Now is before the window opens or after it closes | Now is after the daily cutoff time |
| On firing | Start = today + days-to-add, at the reset time. If the window hasn't opened yet, one day fewer (minimum 0). | The same shift and reset |
| SLA | Not added: the reset time is the delivery slot | Added on top of the shifted start |

- **Absolute, not added.** The reset time is set as a clock time rather than added as a duration. That removes any carry arithmetic across midnight.
- **Early vs. late hyperlocal orders.** An order placed before the window opens lands on the same day's slot. One placed after it closes lands on the next day's.
- **Pickup clock.** The cutoff's days and reset time also seed the pickup clock (4.7).

## 4.3 Static SCM buffers

| Attribute | Options |
|---|---|
| Scope | A cluster + warehouse pair; a warehouse; a cluster |
| Nature | Time addition; or day skip (4.7) |
| Active window | A start and an end date-time |
| Weight range | Optional. For time additions, only enforced on the cluster + warehouse scope. |
| Area | All areas; or specific polygons, pincodes, cities or states |
| Unit | Minutes, hours or days |

- **Summed, no precedence.** Every applicable time-addition row is added up, across all three scopes. No scope overrides another.
- **Only warehouse scope moves the pickup clock (4.7).** Warehouse-scoped rows push it as well as the delivery time. Cluster and cluster + warehouse rows push only the delivery time.

## 4.4 Dynamic environmental (rain) buffers

**How rain status is produced (background jobs):**

```
 poll job: minute-level precipitation per warehouse ───────────┐
 hourly job: next-hour intensity forecast per warehouse ───────┤
                                                               ▼
 decision   raining now          → look up the rain matrix (intensity × spell length); never lower it while raining
            dry, rain due soon   → switch on early from the forecast
            stopped, in cooldown → hold the current minutes
            cooldown over        → switch off
                                                               ▼
 approval   Telegram message per city, with an approve link
            no answer in 10 min      → auto-approve (default)
            outside 06:00–23:00      → auto-approve at once, with a notice (default)
                                                               ▼
 rain status per warehouse: active? · minutes
```

- **Intensity.** For the response shape the code prefers, the poll yields only raining or not. Intensity comes from the previous hour's stored forecast; if there isn't one, it defaults to "heavy".
- **Scope.** Only warehouses with an active rain-matrix row and a weather location key are polled. Location keys are synced for warehouses that serve the hyperlocal delivery types.
- **Weather API failure.** The status is left as it was (so it goes stale). A Telegram alert fires once 15 minutes have passed since the last success.

**Precedence at request time:**
- The engine reads each warehouse's rain status live, uncached.
- If the warehouse–cluster entry already holds **any** SCM static buffer row (of either nature, before any weight or area filtering), rain is **not** added. Otherwise, an active rain status adds its minutes as a warehouse-scoped time addition.
- **SCM buffers win by presence, and the two never stack.** Even a small SCM buffer suppresses a large rain buffer.
- **Rain applies to every delivery type** from that warehouse. For non-hyperlocal types, its minutes only matter if they push delivery past midnight (4.8).
- **Response fields.** Every SKU line and shipment carries rain information: whether it's raining, the intensity label, whether the buffer is active, its minutes, and the expected start and end. The shipment output also has a "rain buffer included" flag, but the current engines never set it to true.

## 4.5 Real-time capacity buffers

Each row covers one warehouse, one delivery type and one time window (an absolute start and end date-time). It holds a capacity, a delay (value and unit), and live counters: order count, spill and breach time.

**Read side:**
- Only rows whose current window is breached are fetched: **order count + spill ≥ capacity**.
- **Which rows apply:** a row applies when it has the same delivery type as the shipment, or no type at all, or when both types are non-hyperlocal. A hyperlocal row applies only to the identical hyperlocal type.
- **Summed.** All applicable delays are added up. They also push the pickup clock.
- **Not instant.** The rows sit inside the cached configuration bundle, so a new breach reaches a given set of warehouses within the cache TTL (5 minutes by default).

**Write side (counting orders):**

```
 order completes → the backend re-calls cart EDD with the order-count flag
   for each distinct (warehouse, delivery type) in the order's shipments:
     current window:  order count + 1                         (one atomic SQL update)
                      breach time stamped once, when the increment crosses capacity
     overflow = order count + spill − capacity                (current window)
     if overflow > 0:  next window's spill = overflow          (a separate read, then a write)
```

- **One increment per order.** The counter goes up once per warehouse and delivery type in the order, not once per unit.
- **Windows are rows.** A new window starts at zero. No job resets the counters, so future windows must be created in advance.
- **Surges slow the promise, nothing more.** Orders aren't blocked, and they aren't rerouted to another warehouse.

## 4.6 SKU tag buffers

- **Definition:** a tag, a delay in minutes, hours or days, and an optional active window. The delay may be negative, to shorten a promise; zero is rejected.
- **SKU tags** come from the item master.
- **Summed.** Every active row whose tag appears in the SKU's tags is added up. Matching is case-sensitive, and stored tag-buffer tags are upper-cased.
- **Cart engine:** only the tags of the first item in each shipment are checked.
- **No category model.** "Fragile" or "heavy" would each just be a tag.

## 4.7 Calendar day-skips

A day-skip is a static buffer whose nature is "day skip". It carries a list of entries: pickup weekdays, delivery weekdays, pickup dates and delivery dates, one value per entry. It applies only when three filters pass: the cluster matches (for cluster-scoped rows), the weight range matches (when one is set, for any scope), and the area list matches (when one is set).

| | Pickup skip (non-pickup days) | Delivery skip (non-delivery days) |
|---|---|---|
| Clock walked | A separate pickup clock: now + cutoff days + warehouse-scoped static buffers + capacity buffers. If a cutoff fired, it is set to the cutoff's reset time. | The delivery clock, after all buffers are applied |
| Weekday walk | While the clock's weekday is a skip day, advance by the buffer's value and unit | Same |
| Date walk | While the clock's date is a skip date, advance one day | Same |
| Result | The days walked are added to the delivery buffer | The days walked move the delivery directly |
| Afterwards | If any days were added, the delivery time of day resets to the cutoff's reset time (when one is configured) | Same |

## 4.8 Time-of-day normalisation and timezone

**Timezone:**
- **Fixed offset, no library.** The engine gets IST by adding 5 h 30 m to the current instant and reading the clock fields of the shifted value. There is no timezone library.
- **Assumption:** this only works if the host clock runs in UTC, which is the App Engine default. Nothing in the code or deployment config sets the timezone. Checking the runtime's timezone setting would confirm it.
- **Output format.** Timestamps are IST wall-clock values written in ISO format with a UTC ("Z") suffix. Consumers have to read them as IST.

**Normalisation, in this order:**
1. **Clock never moved** (delivery equals now): 22:00 today if it's before 22:00, otherwise 22:00 tomorrow.
2. **Non-hyperlocal types:** the time is set to 22:00, unless a day-skip already re-anchored it. Non-hyperlocal promises are therefore end-of-day ("by 10 PM").
3. **Late-night roll-over:** if the time is 23:30 or later, it moves to 13:00 the next day. This applies to every type.

**Consequence:** for non-hyperlocal types, a buffer shorter than a day only changes the promise if it pushes delivery past midnight.

## 4.9 Output

| Field | Meaning |
|---|---|
| Delivery timestamp | IST wall clock (see 4.8) |
| Minutes to delivery | Rounded up |
| Day count | Calendar-day difference from today; handles a single month boundary |
| Message tier | "now" up to 30 min; "fast" up to 60 min, later today, or tomorrow; "standard" beyond tomorrow |
| Copy | Web checkout: "Arriving in 25 mins", "Arriving by Tomorrow 10PM". Display: a prefix ("Delivery in" / "Delivery by"; the product engine uses "Get it in" / "Get it by") plus a time ("25 mins", "Today 8PM", "Tomorrow 10PM", "3rd Oct, 10PM"). The hour rounds up when the minutes exceed 10. |
| Quick-delivery flag | Minutes to delivery ≤ the pincode's required SLA minutes |
| Breakdown | SLA and slab; each static, capacity and tag buffer; cutoffs, applied or not; totals by unit; pickup time; skipped days and dates |

## 4.10 Why the order matters (as coded)

1. **Slab match first.** The delivery type it produces decides which cutoff and capacity rows apply.
2. **Cutoff before any addition.** It sets an absolute time, which would erase anything added earlier.
3. **A hyperlocal cutoff replaces the SLA.** The reset time already is the slot, so adding the SLA as well would double-count.
4. **Rain before the static loop.** Rain is then handled exactly like a warehouse-scoped time addition, including its effect on the pickup clock.
5. **Pickup walk on its own clock.** Only cutoff days, warehouse-scoped static buffers and capacity buffers go on that clock. Cluster-scoped buffers, tag buffers and the SLA do not.
6. **Delivery walk after all additions.** It has to test the final date.
7. **Normalisation last.** It overwrites the time of day.

## 4.11 Illustrative trace (hypothetical values, not production configuration)

**Setup:** Friday 21:10 IST, one 4.2 kg shipment from warehouse W to cluster C.
- SLA row for 3–10 kg: NDD A, 1 day.
- NDD A cutoff: 20:00, 1 day to add, reset time 09:00.
- A warehouse-scoped static buffer of 2 hours.
- A pickup skip on Sundays (a day-skip buffer of 1 day).
- No rain, no capacity breach, no tags.

| Step | Clock |
|---|---|
| 1 Slab | NDD A, SLA 1 day |
| 2 Cutoff | 21:10 is after 20:00, so start = Sat 09:00 |
| 3 Static | +2 h pending |
| 6 SLA | Sat 09:00 + 1 day = Sun 09:00 |
| 7 Pickup | Pickup clock = Fri 21:10 + 1 day 2 h = Sat 23:10, reset to 09:00 → Sat 09:00. Saturday isn't a skip day, so nothing is added. |
| 8 Apply | Sun 09:00 + 2 h = Sun 11:00 |
| 9 Delivery skip | None |
| 10 Normalise | Non-hyperlocal → Sun 22:00 |
| **Result** | Day count 2 → "standard": "Delivery by (Sunday's date), 10PM" |

The 2-hour buffer didn't change the promise, because normalisation reset the time to 22:00 on the same day.

Place the same order on Saturday instead, and the pickup clock lands on Sunday, a skip day. It walks forward to Monday, which adds a day. Delivery becomes Tuesday. Because a day-skip moved the date, the time re-anchors to the 09:00 reset time and the 22:00 default is skipped. The promise is "by Tuesday 9AM".

### As built: caveats
- **Rain is suppressed by presence.** Any active SCM static row suppresses rain, even one that doesn't apply to this shipment's weight or area.
- **Weight-gated buffers break in the product engine.** Its weight gates for buffers divide a weight that is already in kg by 1,000. The cart engine converts correctly.
- **Capacity delivery-type rule.** A non-hyperlocal capacity row applies to every non-hyperlocal delivery type from that warehouse.
- **Spill can lose updates.** The spill write reads, then writes, with no transaction, so concurrent breaches can overwrite each other.
- **Rain active-hours vs. timezone.** The rain approval flow checks active hours against the host's local clock, and its own comment expects that clock to be IST. The EDD engines assume the host runs UTC. At most one of these assumptions holds on a given host.

---

# 5. Comparative Architecture: E-Commerce (this engine) vs. Quick-Commerce

The left column is implemented behaviour. The right column states what the brief's model (10–15 minutes, one darkstore) would require. It is design reasoning, not a description of any specific company's system, and none of it is implemented here.

## 5.1 Comparison matrix

| Dimension | This engine (implemented) | 10–15-minute single-darkstore model (requirement) |
|---|---|---|
| Unit of promise | Per shipment. One cart can split across warehouses and weight-capped parcels. | One order, one darkstore, one trip |
| Serviceability | Four-level fallback. A shopper outside every polygon can still be served through pincode, city or state clusters. | The polygon is the service area; outside it, the order can't be served |
| Sourcing | Several warehouses; quantities split across levels; all-or-nothing per SKU | One darkstore; it can fill the order or it can't |
| Speed tiers | 10 configured delivery types. SLAs in minutes, hours or days. Hyperlocal types get operating windows. | One minute-level promise |
| Time model | Cutoffs, day-skips, a 22:00 end-of-day default, and a 23:30 roll-over | A minute-level ETA; windows only for store hours |
| Stock freshness | ERP deltas plus snapshots, read through a 5-minute cache; no reservation | Near-real-time darkstore stock, with a hold at checkout |
| Capacity | Order counts per warehouse, delivery type and window. A breach adds delay. Read through the cache. | Live picker and rider capacity that gates the promise itself |
| Last mile | No rider, slot or route data anywhere in the engine | ETA coupled to rider availability and distance |
| Weather | Rain status per warehouse, with human approval, applied as a minute buffer | The same need, with a tighter tolerance |
| Failure posture | Mixed. Some failures degrade into optimistic promises (Section 6.3). | A wrong 10-minute promise is exposed within minutes |

**Where this engine already leans toward quick commerce, in code:**
- Hyperlocal delivery types with operating windows, and SLAs in minutes.
- "now" (up to 30 min) and "fast" (up to 60 min) message tiers.
- A quick-delivery flag, set against the pincode's required SLA minutes.
- Rain buffers, set up for warehouses that serve hyperlocal.

## 5.2 Architectural trade-offs

| Trade-off | This engine (code) | What the 10–15-minute model would change (reasoning) |
|---|---|---|
| Polygon radius | Polygons are free-form shapes, not radii. H3 resolution 10 quantises the edge, overlaps are allowed, and a miss falls back to a coarser level. Serviceability is generous, but a polygon miss quietly becomes a slower tier. | A miss means "can't serve". Edges would need to be exact, overlaps disallowed, and the polygon tied to one darkstore. |
| Inventory freshness | Freshness = the ERP push delay + up to 5 minutes of cache. No reservation. | A 5-minute-old count is a large share of a 10-minute promise. It would need live stock and a hold at checkout. |
| Rider coupling | None. The only throughput control is order counting per window: a breach adds delay, read through the cache. | Picker and rider state would have to be an input to the promise, not a delay added after a breach. |
| SLA tolerance | Non-hyperlocal promises snap to 22:00, which absorbs most buffers shorter than a day. The error margin is about a day. Hyperlocal keeps precise times. | Minute-level tolerance: every buffer lands directly in the promise. |

---

# 6. Latency, Caching & Resilience Architecture

## 6.1 What one cart request does

| Step | Reads | Cached? |
|---|---|---|
| Pincode | 1 | Yes |
| Each level, run in sequence, up to 4 | Cluster lookup (the H3 lookup at the lat/lng level), warehouse lookup, stock read | Yes, each one |
| SLA rows | 1 per shipment | Yes |
| Configuration bundle | Cutoffs, static buffers (2 queries), capacity rows and SLA rows, in parallel | Yes, as one bundle |
| Rain status | 1 | No |
| Tag buffers | 1 | No |
| Each applicable buffer | Area list, day-skip entries | Day-skip entries: yes. Area lists: yes for time additions, **no** for day-skips in the cart engine. |
| Order counting (flag set only) | Per (warehouse, delivery type): 1 update, 2 reads, 1 update | Write |

## 6.2 Caching taxonomy

| Cache | Holds | Key | TTL |
|---|---|---|---|
| Spatial: H3 result | Polygons and clusters for a lat/lng | Coordinates, 8 decimal places | 5 min |
| Spatial: clusters per level | Clusters for a pincode, city, state or lat/lng | Level + value | 5 min |
| Warehouses for clusters | Warehouses in priority order | Cluster set (+ the pinned warehouse) | 5 min |
| Inventory | Item-master and stock rows | Set of SKUs | 5 min |
| SLA and configuration bundle | Cutoffs, static buffers, breached capacity rows, SLA rows | Warehouse set + cluster set | 5 min |
| SLA rows per shipment | SLA rows | Cluster + warehouse | 5 min |
| Buffer details | Areas and day-skip entries per buffer | Buffer id | 5 min |
| Warehouse record (pinned mode) | The warehouse entity | Name | 60 min |
| Response cache (in-process) | Whole responses, **legacy endpoints only**. The current endpoints are mounted ahead of it. | URL | 10 min |
| Not cached | Rain status, tag buffers, day-skip area lists (cart engine), capacity writes | — | — |

- **One TTL setting.** Every Redis TTL comes from a single setting (default 300 s), except the warehouse record (3,600 s).
- **Hashed keys.** Keys are a hash of the sorted parameters, so any change in the SKU or warehouse set produces a new key.
- **No invalidation on writes.** No configuration write clears a cache entry; changes appear as entries expire, within 5 minutes. The helpers for targeted invalidation are never called. The admin "clear" endpoint wipes the whole Redis database.
- **The admin app caches separately.** The Control Tower admin app has its own Redis cache for its own reads, off the EDD path.

## 6.3 Failure behaviour by dependency

| Dependency | Failure | Behaviour as coded | Posture |
|---|---|---|---|
| Redis | Down at startup | The server starts anyway | Open |
| Redis | Down while running | Reads miss and go to MySQL; writes are dropped. The client reconnects with a backoff of 100 ms × attempt number (capped at 3 s) and gives up after 10 attempts; the next cache call re-initialises it. No command timeout is set. | Open, slower |
| Rate limiter's Redis or DB | Error | The request is allowed | Open |
| MySQL | Down at startup | The process exits | Closed |
| Stock read | Query error | The cache wrapper retries it once. **Cart engine:** if the retry fails, the level counts as having no stock and the search moves on, so the SKUs end up "Out of Stock". **Product engine:** HTTP 500. | Cart: open, with a wrong answer. Product: closed. |
| Pincode read | Error | Treated as a missing pincode; the request is rejected (HTTP 500) | Closed |
| Cluster lookup | Error | **Lat/lng level (both engines), and every level in the cart engine:** the level is skipped and the search moves to the next one. **Pincode, city or state level in the product engine:** HTTP 500. | Mostly open (coarser); product: closed |
| Configuration bundle | Query error | **Cart engine:** falls back to empty configuration, giving an SLA-only promise with no cutoffs, SCM or capacity buffers, or day-skips. That empty bundle is then cached for the TTL. **Product engine:** HTTP 500. | Cart: open, optimistic. Product: closed. |
| Rain status read | Error | Not caught; HTTP 500 | Closed |
| Weather API | Error or timeout | The poll leaves the status unchanged (stale). A Telegram alert fires after 15 minutes without a success. | Stale |
| Tag buffer read | Error | Not caught; HTTP 500 | Closed |
| Capacity counter write | Error | Logged; the response is still returned | Open |
| Inventory write (ingestion) | DB error | Logged per warehouse, and the message is still acknowledged, so the write isn't retried. An unexpected error before the write triggers redelivery. | Lossy |

**Summary.**
- **Fail open:** Redis, rate limiting and order counting.
- **Fail closed:** rain status, tag buffers and pincode data in both engines. The product engine also fails closed on stock, lookup and configuration errors.
- **Degrade into a wrong-looking-right answer:** the cart engine. Configuration failures give an early promise and stock errors show as out of stock, and both look normal to the shopper. That makes the cart engine's configuration failure the riskiest mode.

## 6.4 Protection

- **Rate limiter:** global middleware, applied only to endpoints enrolled in a database table (that list is cached for 30 days). It is a token bucket per IP address, endpoint and method, defaulting to 100 per minute. It uses an atomic Redis script, with a non-atomic fallback. When the bucket is empty it returns HTTP 429. On any internal error it lets the request through.
- **Unused limiters:** the Control Tower's own express-style rate limiters are defined, but not wired in.
- **Timeouts:** there's no request timeout and no Redis or MySQL query timeout. The ORM connection pools' acquire timeout is 30 s.
- **Isolation:** no circuit breakers or bulkheads.

## 6.5 Observability

- **Tooling:** an APM agent loaded at startup, structured logs to Loggly, console logs, and cache hit/miss logs with elapsed milliseconds.
- **No latency metrics.** The code defines no latency metric, percentile or SLO.
- **Request logs:** only the cart endpoint writes them. The other current EDD endpoints write none.

### Not in this system
- Latency SLOs, timeouts, circuit breakers or bulkheads.
- Cache invalidation driven by configuration writes.
- Caller authentication.
