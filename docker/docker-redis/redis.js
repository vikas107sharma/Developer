import { createClient } from 'redis';
const max_limit = 5

// 1. Initialize Client (Use the Service Name from your docker-compose)
const redisClient = createClient({
    // Look for REDIS_URL from Docker/Environment, otherwise use localhost
    url: process.env.REDIS_URL || 'redis://localhost:6379' // Use environment variable or fallback to localhost
});

// 2. Connect to Redis
await redisClient.connect().then(()=>{
  console.log("Connected to Redis");
}).catch((err)=>{
  console.error("Failed to connect to Redis:", err);
})

// use of INCR and EXPIRE
const fixed_window_rate_limiter = async (req, res, next) => {
    const {id} = req.params;
    const key = `rate_limit:${id}`;

    const currentCount = await redisClient.incr(key);
    if (currentCount === 1) {
        await redisClient.expire(key, 60); // The expiration time is 60 seconds
    }
    if (currentCount > max_limit) { // Uses the module-scoped max_limit (which is 5)
        return res.status(429).json({ success: false, message: "Too Many Requests" });
    }
    next();
};

// More to go 
// https://chatgpt.com/c/695171f4-9fac-8324-9603-feff1d4d7d10
// Distributed locks
// Idempotency & Deduplication

export {
    redisClient,
    fixed_window_rate_limiter
}