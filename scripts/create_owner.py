import getpass
import json
import os
import sys
from pathlib import Path

from werkzeug.security import generate_password_hash

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
    password = getpass.getpass("Owner password: ").strip()
    if not password:
        raise SystemExit("Password is required.")

    password_hash = generate_password_hash(password)

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, email, role, team_id
                FROM user_accounts
                WHERE email = %s
                """,
                (email,),
            )
            old_row = cursor.fetchone()
            cursor.execute(
                """
                INSERT INTO user_accounts (email, password_hash, role, is_active)
                VALUES (%s, %s, 'owner', 1)
                ON CONFLICT (email)
                DO UPDATE SET
                    password_hash = EXCLUDED.password_hash,
                    role = 'owner',
                    is_active = 1
                """,
                (email, password_hash),
            )
            cursor.execute(
                """
                SELECT id, email, role, team_id
                FROM user_accounts
                WHERE email = %s
                """,
                (email,),
            )
            new_row = cursor.fetchone()
            operation = "INSERT" if old_row is None else "UPDATE"
            old_value = json.dumps(old_row) if old_row else None
            new_value = json.dumps(new_row) if new_row else None
            write_audit_entry(cursor, operation, old_value, new_value)
        conn.commit()

    print("Owner account created/updated.")


if __name__ == "__main__":
    main()
