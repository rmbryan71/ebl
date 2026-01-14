import sqlite3
from datetime import datetime, timedelta


DB_PATH = "ebl.db"


OFFENSE_POINTS = {1: 10, 2: 8, 3: 4}
DEFENSE_POINTS = {1: 10, 2: 8, 3: 4}


def week_start(date_value):
    return date_value - timedelta(days=date_value.weekday())


def week_end(date_value):
    return week_start(date_value) + timedelta(days=6)


def load_weekly_totals(conn):
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT team_id, date, offense, pitching
        FROM stats
        """
    )
    weekly = {}
    for row in cursor.fetchall():
        try:
            game_date = datetime.strptime(row["date"], "%Y-%m-%d").date()
        except ValueError:
            continue
        start = week_start(game_date)
        totals = weekly.setdefault(start, {})
        team_totals = totals.setdefault(
            row["team_id"], {"offense": 0, "pitching": 0}
        )
        team_totals["offense"] += row["offense"] or 0
        team_totals["pitching"] += row["pitching"] or 0
    return weekly


def award_points_for_category(team_totals, points_map):
    ordered = sorted(
        team_totals.items(), key=lambda item: (item[1], item[0]), reverse=True
    )
    awards = []
    position = 1
    index = 0
    while index < len(ordered) and position <= 3:
        total = ordered[index][1]
        tied = []
        while index < len(ordered) and ordered[index][1] == total:
            tied.append(ordered[index][0])
            index += 1
        if position <= 3:
            points = points_map[position]
            awards.extend([(team_id, points) for team_id in tied])
        position += len(tied)
    return awards


def score_weeks(db_path=DB_PATH):
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM points")

        weekly = load_weekly_totals(conn)
        point_rows = []
        for week_start_date, team_totals in weekly.items():
            week_end_date = week_end(week_start_date)

            offense_totals = {team_id: totals["offense"] for team_id, totals in team_totals.items()}
            pitching_totals = {team_id: totals["pitching"] for team_id, totals in team_totals.items()}

            for team_id, points in award_points_for_category(offense_totals, OFFENSE_POINTS):
                point_rows.append(
                    (team_id, week_end_date.isoformat(), points, "offense")
                )

            for team_id, points in award_points_for_category(pitching_totals, DEFENSE_POINTS):
                point_rows.append(
                    (team_id, week_end_date.isoformat(), points, "defense")
                )

        if point_rows:
            cursor.executemany(
                """
                INSERT INTO points (team_id, date, value, type)
                VALUES (?, ?, ?, ?)
                """,
                point_rows,
            )
        conn.commit()

    print(f"Awarded {len(point_rows)} point rows.")


if __name__ == "__main__":
    score_weeks()
