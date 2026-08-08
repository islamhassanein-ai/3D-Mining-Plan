"""Tests for shell geometric and statistical validation.

The containment tests carry the weight here. A naive +x ray gets face-, edge-
and vertex-aligned points wrong, and a marching-cubes mesh is full of exactly
those, so the robustness cases are not academic.

Metal capture is stated as a fraction (6/16) so a reader can check it by hand.
"""
import math

import pytest

from backend.src.services.isosurface import IsosurfaceResult, MeshComponent
from backend.src.services.sample_type_comparison import TypedComposite
from backend.src.services.shell_validation import (
    point_in_mesh,
    validate_shell,
)

# A 10 m cube from the origin, triangulated as 12 faces. Every edge is shared
# by exactly two triangles.
_CUBE_VERTICES = [
    (0.0, 0.0, 0.0), (10.0, 0.0, 0.0), (10.0, 10.0, 0.0), (0.0, 10.0, 0.0),
    (0.0, 0.0, 10.0), (10.0, 0.0, 10.0), (10.0, 10.0, 10.0), (0.0, 10.0, 10.0),
]
_CUBE_FACES = [
    (0, 2, 1), (0, 3, 2),      # bottom
    (4, 5, 6), (4, 6, 7),      # top
    (0, 1, 5), (0, 5, 4),      # front
    (3, 7, 6), (3, 6, 2),      # back
    (0, 4, 7), (0, 7, 3),      # left
    (1, 2, 6), (1, 6, 5),      # right
]


def _cube(faces=None, volume=1000.0):
    return MeshComponent(
        vertices=list(_CUBE_VERTICES),
        faces=list(_CUBE_FACES if faces is None else faces),
        volume=volume,
    )


def _result(components=None, threshold=1.0):
    components = [_cube()] if components is None else components
    return IsosurfaceResult(
        components=components,
        threshold=threshold,
        total_volume=sum(c.volume for c in components),
    )


def _c(grade, x, y, z, length=1.0, sample_type="DDH"):
    return TypedComposite(grade, length, sample_type, x, y, z)


# --- containment -------------------------------------------------------------

def test_a_point_inside_the_cube_is_inside():
    assert point_in_mesh((5.0, 5.0, 5.0), _cube()) is True


def test_points_outside_the_cube_are_outside():
    assert point_in_mesh((15.0, 5.0, 5.0), _cube()) is False
    assert point_in_mesh((-1.0, 5.0, 5.0), _cube()) is False
    assert point_in_mesh((5.0, 5.0, 20.0), _cube()) is False


def test_containment_is_robust_just_inside_and_outside_a_face():
    assert point_in_mesh((5.0, 5.0, 0.001), _cube()) is True
    assert point_in_mesh((5.0, 5.0, -0.001), _cube()) is False


def test_containment_is_robust_near_an_edge_and_a_vertex():
    # A pure +x ray from these points runs along a face or through a shared
    # edge and miscounts.
    assert point_in_mesh((5.0, 9.9999, 9.9999), _cube()) is True
    assert point_in_mesh((0.0001, 0.0001, 0.0001), _cube()) is True
    assert point_in_mesh((10.0001, 10.0001, 10.0001), _cube()) is False


def test_a_component_with_no_faces_contains_nothing():
    empty = MeshComponent(vertices=[], faces=[], volume=0.0)

    assert point_in_mesh((0.0, 0.0, 0.0), empty) is False


def test_inside_any_component_counts_as_inside_the_shell():
    far = MeshComponent(
        vertices=[(x + 100.0, y, z) for x, y, z in _CUBE_VERTICES],
        faces=list(_CUBE_FACES),
        volume=1000.0,
    )
    report = validate_shell(
        _result([_cube(), far]),
        [_c(5.0, 105.0, 5.0, 5.0)],
        threshold=1.0,
    )

    assert report.statistics.n_composites_inside == 1


# --- geometry ----------------------------------------------------------------

def test_a_closed_cube_reports_watertight():
    report = validate_shell(_result(), [], threshold=1.0)

    assert report.geometry.is_watertight is True
    assert report.geometry.n_boundary_edges == 0
    assert report.geometry.n_nonmanifold_edges == 0
    assert report.geometry.n_components == 1
    assert math.isclose(report.geometry.total_volume, 1000.0)


def test_removing_one_triangle_opens_the_mesh():
    opened = _cube(faces=_CUBE_FACES[1:])

    report = validate_shell(_result([opened]), [], threshold=1.0)

    assert report.geometry.is_watertight is False
    assert report.geometry.n_boundary_edges == 3
    assert any("not closed" in n for n in report.notes)


def test_degenerate_faces_are_counted():
    with_degenerate = _cube(faces=_CUBE_FACES + [(0, 0, 1)])

    report = validate_shell(_result([with_degenerate]), [], threshold=1.0)

    assert report.geometry.n_degenerate_faces == 1


def test_duplicate_faces_are_counted():
    with_duplicate = _cube(faces=_CUBE_FACES + [_CUBE_FACES[0]])

    report = validate_shell(_result([with_duplicate]), [], threshold=1.0)

    assert report.geometry.n_duplicate_faces == 1


def test_bounding_box_spans_the_shell():
    report = validate_shell(_result(), [], threshold=1.0)

    low, high = report.geometry.bounding_box
    assert low == (0.0, 0.0, 0.0)
    assert high == (10.0, 10.0, 10.0)


# --- metal capture and dilution ----------------------------------------------

