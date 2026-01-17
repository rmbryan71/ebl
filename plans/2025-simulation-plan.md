# 2025 simulation plan (reset)

## Instructions for use

These steps run locally only. They are blocked on Render and require `SIMULATION_MODE=1`.

### 1) Capture fixtures
1. Set environment variables:
   - `SIMULATION_MODE=1`
   - `DATABASE_URL="postgresql://robertbryan@localhost:5432/ebl"`
2. Run capture:
   - `python scripts/capture_2025_fixtures.py --start 2025-04-01 --end 2025-04-14 --out fixtures/2025`

### 2) Replay fixtures into the DB
1. Ensure the database is initialized (fresh DB recommended).
2. Run replay:
   - `python scripts/replay_2025_simulation.py --start 2025-04-01 --end 2025-04-14 --fixtures fixtures/2025`
3. Weekly logs write to `logs/simulations/weekly-YYYY-MM-DD_to_YYYY-MM-DD.md`.
4. Error logs write to `logs/simulations/errors/run-YYYY-MM-DD_HHMMSS.md`.

### 3) Reset simulation artifacts
1. Run reset (preserves `logs/simulations/errors/`):
   - `python scripts/reset_simulation.py --fixtures fixtures/2025 --logs logs/simulations`

Goal: define the problem and requirements first, then choose an approach.

## Problem statement
We need a reliable way to simulate the 2025 MLB season in EBL so we can test roster changes, stats updates, scoring, and roster moves in a controlled, repeatable way.

## Requirements
1. Deterministic replay (same inputs produce same outputs).
2. Supports daily progression from start to end date.
3. Handles MLB 40-man roster changes accurately.
4. Feeds player stats into weekly scoring.
5. Supports roster move requests and weekly processing.
6. Produces audit/log outputs we can review.
7. Runs locally without external dependencies once data is prepared.
8. Can run a small subset (e.g., 1-2 weeks) for quick checks.
9. When a team loses a player from the MLB 40-man roster during simulation, auto-create an EBL roster move request to fill the open spot using three available players prioritized by lowest MLB player IDs.
10. Include safety guards to prevent running against production data (explicit env/flag checks).
11. Support a clean reset that removes all simulation artifacts (logs, fixtures, and any DB changes made by the simulation).
12. Ensure simulation scripts cannot be invoked by production cron jobs or users (explicit permissions and environment gating).
13. Enforce ET date handling for roster and stats fixtures (document and validate in code).
14. Safety denylist: simulations only allowed on local environments; explicitly block Render.

## Decisions
1. Primary purpose: correctness-focused.
2. Data source: hybrid (capture real MLB data once, replay from fixtures).
3. Speed vs fidelity: balanced, with speed as the default and a fidelity mode available.
4. Correctness definition: roster membership + points totals (optional stat spot checks).
5. Default window: configurable with a 2-week default.
6. CI: local-only for now.
7. Automated roster response: simulate owner roster move request on 40-man removal using lowest MLB IDs as priority (1=lowest).
8. Simulation approach: Option A (capture daily fixtures, then replay).
9. Fixture format: separate roster + stats JSON files per day.
10. Storage layout: `fixtures/2025/roster/YYYY-MM-DD.json` and `fixtures/2025/stats/YYYY-MM-DD.json`.
11. Roster snapshot source: MLB roster API only (store active 40-man IDs per day).
12. Stats granularity: store daily totals per player.
13. Replay ordering: `sync_players` → apply roster changes → stats → weekly scoring/moves.
14. Logging: weekly logs at `logs/simulations/weekly-YYYY-MM-DD.md`.
15. Safety guard: require `SIMULATION_MODE=1` env var.
16. Reset strategy: dedicated reset command to remove fixtures/logs and simulation DB artifacts.
17. Weekly log content: points, roster moves, roster-change events, errors/anomalies, weekly summary.
18. Logs include a final season summary.
19. Log format: Markdown.
20. Weekly log ordering: grouped sections (not chronological).
21. Weekly log naming: include week date range (e.g., `weekly-YYYY-MM-DD_to_YYYY-MM-DD.md`).
22. Log retention: overwrite existing week logs on rerun.
23. Failure logging: write failures both in weekly logs and a separate error log per run.
24. Local-only allowlist: only `localhost`, `127.0.0.1`, or unix socket (`host=/tmp`) in `DATABASE_URL`.
25. Cleanup strategy: no tagging; reset script truncates affected tables.
26. Weekly log template: detailed sections (Summary, Points, Roster Moves with per-team breakdown, Roster Changes with adds/removes, Auto-move actions, Errors).
27. Error logs: `logs/simulations/errors/run-YYYY-MM-DD_HHMMSS.md`.

## Next steps
1. Draft implementation steps for capture and replay.
2. Define clean-reset behavior and safety guards.

## Implementation steps (capture + replay)

