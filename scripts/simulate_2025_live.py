import argparse
import sys
from datetime import date, datetime, timedelta
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from db import get_connection

LOGS_DIR = ROOT / "logs" / "simulations"


def load_module(module_name, filename):
    module_path = ROOT / filename
    spec = spec_from_file_location(module_name, module_path)
    module = module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def parse_date(value, label):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise SystemExit(f"Invalid {label} date. Use YYYY-MM-DD.") from exc


def daterange(start_date, end_date):
    current = start_date
    while current <= end_date:
        yield current
        current += timedelta(days=1)


def week_start(day):
    return day - timedelta(days=day.weekday())


def week_end(day):
    return week_start(day) + timedelta(days=6)


def week_label(day):
    start = week_start(day)
    end = week_end(day)
    return f"{start.isoformat()} to {end.isoformat()}"


def count_points_for_week(conn, end_day):
    cursor = conn.cursor()
    cursor.execute(
        "SELECT COUNT(*) AS count FROM points WHERE date = %s",
        (end_day.isoformat(),),
    )
    return cursor.fetchone()["count"]


def count_roster_moves_for_week(conn, start_day, end_day):
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT
            SUM(CASE WHEN status = 'processed' THEN 1 ELSE 0 END) AS processed,
            SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS failed,
            SUM(CASE WHEN status = 'superseded' THEN 1 ELSE 0 END) AS superseded
        FROM roster_move_requests
        WHERE submitted >= %s AND submitted < %s
        """,
        (start_day.isoformat(), (end_day + timedelta(days=1)).isoformat()),
    )
    row = cursor.fetchone()
    return {
        "processed": row["processed"] or 0,
        "failed": row["failed"] or 0,
        "superseded": row["superseded"] or 0,
    }


def write_weekly_log(day):
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    start_day = week_start(day)
    end_day = week_end(day)

    with get_connection() as conn:
        points_count = count_points_for_week(conn, end_day)
        move_counts = count_roster_moves_for_week(conn, start_day, end_day)

    log_path = LOGS_DIR / f"simulation-{end_day.isoformat()}.md"
    lines = [
        f"# 2025 simulation week ending {end_day.isoformat()}",
        "",
        f"- Week: {start_day.isoformat()} to {end_day.isoformat()}",
        f"- Points rows awarded: {points_count}",
        (
            "- Roster moves: "
            f"processed={move_counts['processed']}, "
            f"failed={move_counts['failed']}, "
            f"superseded={move_counts['superseded']}"
        ),
        "",
    ]
    log_path.write_text("\n".join(lines), encoding="utf-8")
    return log_path


def run_day(day, dry_run, roster_sync, stats_populate, scoring, roster_moves):
    label = day.isoformat()
    if dry_run:
        print(f"[{label}] dry-run: roster sync + stats populate")
    else:
        with get_connection() as conn:
            roster_sync.sync_players(conn, roster_date=label)
            conn.commit()
        stats_populate.populate_2025_stats(start_date=day, end_date=day)

    if day.weekday() == 6:
        if dry_run:
            print(f"[{label}] dry-run: scoring + roster moves + weekly log")
            return
        scoring.score_weeks()
        roster_moves.main()
        log_path = write_weekly_log(day)
        print(f"[{label}] wrote weekly log {log_path}")


def main():
    parser = argparse.ArgumentParser(description="Simulate 2025 season using live MLB API calls.")
    parser.add_argument("--start", required=True, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", required=True, help="End date (YYYY-MM-DD)")
    parser.add_argument("--dry-run", action="store_true", help="Log actions without writing data.")
    args = parser.parse_args()

    start_date = parse_date(args.start, "start")
    end_date = parse_date(args.end, "end")
    if end_date < start_date:
        raise SystemExit("End date must be on or after start date.")

    roster_sync = load_module("roster_sync", "roster-sync.py")
    stats_populate = load_module("stats_populate", "stats-populate.py")
    scoring = load_module("scoring", "scoring.py")
    roster_moves = load_module("roster_moves", "roster-moves.py")

    print(f"Simulating {start_date.isoformat()} to {end_date.isoformat()} ({week_label(start_date)})")
    for day in daterange(start_date, end_date):
        run_day(day, args.dry_run, roster_sync, stats_populate, scoring, roster_moves)


if __name__ == "__main__":
    main()
