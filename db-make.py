import os
import sqlite3

DB_PATH = "ebl.db"

if os.path.exists(DB_PATH):
    confirm = input(f"{DB_PATH} exists. Delete and recreate? [y/N]: ").strip().lower()
    if confirm != "y":
        raise SystemExit("Aborted.")
    os.remove(DB_PATH)

with sqlite3.connect(DB_PATH) as conn:
    cursor = conn.cursor()

    # =========================
    # PRAGMAS
    # =========================
    cursor.execute("PRAGMA foreign_keys = ON;")

    # =========================
    # TABLES
    # =========================

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS leagues (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        year INTEGER NOT NULL,
        mlb_team TEXT
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT NOT NULL UNIQUE
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS teams (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        league_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        FOREIGN KEY (league_id) REFERENCES leagues(id),
        FOREIGN KEY (user_id) REFERENCES users(id)
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS players (
        id INTEGER PRIMARY KEY AUTOINCREMENT,

        -- MLB identifiers
        mlb_id INTEGER UNIQUE NOT NULL,

        -- Names
        name TEXT NOT NULL,
        first_name TEXT,
        last_name TEXT,
        name_slug TEXT,

        -- Baseball info
        position_code TEXT,
        position_name TEXT,
        position_type TEXT,
        bat_side TEXT,
        throw_side TEXT,

        -- Roster / uniform
        jersey_number INTEGER,
        status TEXT,                -- Active, Injured List, etc.

        -- Biographical
        birth_date DATE,
        birth_city TEXT,
        birth_state TEXT,
        birth_country TEXT,
        height TEXT,                -- e.g. 6'2"
        weight INTEGER,

        -- Metadata
        is_active INTEGER DEFAULT 1,
        last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS team_player (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        team_id INTEGER NOT NULL,
        player_id INTEGER NOT NULL,
        FOREIGN KEY (team_id) REFERENCES teams(id),
        FOREIGN KEY (player_id) REFERENCES players(id),
        UNIQUE (team_id, player_id)
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS stats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        player_id INTEGER NOT NULL,
        team_id INTEGER NOT NULL,
        date DATETIME NOT NULL,
        offense INTEGER,
        pitching INTEGER,
        FOREIGN KEY (player_id) REFERENCES players(id),
        FOREIGN KEY (team_id) REFERENCES teams(id)
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS points (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        team_id INTEGER NOT NULL,
        date DATETIME NOT NULL,
        value INTEGER NOT NULL,
        type TEXT NOT NULL CHECK (type IN ('offense', 'defense')),
        FOREIGN KEY (team_id) REFERENCES teams(id)
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS roster_move_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        team_id INTEGER NOT NULL,
        submitted DATETIME NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        FOREIGN KEY (team_id) REFERENCES teams(id)
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS roster_move_request_players (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        roster_move_request_id INTEGER NOT NULL,
        player_id INTEGER NOT NULL,
        action TEXT NOT NULL CHECK (action IN ('add', 'drop')),
        FOREIGN KEY (roster_move_request_id) REFERENCES roster_move_requests(id),
        FOREIGN KEY (player_id) REFERENCES players(id),
        UNIQUE (roster_move_request_id, player_id)
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS audit (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        datetime DATETIME NOT NULL,
        league_id INTEGER,
        user_id INTEGER,
        table_name TEXT NOT NULL,
        operation TEXT NOT NULL,
        old_value TEXT,
        new_value TEXT,
        prev_hash TEXT,
        row_hash TEXT NOT NULL
    );
    """)

    # =========================
    # TRIGGERS (ALL TABLES)
    # =========================

    def audit_trigger(table, cols):
        return f"""
        CREATE TRIGGER IF NOT EXISTS audit_{table}_ai
        AFTER INSERT ON {table}
        BEGIN
            INSERT INTO audit
            (datetime, user_id, table_name, operation, new_value, prev_hash, row_hash)
            VALUES (
                CURRENT_TIMESTAMP,
                (SELECT user_version FROM pragma_user_version),
                '{table}',
                'INSERT',
                json_object({cols}),
                (SELECT row_hash FROM audit ORDER BY id DESC LIMIT 1),
                lower(hex(randomblob(16)))
            );
        END;
        """

    cursor.execute(audit_trigger('players', "'id',NEW.id,'name',NEW.name"))
    cursor.execute(audit_trigger('teams', "'id',NEW.id,'league_id',NEW.league_id,'user_id',NEW.user_id,'name',NEW.name"))
    cursor.execute(audit_trigger('leagues', "'id',NEW.id,'name',NEW.name,'year',NEW.year,'mlb_team',NEW.mlb_team"))
    cursor.execute(audit_trigger('stats', "'id',NEW.id,'player_id',NEW.player_id,'team_id',NEW.team_id,'date',NEW.date"))
    cursor.execute(audit_trigger('points', "'id',NEW.id,'team_id',NEW.team_id,'date',NEW.date,'value',NEW.value,'type',NEW.type"))

    # =========================
    # AUDIT PROTECTION
    # =========================

    cursor.execute("""
    CREATE TRIGGER IF NOT EXISTS audit_no_update
    BEFORE UPDATE ON audit
    BEGIN
        SELECT RAISE(FAIL, 'audit table is append-only');
    END;
    """)

    cursor.execute("""
    CREATE TRIGGER IF NOT EXISTS audit_no_delete
    BEFORE DELETE ON audit
    BEGIN
        SELECT RAISE(FAIL, 'audit table is append-only');
    END;
    """)

    # =========================
    # INDEXES
    # =========================

    conn.execute("""
    CREATE INDEX IF NOT EXISTS idx_audit_datetime
    ON audit(datetime);
    """)

    conn.execute("""
    CREATE INDEX IF NOT EXISTS idx_audit_table_datetime
    ON audit(table_name, datetime);
    """)

    conn.execute("""
    CREATE INDEX IF NOT EXISTS idx_audit_league_datetime
    ON audit(league_id, datetime);
    """)

    conn.execute("""
    CREATE INDEX IF NOT EXISTS idx_audit_user_datetime
    ON audit(user_id, datetime);
    """)

    conn.execute("""
    CREATE UNIQUE INDEX IF NOT EXISTS idx_audit_row_hash
    ON audit(row_hash);
    """)

    conn.commit()
