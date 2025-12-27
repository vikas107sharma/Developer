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