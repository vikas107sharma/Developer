REPORTING & BANK RECONCILIATION — Report Platform + ICICI Integration, Ripplr CDMS / Ripplr Fin

"Two halves of the same idea: one side turns messy operational data into a file someone can open, the other turns an encrypted bank payload into a row you can trust exactly once."

This one splits into two acts — a batch report platform and a bank integration — because they're genuinely different problems that happen to share a resume line.

================================================ Step 1 ================================================

Your 90-second answer — Act 1, Reporting

"It's a background report platform behind a database-backed job queue, covering nineteen report types — outstanding ledger, credit-adjustment and cash-discount reconciliation, cheque-bounce recovery and ageing, salesman detail, GPS compliance, store-visit compliance, retailer master, and the rest — plus a shared library several of them pull from for cross-checking missing invoices.

Every type runs the same contract — claim a queue row, generate a workbook, upload to S3, write status back. The interesting part is that one generation strategy doesn't fit all nineteen. A normal report is a single query pulled straight into an in-memory sheet. A very large one streams rows to a workbook writer on disk instead of holding everything in memory. Another paginates the source query in fixed-size chunks. One splits its date range into windows, and one zips per-file outputs into a single archive. The outstanding ledger actually hit that boundary in production: it was capped at 100,000 rows, usage outgrew it, and I raised the cap to 300,000 as the immediate fix while flagging that the durable answer is moving it onto the streaming pattern rather than raising a limit again."

================================================ Step 2 ================================================

"How do you decide which generation strategy a report needs?"

"Row count and memory, mostly. If the result set comfortably fits in memory as a workbook, you don't pay for the complexity of a streaming writer — that's the right call for the majority of the nineteen. Once a result set can plausibly exceed what you want resident in memory on a shared worker process, you either stream the write to disk as rows arrive, or paginate the source query into fixed-size chunks and merge on the way out.

The judgement call I actually had to make was on the outstanding ledger when it outgrew a hard limit: raise the ceiling now, or rebuild onto streaming now. I raised the ceiling, because it was a one-line, immediately safe fix for an active problem, and flagged the streaming rebuild as the correct next step rather than pretending a bigger number was a real answer."

================================================ Step 3 ================================================

The row-cap failure mode

"What actually happens to row 100,001 before your fix?"

"Nothing dramatic, which is exactly the problem — a bare LIMIT with no ordering guarantee just silently drops it. The report still finishes, still gets marked processed, and looks identical to a complete report to whoever downloads it. That's a correctness and observability gap, not just a performance one — there's no signal anywhere that the report was truncated.

The honest fix isn't a bigger number. It's either the streaming pattern, so memory stays bounded regardless of row count, or a windowed export splitting one big report into date-bounded chunks — both patterns the platform already uses for other types, so it's reuse rather than new machinery."

================================================ Step 4 ================================================

The concurrency-and-failure-mode card

"What's the queue's concurrency model, and what happens if a worker dies mid-report?"

"It's a coarse, whole-queue lock rather than per-report locking — before claiming pending rows, the runner checks whether anything in the queue is already inprogress, and if so the entire pass returns without touching anything. That's simple to reason about and it does guarantee only one worker generates at a time, but the cost is that one wedged report blocks all nineteen.

The real gap is what happens if the process is killed after it flips a row to inprogress but before it ever writes status back — that row is stuck forever and every pending report queues behind it. There's no lease, no heartbeat, no reaper. The fix I'd propose doesn't require touching any report handler: add a heartbeat column and treat an inprogress row older than a few minutes as abandoned and reclaimable."

================================================ Step 5 ================================================

The GPS field-visit report

"Tell me about the salesman GPS report."

"It's a geo-fencing check — I compare the coordinates a salesman actually captured at collection time against the store's admin-verified KYC coordinates, and flag anything more than 500 meters apart as 'outside radius.' If the store never had its KYC coordinates verified in the first place, I short-circuit straight to 'not verified' rather than computing a meaningless distance.

