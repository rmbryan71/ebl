from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import pytest


def load_stats_populate_module():
    module_path = Path(__file__).resolve().parents[1] / "stats-populate.py"
    spec = spec_from_file_location("stats_populate", module_path)
    module = module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def test_innings_to_outs_basic():
    stats_populate = load_stats_populate_module()
    assert stats_populate.innings_to_outs("5.2") == 17
    assert stats_populate.innings_to_outs("0.1") == 1
    assert stats_populate.innings_to_outs("7") == 21


def test_innings_to_outs_invalid():
    stats_populate = load_stats_populate_module()
    assert stats_populate.innings_to_outs(None) == 0
    assert stats_populate.innings_to_outs("") == 0
    assert stats_populate.innings_to_outs("abc") == 0


def test_calculate_offense():
    stats_populate = load_stats_populate_module()
    stat_line = {
        "totalBases": 4,
        "baseOnBalls": 2,
        "hitByPitch": 1,
        "stolenBases": 3,
    }
    assert stats_populate.calculate_offense(stat_line) == 10


def test_parse_date_valid():
    stats_populate = load_stats_populate_module()
    assert stats_populate.parse_date("2025-04-01", "start").isoformat() == "2025-04-01"


def test_parse_date_invalid():
    stats_populate = load_stats_populate_module()
    with pytest.raises(SystemExit):
        stats_populate.parse_date("04/01/2025", "start")
