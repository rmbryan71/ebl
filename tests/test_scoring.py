from datetime import date
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


def load_scoring_module():
    module_path = Path(__file__).resolve().parents[1] / "scoring.py"
    spec = spec_from_file_location("scoring", module_path)
    module = module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def test_week_start_end():
    scoring = load_scoring_module()
    sample = date(2025, 4, 9)  # Wednesday
    assert scoring.week_start(sample) == date(2025, 4, 7)
    assert scoring.week_end(sample) == date(2025, 4, 13)


def test_award_points_simple():
    scoring = load_scoring_module()
    totals = {1: 10, 2: 7, 3: 4, 4: 1}
    points = {1: 10, 2: 8, 3: 4}
    awards = dict(scoring.award_points_for_category(totals, points))
    assert awards == {1: 10, 2: 8, 3: 4}


def test_award_points_tie_first_skips_second():
    scoring = load_scoring_module()
    totals = {1: 10, 2: 10, 3: 5}
    points = {1: 10, 2: 8, 3: 4}
    awards = dict(scoring.award_points_for_category(totals, points))
    assert awards == {1: 10, 2: 10, 3: 4}


def test_award_points_tie_second_skips_third():
    scoring = load_scoring_module()
    totals = {1: 12, 2: 9, 3: 9, 4: 5}
    points = {1: 10, 2: 8, 3: 4}
    awards = dict(scoring.award_points_for_category(totals, points))
    assert awards == {1: 10, 2: 8, 3: 8}


def test_award_points_tie_third_awards_all_third():
    scoring = load_scoring_module()
    totals = {1: 12, 2: 9, 3: 6, 4: 6, 5: 6}
    points = {1: 10, 2: 8, 3: 4}
    awards = dict(scoring.award_points_for_category(totals, points))
    assert awards == {1: 10, 2: 8, 3: 4, 4: 4, 5: 4}
