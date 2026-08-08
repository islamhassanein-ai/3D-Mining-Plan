"""End-to-end: composites -> interpolant -> iso-surface -> validation.

The four services are unit-tested in isolation, which does not catch an
interface drifting between them -- a grid origin read as a centre, a sample type
that never reaches the weights, a mesh in index space instead of world space.
This runs the chain on a synthetic body whose answer is known by construction.

No Adel data and no geological parameters are used here. The ellipsoid values
are whatever suits the synthetic body.
"""
import math

import pytest

from backend.src.services.grade_interpolant import (
    SearchEllipsoid,
    interpolate_grade_grid,
)
from backend.src.services.isosurface import extract_isosurface, mesh_to_obj
from backend.src.services.obj_geometry import parse_obj
from backend.src.services.sample_type_comparison import TypedComposite
from backend.src.services.shell_validation import validate_shell

THRESHOLD = 1.0


def _synthetic_body():
    """A high-grade core inside a barren halo, on a 10 m lattice.

    The core spans 40-60 m on every axis at 5 g/t; everything around it is
    0.05 g/t. A shell at 1 g/t should enclose the core and little else.
    """
    composites = []
    for x in range(0, 101, 10):
        for y in range(0, 101, 10):
            for z in range(0, 101, 10):
                in_core = all(40 <= v <= 60 for v in (x, y, z))
                composites.append(TypedComposite(
                    grade=5.0 if in_core else 0.05,
                    length=1.0,
                    sample_type="DDH",
                    x=float(x), y=float(y), z=float(z),
                ))
    return composites


@pytest.fixture(scope="module")
def pipeline():
    composites = _synthetic_body()
    grid = interpolate_grade_grid(
        composites,
        SearchEllipsoid(range_major=25.0, range_semi=25.0, range_minor=25.0,
                        strike_azimuth=0.0, dip=0.0),
        sample_type_weights={"DDH": 1.0},
        cell_size=5.0,
        padding=10.0,
        min_samples=2,
    )
    result = extract_isosurface(grid, threshold=THRESHOLD)
    report = validate_shell(result, composites, threshold=THRESHOLD)
    return composites, grid, result, report


def test_the_interpolant_estimates_the_sampled_region(pipeline):
    _composites, grid, _result, _report = pipeline

    assert grid.n_estimated > 0
    assert grid.n_estimated <= grid.n_total


def test_a_shell_is_produced_and_is_watertight(pipeline):
    _composites, _grid, result, report = pipeline

    assert result.components, "no shell was produced"
    assert report.geometry.is_watertight, report.notes


def test_the_shell_sits_where_the_high_grade_core_is(pipeline):
    _composites, _grid, result, _report = pipeline

    xs = [v[0] for c in result.components for v in c.vertices]
    ys = [v[1] for c in result.components for v in c.vertices]
    zs = [v[2] for c in result.components for v in c.vertices]

    # The core is 40-60; the shell should surround it without reaching the
    # edges of the sampled block.
    for axis in (xs, ys, zs):
        assert min(axis) > 10.0
        assert max(axis) < 90.0
        assert min(axis) < 40.0
        assert max(axis) > 60.0


def test_the_shell_captures_the_high_grade_material(pipeline):
    _composites, _grid, _result, report = pipeline

    assert report.statistics.metal_capture is not None
    assert report.statistics.metal_capture > 0.9, report.notes


def test_high_grade_composites_are_inside_and_barren_ones_are_not(pipeline):
    composites, _grid, result, report = pipeline

    n_core = sum(1 for c in composites if c.grade > 1.0)
    assert report.statistics.n_composites_above_threshold == n_core
    assert report.statistics.n_composites_inside >= n_core
    assert report.statistics.mean_grade_inside > 1.0


def test_the_shell_volume_is_the_right_order_of_magnitude(pipeline):
    _composites, _grid, result, _report = pipeline

    # The 5 g/t core spans 20 m on a side; interpolation rounds its corners and
    # spreads it somewhat, so anything from a fraction of 8000 m3 to a few
    # times it is reasonable. This catches a shell that is out by a factor of
    # a thousand -- an index-space mesh, or a cell_size never applied.
    assert 1_000.0 < result.total_volume < 200_000.0


def test_the_shell_survives_a_round_trip_through_the_obj_reader(pipeline):
    _composites, _grid, result, _report = pipeline

    parsed = parse_obj(mesh_to_obj(result))

    assert len(parsed["vertices"]) == sum(
        len(c.vertices) for c in result.components)
    assert len(parsed["faces"]) == sum(len(c.faces) for c in result.components)


def test_a_zero_weighted_type_cannot_create_a_shell_on_its_own():
    # Decision D6 end to end: a population weighted 0.0 defines no grade, so
    # no shell can form around it however high it reads.
    composites = [
        TypedComposite(50.0, 1.0, "FC", float(x), float(y), float(z))
        for x in (0, 10, 20) for y in (0, 10, 20) for z in (0, 10, 20)
    ]

    grid = interpolate_grade_grid(
        composites,
        SearchEllipsoid(20.0, 20.0, 20.0, 0.0, 0.0),
        sample_type_weights={"FC": 0.0},
        cell_size=5.0, min_samples=1,
    )
    result = extract_isosurface(grid, threshold=THRESHOLD)

    assert grid.n_estimated == 0
    assert result.components == []
