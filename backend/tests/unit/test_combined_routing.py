import math
import pytest
from backend.src.services.combined_routing import route_combined_rows
from backend.src.services.desurvey import compute_minimum_curvature_trace


def _row(
    hole_id,
    ht,
    survey=None,
    zone="Z",
    easting=100.0,
    northing=200.0,
    elevation=300.0,
    end_coords=None,
    grade_value=None,
    sample_id=None,
    from_depth=None,
    to_depth=None,
    row_kind=None,
):
    """Build a combined-CSV parsed row dict. row_kind is inferred when omitted."""
    return {
        "hole_id": hole_id,
        "easting": easting,
        "northing": northing,
        "elevation": elevation,
        "hole_type": ht,
        "zone": zone,
        "inline_survey": survey,
        "end_coords": end_coords,
        "grade_value": grade_value,
        "sample_id": sample_id,
        "from_depth": from_depth,
        "to_depth": to_depth,
        "row_kind": row_kind,
    }


def _assay_row(hole_id, sample_id, from_d, to_d, grade, unit="g/t", zone="Z"):
    """Build a DD/RC assay continuation row dict."""
    return {
        "hole_id": hole_id,
        "easting": None,
        "northing": None,
        "elevation": None,
        "hole_type": "DD",
        "zone": zone,
        "inline_survey": None,
        "end_coords": None,
        "grade_value": grade,
        "sample_id": sample_id,
        "from_depth": from_d,
        "to_depth": to_d,
        "grade_unit": unit,
        "row_kind": "assay",
    }


# ---------------------------------------------------------------------------
# Legacy single-row trench tests (unchanged behaviour)
# ---------------------------------------------------------------------------

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
    survey = {"dip": 16.0, "azimuth": 100.0, "total_length": 145.0}
    out = route_combined_rows([_row("ARTR001", "TR", survey)])
    pts = out["trench_points"]
    assert pts[0]["elevation"] == pts[1]["elevation"]
    assert pts[1]["elevation"] == 300.0


def test_tr_endpoint_bearing_azimuth_90_and_0():
    s90 = {"dip": 0.0, "azimuth": 90.0, "total_length": 100.0}
    out = route_combined_rows([_row("T90", "TR", s90, zone="Z")])
    p0, p1 = out["trench_points"]
    assert abs(p1["easting"] - (p0["easting"] + 100.0)) < 1e-6
    assert abs(p1["northing"] - p0["northing"]) < 1e-6

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
    assert p0["hole_type"] == "TR" and p1["hole_type"] == "TR"
    assert p0["grade_value"] is None and p1["grade_value"] is None
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
    assert sv["depth"] == pytest.approx(44.3)
    assert sv["dip"] == -50.0 and sv["azimuth"] == 122.0

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
    buggy = {"hole_id": "X", "depth": 0.0, "dip": -50.0, "azimuth": 122.0}
    trace = compute_minimum_curvature_trace(100.0, 200.0, 300.0, [buggy])
    assert len(trace) == 1


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


# ---------------------------------------------------------------------------
# Multi-point trench tests (new behaviour)
# ---------------------------------------------------------------------------

def test_multi_row_trench_n_points_in_csv_order():
    # Three sample rows for the same trench → three vertices, point_order 0,1,2
    rows = [
        _row("MKTR001", "TR", easting=100.0, northing=200.0, elevation=300.0, grade_value=1.5, sample_id="S01", from_depth=0, to_depth=2),
        _row("MKTR001", "TR", easting=110.0, northing=205.0, elevation=298.0, grade_value=2.0, sample_id="S02", from_depth=2, to_depth=4),
        _row("MKTR001", "TR", easting=120.0, northing=210.0, elevation=296.0, grade_value=0.5, sample_id="S03", from_depth=4, to_depth=6),
    ]
    out = route_combined_rows(rows)
    pts = out["trench_points"]
    assert len(pts) == 3
    assert [p["point_order"] for p in pts] == [0, 1, 2]
    assert pts[0]["easting"] == 100.0
    assert pts[1]["easting"] == 110.0
    assert pts[2]["easting"] == 120.0
    assert out["collars"] == []


def test_multi_row_trench_elevations_come_from_rows():
    rows = [
        _row("TR2", "TR", easting=0.0, northing=0.0, elevation=500.0),
        _row("TR2", "TR", easting=10.0, northing=0.0, elevation=495.0),
    ]
    out = route_combined_rows(rows)
    pts = out["trench_points"]
    assert pts[0]["elevation"] == 500.0
    assert pts[1]["elevation"] == 495.0


