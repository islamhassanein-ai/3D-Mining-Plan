"""Tests for cut-off threshold evidence.

Every expected value is hand-computed from arithmetic written into the test.
The metal-capture figures in particular are stated as fractions (7.5/7.6) rather
than decimals, so a reader can check them without trusting the implementation.
"""
import math

import pytest

from backend.src.services.sample_type_comparison import TypedComposite
from backend.src.services.threshold_analysis import (
    contact_analysis,
    log_probability_points,
    metal_capture_curve,
)


def _c(grade, length=1.0, x=None, y=None, z=None, sample_type="DDH"):
    return TypedComposite(grade, length, sample_type, x, y, z)


# --- log probability ---------------------------------------------------------

def test_hazen_plotting_positions():
    # n = 4, positions (i - 0.5) / n for i = 1..4
    result = log_probability_points([_c(1.0), _c(2.0), _c(3.0), _c(4.0)])

    assert [p.cumulative_probability for p in result.points] == [
        0.125, 0.375, 0.625, 0.875
    ]
    assert [p.grade for p in result.points] == [1.0, 2.0, 3.0, 4.0]


def test_non_positive_grades_are_excluded_and_counted():
    # 0.0 and -1.0 cannot go on a log axis. The two survivors are re-positioned
    # as a population of 2: (1 - 0.5)/2 = 0.25 and (2 - 0.5)/2 = 0.75.
    result = log_probability_points([_c(0.0), _c(-1.0), _c(2.0), _c(4.0)])

    assert len(result.points) == 2
    assert result.n_excluded_non_positive == 2
    assert [p.cumulative_probability for p in result.points] == [0.25, 0.75]


def test_log_prob_sorts_ascending_regardless_of_input_order():
    result = log_probability_points([_c(4.0), _c(1.0), _c(3.0), _c(2.0)])

    assert [p.grade for p in result.points] == [1.0, 2.0, 3.0, 4.0]


def test_log_prob_of_empty_population():
    result = log_probability_points([])

    assert result.points == []
    assert result.n_excluded_non_positive == 0


def test_log_prob_all_non_positive():
    result = log_probability_points([_c(0.0), _c(0.0)])

    assert result.points == []
    assert result.n_excluded_non_positive == 2


# --- metal capture -----------------------------------------------------------

def _capture_fixture():
    # Four composites, all 1 m: total_length 4.0, total_metal 7.6
    return [_c(0.1), _c(0.5), _c(2.0), _c(5.0)]


def test_metal_capture_arithmetic():
    rows = metal_capture_curve(_capture_fixture(), [0.0, 0.5, 2.0, 6.0])
    by_threshold = {r.threshold: r for r in rows}

    r = by_threshold[0.0]
    assert r.n_above == 4
    assert math.isclose(r.length_above, 4.0)
    assert math.isclose(r.metal_above, 7.6)
    assert math.isclose(r.length_fraction, 1.0)
    assert math.isclose(r.metal_fraction, 1.0)

    # 0.5 is INCLUDED at threshold 0.5 -- the comparison is >=.
    r = by_threshold[0.5]
    assert r.n_above == 3
    assert math.isclose(r.length_above, 3.0)
    assert math.isclose(r.metal_above, 7.5)
    assert math.isclose(r.length_fraction, 0.75)
    assert math.isclose(r.metal_fraction, 7.5 / 7.6)

    r = by_threshold[2.0]
    assert r.n_above == 2
    assert math.isclose(r.metal_above, 7.0)
    assert math.isclose(r.length_fraction, 0.5)
    assert math.isclose(r.metal_fraction, 7.0 / 7.6)

    r = by_threshold[6.0]
    assert r.n_above == 0
    assert math.isclose(r.length_above, 0.0)
    assert math.isclose(r.metal_fraction, 0.0)


def test_mean_grade_above_threshold():
    rows = metal_capture_curve(_capture_fixture(), [2.0])

    # 7.0 g/t-metres over 2.0 m
    assert math.isclose(rows[0].mean_grade_above, 3.5)


def test_mean_grade_above_is_none_when_nothing_qualifies():
    rows = metal_capture_curve(_capture_fixture(), [99.0])

    assert rows[0].mean_grade_above is None


def test_threshold_comparison_is_inclusive_and_consistent():
    # A composite exactly on the threshold must be counted in all three of
    # n_above, length_above and metal_above, or none.
    rows = metal_capture_curve([_c(1.0), _c(0.5)], [1.0])

    assert rows[0].n_above == 1
    assert math.isclose(rows[0].length_above, 1.0)
    assert math.isclose(rows[0].metal_above, 1.0)


def test_zero_metal_population_does_not_divide_by_zero():
    rows = metal_capture_curve([_c(0.0), _c(0.0)], [0.0, 1.0])

    assert all(r.metal_fraction is None for r in rows)
    # Length is still real even when the metal is not.
    assert math.isclose(rows[0].length_fraction, 1.0)


def test_below_threshold_composites_stay_in_the_denominator():
    # A barren composite carries length and belongs in the denominator, so
    # capturing all the metal still costs half the ground.
    rows = metal_capture_curve([_c(0.0), _c(4.0)], [1.0])

    assert math.isclose(rows[0].metal_fraction, 1.0)
    assert math.isclose(rows[0].length_fraction, 0.5)


def test_capture_uses_length_weighting_not_sample_counts():
    # 10 g/t over 0.5 m and 1 g/t over 9.5 m: total metal 14.5.
    # At 5.0 only the short sample qualifies: 5.0 / 14.5 of the metal, in
    # 0.5 / 10.0 of the ground.
    composites = [_c(10.0, length=0.5), _c(1.0, length=9.5)]

    rows = metal_capture_curve(composites, [5.0])

    assert math.isclose(rows[0].metal_fraction, 5.0 / 14.5)
    assert math.isclose(rows[0].length_fraction, 0.05)


