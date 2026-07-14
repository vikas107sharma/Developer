/**
 * =========================================================
 * ARRAY ITERATION — Production Priority Order
 * =========================================================
 */

const fruits = ['apple', 'banana', 'cherry'];


/**
 * 🥇 1️⃣ for...of  (DEFAULT in backend systems)
 * Best balance of readability + performance.
 * Safe with async/await.
 */
for (const fruit of fruits) {
  console.log('for...of:', fruit);
}


/**
 * 🥈 2️⃣ Classic for loop  (Performance / Control heavy logic)
 * Fastest and gives full control (break, continue, reverse, batching).
 */
for (let i = 0; i < fruits.length; i++) {
  console.log('classic for:', i, fruits[i]);
}


/**
 * 🥉 3️⃣ for...of with .entries()
 * Clean way to get index + value.
 */
for (const [index, fruit] of fruits.entries()) {
  console.log('entries():', index, fruit);
}


/**
 * 🟡 4️⃣ forEach (Least preferred in backend)
 * Callback overhead.
 * Cannot break/continue.
 * Avoid with async (common bug).
 */
fruits.forEach((fruit, index) => {
  console.log('forEach:', index, fruit);
});



/**
 * =========================================================
 * OBJECT ITERATION — Production Priority Order
 * =========================================================
 */

const students = {
  id_A: 'Alice',
  id_B: 'Bob',
  id_C: 'Charlie'
};


/**
 * 🥇 1️⃣ Object.entries()  (Most used in backend)
 * Clean and explicit key-value iteration.
 */
for (const [key, value] of Object.entries(students)) {
  console.log('entries():', key, value);
}


/**
 * 🥈 2️⃣ Object.keys()
 * When only keys are needed.
 */
for (const key of Object.keys(students)) {
  console.log('keys():', key);
}


/**
 * 🥉 3️⃣ Object.values()
 * When only values are needed.
 */
for (const value of Object.values(students)) {
  console.log('values():', value);
}


/**
 * 🔴 4️⃣ for...in (Avoid in production unless necessary)
 * Iterates prototype chain.
 * Must guard with Object.hasOwn().
 */
for (const key in students) {
  if (Object.hasOwn(students, key)) {
    console.log('for...in:', key, students[key]);
  }
}


/**
 * =========================================================
 * FINAL PRODUCTION SUMMARY
 * =========================================================
 *
 * ARRAYS:
 *   1. for...of              (default choice)
 *   2. classic for           (performance/control)
 *   3. for...of entries()
 *   4. forEach               (least preferred)
 *
 * OBJECTS:
 *   1. Object.entries()
 *   2. Object.keys()
 *   3. Object.values()
 *   4. for...in              (avoid if possible)
 *
 */



/*
ARRAY ITERATION METHODS (Production Priority Order)

1) map
2) filter
3) find
4) some / every
5) reduce
6) forEach
*/

const users = [
  { id: 1, name: "A", age: 22, active: true },
  { id: 2, name: "B", age: 17, active: false },
  { id: 3, name: "C", age: 30, active: true }
];

const numbers = [10, 20, 30, 40];


/* =========================================================
1️⃣ map() – Transform (most common)
- Returns new array
- Same length
- Pure transformation
- O(n)
========================================================= */

const userNames = users.map(user => user.name);
console.log("map:", userNames);


/* =========================================================
2️⃣ filter() – Select subset
- Returns new array
- Length <= original
- O(n)
========================================================= */

const adults = users.filter(user => user.age >= 18);
console.log("filter:", adults);


/* =========================================================
3️⃣ find() – First match
- Returns single element or undefined
- Stops early (better than filter()[0])
- O(n) worst case
========================================================= */

const firstInactive = users.find(user => !user.active);
console.log("find:", firstInactive);


/* =========================================================
4️⃣ some() / every() – Boolean checks
- Return true/false
- Short-circuit early
- O(n) worst case
========================================================= */

// Any inactive?
const hasInactive = users.some(user => !user.active);
console.log("some:", hasInactive);

// All adults?
const allAdults = users.every(user => user.age >= 18);
console.log("every:", allAdults);


/* =========================================================
5️⃣ reduce() – Accumulator / Aggregation
- Most powerful
- Can replace map, filter, etc.
- O(n)
========================================================= */

// Sum numbers
const total = numbers.reduce((acc, curr) => acc + curr, 0);
console.log("reduce sum:", total);

// Group users by active
const grouped = users.reduce((acc, user) => {
  const key = user.active ? "active" : "inactive";
  if (!acc[key]) acc[key] = [];
  acc[key].push(user);
  return acc;
}, {});
console.log("reduce group:", grouped);


/* =========================================================
6️⃣ forEach() – Side effects only
- Returns undefined
- Cannot break/return early
- Use for logging, DB calls, mutations
- O(n)
========================================================= */

users.forEach(user => {
  console.log("forEach:", user.name);
});


/*
⚠ Performance Notes (Important in backend systems):

- All are O(n)
- find/some/every short-circuit → better for large arrays
- reduce is most flexible but can reduce readability
- forEach cannot break → prefer for..of if early exit needed
- Never run async/await inside map without Promise.all
*/