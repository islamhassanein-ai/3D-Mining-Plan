"""Tests for length-weighted compositing.

Every expected value in this file is hand-computed from the arithmetic stated
in the test, not copied from the implementation's output. Where a number is not
self-evident the working is written into the test as a comment. If the
implementation ever disagrees with one of these numbers, the implementation is
wrong.
"""
import math

import pytest

from backend.src.services.compositing import (
    Composite,
    RawInterval,
    composite_intervals,
)


def _metal(items) -> float:
    """Grade-times-length summed over intervals or composites.

    For composites the assayed length is the part carrying grade, so that is
    what conserves metal when a composite spans unassayed ground.
    """
    total = 0.0
    for item in items:
        if isinstance(item, Composite):
            total += item.grade * item.assayed_length
        elif item.grade is not None:
            total += item.grade * (item.to_depth - item.from_depth)
    return total


# --- F1: clean whole-metre compositing ---------------------------------------

def test_clean_one_metre_composites():
    intervals = [
        RawInterval(0.0, 1.0, 2.0),
        RawInterval(1.0, 2.0, 4.0),
        RawInterval(2.0, 3.0, 6.0),
    ]

    result = composite_intervals(intervals, composite_length=1.0)

    assert len(result) == 3
    assert [c.grade for c in result] == [2.0, 4.0, 6.0]
    assert all(math.isclose(c.length, 1.0) for c in result)
    assert [c.from_depth for c in result] == [0.0, 1.0, 2.0]


# --- F2: length weighting ----------------------------------------------------

def test_grade_is_length_weighted_not_averaged():
    # 0.0-0.5 at 10.0 g/t, 0.5-2.0 at 2.0 g/t.
    # First composite spans 0-1: (10.0 * 0.5 + 2.0 * 0.5) / 1.0 = 6.0
    # An unweighted mean of the two source intervals would give 6.0 as well by
    # coincidence, so n_source_intervals is asserted to prove both contributed.
    intervals = [
        RawInterval(0.0, 0.5, 10.0),
        RawInterval(0.5, 2.0, 2.0),
    ]

    result = composite_intervals(intervals, composite_length=1.0)

    assert len(result) == 2
    assert math.isclose(result[0].grade, 6.0)
    assert result[0].n_source_intervals == 2
    assert math.isclose(result[1].grade, 2.0)
    assert result[1].n_source_intervals == 1


# --- F3: NULL grades are excluded, not zeroed --------------------------------

def test_null_grade_is_excluded_from_the_average():
    # 0.5 m assayed at 8.0 g/t, 0.5 m logged but never assayed.
    # Correct: 8.0 (the unassayed half is unknown, so it does not vote).
    # Wrong:   4.0 (NULL treated as 0.0 g/t).
    intervals = [
        RawInterval(0.0, 0.5, 8.0),
        RawInterval(0.5, 1.0, None),
    ]

    result = composite_intervals(intervals, composite_length=1.0)

    assert len(result) == 1
    assert math.isclose(result[0].grade, 8.0), "NULL grade was averaged in as zero"
    assert math.isclose(result[0].length, 1.0)
    assert math.isclose(result[0].assayed_length, 0.5)
    assert result[0].n_source_intervals == 1


def test_genuine_zero_grade_is_kept():
    # The counterpart to the test above: 0.0 g/t is a real assay result and
    # must be composited. A falsiness check on grade would drop it.
    intervals = [
        RawInterval(0.0, 0.5, 0.0),
        RawInterval(0.5, 1.0, 4.0),
    ]

    result = composite_intervals(intervals, composite_length=1.0)

    assert len(result) == 1
    assert math.isclose(result[0].grade, 2.0)  # (0.0 * 0.5 + 4.0 * 0.5) / 1.0
    assert math.isclose(result[0].assayed_length, 1.0)
    assert result[0].n_source_intervals == 2


# --- F4: fully unassayed windows are not emitted -----------------------------

def test_fully_unassayed_window_is_not_emitted():
    intervals = [
        RawInterval(0.0, 1.0, None),
        RawInterval(1.0, 2.0, 5.0),
    ]

    result = composite_intervals(intervals, composite_length=1.0)

    assert len(result) == 1
    assert math.isclose(result[0].from_depth, 1.0)
    assert math.isclose(result[0].grade, 5.0)


# --- F5: gaps break the compositing run --------------------------------------

def test_gap_breaks_the_run():
    intervals = [
        RawInterval(0.0, 1.0, 3.0),
        RawInterval(10.0, 11.0, 7.0),
    ]

    result = composite_intervals(intervals, composite_length=1.0)

    assert len(result) == 2
    assert (result[0].from_depth, result[0].to_depth) == (0.0, 1.0)
    assert (result[1].from_depth, result[1].to_depth) == (10.0, 11.0)
    assert math.isclose(result[0].grade, 3.0)
    assert math.isclose(result[1].grade, 7.0)
    # Nothing may be invented in the 9 m of unsampled ground between them.
    assert not any(1.0 < c.from_depth < 10.0 for c in result)


def test_gap_within_tolerance_does_not_break_the_run():
    # A 5 mm discontinuity is float noise from a CSV, not unsampled ground.
    intervals = [
        RawInterval(0.0, 1.0, 3.0),
        RawInterval(1.005, 2.005, 7.0),
    ]

    result = composite_intervals(intervals, composite_length=1.0, gap_tolerance=0.01)

    assert len(result) == 2
    assert math.isclose(result[0].from_depth, 0.0)
    # One continuous run 0.0-2.005: the 0.005 residual merges into composite 2.
    assert math.isclose(result[1].to_depth, 2.005)


