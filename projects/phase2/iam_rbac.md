CENTRALIZED IAM & RBAC — DMS + CDMS Estates, Ripplr

"It's not an auth microservice. It's a passthrough — nine login systems that had already drifted apart agree on one truth without a single one of them being rewritten."

================================================ Step 1 ================================================

The 30-second skeleton

"We had nine separate auth implementations across two estates — DMS and CDMS — all HS256, all quietly sharing one hardcoded secret under five different env-var names. Authorization was enforced in three different places: Django permissions in DMS, group-name string matching in CDMS, and about a thousand hardcoded gating checks scattered across two frontends. On top of that, the user-sync between the two estates matched people on their mobile number — a field that can change.

I designed and built a centralized identity, groups and permissions service for around ten thousand employees. The constraint that shaped everything was that I couldn't touch either estate's user IDs — too many foreign keys depend on them. So the design is additive: it sits in the login path only, mints each estate's own token shape with that estate's own secret, and every unmodified verifier downstream just accepts it. Authorization at request time comes down to one Redis set-membership check. That's it — no database join, no call back to IAM."

================================================ Step 2 ================================================

The interviewer asks: "How does the architecture actually work?"

```
 User logs in ──► IAM (own MySQL: 12 tables)
                    │  verify credential, resolve groups, build claims
                    ▼
        mint 3 audience-specific tokens, each signed with
        THAT estate's existing secret
      ┌───────────────┼────────────────────┐
      ▼               ▼                    ▼
   aud=dms         aud=cdms          aud=cdms_collections
  (DJANGO_SECRET) (CDMS JWT_KEY)      (CDMS JWT_SECRET,
                                       user_id=Salesmen.id)
      │               │                    │
      ▼               ▼                    ▼
  DMS verifier    CDMS verifier      Collections verifier
  (unmodified)    (unmodified)         (unmodified)
      │               │                    │
      ▼               ▼                    ▼
  SISMEMBER on   SISMEMBER on         SISMEMBER on
  DMS's own      CDMS's own           CDMS's own
  Redis catalog  Redis catalog        Redis catalog
```

"The trick is that both estates already speak the same auth dialect — same claim shape, same pbkdf2 hash format, same 'read groups off the token' logic on the frontend. That's what makes a passthrough possible instead of a rewrite. I add claims, I never remove or change existing ones, so today's verifiers ignore what they don't recognize and accept the token unmodified. That's what let me ship IAM before touching a single line of estate code."

================================================ Step 3 ================================================

The ⭐ strongest card — why permissions are NOT in the token

They ask: "Why not just put the permission list in the JWT? Isn't that simpler?"

"I actually went the other way deliberately. A System Admin in DMS has around a hundred and forty permission codenames. Base64-encode that into a JWT and you're at roughly 7.6 kilobytes — and nginx's large_client_header_buffers is 8 kilobytes by default. One admin logging in could blow past the header limit for their own request.

The second reason is worse: if permissions live inside the token, revoking one means waiting for the token to expire — up to a day. That's not a security model, that's a delay.

So the token only carries group IDs and a catalog version number — about 210 bytes. The actual permission check happens against Redis at request time: one SISMEMBER against a group-keyed set, unioned with a tiny handful of per-user exceptions that do ride in the token. Revocation becomes 'update Redis,' not 'wait for a token to expire.'"

================================================ Step 4 ================================================

They ask: "Why key the Redis catalog by group instead of by user?"

"Because of the math. Ten thousand employees all resolve down into about thirty groups. If I cache per-user, then every grant change means invalidating potentially thousands of user-keyed entries. If I cache per-group, a grant change rewrites maybe thirty sets — once — regardless of how many people are in them. And grants only change roughly weekly, so I'm optimizing for correctness and freshness over throughput, not the other way around.

The user-to-group mapping itself never lives in the estate at all — it's resolved once, at login, and travels in the token. The estate's Redis only ever needs to answer 'does group 12 have this permission,' never 'does this specific person.'"

