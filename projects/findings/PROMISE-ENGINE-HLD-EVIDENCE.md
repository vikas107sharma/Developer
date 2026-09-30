# Promise Engine HLD: evidence and interview guardrails

Companion to `PROMISE-ENGINE-HLD.md`. The HLD has no file paths by design. This file maps its claims to the code, so you can check any of them before the interview.

- Paths are relative to `~/Developer/promise-engine`, unless marked **backend** (`~/Developer/supertails-backend`).
- Line numbers are for commit `4f07b42` (production, 28 Sep 2026). They will drift.

---

## A. What not to say (claims from the brief)

| Don't say | Say instead | Evidence |
|---|---|---|
| "EDD in under 50 ms" | "There's no latency target in code. One captured cart call took 1,443 ms." | "<50ms" appears only in `control-tower/README.md:11,141` and `control-tower/docs/hld_serviceability_clusters.md:30`, as a location-resolution target; nothing measures it. The captured call is in the cart-revmp skill, `references/sample-response.jsonc` (cart-edd elapsedMs 1443). |
| "Point-in-polygon, with H3 as an optimisation" | "H3 cell membership only, at resolution 10. Exact point-in-polygon exists only in an admin lookup." | `control-tower/src/services/H3IndexingService.js:161-262`; the admin `ST_Contains` is in `control-tower/src/models/GeoPolygon.js:109-115` |
| "A five-level hierarchy with a darkstore-polygon level" | "Four levels: lat/lng (via polygons) → pincode → city → state." | `controllers/functions/ControlTower/cartEddV2ControlTower.js:268-411` |
| "Dynamic geofences" | "Admin-edited polygons. Nothing changes them automatically." | `control-tower/src/services/PolygonService.js` (create and update only) |
| "Darkstore → RFC → vendor sourcing tiers" | "Geographic levels plus a per-cluster priority. Facility type isn't used, and there's no vendor tier." | `control-tower/src/models/ServingEntity.js:20-21` (the warehouse/darkstore enum); neither engine reads it |
| "Reservation that stops two users buying the same unit" | "A ledger scoped to one request. No hold, lock or decrement." | Ledger at `cartEddV2ControlTower.js:265,607-626`; there is no reservation code anywhere in the repo |
| "Packs by weight and dimensions" | "Weight only." | `cartEddV2ControlTower.js:958-1012` |
| "Static buffers follow scope precedence" | "All applicable scopes are summed." | `cartEddV2ControlTower.js:1831-1917` |
| "Capacity reacts in real time" | "The breach state is read through a 5-minute cache." | Capacity rows sit inside the cached bundle, `cartEddV2ControlTower.js:1421-1606` (query at :1505-1516); TTL at `utils/eddCache.js:12` |
| "Category buffers for fragile or heavy items" | "Generic tags, summed; they can be negative." | `control-tower/src/services/TagBufferService.js:228-250`; `control-tower/src/models/TagBuffer.js` |
| "It fails open everywhere" | "It's mixed. Rain-status and tag reads fail the request; a cart config failure yields a cached, optimistic promise." | §D.5 |
| "The service runs in UTC" (as a fact) | "It relies on a UTC host; nothing in code sets the timezone." | The only timezone reference is a comment expecting IST, at `control-tower/src/services/RainBufferApprovalSettingsService.js:80` |

---

## B. Corrections to your existing prep material

These are checked against `../phase2/promise_engine.md` (your interview card) and `code-analysis/promise-engine-edd.md` (the 22 Sep analysis).

1. **Static-buffer precedence** ("cluster_warehouse > warehouse > cluster"). That phrase is only a code comment; it isn't implemented. Every applicable row is summed. *Appears in: card Step 5; analysis §4.6 and §6.*
2. **"Capacity buffering is correct as soon as the next request comes in a few seconds later."** Not true. The capacity rows are inside the cached configuration bundle (TTL 300 s by default). *Appears in: card Step 7.*
3. **"Capacity and tag buffers are not cached."** Tag buffers aren't cached, but capacity rows are, for the reason above. *Appears in: analysis §8 and bullet 11.*
4. **"Dedup keeps the best (lowest) time per SKU."** The code keeps the **latest** time. Its own comment says the opposite of what it does (`cartEddV2ControlTower.js:111-128`). *Appears in: analysis §4.1 step 7, and the cart-revmp skill's reference 03.*
5. **"A request that has to return in milliseconds."** The only measurement on record is 1,443 ms. *Appears in: card Step 4.*
6. **The stage list starts with cutoffs.** The weight-slab match runs first, because it produces the delivery type that the cutoff and capacity rules need. The rest of the card's sequence matches the code. *Appears in: card Step 5; analysis §4.6.*
7. **"Delivery at 23:00–23:59 rolls to 13:00."** Since commit `14f0be3` (5 Sep), only 23:30 or later rolls. *Appears in: analysis §4.5; the card already says 23:30.*
8. **"The whole service runs in UTC."** Nothing in code sets this; it's an assumption. *Appears in: card Step 6.*
9. **Rain applies "only if no static buffer already exists."** Correct, but the check is on presence alone. Any active SCM row suppresses rain, even one that doesn't apply to the shipment's weight or area. *Appears in: card Step 5.*
10. **Authorship.** The card suggests claiming "the geographic search, allocation tracker, weight packer, and the buffer/day-skip pipeline ordering". Git attributes those to other engineers; see §C. *Appears in: card Step 1 and the "Cut these" list.*

