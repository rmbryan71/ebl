import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from db import get_connection


def main():
    if not os.getenv("DATABASE_URL"):
        raise SystemExit("DATABASE_URL is not set.")

    email = input("Owner email: ").strip().lower()
    if not email:
        raise SystemExit("Email is required.")
    team_id = input("Team ID: ").strip()
    if not team_id.isdigit():
        raise SystemExit("Team ID must be a number.")

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT id FROM teams WHERE id = %s",
                (team_id,),
            )
            if not cursor.fetchone():
                raise SystemExit("Team ID not found.")

            cursor.execute(
                "SELECT id, role FROM user_accounts WHERE email = %s",
                (email,),
            )
            row = cursor.fetchone()
            if not row:
                raise SystemExit("Owner account not found.")
            if row["role"] != "owner":
                raise SystemExit("Account is not an owner role.")

            cursor.execute(
                "UPDATE user_accounts SET team_id = %s WHERE email = %s",
                (team_id, email),
            )
        conn.commit()

    print("Owner account assigned to team.")


if __name__ == "__main__":
    main()
