import os
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import requests
from pymlb_statsapi import api

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from db import get_connection


PHILLIES_TEAM_ID = 143


def fetch_game_logs(person_id, group, season, game_type="R"):
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


def innings_to_outs(innings_pitched):
    if not innings_pitched:
        return 0
    try:
        whole, dot, frac = innings_pitched.partition(".")
        outs = int(whole) * 3
        if frac:
            outs += int(frac)
        return outs
    except ValueError:
        return 0


def calculate_offense(stat_line):
    return (
        int(stat_line.get("totalBases", 0))
        + int(stat_line.get("baseOnBalls", 0))
        + int(stat_line.get("hitByPitch", 0))
        + int(stat_line.get("stolenBases", 0))
    )


def parse_date(value, label):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise SystemExit(f"Invalid {label} date. Use YYYY-MM-DD.") from exc


def daterange(start_date, end_date):
    current = start_date
    while current <= end_date:
        yield current
        current += timedelta(days=1)


def load_players():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, mlb_id FROM players WHERE mlb_id IS NOT NULL")
        return cursor.fetchall()


def write_roster_fixture(out_dir, fixture_date):
    roster_resp = api.Team.roster(
        teamId=PHILLIES_TEAM_ID,
        rosterType="40Man",
        date=fixture_date.isoformat(),
    )
    roster_json = roster_resp.json()
    roster_rows = roster_json.get("roster", [])
    mlb_ids = [int(row["person"]["id"]) for row in roster_rows]
    people = []
    for mlb_id in mlb_ids:
        person_resp = api.Person.person(personIds=mlb_id)
        people.extend(person_resp.json().get("people", []))
    payload = {"roster": roster_rows, "people": people}
    out_path = out_dir / "roster" / f"{fixture_date.isoformat()}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json_dumps(payload),
        encoding="utf-8",
    )


def build_stats_by_date(players, season=2025, game_type="R", date_filter=None):
    stats_by_date = {}
    for player in players:
        mlb_id = player["mlb_id"]
        daily = {}
        for split in fetch_game_logs(mlb_id, "hitting", season, game_type):
            date_value = split.get("date")
            if not date_value:
                continue
            if date_filter and date_value not in date_filter:
                continue
            stat = split.get("stat", {})
            offense = calculate_offense(stat)
            entry = daily.setdefault(date_value, {"offense": 0, "pitching": 0})
            entry["offense"] += offense

        for split in fetch_game_logs(mlb_id, "pitching", season, game_type):
            date_value = split.get("date")
            if not date_value:
                continue
            if date_filter and date_value not in date_filter:
                continue
            stat = split.get("stat", {})
            outs = innings_to_outs(stat.get("inningsPitched"))
            entry = daily.setdefault(date_value, {"offense": 0, "pitching": 0})
            entry["pitching"] += outs

        for date_value, totals in daily.items():
            stats_by_date.setdefault(date_value, []).append(
                {
                    "mlb_id": mlb_id,
                    "offense": totals["offense"],
                    "pitching": totals["pitching"],
                }
            )
    return stats_by_date


def write_stats_fixtures(out_dir, stats_by_date, start_date, end_date):
    stats_dir = out_dir / "stats"
    stats_dir.mkdir(parents=True, exist_ok=True)
    for day in daterange(start_date, end_date):
        day_key = day.isoformat()
        rows = stats_by_date.get(day_key, [])
        out_path = stats_dir / f"{day_key}.json"
        if out_path.exists():
            print(f"Stats {day_key}: skip (exists)")
            continue
        out_path.write_text(json_dumps(rows), encoding="utf-8")
        print(f"Stats {day_key}: written ({len(rows)} rows)")


def json_dumps(data):
    import json

    return json.dumps(data, indent=2, sort_keys=True)


def main():
    start_input = input("Start date (YYYY-MM-DD): ").strip()
    end_input = input("End date (YYYY-MM-DD): ").strip()
    start_date = parse_date(start_input, "start")
    end_date = parse_date(end_input, "end")
    if not start_date or not end_date:
        raise SystemExit("Start and end dates are required.")
    if end_date < start_date:
        raise SystemExit("End date must be on or after start date.")

    out_dir = Path(os.getenv("FIXTURES_DIR", ROOT / "fixtures" / "2025"))
    players = load_players()
    if not players:
        raise SystemExit("No players found in database.")

    stats_dir = out_dir / "stats"
    missing_stat_dates = []
    for day in daterange(start_date, end_date):
        out_path = stats_dir / f"{day.isoformat()}.json"
        if not out_path.exists():
            missing_stat_dates.append(day.isoformat())

    if missing_stat_dates:
        print("Building stats snapshots...")
        stats_by_date = build_stats_by_date(players, date_filter=set(missing_stat_dates))
        write_stats_fixtures(out_dir, stats_by_date, start_date, end_date)
    else:
        print("Stats fixtures already up to date.")

    print("Building roster snapshots...")
    for day in daterange(start_date, end_date):
        out_path = out_dir / "roster" / f"{day.isoformat()}.json"
        if out_path.exists():
            print(f"Roster {day.isoformat()}: skip (exists)")
            continue
        write_roster_fixture(out_dir, day)
        print(f"Roster {day.isoformat()}: written")
        time.sleep(0.1)

    print(f"Fixtures written to {out_dir}")


if __name__ == "__main__":
    main()
