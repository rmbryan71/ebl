from datetime import date, datetime
import json
import os
from pathlib import Path

import requests

from db import get_connection, ensure_identities
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


def load_stats_fixtures(fixtures_dir, start_date, end_date):
    stats_dir = Path(fixtures_dir) / "stats"
    if not stats_dir.exists():
        return {}
    files = sorted(stats_dir.glob("*.json"))
    stats_by_date = {}
    for file_path in files:
        try:
            fixture_date = datetime.strptime(file_path.stem, "%Y-%m-%d").date()
        except ValueError:
            continue
        if start_date and fixture_date < start_date:
            continue
        if end_date and fixture_date > end_date:
            continue
        payload = json.loads(file_path.read_text(encoding="utf-8"))
        rows = payload.get("stats", payload)
        if isinstance(rows, list):
            stats_by_date[fixture_date] = rows
    return stats_by_date


def populate_2025_stats(replace=True, game_type="R", start_date=None, end_date=None, fixtures_dir=None):
    with get_connection() as conn:
        cursor = conn.cursor()
        ensure_identities(conn, ["stats"])

        cursor.execute("SELECT id FROM teams ORDER BY id")
        team_ids = [row["id"] for row in cursor.fetchall()]
        if not team_ids:
            raise SystemExit("No teams found in ebl.db. Create teams before populating stats.")

        cursor.execute("SELECT player_id, team_id FROM team_player")
        team_map = {row["player_id"]: row["team_id"] for row in cursor.fetchall()}

        cursor.execute("SELECT id, mlb_id FROM players WHERE is_active = 1 ORDER BY id")
        players = cursor.fetchall()

        fixtures_dir = fixtures_dir or os.getenv("FIXTURES_DIR")
        fixture_stats = load_stats_fixtures(fixtures_dir, start_date, end_date) if fixtures_dir else {}

        if replace and players:
            player_ids = [str(row["id"]) for row in players]
            placeholders = ",".join(["%s"] * len(player_ids))
            params = []
            if fixture_stats:
                dates = sorted(fixture_stats.keys())
                if dates:
                    date_clause = "date BETWEEN %s AND %s"
                    params.extend([dates[0].isoformat(), dates[-1].isoformat()])
                else:
                    date_clause = "date >= %s AND date < %s"
                    params.extend(["2025-01-01", "2026-01-01"])
            elif start_date or end_date:
                if start_date and end_date:
                    date_clause = "date BETWEEN %s AND %s"
                    params.extend([start_date.isoformat(), end_date.isoformat()])
                elif start_date:
                    date_clause = "date >= %s"
                    params.append(start_date.isoformat())
                else:
                    date_clause = "date <= %s"
                    params.append(end_date.isoformat())
            else:
                date_clause = "date >= %s AND date < %s"
                params.extend(["2025-01-01", "2026-01-01"])
            params.extend(player_ids)
            delete_sql = f"DELETE FROM stats WHERE {date_clause} AND player_id IN ({placeholders})"
            cursor.execute(delete_sql, params)

        rows = []
        if fixture_stats:
            mlb_to_player = {row["mlb_id"]: row["id"] for row in players}
            for fixture_date, stats_rows in fixture_stats.items():
                for entry in stats_rows:
                    mlb_id = entry.get("mlb_id")
                    if mlb_id is None:
                        continue
                    player_id = mlb_to_player.get(mlb_id)
                    if player_id is None:
                        continue
                    team_id = team_map.get(player_id)
                    if team_id is None:
                        continue
                    offense = int(entry.get("offense", 0) or 0)
                    pitching = int(entry.get("pitching", 0) or 0)
                    rows.append((player_id, team_id, fixture_date.isoformat(), offense, pitching))
        else:
            for player in players:
                player_id = player["id"]
                mlb_id = player["mlb_id"]
                team_id = team_map.get(player_id)
                if team_id is None:
                    continue

                daily = {}
                for split in fetch_game_logs(mlb_id, "hitting", 2025, game_type):
                    date_value = split.get("date")
                    if not date_value:
                        continue
                    game_date = datetime.strptime(date_value, "%Y-%m-%d").date()
                    if start_date and game_date < start_date:
                        continue
                    if end_date and game_date > end_date:
                        continue
                    stat = split.get("stat", {})
                    offense = calculate_offense(stat)
                    entry = daily.setdefault(date_value, {"offense": 0, "pitching": 0})
                    entry["offense"] += offense

                for split in fetch_game_logs(mlb_id, "pitching", 2025, game_type):
                    date_value = split.get("date")
                    if not date_value:
                        continue
                    game_date = datetime.strptime(date_value, "%Y-%m-%d").date()
                    if start_date and game_date < start_date:
                        continue
                    if end_date and game_date > end_date:
                        continue
                    stat = split.get("stat", {})
                    outs = innings_to_outs(stat.get("inningsPitched"))
                    entry = daily.setdefault(date_value, {"offense": 0, "pitching": 0})
                    entry["pitching"] += outs

                for date_value, totals in daily.items():
                    rows.append(
                        (
                            player_id,
                            team_id,
                            date_value,
                            totals["offense"],
                            totals["pitching"],
                        )
                    )

        if rows:
            cursor.executemany(
                """
                INSERT INTO stats (player_id, team_id, date, offense, pitching)
                VALUES (%s, %s, %s, %s, %s)
                """,
                rows,
            )

        conn.commit()

    print(f"Inserted {len(rows)} daily stat rows.")


if __name__ == "__main__":
    start_input = input("Start date (YYYY-MM-DD, blank for season): ").strip()
    end_input = input("End date (YYYY-MM-DD, blank for season): ").strip()
    start_date = parse_date(start_input, "start")
    end_date = parse_date(end_input, "end")
    if start_date and end_date and end_date < start_date:
        raise SystemExit("End date must be on or after start date.")
    fixtures_dir = os.getenv("FIXTURES_DIR")
    populate_2025_stats(start_date=start_date, end_date=end_date, fixtures_dir=fixtures_dir)
