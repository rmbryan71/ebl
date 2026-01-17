# Roster change handling plan

Goal: keep the EBL player pool aligned to the Phillies 40‑man roster. Only 40‑man status matters.

## Option 1: Daily 40‑man snapshot (current baseline)

**Description**
Pull the Phillies 40‑man roster each day and diff against the `players` table.

**Pros**
- Simple and reliable.
- Doesn’t require interpreting transaction types.

**Cons**
- Many API calls (player details per day).
- Captures state, not the reason for changes.

**Implementation steps**
1. Run `roster-sync.py` nightly (date optional).
2. Upsert all rostered players (mark `is_active = 1`).
3. Deactivate players no longer on the roster, write alumni, remove from `team_player`.
4. Set `has_empty_roster_spot = 1` for teams that lost players.

---

## Option 2: 40‑man snapshot + caching

**Description**
Same as Option 1, but cache player details so they aren’t fetched every day.

**Pros**
- Fewer API calls.
- Same correctness as snapshot diff.

**Cons**
- Requires a local cache table or file.

**Implementation steps**
1. Add a cache table (e.g., `player_cache`) keyed by `mlb_id` and `last_fetched`.
2. When syncing, reuse cached player details if fresh (e.g., within 7 days).
3. Refresh cache only when missing/stale.

---

## Option 3: Transaction‑triggered snapshot

**Description**
Only run a full roster snapshot when there is evidence of a 40‑man change.

**Pros**
- Fewer full pulls.
- Keeps roster accurate.

**Cons**
- Requires reliable detection of 40‑man changes.

**Implementation steps**
1. Monitor MLB transactions for Phillies.
2. If any transaction looks like a 40‑man add/remove, run `roster-sync.py` that day.
3. Otherwise skip the daily snapshot.

---

## Recommendation

If you want maximum correctness with minimal complexity, Option 1 is best. If you want fewer API calls while keeping accuracy, Option 2 is the best balance.

## Status
- 2026-01-17 00:05 ET: Plan created.
