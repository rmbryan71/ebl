from collections import defaultdict
import sqlite3

from flask import Flask, render_template


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


@app.route("/")
def roster_view():
    teams, total_players = load_roster()
    return render_template(
        "roster.html",
        teams=teams,
        total_players=total_players,
        team_count=len(teams),
    )


if __name__ == "__main__":
    app.run(debug=True)
