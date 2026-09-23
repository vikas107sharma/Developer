FINANCIAL INGESTION PIPELINE — OBC Adjustment, Ripplr CDMS

"It looks like a file upload. It's actually fifteen thousand independent financial transactions wearing a spreadsheet as a disguise, and the money on the other end has often already been promised to a salesman standing in a store right now."

================================================ Step 1 ================================================

The 30-second skeleton

"Brands send us credit notes and cash discounts as spreadsheets — one file can carry thousands of rows, and every brand's file looks completely different. Different headers, different column names. Some ship one row per adjustment; some ship ten line items that need summing into one; some ship a single row that actually has to split into two separate adjustment types.

The part that made this hard wasn't parsing — it's that every row is a financial write across four to seven tables: the adjustment record itself, the invoice's outstanding balance, the salesman's collection assignment, sometimes a short-close audit log. So a file isn't an import, it's a few thousand small transactions, and I made the row — not the file — the unit of work. One bad row rolls back on its own and never blocks the rest of the file. Across all brands that's roughly 35,000 adjustment entries a day moving through the pipeline.

I built it on S3, Lambda, and Kafka, with pandas doing the config-driven parsing per brand, and every row landing as its own SQL transaction downstream."

================================================ Step 2 ================================================

The interviewer asks: "Walk me through the architecture."

```
Brand uploads file ──► S3
                          │ ObjectCreated
                          ▼
                  Lambda: filevalidator
                          │  routes by file_type
                          ▼
              OBCAdjustmentAdapter
        auth ─ brand config ─ ETAG DEDUP GUARD ─ pandas pipeline
                          │
          ┌───────────────┴────────────────┐
          ▼                                 ▼
   Kafka: file-create event          per row: Mongo insert (batch 100)
          │                             + Kafka: one message per row
          ▼                                 ▼
   filecreate_consumer              grn_consumer  (constant key →
   creates SQL `Files` row           same partition → strict order)
                                          │
                                          ▼
                                 OBCAdjustmentProcessor
                          validate ─ SQL transaction (4–7 tables) ─ commit
                                          │
                                          ▼
                            update Mongo counters ─ check completion
                                          │
                                          ▼
                         Kafka: file-status event ─ Files.fileStatus flips
```

"Every row does its own Mongo fetch, its own validation against live financial state, and its own single-commit SQL transaction. That's more round trips per row than a batch import would need, but it's the price of true isolation — and it's a price I was happy to pay, because the alternative is one bad row taking the whole file down."

================================================ Step 3 ================================================

They ask: "How did you handle every brand having a different file format?"

"Each brand and adjustment type gets a JSON config, not code. The parser is an ordered pipeline: detect the header row wherever it actually sits — one brand's file has a nine-line preamble before the real header — clean and strip everything, check mandatory columns, apply filters, aggregate, filter again post-aggregation, convert types, then expand rows if a config says one source row becomes multiple adjustment types. Adding a new brand is a config file and a fixture test, not a code change, unless the brand has a genuine quirk."

Then give one concrete example:
"Britannia is the interesting one. One raw row could actually represent two different things depending on its credit-note date versus the invoice date, so before aggregation I categorize it and carry a per-invoice running total of what was already netted at invoicing time — because if I aggregate first, that distinction disappears and I silently double-adjust."

================================================ Step 4 ================================================

They ask: "How do you stop the same adjustment being applied twice?"

"Three independent layers, because each one catches a different re-upload scenario.

First, the S3 file etag becomes the Mongo document's ID — re-upload the exact same file, it's rejected outright before a single row is touched.

Second, within one file, I flag duplicate rows by a set of uniqueness columns before they're even sent downstream.

Third, and this is the one that survives a corrected re-upload of a *different* file with overlapping rows: every row gets an MD5 hash of its brand code plus its uniqueness columns, checked against SQL before insert. I deliberately normalize before hashing — numbers to two decimal places so 9, 9.0 and 9.00 hash identically, strings lowercased and stripped, blanks collapsed to empty string. Without that normalization, the exact same adjustment re-typed with different whitespace hashes differently and slips past the dedup entirely."

================================================ Step 5 ================================================

⭐ The strongest card — the ₹1 phantom at exactly half a rupee

They ask: "What's the trickiest bug you found in this pipeline?"

"There was a rounding bug that only showed up at exact half-rupee fractions. I was rounding the adjustment amount and the resulting new outstanding balance separately, and recombining them — and half-up rounding two numbers independently and then combining them isn't the same as rounding the combination once. At exactly .50 it inflated collected_amount by one rupee, silently, in the ledger.

The fix was to compute one number — the rounded outstanding minus the pre-rounded new outstanding gives you the actual applied_amount — and use that single number everywhere it's written: the adjustment record, the collection row, the payment row. One source of truth for the money, computed once, instead of three tables independently rounding the same underlying fact and drifting apart from each other."

================================================ Step 6 ================================================

⭐ The bug you SHOULD volunteer — driving an invoice negative in production

They ask: "Tell me about a production incident you actually caused or inherited."

"An invoice — I remember the exact one — got driven to a current outstanding of minus 328 rupees in production. Here's the sequence: a delivery collection had already brought its outstanding down and flipped its status to 'No Bill Back.' Then a 645-rupee adjustment landed on it. The existing code had a bypass rule that let No Bill Back invoices skip the normal outstanding checks entirely if the underlying order was in a certain delivery status — the bypass was keyed on order status, not on the amount, and that's the actual root cause, not rounding.

