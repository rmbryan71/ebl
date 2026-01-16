import argparse
import json
import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from db import get_connection
import scoring


def load_module(module_name, filename):
    module_path = ROOT / filename
    spec = __import__("importlib.util").util.spec_from_file_location(module_name, module_path)
    module = __import__("importlib.util").util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


roster_sync = load_module("roster_sync", "roster-sync.py")
stats_populate = load_module("stats_populate", "stats-populate.py")
roster_moves = load_module("roster_moves", "roster-moves.py")


EASTERN_TZ = ZoneInfo("America/New_York")


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


def assert_equal(label, actual, expected, failures):
    if actual != expected:
        failures.append(f"{label}: expected {expected}, got {actual}")


def assert_true(label, condition, failures):
    if not condition:
        failures.append(f"{label}: expected true")


def load_expected(path):
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def check_invariants(cursor, failures):
    cursor.execute(
        """
        SELECT team_id, COUNT(*) AS count
        FROM team_player
        GROUP BY team_id
        """
    )
    for row in cursor.fetchall():
        if row["count"] > 4:
            failures.append(f"team {row['team_id']} roster size {row['count']} > 4")

    cursor.execute(
        """
        SELECT player_id, COUNT(*) AS count
        FROM team_player
        GROUP BY player_id
        HAVING COUNT(*) > 1
        """
    )
    duplicates = cursor.fetchall()
    if duplicates:
        failures.append("duplicate player assignments detected")

    cursor.execute(
        """
        SELECT tp.player_id
        FROM team_player tp
        JOIN players p ON p.id = tp.player_id
        WHERE p.is_active != 1
        LIMIT 1
        """
    )
    if cursor.fetchone():
        failures.append("inactive player assigned to team")


def check_expected_rosters(cursor, expected, failures):
    rosters = expected.get("team_rosters")
    if not rosters:
        return
    for team_id, expected_players in rosters.items():
        cursor.execute(
            "SELECT player_id FROM team_player WHERE team_id = %s ORDER BY player_id",
            (int(team_id),),
        )
        actual_players = [row["player_id"] for row in cursor.fetchall()]
        assert_equal(
            f"team {team_id} roster",
            actual_players,
            expected_players,
            failures,
        )


def check_expected_points(cursor, expected, failures):
    points = expected.get("weekly_points")
    if not points:
        return
    for team_id, expected_total in points.items():
        cursor.execute(
            "SELECT COALESCE(SUM(value), 0) AS total FROM points WHERE team_id = %s",
            (int(team_id),),
        )
        actual_total = cursor.fetchone()["total"]
        assert_equal(
            f"team {team_id} total points",
            actual_total,
            expected_total,
            failures,
        )


def main():
    parser = argparse.ArgumentParser(description="Replay 2025 fixtures and assert outcomes.")
    parser.add_argument("--start", required=True, help="Start date YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="End date YYYY-MM-DD")
    parser.add_argument("--fixtures", required=True, help="Base fixtures directory")
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Run roster sync, stats populate, scoring, and roster moves.",
    )
    parser.add_argument("--fail-fast", action="store_true", help="Stop on first failure")
    args = parser.parse_args()

    start_date = parse_date(args.start, "start")
    end_date = parse_date(args.end, "end")
    fixtures_dir = Path(args.fixtures)
    expected_dir = fixtures_dir / "expected"

    if not fixtures_dir.exists():
        raise SystemExit("Fixtures directory not found.")

    failures_by_day = {}

    if args.execute:
        for day in daterange(start_date, end_date):
            roster_sync.sync_phillies_40_man(
                roster_date=day.isoformat(),
                fixtures_dir=fixtures_dir,
            )
            stats_populate.populate_2025_stats(
                start_date=day,
                end_date=day,
                fixtures_dir=str(fixtures_dir),
            )
            if day.weekday() == 6:
                scoring.score_weeks()
                roster_moves.main()

    with get_connection() as conn:
        cursor = conn.cursor()
        for day in daterange(start_date, end_date):
            failures = []
            expected_path = expected_dir / f"{day.isoformat()}.json"
            expected = load_expected(expected_path)

            check_invariants(cursor, failures)
            check_expected_rosters(cursor, expected, failures)
            check_expected_points(cursor, expected, failures)

            if failures:
                failures_by_day[day.isoformat()] = failures
                if args.fail_fast:
                    break

    if failures_by_day:
        print("Simulation failures detected:")
        for day, issues in failures_by_day.items():
            print(f"- {day}")
            for issue in issues:
                print(f"  - {issue}")
        raise SystemExit(1)

    print("Simulation completed with no failures.")


if __name__ == "__main__":
    main()
