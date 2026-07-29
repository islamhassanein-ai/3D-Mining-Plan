import math
import pytest
from backend.src.services.combined_routing import route_combined_rows
from backend.src.services.desurvey import compute_minimum_curvature_trace


def _row(hole_id, ht, survey=None, zone="Z"):
    return {
        "hole_id": hole_id,
        "easting": 100.0,
        "northing": 200.0,
        "elevation": 300.0,
        "hole_type": ht,
        "zone": zone,
        "inline_survey": survey,
    }


def test_tr_row_produces_two_points_with_identical_elevations():
    survey = {"dip": 16.0, "azimuth": 100.0, "total_length": 145.0}
    out = route_combined_rows([_row("ARTR001", "TR", survey)])
    pts = out["trench_points"]
    assert len(pts) == 2
    assert [p["point_order"] for p in pts] == [0, 1]
    # The explicit guard for the floating-trench bug: equal elevations.
    assert pts[0]["elevation"] == pts[1]["elevation"] == 300.0
    assert out["collars"] == []
    assert out["surveys"] == []


def test_tr_positive_dip_zero_elevation_change_regression():
    # ARTR001: dip +16, length 145. The bug put it ~40 m in the air.
    # The fix: dz = 0, flat at collar elevation.
    survey = {"dip": 16.0, "azimuth": 100.0, "total_length": 145.0}
    out = route_combined_rows([_row("ARTR001", "TR", survey)])
    pts = out["trench_points"]
    assert pts[0]["elevation"] == pts[1]["elevation"]
    assert pts[1]["elevation"] == 300.0  # collar elevation, not 300+40


def test_tr_endpoint_bearing_azimuth_90_and_0():
    # azimuth 90, length 100 -> easting +100, northing unchanged
    s90 = {"dip": 0.0, "azimuth": 90.0, "total_length": 100.0}
    out = route_combined_rows([_row("T90", "TR", s90, zone="Z")])
    p0, p1 = out["trench_points"]
    assert abs(p1["easting"] - (p0["easting"] + 100.0)) < 1e-6
    assert abs(p1["northing"] - p0["northing"]) < 1e-6

    # azimuth 0, length 100 -> northing +100, easting unchanged
    s0 = {"dip": 0.0, "azimuth": 0.0, "total_length": 100.0}
    out = route_combined_rows([_row("T0", "TR", s0)])
    p0, p1 = out["trench_points"]
    assert abs(p1["northing"] - (p0["northing"] + 100.0)) < 1e-6
    assert abs(p1["easting"] - p0["easting"]) < 1e-6


def test_tr_dip_azimuth_stored_only_on_point_order_0():
    survey = {"dip": 16.0, "azimuth": 100.0, "total_length": 145.0}
    out = route_combined_rows([_row("ARTR001", "TR", survey)])
    p0, p1 = out["trench_points"]
    assert p0["dip"] == 16.0
    assert p0["azimuth"] == 100.0
    assert p1["dip"] is None
    assert p1["azimuth"] is None
    # hole_type on both points
    assert p0["hole_type"] == "TR" and p1["hole_type"] == "TR"
    # grade_value always None
    assert p0["grade_value"] is None and p1["grade_value"] is None
    # trench_id == hole_id, used verbatim
    assert p0["trench_id"] == "ARTR001"


def test_dd_row_emits_one_survey_at_depth_equal_total_length_with_2pt_trace():
    survey = {"dip": -50.0, "azimuth": 122.0, "total_length": 44.3}
    out = route_combined_rows([_row("ARDD0001", "DD", survey)])
    assert len(out["collars"]) == 1
    assert out["collars"][0]["hole_type"] == "DD"
    assert out["trench_points"] == []
    assert len(out["surveys"]) == 1
    sv = out["surveys"][0]
    assert sv["hole_id"] == "ARDD0001"
    # NOT depth 0 -- depth == total_length, so desurvey auto-prepends depth 0.
    assert sv["depth"] == pytest.approx(44.3)
    assert sv["dip"] == -50.0 and sv["azimuth"] == 122.0

    # Feeding it through compute_minimum_curvature_trace yields a 2-point trace
    # (the auto-prepend at depth 0 produces the collar point).
    trace = compute_minimum_curvature_trace(100.0, 200.0, 300.0, [sv])
    assert len(trace) == 2
    assert trace[0]["depth"] == pytest.approx(0.0)
    assert trace[1]["depth"] == pytest.approx(44.3)


def test_dd_row_no_survey_no_crash():
    out = route_combined_rows([_row("DD1", "DD", survey=None)])
    assert out["surveys"] == []
    assert len(out["collars"]) == 1
    assert out["trench_points"] == []


def test_dd_survey_at_depth_zero_would_be_one_point_trace():
    # Regression guard for the rationale: a single station AT depth 0 yields a
    # one-point trace. We assert the buggy input (depth 0) reproduces that, so
    # the correct depth==total_length fix can be seen to matter.
    buggy = {"hole_id": "X", "depth": 0.0, "dip": -50.0, "azimuth": 122.0}
    trace = compute_minimum_curvature_trace(100.0, 200.0, 300.0, [buggy])
    assert len(trace) == 1  # the dropped-collar bug shape


def test_ch_and_fc_route_to_trench_points_not_collars():
    for ht in ("CH", "FC"):
        survey = {"dip": 0.0, "azimuth": 90.0, "total_length": 10.0}
        out = route_combined_rows([_row(f"{ht}1", ht, survey)])
        assert out["collars"] == [], f"{ht} must not route to collars"
        assert out["surveys"] == [], f"{ht} must not emit a survey"
        assert len(out["trench_points"]) == 2
        assert out["trench_points"][0]["hole_type"] == ht
        assert out["trench_points"][0]["trench_id"] == f"{ht}1"


def test_rc_routes_to_collars_with_survey():
    survey = {"dip": -45.0, "azimuth": 90.0, "total_length": 60.0}
    out = route_combined_rows([_row("RC1", "RC", survey)])
    assert len(out["collars"]) == 1
    assert out["collars"][0]["hole_type"] == "RC"
    assert len(out["surveys"]) == 1
    assert out["surveys"][0]["depth"] == pytest.approx(60.0)
    assert out["trench_points"] == []