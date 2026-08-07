"""Tests for the database-to-TypedComposite transformation.

The transformation itself is pure and is tested here without a database; the
querying is covered by backend/tests/integration/test_composite_points_flow.py.

Every expected coordinate is hand-computed from the geometry stated in the
test. Two of them exist specifically to fail loudly if a convention drifts: a
vertical hole's elevation must DECREASE with depth (dip sign), and a trench
sample must keep the elevation its row states (dip is ground slope, not a
trajectory).
"""
import math

import pytest

from backend.src.services.composite_points import (
    build_drillhole_composites,
    build_trench_composites,
)
from backend.src.services.compositing import RawInterval

_COLLAR = {
    "hole_id": "TEST-001",
    "easting": 1000.0,
    "northing": 2000.0,
    "elevation": 500.0,
}


def _vertical(depth=100.0):
    return [
        {"depth": 0.0, "dip": -90.0, "azimuth": 0.0},
        {"depth": depth, "dip": -90.0, "azimuth": 0.0},
    ]


# --- drillhole geometry ------------------------------------------------------

def test_vertical_hole_places_composites_below_the_collar():
    # Collar at 500 m elevation, vertical. Two 1 m composites, midpoints at
    # 0.5 m and 1.5 m downhole, so elevations 499.5 and 498.5.
    composites, _ = build_drillhole_composites(
        _COLLAR, _vertical(), [RawInterval(0.0, 2.0, 3.0)]
    )

    assert len(composites) == 2
    assert math.isclose(composites[0].z, 499.5, abs_tol=1e-6)
    assert math.isclose(composites[1].z, 498.5, abs_tol=1e-6)
    assert composites[0].z > composites[1].z, "elevation must decrease with depth"
    assert all(math.isclose(c.x, 1000.0, abs_tol=1e-6) for c in composites)
    assert all(math.isclose(c.y, 2000.0, abs_tol=1e-6) for c in composites)


def test_coordinates_are_easting_northing_elevation_with_no_axis_swap():
    # Northing 2000 must land in y and elevation 500 in z. A Y-up swap would
    # put 2000 in z, which is the trap obj_geometry.py warns about.
    composites, _ = build_drillhole_composites(
        _COLLAR, _vertical(), [RawInterval(0.0, 1.0, 1.0)]
    )

    assert math.isclose(composites[0].y, 2000.0, abs_tol=1e-6)
    assert math.isclose(composites[0].z, 499.5, abs_tol=1e-6)


def test_horizontal_hole_due_east():
    # dip 0 is horizontal, azimuth 90 is due East: easting advances, northing
    # and elevation do not.
    surveys = [
        {"depth": 0.0, "dip": 0.0, "azimuth": 90.0},
        {"depth": 10.0, "dip": 0.0, "azimuth": 90.0},
    ]
    collar = {"hole_id": "H", "easting": 0.0, "northing": 0.0, "elevation": 0.0}

    composites, _ = build_drillhole_composites(
        collar, surveys, [RawInterval(0.0, 2.0, 1.0)]
    )

    assert math.isclose(composites[0].x, 0.5, abs_tol=1e-6)
    assert math.isclose(composites[1].x, 1.5, abs_tol=1e-6)
    assert all(math.isclose(c.y, 0.0, abs_tol=1e-6) for c in composites)
    assert all(math.isclose(c.z, 0.0, abs_tol=1e-6) for c in composites)


def test_composite_is_placed_at_its_midpoint_not_its_top():
    # A single 4 m composite over 0-4 m sits at 2 m downhole, elevation 498.
    composites, _ = build_drillhole_composites(
        _COLLAR, _vertical(), [RawInterval(0.0, 4.0, 1.0)], composite_length=4.0
    )

    assert len(composites) == 1
    assert math.isclose(composites[0].z, 498.0, abs_tol=1e-6)


