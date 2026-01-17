import random
import re

from werkzeug.security import generate_password_hash

from db import get_connection, ensure_identities

LEAGUE_DATA_PATH = "demo-league.md"
ROOT_DIR = Path(__file__).resolve().parent

SECTION_PATTERN = re.compile(r"^##\s+(.*)$")


def load_league_data(path=LEAGUE_DATA_PATH):
    data_path = ROOT_DIR / path
    sections = {"team names": [], "emails": [], "passwords": []}
    current = None
    with open(data_path, "r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            match = SECTION_PATTERN.match(line)
            if match:
                current = match.group(1).strip().lower()
                continue
            if current in sections and line.startswith("- "):
                sections[current].append(line[2:].strip())

    team_names = sections["team names"]
    emails = sections["emails"]
    passwords = sections["passwords"]
    if not team_names or not emails or not passwords:
        raise SystemExit("demo-league.md must include Team names, Emails, and Passwords sections.")
    if len(emails) != len(passwords):
        raise SystemExit("Emails and Passwords must have the same count.")
    return team_names, emails, passwords


def make_test_league_and_teams(conn, team_count=8, seed=None):
    cursor = conn.cursor()
    ensure_identities(conn, ["leagues", "users", "teams", "user_accounts"])

    cursor.execute("DELETE FROM team_player")
    cursor.execute("DELETE FROM stats")
    cursor.execute("DELETE FROM points")
    cursor.execute("DELETE FROM roster_move_request_players")
    cursor.execute("DELETE FROM roster_move_requests")
    cursor.execute("DELETE FROM alumni")
    cursor.execute("UPDATE user_accounts SET team_id = NULL")
    cursor.execute("DELETE FROM teams")

    team_names, emails, passwords = load_league_data()
    team_names = team_names[:team_count]
    emails = emails[:team_count]
    passwords = passwords[:team_count]

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

    cursor.execute("SELECT id, email FROM users")
    existing_users = {row["email"]: row["id"] for row in cursor.fetchall()}
    user_ids = []
    for email in emails:
        if email in existing_users:
            user_ids.append(existing_users[email])
            continue
        cursor.execute(
            "INSERT INTO users (email) VALUES (%s) RETURNING id",
            (email,),
        )
        user_ids.append(cursor.fetchone()["id"])

    shuffled_names = list(team_names)
    team_ids = []
    for idx, team_name in enumerate(shuffled_names):
        cursor.execute(
            "INSERT INTO teams (league_id, user_id, name) VALUES (%s, %s, %s) RETURNING id",
            (league_id, user_ids[idx], team_name),
        )
        team_ids.append(cursor.fetchone()["id"])

    return team_ids[:team_count]


def create_owner_accounts(conn, emails, passwords, team_ids, seed=None):
    cursor = conn.cursor()
    ensure_identities(conn, ["user_accounts"])

    for email, password, team_id in zip(emails, passwords, team_ids):
        password_hash = generate_password_hash(password)
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


def assign_players_to_teams(conn, team_ids, force=False, seed=None, max_per_team=4):
    cursor = conn.cursor()
    ensure_identities(conn, ["team_player"])
    if force:
        cursor.execute("DELETE FROM team_player")
    else:
        cursor.execute("SELECT COUNT(*) AS count FROM team_player")
        if cursor.fetchone()["count"] > 0:
            return 0

    cursor.execute("SELECT mlb_id FROM players WHERE is_active = 1 ORDER BY mlb_id")
    player_ids = [row["mlb_id"] for row in cursor.fetchall()]
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
        INSERT INTO team_player (team_id, player_mlb_id)
        VALUES (%s, %s)
        ON CONFLICT DO NOTHING
        """,
        rows,
    )
    return len(rows)


if __name__ == "__main__":
    with get_connection() as conn:
        team_ids = make_test_league_and_teams(conn)
        team_names, emails, passwords = load_league_data()
        create_owner_accounts(conn, emails[: len(team_ids)], passwords[: len(team_ids)], team_ids)
        assigned = assign_players_to_teams(conn, team_ids, force=True)
        conn.commit()
    print(f"Created {len(team_ids)} teams and assigned {assigned} players.")

    from importlib.util import module_from_spec, spec_from_file_location
    from datetime import datetime
    from pathlib import Path as SysPath

    root_dir = SysPath(__file__).resolve().parents[1]
    stats_path = root_dir / "stats-populate.py"
    score_path = root_dir / "scoring.py"

    stats_spec = spec_from_file_location("stats_populate", stats_path)
    stats_module = module_from_spec(stats_spec)
    stats_spec.loader.exec_module(stats_module)  # type: ignore[union-attr]

    score_spec = spec_from_file_location("scoring", score_path)
    score_module = module_from_spec(score_spec)
    score_spec.loader.exec_module(score_module)  # type: ignore[union-attr]

    start_date = datetime.strptime("2025-03-26", "%Y-%m-%d").date()
    end_date = datetime.strptime("2025-07-04", "%Y-%m-%d").date()
    stats_module.populate_2025_stats(start_date=start_date, end_date=end_date)
    score_module.score_weeks()
