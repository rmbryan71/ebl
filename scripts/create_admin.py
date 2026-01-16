import getpass
import os
import sys
from pathlib import Path

from werkzeug.security import generate_password_hash

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from db import get_connection


def main():
    if not os.getenv("DATABASE_URL"):
        raise SystemExit("DATABASE_URL is not set.")

    email = input("Admin email: ").strip().lower()
    if not email:
        raise SystemExit("Email is required.")
    password = getpass.getpass("Admin password: ").strip()
    if not password:
        raise SystemExit("Password is required.")

    password_hash = generate_password_hash(password)

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO user_accounts (email, password_hash, role, is_active)
                VALUES (%s, %s, 'admin', 1)
                ON CONFLICT (email)
                DO UPDATE SET
                    password_hash = EXCLUDED.password_hash,
                    role = 'admin',
                    is_active = 1
                """,
                (email, password_hash),
            )
        conn.commit()

    print("Admin account created/updated.")


if __name__ == "__main__":
    main()
