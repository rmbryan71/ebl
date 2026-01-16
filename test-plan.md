# Test plan

This plan is written for the current EBL codebase and is meant to be read by a human. It lists six automated testing options, why they matter, and concrete steps for how you would run them.

## 1) Unit tests (pure functions)

**What it covers**
- Scoring rules, tie handling, point awards, and other pure logic that does not touch the database or Flask.

**Why it helps**
- Fastest tests, easiest to debug, and ideal for CI because they are deterministic.

**Steps**
1. Identify pure functions to isolate (examples: tie resolution in `scoring.py`, innings/out conversions in `stats-populate.py`).
2. Write tests that feed inputs and assert exact outputs.
3. Run locally before commits.

**Current unit tests added**
- `tests/test_scoring.py`: `week_start`, `week_end`, and tie-handling in `award_points_for_category`.
- `tests/test_roster_moves.py`: `order_teams` sorting rules.
- `tests/test_stats_populate.py`: `innings_to_outs`, `calculate_offense`, and `parse_date`.
- `tests/test_transactions_sync.py`: `transaction_matches` pattern detection.

**Pros**
- Fast and reliable.
- Failures are easy to pinpoint.

**Cons**
- Does not test database or web app behavior.

---

## 2) DB integration tests (schema + triggers)

**What it covers**
- Database schema, constraints, triggers, audit trail writes, and SQL queries that must be correct.

**Why it helps**
- Your app relies heavily on SQL and triggers. These tests validate that the database enforces rules correctly.

**Steps**
1. Create a dedicated test database (local Postgres).
2. Run `db-init.py` to create schema and baseline data.
3. Run short scripts that insert/update data and confirm audit rows exist.
4. Assert key invariants (e.g., no duplicate team-player rows).

**Pros**
- Catches real DB issues early.
- Verifies audit trail behavior.

**Cons**
- Slower and requires database setup.

---

## 3) API/service tests (Flask test client)

**What it covers**
- Flask routes, query parameters, and server-side rendering without a browser.

**Why it helps**
- Ensures routes work with expected inputs and protects against regressions.

**Steps**
1. Use Flask’s test client in a test file.
2. Call key routes: `/week`, `/season`, `/team`, `/player`, `/roster-move`.
3. Assert status codes and presence of key text in HTML.
4. Add tests for bad input (e.g., invalid IDs) to confirm 400/404 responses.

**Pros**
- Faster than browser tests.
- Good coverage of routing and validation.

**Cons**
- Does not test real browser behavior or client-side JS.

---

## 4) End-to-end browser tests (Playwright)

**What it covers**
- Actual user behavior in a real browser: login, navigation, roster moves.

**Why it helps**
- Catches UI regressions and broken flows.

**Steps**
1. Spin up the app locally.
2. Launch Playwright and run a scripted flow (login → team page → roster move → verify result).
3. Keep tests small and only on critical user paths.

**Pros**
- Closest to real user behavior.
- Catches issues that server-side tests miss.

**Cons**
- Slow and can be brittle.
- Requires stable test data.

---

## 5) Data pipeline tests (roster sync + stats + scoring)

**What it covers**
- Your daily/weekly batch flows that populate players, stats, points, and roster moves.

**Why it helps**
- These batch flows drive the entire league. Testing them end-to-end catches real-world logic issues.

**Steps**
1. Use a test database and seed it from `db-init.py`.
2. Run `roster-sync.py` and `stats-populate.py` for a small date range.
3. Run `scoring.py` and (optionally) `roster-moves.py`.
4. Assert expected row counts and invariants.

**Pros**
- Validates full system behavior.
- Catches data pipeline regressions.

**Cons**
- Slower and dependent on external data if using live API.

---

## 6) Snapshot tests (HTML/JSON outputs)

**What it covers**
- Regression checks for key rendered pages or query results.

**Why it helps**
- Quick detection of unexpected layout or data changes.

**Steps**
1. Render key pages (e.g., `/week`, `/season`) and save HTML output.
2. Compare against known-good snapshots in tests.
3. Update snapshots only when intentional changes are made.

**Pros**
- Fast and easy to run.
- Good for catching UI regressions.

**Cons**
- Can be noisy if pages change often.
- Does not explain why a change occurred.

---

## Suggested starting point

Start with unit tests + DB integration tests. They give the best coverage-per-effort. Then add a small Playwright smoke test and a lightweight pipeline test once the basics are stable.

## Notes

- 2026-01-16 21:30 ET: Ran unit tests via `.venv/bin/python -m pytest`; all 12 tests passed.
