
// use of INCR and EXPIRE
const fixed_window_rate_limiter = (redisClient, max_limit = 5) => async (req, res, next) => { 
    const {id} = req.params
    const key = `rate_limit:${id}`;

    const currentCount = await redisClient.incr(key);
    if (currentCount === 1) {
        await redisClient.expire(key, 60);
    }
    if (currentCount > max_limit) {
        return res.status(429).json({ success: false, message: "Too Many Requests" });
    }
    next();
};

// More to go 
// https://chatgpt.com/c/695171f4-9fac-8324-9603-feff1d4d7d10
// Distributed locks
// Idempotency & Deduplication

export {
    fixed_window_rate_limiter
}