def test_samples_below_the_last_survey_station_are_not_stacked():
    # Surveys stop at 5 m, assays run to 20 m. Without extending the trace the
    # deep composites would all clamp to the 5 m position.
    composites, warnings = build_drillhole_composites(
        _COLLAR, _vertical(depth=5.0), [RawInterval(0.0, 20.0, 1.0)]
    )

    assert len(composites) == 20
    depths = [c.z for c in composites]
    assert len(set(depths)) == 20
    assert math.isclose(composites[-1].z, 500.0 - 19.5, abs_tol=1e-6)
    assert any("surveys stop" in w for w in warnings)


def test_hole_without_surveys_yields_nothing():
    # No trajectory means no position. A vertical fallback would place real
    # assays at invented coordinates.
    composites, _ = build_drillhole_composites(
        _COLLAR, [], [RawInterval(0.0, 2.0, 3.0)]
    )

    assert composites == []


def test_unassayed_intervals_do_not_become_composites():
    composites, _ = build_drillhole_composites(
        _COLLAR,
        _vertical(),
        [RawInterval(0.0, 1.0, None), RawInterval(1.0, 2.0, 5.0)],
    )

    assert len(composites) == 1
    assert math.isclose(composites[0].grade, 5.0)
    assert math.isclose(composites[0].z, 498.5, abs_tol=1e-6)


def test_genuine_zero_grade_survives_to_a_composite():
    composites, _ = build_drillhole_composites(
        _COLLAR, _vertical(), [RawInterval(0.0, 1.0, 0.0)]
    )

    assert len(composites) == 1
    assert math.isclose(composites[0].grade, 0.0)


def test_drillhole_composites_are_typed_ddh():
    composites, _ = build_drillhole_composites(
        _COLLAR, _vertical(), [RawInterval(0.0, 1.0, 1.0)]
    )

    assert composites[0].sample_type == "DDH"


def test_overlapping_intervals_propagate_as_valueerror():
    # The caller catches this per hole; it must not be swallowed here.
    with pytest.raises(ValueError, match="Overlap"):
        build_drillhole_composites(
            _COLLAR,
            _vertical(),
            [RawInterval(0.0, 2.0, 1.0), RawInterval(1.0, 3.0, 2.0)],
        )


# --- trench geometry ---------------------------------------------------------

def _trench_point(order, e, n, z, grade, hole_type="TR", frm=None, to=None):
    return {
        "trench_id": "TR-001",
        "point_order": order,
        "easting": e,
        "northing": n,
        "elevation": z,
        "grade_value": grade,
        "hole_type": hole_type,
        "from_depth": frm,
        "to_depth": to,
    }


def test_trench_sample_sits_at_the_coordinates_its_row_states():
    points = [
        _trench_point(0, 100.0, 200.0, 300.0, 2.0, frm=0.0, to=1.0),
        _trench_point(1, 110.0, 200.0, 300.0, 4.0, frm=1.0, to=2.0),
    ]

    composites, _, _ = build_trench_composites(points)

    assert len(composites) == 2
    assert math.isclose(composites[0].x, 100.0)
    assert math.isclose(composites[1].x, 110.0)
    assert all(math.isclose(c.z, 300.0) for c in composites)


def test_trench_sample_ignores_dip_and_stays_at_its_stated_elevation():
    # dip on a trench row is ground slope at the start point, never a
    # trajectory. Applying it would push samples below or above surface.
    points = [_trench_point(0, 100.0, 200.0, 300.0, 2.0, frm=0.0, to=1.0)]
    points[0]["dip"] = -45.0
    points[0]["azimuth"] = 90.0

    composites, _, _ = build_trench_composites(points)

    assert math.isclose(composites[0].z, 300.0)


def test_trench_sample_length_comes_from_its_chainage_interval():
    points = [_trench_point(0, 100.0, 200.0, 300.0, 2.0, frm=4.0, to=6.0)]

    composites, _, _ = build_trench_composites(points)

    assert math.isclose(composites[0].length, 2.0)


def test_trench_row_without_a_stated_length_is_excluded_by_default():
    # The legacy trench uploaders record a point and a grade and nothing else.
    # Inventing a sample length would silently set the support of the whole
    # trench population.
    points = [_trench_point(0, 100.0, 200.0, 300.0, 2.0)]

    composites, warnings, _ = build_trench_composites(points)

    assert composites == []
    assert any("states no sample length" in w for w in warnings)


