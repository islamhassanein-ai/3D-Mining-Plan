"""Absolute-depth trace placement and unsampled-gap detection."""
import math

import pytest

from backend.src.services.desurvey import compute_minimum_curvature_trace
from backend.src.services.downhole_log import (
    compute_total_depth,
    extend_trace_to_depth,
    find_unsampled_gaps,
    interpolate_trace_position,
)
from backend.src.services.grade_coloring import (
    UNSAMPLED_COLOR,
    get_grade_bucket_index,
    get_grade_color,
    is_unsampled,
)


def _vertical_trace(total=100.0):
    return compute_minimum_curvature_trace(
        0.0, 0.0, 0.0,
        [{"depth": 0.0, "dip": -90.0, "azimuth": 0.0},
         {"depth": total, "dip": -90.0, "azimuth": 0.0}],
    )


# --------------------------------------------------------------------------
# Absolute depth placement (the AADD004 regression)
# --------------------------------------------------------------------------

def test_first_assay_under_unsampled_top_zone_is_placed_at_its_own_depth():
    """AADD004: no samples 0 - 37 m, first assay 37 - 38 m.

    The interval must land 37 m down the trace, NOT at the collar.
    """
    trace = _vertical_trace(100.0)

    start = interpolate_trace_position(trace, 37.0)
    end = interpolate_trace_position(trace, 38.0)

    collar = interpolate_trace_position(trace, 0.0)
    assert start != collar
    # Vertical hole: elevation drops by exactly the downhole distance.
    assert start[2] == pytest.approx(-37.0)
    assert end[2] == pytest.approx(-38.0)


def test_placement_is_independent_of_how_many_intervals_precede_it():
    """Position depends only on absolute depth, never on interval ordinal."""
    trace = _vertical_trace(100.0)
    assert (interpolate_trace_position(trace, 37.0)
            == interpolate_trace_position(trace, 37.0))
    # A hole with 1 interval at 37 m and one with 20 intervals ending at 37 m
    # must agree, because neither consults the interval list.
    assert interpolate_trace_position(trace, 37.0)[2] == pytest.approx(-37.0)


def test_inclined_hole_uses_distance_along_the_curve():
    trace = compute_minimum_curvature_trace(
        0.0, 0.0, 0.0,
        [{"depth": 0.0, "dip": -45.0, "azimuth": 90.0},
         {"depth": 100.0, "dip": -45.0, "azimuth": 90.0}],
    )
    pos = interpolate_trace_position(trace, 37.0)
    # 37 m along a 45-degree hole bearing due East.
    assert pos[0] == pytest.approx(37.0 * math.cos(math.radians(45)), abs=1e-6)
    assert pos[2] == pytest.approx(-37.0 * math.cos(math.radians(45)), abs=1e-6)


# --------------------------------------------------------------------------
# Trace extension
# --------------------------------------------------------------------------

def test_intervals_below_last_survey_station_do_not_collapse_together():
    """Without extension, everything past the last station clamps to one point."""
    short = _vertical_trace(40.0)

    # Deepest logged interval runs to 90 m, well past the last survey at 40 m.
    assert interpolate_trace_position(short, 60.0) == interpolate_trace_position(short, 90.0)

    extended = extend_trace_to_depth(short, 90.0)
    assert interpolate_trace_position(extended, 60.0) != interpolate_trace_position(extended, 90.0)
    assert interpolate_trace_position(extended, 90.0)[2] == pytest.approx(-90.0)


def test_extend_trace_is_a_no_op_when_already_long_enough():
    trace = _vertical_trace(100.0)
    assert extend_trace_to_depth(trace, 100.0) is trace
    assert extend_trace_to_depth(trace, 50.0) is trace


