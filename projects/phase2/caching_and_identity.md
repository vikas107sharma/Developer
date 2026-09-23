CACHING & IDENTITY — MyDesignation Backend, Shopify

"A cache that lies is worse than no cache at all — and a login system where two humans can end up sharing one account is a support ticket waiting to happen. Both had to be provably safe, not just usually right."

================================================ Step 1 ================================================

The 60-second version

"There are two systems here, and they share one rule: never trust a shortcut you can't verify. The cache sits in front of every Shopify read, and the rule is that it's an optimization, never a dependency — every call is wrapped so a Redis failure just falls through to calling Shopify directly. The identity system is passwordless — phone OTP, email OTP, Google, Apple — and the rule there is one verified identifier belongs to exactly one account, enforced by a database constraint, not by application code checking first and writing second.

Both rules exist because I broke them once, in a smaller way, and had to fix the underlying seam instead of the one call site. The cache one turned into a real outage — a size-chart endpoint told customers 'no chart available' for a product that had one, for close to an hour, because a transient failure got cached as if it were a real answer."

================================================ Step 2 ================================================

They ask: "How does the cache actually stay safe under a Redis outage?"

"Every cache call is wrapped in the same helper, and the client itself is tuned to fail fast — short connect and command timeouts — because a Redis connection that hangs is worse than one that's simply down. If a read fails for any reason, it calls the loader directly and returns real data late instead of returning nothing. The trade-off is honest: during an outage every request now pays Shopify's full latency, and the stampede lock itself needs Redis to work, so there's no crowd protection either. But correctness never depends on Redis being up — only speed does."

================================================ Step 3 ================================================

They ask: "What actually stops a thundering herd when a hot key expires?"

"Two layers, at two different scopes. Inside one container, concurrent requests that miss on the same key share a single in-flight promise — the second, third, and hundredth caller all just wait on the first one's result instead of each calling Shopify separately. Across containers, where in-process coalescing can't reach, I use a short `SET NX` lock in Redis — one container wins the lock and runs the loader, the rest poll briefly for its result instead of all hitting Shopify at once. Neither layer is sufficient alone: in-process only helps within a container, and the distributed lock alone would still let every container's first request through at the same instant."

================================================ Step 4 ================================================

They ask: "How do you invalidate a cache key family without deleting keys one at a time?"

"I don't track individual keys at all — each family has a version counter, and the cache key is built from that version. One write bumps the counter, and every key built from the old version is instantly orphaned without anything being deleted. For the bulk sweeps — a catalog webhook invalidating a whole product family — I use a cursor-based `SCAN` plus `UNLINK` instead of `KEYS` plus `DEL`. `KEYS` blocks the whole Redis instance while it walks the keyspace, which on a shared instance would stall every cart, session, and OTP read at the same moment. `SCAN` walks incrementally and `UNLINK` frees memory off the main thread, so a catalog purge never becomes a latency spike for everything else sharing that Redis."

================================================ Step 5 ================================================

They ask: "If it's TTL-based, how do you keep it from just being stale most of the time?"

"The TTL is the fallback, not the mechanism. Freshness is actually driven by Shopify's own webhooks — a product update, a collection change, fires a webhook that busts the relevant version counter immediately, so most reads are fresh within seconds of the change, not within the TTL window. The TTL only matters when a webhook delivery itself gets lost or delayed — it's the safety net underneath the real invalidation path, not the thing doing the work day to day. That's also why the TTLs are tiered by how much a stale answer would actually cost: search and suggest sit at two minutes because staleness there is just an annoying result, while size charts sit at an hour because a chart barely ever changes and a webhook will bust it the moment it does."

Stampede guard, in one picture:
```
   5 concurrent misses on the same expired key, one container
        req1  req2  req3  req4  req5
          \    |     |     |    /
           \   |     |     |   /
            \  |     |     |  /
             in-process promise cache
                     |
              (only req1 actually calls the loader,
               req2..req5 await the same promise)
                     |
              writes result to Redis
   ---------------------------------------------------
   same key, expired, but now across containers
   container A            container B, C, D...
        |                        |
   SET NX lock:OK           SET NX lock: fails
        |                        |
   runs loader,              polls briefly,
   writes to Redis           then reads A's result
```

================================================ Step 6 ================================================

⭐ The bug you SHOULD volunteer — the null-caching outage

"A size-chart endpoint returned 'no chart available' for a product that definitely had one, silently, for almost an hour. What actually happened: the upstream gateway hit a transient failure and collapsed it to `null` instead of throwing. My cache helper didn't know the difference — a loader that returns `null` looks exactly like a loader that successfully found nothing, so it cached that `null` for the full TTL and every request for an hour got the wrong answer with total confidence.

