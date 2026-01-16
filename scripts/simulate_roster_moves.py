import argparse
import os
import random
import sys
from datetime import datetime
from pathlib import Path

from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from db import get_connection, set_audit_user_id


EASTERN_TZ = ZoneInfo("America/New_York")


def parse_args():
    parser = argparse.ArgumentParser(description="Simulate roster move submissions for testing.")
    parser.add_argument(
        "--date",
        help="Submission date (YYYY-MM-DD). Defaults to today.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for selecting add players.",
    )
    return parser.parse_args()


def resolve_date(value):
    if not value:
        return datetime.now(EASTERN_TZ).replace(tzinfo=None)
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise SystemExit("Invalid --date. Use YYYY-MM-DD.") from exc
    return datetime.combine(parsed, datetime.min.time())


def main():
    if not os.getenv("DATABASE_URL"):
        raise SystemExit("DATABASE_URL is not set.")

    args = parse_args()
    submitted_at = resolve_date(args.date).isoformat(sep=" ")
    rng = random.Random(args.seed)

    with get_connection() as conn:
        cursor = conn.cursor()
        set_audit_user_id(conn, 0)

        cursor.execute("SELECT id, name FROM teams ORDER BY id")
        teams = cursor.fetchall()
        if not teams:
            raise SystemExit("No teams found.")

        cursor.execute("SELECT player_id, team_id FROM team_player")
        team_players = {}
        for row in cursor.fetchall():
            team_players.setdefault(row["team_id"], []).append(row["player_id"])

        cursor.execute(
            """
            SELECT id
            FROM players
            WHERE is_active = 1
              AND id NOT IN (SELECT player_id FROM team_player)
            ORDER BY id
            """
        )
        available_players = [row["id"] for row in cursor.fetchall()]
        if len(available_players) < 3:
            raise SystemExit("Need at least 3 available players to simulate moves.")

        created = 0
        for team in teams:
            team_id = team["id"]
            roster = team_players.get(team_id, [])
            if not roster:
                continue
            drop_player_id = roster[0]
            add_choices = rng.sample(available_players, k=3)

            cursor.execute(
                """
                UPDATE roster_move_requests
                SET status = 'superseded'
                WHERE team_id = %s AND status = 'pending'
                """,
                (team_id,),
            )
            cursor.execute(
                """
                INSERT INTO roster_move_requests (team_id, submitted, status)
                VALUES (%s, %s, 'pending')
                RETURNING id
                """,
                (team_id, submitted_at),
            )
            request_id = cursor.fetchone()["id"]
            cursor.execute(
                """
                INSERT INTO roster_move_request_players (roster_move_request_id, player_id, action)
                VALUES (%s, %s, 'drop')
                """,
                (request_id, drop_player_id),
            )
            for priority, player_id in enumerate(add_choices, start=1):
                cursor.execute(
                    """
                    INSERT INTO roster_move_request_players (
                        roster_move_request_id,
                        player_id,
                        action,
                        priority
                    )
                    VALUES (%s, %s, 'add', %s)
                    """,
                    (request_id, player_id, priority),
                )
            created += 1

        conn.commit()

    print(f"Created {created} pending roster move requests.")


if __name__ == "__main__":
    main()
