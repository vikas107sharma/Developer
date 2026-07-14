🧩 Practice Problem — Search Query Engine (Dynamic SQL / Elastic Query Builder)

You’re building a backend API that lets clients perform advanced search on a marketplace.

Frontend sends a flexible search request:

{
  "entity": "products",
  "filters": {
    "price_min": 100,
    "price_max": 5000,
    "brand": ["nike", "adidas"],
    "rating_gte": 4
  },
  "sort": [
    { "field": "popularity", "order": "desc" },
    { "field": "price", "order": "asc" }
  ],
  "include": ["seller", "inventory"],
  "pagination": { "limit": 20, "offset": 0 },
  "search": "running shoes",
  "mode": "elastic"
}

The Output Is NOT Just a String

You must construct a Query Plan Object

QueryPlan
 ├── Data source (SQL / Elastic)
 ├── WHERE conditions
 ├── Full-text search block
 ├── Joins / nested queries
 ├── Aggregations
 ├── Sorting rules
 ├── Pagination
 └── Execution hints


Different modes assemble queries differently.

Axes of Variation (Level-3)
1️⃣ Storage Engine
Mode	Behavior
sql	joins + where clauses
elastic	bool/must/filter queries
cache	precomputed lookup
2️⃣ Entity Type
Entity	Special Rules
products	price + inventory joins
orders	status history
users	permissions filtering
stores	geo-distance queries
3️⃣ Optional Features
Option	Effect
search	full-text clause
filters	where/must filters
include	joins / nested docs
sort	order block
pagination	limit/offset or search_after
aggregations	facets
What You Must Avoid

This kind of code:

if (mode === 'sql') {
   if (entity === 'products') {
      if (filters.price) ...
      if (search) ...
   }
}
else if (mode === 'elastic') {
   if (entity === 'products') {
      if (filters.price) ...
      if (search) ...
   }
}


This explodes as features grow.

What You Need To Build
const queryPlan = QueryDirector.build(request);
const result = await queryExecutor.execute(queryPlan);


Builder must construct step-by-step:

1. choose data source
2. apply entity rules
3. add filters
4. add search
5. add relations
6. add sorting
7. finalize

Example Scenarios
Example 1
Products + SQL + filters
→ SELECT + WHERE + JOIN inventory

Example 2
Products + Elastic + search text
→ bool.must + analyzer + scoring

Example 3
Stores + geo search
→ geo_distance query

Constraints

Query object immutable after build

Invalid combos fail early
(example: JOIN in elastic mode)

Same director builds different engines

Builders define representation

Easy to add new engine later (Mongo, ClickHouse)

Why This Is Level-3

Because construction depends on:

storage_engine × entity × query_features


Same request → completely different assembly process.

This is exactly where Builder pattern is the right abstraction.

If you want, after you design it, I can review and point out the typical mistake:
people accidentally recreate a giant conditional inside the director 😄