================================================ Step 5 ================================================

They ask: "How do you guarantee a reader never sees a half-written catalog mid-update?"

```
iam:catalog:dms:v          STRING  48   ← the pointer, flipped LAST
iam:catalog:dms:48:g:12    SET     {distribution.view_collection, ...}
iam:catalog:dms:47:g:12    SET     {...}   ← kept for a grace period
```

"Every version writes to a brand-new key prefix. Only after every group's set for that version is written do I flip the pointer key to the new version number. A reader always does the same two-step round trip — read the pointer, then SISMEMBER against whatever version it points to — so it either sees the complete old catalog or the complete new one, never something half-written. I keep the previous version's keys around for a grace period specifically so an in-flight reader that already grabbed the old pointer doesn't get a 404 mid-request."

================================================ Step 6 ================================================

They ask: "What happens when IAM itself is down?"

"Only new logins and token refreshes stop. Anyone already holding a valid token keeps working — because the check they hit on every request is against the estate's own Redis, which IAM doesn't sit in front of.

But I had to be precise about three separate failure shapes, because conflating them is exactly how you turn an outage into a security hole:
- the version pointer key is missing entirely → that's unavailable, fail closed, return 503. Never treat 'I can't tell' as 'no permissions.'
- Redis itself is unreachable → serve from the process's last-known-good in-memory copy and alert. Never fail open.
- a group ID in someone's token has no matching set → deny that group's permissions and alert. Never treat an unknown group as unrestricted.

The failure mode that actually matters is the first one — a missing catalog is not the same thing as an empty one, and a naive implementation collapses those into the same 403/allow-nothing path, which sounds safe but isn't, because 'unavailable' and 'no permissions' need different alarms."

================================================ Step 7 ================================================

They ask: "How do you create one person across three databases with no distributed transaction?"

```
Admin creates user
   │
   ▼
IAM local transaction: INSERT iam_identity + 2x iam_outbox rows (pending)
   │
   ▼
Async worker picks up outbox rows
   ├──► POST DMS  /api/v2/user     ──► on success: write iam_identity_link, mark outbox done
   └──► POST CDMS /champ/user/create ──► on success: write iam_identity_link, mark outbox done
                                         on failure: attempts++, backoff, retry
```

"Creating a person is really two remote HTTP writes across three databases, and there's no transaction that spans all of them. If the DMS call succeeds and the CDMS call 500s, without an outbox that failure is invisible — the admin just sees an error, nobody knows the DMS row already got created, and a naive retry duplicates it.

So the outbox holds the pending intent before either estate has even replied. `iam_identity_link` can't exist yet at that point — it needs the estate's own generated user ID, which doesn't exist until the estate accepts the write. The admin UI shows per-estate status honestly: 'DMS: provisioned, CDMS: failed, 3 attempts, last error 500' — instead of pretending the whole operation is atomic when it structurally can't be."

================================================ Step 8 ================================================

⭐ The bug you SHOULD volunteer — the shared salt

"When I went through the existing auth code, I found both estates were hardcoding the exact same constant pbkdf2 salt across their entire user base. Meaning: two different people with the same password produce the identical password hash. That's a real security defect, not a style nit — it means a leaked hash table lets you build a rainbow table across the whole company instead of per-user.

I couldn't just bulk re-hash everyone, because re-hashing needs the plaintext password, and the plaintext exists exactly once — at the moment someone next logs in. So I imported the legacy hashes flagged `legacy_salt=true`, and on the user's next successful login I verify against the old hash, then immediately re-hash with a fresh per-user random salt and clear the flag. Zero user-visible disruption, and `legacy_salt` doubles as my coverage metric — I can query exactly what fraction of the user base is still on the old salt and force-reset the stragglers after a window."

================================================ Step 9 ================================================

They ask: "Kafka is at-least-once. What stops a dropped or duplicate propagation message from leaving an estate stale?"

