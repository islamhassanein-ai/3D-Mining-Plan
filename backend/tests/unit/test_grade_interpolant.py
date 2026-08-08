"""Tests for anisotropic inverse-distance interpolation.

The rotation test (F2) is the one that matters most: swapping a sine for a
cosine there produces a shell rotated ninety degrees off the structure, which
looks entirely plausible and is wrong. The IDW arithmetic tests state their
working, so a reader can check 10/4 by hand rather than trusting the code.
"""
import math
import time

import numpy as np
import pytest

from backend.src.services.grade_interpolant import (
    SearchEllipsoid,
    inverse_distance_kernel,
    interpolate_grade_grid,
)
from backend.src.services.sample_type_comparison import TypedComposite

ALL_DDH = {"DDH": 1.0}


def _c(grade, x, y, z, sample_type="DDH", length=1.0):
    return TypedComposite(grade, length, sample_type, x, y, z)


def _isotropic(radius):
    return SearchEllipsoid(
        range_major=radius, range_semi=radius, range_minor=radius,
        strike_azimuth=0.0, dip=0.0,
    )


# --- grid and exact hits -----------------------------------------------------

def test_a_node_on_a_sample_reproduces_its_grade():
    # Padding and cell size chosen so the sample lands exactly on node (2,2,2).
    grid = interpolate_grade_grid(
        [_c(5.0, 100.0, 200.0, 300.0)],
        _isotropic(50.0), ALL_DDH,
        cell_size=10.0, padding=20.0, min_samples=1,
    )

    node = grid.values[2, 2, 2]
    assert math.isclose(node, 5.0, abs_tol=1e-6)


def test_node_world_coordinates_follow_origin_plus_index_times_cell():
    grid = interpolate_grade_grid(
        [_c(1.0, 100.0, 200.0, 300.0)],
        _isotropic(50.0), ALL_DDH,
        cell_size=10.0, padding=20.0, min_samples=1,
    )

    # origin is the sample position less the padding.
    assert math.isclose(grid.origin[0], 80.0)
    assert math.isclose(grid.origin[1], 180.0)
    assert math.isclose(grid.origin[2], 280.0)
    assert grid.values.shape == (5, 5, 5)
    assert grid.n_total == 125


# --- anisotropy --------------------------------------------------------------

def test_anisotropy_reaches_along_strike_not_across_it():
    # A 100 m major range due east, 10 m across. Two samples 50 m apart along
    # EAST are within one another's ellipsoid; the same pair along NORTH is not.
    # A swapped sin/cos in the rotation makes these two cases identical.
    east_west = SearchEllipsoid(
        range_major=100.0, range_semi=10.0, range_minor=10.0,
        strike_azimuth=90.0, dip=0.0,
    )

    along = interpolate_grade_grid(
        [_c(1.0, 0.0, 0.0, 0.0), _c(3.0, 50.0, 0.0, 0.0)],
        east_west, ALL_DDH, cell_size=5.0, padding=10.0, min_samples=2,
    )
    across = interpolate_grade_grid(
        [_c(1.0, 0.0, 0.0, 0.0), _c(3.0, 0.0, 50.0, 0.0)],
        east_west, ALL_DDH, cell_size=5.0, padding=10.0, min_samples=2,
    )

    assert along.n_estimated > 0
    assert across.n_estimated == 0


def test_dip_tilts_the_search_ellipsoid():
    # Strike north-south, dipping 90 degrees down: the semi axis then runs
    # vertically, so a sample directly below is reachable and one due east,
    # across the structure, is not.
    steep = SearchEllipsoid(
        range_major=5.0, range_semi=100.0, range_minor=5.0,
        strike_azimuth=0.0, dip=-90.0,
    )

    vertical = interpolate_grade_grid(
        [_c(1.0, 0.0, 0.0, 0.0), _c(3.0, 0.0, 0.0, -50.0)],
        steep, ALL_DDH, cell_size=5.0, padding=5.0, min_samples=2,
    )
    lateral = interpolate_grade_grid(
        [_c(1.0, 0.0, 0.0, 0.0), _c(3.0, 50.0, 0.0, 0.0)],
        steep, ALL_DDH, cell_size=5.0, padding=5.0, min_samples=2,
    )

    assert vertical.n_estimated > 0
    assert lateral.n_estimated == 0


def test_ellipsoid_rejects_non_positive_ranges():
    with pytest.raises(ValueError, match="range_major"):
        SearchEllipsoid(0.0, 10.0, 10.0, 0.0, 0.0)


# --- the no-extrapolation guard ----------------------------------------------

def test_a_lone_sample_leaves_everything_unestimated_when_two_are_required():
    grid = interpolate_grade_grid(
        [_c(5.0, 0.0, 0.0, 0.0)], _isotropic(50.0), ALL_DDH,
        cell_size=10.0, min_samples=2,
    )

    assert grid.n_estimated == 0
    assert np.all(np.isnan(grid.values))