### Capture fixtures
1. Add `scripts/capture_2025_fixtures.py` with CLI:
   - `--start YYYY-MM-DD`, `--end YYYY-MM-DD`, `--out fixtures/2025`
   - Require `SIMULATION_MODE=1` or exit with a clear message.
2. For each day in range:
   - Fetch 40-man roster MLB IDs for the date.
   - Fetch daily stat totals for those MLB IDs.
   - Write roster fixture to `fixtures/2025/roster/YYYY-MM-DD.json`.
   - Write stats fixture to `fixtures/2025/stats/YYYY-MM-DD.json`.
3. Write `fixtures/2025/manifest.json` with:
   - date range, capture timestamp, source notes, and fixture schema version.
4. Fail fast on any API error; print which day failed.

### Replay simulation
1. Add `scripts/replay_2025_simulation.py` with CLI:
   - `--start YYYY-MM-DD`, `--end YYYY-MM-DD`, `--fixtures fixtures/2025`
   - Require `SIMULATION_MODE=1` or exit with a clear message.
2. For each day in range:
   - Load roster fixture for the day.
   - Load stats fixture for the day.
   - `sync_players()` using the roster MLB IDs.
   - `apply_mlb_roster_changes()` using previous-day vs current-day roster sets.
   - Insert stats for the day from the fixture.
3. On Sundays (end of week):
   - Run `scoring.py` to award weekly points.
   - Run `roster-moves.py` to process pending requests.
   - Write weekly log to `logs/simulations/weekly-YYYY-MM-DD.md`.
4. When a 40-man removal affects an EBL team:
   - Auto-create a roster move request using three available players with lowest MLB IDs as priorities 1–3.

## Reset + safety guards
1. Add a reset script (e.g., `scripts/reset_simulation.py`) that:
   - Deletes `fixtures/2025/` and `logs/simulations/` (except `logs/simulations/errors/`).
   - Clears simulation-created DB data (pending roster moves, stats, points).
   - Requires `SIMULATION_MODE=1` to run.
2. Ensure capture, replay, and reset scripts all refuse to run if:
   - `SIMULATION_MODE` is not set.
   - `DATABASE_URL` points to Render or any non-local host (explicit denylist check).

## Execution plan
1. Define fixture schemas and add a `manifest.json` schema version.
2. Implement `scripts/capture_2025_fixtures.py` and validate fixture output for a 1-week range.
3. Implement `scripts/replay_2025_simulation.py` and run a 1-week replay against a fresh local DB.
4. Implement `scripts/reset_simulation.py` and verify it removes fixtures, logs, and simulation DB data.
5. Add safety guard checks to all three scripts (env + denylist).
6. Add targeted tests for fixture parsing and roster-move auto-response.
7. Run a 2-week replay and verify weekly logs and points totals.
8. Add ET date validation to capture/replay and document behavior.
9. Use truncation-based cleanup (no per-row tagging).
10. Implement and test the Render denylist guard (block non-local DATABASE_URL).

## Fixture schema plan
1. `fixtures/2025/manifest.json`
   - Fields: `schema_version`, `season`, `start_date`, `end_date`, `captured_at`, `source`, `notes`.
2. `fixtures/2025/roster/YYYY-MM-DD.json`
   - Fields: `date`, `team_id`, `mlb_player_ids` (array of ints), `players` (array of objects with `mlb_player_id`, `name`, `position_code`, `position_name`, `position_type`).
3. `fixtures/2025/stats/YYYY-MM-DD.json`
   - Fields: `date`, `players` (array of objects with `mlb_player_id`, `outs`, `offense`).
4. Validate schema on capture and replay; fail fast with a clear error.
5. Validate `date` fields are interpreted as ET dates (no time component).

## Execution progress (phased)

Phase 1: Fixture schema + manifest validation
2026-01-17 07:32 EST - Added `simulation_fixtures.py` with manifest/roster/stats schema validation helpers and ET date validation (YYYY-MM-DD).
Phase 2: Capture script
2026-01-17 07:34 EST - Added `scripts/capture_2025_fixtures.py` with SIMULATION_MODE and local-only guards, manifest writing, and daily roster/stats fixture capture.
Phase 3: Replay script
2026-01-17 07:42 EST - Added `scripts/replay_2025_simulation.py` to replay fixtures, apply roster changes, insert stats, run scoring + roster moves, and write weekly logs.
Phase 4: Reset script
2026-01-17 07:42 EST - Added `scripts/reset_simulation.py` to delete fixtures/logs (preserving error logs) and truncate simulation-related tables.
Phase 5: Safety guard checks
2026-01-17 07:42 EST - Added `require_local_simulation()` guard and wired it into capture/replay/reset scripts.
Phase 6: Tests + validation runs
2026-01-17 07:42 EST - Added `tests/test_simulation_fixtures.py` to validate fixture schemas.

Add timestamped notes under each phase as work is completed.
