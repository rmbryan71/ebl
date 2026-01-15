from datetime import datetime

import requests

from db import get_connection, param_placeholder, using_postgres
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


def populate_2025_stats(db_path="ebl.db", replace=True, game_type="R", start_date=None, end_date=None):
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        ph = param_placeholder()

        cursor.execute("SELECT id FROM teams ORDER BY id")
        team_ids = [row["id"] for row in cursor.fetchall()]
        if not team_ids:
            raise SystemExit("No teams found in ebl.db. Create teams before populating stats.")

        cursor.execute("SELECT player_id, team_id FROM team_player")
        team_map = {row["player_id"]: row["team_id"] for row in cursor.fetchall()}

        cursor.execute("SELECT id, mlb_id FROM players WHERE is_active = 1 ORDER BY id")
        players = cursor.fetchall()

        if replace and players:
            player_ids = [str(row["id"]) for row in players]
            placeholders = ",".join([ph] * len(player_ids))
            params = []
            if start_date or end_date:
                if start_date and end_date:
                    date_clause = f"date BETWEEN {ph} AND {ph}"
                    params.extend([start_date.isoformat(), end_date.isoformat()])
                elif start_date:
                    date_clause = f"date >= {ph}"
                    params.append(start_date.isoformat())
                else:
                    date_clause = f"date <= {ph}"
                    params.append(end_date.isoformat())
            else:
                if using_postgres():
                    date_clause = "CAST(date AS TEXT) LIKE '2025-%%'"
                else:
                    date_clause = "date LIKE '2025-%'"
            params.extend(player_ids)
            delete_sql = f"DELETE FROM stats WHERE {date_clause} AND player_id IN ({placeholders})"
            cursor.execute(delete_sql, params)

        rows = []
        for player in players:
            player_id = player["id"]
            mlb_id = player["mlb_id"]
            team_id = team_map.get(player_id)
            if team_id is None:
                continue

            daily = {}
            for split in fetch_game_logs(mlb_id, "hitting", 2025, game_type):
                date = split.get("date")
                if not date:
                    continue
                game_date = datetime.strptime(date, "%Y-%m-%d").date()
                if start_date and game_date < start_date:
                    continue
                if end_date and game_date > end_date:
                    continue
                stat = split.get("stat", {})
                offense = calculate_offense(stat)
                entry = daily.setdefault(date, {"offense": 0, "pitching": 0})
                entry["offense"] += offense

            for split in fetch_game_logs(mlb_id, "pitching", 2025, game_type):
                date = split.get("date")
                if not date:
                    continue
                game_date = datetime.strptime(date, "%Y-%m-%d").date()
                if start_date and game_date < start_date:
                    continue
                if end_date and game_date > end_date:
                    continue
                stat = split.get("stat", {})
                outs = innings_to_outs(stat.get("inningsPitched"))
                entry = daily.setdefault(date, {"offense": 0, "pitching": 0})
                entry["pitching"] += outs

            for date, totals in daily.items():
                rows.append(
                    (
                        player_id,
                        team_id,
                        date,
                        totals["offense"],
                        totals["pitching"],
                    )
                )

        if rows:
            cursor.executemany(
                f"""
                INSERT INTO stats (player_id, team_id, date, offense, pitching)
                VALUES ({ph}, {ph}, {ph}, {ph}, {ph})
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
    populate_2025_stats("ebl.db", start_date=start_date, end_date=end_date)
