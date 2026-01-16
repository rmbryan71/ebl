from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


def load_roster_moves_module():
    module_path = Path(__file__).resolve().parents[1] / "roster-moves.py"
    spec = spec_from_file_location("roster_moves", module_path)
    module = module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def test_order_teams_empty_spots_first_then_points_then_time():
    roster_moves = load_roster_moves_module()

    team_info = [
        {
            "team_id": 1,
            "team_name": "Alpha",
            "submitted": "2025-04-07 10:00:00",
            "has_empty_roster_spot": True,
            "points": 12,
        },
        {
            "team_id": 2,
            "team_name": "Beta",
            "submitted": "2025-04-07 09:00:00",
            "has_empty_roster_spot": True,
            "points": 6,
        },
        {
            "team_id": 3,
            "team_name": "Gamma",
            "submitted": "2025-04-07 08:00:00",
            "has_empty_roster_spot": False,
            "points": 6,
        },
        {
            "team_id": 4,
            "team_name": "Delta",
            "submitted": "2025-04-07 07:00:00",
            "has_empty_roster_spot": False,
            "points": 20,
        },
    ]

    ordered = roster_moves.order_teams(team_info)
    ordered_ids = [info["team_id"] for info in ordered]

    # Empty roster spots first, lowest points first, then submitted time.
    assert ordered_ids == [2, 1, 3, 4]
