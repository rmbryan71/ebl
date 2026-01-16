import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from db import get_connection


def column_exists(cursor, table_name, column_name):
    cursor.execute(
        """
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = %s AND column_name = %s
        """,
        (table_name, column_name),
    )
    return cursor.fetchone() is not None


def main():
    if not os.getenv("DATABASE_URL"):
        raise SystemExit("DATABASE_URL is not set.")

    with get_connection() as conn:
        with conn.cursor() as cursor:
            if not column_exists(cursor, "roster_move_request_players", "priority"):
                cursor.execute(
                    """
                    ALTER TABLE roster_move_request_players
                    ADD COLUMN priority INTEGER CHECK (priority IN (1, 2, 3))
                    """
                )
            conn.commit()

    print("Migration complete.")


if __name__ == "__main__":
    main()