def test_extend_trace_follows_the_last_station_orientation():
    trace = compute_minimum_curvature_trace(
        0.0, 0.0, 0.0,
        [{"depth": 0.0, "dip": -90.0, "azimuth": 0.0},
         {"depth": 10.0, "dip": 0.0, "azimuth": 90.0}],
    )
    extended = extend_trace_to_depth(trace, 20.0)
    tail = extended[-1]
    # Final station is horizontal bearing East: 10 m more easting, no drop.
    assert tail["x"] - trace[-1]["x"] == pytest.approx(10.0)
    assert tail["z"] == pytest.approx(trace[-1]["z"])


def test_compute_total_depth_takes_the_deepest_source():
    trace = _vertical_trace(40.0)
    assert compute_total_depth(trace, [10.0, 90.0]) == 90.0
    assert compute_total_depth(trace, [10.0, 20.0]) == 40.0
    assert compute_total_depth(trace, [10.0], declared_total=120.0) == 120.0
    assert compute_total_depth([], []) == 0.0


# --------------------------------------------------------------------------
# Unsampled gaps
# --------------------------------------------------------------------------

def test_unsampled_top_zone_is_reported():
    gaps = find_unsampled_gaps([(37.0, 38.0), (38.0, 40.0)], 60.0)
    assert gaps == [(0.0, 37.0), (40.0, 60.0)]


def test_fully_sampled_hole_has_no_gaps():
    assert find_unsampled_gaps([(0.0, 50.0)], 50.0) == []


def test_hole_with_no_assays_is_one_continuous_gap():
    assert find_unsampled_gaps([], 44.3) == [(0.0, 44.3)]


def test_overlapping_and_unordered_intervals_are_swept_correctly():
    gaps = find_unsampled_gaps([(20.0, 30.0), (0.0, 25.0), (28.0, 40.0)], 50.0)
    assert gaps == [(40.0, 50.0)]


def test_gap_list_plus_intervals_covers_the_whole_hole():
    intervals = [(5.0, 10.0), (20.0, 25.0)]
    total = 40.0
    covered = sum(t - f for f, t in intervals)
    covered += sum(t - f for f, t in find_unsampled_gaps(intervals, total))
    assert covered == pytest.approx(total)


# --------------------------------------------------------------------------
# Unsampled classification / colour lookup
# --------------------------------------------------------------------------

@pytest.mark.parametrize("sample_id", [
    "Unsampled", "NSR", "NS", "No Sample", "No Samples",
    "  no sample  ", "UNSAMPLED", "nsr",
])
def test_placeholder_sample_ids_are_unsampled(sample_id):
    assert is_unsampled(1.5, sample_id) is True
    assert get_grade_color(1.5, "g/t", sample_id) == UNSAMPLED_COLOR


@pytest.mark.parametrize("grade", [None, float("nan"), "", "not-a-number"])
def test_missing_or_malformed_grades_are_unsampled_without_raising(grade):
    assert is_unsampled(grade) is True
    assert get_grade_color(grade) == UNSAMPLED_COLOR
    assert get_grade_bucket_index(grade) == -1


def test_zero_grade_is_a_real_result_not_unsampled():
    """0.0 g/t is a genuine barren assay and must not read as 'no sample'."""
    assert is_unsampled(0.0) is False
    assert get_grade_color(0.0) != UNSAMPLED_COLOR


@pytest.mark.parametrize("grade,expected", [
    (0.0,   "#64748b"),  # < 0.10  slate grey
    (0.09,  "#64748b"),
    (0.10,  "#2563eb"),  # 0.10 - 0.30  blue
    (0.29,  "#2563eb"),
    (0.30,  "#22c55e"),  # 0.30 - 0.50  bright green
    (0.49,  "#22c55e"),
    (0.50,  "#f97316"),  # 0.50 - 1.00  orange
    (0.99,  "#f97316"),
    (1.00,  "#ef4444"),  # 1.00 - 3.00  bright red
    (2.99,  "#ef4444"),
    (3.00,  "#ec4899"),  # >= 3.00  magenta
    (150.0, "#ec4899"),
])
def test_grade_scale_bracket_boundaries(grade, expected):
    assert get_grade_color(grade, "g/t") == expected