def test_nodes_beyond_the_search_range_are_nan_not_zero():
    # Two samples in one corner, a padding wide enough to put the far corner
    # well outside any ellipsoid.
    grid = interpolate_grade_grid(
        [_c(5.0, 0.0, 0.0, 0.0), _c(5.0, 5.0, 0.0, 0.0)],
        _isotropic(20.0), ALL_DDH,
        cell_size=10.0, padding=100.0, min_samples=2,
    )

    assert np.isnan(grid.values[0, 0, 0])
    assert grid.n_estimated > 0
    assert grid.n_estimated < grid.n_total


def test_unestimated_nodes_are_never_filled_with_a_global_mean():
    grid = interpolate_grade_grid(
        [_c(7.0, 0.0, 0.0, 0.0), _c(7.0, 1.0, 0.0, 0.0)],
        _isotropic(5.0), ALL_DDH, cell_size=5.0, padding=60.0, min_samples=2,
    )

    far = grid.values[0, 0, 0]
    assert np.isnan(far), "unsampled ground must be nan, never a fallback value"


# --- inverse-distance arithmetic ---------------------------------------------

def test_midpoint_between_two_samples_is_their_mean():
    # Node (1,0,0) sits 10 m from each sample, so the weights are equal.
    grid = interpolate_grade_grid(
        [_c(0.0, -10.0, 0.0, 0.0), _c(10.0, 10.0, 0.0, 0.0)],
        _isotropic(50.0), ALL_DDH,
        cell_size=10.0, padding=0.0, min_samples=2,
    )

    assert math.isclose(grid.values[1, 0, 0], 5.0, abs_tol=1e-9)


def test_power_controls_how_sharply_distance_tells():
    # Node at the origin, sample A (0.0 g/t) 10 m away, sample B (10.0 g/t)
    # 20 m away. Ranges 100 m so both are comfortably inside.
    #   power 1: (0/0.1 + 10/0.2) / (1/0.1 + 1/0.2) = 50 / 15    = 3.3333...
    #   power 2: (0/0.01 + 10/0.04) / (1/0.01 + 1/0.04) = 250/125 = 2.0
    samples = [_c(0.0, -10.0, 0.0, 0.0), _c(10.0, 20.0, 0.0, 0.0)]
    ellipsoid = _isotropic(100.0)

    linear = interpolate_grade_grid(
        samples, ellipsoid, ALL_DDH, cell_size=10.0, padding=0.0,
        power=1.0, min_samples=2,
    )
    squared = interpolate_grade_grid(
        samples, ellipsoid, ALL_DDH, cell_size=10.0, padding=0.0,
        power=2.0, min_samples=2,
    )

    assert math.isclose(linear.values[1, 0, 0], 10.0 / 3.0, abs_tol=1e-6)
    assert math.isclose(squared.values[1, 0, 0], 2.0, abs_tol=1e-6)


# --- sample-type weights -----------------------------------------------------

def test_type_weights_scale_a_population_contribution():
    # Coincident samples equidistant from the midpoint node.
    samples = [
        _c(1.0, -10.0, 0.0, 0.0, sample_type="DDH"),
        _c(5.0, 10.0, 0.0, 0.0, sample_type="FC"),
    ]
    ellipsoid = _isotropic(50.0)

    both = interpolate_grade_grid(
        samples, ellipsoid, {"DDH": 1.0, "FC": 1.0},
        cell_size=10.0, padding=0.0, min_samples=2,
    )
    assert math.isclose(both.values[1, 0, 0], 3.0, abs_tol=1e-9)


def test_a_zero_weight_excludes_a_type_from_grade_entirely():
    # Decision D6: face channels define geometry and cast no vote on grade.
    samples = [
        _c(1.0, -10.0, 0.0, 0.0, sample_type="DDH"),
        _c(50.0, 10.0, 0.0, 0.0, sample_type="FC"),
    ]

    grid = interpolate_grade_grid(
        samples, _isotropic(50.0), {"DDH": 1.0, "FC": 0.0},
        cell_size=10.0, padding=0.0, min_samples=1,
    )

    node = grid.values[1, 0, 0]
    assert math.isclose(node, 1.0, abs_tol=1e-9), \
        "a zero-weighted type still influenced the grade"


def test_zero_weighted_samples_still_define_the_grid_extent():
    # They describe where the deposit was sampled even when they do not vote.
    with_fc = interpolate_grade_grid(
        [_c(1.0, 0.0, 0.0, 0.0, sample_type="DDH"),
         _c(1.0, 1.0, 0.0, 0.0, sample_type="DDH"),
         _c(9.0, 500.0, 0.0, 0.0, sample_type="FC")],
        _isotropic(20.0), {"DDH": 1.0, "FC": 0.0},
        cell_size=50.0, padding=0.0, min_samples=1,
    )

    assert with_fc.values.shape[0] > 5


def test_an_unweighted_sample_type_raises():
    with pytest.raises(ValueError, match="No weight given"):
        interpolate_grade_grid(
            [_c(1.0, 0.0, 0.0, 0.0, sample_type="TR")],
            _isotropic(10.0), {"DDH": 1.0}, min_samples=1,
        )