I replaced the bypass with a bounded rule: a No Bill Back settlement can only move outstanding to somewhere between minus one rupee and zero — never further negative — and I added a dedicated audit table that logs every short-close in that same transaction, so there's a permanent record of exactly which adjustment short-closed which invoice and why. I own this one — it shipped, it broke, and the fix is a tighter invariant plus an audit trail, not just a patch on the symptom."

================================================ Step 7 ================================================

They ask: "Any other double-counting bugs?"

"Yes — Britannia again, from the other direction this time. Britannia sometimes nets credit notes into the invoice at the moment of invoicing itself, which gets recorded on the order's own extra_info. If my pipeline didn't know that, it would re-apply the same credit note as a fresh adjustment on top of one that was already baked into the invoice — a genuine double-adjustment, not just a duplicate row.

I compare the credit note's date against the invoice date before aggregating, and cross-check the pre-invoice total against what the order record says was already netted. If it was already netted at invoicing, I don't re-apply it. This has to run before aggregation, not after, because aggregation collapses exactly the distinction I need to make the call."

================================================ Step 8 ================================================

They ask: "What happens if the consumer crashes in the middle of processing a row?"

"The Kafka offset for that row is only committed after processing finishes. If the consumer dies mid-row, the message gets redelivered on restart. The SQL-side hash dedup catches it and marks it a duplicate rather than double-applying the adjustment — so financially it's safe. The one thing I'll own honestly: the Mongo counters increment again on redelivery, so 'processed' can technically exceed 'total.' It doesn't break the terminal-state logic, because that only checks processed-versus-total as a floor, but it's not a fully idempotent counter, and I'd tighten that with a short-circuit on already-success rows if I revisited it."

================================================ Step 9 ================================================

They ask: "Is the file-completion check race-safe under concurrent processing?"

"Honestly — not strictly, and I'll say that up front rather than have it found. It's a read-then-write: read the current counters, decide if the file's done, then set the status. That's not atomic. What makes it safe in practice is that every row for a given file publishes to Kafka under the same message key, so librdkafka's default partitioner sends every row for that file to the same partition, and one consumer processes that partition strictly in order. There's no genuine concurrent write to race against — but that safety comes from partition assignment, not from a database-level guard. If I ever scaled that consumer group to multiple partitions per file, I'd need a proper `find-and-update`-with-status-filter instead of trusting ordering."

================================================ Step 10 ================================================

They ask: "Why pandas for this instead of just looping over rows in Python?"

"Because the actual parsing problem is vectorizable and the row-level problem isn't. Header detection, cleaning, filtering, and aggregation are naturally boolean masks and group-bys over a whole dataframe — pandas does that fast and the code reads like the business rule instead of a nested loop. Where I do still loop row-by-row is exactly where it has to be row-by-row: computing each row's dedup hash, and expanding one source row into multiple typed entries for the brands that need it. I didn't force those into vectorized form just for consistency — they're genuinely per-row operations."

Cut these from your interview story:

❌ "I built a CSV upload feature."
Makes it sound like a form and a database insert. The actual story is thousands of independent financial transactions per file — about 35,000 a day — with three layers of dedup and per-row rollback.

❌ "I used S3, Lambda, and Kafka."
A technology list, not a decision. Lead with why the row had to be the unit of work, then mention the stack in service of that.

❌ "The pipeline handles 14 brands."
Invites "what's hard about that" without you having framed it yet. Open with the config-driven parser and the two double-adjustment bugs instead — that's where the actual engineering is.

❌ "I fixed some bugs in production."
Vague and defensive-sounding. Name the negative-outstanding incident specifically — owning a quantified, root-caused production defect is stronger than implying nothing broke.

Numbers you must know:

- Minimum 4, maximum 6 (7 including a shared-file dispute-close update) SQL tables written per row, inside one transaction with a single commit.
- 3 dedup layers: S3 etag at the file level, in-file duplicate flagging, and SQL hash lookup on unique_key_hash.
- MD5 hash inputs normalized: numerics to 2 decimal places, strings lowercased and stripped, blanks to empty string.
- Mongo entry inserts batched at 100 rows per insert_many call, unordered, with one retry for transient errors.
- No Bill Back settlement bound: outstanding may move to between −1 and 0, never further negative.
- 14 brand codes, 22 brand/adjustment-type config files (14 credit_adjustment + 8 cash_discount).
- Lambda timeout 600 seconds bounds the entire per-file adapter run, including the row-push loop.
- **~35,000 obc_adjustment_entry messages/day** across the pipeline. Confirmed 2026-09-22 from your own production observation. This is the number to quote — it is a daily total across all brands, NOT a per-file count.
- [NEED FROM ME]: "What's the average and p95 row count per *single upload* from obcAdjustmentFileLog?" — only the daily total is confirmed. The largest sample file on disk is under 3,000 rows, so if asked "how big is one file?", say "a few thousand rows, the daily total across brands is ~35K" rather than guessing a per-file figure.
- [NEED FROM ME]: "What's the failure and duplicate rate across all files — sum of failed/duplicates/success over total?"
- [NEED FROM ME]: "How many No Bill Back short-closes have been logged since the bounded-rule fix shipped?"
- [NEED FROM ME]: "What's the total rupee value of adjustments processed, split by credit_adjustment vs cash_discount?"