"Propagation goes MySQL → IAM's own Redis → a Kafka event → the estate's consumer → the estate's own Redis. That's fast — seconds end to end. But if a consumer is down when the message publishes and Kafka's retention rolls past it, that consumer's Redis is stale forever unless something else catches it.

So every consumer also runs a 15-minute reconcile: compare its local version against IAM's catalog endpoint by ETag, and rebuild on mismatch. Worst-case staleness is bounded at 15 minutes even if the message is lost outright. A duplicate message is harmless by construction — the consumer just refetches and rewrites the same versioned prefix, so replaying it twice does nothing extra."

================================================ Step 10 ================================================

They ask: "You said the user-sync used to match on phone number — why was that dangerous, and what did you replace it with?"

"A phone number is mutable — someone changes SIMs, numbers get recycled, and now you've silently linked the wrong human across two systems that both think they know who this is. I replaced it with `iam_identity_link`, keyed on identity ID plus which system plus that system's own external user ID, and — critically — IAM is the only thing allowed to write it. If an estate could create a user directly, you'd get unlinked rows with no reliable key to reconcile them by afterward. With IAM as the sole writer, the link table is complete by construction, not by a nightly best-effort job trying to guess who's who."

Cut these from your interview story:

❌ "I built 12 tables and 3 Redis instances."
That's an inventory, not a decision. It invites "why 12" and now you're defending schema count instead of explaining the design.

❌ "I implemented JWT auth with RBAC."
Every backend engineer has done this. It doesn't distinguish anything — lead with the passthrough constraint instead.

❌ "I unified nine auth systems into one."
Sounds like a rewrite, which invites "so you migrated nine codebases?" The actual story is the opposite — nothing downstream changed. Say "additive" explicitly.

❌ "Permissions are checked via Redis."
Too vague, sounds like you just picked a cache. The real answer is the size constraint (nginx header buffer) and the revocation-latency tradeoff — that's the engineering, not the tool choice.

Numbers you must know:

- Nine auth implementations, all HS256, one shared secret under five env-var names.
- 12 IAM tables, own MySQL instance, no shared schema with either estate.
- 3 token audiences: dms, cdms, cdms_collections — three separate secrets, three id spaces, never interchangeable.
- ~10,000 employees indexing into ~30 catalog sets; grant changes roughly weekly.
- Token ≈ 210 bytes; a fully-expanded permission list would be ≈ 7.6 KB against nginx's 8 KB header buffer default.
- Catalog propagation: seconds end-to-end via Kafka; 15-minute reconcile as the worst-case bound under at-least-once delivery.
- SSO cookie 12 hours; per-audience API token 1 hour.
- Per-user exception grants (extra_perms) typically 0–3 entries riding in the token.
- **~2,000 successful logins/day** across both estates, **peak ~310/hour** (10:00–11:00 IST).
  Measured on CDMS: 978 on Mon 2026-09-21, 964 on Tue 2026-09-22, peak hour 155 (second peak 143 at
  11:00). Roughly doubles when DMS is included, which is the figure the resume carries.

  **How it was measured, because this is worth knowing if asked.** `/api/champ/login` emits no log line
  and morgan is env-gated off in production, so filtering on the route path returns zero over 24 hours.
  The signal that works is `logger.info(access_data)` at `user.ts:1462` — the only such call in the
  codebase, firing once per successful login. Filter `/ecs/CDMS-PROD-TG` on `"token_type"`. If an
  interviewer asks how you instrument something with no request logging, this is a real answer: find the
  one call that is guaranteed to fire on the success path, and key off its payload.
- [NEED FROM ME]: "What's the measured p50/p99 from a grant commit to the estate's Redis pointer flip, and how often has the 15-minute reconcile actually had to rebuild something?"
- [NEED FROM ME]: "What's the outbox success rate and mean time-to-done for user provisioning, and how many rows are currently stuck in failed?"
- [NEED FROM ME]: "What percentage of identities are still flagged legacy_salt after rollout, and how many accounts were force-reset?"
