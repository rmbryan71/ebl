# Active users heartbeat plan

Goal: show the number of people actively using the website via client-side heartbeats.

## Scope
- Track active users (logged-in and anonymous).
- Display active count on the home page (large screens only).

## Implementation steps
1. Add a new table `active_sessions` (or reuse an existing table) with:
   - `id`, `session_id`, `user_id` (nullable), `last_seen_at`, `user_agent`, `ip_address`.
2. Add a lightweight endpoint `/heartbeat`:
   - Accepts POST from the client every 30–60 seconds.
   - Updates/creates the row for the current session.
3. Create a session identifier:
   - For logged-in users, use `user_id`.
   - For anonymous visitors, set a signed cookie with a random ID.
4. Add a small JS snippet on all pages:
   - `setInterval` to POST `/heartbeat`.
   - Use `navigator.sendBeacon` when possible; fallback to `fetch`.
5. In the home page route, query active count:
   - `SELECT COUNT(*)` from `active_sessions`
   - Filter where `last_seen_at >= now() - interval '5 minutes'`.
6. Add a cleanup mechanism:
   - Periodic delete of rows older than N hours (cron or at request time).
7. Add UI element (large screens only):
   - Display “Active users: X” on the home page.
8. Add tests:
   - Unit test for heartbeat handler.
   - Integration test for active count query.

## Decisions
1. Heartbeat interval: 60 seconds.
2. Active window: 10 minutes.
3. Anonymous identification: IP + user agent hash (no cookies).
4. Include anonymous users in count.
5. Cleanup strategy: delete stale rows during heartbeat requests.
6. Display location: top nav (large screens only).
7. Label format: show value followed by " people online".

## Decisions needed
- Heartbeat interval (default 30s or 60s).
- Active window for “currently active” (default 5 minutes).
- Anonymous identification strategy (cookie vs IP/user-agent hash).
- Whether to include logged-out users in the count.

## Risks
- Extra DB writes (one per client per interval).
- Abuse/spam (consider minimal rate limiting).

## Abuse prevention
1. Rate limit `/heartbeat` (e.g., 1 request per 30–60 seconds per IP + user-agent).
2. Ignore rapid repeats by updating `last_seen_at` only if the previous update was older than N seconds.
3. Cap active session rows per IP to prevent flooding.
4. Optionally filter known bots by user-agent.