The bug wasn't the null itself, it was that null meant two different things at the same seam — 'genuinely nothing here' and 'I failed to find out' — and nothing forced them apart. The fix was structural, not a patch at the call site: the shared cache helper itself now refuses to write a null or undefined loader result to Redis, for every caller, by construction. I'll also be honest about the other half of that rule — negative caching is supposed to use an explicit sentinel value when you do want to cache 'confirmed nothing,' but as of today there's no live call site actually using that sentinel. The guarantee that matters — never silently cache a failure — is real and enforced everywhere. The sentinel convention exists on paper with no example yet, and that's a fair thing to say plainly if asked."

================================================ Step 7 ================================================

The ⭐ strongest card — one identifier, one account, enforced by the database

"Login is passwordless across four providers — phone OTP, email OTP, Google, Apple — and the hardest question isn't issuing a token, it's what happens when a Google sign-in's email matches an account that a phone OTP already created. My rule is never merge, ever. A verified identifier — a phone number or an email — belongs to exactly one account, and that's a database unique constraint, not a check-then-write in application code. The difference matters under concurrency: if I read 'is this identifier taken' and then wrote the attachment as two separate steps, two simultaneous logins could both read 'no' and both attach, and now the constraint model itself is broken. Because it's one unique constraint, the second attach doesn't get a chance to race — it just fails at the database, atomically, and I turn that failure into 'this identifier already belongs to someone else, block it' with no window where both could succeed."

Then give one concrete example:
"Google's People API can hand me a phone number it scraped off someone's profile — I never treat that as proof they own it, only as a hint. So there's one deliberate exception to 'never merge': if a real phone OTP later proves ownership of that same number, it can reclaim it from the Google-sourced account. Otherwise a phone number that gets recycled to a new owner would permanently lock the real person out because a stranger's old Google profile still claims it."

================================================ Step 8 ================================================

They ask: "What happens when a refresh token gets used twice?"

"Refresh tokens are grouped into families, and each one rotates on every use — the token you just used stops being valid and a new one is issued. If a token that's already been consumed ever gets replayed, that's not a race condition, that's a sign it leaked to someone else, because the legitimate client already moved on to the next token in the chain. So a replay doesn't just reject that one token — it revokes the entire family. That's the difference between 'this specific token is bad' and 'this session's whole lineage might be compromised,' and I treat a replay as evidence of the second, worse case."

================================================ Step 9 ================================================

They ask: "Where do you deliberately fail open, and where do you fail closed?"

"By blast radius, not by uniform policy. Rate limiting and the OTP resend cooldown fail open — if Redis is down, I'd rather let a login attempt through uncapped for a few minutes than lock every real customer out of signing in during an infrastructure blip. Both are defense-in-depth on top of other limits anyway — the OTP itself expires in ten minutes and is single-use regardless. Webhook signature checks fail closed, hard — if the Razorpay webhook secret is ever unset, the endpoint returns 503 and refuses every request rather than silently accepting unsigned payloads, because accepting an unverified payment event is a direct path to fabricating an order. Same logic for the admin cache-purge endpoint's token. The split isn't inconsistency, it's asking 'what's the actual cost of being wrong here' for each control separately."

================================================ Step 10 ================================================

Cut these from your interview story:

❌ "The cache guarantees consistency with Shopify."
Why it's weak: it's a TTL-based cache with webhook-driven invalidation as a best-effort freshness signal — that's "usually fresh, safety-netted by an upper bound," not a consistency guarantee.

❌ "We prevent account takeover by never letting two providers share an identifier."
Why it's weak: overstates it — there's one deliberate, audited exception (OTP reclaiming a Google-sourced phone number), and glossing over it invites a follow-up that catches you contradicting yourself.

❌ "Negative caching with a sentinel stops us from re-hitting a dead upstream."
Why it's weak: the sentinel convention is documented but has no live call site today — claiming it's in active use won't survive "show me where."

================================================ Step 11 ================================================

Numbers you must know

- Cache TTLs: catalog reads 900s; near-static content 1800s; size chart 3600s; search/suggest 120s; app config 60s; customer/reviews 300s; wishlist 120s; OTP resend cooldown 30s
- OTP verify-attempt cap: 5 wrong guesses invalidates the code; OTP expiry: 10 minutes
- Access token TTL: 900s (15 minutes); refresh token TTL: 15,552,000s (180 days)
- Identity model: unique constraint enforced at the database, zero merge paths except the one audited OTP-reclaim exception
- [NEED FROM ME]: "How many rows are in verified_identifiers today, and how many refresh-token-family revocations have actually fired in production?"
- [NEED FROM ME]: "Do we have a real Redis cache-hit-ratio sample from production, instead of the qualitative 'read performance stayed flat' claim?"
