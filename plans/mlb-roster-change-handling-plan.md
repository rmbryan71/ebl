# Roster change handling plan

Goal: keep the EBL player pool aligned to the Phillies 40‑man roster. Only 40‑man status matters.

Note: this plan intentionally ignores migration complexity. Changes will be applied via `db-init.py`, so migrations are out of scope.

**Implementation steps**
1. Add a lightweight checker function (e.g., `check_roster_delta()`) that compares:
   - Active MLB IDs in the DB (`SELECT mlb_id FROM players WHERE is_active = 1`)
   - Active MLB IDs from the MLB API 40‑man roster (`Team.roster` list of person IDs)
2. If the sets are identical, exit without doing anything else.
3. If there is any difference, run `sync_players()` (players table only).
4. After `sync_players()` finishes, run `apply_mlb_roster_changes()`:
   - Diff the previous active MLB IDs vs. the new active MLB IDs.
   - Insert rows into a new table `mlb_roster_changes` for each add/remove.
   - Apply league effects for removals (remove from `team_player`, set `has_empty_roster_spot`, insert `alumni`).
5. Keep `mlb_roster_changes` append‑only; add audit triggers.

**Cron changes**
- Replace the nightly `roster-sync.py` cron with a new checker job (e.g., `roster-check.py`).
- The checker runs nightly and, on a detected change, executes:
  1. `roster-sync.py` (players table update only)
  2. `apply_mlb_roster_changes()` (writes `mlb_roster_changes`, updates teams/alumni)
- Weekly scoring and roster moves remain unchanged.

**Explicit change tracking table**
Add a new table named **`mlb_roster_changes`** that records roster adds/removes detected during snapshot diffs.
- Columns: `id`, `player_mlb_id`, `change_date`, `change_type` (add/remove), `source` (snapshot), `notes`.
- `apply_mlb_roster_changes()` writes to this table; `roster-sync.py` does not.

**Decision 1 (2026-01-17 00:20 ET)**
- Selected Option 2: split into two functions (`sync_players`, `apply_mlb_roster_changes`).

**Decision 2 (2026-01-17 00:22 ET)**
- Selected Option 2: wrap `sync_players` + `apply_mlb_roster_changes` in a single DB transaction.

**Decision 3 (2026-01-17 00:23 ET)**
- Selected Option 1: unique constraint on `(player_mlb_id, change_date, change_type)`.

**Decision 4 (2026-01-17 00:24 ET)**
- Selected Option 1: use checker run date in ET for `change_date`.

**Decision 5 (2026-01-17 00:25 ET)**
- Selected Option 2: retry with limited backoff on API failures.

**Decision 6 (2026-01-17 00:26 ET)**
- Selected Option 1: run nightly checker before weekly scoring/moves.

**Decision 7 (2026-01-17 00:27 ET)**
- Selected Option 2: add audit triggers for `mlb_roster_changes`.

**Decision 8 (2026-01-17 00:28 ET)**
- Selected Option 2: DB integration tests for `apply_mlb_roster_changes`.

**Decision 9 (2026-01-17 00:35 ET)**
- Selected Option 1: store the “before” roster set in memory only.

**Decision 10 (2026-01-17 00:36 ET)**
- Selected Option 2: retry `sync_players()` with limited backoff on failure.

**Decision 11 (2026-01-17 00:37 ET)**
- Selected Option 1: update players → compute diff → write `mlb_roster_changes` → apply team effects.

**Decision 12 (2026-01-17 00:38 ET)**
- Selected Option 1: allow one net change per player per day (unique constraint enforces).

**Decision 13 (2026-01-17 00:39 ET)**
- Selected Option 1: keep `mlb_roster_changes.notes` empty for now.

**Decision 14 (2026-01-17 00:40 ET)**
- Selected Option 2: `sync_players()` updates only `is_active` and `last_updated` for existing players.

**Decision 15 (2026-01-17 00:41 ET)**
- Selected Option 2: audit triggers only on `mlb_roster_changes`.

**Decision 16 (2026-01-17 00:42 ET)**
- Selected Option 1: add indexes on `players.is_active`, `team_player.player_mlb_id`, `mlb_roster_changes(change_date)`, plus the unique constraint.

**Decision 17 (2026-01-17 00:43 ET)**
- Selected Option 2: cache player details and only fetch for new players.

**Decision 18 (2026-01-17 00:44 ET)**
- Selected Option 1: log-only failure handling; alerting deferred.

---

## Test strategy

### Unit tests (diff + decision logic)

**Pros**
- Fast and deterministic.
- Easy to run in CI.

**Cons**
- Doesn’t validate DB side effects or triggers.

**Implementation steps**
1. Extract diff logic into small functions (e.g., `compute_roster_delta()`).
2. Test identical sets (no changes), add-only, remove-only, and mixed changes.
3. Validate that the checker only triggers sync on real differences.

---

## Status
- 2026-01-17 00:05 ET: Plan created.

## Execution Notes

When execution begins, add a detailed, timestamped list of all changes, commands, and outcomes here.