def test_trench_row_without_a_length_is_included_under_a_stated_assumption():
    points = [_trench_point(0, 100.0, 200.0, 300.0, 2.0)]

    composites, _, _ = build_trench_composites(
        points, length_when_unspecified=1.0
    )

    assert len(composites) == 1
    assert math.isclose(composites[0].length, 1.0)


def test_unassayed_trench_rows_are_counted_not_composited():
    # point_order 1 here is the generated far-end vertex of a single-row
    # trench: geometry only, never a sample.
    points = [
        _trench_point(0, 100.0, 200.0, 300.0, 2.0, frm=0.0, to=1.0),
        _trench_point(1, 200.0, 200.0, 300.0, None),
    ]

    composites, _, n_unassayed = build_trench_composites(points)

    assert len(composites) == 1
    assert n_unassayed == 1


def test_trench_sample_types_are_preserved_separately():
    points = [
        _trench_point(0, 1.0, 1.0, 1.0, 1.0, hole_type="TR", frm=0.0, to=1.0),
        _trench_point(1, 2.0, 1.0, 1.0, 1.0, hole_type="CH", frm=0.0, to=1.0),
        _trench_point(2, 3.0, 1.0, 1.0, 1.0, hole_type="FC", frm=0.0, to=1.0),
    ]

    composites, _, _ = build_trench_composites(points)

    assert [c.sample_type for c in composites] == ["TR", "CH", "FC"]


def test_unknown_or_missing_trench_type_defaults_to_tr():
    points = [
        _trench_point(0, 1.0, 1.0, 1.0, 1.0, hole_type=None, frm=0.0, to=1.0),
        _trench_point(1, 2.0, 1.0, 1.0, 1.0, hole_type="channel", frm=0.0, to=1.0),
    ]

    composites, _, _ = build_trench_composites(points)

    assert [c.sample_type for c in composites] == ["TR", "TR"]


def test_trench_type_is_case_insensitive():
    points = [_trench_point(0, 1.0, 1.0, 1.0, 1.0, hole_type="fc", frm=0.0, to=1.0)]

    composites, _, _ = build_trench_composites(points)

    assert composites[0].sample_type == "FC"


def test_trench_row_without_elevation_is_reported_not_placed_at_zero():
    points = [_trench_point(0, 100.0, 200.0, None, 2.0, frm=0.0, to=1.0)]

    composites, warnings, _ = build_trench_composites(points)

    assert composites == []
    assert any("no complete position" in w for w in warnings)


def test_duplicate_chainage_across_parallel_channels_does_not_raise():
    # AAF002 in the real database carries two samples at chainage 0-1 and two
    # more at 1-2: parallel channel lines sharing a trench_id. Compositing
    # along chainage would raise on the overlap; placing each row at its own
    # coordinates keeps both samples.
    points = [
        _trench_point(0, 100.0, 200.0, 300.0, 5.86, frm=0.0, to=1.0),
        _trench_point(1, 100.8, 200.2, 300.0, 2.82, frm=0.0, to=1.0),
        _trench_point(2, 101.5, 201.0, 300.0, 8.54, frm=1.0, to=2.0),
        _trench_point(3, 102.6, 201.4, 300.0, 35.90, frm=1.0, to=2.0),
    ]

    composites, _, _ = build_trench_composites(points)

    assert len(composites) == 4
    assert math.isclose(composites[0].grade, 5.86)
    assert math.isclose(composites[3].grade, 35.90)


def test_trench_genuine_zero_grade_is_kept():
    points = [_trench_point(0, 100.0, 200.0, 300.0, 0.0, frm=0.0, to=1.0)]

    composites, _, n_unassayed = build_trench_composites(points)

    assert len(composites) == 1
    assert math.isclose(composites[0].grade, 0.0)
    assert n_unassayed == 0


def test_empty_trench_yields_nothing_without_raising():
    composites, warnings, n_unassayed = build_trench_composites([])

    assert composites == []
    assert warnings == []
    assert n_unassayed == 0
