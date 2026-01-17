import pytest

from simulation_fixtures import (
    SCHEMA_VERSION,
    validate_manifest,
    validate_roster_fixture,
    validate_stats_fixture,
)


def test_validate_manifest_accepts_valid_payload():
    payload = {
        "schema_version": SCHEMA_VERSION,
        "season": 2025,
        "start_date": "2025-03-01",
        "end_date": "2025-03-07",
        "captured_at": "2025-03-08T12:30:00+00:00",
        "source": "mlb_statsapi",
        "notes": "",
    }
    validate_manifest(payload)


def test_validate_roster_fixture_accepts_valid_payload():
    payload = {
        "date": "2025-04-01",
        "team_id": 143,
        "mlb_player_ids": [1, 2],
        "players": [
            {
                "mlb_player_id": 1,
                "name": "Player One",
                "position_code": "1B",
                "position_name": "First Base",
                "position_type": "Infield",
            },
            {
                "mlb_player_id": 2,
                "name": "Player Two",
                "position_code": None,
                "position_name": None,
                "position_type": None,
            },
        ],
    }
    validate_roster_fixture(payload)


def test_validate_stats_fixture_accepts_valid_payload():
    payload = {
        "date": "2025-04-01",
        "players": [
            {"mlb_player_id": 1, "outs": 3, "offense": 4},
            {"mlb_player_id": 2, "outs": 0, "offense": 1},
        ],
    }
    validate_stats_fixture(payload)


def test_validate_roster_fixture_rejects_bad_date():
    payload = {
        "date": "2025-04-01T00:00:00Z",
        "team_id": 143,
        "mlb_player_ids": [1],
        "players": [
            {
                "mlb_player_id": 1,
                "name": "Player One",
                "position_code": "1B",
                "position_name": "First Base",
                "position_type": "Infield",
            }
        ],
    }
    with pytest.raises(ValueError):
        validate_roster_fixture(payload)
