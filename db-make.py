import sqlite3

with sqlite3.connect('ebl.db') as conn:
    cursor = conn.cursor()
    cursor.execute("""
    PRAGMA foreign_keys = ON;
    """)

    cursor.execute("""
    CREATE TABLE leagues (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        year INTEGER NOT NULL,
        mlb_team TEXT
    );
    """)

    cursor.execute("""
    CREATE TABLE users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT NOT NULL UNIQUE
    );
    """)

    cursor.execute("""
    CREATE TABLE teams (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        league_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        FOREIGN KEY (league_id) REFERENCES leagues(id),
        FOREIGN KEY (user_id) REFERENCES users(id)
    );
    """)

    cursor.execute("""
    CREATE TABLE players (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL
    );
    """)

    cursor.execute("""
    CREATE TABLE team_player (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        team_id INTEGER NOT NULL,
        player_id INTEGER NOT NULL,
        FOREIGN KEY (team_id) REFERENCES teams(id),
        FOREIGN KEY (player_id) REFERENCES players(id),
        UNIQUE (team_id, player_id)
    );
    """)

    cursor.execute("""
    CREATE TABLE stats (
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
    CREATE TABLE points (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        team_id INTEGER NOT NULL,
        date DATETIME NOT NULL,
        value INTEGER NOT NULL,
        type TEXT NOT NULL CHECK (type IN ('offense', 'defense')),
        FOREIGN KEY (team_id) REFERENCES teams(id)
    );
    """)

    cursor.execute("""
    CREATE TABLE roster_move_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        team_id INTEGER NOT NULL,
        submitted DATETIME NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        FOREIGN KEY (team_id) REFERENCES teams(id)
    );
    """)

    cursor.execute("""
    CREATE TABLE roster_move_request_players (
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
    CREATE TABLE audit (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        datetime DATETIME NOT NULL,
        league_id INTEGER,
        user_id INTEGER,
        operation TEXT NOT NULL,
        old_value TEXT,
        new_value TEXT,
        FOREIGN KEY (league_id) REFERENCES leagues(id),
        FOREIGN KEY (user_id) REFERENCES users(id)
    );
    """)