---

## C. Git authorship (what the repository records)

**Non-merge commits, whole repo:** Sachin 129; Ankit Singh 94, plus 18 more under the "Ubuntu" identity (same email); Ajay N 54; alimisettyrakesh23 38; **vikas7312sharma 26**; Sachin Singh 25; a few others.

**git blame on the cart engine:**

| Part | Attributed to |
|---|---|
| Ledger and per-level allocation | Sachin |
| Shipment grouping and the gift phase | Ankit Singh, Sachin |
| Weight packer | Sachin |
| Cluster lookup | Sachin |
| Slab match and cutoff; static, capacity and tag buffers | Sachin, Ankit Singh |
| Day-skips | Ankit Singh, Sachin |
| Normalisation | Ankit Singh, Sachin; vikas7312sharma (the 23:30 change) |
| Order counting | Ankit Singh |

**Your 26 commits** cover:
- The ERP realtime inventory webhook → Pub/Sub pipeline, and its delta and clobber fixes (May–Jun 2026).
- The paginated ERP inventory endpoint.
- EDD message formatting and day-count fixes.
- Special-item EDD in the older engine (Jan 2025).
- The shipment-info fields (Apr 2026).
- The 23:30 late-night threshold (Sep 2026).

Git records who committed code. It doesn't record design input, reviews or pairing, so if you shaped parts of the engine in ways the log doesn't show, you know that better than git does.

---

## D. Evidence map, by HLD section

### D.1 Architecture (HLD §1)

| Claim | Evidence |
|---|---|
| Mount order; the response cache is mounted after `/v2` | `server.js:57-82` (`/v2` at :61, cache at :77) |
| Startup; subscriber started after listen; exit on DB failure | `server.js:87-106` |
| Current endpoints | `controllers/EddV2.controller.js:13-86`, `88-151`, `154-189`, `191-219` (qty forced to 1 at :207), `221-231` |
| Order-count flag parsing | `controllers/EddV2.controller.js:134` |
| The adapter calls the current engines | `controllers/EddMapping.controller.js:21,54` |
| No caller authentication | `middleware/security/index.js` wires only helmet and nocache; `middleware/security/authentication.js` is never required |
| CORS allows every origin | `server.js:37-42` |
| No scheduler inside the app | No `node-cron` or `setInterval` anywhere in the repo |
| Deployment | `app.yaml` (2 lines) |
| Cart caller | **backend** `app/Functions/CartOptimization/handlers/cartEddHandlerV2.js:209-225` (10 s timeout at :225) |
| SKU-list caller | **backend** `getEdd.js:462-468` |
| Order-complete caller | **backend** `webhook/postOrder/completeOrder/shopify.js:136-141` (flag = order id unless the email is internal) → `completeOrder/helper.js:238` → `getEdd.js:116,150` |
| Delivery-note caller | **backend** `webhook/deliveryNote/deliveryNoteWebhook.js:153` |
| Allocation caller | **backend** `getEdd.js:353-368`, used by `app/Functions/CartSupriseGift/*` |

### D.2 Geospatial (HLD §2)

| Claim | Evidence |
|---|---|
| Resolution fixed at 10; polyfill; cells deleted then re-inserted | `H3IndexingService.js:8-130` (:10, :23, :34-37, :40-91) |
| One cell, exact match, active polygons only | `H3IndexingService.js:161-194` |
| The SLA matrix is computed, then thrown away | `H3IndexingService.js:249-257`; callers read only `.clusters` (`cartEddV2ControlTower.js:1224-1225`) |
| A lookup error falls through to the next level | `cartEddV2ControlTower.js:1226-1229` |
| Level order | `cartEddV2ControlTower.js:268-411`; `eddMainV2ControlTower.js:134-179` |
| Cluster types | `control-tower/src/models/Cluster.js:21-22` |
| The overlap check is advisory | `PolygonService.js:282-289` (the throw is commented out) |
| Geometry validation blocks the save | `PolygonService.js:270-281` |
| Indexing runs inside the create request; a failure is logged and the polygon is still saved | `PolygonService.js:318-328` |
| Bulk multi-part flattening (union, else convex hull) | `BulkUploadService.js:3247-3305`, `3578-3633`, `4026-4052` |
| H3 cache key rounds to 8 decimal places | `utils/eddCache.js:154-159` |
| Spatial index on warehouse location disabled | `ServingEntity.js:107-111` |

### D.3 Allocation (HLD §3)

