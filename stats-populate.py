import sqlite3

import requests

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


def populate_2025_stats(db_path="ebl.db", replace=True, game_type="R"):
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM teams ORDER BY id")
        team_ids = [row[0] for row in cursor.fetchall()]
        if not team_ids:
            raise SystemExit("No teams found in ebl.db. Create teams before populating stats.")

        cursor.execute("SELECT player_id, team_id FROM team_player")
        team_map = {row[0]: row[1] for row in cursor.fetchall()}

        cursor.execute("SELECT id, mlb_id FROM players WHERE is_active = 1 ORDER BY id")
        players = cursor.fetchall()

        if replace and players:
            player_ids = [str(row["id"]) for row in players]
            cursor.execute(
                "DELETE FROM stats WHERE date LIKE '2025-%' "
                f"AND player_id IN ({','.join(['?'] * len(player_ids))})",
                player_ids,
            )

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
                stat = split.get("stat", {})
                offense = calculate_offense(stat)
                entry = daily.setdefault(date, {"offense": 0, "pitching": 0})
                entry["offense"] += offense

            for split in fetch_game_logs(mlb_id, "pitching", 2025, game_type):
                date = split.get("date")
                if not date:
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
                """
                INSERT INTO stats (player_id, team_id, date, offense, pitching)
                VALUES (?, ?, ?, ?, ?)
                """,
                rows,
            )

        conn.commit()

    print(f"Inserted {len(rows)} daily stat rows.")


if __name__ == "__main__":
    populate_2025_stats("ebl.db")