def test_empty_population_returns_a_row_per_threshold():
    rows = metal_capture_curve([], [0.5, 1.0])

    assert len(rows) == 2
    assert all(r.n_above == 0 for r in rows)
    assert all(r.length_fraction is None for r in rows)


# --- contact analysis --------------------------------------------------------

def test_sharp_contact_shows_a_step_at_zero():
    # Composites on the x axis every 5 m. Below zero they are 0.1 g/t, at and
    # above zero 5.0 g/t. Threshold 1.0 puts the boundary at x = 0.
    composites = [
        _c(0.1 if x < 0 else 5.0, x=float(x), y=0.0, z=0.0)
        for x in range(-20, 25, 5)
    ]

    bins = contact_analysis(composites, threshold=1.0, bin_width=5.0,
                            max_distance=25.0)

    populated = [b for b in bins if b.n]
    negative = [b for b in populated if b.distance_bin_center < 0]
    positive = [b for b in populated if b.distance_bin_center > 0]

    assert negative and positive
    assert all(math.isclose(b.mean_grade, 0.1) for b in negative)
    assert all(math.isclose(b.mean_grade, 5.0) for b in positive)


def test_signs_follow_which_side_of_the_threshold_a_composite_is_on():
    composites = [
        _c(0.1, x=-10.0, y=0.0, z=0.0),
        _c(5.0, x=10.0, y=0.0, z=0.0),
    ]

    bins = contact_analysis(composites, threshold=1.0, bin_width=5.0,
                            max_distance=50.0)
    populated = {b.distance_bin_center: b for b in bins if b.n}

    # Each is 20 m from the other, so one lands at -20 and one at +20.
    assert any(c < 0 for c in populated)
    assert any(c > 0 for c in populated)
    below = [b for c, b in populated.items() if c < 0][0]
    above = [b for c, b in populated.items() if c > 0][0]
    assert math.isclose(below.mean_grade, 0.1)
    assert math.isclose(above.mean_grade, 5.0)


def test_composites_without_coordinates_are_excluded():
    composites = [
        _c(0.1, x=-10.0, y=0.0, z=0.0),
        _c(5.0, x=10.0, y=0.0, z=0.0),
        _c(9.0),  # no position
    ]

    bins = contact_analysis(composites, threshold=1.0)

    assert sum(b.n for b in bins) == 2


def test_contact_analysis_with_one_side_empty():
    # Everything above threshold: there is no other side to measure to.
    composites = [_c(5.0, x=float(i), y=0.0, z=0.0) for i in range(5)]

    bins = contact_analysis(composites, threshold=1.0)

    assert sum(b.n for b in bins) == 0


def test_composites_beyond_max_distance_are_dropped():
    composites = [
        _c(0.1, x=0.0, y=0.0, z=0.0),
        _c(5.0, x=500.0, y=0.0, z=0.0),
    ]

    bins = contact_analysis(composites, threshold=1.0, max_distance=50.0)

    assert sum(b.n for b in bins) == 0


def test_length_weighted_mean_reported_alongside_plain_mean():
    # Both above-threshold composites land in one bin: one short and high, one
    # long and lower.
    #   plain mean      = (10.0 + 6.0) / 2 = 8.0
    #   length-weighted = (10.0 * 0.5 + 6.0 * 9.5) / 10.0 = 62.0 / 10.0 = 6.2
    # The gap between them is the sample-support effect, and a contact plot
    # drawn on the plain mean alone would overstate the domain by 1.8 g/t.
    composites = [
        _c(10.0, length=0.5, x=-10.0, y=0.0, z=0.0),
        _c(6.0, length=9.5, x=-11.0, y=0.0, z=0.0),
        _c(0.0, length=1.0, x=10.0, y=0.0, z=0.0),
    ]

    bins = contact_analysis(composites, threshold=5.0, bin_width=50.0,
                            max_distance=50.0)
    populated = [b for b in bins if b.n == 2]

    assert populated
    assert math.isclose(populated[0].mean_grade, 8.0)
    assert math.isclose(populated[0].length_weighted_mean_grade, 6.2)


def test_no_bin_straddles_zero():
    composites = [
        _c(0.1, x=-1.0, y=0.0, z=0.0),
        _c(5.0, x=1.0, y=0.0, z=0.0),
    ]

    bins = contact_analysis(composites, threshold=1.0, bin_width=5.0,
                            max_distance=25.0)

    for b in bins:
        assert b.distance_bin_center != 0.0


def test_invalid_bin_parameters_raise():
    with pytest.raises(ValueError, match="bin_width"):
        contact_analysis([], threshold=1.0, bin_width=0.0)
    with pytest.raises(ValueError, match="max_distance"):
        contact_analysis([], threshold=1.0, max_distance=-1.0)


def test_contact_analysis_of_empty_population():
    bins = contact_analysis([], threshold=1.0)

    assert all(b.n == 0 for b in bins)
    assert all(b.mean_grade is None for b in bins)


# --- purity ------------------------------------------------------------------

def test_inputs_are_not_mutated():
    composites = _capture_fixture()
    before = list(composites)

    log_probability_points(composites)
    metal_capture_curve(composites, [0.5])
    contact_analysis(
        [_c(1.0, x=0.0, y=0.0, z=0.0), _c(9.0, x=1.0, y=0.0, z=0.0)],
        threshold=5.0,
    )

    assert composites == before
