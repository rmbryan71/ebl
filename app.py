from collections import defaultdict
from datetime import datetime, timedelta
import sqlite3

from flask import Flask, render_template, request


DB_PATH = "ebl.db"

app = Flask(__name__)


def load_roster(db_path=DB_PATH):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            t.name AS team_name,
            p.id AS player_id,
            p.name,
            p.position_name,
            p.is_active
        FROM players p
        LEFT JOIN team_player tp ON tp.player_id = p.id
        LEFT JOIN teams t ON t.id = tp.team_id
        WHERE p.is_active = 1
        ORDER BY t.name IS NULL, t.name, p.name
    """)
    rows = cursor.fetchall()
    conn.close()

    grouped = defaultdict(list)
    for row in rows:
        if row["team_name"] is None:
            continue
        position_name = row["position_name"] or ""
        display_position = "Pitcher" if position_name == "Pitcher" else "Hitter"
        row_dict = dict(row)
        row_dict["display_position"] = display_position
        grouped[row["team_name"]].append(row_dict)

    teams = [{"name": name, "players": grouped[name]} for name in sorted(grouped.keys())]
    total_players = sum(len(team["players"]) for team in teams)

    return teams, total_players


def load_team_stats(team_id=None, week_start=None, db_path=DB_PATH):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT id, name FROM teams ORDER BY name")
    teams = cursor.fetchall()
    if not teams:
        conn.close()
        return [], None, [], None

    selected_team_id = team_id or teams[0]["id"]
    cursor.execute(
        "SELECT DISTINCT date FROM stats WHERE team_id = ? ORDER BY date DESC",
        (selected_team_id,),
    )
    dates = []
    for row in cursor.fetchall():
        try:
            dates.append(datetime.strptime(row["date"], "%Y-%m-%d").date())
        except ValueError:
            continue
    week_starts = sorted({date - timedelta(days=date.weekday()) for date in dates}, reverse=True)

    selected_week_start = None
    if week_start:
        try:
            parsed = datetime.strptime(week_start, "%Y-%m-%d").date()
            if parsed in week_starts:
                selected_week_start = parsed
        except ValueError:
            selected_week_start = None
    if selected_week_start is None and week_starts:
        selected_week_start = week_starts[0]

    params = [selected_team_id]
    date_filter = ""
    if selected_week_start:
        week_end = selected_week_start + timedelta(days=6)
        date_filter = "AND s.date BETWEEN ? AND ?"
        params.extend([selected_week_start.isoformat(), week_end.isoformat()])
    cursor.execute(
        """
        SELECT
            s.date,
            s.offense,
            s.pitching,
            p.name AS player_name
        FROM stats s
        JOIN players p ON p.id = s.player_id
        WHERE s.team_id = ?
        """ + date_filter + """
        ORDER BY s.date DESC, p.name
        """,
        params,
    )
    rows = cursor.fetchall()

    totals_params = [selected_team_id]
    totals_filter = ""
    if selected_week_start:
        week_end = selected_week_start + timedelta(days=6)
        totals_filter = "AND date BETWEEN ? AND ?"
        totals_params.extend([selected_week_start.isoformat(), week_end.isoformat()])

    cursor.execute(
        f"""
        SELECT
            SUM(offense) AS total_offense,
            SUM(pitching) AS total_pitching
        FROM stats
        WHERE team_id = ?
        {totals_filter}
        """,
        totals_params,
    )
    totals = cursor.fetchone()

    conn.close()
    return teams, selected_team_id, rows, totals, week_starts, selected_week_start


@app.route("/")
def roster_view():
    teams, total_players = load_roster()
    return render_template(
        "roster.html",
        teams=teams,
        total_players=total_players,
        team_count=len(teams),
    )


@app.route("/team-stats")
def team_stats():
    team_id = request.args.get("team_id", type=int)
    week_start = request.args.get("week_start")
    teams, selected_team_id, rows, totals, week_starts, selected_week_start = load_team_stats(
        team_id=team_id,
        week_start=week_start,
    )
    return render_template(
        "team-stats.html",
        teams=teams,
        selected_team_id=selected_team_id,
        rows=rows,
        totals=totals,
        week_starts=week_starts,
        selected_week_start=selected_week_start,
    )


def load_leaderboard(week_start=None, db_path=DB_PATH):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT DISTINCT date FROM stats ORDER BY date DESC")
    dates = []
    for row in cursor.fetchall():
        try:
            dates.append(datetime.strptime(row["date"], "%Y-%m-%d").date())
        except ValueError:
            continue
    week_starts = sorted({date - timedelta(days=date.weekday()) for date in dates}, reverse=True)

    selected_week_start = None
    if week_start:
        try:
            parsed = datetime.strptime(week_start, "%Y-%m-%d").date()
            if parsed in week_starts:
                selected_week_start = parsed
        except ValueError:
            selected_week_start = None
    if selected_week_start is None and week_starts:
        selected_week_start = week_starts[0]

    params = []
    date_filter = ""
    if selected_week_start:
        week_end = selected_week_start + timedelta(days=6)
        date_filter = "WHERE s.date BETWEEN ? AND ?"
        params.extend([selected_week_start.isoformat(), week_end.isoformat()])

    cursor.execute(
        f"""
        SELECT
            t.name AS team_name,
            SUM(s.offense) AS total_offense
        FROM stats s
        JOIN teams t ON t.id = s.team_id
        {date_filter}
        GROUP BY t.id
        ORDER BY total_offense DESC, t.name
        """,
        params,
    )
    offense_rows = cursor.fetchall()

    cursor.execute(
        f"""
        SELECT
            t.name AS team_name,
            SUM(s.pitching) AS total_pitching
        FROM stats s
        JOIN teams t ON t.id = s.team_id
        {date_filter}
        GROUP BY t.id
        ORDER BY total_pitching DESC, t.name
        """,
        params,
    )
    pitching_rows = cursor.fetchall()

    conn.close()
    return offense_rows, pitching_rows, week_starts, selected_week_start


@app.route("/leaderboard")
def leaderboard():
    week_start = request.args.get("week_start")
    offense_rows, pitching_rows, week_starts, selected_week_start = load_leaderboard(
        week_start=week_start
    )
    return render_template(
        "leaderboard.html",
        offense_rows=offense_rows,
        pitching_rows=pitching_rows,
        week_starts=week_starts,
        selected_week_start=selected_week_start,
    )


if __name__ == "__main__":
    app.run(debug=True)
