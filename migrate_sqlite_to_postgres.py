import os
import sqlite3

import psycopg


SQLITE_DB = "ebl.db"
DATABASE_URL = os.getenv("DATABASE_URL")


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS leagues (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    year INTEGER NOT NULL,
    mlb_team TEXT
);

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    email TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS teams (
    id INTEGER PRIMARY KEY,
    league_id INTEGER NOT NULL REFERENCES leagues(id),
    user_id INTEGER NOT NULL REFERENCES users(id),
    name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS players (
    id INTEGER PRIMARY KEY,
    mlb_id INTEGER UNIQUE NOT NULL,
    name TEXT NOT NULL,
    first_name TEXT,
    last_name TEXT,
    name_slug TEXT,
    position_code TEXT,
    position_name TEXT,
    position_type TEXT,
    bat_side TEXT,
    throw_side TEXT,
    jersey_number INTEGER,
    status TEXT,
    birth_date DATE,
    birth_city TEXT,
    birth_state TEXT,
    birth_country TEXT,
    height TEXT,
    weight INTEGER,
    is_active INTEGER DEFAULT 1,
    last_updated TIMESTAMP
);

CREATE TABLE IF NOT EXISTS team_player (
    id INTEGER PRIMARY KEY,
    team_id INTEGER NOT NULL REFERENCES teams(id),
    player_id INTEGER NOT NULL REFERENCES players(id),
    UNIQUE (team_id, player_id)
);

CREATE TABLE IF NOT EXISTS stats (
    id INTEGER PRIMARY KEY,
    player_id INTEGER NOT NULL REFERENCES players(id),
    team_id INTEGER NOT NULL REFERENCES teams(id),
    date TIMESTAMP NOT NULL,
    offense INTEGER,
    pitching INTEGER
);

CREATE TABLE IF NOT EXISTS points (
    id INTEGER PRIMARY KEY,
    team_id INTEGER NOT NULL REFERENCES teams(id),
    date TIMESTAMP NOT NULL,
    value INTEGER NOT NULL,
    type TEXT NOT NULL CHECK (type IN ('offense', 'defense'))
);

CREATE TABLE IF NOT EXISTS roster_move_requests (
    id INTEGER PRIMARY KEY,
    team_id INTEGER NOT NULL REFERENCES teams(id),
    submitted TIMESTAMP NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending'
);

CREATE TABLE IF NOT EXISTS roster_move_request_players (
    id INTEGER PRIMARY KEY,
    roster_move_request_id INTEGER NOT NULL REFERENCES roster_move_requests(id),
    player_id INTEGER NOT NULL REFERENCES players(id),
    action TEXT NOT NULL CHECK (action IN ('add', 'drop')),
    UNIQUE (roster_move_request_id, player_id)
);

CREATE TABLE IF NOT EXISTS audit (
    id INTEGER PRIMARY KEY,
    datetime TIMESTAMP NOT NULL,
    league_id INTEGER,
    user_id INTEGER,
    table_name TEXT NOT NULL,
    operation TEXT NOT NULL,
    old_value TEXT,
    new_value TEXT,
    prev_hash TEXT,
    row_hash TEXT NOT NULL
);
"""


TABLES_IN_ORDER = [
    "leagues",
    "users",
    "teams",
    "players",
    "team_player",
    "stats",
    "points",
    "roster_move_requests",
    "roster_move_request_players",
    "audit",
]


def fetch_table(sqlite_conn, table):
    cursor = sqlite_conn.cursor()
    cursor.execute(f"SELECT * FROM {table}")
    rows = cursor.fetchall()
    columns = [desc[0] for desc in cursor.description]
    return columns, rows


def insert_rows(pg_conn, table, columns, rows):
    if not rows:
        return 0
    cols = ", ".join(columns)
    placeholders = ", ".join(["%s"] * len(columns))
    query = f"INSERT INTO {table} ({cols}) VALUES ({placeholders})"
    with pg_conn.cursor() as cur:
        cur.executemany(query, rows)
    return len(rows)


def main():
    if not DATABASE_URL:
        raise SystemExit("DATABASE_URL is not set.")
    if not os.path.exists(SQLITE_DB):
        raise SystemExit(f"{SQLITE_DB} not found.")

    sqlite_conn = sqlite3.connect(SQLITE_DB)
    sqlite_conn.row_factory = sqlite3.Row

    with psycopg.connect(DATABASE_URL) as pg_conn:
        with pg_conn.cursor() as cur:
            cur.execute(SCHEMA_SQL)

        total_inserted = 0
        for table in TABLES_IN_ORDER:
            columns, rows = fetch_table(sqlite_conn, table)
            inserted = insert_rows(pg_conn, table, columns, rows)
            total_inserted += inserted
            print(f"{table}: {inserted}")

    sqlite_conn.close()
    print(f"Inserted {total_inserted} rows.")


if __name__ == "__main__":
    main()