def test_all_types_zero_weighted_yields_an_empty_grid():
    grid = interpolate_grade_grid(
        [_c(1.0, 0.0, 0.0, 0.0, sample_type="FC")],
        _isotropic(10.0), {"FC": 0.0}, cell_size=10.0, min_samples=1,
    )

    assert grid.n_estimated == 0
    assert np.all(np.isnan(grid.values))


# --- replaceable engine (decision D2) ----------------------------------------

def test_a_custom_kernel_is_used():
    # A constant kernel makes every in-range sample count equally, so the node
    # becomes the unweighted mean: (1.0 + 4.0) / 2 = 2.5, not the
    # distance-weighted value.
    def constant(d_aniso):
        return np.ones_like(d_aniso)

    grid = interpolate_grade_grid(
        [_c(1.0, -10.0, 0.0, 0.0), _c(4.0, 20.0, 0.0, 0.0)],
        _isotropic(100.0), ALL_DDH,
        cell_size=10.0, padding=0.0, min_samples=2, kernel=constant,
    )

    assert math.isclose(grid.values[1, 0, 0], 2.5, abs_tol=1e-9)


def test_inverse_distance_kernel_rejects_non_positive_power():
    with pytest.raises(ValueError, match="power"):
        inverse_distance_kernel(0.0)


# --- determinism and validation ----------------------------------------------

def test_result_does_not_depend_on_input_order():
    samples = [
        _c(1.0, 0.0, 0.0, 0.0), _c(4.0, 10.0, 0.0, 0.0),
        _c(9.0, 0.0, 10.0, 0.0), _c(2.0, 0.0, 0.0, 10.0),
    ]
    ellipsoid = _isotropic(40.0)

    forward = interpolate_grade_grid(
        samples, ellipsoid, ALL_DDH, cell_size=5.0, min_samples=2)
    backward = interpolate_grade_grid(
        list(reversed(samples)), ellipsoid, ALL_DDH, cell_size=5.0,
        min_samples=2)

    np.testing.assert_array_equal(forward.values, backward.values)


def test_repeated_runs_are_bitwise_identical():
    samples = [_c(float(i), float(i) * 3.0, 0.0, 0.0) for i in range(10)]
    ellipsoid = _isotropic(30.0)

    first = interpolate_grade_grid(samples, ellipsoid, ALL_DDH, cell_size=5.0)
    second = interpolate_grade_grid(samples, ellipsoid, ALL_DDH, cell_size=5.0)

    np.testing.assert_array_equal(first.values, second.values)


def test_invalid_parameters_raise():
    samples = [_c(1.0, 0.0, 0.0, 0.0)]
    ellipsoid = _isotropic(10.0)

    with pytest.raises(ValueError, match="cell_size"):
        interpolate_grade_grid(samples, ellipsoid, ALL_DDH, cell_size=0.0)
    with pytest.raises(ValueError, match="min_samples"):
        interpolate_grade_grid(samples, ellipsoid, ALL_DDH, min_samples=0)
    with pytest.raises(ValueError, match="max_samples"):
        interpolate_grade_grid(
            samples, ellipsoid, ALL_DDH, min_samples=8, max_samples=4)


def test_empty_input_returns_an_empty_grid_without_raising():
    grid = interpolate_grade_grid([], _isotropic(10.0), ALL_DDH)

    assert grid.n_estimated == 0
    assert np.all(np.isnan(grid.values))


def test_composites_without_coordinates_are_ignored():
    grid = interpolate_grade_grid(
        [TypedComposite(5.0, 1.0, "DDH")], _isotropic(10.0), ALL_DDH,
        min_samples=1,
    )

    assert grid.n_estimated == 0


# --- max_samples -------------------------------------------------------------

def test_only_the_nearest_samples_contribute():
    # A node at the origin with one near sample and many distant ones. With
    # max_samples=1 only the nearest may vote, so the node takes its grade.
    samples = [_c(1.0, 0.0, 0.0, 0.0)]
    samples += [_c(100.0, float(20 + i), 0.0, 0.0) for i in range(8)]

    grid = interpolate_grade_grid(
        samples, _isotropic(200.0), ALL_DDH,
        cell_size=10.0, padding=0.0, min_samples=1, max_samples=1,
    )

    assert math.isclose(grid.values[0, 0, 0], 1.0, abs_tol=1e-6)


# --- performance -------------------------------------------------------------

def test_a_forty_cubed_grid_with_five_hundred_samples_is_quick():
    rng = np.random.default_rng(20260808)
    points = rng.uniform(0.0, 200.0, size=(500, 3))
    grades = rng.uniform(0.0, 10.0, size=500)
    samples = [
        _c(float(g), float(p[0]), float(p[1]), float(p[2]))
        for g, p in zip(grades, points)
    ]

    started = time.perf_counter()
    grid = interpolate_grade_grid(
        samples, _isotropic(40.0), ALL_DDH, cell_size=5.0, padding=0.0)
    elapsed = time.perf_counter() - started

    assert grid.values.size >= 40 ** 3
    assert elapsed < 3.0, f"took {elapsed:.2f}s"
