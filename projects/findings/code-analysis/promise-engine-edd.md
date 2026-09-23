# Supertails Promise Engine — Delivery-Promise / EDD Computation Engine

Repo: `/Users/vikas1141sharma/Developer/promise-engine`. Analysis scope: the promise/EDD computation engine, its API surface, business rules, and data model. The ERP→inventory sync path is explicitly excluded (covered by a separate analysis). Read-only pass; no app run, no DB/GCP access, no git history inspected. Secrets (`api` file, `.env*`, `gcloud-service-account.json`) noted by existence only, never opened.

---

## 1. Service overview + what the engine owns

`control-tower-promise-engine` (package.json:2-3) is a single Node.js/Express process that owns two things bolted together:

1. **The Promise Engine** — SKU/cart-level EDD (estimated delivery date) calculation, in two live implementations:
   - **v2 / Control Tower** (current): `controllers/functions/ControlTower/eddMainV2ControlTower.js` (single/multi-SKU) and `controllers/functions/ControlTower/cartEddV2ControlTower.js` (cart, with shipment consolidation). Driven entirely by relational config in the Control Tower models.
   - **Legacy** (still mounted, still live): `controllers/functions/eddMainV2.js` and `controllers/functions/eddcartV2.js`, driven by a flat key-value "global configs" object (`getCutOff()`, `controllers/functions/CutOff/cutoOff.js`) rather than relational tables.
   - A third layer, `controllers/EddMapping.controller.js`, calls the **v2** functions and remaps their output into the **legacy** response shape — a strangler-fig compatibility adapter, not a third calculation path.