I'll volunteer the honest limitation here rather than wait for it: the distance calculation multiplies both the latitude delta and the longitude delta by the same meters-per-degree constant. That's fine for latitude, but a degree of longitude is only that wide at the equator — it shrinks by the cosine of latitude as you move away from it. At roughly 20°N, that overstates east-west distance by about 6%. For a short, local 500-meter threshold that's a tolerable approximation, not the real haversine formula, and it's the first thing I'd fix if this report needed to be trusted at longer range."

================================================ Step 6 ================================================

⭐ The bug you SHOULD volunteer — the timezone bug

"Any bug in your own code you'd bring up unprompted?"

"Yes — a silent timezone corruption in the shared invoice-tracking library I built. MySQL was handing back a UTC datetime as a plain string, and my first version parsed that string as if it were already in the batch host's local timezone before converting it to IST for display. Every timestamp in that column was quietly wrong by whatever the offset between the host's local zone and UTC happened to be.

I fixed it by parsing explicitly as UTC first, then converting to IST — and I didn't just fix it, I wrote a test that pins the process's TZ environment variable, specifically so this exact bug can't come back and hide just because it happens to run correctly on whichever machine you're testing on that day."

================================================ Step 7 ================================================

Your 90-second answer — Act 2, Banking

"The other half is the ICICI bank integration for reconciliation. ICICI actually exposes two different channels for the same account, encrypted two different ways, and I built both. The pull side — a scheduled statement fetch — uses a hybrid envelope: a fresh symmetric AES key generated per request, wrapped with the bank's RSA public key, with the payload encrypted under that AES key. The push side — a webhook ICICI calls when a transaction posts — uses pure RSA-4096 encryption per field, no AES envelope at all, because it's a completely separate spec from the bank.

The other real problem was reconciliation dedup. ICICI resends the same webhook roughly every 30 minutes until it gets acknowledged, and a statement re-pull can return rows I've already seen. I built a four-column unique key and an insert-that-ignores-duplicates so both of those replay patterns are naturally idempotent, without needing application-level dedup logic."

================================================ Step 8 ================================================

⭐ THE strongest card — the hybrid envelope

The interviewer asks: "Walk me through the actual encryption, and why two schemes for one bank?"

"On the pull side, ICICI's spec is a hybrid envelope: for every request, I generate a fresh symmetric key, encrypt the request payload with it, then encrypt that symmetric key itself with the bank's RSA public key and send both. On the response side, ICICI encrypts the same way, but the initialization vector is handled differently depending on direction — on my outbound request the IV goes in its own field, but on the bank's response the IV comes prepended to the ciphertext instead. If you don't know that going in, decryption just fails with no useful error.

On the push side, the webhook ICICI calls when a transaction happens uses a completely different scheme — pure per-field RSA-4096 with no symmetric key at all, because it's a different API document from the bank. To make one handler work whether encryption is switched on in production or the payload is a plaintext UAT sample, I added a byte-length check: a field is only treated as RSA ciphertext if decoding it produces exactly 512 bytes, one full RSA-4096 block. If it's not that length, I treat it as already-plaintext."

================================================ Step 9 ================================================

The reconciliation dedup card

"How do you make sure you never double-count a bank transaction?"

"A unique key across four columns — value date, UTR number, transaction amount, and a type flag — with an insert-ignore, so the same logical transaction arriving twice just gets silently dropped on the second attempt instead of needing an explicit duplicate check in application code.

The type flag matters more than it looks like it should: I deliberately scope the uniqueness by whether the row came from the push webhook or the pull statement, because I want both a push row and a pull-audit row for the exact same transaction to be able to coexist — they're not duplicates of each other, they're two different observations of the same event, and I need both for audit purposes.

One exemption I built in on purpose: cash and cash-deposit-machine entries don't carry a UTR at all, so I let that column be NULL for those rows. MySQL treats NULL as distinct from itself in a unique index, so those rows never collide against each other on that column — which is exactly the behavior I want, not a bug I'm working around."

================================================ Step 10 ================================================

The extra cards, if there's time

"Anything else worth knowing about that integration?"

