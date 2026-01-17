from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from db import ensure_identities, get_connection, set_audit_user_id
from roster_sync import apply_mlb_roster_changes
from scoring import score_weeks
import importlib.util
from simulation_fixtures import (
    load_json_file,
    require_local_simulation,
    validate_manifest,
    validate_roster_fixture,
    validate_stats_fixture,
)


EASTERN_TZ = ZoneInfo("America/New_York")


@dataclass
class WeeklyLog:
    week_start: date
    week_end: date
    points: list[str] = field(default_factory=list)
    roster_moves: list[str] = field(default_factory=list)
    roster_changes: list[str] = field(default_factory=list)
    auto_moves: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    summary: list[str] = field(default_factory=list)

    def write(self, log_dir: Path) -> Path:
        log_dir.mkdir(parents=True, exist_ok=True)
        filename = f"weekly-{self.week_start.isoformat()}_to_{self.week_end.isoformat()}.md"
        path = log_dir / filename
        lines = [
            f"# Weekly simulation log: {self.week_start.isoformat()} to {self.week_end.isoformat()}",
            "",
            "## Summary",
            *(self.summary or ["- No summary entries."]),
            "",
            "## Points",
            *(self.points or ["- No points awarded."]),
            "",
            "## Roster moves",
            *(self.roster_moves or ["- No roster moves processed."]),
            "",
            "## Roster changes",
            *(self.roster_changes or ["- No roster changes detected."]),
            "",
            "## Auto-move actions",
            *(self.auto_moves or ["- No auto-move requests created."]),
            "",
            "## Errors",
            *(self.errors or ["- No errors recorded."]),
            "",
        ]
        path.write_text("\n".join(lines), encoding="utf-8")
        return path


def parse_date(value: str, label: str) -> date:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise SystemExit(f"Invalid {label} date. Use YYYY-MM-DD.") from exc


def load_manifest(fixtures_dir: Path) -> dict[str, Any]:
    manifest_path = fixtures_dir / "manifest.json"
    if not manifest_path.exists():
        raise SystemExit(f"Missing manifest: {manifest_path}")
    manifest = load_json_file(manifest_path)
    validate_manifest(manifest)
    return manifest


def iter_dates(start_date: date, end_date: date):
    current = start_date
    while current <= end_date:
        yield current
        current += timedelta(days=1)


def load_fixture(path: Path, validator) -> dict[str, Any]:
    if not path.exists():
        raise SystemExit(f"Missing fixture: {path}")
    data = load_json_file(path)
    validator(data)
    return data


def ensure_players(conn, roster_players: list[dict], now_ts: str) -> None:
    cursor = conn.cursor()
    cursor.execute("SELECT mlb_id FROM players")
    existing = {row["mlb_id"] for row in cursor.fetchall()}

    new_rows = []
    for player in roster_players:
        mlb_id = player["mlb_player_id"]
        if mlb_id in existing:
            continue
        new_rows.append(
            (
                mlb_id,
                player["name"],
                player["position_code"],
                player["position_name"],
                player["position_type"],
                now_ts,
            )
        )
    if new_rows:
        cursor.executemany(
            """
            INSERT INTO players (
                mlb_id,
                name,
                position_code,
                position_name,
                position_type,
                last_updated,
                is_active
            )
            VALUES (%s, %s, %s, %s, %s, %s, 1)
            ON CONFLICT (mlb_id) DO NOTHING
            """,
            new_rows,
        )

    roster_ids = [player["mlb_player_id"] for player in roster_players]
    cursor.execute(
        """
        UPDATE players
        SET is_active = 1,
            last_updated = %s
        WHERE mlb_id = ANY(%s)
        """,
        (now_ts, roster_ids),
    )
    cursor.execute(
        """
        UPDATE players
        SET is_active = 0,
            last_updated = %s
        WHERE is_active = 1
          AND NOT (mlb_id = ANY(%s))
        """,
        (now_ts, roster_ids),
    )


def insert_stats(conn, day: date, stats_players: list[dict]) -> int:
    cursor = conn.cursor()
    cursor.execute("SELECT player_mlb_id, team_id FROM team_player")
    team_map = {row["player_mlb_id"]: row["team_id"] for row in cursor.fetchall()}

    cursor.execute("DELETE FROM stats WHERE date = %s", (day.isoformat(),))

    rows = []
    for entry in stats_players:
        mlb_id = entry["mlb_player_id"]
        team_id = team_map.get(mlb_id)
        if team_id is None:
            continue
        rows.append(
            (
                mlb_id,
                team_id,
                day.isoformat(),
                entry["offense"],
                entry["outs"],
            )
        )
    if rows:
        cursor.executemany(
            """
            INSERT INTO stats (player_mlb_id, team_id, date, offense, pitching)
            VALUES (%s, %s, %s, %s, %s)
            """,
            rows,
        )
    return len(rows)