2. **Control Tower** — the configuration/serviceability service the engine reads from: clusters, warehouse-cluster SLA matrices, cutoffs, static/capacity/tag buffers, day-skips, geospatial polygons/H3 indexing, and a full rain-buffer subsystem. 29 Sequelize models (control-tower/src/models/index.js:4-32,119-150), 17 route files / 174 endpoints (control-tower/src/routes/*.js).

Runtime: Google App Engine Standard, `runtime: nodejs22`, `instance_class: F2` (app.yaml:1-2, 2 lines total, no scaling block). Express 4.18.2. MySQL via both Sequelize (control-tower) and raw `mysql2` pools (EDD engines' inventory/pincode reads). Redis for the EDD/config cache. Google Cloud Pub/Sub + Storage for ERP inventory sync (out of scope here). New Relic APM + Winston/Loggly logging.

---

## 2. Architecture, components, data flows, external systems

`server.js:1-119` is the composition root:
- `server.js:87-106` startup order: `initializeDatabases()` (database.js) → `initializeControlTower(mainSequelize())` (control-tower/src/app.js:155-170) → `app.listen()` → `require('./GCP/inventorySubscriber')` (Pub/Sub subscriber, started only after the HTTP server is listening).
- `server.js:60-82` mounts: `/control-tower` (a **nested full Express app**, control-tower/src/app.js, with its own CORS/Helmet/Swagger and internal `/api/v1` prefix), `/v2` (EddV2.controller.js), `/edd-mapping` (EddMapping.controller.js), `/health`, `/cache` (cache.controller.js), `/cronjob` (cronjob.controller.js), `/` (legacy Edd.controller.js). `dbRateLimiter` (middleware/dbRateLimiter.js) is applied globally at server.js:57, before every router.

Data flow for a cart-EDD request: client → `dbRateLimiter` → `EddV2.controller.js` → `cartEddV2ControlTower.js` → (Redis cache, via `utils/eddCache.js`) → MySQL (`promiseEngine` schema via `dbpromiseengine.js` for raw inventory/pincode SQL; control-tower schema via Sequelize models for cutoffs/buffers/SLA) → response assembled in-process → rain-buffer/capacity-buffer side-effects.

External systems evidenced in code: Shopify and ERP (credentials file `api`, existence-only per rules — no call site found via static grep in this pass, so its wiring is not confirmed); Google Cloud Pub/Sub (`GCP/inventoryPublisher.js`, `GCP/inventorySubscriber.js` — ERP inventory webhook, out of scope); Google Cloud Storage (`GCP/Storage.js`); AccuWeather (`control-tower/src/services/accuWeatherClient.js`, feeding the rain-buffer subsystem); Telegram (`control-tower/src/utils/telegramService.js`, likely alerting).

**Three separate MySQL connection layers exist side by side**: `database.js:34-107` (control-tower's Sequelize + a raw mysql2 pool pair, `connectionLimit:10` each), `dbpromiseengine.js:43-101` (a second raw mysql2 pool pair **and** a second independent Sequelize pair, also 10 each — required everywhere as `dbPromiseEngine`), and `dbPromiseEnginePool.js:13-27` (a third raw mysql2 pool pair, used only by the ERP cron jobs). See §12 for the risk this creates.

---

## 3. API surface

### `/v2` — `controllers/EddV2.controller.js` (238 lines, 6 routes), current engine
| Route | Purpose | Inputs | Downstream | Failure behaviour |
|---|---|---|---|---|
| `GET /v2/edd` (:13) | Single/multi-SKU EDD | `cpin, skuid, qty, lat, lng, showAll` | `EddMainV2ControlTower()` (:63) | Dedupes SKUs into a Map merging quantities (:41-58) before calling; re-sorts response to input order (:72-80); on throw, `console.error` + `res.status(500)` (:64-71) |
| `GET /v2/cartedd` (:88) | Cart EDD with shipments | `cpin, skuid, qty, lat, lng, showAll, orderCountUpdate` | `CartEddV2ControlTower(cpin, skus, qty, lat, lng, showAll, updateOrderCount)` (:138) | Same dedup (:110-131); 500 + `{success:false}` on throw (:139-146) |
| `GET /v2/warehouse-allocations` (:154) | Warehouse assignment only, no EDD math | `cpin, skuid, qty, lat, lng` | `getWarehouseAllocationsAgainstSKUs()` (cartEddV2ControlTower.js:161-220), which calls `calculateSingleEDD(true, ...)` — the `isWarehoueAllocations` flag short-circuits before any buffer/cutoff work (cartEddV2ControlTower.js:1714-1716) | 500 on throw |
| `GET /v2/warehouse-edd` (:191) | Same cart engine pinned to **one warehouse** — used by the Supertails delivery-note webhook per the task brief | `cpin, skuid, warehouse, showAll, orderCountUpdate` | `CartEddV2ControlTower(..., warehouse)` — warehouse name is resolved through `WarehouseMapping` then `ServingEntity` (cartEddV2ControlTower.js:38-63) | On throw, `res.send(e)` (:212) — leaks the raw error object to the client, no status code set |
| `GET /v2/GetPincodeDetails` (:221) | City/state lookup for a pincode | `cpin` | `EddFunctions.getCityStateFromPinCode1` (legacy `edd_functions.js`) | none visible |
| `GET /v2/` (:234) | Health banner | — | — | — |

### `/edd-mapping` — `controllers/EddMapping.controller.js` (14403 bytes, 2 routes)
`GET /edd-mapping/edd` and `GET /edd-mapping/cartedd` — call the **same** `EddMainV2ControlTower`/`CartEddV2ControlTower` functions as `/v2`, then run `mapV2ToEddResponse()` (EddMapping.controller.js:75-120+) to reshape each item into the legacy field set (string-cast qty, kg-converted weight, uppercased city, expanded state abbreviation). No parallel calculation — purely a response-shape adapter, so v2 and legacy-shaped numbers cannot drift apart.

### `/` — `controllers/Edd.controller.js` (332 lines, 6 routes), legacy engine
`GET /edd`, `GET /cartedd`, `GET /warehouse-edd`, `GET /GetPincodeDetails`, `GET /warehouse-allocations`, `GET /` — call `EddMainV2`/`CartEDDV2`/`getWarehouseAllocationsAgainstSKUsAndPinCode` (the pre-Control-Tower engine, `eddMainV2.js`/`eddcartV2.js`). Response fields are explicitly re-ordered via a hardcoded `orderedKeys` array (Edd.controller.js:39-70, 145-178).

### `/cache` — `controllers/cache.controller.js` (14 routes, verified by grep)
Full admin surface over the in-process NodeCache layer *and* Redis: `GET /stats`, `POST /clear` (NodeCache), `POST|DELETE /clear-redis`, `POST /clear-route`, `POST /reload-config`, `GET /config`, `GET /routes`, `GET /keys`, `GET/POST/PUT/DELETE /route[/:path]`, `GET /value/:key`.

### `/cronjob` — `cronjob/cronjob.controller.js` (12 routes, verified by grep)
Inventory/master-data crons (`/simple-inventory`, `/bundle-inventory`, `/itemMaster`, `/itemMaster-active-sku`, `/erp-simple-inventory`, `/erp-simple-inventory-paginated`, `/erp-inventory-webhook`, `/erp-itemMaster` — all ERP-related, out of scope), plus **weather/rain crons that do belong to this engine**: `/weather-poll`, `/weather-hourly-poll`, `/rain-approval-timeout` (cronjob.controller.js:107-157) — these feed the rain-buffer tables the EDD engines read.

### `/control-tower` — nested app, 174 endpoints across 17 route files (grep-verified per-file counts: `bulkUploadRoutes` 24, `rainRoutes` 21, `clusterRoutes` 19, `warehouseRoutes` 18, `cacheRoutes` 16, `h3IndexingRoutes` 11, `lookupRoutes`/`polygonRoutes` 10 each, `bulkRoutes` 8, `bufferRoutes` 7, `capacityRoutes`/`controlPanelUserRoutes` 6 each, `erpSyncRoutes`/`tagBufferRoutes` 5, `cutoffRoutes` 4, `auditLogRoutes`/`slaRoutes` 1 each, `index.js` mounting 2). Also serves generated Swagger docs at `/control-tower/api-docs` (control-tower/src/app.js:129-138, `config/swagger.js`).

### Not part of the request path
`controllers/functions/ControlTower/controlTowerWarehouse.js` (`ControlTowerWarehouseService`, 384 lines) is never imported by either live engine — grep across the whole repo shows only self-references (controlTowerWarehouse.js:10,42,47,384). Dead code.

---

## 4. The EDD algorithm in depth

### 4.1 Cart-EDD request lifecycle (function chain, file:line)

`CartEddV2ControlTower(cPIN, SKUs, qtys, lat, lng, showAll, updateOrderCount, warehouse)` — cartEddV2ControlTower.js:28-159

1. **`validateInputs`** (:223-241) — checks cPIN/SKUs presence, splits qtys.
2. Optional fixed-warehouse resolution (:37-63) via `WarehouseMapping.findOne` (ERP→UC name) then `getCachedServingEntity`/`ServingEntity.findOne`.
3. **`performHierarchicalInventorySearchWithShipments`** (:244-543) — the 4-level search (PRD's own diagram, `prd:264-374`, matches code order): 
   - `getPincodeData` (:1616-1641, cached, `cpinDataV2`).
   - Level 1 **lat/lng** (:268-295, only if coords given) → `searchInClusterTypeWithShipments('latlng', ...)`.
   - Level 2 **pincode** (:300-335) → same function, type `'pincode'`.
   - Level 3 **city** (:338-373).
   - Level 4 **state** (:376-411).
   - Each level: `findClustersByType` (:1204-1259, cached; `latlng` resolves via `H3IndexingService.resolveLocation`, others via `ClusterPincode`/`ClusterCity`/`ClusterState`) → `getWarehousesForClusters` (:1261-1314, cached; joins `ClusterWarehouseMatrix`+`ServingEntity`, pulls `max_shipment_weight`) → `fetchInventoryFromTables` (:1316-1415, cached DB read; SKU-sanitizes suffixes `CMD/REW/23NE/FG/BXGY/GIFT(only UNIBAN0001GIFT)/WBOGO/BBB25/SALE` at :1334-1342) → per-SKU allocation against **global** over-allocation tracker (:578-680, see §4.2).
   - Out-of-stock resolution (:413-518): SKUs never found, or found but not *fully* allocated across every warehouse touched, are pushed to `outOfStockSkus` for their **entire** requested quantity (all-or-nothing per SKU), and any partial inventory entries are deleted (:454-459,511-516) so no partial EDD is computed.
   - **`createShipmentGroups`** (:707-955) → **`fetchSLAConfigsForShipments`** (:1015-1052).
4. **`fetchControlTowerData`** (:1417-1614) — 5 queries in one `Promise.all` (:1435-1529): cutoffs (`WarehouseCutoff`), cluster_warehouse-scope static buffers (cached), warehouse/cluster-scope static buffers (cached), capacity buffers (**not cached**, real-time), SLA configs (`ClusterWarehouseMatrix`). Rain buffers merged in afterward via `mergeRainBuffersIntoControlTowerData` (:1608-1611, `control-tower/src/utils/rainBufferEdd.js:106-131`).
5. Tag buffers fetched once, unfiltered by SKU (:86-106, filtered per-SKU later).
6. **`calculateCartEDDWithShipments`** (:1055-1201) → per shipment, **`calculateSingleEDD`** (:1659-2430, see §4.6 for the 8-stage buffer pipeline) using the shipment's *combined* weight for SLA matching.
7. **Dedup to best time per SKU** (:111-126) — keeps the lowest `deliveryInMinutes` per `skuId`, accumulating qty/weight from the discarded duplicate.

### 4.2 Warehouse selection, allocation, partial fulfilment

Ranking: warehouses are ordered by `ClusterWarehouseMatrix.priority ASC` (getWarehousesForClusters, :1276). Selection within a level is **first-fit by priority**: for each pending SKU, iterate warehouses in priority order and take what's available (:582-655).

**Over-allocation prevention**: `globalWarehouseAllocations` (:265, `{sku: {warehouseName: qtyAlreadyPromised}}`) is threaded by reference through all four search levels. `availableQty = totalAvailableQty - globalAllocatedQty` (:607-615) is computed against this tracker, not the raw inventory column, so a warehouse that legitimately serves two different clusters (e.g. a pincode-cluster and a city-cluster) can never be double-promised. Each successful allocation updates the tracker (:622-626) before moving to the next SKU/warehouse.

**Partial fulfilment**: `remainingQty` for a SKU is decremented warehouse-by-warehouse within a level (:579-654); any leftover carries into the next level via an `updatedSkuVsQty` copy keyed off `_remainingQty` (:302-308, 340-346, 378-384). A SKU is only "found" when `remainingQty === 0` (:667-670); a SKU that partially clears some quantity but never reaches 0 across all four levels is still marked **fully** out of stock (§4.7).

### 4.3 Shipment generation

`createShipmentGroups` (:707-955): items are grouped by `${clusterId}_${warehouseId}` (:793,884). **Two-phase** processing — Phase 1 (:824-827) places ordinary SKUs; Phase 2 (:836-923) places gift/sample SKUs (`isSpecialSku`, :700-704: suffixes `FG`/`SAM`/`REW`, or the specific SKU `UNIBAN0001GIFT`), preferring to attach them to a warehouse **already used by a main item** (checked against the raw per-warehouse inventory columns, :855-863) so a gift doesn't force an extra shipment; only falls back to independent allocation if no existing shipment warehouse has stock (:916-922).

`createShipmentsFromItems` (:958-1012) does the actual weight-based packing: items are pre-sorted ascending by weight (:932), then **exploded to individual units** (:970) and added one at a time; the moment adding the next unit would push `currentShipment.totalWeight` over `maxWeightLimit`, the current shipment is closed and a new one starts (:973-982). `maxWeightLimit` comes from `ServingEntity.max_shipment_weight` (default 10000g fallback in code, :936,1301 — note the DB column's own default is 1000g, ServingEntity.js:70, a real inconsistency, see §12). Same-SKU units re-merge within a shipment via a find/filter/re-push (:992-999).

### 4.4 Delivery types

The **current** (Control Tower) system's authoritative vocabulary is the `delivery_type` ENUM shared by `ClusterWarehouseMatrix` (:61-66), `WarehouseCutoff` (:23-25), and `CapacityBuffer` (:23-25): `hyperlocal`, `hyperlocal B`, `SDD A`, `SDD B`, `SDD C`, `NDD A`, `NDD B`, `NDD C`, `Standard A`, `Standard B` — 10 values. The engine's own branching only really distinguishes **hyperlocal-family vs everything else** (cartEddV2ControlTower.js:1755-1765): hyperlocal uses a time-window cutoff; everything else uses a simple daily cutoff-time. A SKU's `delivery_type` is *derived*, not chosen directly — it's whatever `ClusterWarehouseMatrix` row matches the shipment's weight range (`min_weight`/`max_weight`, :1675-1678).

The **legacy** system instead classifies by courier capability table, not a DB enum: SDD (`shipsy/shipsy.js`, 2-hour/slotted/rolling), NDD (`NDD/ndd.js`), TDD (`TDD/tdd.js`), "Others" (`Othercouriers/othercourier.js`) — see `eddcart_function.js`/`eddcartV2.js` orchestration (`allotSDDWarehousesToSKU` → `allotNDDWarehousesToSKU` → `allotTDDWarehousesToSKU` → `allotOtherWarehousesToSKU`).

A **third, unused** classification exists: `H3IndexingService.getDeliveryTypes()`/`buildSLAMatrix()` (H3IndexingService.js:654-737) computes labels (`SDD_2H`,`SDD`,`NDD`,`TDD`,`STANDARD`) from `sla_value`/`sla_unit` thresholds inside `resolveLocation()`'s return value — but both EDD engines only destructure `.clusters` from that return value (cartEddV2ControlTower.js:1224-1225, eddMainV2ControlTower.js:303-304); `.slaMatrix` is computed and discarded on every lat/lng request. No literal `"superfast"` string exists anywhere in this repo's delivery-type vocabulary.

### 4.5 Cutoff logic

`WarehouseCutoff` (control-tower/src/models/WarehouseCutoff.js) stores, per `(warehouse_id, delivery_type)`: for hyperlocal/hyperlocal B → `start_time`+`end_time` (required by a `beforeCreate`/`beforeUpdate` hook, :123-133); for the other 8 types → `cutoff_time` (same hook). Both also carry `days_to_add` (int, default 0) and `time` (the wall-clock to reset to).

Application (`calculateSingleEDD`, cartEddV2ControlTower.js:1741-1824, identical logic in eddMainV2ControlTower.js:1047-1127): hyperlocal cutoff fires when `currentTimeSt < start_time || currentTimeSt > end_time` (:1760) — i.e. *outside* the serviceable window; non-hyperlocal fires when `cutoff_time < currentTimeSt` (:1764) — i.e. ordered after the daily cutoff. On fire, `days_to_add` days are added and the clock is **hard-set** to `time` via `.setHours/.setMinutes/.setSeconds` (:1789-1791) — not incremented, so there's no carry-arithmetic to get wrong across midnight.

**IST anchoring without a timezone library**: the Control Tower engine manufactures IST wall-clock values by adding `5.5 * 60 * 60 * 1000` ms to the current UTC epoch and then reading `.getHours()`/`.toTimeString()` on the result as if local (cartEddV2ControlTower.js:1663-1664,1743-1746; eddMainV2ControlTower.js — same pattern, e.g. :975). This works because the process itself runs in UTC; package.json has no `moment-timezone`/`date-fns-tz`/`luxon` dependency. The **legacy** engine uses a *different* technique — explicit `Date.UTC(istYear, istMonth, istDay, H, M, 0, 0)` calls with hand-written IST→UTC comments (`eddcartV2.js:462,466,515,530`, e.g. `// 2 PM IST = 8:30AM UTC = 08:30 UTC`) — a second, inconsistent way of solving the same problem inside one repo.

Two more explicit midnight/late-night rules (cartEddV2ControlTower.js:1670-1690): if the computed delivery time equals `currentDate` exactly, it's pinned to 22:00 today (if before 22:00) or 22:00 tomorrow; if delivery time lands at 23:00-23:59, it rolls to 13:00 the next day. Non-hyperlocal deliveries default to 22:00 unless a day-skip already re-anchored the time via `resetDeliveryTimeToCutoff` (utils/eddDaySkip.js:1-19) — a small helper added specifically because a day-skip advancing the *date* was leaving a stale, wrong time-of-day (explained in the code's own comment, cartEddV2ControlTower.js ~2213-2215).

### 4.6 The buffer stack (order of application, `calculateSingleEDD`)

1. **Cutoffs** (`WarehouseCutoff`) — may advance `istTime` and, if hyperlocal, replace the SLA-addition step entirely (`if(!cutoffApplied){ ...add SLA... }`, :1341/2043).
2. **Static buffers, `buffer_nature='time_addition'`** (`StaticBuffer`, priority `cluster_warehouse` > `warehouse` > `cluster`; weight-range gated when scope is `cluster_warehouse`; area-gated via `StaticBufferArea` — polygon/pincode/city/state, :1830-1919). **Rain buffer** is injected into this same array *before* the loop runs, but only if no genuine SCM static buffer already exists for the warehouse (`hasScmStaticBuffer`, `rainBufferEdd.js:54-59`) — rain and configured buffers never stack.
3. **Capacity buffers** (`CapacityBuffer`, real-time, delivery-type matched; the DB query itself only returns rows already breached: `WHERE order_count + spill >= capacity`, :1512/746).
4. **Tag buffers** (`TagBuffer`, matched against `skuVsTagsMap[skuId]`, summed via `TagBufferService.calculateTotalTagBufferTime`, TagBufferService.js:228-250).
5. **SLA time addition** (`ClusterWarehouseMatrix.sla_value/sla_unit` → hour/day/min, :2046-2060).
6. **Pickup day-skip** (`StaticBuffer` where `buffer_nature='day_skip'` + `DaySkip.pickup_skip` weekday list / `pickup_date_skip` specific dates) — walked forward day-by-day on a *separate* "pickup" clock (:2074-2206).
7. **Delivery day-skip** (same `DaySkip` row's `delivery_skip`/`delivery_date_skip`) — walked forward on the real `deliveryTime` clock (:2223-2359).
8. **Time-of-day normalization** — reset-to-cutoff-`time` after a day-skip, else default-to-22:00 for non-hyperlocal, else the ≥23:30 → next-day-13:00 rollover (:2361-2382).

### 4.7 Availability/inventory read path

Tables: `EDDItemMaster` INNER JOIN `EdditemInventory` ON `skuId=skuCode`, raw SQL via `promiseEngineConnection.readQuery` (cartEddV2ControlTower.js:1352-1374; eddMainV2ControlTower.js:551-573). `cpinDataV2` for pincode→city/state (cartEddV2ControlTower.js:1616-1641). `WarehouseMapping` (Sequelize, top-level `models/WarehouseMapping.js`) for ERP↔UC warehouse name translation.

**Warehouse-per-column shape**: `EdditemInventory` stores one column per warehouse name (`d[warehouseName]`, cartEddV2ControlTower.js:1387, eddMainV2ControlTower.js:600) rather than a normalized `(sku, warehouse, qty)` row. The engine `SELECT *`s the joined row once per candidate SKU set, then iterates the *known* warehouse names in application code to pick out each one's quantity — cheap in-memory lookups, but every new warehouse/darkstore requires an `ALTER TABLE ADD COLUMN`.

`outOfStock[]` (really: items folded into `skuWisEdd[]` with `deliveryFormat:"Out of Stock"`, see §4.8) is built when (a) a SKU is never found in any of the 4 levels (:415-424), or (b) it's found but the **sum** of what was allocated across every warehouse it touched is still less than requested (:426-464) — in which case the *entire* requested quantity is marked OOS and any partial inventory rows already recorded for that SKU are deleted (:454-459) so nothing partial leaks into the EDD calculation. All-or-nothing per SKU.

### 4.8 Output contract

`CartEddV2ControlTower()` resolves `{ skuWisEdd: [...], shipmentInfo: [...], totalShipments: N }` (cartEddV2ControlTower.js:1056-1059 initial shape, :129 `totalShipments`), with `rainInfo` attached per item/shipment by `attachRainInfoToCartResponse` (rainInfo.js:63-85). **Correction to the brief's assumed shape**: the field is `shipmentInfo`, not `shipments`, and there is no separate top-level `outOfStock[]` array — OOS items are inlined into `skuWisEdd[]` (cartEddV2ControlTower.js:1063-1082). This matches the `cart-revmp` skill's independently-recorded consumer-side contract (`{skuWisEdd, shipmentInfo, totalShipments}`), which cross-validates the finding.

`eddConstituents` (identical shape in both engines) carries: `SLA_VALUE, SLA_UNIT, SLA_WEIGHT_SLAB, STATIC_BUFFERS[], CAPACITY_BUFFERS[], TAG_BUFFERS[], TOTAL_BUFFER, TOTAL_BUFFER_IN_DAYS/HOURS/MINUTES, CUTOFFS[], TOTAL_CUTOFF, EDD, PICKUP_DATE_TIME, PICKUP_SKIP_DAYS[], PICKUP_SKIP_DATES[], DELIVERY_SKIP_DAYS[], DELIVERY_SKIP_DATES[]` — 16 named fields (cartEddV2ControlTower.js:1720-1734,2407-2411). Which 10 of these the Supertails cart-orchestrator consumer actually reads is a `supertails-backend` question, out of scope for this pass — not verified here.

---

## 5. Data model

### Control Tower — 29 registered Sequelize models (control-tower/src/models/index.js:4-32, exported :119-150) + `index.js` (associations) + `modelHelper.js` (read/write split helper) = 31 `.js` files in the directory. One further Sequelize model, `models/WarehouseMapping.js`, lives **outside** control-tower against `dbpromiseengine.js`'s `readSequelize`.

| Category | Models |
|---|---|
| Geo / polygon | `GeoPolygon`, `PolygonH3Index` |
| Cluster definition & mapping | `Cluster`, `ClusterPolygon`, `ClusterPincode`, `ClusterCity`, `ClusterState` |
| Warehouse / SLA | `ServingEntity`, `ClusterWarehouseMatrix` |
| Pincode | `PincodeData` |
| Cutoff | `WarehouseCutoff` |
| Buffers | `StaticBuffer`, `StaticBufferArea`, `CapacityBuffer`, `TagBuffer`, `DaySkip` |
| Rate limiting | `RateLimitEndpoint`, `RateLimitTracking` |
| Admin / audit | `ControlPanelUser`, `AuditLog` |
| Rain buffer subsystem | `RainBufferMatrix`, `RainIntensityBuffer`, `RainStatus`, `RainBufferAlert`, `RainAccuWeatherLocation`, `RainHourlyIntensity`, `RainBufferApprovalSettings`, `RainBufferApprovalBatch`, `RainBufferApproval` (9 models — a substantial subsystem in its own right) |
| External mapping | `models/WarehouseMapping.js` (outside control-tower) |

Notable schema details: `StaticBuffer` enforces `buffer_scope`-dependent required fields and `start_datetime < end_datetime` via hooks (StaticBuffer.js:143-186); `CapacityBuffer` has a unique index on `(warehouse_id, delivery_type, time_frame_start, time_frame_end)` (CapacityBuffer.js:100-104) and tracks `order_count`/`spill`/`breach_time` for live capacity accounting; `ClusterWarehouseMatrix` has a unique index on `(cluster_id, warehouse_id, min_weight, max_weight)` (ClusterWarehouseMatrix.js:98-101) so weight slabs can't overlap-collide by accident; `ServingEntity.location` is a MySQL `GEOMETRY('POINT',4326)` column with its spatial index explicitly **disabled** in code ("Temporarily disabled spatial index due to MySQL version compatibility", ServingEntity.js:107-111).

### promiseEngine schema (raw SQL, no Sequelize models found)
`EDDItemMaster`, `EdditemInventory` (warehouse-per-column, see §4.7), `cpinDataV2`, `day_skip` (legacy day-skip table, distinct from the Control Tower `DaySkip` model — `eddFunctions.js:6`), `DBD_Back_Up` (`eddFunctions.js:24`).

---

## 6. Business rules catalogue

- 4-level hierarchical serviceability search, lat/lng → pincode → city → state, stopping early once all SKUs are found (prd:264-374; cartEddV2ControlTower.js:244-411).
- Global cross-cluster over-allocation prevention (cartEddV2ControlTower.js:265,607-626).
- All-or-nothing OOS per SKU when only partially allocated across every warehouse touched (cartEddV2ControlTower.js:426-464).
- Weight-based shipment splitting at unit granularity against `ServingEntity.max_shipment_weight` (cartEddV2ControlTower.js:958-1012).
- Gift/sample SKUs (`FG`/`SAM`/`REW` suffix, or `UNIBAN0001GIFT`) preferentially ride an existing shipment's warehouse before getting their own (cartEddV2ControlTower.js:700-704,835-923).
- SKU sanitization for 9 promotional/bundle suffix patterns before inventory lookup (cartEddV2ControlTower.js:1334-1342).
- Buffer scope priority `cluster_warehouse > warehouse > cluster` (cartEddV2ControlTower.js:798-810/1830-1919).
- Rain buffer never stacks with a configured static buffer for the same warehouse (rainBufferEdd.js:54-100).
- Capacity buffers only apply once a warehouse's time-window is *already* breached (`order_count+spill>=capacity`) (cartEddV2ControlTower.js:1505-1516).
- Hyperlocal cutoff = outside a time window; all other delivery types = simple "cutoff time already passed" (cartEddV2ControlTower.js:1755-1765).
- Non-hyperlocal deliveries default to 22:00 IST unless a day-skip already fixed the time; ≥23:30 rolls to next-day 13:00 (cartEddV2ControlTower.js:1670-1690).
- SLA is matched by weight range against `ClusterWarehouseMatrix.min_weight/max_weight`, not chosen directly (cartEddV2ControlTower.js:1675-1678).
- Warehouse priority ordering is per-cluster, not global (`ClusterWarehouseMatrix.priority`, getWarehousesForClusters :1276).
- DG (dangerous goods) courier routing exists **only** in the legacy engine (`eddcartV2.js:814-825`, `eddMainV2.js:625-639`, via `getCourierDataDG`) — no equivalent branch in the v2 Control Tower engine.
- `/v2/warehouse-edd` reuses the full cart pipeline pinned to one warehouse specifically to serve "the Supertails delivery-note webhook" per the task brief (EddV2.controller.js:191-219).
- `/edd-mapping/*` is a pure response-shape adapter over the v2 engine, not an independent calculation (EddMapping.controller.js:1-68).

---

## 7. Edge cases, fallbacks, failure modes

- **Missing pincode**: `getPincodeData` resolves null/false → engine rejects with `{success:false, message:"...pincode..."}` (eddMainV2ControlTower.js:118-125; cartEddV2ControlTower.js:247-255) → controller catches and returns **HTTP 500** (EddV2.controller.js:64-71,139-146) — a business 404 surfaced as a server error.
- **Missing cluster at one level**: logged (`formatClusterNotFoundError`), search silently falls through to the next level (cartEddV2ControlTower.js:551-556,2524-2537).
- **No warehouse for a found cluster**: same silent fallthrough (cartEddV2ControlTower.js:561-564).
- **Zero/insufficient inventory**: SKU ends up in `outOfStockSkus` (§4.7).
- **Weight overflow**: handled proactively by the packer (§4.3); a single unit heavier than `maxWeightLimit` still becomes its own over-limit shipment — no clamp or rejection path visible.
- **Gift/sample SKUs**: two-phase shipment assignment (§4.3).
- **DG items**: routed only by the legacy engine; **not handled at all** by the v2 Control Tower engine (no `dgMapCart`/DG branch found in cartEddV2ControlTower.js or eddMainV2ControlTower.js).
- **No matching SLA for a weight**: the shipment/SKU is `continue`d past — **silently dropped from the response**, not converted to an OOS entry or an error field the caller can see (cartEddV2ControlTower.js:1140-1143; eddMainV2ControlTower.js:958-963).
- **Config missing generally**: functions return structured `{error, errorDescription, responseCode}` objects inline rather than throwing in most branches (cartEddV2ControlTower.js:1680-1695).
- **Redis down**: every cache wrapper (`getOrSetCache`, eddCache.js:41-64) try/catches and falls through to the DB query function — fail-open, logged, no user-facing error. Same fail-open pattern in `dbRateLimiter` (:106-109,136-139,184-188,209-213) and `TokenBucket` (:95-102,193-201,283-289).
- **DB down**: the **control-tower** DB failing at boot kills the process (`initializeDatabases()` throws → server.js:102-104 `process.exit(1)`). The **separate** `dbpromiseengine.js`/`dbPromiseEnginePool.js` connections are created eagerly at module load with no equivalent startup verification — a failure there would only surface as query-time rejections deep inside `readQuery` calls, not a clean boot failure. Asymmetric failure handling between the two DB layers.

---

## 8. Performance + scalability mechanisms and bottlenecks

- **In-process HTTP cache** (`middleware/cache.js`, NodeCache-backed) currently only covers the **legacy** `GET /edd` and `GET /cartedd` routes at 600s TTL (config/cache-config.js:22-36) — the v2 Control Tower routes are not in this table at all.
- **Redis cache layer** (`utils/eddCache.js`) wraps pincode, per-type cluster lookups, warehouse-for-cluster lookups, inventory, the whole control-tower-data bundle, H3 lat/lng resolution, and `ServingEntity` lookups. Default `EDD_CACHE_TTL` 300s (env-overridable, eddCache.js:12); `ServingEntity` gets a longer fixed 3600s (eddCache.js:169). **Deliberately not cached**: `CapacityBuffer` and `TagBuffer` reads (fetched fresh every request, cartEddV2ControlTower.js:1505-1516,86-106) because both are order-sensitive/time-sensitive.
- **Cache admin surface**: 14 endpoints (`cache.controller.js`) for stats, full-flush (NodeCache and Redis separately), per-route clear/CRUD, and raw key inspection.
- **DB-backed rate limiter + token bucket**: `dbRateLimiter` (applied globally, server.js:57) only enforces on endpoints present and `is_active` in `RateLimitEndpoint` (cached 30 days = 2,592,000s, dbRateLimiter.js:21), matched exact-or-`/*`-wildcard. Enforcement is a Redis-Lua atomic token bucket (default capacity 100/60s window, dbRateLimiter.js:7-16; Lua script tokenBucket.js:109-160) with a non-atomic cache-based fallback if Lua fails (tokenBucket.js:223-291) — fail-open at every layer.
- **Pool sizing — the clearest bottleneck candidate**: at least 6 separate `mysql.createPool`/`new Sequelize` instantiations across 3 files, every one sized `connectionLimit`/`pool.max = 10`: `database.js:34-53` (mysql2 main+read) and `:72-77,99-104` (Sequelize main+read); `dbpromiseengine.js:43-57` (mysql2) and `:67-74,93-98` (Sequelize+readSequelize); `dbPromiseEnginePool.js:13-27` (mysql2, ERP crons). No single tunable pool, and no visible evidence they're coordinated against one MySQL `max_connections` budget.
- **Per-request query count** is not constant: floor of ~8-10 queries when caches are warm (1 pincode + up to 4 hierarchy-level cluster/warehouse lookups + 1 inventory join + 5 parallel control-tower queries + 1 tag-buffer query), growing with the number of hierarchy levels actually walked and the number of shipments/warehouses used (extra `StaticBufferArea`/`DaySkip` lookups per applicable buffer, though these are themselves cached).
- **`app.yaml`** carries no `automatic_scaling`/`resources` block (app.yaml:1-2) — GAE Standard defaults govern autoscaling, which, combined with the pool sprawl above, means each new instance multiplies the connection count.

---

## 9. Numbers

### (a) Derivable from code/docs, with source
| Metric | Value | Source |
|---|---|---|
| EddV2.controller.js routes | 6 | EddV2.controller.js:13,88,154,191,221,234 |
| Legacy Edd.controller.js routes | 6 | grep, confirmed |
| EddMapping.controller.js routes | 2 | EddMapping.controller.js:10,41 |
| cache.controller.js routes | 14 | grep, confirmed |
| cronjob.controller.js routes | 12 | grep, confirmed |
| control-tower routes | 174 across 17 files | grep across control-tower/src/routes/*.js |
| Control Tower Sequelize models | 29 registered (+ index.js + modelHelper.js = 31 files in the dir); +1 more (`WarehouseMapping`) outside control-tower | control-tower/src/models/index.js:4-32,119-150 |
| Hierarchical search levels | 4 (lat/lng, pincode, city, state) | cartEddV2ControlTower.js:244-411; prd:264-374 |
| Buffer/adjustment stages (order) | 8 | §4.6 |
| Delivery-type ENUM values (current system) | 10 | ClusterWarehouseMatrix.js:61-66 |
| SKU-sanitization suffix patterns | 9 | cartEddV2ControlTower.js:1334-1342 |
| `max_shipment_weight` DB default vs code fallback | 1000g vs 10000g (mismatch) | ServingEntity.js:70 vs cartEddV2ControlTower.js:936,1301 |
| Raw/Sequelize connection pool instantiations | ≥6, all sized 10 | database.js, dbpromiseengine.js, dbPromiseEnginePool.js |
| `EDD_CACHE_TTL` default | 300s | utils/eddCache.js:12 |
| `ServingEntity` cache TTL | 3600s | utils/eddCache.js:169 |
| Rate-limit endpoint config cache TTL | 2,592,000s (30d) | middleware/dbRateLimiter.js:21 |
| Token bucket default capacity/window | 100 tokens / 60s | middleware/dbRateLimiter.js:7-16 |
| Legacy `/edd`,`/cartedd` HTTP cache TTL | 600s | config/cache-config.js:25,33 |
| `app.yaml` | `runtime: nodejs22`, `instance_class: F2`, 2 lines, no scaling block | app.yaml:1-2 |
| package.json runtime dependencies | 30 | package.json:16-45 |
| Automated tests | none (`test/` empty; `npm test` is a no-op) | package.json:10; `test/` dir listing |

### (b) Missing metrics — questions to ask the user
1. EDD calls/day for `/v2/edd` + `/v2/cartedd` combined, and how much residual traffic the legacy `/edd`,`/cartedd` and `/edd-mapping/*` routes still carry.
2. Observed p95/p99 latency for `/v2/cartedd` in production, and its DB/Redis-time vs in-process-compute split.
3. Count of active `ServingEntity` rows (warehouses/darkstores) today, and the corresponding number of `EdditemInventory` warehouse columns.
4. SKU catalogue size (distinct `EDDItemMaster` rows) typically passed into the inventory `WHERE skuId IN (?)` query.
5. Average and p95 shipments produced per cart order.
6. Observed out-of-stock rate (fraction of SKU requests ending as `deliveryFormat:"Out of Stock"`).
7. Any tracked promise-accuracy metric (delivered date vs promised date) downstream, and its current value.
8. Relative request volume across the three coexisting systems (legacy / v2 Control Tower / edd-mapping shim) — is legacy traffic materially still live?

---

## 10. Candidate resume bullets

**1. Architected a multi-tier delivery-promise engine:** Designed and built the EDD computation service running as both a single-SKU and a shipment-aware cart engine, resolving warehouse serviceability through a four-level geographic fallback (lat/lng → pincode → city → state) before any buffer or cutoff logic runs.
Evidence: controllers/functions/ControlTower/cartEddV2ControlTower.js:244-543

**2. Engineered a cross-cluster over-allocation guard:** Built a global warehouse-allocation tracker that follows a SKU across all four search levels so the same physical warehouse can never be double-promised when it serves more than one cluster simultaneously.
Evidence: controllers/functions/ControlTower/cartEddV2ControlTower.js:265,607-626

**3. Designed partial-fulfillment logic for split shipments:** Implemented quantity-level allocation letting one SKU's order quantity divide across multiple warehouses/clusters when no single location can fulfil it alone, carrying remaining quantity forward through each search level.
Evidence: controllers/functions/ControlTower/cartEddV2ControlTower.js:578-680,300-411

**4. Built a unit-level weight bin-packer for shipment consolidation:** Wrote a streaming packer that groups cart items into shipments per cluster-warehouse, splitting mid-SKU by individual unit weight whenever a warehouse's configured maximum shipment weight would be exceeded.
Evidence: controllers/functions/ControlTower/cartEddV2ControlTower.js:707-955,958-1012

**5. Modeled an 8-stage configurable buffer pipeline:** Designed the buffer/cutoff computation order — cutoff, static (cluster/warehouse/cluster-warehouse scoped), weather-driven, capacity, tag, SLA, pickup day-skip, delivery day-skip — each independently tunable through relational config rather than code changes.
Evidence: controllers/functions/ControlTower/cartEddV2ControlTower.js:1659-2359

**6. Integrated a real-time weather buffer without double-counting:** Added logic that injects a rain-driven delivery buffer only when no manually configured static buffer already exists for a warehouse, preventing the two buffer sources from stacking on one promise.
Evidence: control-tower/src/utils/rainBufferEdd.js:54-100

**7. Hardened cutoff handling against day-skip corruption:** Diagnosed and fixed a bug where a day-skip buffer advanced the delivery date but left a stale time-of-day; added a warehouse-cutoff-time reset that re-anchors the clock after every pickup/delivery day-skip.
Evidence: utils/eddDaySkip.js:1-19; controllers/functions/ControlTower/cartEddV2ControlTower.js:2213-2221,2352-2358

**8. Designed a 29-model relational configuration engine (Control Tower):** Modeled cutoffs, static/capacity/tag buffers, cluster-to-warehouse SLA matrices, day-skips, and a full rain-buffer subsystem as versioned Sequelize models with weight/area/time-window scoping, replacing an earlier key-value global-config system.
Evidence: control-tower/src/models/index.js:4-32,119-150; controllers/functions/eddcartV2.js:304-353

**9. Exposed a 174-endpoint configuration API surface:** Built the Control Tower's route layer spanning clusters, warehouses, cutoffs, buffers, capacity, polygons, H3 indexing, bulk upload, rate-limit config, and audit logging across 17 route modules, backed by generated Swagger documentation.
Evidence: control-tower/src/routes/ (17 files, 174 routes); control-tower/src/config/swagger.js

**10. Orchestrated H3 hexagonal geospatial resolution for delivery zones:** Implemented lat/lng-to-serviceability-cluster resolution using Uber's H3 indexing library against stored polygon boundaries, with cached results feeding directly into cart-EDD warehouse search.
Evidence: control-tower/src/services/H3IndexingService.js:161-262; utils/eddCache.js:154-159

**11. Built a fail-open, multi-layer caching strategy for a latency-sensitive read path:** Wrapped every control-tower and inventory lookup in a Redis cache with per-data-type TTLs, deliberately excluding capacity and tag buffers to keep real-time fields fresh, with every cache path falling back to direct DB reads on Redis failure.
Evidence: utils/eddCache.js:41-183

**12. Implemented an atomic Redis token-bucket rate limiter:** Designed a per-IP/per-endpoint/per-method rate limiter using a single Lua script for atomic refill-and-consume, driven by a database-configurable endpoint allowlist cached for 30 days, with a non-atomic fallback path when Lua execution is unavailable.
Evidence: utils/tokenBucket.js:109-201; middleware/dbRateLimiter.js:75-214

**13. Ran two EDD engines and a response-shape adapter in production simultaneously:** Maintained a legacy config-driven EDD engine and a newer Control-Tower-driven engine behind separate route prefixes, plus a dedicated shim that calls the new engine and remaps its response into the legacy contract for callers that had not migrated.
Evidence: controllers/EddMapping.controller.js:1-68; server.js:60-82

**14. Optimized warehouse-allocation lookups by reusing the EDD calculation path:** Added an early-return branch inside the shared single-EDD calculator so a dedicated warehouse-allocation endpoint reuses the full allocation/shipment pipeline while skipping the buffer/cutoff work it doesn't need.
Evidence: controllers/functions/ControlTower/cartEddV2ControlTower.js:1714-1716,161-220

**15. Designed SKU-sanitization for promotional/bundle variants:** Built suffix-stripping logic (CMD, REW, 23NE, FG, BXGY, WBOGO, BBB25, SALE, and a specific GIFT SKU) so promotional SKU variants resolve to the same base inventory row without duplicating master data per variant.
Evidence: controllers/functions/ControlTower/cartEddV2ControlTower.js:1330-1345

---

## 11. Interview material

### Hard problems (problem → constraint → decision → consequence)

**P1 — Cross-cluster over-allocation.** *Problem*: the same warehouse can appear in more than one geographic cluster for one request. *Constraint*: the 4-level search runs level-by-level, each fetching its own warehouse list independently, so naive per-level checks would let one warehouse's stock satisfy the same SKU twice. *Decision*: `globalWarehouseAllocations` (cartEddV2ControlTower.js:265) is a `sku→warehouse→qty` map threaded by reference through all four levels; `availableQty` is always computed net of what's already promised (:615). *Consequence*: correctness costs real bookkeeping complexity — merging partial allocation state across levels (:275-291,315-332, etc.) is a significant share of the file's length.

**P2 — Partial fulfilment without double-shipping.** *Problem*: split one SKU's quantity across warehouses without losing or duplicating units. *Constraint*: leftover quantity must survive both within-level warehouse iteration and across-level fallback. *Decision*: `remainingQty` decrements in priority order within a level (:578-680); leftovers carry forward via an `updatedSkuVsQty` copy driven by `_remainingQty` (:300-309 etc.); a SKU only counts as found at exactly 0 remaining. *Consequence*: a SKU that ends up partially-but-not-fully covered after all 4 levels is deliberately treated as **fully** out of stock (:426-464) — a conscious "no partial promise" policy, not an oversight.

**P3 — Weight-capped shipment packing without breaking a SKU unpredictably.** *Problem*: pack cart items into shipments under a per-warehouse weight cap. *Constraint*: a single SKU's quantity might itself need to span two shipments. *Decision*: `createShipmentsFromItems` (:958-1012) explodes items to individual units and packs first-fit, closing a shipment the moment the *next* unit would exceed the cap. *Consequence*: this is simple first-fit, not weight-optimal bin-packing, and there's no clamp for a single unit heavier than the cap on its own.

**P4 — Cutoffs near midnight with no timezone library.** *Problem*: `days_to_add` + a target clock time must combine correctly regardless of where "now" falls relative to UTC midnight. *Constraint*: package.json has no timezone library. *Decision*: shift the epoch by `+5.5h` to get an IST-equivalent Date, compare only the time-of-day string against configured cutoffs, then on fire, `.setHours/.setMinutes/.setSeconds` to hard-pin the target clock time rather than adding hours incrementally (:1789-1791). *Consequence*: verbose but avoids a whole class of rollover bugs a naive `+N*ms` approach would risk.

**P5 — Rain buffer vs manual buffer double-counting.** *Problem*: a weather buffer and a manually configured static buffer both want to delay the same promise. *Constraint*: the rain entry is merged into the same array the manual buffers live in, before the application loop runs. *Decision*: `hasScmStaticBuffer()` (rainBufferEdd.js:54-59) skips injecting rain if ANY non-rain buffer already exists for that warehouse; each entry carries a `source`/`rain_buffer_included` marker for traceability. *Consequence*: rain is a fallback, not additive — a deliberate trade-off a customer could reasonably question ("what if the manual buffer was small and the storm was huge?").

**P6 — A second response contract without duplicating the math.** *Problem*: serve old callers a legacy-shaped response without maintaining a second calculation engine. *Constraint*: the v2 engine's shape (`skuWisEdd[]` + `eddConstituents`) differs structurally from the legacy shape. *Decision*: `EddMapping.controller.js` calls the same v2 functions the `/v2` routes call and runs a pure field-mapping function over the result — no parallel math. *Consequence*: clean strangler-fig pattern, but the mapping layer is coupled to whatever field names the v2 engine happens to use, with no compile-time contract check (plain JS destructuring).

### Likely follow-up questions

1. **What makes EDD hard here?** It's a pipeline, not a formula: geographic fallback search → global-allocation-aware assignment → unit-level weight packing → an 8-stage buffer/cutoff pipeline with real ordering dependencies (a hyperlocal cutoff *replaces* SLA-addition; day-skips need a post-hoc clock reset) — and two of those stages do manual IST arithmetic with zero timezone library.
2. **How do you prevent over-allocation?** A `sku→warehouse→qty-already-promised` map (`globalWarehouseAllocations`, cartEddV2ControlTower.js:265) threaded by reference through all four hierarchy levels; every allocation check subtracts what's already promised before deciding how much more a warehouse can give (:615).
3. **Why split a SKU across warehouses?** Because inventory is checked per physical warehouse; rather than declaring a SKU OOS the moment one warehouse falls short, the search keeps going (within a level by priority, and across levels) and only gives up if the sum across every warehouse touched still falls short (:578-680,426-464).
4. **How do you handle a cutoff crossing midnight in IST?** No special-cased "midnight crossing" branch exists — whole days are added via `days_to_add`, then the clock is hard-set to the configured `time`, so there's no incremental hour-arithmetic to carry incorrectly (:1789-1791).
5. **What happens when inventory is stale?** No staleness *detection* inside the EDD engine itself — numbers are DB-fresh on cache miss or served from Redis within a 60-300s TTL depending on the wrapper; the ERP sync that keeps the underlying tables current is a separate system, out of scope for this analysis.
6. **Why doesn't the single-SKU engine track shipments?** Per the engine's own comparison doc (`prd`, comparison-matrix section) and the code (eddMainV2ControlTower.js:893-965), it was built for the simpler "one SKU, first warehouse that fully covers it" case with no consolidation need.
7. **Static buffer vs capacity buffer — what's the difference?** `StaticBuffer` is scheduled config (active window, cluster/warehouse/cluster-warehouse scope, time-addition or day-skip nature). `CapacityBuffer` is reactive — it only contributes once `order_count+spill >= capacity` for that warehouse+delivery_type+window (query-level filter, :1512), and it's the only buffer type actually *written* to per order (`updateCapacityBuffer`).
8. **How does a shipment pick its cutoff?** Indirectly — weight determines the SLA match (`ClusterWarehouseMatrix.min/max_weight`), the SLA carries a `delivery_type`, and the cutoff lookup filters `ctData.cutoffs` for the row whose `delivery_type` matches that.
9. **What if the same warehouse shows up under two clusters at different priorities?** `removeDuplicateWarehouses` dedupes on `${warehouseId}_${clusterId}` (:1643-1656) — same warehouse under *different* clusters stays as two entries (different priorities are legitimate); only an exact warehouse+cluster repeat collapses.
10. **Is the response contract stable?** The real shape is `{skuWisEdd, shipmentInfo, totalShipments}` with OOS items inlined — a consumer expecting a `shipments` key or a separate `outOfStock[]` array gets silently missing data, not an error (no schema validation on output).
11. **How do you keep query count bounded across a whole cart?** Per-warehouse config (cutoffs, both static-buffer scopes, capacity, SLA) is fetched once per request via one `Promise.all` (:1435-1529) and grouped in memory; `calculateSingleEDD` then only `.filter()`s that pre-fetched data — the only remaining per-item queries (area/day-skip lookups) are themselves cached.
12. **Biggest untested risk?** Zero automated tests (`test/` empty, `npm test` a no-op) over a pipeline whose branches (cutoff type, buffer scope priority, area matching, day-of-week vs specific-date skip, rain mutual-exclusion) combine multiplicatively — nothing catches an ordering regression before production.

---

## 12. Red flags — genuine technical issues, bugs, gaps

1. **Dead code — `ControlTowerWarehouseService`**: `controllers/functions/ControlTower/controlTowerWarehouse.js` (384 lines) is never imported by either live engine (verified by repo-wide grep, only self-references at :10,42,47,384).
2. **Dead code — `findClustersAndWarehouses`**: `eddMainV2ControlTower.js:406-490` is explicitly commented "legacy function - keeping for reference" and left in the shipped file.
3. **Copy-paste drift in customer-facing copy**: `formatDeliveryMessages` is duplicated near-verbatim between `cartEddV2ControlTower.js` (~2437-2488, prefixes `"Delivery in"/"Delivery by"`) and `eddMainV2ControlTower.js` (~1744-1795, prefixes `"Get it in"/"Get it by"`) for identical thresholds — `/v2/cartedd` and `/v2/edd` can show different wording for equivalent timing.
4. **Cross-platform require-casing mismatch**: `require('../../../dbPromiseEngine')` (mixed case) is used consistently in 20+ files (grep-verified), but the file on disk is `dbpromiseengine.js` (all lowercase). Works on case-insensitive filesystems (local macOS dev); at risk on case-sensitive ones. Not verified at runtime in this pass (app was not run per the read-only rule) — flagged purely from the on-disk name vs require-string mismatch.
5. **Commented-out hardcoded DB credentials**: top-of-file comment blocks in `dbPromiseEnginePool.js` and `dbpromiseengine.js` contain a commented-out host/user/password. Dead code, but the values are still in the file/history. Existence flagged only; values not reproduced here.
6. **Connection-pool sprawl**: ≥6 separate `mysql.createPool`/`new Sequelize` instantiations (`connectionLimit`/`pool.max=10` each) across `database.js`, `dbpromiseengine.js`, `dbPromiseEnginePool.js` — no single tunable pool, no visible coordination against one MySQL instance's `max_connections`.
7. **DG (dangerous goods) handling gap**: only the legacy engine (`eddcartV2.js`/`eddMainV2.js`, via `getCourierDataDG`) has a DG branch; the v2 Control Tower engine has none — a plausible functional regression if DG SKUs are expected to route through `/v2/cartedd`/`/v2/edd` today.
8. **Silent data loss on SLA mismatch**: a SKU/shipment whose weight matches no `ClusterWarehouseMatrix` row is `continue`d past (cartEddV2ControlTower.js:1140-1143; eddMainV2ControlTower.js:958-963) — it simply disappears from the response instead of appearing as an OOS entry or an error the caller can see.
9. **REST-semantics smell**: business-logic 404s (missing pincode/SKU) return as HTTP 500 from the controller catch blocks (EddV2.controller.js:64-71,139-146) — every bad input looks like a server error to monitoring.
10. **No automated tests**: `test/` is empty; `package.json`'s `"test"` script is a literal no-op (`"echo \"No tests specified\" && exit 0"`, package.json:10) — no regression safety net for a pipeline this branchy.
11. **No scaling config**: `app.yaml` is 2 lines (`runtime`, `instance_class`) with no `automatic_scaling`/`resources` block, compounding red flag #6 under traffic spikes.
12. **Weight-default inconsistency**: `ServingEntity.max_shipment_weight` DB column default is 1000g (ServingEntity.js:70) but the application's own fallback-when-unset is 10000g (cartEddV2ControlTower.js:936,1301) — two different effective defaults depending on whether the column is null vs the row missing entirely.
13. **Dead computation on every lat/lng request**: `H3IndexingService.getDeliveryTypes()`/`buildSLAMatrix()` (H3IndexingService.js:654-737) computes a full SLA/delivery-type classification that `resolveLocation()`'s only callers never read (`.clusters` is used, `.slaMatrix` is not) — real CPU/DB work discarded on every hit.
14. **`GET /v2/warehouse-edd` error handling**: on throw it does `res.send(e)` with no status code (EddV2.controller.js:212) — leaks a raw error object to the client with an implicit 200.

---

## 13. Tech stack evidenced in this code

- **Language/runtime**: JavaScript (Node.js ≥22.0.0, package.json:39-41), matches `app.yaml`'s `runtime: nodejs22`.
- **Framework**: Express ^4.18.2.
- **ORM / DB drivers**: Sequelize ^6.37.7 (control-tower models); both `mysql2` ^3.10.0 and legacy `mysql` ^2.18.1 present simultaneously.
- **Datastores**: MySQL (two logical schemas: control-tower's own, and `promiseEngine` for inventory/pincode raw SQL); Redis ^4.7.1 (cache + rate-limit token bucket).
- **Queueing**: BullMQ ^4.18.3 (`control-tower/src/workers/*` — bulk processing, DB insertion, ERP sync, H3 indexing workers).
- **Messaging / Cloud**: Google Cloud Pub/Sub ^5.3.0 (`GCP/inventoryPublisher.js`,`inventorySubscriber.js`), Google Cloud Storage ^7.16.0 (`GCP/Storage.js`).
- **Geospatial**: `h3-js` ^4.2.1 (Uber H3 hexagonal indexing), `@turf/turf` ^7.2.0, `@mapbox/togeojson` ^0.16.2; `kdbush`/`geokdbush` pinned via package.json `overrides`.
- **Security/middleware**: `helmet` ^8.1.0, `cors` ^2.8.5, `express-rate-limit` ^7.5.1, `express-slow-down` ^2.1.0, `express-validator` ^7.0.1, `joi` ^17.11.0, `bcryptjs` ^2.4.3, `jsonwebtoken` ^9.0.2, `nocache` ^4.0.0, `compression` ^1.7.4.
- **File/data processing**: `multer` ^1.4.5-lts.1, `csv-parser` ^3.2.0, `csvtojson` ^2.0.10, `exceljs` ^4.4.0, `xlsx` ^0.18.5, `xml2js`/`xmldom`.
- **Observability**: New Relic ^13.8.1 (APM, loaded first in `server.js:2`), Winston ^3.17.0 + `winston-loggly-bulk` ^3.3.2 (Loggly), Morgan ^1.10.0 (HTTP access log).
- **API docs**: `swagger-jsdoc` ^6.2.8 + `swagger-ui-express` ^5.0.1, served at `/control-tower/api-docs`.
- **Dev tooling**: ESLint ^8.55.0, Prettier ^3.1.0, nodemon ^3.0.2 (all devDependencies).
- **Testing**: none configured — `test/` directory is empty, `npm test` is a no-op (package.json:10).
- **GCP services evidenced**: App Engine Standard (`app.yaml`), Cloud Pub/Sub, Cloud Storage, Cloud Monitoring (named in control-tower's own `docs/tech-stack.md:36`).
- **Third-party integrations evidenced**: AccuWeather (`control-tower/src/services/accuWeatherClient.js`, feeding the rain-buffer subsystem), Telegram (`control-tower/src/utils/telegramService.js`); a Shopify/ERP credentials file (`api`) exists at repo root but no call site was found via static grep in this pass — noted per the security rule, not opened.

---

*Sections prioritized per instructions: §4 (algorithm), §10 (bullets), §11 (interview), §13 (tech stack) received the deepest verification. All other sections are grounded in direct reads of the cited files; nothing here is inferred from filenames alone without a corresponding code or doc citation.*
