from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests
from pymlb_statsapi import api

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from simulation_fixtures import (
    SCHEMA_VERSION,
    require_local_simulation,
    validate_manifest,
    validate_roster_fixture,
    validate_stats_fixture,
)

PHILLIES_TEAM_ID = 143


def parse_date(value: str, label: str) -> date:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise SystemExit(f"Invalid {label} date. Use YYYY-MM-DD.") from exc


def fetch_roster_players(day: date) -> list[dict]:
    roster_resp = api.Team.roster(
        teamId=PHILLIES_TEAM_ID,
        rosterType="40Man",
        date=day.isoformat(),
    )
    roster_json = roster_resp.json()
    roster_rows = roster_json.get("roster", [])
    players = []
    seen_ids = set()
    for row in roster_rows:
        person = row.get("person", {})
        mlb_id = int(person["id"])
        if mlb_id in seen_ids:
            continue
        seen_ids.add(mlb_id)
        position = row.get("position", {})
        players.append(
            {
                "mlb_player_id": mlb_id,
                "name": person.get("fullName") or "",
                "position_code": position.get("code"),
                "position_name": position.get("name"),
                "position_type": position.get("type"),
            }
        )
    players.sort(key=lambda item: item["mlb_player_id"])
    return players


def fetch_game_logs(person_id: int, group: str, season: int, game_type: str = "R") -> list[dict]:
    url = f"https://statsapi.mlb.com/api/v1/people/{person_id}/stats"
    params = {
        "stats": "gameLog",
        "group": group,
        "season": str(season),
        "gameType": game_type,
    }
    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()
    data = response.json()
    stats = data.get("stats", [])
    if not stats:
        return []
    return stats[0].get("splits", [])


def innings_to_outs(innings_pitched: str | None) -> int:
    if not innings_pitched:
        return 0
    try:
        whole, _, frac = innings_pitched.partition(".")
        outs = int(whole) * 3
        if frac:
            outs += int(frac)
        return outs
    except ValueError:
        return 0


def calculate_offense(stat_line: dict) -> int:
    return (
        int(stat_line.get("totalBases", 0))
        + int(stat_line.get("baseOnBalls", 0))
        + int(stat_line.get("hitByPitch", 0))
        + int(stat_line.get("stolenBases", 0))
    )


def build_daily_stats(mlb_id: int, day: date, season: int = 2025) -> tuple[int, int]:
    offense_total = 0
    outs_total = 0
    day_str = day.isoformat()

    for split in fetch_game_logs(mlb_id, "hitting", season):
        if split.get("date") != day_str:
            continue
        stat = split.get("stat", {})
        offense_total += calculate_offense(stat)

    for split in fetch_game_logs(mlb_id, "pitching", season):
        if split.get("date") != day_str:
            continue
        stat = split.get("stat", {})
        outs_total += innings_to_outs(stat.get("inningsPitched"))

    return offense_total, outs_total


def write_manifest(out_dir: Path, start_date: date, end_date: date) -> None:
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "season": start_date.year,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "source": "mlb_statsapi",
        "notes": "",
    }
    validate_manifest(manifest)
    path = out_dir / "manifest.json"
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")


def write_roster_fixture(out_dir: Path, day: date, roster_players: list[dict]) -> None:
    roster_ids = [player["mlb_player_id"] for player in roster_players]
    roster_payload = {
        "date": day.isoformat(),
        "team_id": PHILLIES_TEAM_ID,
        "mlb_player_ids": roster_ids,
        "players": roster_players,
    }
    validate_roster_fixture(roster_payload)
    path = out_dir / "roster" / f"{day.isoformat()}.json"
    path.write_text(json.dumps(roster_payload, indent=2, sort_keys=True), encoding="utf-8")


def write_stats_fixture(out_dir: Path, day: date, players: list[dict]) -> None:
    stats_payload = {
        "date": day.isoformat(),
        "players": players,
    }
    validate_stats_fixture(stats_payload)
    path = out_dir / "stats" / f"{day.isoformat()}.json"
    path.write_text(json.dumps(stats_payload, indent=2, sort_keys=True), encoding="utf-8")


def capture_range(start_date: date, end_date: date, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "roster").mkdir(parents=True, exist_ok=True)
    (out_dir / "stats").mkdir(parents=True, exist_ok=True)

    write_manifest(out_dir, start_date, end_date)

    current = start_date
    while current <= end_date:
        roster_players = fetch_roster_players(current)
        roster_ids = [player["mlb_player_id"] for player in roster_players]
        write_roster_fixture(out_dir, current, roster_players)

        players = []
        for mlb_id in roster_ids:
            offense, outs = build_daily_stats(mlb_id, current)
            if offense == 0 and outs == 0:
                continue
            players.append(
                {
                    "mlb_player_id": mlb_id,
                    "outs": outs,
                    "offense": offense,
                }
            )
        write_stats_fixture(out_dir, current, players)

        print(f"Captured {current.isoformat()} ({len(roster_ids)} roster, {len(players)} stats)")
        current += timedelta(days=1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Capture 2025 fixtures from MLB APIs.")
    parser.add_argument("--start", required=True, help="Start date (YYYY-MM-DD).")
    parser.add_argument("--end", required=True, help="End date (YYYY-MM-DD).")
    parser.add_argument("--out", default="fixtures/2025", help="Output directory.")
    args = parser.parse_args()

    require_local_simulation()

    start_date = parse_date(args.start, "start")
    end_date = parse_date(args.end, "end")
    if end_date < start_date:
        raise SystemExit("End date must be on or after start date.")

    capture_range(start_date, end_date, Path(args.out))


if __name__ == "__main__":
    main()