def test_metal_capture_measures_against_all_above_threshold_material():
    # Inside: 4.0 and 2.0. Outside: 10.0. All 1 m, all above threshold.
    #   capture = (4 + 2) / (4 + 2 + 10) = 6 / 16 = 0.375
    # Inside-over-inside would give 1.0 and mean nothing.
    composites = [
        _c(4.0, 5.0, 5.0, 5.0),
        _c(2.0, 6.0, 6.0, 6.0),
        _c(10.0, 50.0, 50.0, 50.0),
    ]

    report = validate_shell(_result(), composites, threshold=1.0)

    assert report.statistics.n_composites_inside == 2
    assert report.statistics.n_composites_above_threshold == 3
    assert math.isclose(report.statistics.metal_capture, 6.0 / 16.0)


def test_internal_dilution_is_waste_length_over_enclosed_length():
    # Three composites inside, one of them below threshold: 1.0 m of 3.0 m.
    composites = [
        _c(4.0, 5.0, 5.0, 5.0),
        _c(2.0, 6.0, 6.0, 6.0),
        _c(0.2, 4.0, 4.0, 4.0),
        _c(10.0, 50.0, 50.0, 50.0),
    ]

    report = validate_shell(_result(), composites, threshold=1.0)

    assert report.statistics.n_composites_inside == 3
    assert math.isclose(report.statistics.internal_dilution, 1.0 / 3.0)


def test_mean_grade_inside_is_length_weighted():
    # (4.0 * 1.0 + 2.0 * 3.0) / 4.0 = 2.5
    composites = [
        _c(4.0, 5.0, 5.0, 5.0, length=1.0),
        _c(2.0, 6.0, 6.0, 6.0, length=3.0),
    ]

    report = validate_shell(_result(), composites, threshold=1.0)

    assert math.isclose(report.statistics.mean_grade_inside, 2.5)


def test_low_metal_capture_is_noted_not_enforced():
    composites = [
        _c(1.0, 5.0, 5.0, 5.0),
        _c(99.0, 50.0, 50.0, 50.0),
    ]

    report = validate_shell(_result(), composites, threshold=1.0)

    assert report.statistics.metal_capture < 0.9
    assert any("Metal capture" in n for n in report.notes)
    # No verdict is issued -- the geologist decides.
    assert not hasattr(report, "is_valid")


def test_high_internal_dilution_is_noted():
    composites = [
        _c(4.0, 5.0, 5.0, 5.0, length=1.0),
        _c(0.1, 6.0, 6.0, 6.0, length=9.0),
    ]

    report = validate_shell(_result(), composites, threshold=1.0)

    assert report.statistics.internal_dilution > 0.25
    assert any("Internal dilution" in n for n in report.notes)


# --- by sample type ----------------------------------------------------------

def test_statistics_are_broken_out_by_sample_type():
    composites = [
        _c(4.0, 5.0, 5.0, 5.0, sample_type="DDH"),
        _c(2.0, 6.0, 6.0, 6.0, sample_type="TR"),
        _c(9.0, 50.0, 50.0, 50.0, sample_type="TR"),
    ]

    report = validate_shell(_result(), composites, threshold=1.0)
    by_type = {s.sample_type: s for s in report.statistics.by_sample_type}

    assert set(by_type) == {"DDH", "TR"}
    assert by_type["DDH"].n_inside == 1
    assert by_type["DDH"].n_outside == 0
    assert by_type["TR"].n_inside == 1
    assert by_type["TR"].n_outside == 1
    assert math.isclose(by_type["TR"].mean_grade_inside, 2.0)


def test_a_type_entirely_outside_the_shell_is_noted():
    composites = [
        _c(4.0, 5.0, 5.0, 5.0, sample_type="DDH"),
        _c(9.0, 50.0, 50.0, 50.0, sample_type="FC"),
    ]

    report = validate_shell(_result(), composites, threshold=1.0)

    assert any("No FC composite" in n for n in report.notes)


# --- degenerate inputs -------------------------------------------------------

def test_an_empty_shell_captures_nothing_without_raising():
    composites = [_c(5.0, 5.0, 5.0, 5.0)]

    report = validate_shell(
        IsosurfaceResult(components=[], threshold=1.0, total_volume=0.0),
        composites, threshold=1.0,
    )

    assert report.statistics.n_composites_inside == 0
    # Zero of a non-zero total is 0.0, which is a real answer; None would
    # wrongly say the question could not be asked.
    assert report.statistics.metal_capture == 0.0
    assert report.statistics.internal_dilution is None
    assert any("No shell" in n for n in report.notes)


def test_metal_capture_is_undefined_when_nothing_reaches_the_threshold():
    composites = [_c(0.1, 5.0, 5.0, 5.0)]

    report = validate_shell(_result(), composites, threshold=1.0)

    assert report.statistics.n_composites_above_threshold == 0
    assert report.statistics.metal_capture is None
    assert any("undefined" in n for n in report.notes)


def test_no_composites_at_all():
    report = validate_shell(_result(), [], threshold=1.0)

    assert report.statistics.n_composites_inside == 0
    assert report.statistics.metal_capture is None
    assert report.statistics.internal_dilution is None
    assert report.statistics.by_sample_type == []


def test_composites_without_coordinates_are_ignored():
    composites = [
        _c(4.0, 5.0, 5.0, 5.0),
        TypedComposite(9.0, 1.0, "DDH"),
    ]

    report = validate_shell(_result(), composites, threshold=1.0)

    assert report.statistics.n_composites_inside == 1
    assert report.statistics.n_composites_above_threshold == 1