| Claim | Evidence |
|---|---|
| Ledger | `cartEddV2ControlTower.js:265`, `607-626` |
| Per-level allocation loop | `cartEddV2ControlTower.js:578-680` |
| All-or-nothing out of stock | `cartEddV2ControlTower.js:413-518` |
| Special SKUs | `cartEddV2ControlTower.js:699-704`, `835-923` |
| Packing and the cap fallback | `cartEddV2ControlTower.js:928-952`, `958-1012` (fallback at :936, :1301); column default 1000 g at `ServingEntity.js:64-71` |
| Warehouse visiting order | `cartEddV2ControlTower.js:1261-1314`; `eddMainV2ControlTower.js:341-392` |
| Suffix normalisation | `cartEddV2ControlTower.js:1330-1345`; `eddMainV2ControlTower.js:524-536` |
| Inventory inner join | `cartEddV2ControlTower.js:1352-1374` |
| Pinned mode: name mapping, stock check bypassed | `cartEddV2ControlTower.js:37-63`, `1389-1391` |
| Latest shipment wins per SKU | `cartEddV2ControlTower.js:111-128` |
| Product-engine rule | `eddMainV2ControlTower.js:249-261`, `893-965` |
| Inventory writers | `cronjob/cronjobERPInv.js:117-290` (delta rule :128-134 and :192-204; item master written only by snapshots, :233-256); webhook at :323-408; `GCP/inventorySubscriber.js:11-14`, `48-63`; bundle stock at `cronjob/cronjobBundle.js:90-120` |

### D.4 Pipeline (HLD §4; cart engine's per-shipment calculation, `cartEddV2ControlTower.js:1659-2430`)

| Claim | Evidence |
|---|---|
| Slab match | `:1669-1695`; enum at `ClusterWarehouseMatrix.js:53-67`; unique key at :97-101 |
| The allocation endpoint stops here | `:1714-1716` |
| Cutoff | `:1736-1828` |
| Static time additions | `:1830-1919` |
| Rain merge and precedence | `control-tower/src/utils/rainBufferEdd.js:54-100`, `106-131`; called at `:1608-1611` |
| The rain flag is never true | The constituent entry built at `:1903-1913` drops `source`, which `rainBufferEdd.js:136-142` looks for |
| Capacity read | `:1505-1516` (inside the bundle cached at :1421 / :1606); applied at `:1923-1989` (delivery-type rule :1935-1947) |
| Capacity write | Trigger at `:131-145`; update at `:2547-2643` |
| Tag buffers | `:1991-2037`; `TagBufferService.js:228-250`; `TagBuffer.js` (negative allowed, zero rejected, upper-cased) |
| SLA addition | `:2039-2062` |
| Pickup clock and walk | `:2064-2206` |
| Apply buffers, re-anchor the time | `:2208-2221`; `utils/eddDaySkip.js:1-19` |
| Delivery walk | `:2223-2359` |
| Normalisation | `:2361-2382` (23:30 since `14f0be3`) |
| Output and copy | `:2384-2429`, `:2437-2501` |
| IST offset | `:1663-1664` |
| Product-engine unit mismatch | `eddMainV2ControlTower.js:982` (kg) vs `:1146`, `:1396`, `:1550` (÷ 1000) |
| Rain decision cases | `control-tower/src/services/RainBufferDecisionService.js` (header) |
| Approval defaults | `RainBufferApprovalSettingsService.js:3-13`; outside hours at `RainBufferApprovalService.js:283-299`; active-hours check on the host clock at `RainBufferApprovalSettingsService.js:78-94` |
| Intensity defaults to "heavy" | `cronjob/cronjobWeatherPoll.js:324` |
| Weather failure: stale status plus alert | `cronjob/cronjobWeatherPoll.js:505-529` |

### D.5 Caching and resilience (HLD §6)

| Claim | Evidence |
|---|---|
| Cache wrapper fails open, and re-runs the query on any error | `utils/eddCache.js:41-65` |
| TTLs | `utils/eddCache.js:12`, `169` |
| Redis client behaviour; "clear" wipes the database | `utils/redisCache.js:27-41`, `93-96`, `109-149`; `flushDb` at :176-182 |
| Cart config failure → empty bundle, which is then cached | `cartEddV2ControlTower.js:1591-1605` (the returned value is cached by the wrapper) |
| Product-engine config failure throws | `eddMainV2ControlTower.js:844-846` |
| Product engine: stock or pincode/city/state lookup errors fail the request | `eddMainV2ControlTower.js:274-276` (throws) → `:202-208` (`success: false`) → `:45-47` (reject → HTTP 500); lat/lng errors are caught at `:302-308` |
| Rain-status read is uncaught | `control-tower/src/utils/rainInfo.js:30-48` |
| Tag buffers are uncached and uncaught | `cartEddV2ControlTower.js:87-106` |
| Response cache covers legacy endpoints only | `config/cache-config.js:22-36`; `server.js:61` vs `:77` |
| Rate limiter | `middleware/dbRateLimiter.js:7-8`, `20-21`, `174`, `191-200`; fail-open paths at :95, 138, 169, 187, 213 |
| Reads use the read connection | `control-tower/src/models/modelHelper.js:1-40` |

The HLD's Section 5 (comparison) has no separate evidence table. Its left column uses the facts in D.1–D.4, and its right column is labelled reasoning.
