# 2025 season simulation plan

Goal: document options for simulating the 2025 season for testing, with pros/cons and implementation steps for each.

## Option 1: Live API replay (daily calls)

**Description**
Call MLB StatsAPI for roster, stats, and transactions for each day in the range.

**Pros**
- Uses real MLB data.
- No upfront data generation.

**Cons**
- Slow and non-deterministic.
- Depends on API availability and rate limits.

**Implementation steps**
1. Create a runner script (e.g., `scripts/simulate_2025_live.py`) with CLI args for `start_date`, `end_date`, `--dry-run`, and `--resume`.\n
2. For each day in the range:\n
   - If `--resume` is enabled, skip days that already have a simulation log for that week.\n
   - Call `roster-sync.py` with a roster date for that day (live API).\n
   - Call `stats-populate.py` for that single day (live API game logs).\n
   - Check daily invariants: team roster size <= 4, no inactive players assigned, and no negative stats.\n
3. On Sundays (end of week):\n
   - Run `scoring.py` to award points.\n
   - Run `roster-moves.py` to process pending requests.\n
   - Write a weekly Markdown log summarizing date range, points awarded, and roster move outcomes.\n
4. Add retry/backoff around MLB API calls to reduce timeouts and rate-limit errors.\n
5. Add a configurable throttle (sleep between requests) to reduce API pressure during long runs.\n
6. Add a final summary that prints total days processed, errors, and where logs were written.

**Current implementation status (2026-01-16 22:05 ET)**
- Script added: `scripts/simulate_2025_live.py`.
- CLI: `--start YYYY-MM-DD`, `--end YYYY-MM-DD`, `--dry-run`.
- Daily loop actions:
  - `roster-sync.py` for the current day.
  - `stats-populate.py` for the current day.
- Weekly (Sunday) actions:
  - `scoring.py` then `roster-moves.py`.
  - Writes a weekly Markdown log to `logs/simulations/simulation-YYYY-MM-DD.md` with points and roster-move counts.
- Notes: retry/backoff and resume options are not implemented yet.

---

## Option 2: Cached daily snapshots (fixtures)

**Description**
Save roster + stats as JSON for each day, then replay from disk.

**Pros**
- Deterministic and fast.
- Offline testing.

**Cons**
- Large data storage.
- Requires fixture generation and maintenance.

**Implementation steps**
1. Build a fixture generator that writes daily roster and stats JSON files.
2. Add a replay runner that reads fixtures instead of live API.
3. Store fixtures under a standard path (e.g., `fixtures/2025`).
4. Keep a small “smoke” fixture set for CI.

---

## Option 3: Transaction-only replay

**Description**
Ingest MLB transactions and derive roster changes from those events.

**Pros**
- Smaller data footprint.
- Captures event history with dates.

**Cons**
- Complex parsing rules.
- Can miss edge cases if transactions are incomplete.

**Implementation steps**
1. Store transactions daily into a table (idempotent by transaction ID).
2. Map transaction types to roster add/remove logic.
3. Apply roster changes in date order.
4. Validate results against known roster snapshots.

---

## Option 4: Hybrid (transactions + roster snapshots)

**Description**
Use transactions for events but reconcile with periodic roster snapshots.

**Pros**
- Most accurate.
- Catches missed transactions.

**Cons**
- Most complex to implement and maintain.

**Implementation steps**
1. Run transaction ingestion daily.
2. Run roster snapshot sync daily (or weekly).
3. Compare derived roster vs. snapshot and reconcile differences.
4. Record anomalies for review.

---

## Option 5: Synthetic season generator

**Description**
Generate randomized roster changes and stats to stress-test rules.

**Pros**
- Fast and fully controllable.
- Great for edge cases.

**Cons**
- Not real MLB behavior.
- Harder to validate.

**Implementation steps**
1. Define probability rules for roster churn and stat distributions.
2. Generate daily data for all players.
3. Run scoring + roster moves on synthetic data.
4. Validate invariants and edge-case handling.

---

## Option 6: DB snapshots + deltas

**Description**
Start from a baseline DB snapshot, then apply daily deltas.

**Pros**
- Very fast replay.
- Easy rollback to any day.

**Cons**
- Larger storage; tooling required to create/apply deltas.

**Implementation steps**
1. Take baseline DB dump.
2. Record per-day deltas (SQL or JSON operations).
3. Apply deltas in order for replay.
4. Maintain tools to regenerate snapshots.

---

## Next decision

Pick one primary path (and optionally a backup path). If you want deterministic tests, Option 2 or 4 is typically best. If you want simpler real-world data, Option 1 is quickest but least stable.