def test_runs_restart_their_own_composite_grid():
    # The second run starts at 10.3, so its composites start at 10.3 -- not at
    # 10.0, which a global grid aligned to the hole collar would produce.
    intervals = [
        RawInterval(0.0, 1.0, 3.0),
        RawInterval(10.3, 12.3, 7.0),
    ]

    result = composite_intervals(intervals, composite_length=1.0)

    assert [c.from_depth for c in result] == [0.0, 10.3, 11.3]


# --- F6 / F7: residual handling ----------------------------------------------

def test_short_residual_merges_into_previous_composite():
    # 1.4 m of ground, 1.0 m composites. Residual 0.4 < 0.5 -> merged.
    result = composite_intervals(
        [RawInterval(0.0, 1.4, 5.0)], composite_length=1.0
    )

    assert len(result) == 1
    assert math.isclose(result[0].from_depth, 0.0)
    assert math.isclose(result[0].to_depth, 1.4)
    assert math.isclose(result[0].length, 1.4)
    assert math.isclose(result[0].grade, 5.0)


def test_long_residual_stands_alone():
    # 1.8 m of ground, 1.0 m composites. Residual 0.8 >= 0.5 -> own composite.
    result = composite_intervals(
        [RawInterval(0.0, 1.8, 5.0)], composite_length=1.0
    )

    assert len(result) == 2
    assert math.isclose(result[0].to_depth, 1.0)
    assert math.isclose(result[1].from_depth, 1.0)
    assert math.isclose(result[1].to_depth, 1.8)
    assert math.isclose(result[1].length, 0.8)
    assert all(math.isclose(c.grade, 5.0) for c in result)


def test_run_shorter_than_one_composite_is_still_emitted():
    # A 0.3 m intersection is exactly the kind of narrow high-grade sample that
    # must never be discarded for being short.
    result = composite_intervals(
        [RawInterval(0.0, 0.3, 25.0)], composite_length=1.0
    )

    assert len(result) == 1
    assert math.isclose(result[0].length, 0.3)
    assert math.isclose(result[0].grade, 25.0)


# --- F8: invalid input -------------------------------------------------------

def test_overlapping_intervals_raise():
    intervals = [
        RawInterval(0.0, 2.0, 1.0),
        RawInterval(1.0, 3.0, 2.0),
    ]

    with pytest.raises(ValueError, match="Overlap"):
        composite_intervals(intervals)


def test_inverted_interval_raises():
    with pytest.raises(ValueError, match="from_depth >= to_depth"):
        composite_intervals([RawInterval(5.0, 2.0, 1.0)])


def test_zero_length_interval_raises():
    with pytest.raises(ValueError, match="from_depth >= to_depth"):
        composite_intervals([RawInterval(2.0, 2.0, 1.0)])


def test_non_positive_composite_length_raises():
    with pytest.raises(ValueError, match="composite_length"):
        composite_intervals([RawInterval(0.0, 1.0, 1.0)], composite_length=0.0)


# --- F9: input order independence --------------------------------------------

def test_unsorted_input_gives_the_same_result():
    ordered = [
        RawInterval(0.0, 1.0, 2.0),
        RawInterval(1.0, 2.0, 4.0),
        RawInterval(2.0, 3.0, 6.0),
    ]
    shuffled = [ordered[2], ordered[0], ordered[1]]

    assert composite_intervals(shuffled) == composite_intervals(ordered)


def test_empty_input_returns_empty():
    assert composite_intervals([]) == []


# --- F10: metal is conserved -------------------------------------------------

def test_metal_conserved_across_length_weighting():
    # 10.0 * 0.5 + 2.0 * 1.5 = 8.0
    intervals = [
        RawInterval(0.0, 0.5, 10.0),
        RawInterval(0.5, 2.0, 2.0),
    ]

    result = composite_intervals(intervals, composite_length=1.0)

    assert math.isclose(_metal(intervals), 8.0)
    assert math.isclose(_metal(result), _metal(intervals), abs_tol=1e-9)


def test_metal_conserved_across_residual_split():
    # 5.0 * 1.8 = 9.0, split as 5.0 * 1.0 + 5.0 * 0.8
    intervals = [RawInterval(0.0, 1.8, 5.0)]

    result = composite_intervals(intervals, composite_length=1.0)

    assert math.isclose(_metal(intervals), 9.0)
    assert math.isclose(_metal(result), _metal(intervals), abs_tol=1e-9)


def test_metal_conserved_with_unassayed_ground():
    # The unassayed 0.5 m carries no metal in either the input or the output,
    # so the balance still holds -- which it would not if NULL became 0.0.
    intervals = [
        RawInterval(0.0, 0.5, 8.0),
        RawInterval(0.5, 1.0, None),
    ]

    result = composite_intervals(intervals, composite_length=1.0)

    assert math.isclose(_metal(intervals), 4.0)
    assert math.isclose(_metal(result), 4.0, abs_tol=1e-9)


# --- purity ------------------------------------------------------------------

def test_input_intervals_are_not_mutated():
    intervals = [
        RawInterval(2.0, 3.0, 6.0),
        RawInterval(0.0, 1.0, 2.0),
    ]
    before = list(intervals)

    composite_intervals(intervals)

    assert intervals == before


def test_composite_length_of_two_metres():
    # Sanity check that the composite length actually drives the windows.
    intervals = [RawInterval(0.0, 4.0, 3.0)]

    result = composite_intervals(intervals, composite_length=2.0)

    assert len(result) == 2
    assert all(math.isclose(c.length, 2.0) for c in result)
