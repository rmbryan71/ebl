import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from db import get_connection


def write_audit_entry(cursor, operation, old_value, new_value):
    cursor.execute(
        """
        INSERT INTO audit (datetime, user_id, table_name, operation, old_value, new_value, prev_hash, row_hash)
        VALUES (
            CURRENT_TIMESTAMP,
            %s,
            'user_accounts',
            %s,
            %s,
            %s,
            (SELECT row_hash FROM audit ORDER BY id DESC LIMIT 1),
            encode(gen_random_bytes(16), 'hex')
        )
        """,
        (0, operation, old_value, new_value),
    )


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
                "SELECT id, email, role, team_id FROM user_accounts WHERE email = %s",
                (email,),
            )
            old_row = cursor.fetchone()

            cursor.execute(
                "UPDATE user_accounts SET team_id = %s WHERE email = %s",
                (team_id, email),
            )
            cursor.execute(
                "SELECT id, email, role, team_id FROM user_accounts WHERE email = %s",
                (email,),
            )
            new_row = cursor.fetchone()
            write_audit_entry(
                cursor,
                "UPDATE",
                json.dumps(old_row) if old_row else None,
                json.dumps(new_row) if new_row else None,
            )
        conn.commit()

    print("Owner account assigned to team.")


if __name__ == "__main__":
    main()
