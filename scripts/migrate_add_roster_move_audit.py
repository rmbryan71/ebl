import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from db import get_connection


def main():
    if not os.getenv("DATABASE_URL"):
        raise SystemExit("DATABASE_URL is not set.")

    sql = """
    CREATE EXTENSION IF NOT EXISTS pgcrypto;

    CREATE OR REPLACE FUNCTION audit_insert_roster_move_request() RETURNS trigger AS $$
    BEGIN
      INSERT INTO audit (datetime, user_id, table_name, operation, new_value, prev_hash, row_hash)
      VALUES (
        CURRENT_TIMESTAMP,
        COALESCE(current_setting('app.user_id', true), '0')::int,
        'roster_move_requests',
        'INSERT',
        json_build_object('id', NEW.id, 'team_id', NEW.team_id, 'submitted', NEW.submitted, 'status', NEW.status),
        (SELECT row_hash FROM audit ORDER BY id DESC LIMIT 1),
        encode(gen_random_bytes(16), 'hex')
      );
      RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;

    CREATE OR REPLACE FUNCTION audit_insert_roster_move_request_player() RETURNS trigger AS $$
    BEGIN
      INSERT INTO audit (datetime, user_id, table_name, operation, new_value, prev_hash, row_hash)
      VALUES (
        CURRENT_TIMESTAMP,
        COALESCE(current_setting('app.user_id', true), '0')::int,
        'roster_move_request_players',
        'INSERT',
        json_build_object('id', NEW.id, 'roster_move_request_id', NEW.roster_move_request_id, 'player_id', NEW.player_id, 'action', NEW.action, 'priority', NEW.priority),
        (SELECT row_hash FROM audit ORDER BY id DESC LIMIT 1),
        encode(gen_random_bytes(16), 'hex')
      );
      RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;

    DROP TRIGGER IF EXISTS audit_roster_move_requests_ai ON roster_move_requests;
    CREATE TRIGGER audit_roster_move_requests_ai
    AFTER INSERT ON roster_move_requests
    FOR EACH ROW EXECUTE FUNCTION audit_insert_roster_move_request();

    DROP TRIGGER IF EXISTS audit_roster_move_request_players_ai ON roster_move_request_players;
    CREATE TRIGGER audit_roster_move_request_players_ai
    AFTER INSERT ON roster_move_request_players
    FOR EACH ROW EXECUTE FUNCTION audit_insert_roster_move_request_player();
    """

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql)
        conn.commit()

    print("Roster move audit triggers installed.")


if __name__ == "__main__":
    main()