"Two smaller things I'd bring up if asked. First, ICICI's free-text remarks field carries the transaction reference in a different position depending on the payment rail — UPI and NACH put it in one segment, IMPS/NEFT/RTGS in another, IFT in a third — so the parser has to branch on rail type, with a fallback to the bank's own transaction ID if nothing parses cleanly.

Second, every outbound call to ICICI goes through a retry wrapper — ten retries at a fixed five-second delay — and I specifically avoided a bug I found in a sibling integration in the same codebase for a different bank, where an undefined logging reference would have thrown inside the retry path itself."

Cut these from your interview story:

❌ "I built a reporting service with nineteen report types."
That's a feature count, not engineering. Lead with the strategy choice — in-memory versus streaming versus chunked versus windowed — and the row-cap incident that forced it, because that's the part that shows judgement.

❌ "The queue handles concurrency correctly."
It guarantees one worker at a time, but there's no lease or heartbeat, so a process killed mid-report wedges the whole queue. Volunteer that failure mode and the heartbeat fix — getting caught by it is far worse than raising it.

❌ "The bank integration has zero test coverage gaps."
The sales-officer payment branch I added to the downstream consumer has no test covering it — a schema drift between the two payment tables it reads from would only surface at runtime. I'd rather say that than get caught flat if asked.

Numbers you must know

- Report platform: 19 active report types behind one database-backed queue, with four generation strategies (in-memory, streamed, chunked, date-windowed) plus zipped multi-file output.
- Outstanding-ledger row cap: raised from 100,000 to 300,000 rows after production usage outgrew the original ceiling.
- GPS radius threshold: 500 meters; date-range caps on my date-bounded reports: 62 days inclusive.
- ICICI dedup key: 4 columns (value date, UTR, amount, type), enforced via insert-ignore.
- ICICI retry policy: 10 attempts, fixed 5-second delay; statement pagination capped at 100 pages per run as a safety ceiling.
- RSA block-size check on the push webhook: 512 bytes = one RSA-4096 block.
- [NEED FROM ME: has the whole-queue lock ever actually caused a stuck-queue incident in production, and if so, which report type triggered it?]
- [NEED FROM ME: what's the real current row count for outstanding-ledger — is 300,000 durable headroom, or already close to being outgrown again?]
**Reporting volume — confirmed 2026-09-22 from `report_queue`.**

- **333–452 reports/day**, mean ~375 over 12 months. Peak day **642** (2026-02-19).
- **146,430 reports** in the last 12.7 months; 438,600 rows in the table since Sep 2022.
- **192–344 distinct users/month.** Peak hours 09:30 and 10:30 IST — which is exactly why the
  whole-queue lock matters: the contention is concentrated, not spread.

**Bank reconciliation — IDFC, Aug 2026. Read the caveat before quoting these.**

- **55,069 transactions, ₹36.4 Cr reconciled** in the month — ~2,120 transactions and ~₹1.40 Cr per working day.
- **Coverage 85%**: ₹36.4 Cr against ₹42.6 Cr of UPI+NEFT collections.
- Match rate by instrument: IMPS 93.1%, NEFT 90.6%, RTGS 81.8%, **UPI 61.2%** — UPI is the only real gap.
- IFT, Cash and blank-type rows (6,412 lines, ₹15.5 Cr) are not collections and can never match. Say
  that before someone computes a misleadingly low overall match rate from the raw feed.
- Deduped by `transaction_number`: the feed carries each UPI transaction twice — a bank line and a
  virtual-account line sharing a UTR — 11,775 duplicated UTRs in August. **Always quote the deduped
  number.** The dedup itself is a good thing to volunteer; it shows you read the feed rather than the total.
- There is no rejected state. A NULL `verification_status` means unclaimed, not failed.

⚠️ **The reconciliation figures are IDFC; the RSA+AES envelope work in this card is ICICI.** The resume
says "bank integrations" rather than naming one, deliberately. Do not let the ₹36 Cr get attached to the
ICICI envelope in conversation — they are different integrations.
