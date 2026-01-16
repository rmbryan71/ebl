import os
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
        "teams",
        "team_player",
        "stats",
        "points",
        "audit",
        "roster_move_requests",
        "roster_move_request_players",
        "mlb_transactions",
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
