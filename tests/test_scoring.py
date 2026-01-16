from datetime import date

from scoring import award_points_for_category, week_end, week_start


def test_week_start_end():
    sample = date(2025, 4, 9)  # Wednesday
    assert week_start(sample) == date(2025, 4, 7)
    assert week_end(sample) == date(2025, 4, 13)


def test_award_points_simple():
    totals = {1: 10, 2: 7, 3: 4, 4: 1}
    points = {1: 10, 2: 8, 3: 4}
    awards = dict(award_points_for_category(totals, points))
    assert awards == {1: 10, 2: 8, 3: 4}


def test_award_points_tie_first_skips_second():
    totals = {1: 10, 2: 10, 3: 5}
    points = {1: 10, 2: 8, 3: 4}
    awards = dict(award_points_for_category(totals, points))
    assert awards == {1: 10, 2: 10, 3: 4}


def test_award_points_tie_second_skips_third():
    totals = {1: 12, 2: 9, 3: 9, 4: 5}
    points = {1: 10, 2: 8, 3: 4}
    awards = dict(award_points_for_category(totals, points))
    assert awards == {1: 10, 2: 8, 3: 8}


def test_award_points_tie_third_awards_all_third():
    totals = {1: 12, 2: 9, 3: 6, 4: 6, 5: 6}
    points = {1: 10, 2: 8, 3: 4}
    awards = dict(award_points_for_category(totals, points))
    assert awards == {1: 10, 2: 8, 3: 4, 4: 4, 5: 4}
