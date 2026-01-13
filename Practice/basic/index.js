/**
 * JavaScript Array Methods Examples
 *
 * This file demonstrates common and advanced use cases for
 * .map(), .filter(), and .reduce() on data arrays.
 *
 * Each example is wrapped in a separate function to prevent
 * variable scope conflicts (e.g., 'orders' being declared multiple times).
 * The core logic in each example is preserved exactly as provided.
 */

console.log("--- Running Array Method Examples ---");

// -----------------------------------------------------------------
// Example 1: Formatting with .map()
// -----------------------------------------------------------------
function example1_FormatOrders() {
  // 5. Format order records fetched from MongoDB/Postgres.
  // DB result
  const orders = [
    { id: 1, amount: 1200, createdAt: "2025-11-15T12:00:00Z" },
    { id: 2, amount: 900,  createdAt: "2025-11-16T14:30:00Z" }
  ];

  // API formatting using map
  const formatted = orders.map(o => ({
    orderId: o.id,
    amount: o.amount,
    date: new Date(o.createdAt).toLocaleDateString()
  }));

  console.log(formatted);
  /*
  [
    { orderId: 1, amount: 1200, date: "11/15/2025" },
    { orderId: 2, amount: 900,  date: "11/16/2025" }
  ]
  */
}


// -----------------------------------------------------------------
// Example 2: Searching with .filter()
// -----------------------------------------------------------------
function example2_FilterOrders() {
  // 6. Search orders with status = DELIVERED and amount > 1000
  const orders = [
    { id: 1, status: 'DELIVERED', amount: 1200 },
    { id: 2, status: 'PENDING', amount: 900 },
    { id: 3, status: 'DELIVERED', amount: 800 },
  ];

  const filtered = orders.filter(o =>
    o.status === 'DELIVERED' && o.amount > 1000
  );

  console.log(filtered);
  // [ { id: 1, status: "DELIVERED", amount: 1200 } ]
}


// -----------------------------------------------------------------
// Example 3: Grouping with .reduce()
// -----------------------------------------------------------------
function example3_GroupShipments() {
  // 7. Group shipments by status
  const shipments = [
    { id: 1, status: "DELIVERED" },
    { id: 2, status: "DELAYED" },
    { id: 3, status: "DELIVERED" },
    { id: 4, status: "PENDING" }
  ];

  const grouped = shipments.reduce((acc, s) => {
      // NOTE: The original code `push(s.id)` would produce:
      // { DELIVERED: [1, 3], DELAYED: [2], PENDING: [4] }
      // The original output comment below seems to expect `push(s)`.
      // The code is preserved exactly as requested.
      
      if (!acc[s.status]) {
          acc[s.status] = []; // Create an empty array if this status is new
      }
      acc[s.status].push(s.id);
      return acc; // Added return acc to make reduce work correctly
  }, {});

  console.log(grouped);
  /*
  {
    DELIVERED: [ {id:1}, {id:3} ],
    DELAYED:   [ {id:2} ],
    PENDING:   [ {id:4} ]
  }
  */
  // Note: Actual output from the code as-written will be:
  // { DELIVERED: [ 1, 3 ], DELAYED: [ 2 ], PENDING: [ 4 ] }
}


// -----------------------------------------------------------------
// Example 4: Chained Pipeline (Filter > Map > Reduce)
// -----------------------------------------------------------------
function example4_ChainedPipeline() {
  // 🔥 5. Map + Filter + Reduce in real pipelines
  // Use case: Calculate total RUNNING DELAYED shipments with message summary.
  const shipments = [
    { sku: "A1", status: "ON TIME", dayCount: 1 },
    { sku: "B1", status: "RUNNING DELAYED", dayCount: 3 },
    { sku: "C1", status: "RUNNING DELAYED", dayCount: 2 },
  ];

  const result = shipments
    .filter(s => s.status === "RUNNING DELAYED")
    .map(s => ({ ...s, message: `Delayed by ${s.dayCount} days` }))
    .reduce((acc, s) => {
      acc.count++;
      acc.messages.push(s.message);
      return acc;
    }, { count: 0, messages: [] });

  console.log(result);
  /*
  {
    count: 2,
    messages: [
      "Delayed by 3 days",
      "Delayed by 2 days"
    ]
  }
  */
}


