import random

from werkzeug.security import generate_password_hash

from db import get_connection, ensure_identities

TEST_LEAGUE_PATH = "test-league.md"


def load_test_league_data(path=TEST_LEAGUE_PATH):
    sections = {
        "team names": [],
        "emails": [],
        "passwords": [],
    }
    current = None
    with open(path, "r") as handle:
        for raw_line in handle.readlines():
            line = raw_line.strip()
            if line.startswith("## "):
                current = line[3:].strip().lower()
                continue
            if current in sections and line.startswith("- "):
                sections[current].append(line[2:].strip())
    return sections


def make_test_league_and_teams(conn, team_count=8, seed=None):
    cursor = conn.cursor()
    ensure_identities(conn, ["leagues", "users", "user_accounts", "teams"])

    cursor.execute("SELECT id FROM leagues ORDER BY id LIMIT 1")
    row = cursor.fetchone()
    if row:
        league_id = row["id"]
    else:
        cursor.execute(
            "INSERT INTO leagues (name, year, mlb_team) VALUES (%s, %s, %s)",
            ("EBL 2025", 2025, "PHI"),
        )
        cursor.execute("SELECT id FROM leagues ORDER BY id DESC LIMIT 1")
        league_id = cursor.fetchone()["id"]

    data = load_test_league_data()
    team_names = data["team names"]
    emails = data["emails"]
    passwords = data["passwords"]

    if not (len(team_names) == len(emails) == len(passwords) == team_count):
        raise SystemExit("test-league.md must define 8 team names, emails, and passwords.")

    user_ids = []
    for idx in range(team_count):
        email = emails[idx].lower()
        cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
        row = cursor.fetchone()
        if row:
            user_id = row["id"]
        else:
            cursor.execute("INSERT INTO users (email) VALUES (%s) RETURNING id", (email,))
            user_id = cursor.fetchone()["id"]
        user_ids.append(user_id)

    team_ids = []
    for idx in range(team_count):
        name = team_names[idx]
        user_id = user_ids[idx]
        cursor.execute(
            "SELECT id FROM teams WHERE league_id = %s AND name = %s",
            (league_id, name),
        )
        row = cursor.fetchone()
        if row:
            team_id = row["id"]
            cursor.execute(
                "UPDATE teams SET user_id = %s WHERE id = %s",
                (user_id, team_id),
            )
        else:
            cursor.execute(
                "INSERT INTO teams (league_id, user_id, name) VALUES (%s, %s, %s) RETURNING id",
                (league_id, user_id, name),
            )
            team_id = cursor.fetchone()["id"]
        team_ids.append(team_id)

    for idx in range(team_count):
        email = emails[idx].lower()
        password_hash = generate_password_hash(passwords[idx])
        team_id = team_ids[idx]
        cursor.execute(
            """
            INSERT INTO user_accounts (email, password_hash, role, team_id, is_active)
            VALUES (%s, %s, 'owner', %s, 1)
            ON CONFLICT (email)
            DO UPDATE SET
                password_hash = EXCLUDED.password_hash,
                role = 'owner',
                team_id = EXCLUDED.team_id,
                is_active = 1
            """,
            (email, password_hash, team_id),
        )

    return team_ids


def assign_players_to_teams(conn, team_ids, force=False, seed=None, max_per_team=4):
    cursor = conn.cursor()
    ensure_identities(conn, ["team_player"])
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
        """
        INSERT INTO team_player (team_id, player_id)
        VALUES (%s, %s)
        ON CONFLICT DO NOTHING
        """,
        rows,
    )
    return len(rows)


if __name__ == "__main__":
    with get_connection() as conn:
        team_ids = make_test_league_and_teams(conn)
        assigned = assign_players_to_teams(conn, team_ids, force=True)
        conn.commit()
    print(f"Created {len(team_ids)} teams and assigned {assigned} players.")
