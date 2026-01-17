# Transaction handling plan

Goal: overhaul roster-move handling using MLB transactions, with clear options, pros/cons, and implementation steps.

## Option 1: Transactions-only eligibility

**Description**
Use MLB transactions to mark players as eligible/ineligible without running daily full roster snapshots.

**Pros**
- Minimal API calls and fast nightly sync.
- Directly reflects real-world events.

**Cons**
- Requires accurate transaction type mapping.
- Risk of missing data if transactions are delayed or incomplete.

**Implementation steps**
1. Add a `mlb_transactions` table (idempotent by transaction ID).
2. Create a nightly job to pull a 7-day window of transactions.
3. Map transaction types/descriptions to eligibility changes.
4. When a player becomes ineligible, remove them from `team_player` and set `has_empty_roster_spot`.
5. When a player becomes eligible again, set `players.is_active = 1` (do not auto-assign).
6. Record all changes in the audit trail.

---

## Option 2: Transactions + weekly roster reconciliation

**Description**
Use transactions nightly and reconcile against a full roster snapshot weekly.

**Pros**
- Catches transaction gaps and data inconsistencies.
- Maintains higher confidence in eligibility state.

**Cons**
- More complex; still requires full roster pulls.

**Implementation steps**
1. Implement Option 1.
2. Add a weekly roster snapshot sync (Sunday night).
3. Compare snapshot vs. current `players.is_active` and reconcile differences.
4. Log reconciliations to a weekly report.

---

## Option 3: Transactions-triggered sync

**Description**
Only run a full roster sync when a transaction indicates a 40-man change.

**Pros**
- Reduces full roster pulls to only when needed.
- Keeps roster states more accurate than transactions-only.

**Cons**
- Requires reliable detection of 40-man-related transaction types.

**Implementation steps**
1. Implement Option 1.
2. Maintain a list of transaction types that require full roster refresh.
3. If any such transaction appears in the nightly window, run a roster snapshot sync.
4. Reconcile differences as needed.

---

## Option 4: Event-sourced ledger + derived state

**Description**
Store every transaction event and derive roster eligibility from the event stream.

**Pros**
- Full auditability and reproducibility.
- Easy to reprocess from scratch.

**Cons**
- Most complex to implement.
- Requires careful ordering and conflict rules.

**Implementation steps**
1. Store transactions in a ledger table.
2. Build a state-derivation process that replays the ledger into `players` status.
3. Add tooling to re-run derivation for any date range.
4. Persist reconciliation logs.

---

## Option 5: Manual admin overrides (with transaction feed)

**Description**
Use transactions for a feed, but let admins decide eligibility updates.

**Pros**
- Maximum control for edge cases.
- Simple implementation.

**Cons**
- Not automated; requires manual work.

**Implementation steps**
1. Display transactions on a new admin page.
2. Provide controls to mark a player eligible/ineligible.
3. Record admin actions in the audit trail.

---

## Recommendation

If you want automation with reliability, Option 2 (transactions + weekly reconciliation) is the best balance. Option 1 is simplest but relies on transaction accuracy.

---

## Transaction mapping rule (2026-01-16 22:25 ET)

For league logic, only map MLB transactions into two outcomes:
- **Add to 40‑man**\n
- **Remove from 40‑man**\n

All other transaction types are ignored for eligibility.