def create_auto_roster_moves(conn, team_ids: list[int], day: date) -> list[str]:
    if not team_ids:
        return []
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT p.mlb_id
        FROM players p
        LEFT JOIN team_player tp ON tp.player_mlb_id = p.mlb_id
        WHERE p.is_active = 1 AND tp.player_mlb_id IS NULL
        ORDER BY p.mlb_id
        """
    )
    available = [row["mlb_id"] for row in cursor.fetchall()]

    log_entries = []
    submitted_at = datetime.combine(day, time(9, 0)).replace(tzinfo=EASTERN_TZ).replace(
        tzinfo=None
    )
    submitted_value = submitted_at.isoformat(sep=" ")

    for team_id in sorted(set(team_ids)):
        cursor.execute(
            """
            UPDATE roster_move_requests
            SET status = 'superseded'
            WHERE team_id = %s AND status = 'pending'
            """,
            (team_id,),
        )
        cursor.execute(
            """
            INSERT INTO roster_move_requests (team_id, submitted, status)
            VALUES (%s, %s, 'pending')
            RETURNING id
            """,
            (team_id, submitted_value),
        )
        request_id = cursor.fetchone()["id"]

        selected = available[:3]
        for priority, player_id in enumerate(selected, start=1):
            cursor.execute(
                """
                INSERT INTO roster_move_request_players (
                    roster_move_request_id,
                    player_mlb_id,
                    action,
                    priority
                )
                VALUES (%s, %s, 'add', %s)
                """,
                (request_id, player_id, priority),
            )
        log_entries.append(
            f"- Team {team_id}: auto-request {request_id} (add choices: {', '.join(str(pid) for pid in selected) or 'none'})"
        )

    return log_entries


def log_points(cursor, week_end: date) -> list[str]:
    cursor.execute(
        """
        SELECT t.name AS team_name, p.type, p.value
        FROM points p
        JOIN teams t ON t.id = p.team_id
        WHERE p.date = %s
        ORDER BY t.name, p.type
        """,
        (week_end.isoformat(),),
    )
    rows = cursor.fetchall()
    if not rows:
        return []
    entries = []
    current = None
    for row in rows:
        if current != row["team_name"]:
            current = row["team_name"]
            entries.append(f"- {current}")
        entries.append(f"  - {row['type']}: {row['value']}")
    return entries


def log_roster_changes(cursor, week_start: date, week_end: date) -> list[str]:
    cursor.execute(
        """
        SELECT change_date, change_type, player_mlb_id
        FROM mlb_roster_changes
        WHERE change_date BETWEEN %s AND %s
        ORDER BY change_date, change_type, player_mlb_id
        """,
        (week_start.isoformat(), week_end.isoformat()),
    )
    rows = cursor.fetchall()
    if not rows:
        return []
    entries = []
    current_date = None
    for row in rows:
        if current_date != row["change_date"]:
            current_date = row["change_date"]
            entries.append(f"- {current_date}")
        entries.append(f"  - {row['change_type']}: {row['player_mlb_id']}")
    return entries


def log_roster_moves(cursor, week_start: date, week_end: date) -> list[str]:
    cursor.execute(
        """
        SELECT r.id, r.team_id, r.status, r.submitted, t.name AS team_name
        FROM roster_move_requests r
        JOIN teams t ON t.id = r.team_id
        WHERE r.submitted >= %s AND r.submitted < %s
        ORDER BY r.submitted
        """,
        (
            datetime.combine(week_start, time.min).isoformat(sep=" "),
            datetime.combine(week_end + timedelta(days=1), time.min).isoformat(sep=" "),
        ),
    )
    requests = cursor.fetchall()
    if not requests:
        return []

    request_ids = [row["id"] for row in requests]
    cursor.execute(
        """
        SELECT rmp.roster_move_request_id, rmp.action, rmp.priority, p.name AS player_name
        FROM roster_move_request_players rmp
        JOIN players p ON p.mlb_id = rmp.player_mlb_id
        WHERE rmp.roster_move_request_id = ANY(%s)
        ORDER BY rmp.roster_move_request_id, rmp.action, rmp.priority NULLS LAST
        """,
        (request_ids,),
    )
    players = cursor.fetchall()
    players_by_request = {}
    for row in players:
        players_by_request.setdefault(row["roster_move_request_id"], []).append(row)

    entries = []
    for request in requests:
        entries.append(f"- {request['team_name']} (request {request['id']}, {request['status']})")
        for player in players_by_request.get(request["id"], []):
            label = f"{player['action']}"
            if player["priority"]:
                label += f" {player['priority']}"
            entries.append(f"  - {label}: {player['player_name']}")
    return entries


def write_error_log(log_dir: Path, errors: list[str]) -> Path:
    log_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(EASTERN_TZ).strftime("%Y-%m-%d_%H%M%S")
    path = log_dir / f"run-{timestamp}.md"
    lines = ["# Simulation errors", ""]
    lines.extend(errors or ["- No errors recorded."])
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def write_season_summary(log_dir: Path, start_date: date, end_date: date) -> Path:
    log_dir.mkdir(parents=True, exist_ok=True)
    path = log_dir / f"season-summary-{start_date.isoformat()}_to_{end_date.isoformat()}.md"
    path.write_text(
        "\n".join(
            [
                f"# Season summary: {start_date.isoformat()} to {end_date.isoformat()}",
                "",
                "- Completed replay run.",
            ]
        ),
        encoding="utf-8",
    )
    return path


def load_module(module_name: str, filename: str):
    path = Path(filename).resolve()
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"Unable to load module from {filename}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay 2025 fixtures into the EBL database.")
    parser.add_argument("--start", required=True, help="Start date (YYYY-MM-DD).")
    parser.add_argument("--end", required=True, help="End date (YYYY-MM-DD).")
    parser.add_argument("--fixtures", default="fixtures/2025", help="Fixture directory.")
    args = parser.parse_args()

    require_local_simulation()

    fixtures_dir = Path(args.fixtures)
    manifest = load_manifest(fixtures_dir)

    start_date = parse_date(args.start, "start")
    end_date = parse_date(args.end, "end")
    if end_date < start_date:
        raise SystemExit("End date must be on or after start date.")

    if start_date.isoformat() < manifest["start_date"] or end_date.isoformat() > manifest["end_date"]:
        raise SystemExit("Requested range is outside the fixture manifest range.")

    error_log_entries: list[str] = []
    weekly_log = None
    prev_roster_ids: set[int] | None = None

    with get_connection() as conn:
        ensure_identities(conn, ["stats", "points", "roster_move_requests", "roster_move_request_players"])
        set_audit_user_id(conn, 0)

        roster_moves = load_module("roster_moves", "roster-moves.py")

        for day in iter_dates(start_date, end_date):
            if weekly_log is None:
                week_start = day - timedelta(days=day.weekday())
                week_end = week_start + timedelta(days=6)
                weekly_log = WeeklyLog(week_start=week_start, week_end=week_end)

            roster_path = fixtures_dir / "roster" / f"{day.isoformat()}.json"
            stats_path = fixtures_dir / "stats" / f"{day.isoformat()}.json"
            roster_fixture = load_fixture(roster_path, validate_roster_fixture)
            stats_fixture = load_fixture(stats_path, validate_stats_fixture)

            roster_players = roster_fixture["players"]
            roster_ids = set(roster_fixture["mlb_player_ids"])
            now_ts = datetime.now(EASTERN_TZ).replace(tzinfo=None).isoformat(sep=" ")

            try:
                with conn.transaction():
                    ensure_players(conn, roster_players, now_ts)

                    before_set = prev_roster_ids or set()
                    removed_ids = sorted(before_set - roster_ids)
                    removed_team_rows = []
                    if removed_ids:
                        cursor = conn.cursor()
                        cursor.execute(
                            """
                            SELECT team_id, player_mlb_id
                            FROM team_player
                            WHERE player_mlb_id = ANY(%s)
                            """,
                            (removed_ids,),
                        )
                        removed_team_rows = cursor.fetchall()

                    apply_mlb_roster_changes(
                        conn,
                        before_set,
                        roster_ids,
                        day.isoformat(),
                        source="fixture",
                    )

                    if removed_team_rows:
                        team_ids = [row["team_id"] for row in removed_team_rows]
                        weekly_log.auto_moves.extend(create_auto_roster_moves(conn, team_ids, day))

                    inserted = insert_stats(conn, day, stats_fixture["players"])
                    weekly_log.summary.append(
                        f"- {day.isoformat()}: inserted {inserted} stat rows."
                    )
            except Exception as exc:
                message = f"- {day.isoformat()}: {exc}"
                weekly_log.errors.append(message)
                error_log_entries.append(message)
                error_log_path = write_error_log(
                    Path("logs/simulations/errors"), error_log_entries
                )
                weekly_log.summary.append(f"- Wrote error log to {error_log_path}")
                weekly_log.write(Path("logs/simulations"))
                raise

            prev_roster_ids = roster_ids

            if day.weekday() == 6:
                score_weeks()
                roster_moves.main()

                cursor = conn.cursor()
                weekly_log.points.extend(log_points(cursor, day))
                weekly_log.roster_changes.extend(log_roster_changes(cursor, weekly_log.week_start, day))
                weekly_log.roster_moves.extend(log_roster_moves(cursor, weekly_log.week_start, day))

                weekly_log.write(Path("logs/simulations"))
                weekly_log = None

        if weekly_log:
            cursor = conn.cursor()
            weekly_log.roster_changes.extend(
                log_roster_changes(cursor, weekly_log.week_start, weekly_log.week_end)
            )
            weekly_log.roster_moves.extend(
                log_roster_moves(cursor, weekly_log.week_start, weekly_log.week_end)
            )
            weekly_log.write(Path("logs/simulations"))

    write_season_summary(Path("logs/simulations"), start_date, end_date)


if __name__ == "__main__":
    main()
