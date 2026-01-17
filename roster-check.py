import time
from datetime import datetime
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from zoneinfo import ZoneInfo

from db import get_connection, set_audit_user_id

ROOT = Path(__file__).resolve().parent
EASTERN_TZ = ZoneInfo("America/New_York")
MAX_RETRIES = 3


def load_roster_sync_module():
    module_path = ROOT / "roster-sync.py"
    spec = spec_from_file_location("roster_sync", module_path)
    module = module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def fetch_active_mlb_ids(conn):
    cursor = conn.cursor()
    cursor.execute("SELECT mlb_id FROM players WHERE is_active = 1")
    return {row["mlb_id"] for row in cursor.fetchall()}


def fetch_roster_ids_with_retry(roster_date=None):
    roster_sync = load_roster_sync_module()
    for attempt in range(MAX_RETRIES):
        try:
            return roster_sync.fetch_roster_mlb_ids(roster_date=roster_date)
        except Exception:
            if attempt == MAX_RETRIES - 1:
                raise
            time.sleep(2 ** attempt)
    return []


def run_checker(roster_date=None):
    roster_ids = fetch_roster_ids_with_retry(roster_date=roster_date)
    if not roster_ids:
        print("Roster check: no roster IDs returned.")
        return

    with get_connection() as conn:
        before_set = fetch_active_mlb_ids(conn)

    if set(roster_ids) == before_set:
        print("Roster check: no changes detected.")
        return

    roster_sync = load_roster_sync_module()
    for attempt in range(MAX_RETRIES):
        try:
            with get_connection() as conn:
                set_audit_user_id(conn, 0)
                before_set = fetch_active_mlb_ids(conn)
                roster_sync.sync_players(conn, roster_date=roster_date, roster_ids=roster_ids)
                after_set = fetch_active_mlb_ids(conn)
                change_date = datetime.now(EASTERN_TZ).date()
                roster_sync.apply_mlb_roster_changes(conn, before_set, after_set, change_date)
                conn.commit()
            print("Roster check: changes applied.")
            return
        except Exception:
            if attempt == MAX_RETRIES - 1:
                raise
            time.sleep(2 ** attempt)


if __name__ == "__main__":
    run_checker()