// -----------------------------------------------------------------
// Example 5: Get Latest Record per Item with .reduce()
// -----------------------------------------------------------------
function example5_GetLatestWithReduce() {
  // 🔥 6. Selecting latest records using reduce (very useful)
  // Use case: Pick latest EDD update per SKU
  const eddUpdates = [
    { sku: "A1", edd: "2025-01-05", updatedAt: 10 },
    { sku: "A1", edd: "2025-01-07", updatedAt: 20 }, // latest
    { sku: "B1", edd: "2025-02-02", updatedAt: 5 }
  ];

  const latest = eddUpdates.reduce((acc, rec) => {
    const curr = acc[rec.sku];
    if (!curr || rec.updatedAt > curr.updatedAt) {
      acc[rec.sku] = rec;   // keep the latest
    }
    return acc;
  }, {});

  console.log(latest);
  /*
  {
    A1: { sku: "A1", edd: "2025-01-07", updatedAt: 20 },
    B1: { sku: "B1", edd: "2025-02-02", updatedAt: 5 }
  }
  */
}


// --- Execute all examples ---
function runAll() {
  console.log("--- Example 1: Formatting with .map() ---");
  example1_FormatOrders();
  
  console.log("\n--- Example 2: Searching with .filter() ---");
  example2_FilterOrders();
  
  console.log("\n--- Example 3: Grouping with .reduce() ---");
  example3_GroupShipments();
  
  console.log("\n--- Example 4: Chained Pipeline (Filter > Map > Reduce) ---");
  example4_ChainedPipeline();
  
  console.log("\n--- Example 5: Get Latest Record per Item with .reduce() ---");
  example5_GetLatestWithReduce();
}

// Run all examples
runAll();

/**
 * ==========================================
 * NODE.JS INTERVIEW CODING PRACTICE (25 Qs)
 * ==========================================
 * Each question:
 * - Has a clear real-world use case
 * - Requires YOU to write code
 * - Mirrors real backend interview problems
 */

/* =====================================================
 * Q1. Async Map with Concurrency Limit
 * =====================================================
 * Problem:
 * You are given an array of userIds.
 * Fetch user details using an async function.
 *
 * Constraints:
 * - Only `limit` async calls can run at a time
 * - Order of results must be preserved
 *
 * Common use case:
 * External API calls, DB queries, webhooks
 */
async function fetchUsersWithLimit(userIds, limit = 3) {
  // TODO
}

/* =====================================================
 * Q2. Async Error Wrapper (Express)
 * =====================================================
 * Problem:
 * Express does NOT catch async errors automatically.
 *
 * Task:
 * Write a higher-order function that wraps async routes
 * and forwards errors to next(err)
 *
 * Common use case:
 * Centralized error handling
 */
const asyncHandler = (fn) => {
  // TODO
};

/* =====================================================
 * Q3. Group Orders with Reduce
 * =====================================================
 * Problem:
 * Group orders by status and compute:
 * - count
 * - total amount
 *
 * Use case:
 * Dashboard analytics / reporting APIs
 */
function groupOrders(orders) {
  // TODO
}

/* =====================================================
 * Q4. Retry with Exponential Backoff
 * =====================================================
 * Problem:
 * Retry an async function on failure.
 *
 * Rules:
 * - Max retries
 * - Delay doubles on every retry
 *
 * Use case:
 * Payment APIs, third-party services
 */
async function retry(fn, retries = 3, delay = 100) {
  // TODO
}

/* =====================================================
 * Q5. Authentication Middleware
 * =====================================================
 * Problem:
 * Read Authorization header
 * Validate Bearer token
 * Attach decoded user to req
 *
 * Use case:
 * Protected APIs
 */
function authMiddleware(req, res, next) {
  // TODO
}

/* =====================================================
 * Q6. Deduplicate Records
 * =====================================================
 * Problem:
 * Remove duplicates by `orderId`
 * Keep the record with latest `updatedAt`
 *
 * Use case:
 * Sync jobs, webhook data
 */
function deduplicateOrders(orders) {
  // TODO
}

/* =====================================================
 * Q7. Cursor-Based Pagination
 * =====================================================
 * Problem:
 * Implement pagination using a cursor instead of offset.
 *
 * Output:
 * - data
 * - nextCursor
 *
 * Use case:
 * Large datasets, infinite scroll
 */
function paginate(data, cursor = null, limit = 5) {
  // TODO
}

/* =====================================================
 * Q8. Timeout Wrapper
 * =====================================================
 * Problem:
 * Wrap an async function and reject
 * if it takes longer than given time.
 *
 * Use case:
 * Prevent hanging API calls
 */
function withTimeout(fn, ms) {
  // TODO
}

/* =====================================================
 * Q9. Middleware Execution Tracker
 * =====================================================
 * Problem:
 * Track order of middleware execution.
 *
 * Use case:
 * Debugging complex middleware chains
 */
function middlewareTracker(name, log) {
  return (req, res, next) => {
    // TODO
  };
}

/* =====================================================
 * Q10. Flatten Nested API Response
 * =====================================================
 * Problem:
 * Convert nested order → item structure
 * into a flat array of records.
 *
 * Use case:
 * Reporting / exports
 */
