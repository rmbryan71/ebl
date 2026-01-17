import os
from datetime import date
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest

from db import get_connection


pytestmark = pytest.mark.skipif(
    not os.getenv("DATABASE_URL"),
    reason="DATABASE_URL not set.",
)


def test_core_tables_exist():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            """
        )
        tables = {row["table_name"] for row in cursor.fetchall()}

    expected = {
        "players",
        "mlb_roster_changes",
        "teams",
        "team_player",
        "stats",
        "points",
        "audit",
        "roster_move_requests",
        "roster_move_request_players",
    }
    assert expected.issubset(tables)


def test_team_player_audit_trigger_exists():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT tgname
            FROM pg_trigger
            WHERE NOT tgisinternal
            """
        )
        triggers = {row["tgname"] for row in cursor.fetchall()}

    assert "audit_team_player_ai" in triggers
    assert "audit_mlb_roster_changes_ai" in triggers


def load_roster_sync_module():
    module_path = Path(__file__).resolve().parents[1] / "roster-sync.py"
    spec = spec_from_file_location("roster_sync", module_path)
    module = module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def test_apply_mlb_roster_changes_removal():
    roster_sync = load_roster_sync_module()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO leagues (name, year) VALUES (%s, %s) RETURNING id",
            ("Test League", 2025),
        )
        league_id = cursor.fetchone()["id"]
        cursor.execute(
            "INSERT INTO users (email) VALUES (%s) RETURNING id",
            ("test@example.com",),
        )
        user_id = cursor.fetchone()["id"]
        cursor.execute(
            """
            INSERT INTO teams (league_id, user_id, name, has_empty_roster_spot)
            VALUES (%s, %s, %s, 0)
            RETURNING id
            """,
            (league_id, user_id, "Test Team"),
        )
        team_id = cursor.fetchone()["id"]
        cursor.execute(
            """
            INSERT INTO players (mlb_id, name, is_active)
            VALUES (%s, %s, 1)
            """,
            (999999, "Test Player"),
        )
        cursor.execute(
            """
            INSERT INTO team_player (team_id, player_mlb_id)
            VALUES (%s, %s)
            """,
            (team_id, 999999),
        )

        roster_sync.apply_mlb_roster_changes(
            conn,
            before_set={999999},
            after_set=set(),
            change_date=date(2025, 1, 1),
        )

        cursor.execute(
            """
            SELECT COUNT(*) AS count
            FROM mlb_roster_changes
            WHERE player_mlb_id = %s AND change_type = 'remove'
            """,
            (999999,),
        )
        assert cursor.fetchone()["count"] == 1
        cursor.execute(
            """
            SELECT COUNT(*) AS count
            FROM team_player
            WHERE player_mlb_id = %s
            """,
            (999999,),
        )
        assert cursor.fetchone()["count"] == 0
        cursor.execute(
            """
            SELECT COUNT(*) AS count
            FROM alumni
            WHERE player_mlb_id = %s
            """,
            (999999,),
        )
        assert cursor.fetchone()["count"] == 1
        cursor.execute(
            """
            SELECT has_empty_roster_spot
            FROM teams
            WHERE id = %s
            """,
            (team_id,),
        )
        assert cursor.fetchone()["has_empty_roster_spot"] == 1

        conn.rollback()