def test_multi_row_trench_dip_azimuth_only_on_first_point():
    survey = {"dip": 5.0, "azimuth": 90.0, "total_length": 50.0}
    rows = [
        _row("TR3", "TR", survey=survey),
        _row("TR3", "TR"),
        _row("TR3", "TR"),
    ]
    out = route_combined_rows(rows)
    pts = out["trench_points"]
    assert pts[0]["dip"] == 5.0
    assert pts[0]["azimuth"] == 90.0
    assert pts[1]["dip"] is None
    assert pts[2]["dip"] is None


def test_multi_row_trench_grade_and_sample_fields_per_vertex():
    rows = [
        _row("TR4", "TR", grade_value=3.0, sample_id="A01", from_depth=0.0, to_depth=2.0),
        _row("TR4", "TR", grade_value=1.2, sample_id="A02", from_depth=2.0, to_depth=4.0),
    ]
    out = route_combined_rows(rows)
    pts = out["trench_points"]
    assert pts[0]["grade_value"] == 3.0
    assert pts[0]["sample_id"] == "A01"
    assert pts[0]["from_depth"] == 0.0
    assert pts[0]["to_depth"] == 2.0
    assert pts[1]["grade_value"] == 1.2
    assert pts[1]["sample_id"] == "A02"


def test_single_row_trench_with_end_coords():
    end = {"easting": 200.0, "northing": 300.0, "elevation": 290.0}
    rows = [_row("TR5", "TR", end_coords=end)]
    out = route_combined_rows(rows)
    pts = out["trench_points"]
    assert len(pts) == 2
    assert pts[1]["easting"] == 200.0
    assert pts[1]["northing"] == 300.0
    assert pts[1]["elevation"] == 290.0


def test_multiple_trenches_independent_point_orders():
    rows = [
        _row("TRA", "TR", easting=0.0, northing=0.0, elevation=100.0),
        _row("TRA", "TR", easting=10.0, northing=0.0, elevation=100.0),
        _row("TRB", "TR", easting=50.0, northing=50.0, elevation=200.0),
        _row("TRB", "TR", easting=60.0, northing=50.0, elevation=200.0),
        _row("TRB", "TR", easting=70.0, northing=50.0, elevation=200.0),
    ]
    out = route_combined_rows(rows)
    pts_a = [p for p in out["trench_points"] if p["trench_id"] == "TRA"]
    pts_b = [p for p in out["trench_points"] if p["trench_id"] == "TRB"]
    assert [p["point_order"] for p in pts_a] == [0, 1]
    assert [p["point_order"] for p in pts_b] == [0, 1, 2]


# ---------------------------------------------------------------------------
# DD/RC assay continuation row tests
# ---------------------------------------------------------------------------

def test_dd_assay_rows_route_to_assays_list():
    collar = _row("MKDD001", "DD", survey={"dip": -50.0, "azimuth": 122.0, "total_length": 44.3})
    a1 = _assay_row("MKDD001", "MKDD001-S01", 0, 1, 1.0)
    a2 = _assay_row("MKDD001", "MKDD001-S02", 1, 2, 0.2)
    out = route_combined_rows([collar, a1, a2])

    assert len(out["collars"]) == 1
    assert len(out["surveys"]) == 1
    assert out["trench_points"] == []
    assert len(out["assays"]) == 2

    assay = out["assays"][0]
    assert assay["hole_id"] == "MKDD001"
    assert assay["sample_id"] == "MKDD001-S01"
    assert assay["from_depth"] == 0
    assert assay["to_depth"] == 1
    assert assay["grade_value"] == 1.0
    assert assay["grade_unit"] == "g/t"


def test_dd_assay_grade_unit_preserved():
    collar = _row("RC1", "RC")
    a = _assay_row("RC1", "S01", 0, 2, 5.5, unit="ppm")
    out = route_combined_rows([collar, a])
    assert out["assays"][0]["grade_unit"] == "ppm"


def test_collar_only_dd_emits_empty_assays():
    out = route_combined_rows([_row("DD_SOLO", "DD")])
    assert out["assays"] == []


def test_result_always_has_assays_key():
    out = route_combined_rows([_row("T1", "TR")])
    assert "assays" in out
