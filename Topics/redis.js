/**
 * Redis Demo – Production-used data types, methods & patterns
 * Based on Redis official documentation concepts
 */

import { createClient } from "redis";

const client = createClient();
client.on("error", (err) => console.error("Redis Client Error", err));

await client.connect();

/* ======================================================
   STRING
   One-liner: Strings store simple key-value data like cache, counters, tokens.
   Production methods: SET, GET, INCR, EXPIRE
====================================================== */

await client.set("user:name", "Vikas");
console.log("STRING GET:", await client.get("user:name"));

await client.incr("page:views");
console.log("STRING INCR:", await client.get("page:views"));

await client.set("temp:key", "will-expire");
await client.expire("temp:key", 5);


/* ======================================================
   LIST
   One-liner: Lists are ordered collections used for queues and background jobs.
   Production methods: LPUSH, RPUSH, LPOP, RPOP, LRANGE
====================================================== */

await client.lPush("job:queue", "job1");
await client.rPush("job:queue", "job2");

console.log("LIST LRANGE:", await client.lRange("job:queue", 0, -1));
console.log("LIST LPOP:", await client.lPop("job:queue"));


/* ======================================================
   SET
   One-liner: Sets store unique values and are used for tags, likes, permissions.
   Production methods: SADD, SREM, SMEMBERS, SISMEMBER
====================================================== */

await client.sAdd("post:likes", "user1", "user2");
console.log("SET MEMBERS:", await client.sMembers("post:likes"));
console.log("SET SISMEMBER:", await client.sIsMember("post:likes", "user1"));


/* ======================================================
   HASH (HSET)
   One-liner: Hashes store structured objects like user profiles.
   Production methods: HSET, HGET, HGETALL, HDEL
====================================================== */

await client.hSet("user:1", {
  name: "Vikas",
  role: "Developer",
});

console.log("HASH HGET:", await client.hGet("user:1", "name"));
console.log("HASH HGETALL:", await client.hGetAll("user:1"));


/* ======================================================
   REDIS STREAMS
   One-liner: Streams are append-only logs used for event sourcing and async processing.
   Production methods: XADD, XRANGE, XREAD
====================================================== */

await client.xAdd("orders:stream", "*", {
  orderId: "101",
  status: "created",
});

console.log(
  "STREAM XRANGE:",
  await client.xRange("orders:stream", "-", "+")
);


/* ======================================================
   PUB / SUB
   One-liner: Pub/Sub enables real-time messaging between services.
   Production methods: PUBLISH, SUBSCRIBE
====================================================== */

const subscriber = client.duplicate();
await subscriber.connect();

await subscriber.subscribe("notifications", (message) => {
  console.log("PUB/SUB MESSAGE:", message);
});

await client.publish("notifications", "Hello from Redis Pub/Sub");


/* ======================================================
   1️⃣ RATE LIMITING
   One-liner: Rate limiting restricts how many requests a user can make in a time window.
   Core commands: INCR, EXPIRE, TTL
====================================================== */

async function rateLimiter(userId, limit, windowSec) {
  const key = `rate:${userId}`;
  const count = await client.incr(key);

  if (count === 1) await client.expire(key, windowSec);

  if (count > limit) {
    return { allowed: false, remaining: 0 };
  }

  return {
    allowed: true,
    remaining: limit - count,
    resetIn: await client.ttl(key),
  };
}

console.log("RATE LIMIT:", await rateLimiter("user1", 3, 10));
console.log("RATE LIMIT:", await rateLimiter("user1", 3, 10));
console.log("RATE LIMIT:", await rateLimiter("user1", 3, 10));
console.log("RATE LIMIT:", await rateLimiter("user1", 3, 10));


/* ======================================================
   2️⃣ DISTRIBUTED LOCK
   One-liner: Distributed lock ensures only one process executes a critical section.
   Core commands: SET NX PX, DEL
====================================================== */

async function acquireLock(lockKey, lockId, ttlMs) {
  return await client.set(lockKey, lockId, { NX: true, PX: ttlMs });
}

async function releaseLock(lockKey, lockId) {
  const value = await client.get(lockKey);
  if (value === lockId) {
    await client.del(lockKey);
    return true;
  }
  return false;
}

const lockKey = "lock:payment";
const lockId = "server-1";

const locked = await acquireLock(lockKey, lockId, 5000);
console.log("LOCK ACQUIRED:", locked);

if (locked) {
  console.log("Critical section running...");
  await releaseLock(lockKey, lockId);
  console.log("LOCK RELEASED");
}


/* ======================================================
   3️⃣ CACHE-ASIDE PATTERN
   One-liner: Cache-aside loads data into cache only on cache miss.
   Core commands: GET, SET, EXPIRE
====================================================== */

async function getUserFromDB(userId) {
  return { id: userId, name: "Vikas", role: "Developer" };
}

async function getUser(userId) {
  const cacheKey = `user:${userId}`;

  const cached = await client.get(cacheKey);
  if (cached) {
    console.log("CACHE HIT");
    return JSON.parse(cached);
  }

  console.log("CACHE MISS");
  const user = await getUserFromDB(userId);

  await client.set(cacheKey, JSON.stringify(user), { EX: 30 });
  return user;
}

console.log("USER:", await getUser(1));
console.log("USER:", await getUser(1));


/* ======================================================
   CLEANUP & EXIT
====================================================== */

setTimeout(async () => {
  await subscriber.unsubscribe("notifications");
  await subscriber.quit();
  await client.quit();
  console.log("Redis full demo finished");
}, 2000);