function flattenOrders(orders) {
  // TODO
}

/* =====================================================
 * Q11. Fix N+1 Query Problem
 * =====================================================
 * Problem:
 * Fetch users and their orders efficiently.
 * Avoid per-user DB/API calls.
 *
 * Use case:
 * Performance optimization
 */
async function getUsersWithOrders(users, fetchOrders) {
  // TODO
}

/* =====================================================
 * Q12. In-Memory Rate Limiter
 * =====================================================
 * Problem:
 * Allow only N requests per IP per minute.
 *
 * Use case:
 * Prevent abuse, DDoS protection
 */
function rateLimiter(req, res, next) {
  // TODO
}

/* =====================================================
 * Q13. Debounce Async Function
 * =====================================================
 * Problem:
 * Delay execution until calls stop.
 *
 * Use case:
 * Search APIs, user typing events
 */
function debounce(fn, delay) {
  // TODO
}

/* =====================================================
 * Q14. Throttle Function
 * =====================================================
 * Problem:
 * Allow function execution only once
 * in a fixed time window.
 *
 * Use case:
 * Webhooks, rate-controlled APIs
 */
function throttle(fn, limit) {
  // TODO
}

/* =====================================================
 * Q15. Deep Clone Object
 * =====================================================
 * Problem:
 * Create a deep clone without JSON.stringify
 *
 * Use case:
 * Immutable state handling
 */
function deepClone(obj) {
  // TODO
}

/* =====================================================
 * Q16. Request Body Validation Middleware
 * =====================================================
 * Problem:
 * Validate required fields in req.body
 *
 * Use case:
 * Input validation
 */
function validateBody(requiredFields) {
  return (req, res, next) => {
    // TODO
  };
}

/* =====================================================
 * Q17. Build Query Object Dynamically
 * =====================================================
 * Problem:
 * Remove undefined/null filters
 * Build clean query object
 *
 * Use case:
 * Search & filter APIs
 */
function buildQuery(filters) {
  // TODO
}

/* =====================================================
 * Q18. Sequential Async Processing
 * =====================================================
 * Problem:
 * Execute async tasks one after another.
 *
 * Use case:
 * Ordered processing
 */
async function processSequentially(tasks) {
  // TODO
}

/* =====================================================
 * Q19. Parallel Processing with Error Capture
 * =====================================================
 * Problem:
 * Run async tasks in parallel.
 * Collect both results and errors.
 *
 * Use case:
 * Bulk operations
 */
async function runParallel(tasks) {
  // TODO
}

/* =====================================================
 * Q20. Graceful Shutdown
 * =====================================================
 * Problem:
 * Close server and DB connections safely
 * on SIGTERM / SIGINT
 *
 * Use case:
 * Production readiness
 */
function setupGracefulShutdown(server, db) {
  // TODO
}

/* =====================================================
 * Q21. Transform API Response
 * =====================================================
 * Problem:
 * Rename fields and restructure response.
 *
 * Use case:
 * API versioning
 */
function transformOrders(orders) {
  // TODO
}

/* =====================================================
 * Q22. Latest Record per Key
 * =====================================================
 * Problem:
 * From list of records, keep only
 * the latest per given key.
 *
 * Use case:
 * Event streams, updates
 */
function getLatestByKey(records, key) {
  // TODO
}

/* =====================================================
 * Q23. Validate JWT Format
 * =====================================================
 * Problem:
 * Validate JWT structure without libraries.
 *
 * Use case:
 * Early request rejection
 */
function isValidJWT(token) {
  // TODO
}

/* =====================================================
 * Q24. In-Memory Cache with TTL
 * =====================================================
 * Problem:
 * Implement cache with expiry time.
 *
 * Use case:
 * Performance optimization
 */
function createCache(ttlMs) {
  // TODO
}

/* =====================================================
 * Q25. Request Logger Middleware
 * =====================================================
 * Problem:
 * Log method, URL, response time.
 *
 * Use case:
 * Observability & debugging
 */
function requestLogger(req, res, next) {
  // TODO
}


/* =====================================================
 * Q25. Write a file server.js and controller.js with sinple api apply middleware of auth
 * =====================================================
 * Problem:
 * const express = require('express');
    const router = express.Router();

    router.get('/', (req,res)=>{
        res.status(200).json({message: "success"});
    })

    module.exports = router;
 *
 * const express = require('express')
    const test_router = require('./controller');
    
    const app = express();
    
    app.get("/", (req, res)=>{
        res.status(200).json({message: "success"});
    })
    
    app.use('/test', test_router);
    
    
    app.listen(8000, ()=>{
        console.log('Server is running on 8000');
    })
 */