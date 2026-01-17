# Players use MLB ID plan

Goal: use `mlb_id` as the only player identifier everywhere. No local-only player IDs.

## Summary
- Make `players.mlb_id` the primary key.
- Update all foreign keys and queries to reference `players.mlb_id` instead of `players.id`.
- Remove or stop using `players.id` entirely.

## Implementation steps

1. **Schema design**
   - Change `players` table to use `mlb_id` as the primary key.
   - Remove the local `id` column or leave it unused (preferred: remove).
   - Update all FK relationships:
     - `team_player.player_mlb_id` → `players.mlb_id`
     - `stats.player_mlb_id` → `players.mlb_id`
     - `roster_move_request_players.player_mlb_id` → `players.mlb_id`
     - `alumni.player_mlb_id` → `players.mlb_id`

2. **Code updates**
   - Replace all queries that use `players.id` with `players.mlb_id`.
   - Update joins to use `players.mlb_id`.
   - Update `roster-sync.py`, `stats-populate.py`, `roster-moves.py`, and `app.py` to treat MLB IDs as primary identifiers.
   - Update any request params (`player_id`) to accept MLB IDs explicitly.

3. **Audit triggers**
   - Update audit trigger payloads to store `mlb_id` instead of internal `id`.
   - Ensure audit records remain consistent after schema change.

4. **Tests and fixtures**
   - Update tests to use MLB IDs in all inserts and asserts.
   - Add a small migration test to ensure FK integrity after conversion.

5. **Deployment steps**
   - Rebuild the database via `db-init.py` after schema change.
   - Validate: roster view, player page, roster moves, stats population.

## Risks
- Migration complexity: FK updates must be done in the correct order.
- Any code still referencing `players.id` will break.

## Status
- 2026-01-16 23:10 ET: Plan created.
- 2026-01-16 23:40 ET: Implemented schema + code updates to use MLB IDs throughout; requires running `db-init.py` to rebuild the database.
- 2026-01-16 23:53 ET: Updated `db-init.py` to drop/recreate tables so schema changes take effect.
