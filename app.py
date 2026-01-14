from collections import defaultdict
from datetime import date, datetime, timedelta
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
            t.id AS team_id,
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

    teams = []
    for name in sorted(grouped.keys()):
        team_id = grouped[name][0].get("team_id")
        teams.append({"id": team_id, "name": name, "players": grouped[name]})
    total_players = sum(len(team["players"]) for team in teams)

    return teams, total_players


def load_team_stats(team_id=None, db_path=DB_PATH):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT id, name FROM teams ORDER BY name")
    teams = cursor.fetchall()
    if not teams:
        conn.close()
        return [], None, [], None

    selected_team_id = team_id or teams[0]["id"]
    params = [selected_team_id]
    date_filter = ""
    cursor.execute(
        """
        SELECT
            s.date,
            s.offense,
            s.pitching,
            p.id AS player_id,
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

    cursor.execute(
        """
        SELECT
            p.id AS player_id,
            p.name AS player_name,
            COALESCE(SUM(s.offense), 0) AS total_offense,
            COALESCE(SUM(s.pitching), 0) AS total_pitching
        FROM team_player tp
        JOIN players p ON p.id = tp.player_id
        LEFT JOIN stats s
            ON s.player_id = p.id AND s.team_id = tp.team_id
        WHERE tp.team_id = ?
        GROUP BY p.id
        ORDER BY p.name
        """,
        (selected_team_id,),
    )
    player_totals = cursor.fetchall()

    totals_params = [selected_team_id]
    totals_filter = ""
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
    selected_team_name = None
    for team in teams:
        if team["id"] == selected_team_id:
            selected_team_name = team["name"]
            break

    return teams, selected_team_id, selected_team_name, rows, totals, player_totals


@app.route("/")
def roster_view():
    teams, total_players = load_roster()
    return render_template(
        "roster.html",
        teams=teams,
        total_players=total_players,
        team_count=len(teams),
    )


@app.route("/team")
def team_stats():
    team_id = request.args.get("team_id", type=int)
    teams, selected_team_id, selected_team_name, rows, totals, player_totals = load_team_stats(
        team_id=team_id
    )
    return render_template(
        "team-stats.html",
        teams=teams,
        selected_team_id=selected_team_id,
        selected_team_name=selected_team_name,
        rows=rows,
        totals=totals,
        player_totals=player_totals,
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
    selected_week_end = None
    if selected_week_start:
        selected_week_end = selected_week_start + timedelta(days=6)
        date_filter = "WHERE s.date BETWEEN ? AND ?"
        params.extend([selected_week_start.isoformat(), selected_week_end.isoformat()])

    cursor.execute(
        f"""
        SELECT
            t.id AS team_id,
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
            t.id AS team_id,
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

    offense_points = {}
    pitching_points = {}
    if selected_week_end and selected_week_end < date.today():
        cursor.execute(
            """
            SELECT team_id, value
            FROM points
            WHERE date = ? AND type = 'offense'
            """,
            (selected_week_end.isoformat(),),
        )
        offense_points = {row["team_id"]: row["value"] for row in cursor.fetchall()}

        cursor.execute(
            """
            SELECT team_id, value
            FROM points
            WHERE date = ? AND type = 'defense'
            """,
            (selected_week_end.isoformat(),),
        )
        pitching_points = {row["team_id"]: row["value"] for row in cursor.fetchall()}

    conn.close()
    return (
        offense_rows,
        pitching_rows,
        week_starts,
        selected_week_start,
        offense_points,
        pitching_points,
    )


@app.route("/week")
def week_view():
    week_start = request.args.get("week_start")
    (
        offense_rows,
        pitching_rows,
        week_starts,
        selected_week_start,
        offense_points,
        pitching_points,
    ) = load_leaderboard(week_start=week_start)
    return render_template(
        "leaderboard.html",
        offense_rows=offense_rows,
        pitching_rows=pitching_rows,
        week_starts=week_starts,
        selected_week_start=selected_week_start,
        offense_points=offense_points,
        pitching_points=pitching_points,
    )


def load_player_details(player_id, db_path=DB_PATH):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            p.id,
            p.name,
            p.birth_date,
            p.position_name,
            t.id AS team_id,
            t.name AS team_name
        FROM players p
        LEFT JOIN team_player tp ON tp.player_id = p.id
        LEFT JOIN teams t ON t.id = tp.team_id
        WHERE p.id = ?
        """,
        (player_id,),
    )
    player = cursor.fetchone()
    if not player:
        conn.close()
        return None, [], None

    cursor.execute(
        "SELECT MIN(date) AS first_date FROM stats WHERE player_id = ?",
        (player_id,),
    )
    first_row = cursor.fetchone()
    year = None
    if first_row and first_row["first_date"]:
        try:
            year = datetime.strptime(first_row["first_date"], "%Y-%m-%d").year
        except ValueError:
            year = None

    stats_rows = []
    if year:
        cursor.execute(
            """
            SELECT date, offense, pitching
            FROM stats
            WHERE player_id = ? AND date LIKE ?
            ORDER BY date DESC
            """,
            (player_id, f"{year}-%"),
        )
        stats_rows = cursor.fetchall()

    conn.close()
    return player, stats_rows, year


@app.route("/player")
def player_view():
    player_id = request.args.get("player_id", type=int)
    if not player_id:
        return render_template("player.html", player=None, stats_rows=[], year=None)

    player, stats_rows, year = load_player_details(player_id)
    return render_template(
        "player.html",
        player=player,
        stats_rows=stats_rows,
        year=year,
    )


def load_season_totals(db_path=DB_PATH):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            t.id AS team_id,
            t.name AS team_name,
            SUM(CASE WHEN p.type = 'offense' THEN p.value ELSE 0 END) AS offense_points,
            SUM(CASE WHEN p.type = 'defense' THEN p.value ELSE 0 END) AS pitching_points,
            SUM(p.value) AS total_points
        FROM teams t
        LEFT JOIN points p ON p.team_id = t.id
        GROUP BY t.id
        ORDER BY total_points DESC, t.name
        """
    )
    rows = cursor.fetchall()
    conn.close()
    return rows


@app.route("/season")
def season_view():
    rows = load_season_totals()
    return render_template("season.html", rows=rows)


def load_available_players(db_path=DB_PATH):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT
            p.id,
            p.name,
            p.position_name,
            p.birth_date
        FROM players p
        LEFT JOIN team_player tp ON tp.player_id = p.id
        WHERE p.is_active = 1 AND tp.player_id IS NULL
        ORDER BY p.name
        """
    )
    rows = cursor.fetchall()
    conn.close()
    return rows


@app.route("/available")
def available_view():
    rows = load_available_players()
    return render_template("available.html", rows=rows)


if __name__ == "__main__":
    app.run(debug=True)
