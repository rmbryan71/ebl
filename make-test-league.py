import random

from db import get_connection, param_placeholder

TEAM_NAMES_PATH = "test-team-names.md"

DB_PATH = "ebl.db"

def load_team_names(path=TEAM_NAMES_PATH):
    with open(path, "r") as handle:
        names = [line.strip() for line in handle.readlines() if line.strip()]
    return names


def make_test_league_and_teams(conn, team_count=8, seed=None):
    cursor = conn.cursor()
    ph = param_placeholder()

    cursor.execute("SELECT id FROM leagues ORDER BY id LIMIT 1")
    row = cursor.fetchone()
    if row:
        league_id = row["id"]
    else:
        cursor.execute(
            f"INSERT INTO leagues (name, year, mlb_team) VALUES ({ph}, {ph}, {ph})",
            ("EBL 2025", 2025, "PHI"),
        )
        cursor.execute("SELECT id FROM leagues ORDER BY id DESC LIMIT 1")
        league_id = cursor.fetchone()["id"]

    cursor.execute("SELECT id FROM users ORDER BY id")
    user_ids = [row["id"] for row in cursor.fetchall()]
    if len(user_ids) < team_count:
        for idx in range(len(user_ids) + 1, team_count + 1):
            cursor.execute(
                f"INSERT INTO users (email) VALUES ({ph})",
                (f"test_owner_{idx}@ebl.local",),
            )
        cursor.execute("SELECT id FROM users ORDER BY id")
        user_ids = [row["id"] for row in cursor.fetchall()]

    cursor.execute("SELECT id FROM teams ORDER BY id")
    team_ids = [row["id"] for row in cursor.fetchall()]
    if len(team_ids) < team_count:
        team_names = load_team_names()
        rng = random.Random(seed)
        rng.shuffle(team_names)
        for idx in range(len(team_ids) + 1, team_count + 1):
            cursor.execute(
                f"INSERT INTO teams (league_id, user_id, name) VALUES ({ph}, {ph}, {ph})",
                (league_id, user_ids[idx - 1], team_names[idx - 1]),
            )
        cursor.execute("SELECT id FROM teams ORDER BY id")
        team_ids = [row["id"] for row in cursor.fetchall()]

    return team_ids[:team_count]


def assign_players_to_teams(conn, team_ids, force=False, seed=None, max_per_team=4):
    cursor = conn.cursor()
    ph = param_placeholder()
    if force:
        cursor.execute("DELETE FROM team_player")
    else:
        cursor.execute("SELECT COUNT(*) AS count FROM team_player")
        if cursor.fetchone()["count"] > 0:
            return 0

    cursor.execute("SELECT id FROM players WHERE is_active = 1 ORDER BY id")
    player_ids = [row["id"] for row in cursor.fetchall()]
    if not player_ids:
        return 0

    rng = random.Random(seed)
    rng.shuffle(player_ids)

    rows = []
    assignments = {team_id: 0 for team_id in team_ids}
    team_cycle = list(team_ids)
    for player_id in player_ids:
        available = [team_id for team_id in team_cycle if assignments[team_id] < max_per_team]
        if not available:
            break
        team_id = available[0]
        assignments[team_id] += 1
        rows.append((team_id, player_id))

    cursor.executemany(
        f"""
        INSERT INTO team_player (team_id, player_id)
        VALUES ({ph}, {ph})
        ON CONFLICT DO NOTHING
        """,
        rows,
    )
    return len(rows)


if __name__ == "__main__":
    with get_connection(DB_PATH) as conn:
        team_ids = make_test_league_and_teams(conn)
        assigned = assign_players_to_teams(conn, team_ids, force=True)
        conn.commit()
    print(f"Created {len(team_ids)} teams and assigned {assigned} players.")
