"""Dip sign convention detection.

A survey file using "degrees below horizontal" (positive numbers) fed into a
desurvey that expects signed inclination sends every hole upward into the air.
The intervals stay at their correct distance along the trajectory, so the
depths look right in the data while every sample plots above its collar.
"""
import pytest

from backend.src.services.desurvey import compute_minimum_curvature_trace
from backend.src.services.dip_convention import (
    POSITIVE_DOWN,
    SIGNED,
    detect_dip_convention,
    normalize_dip,
    normalize_survey_dips,
)


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------

def test_all_positive_dips_are_degrees_below_horizontal():
    """You cannot drill upward from surface, so all-positive is unambiguous."""
    assert detect_dip_convention([70, 70, 60, 55]) == POSITIVE_DOWN


def test_all_negative_dips_are_already_signed():
    assert detect_dip_convention([-50, -55, -60]) == SIGNED


def test_mixed_signs_are_left_alone():
    """Mixed signs mean the file already carries direction information."""
    assert detect_dip_convention([8, 0, -6, -20]) == SIGNED


def test_zero_dips_carry_no_evidence():
    assert detect_dip_convention([0, 0]) == SIGNED
    assert detect_dip_convention([]) == SIGNED


def test_zeros_do_not_block_detection_of_positive_data():
    assert detect_dip_convention([0, 70, 60]) == POSITIVE_DOWN


def test_trench_dips_are_excluded_from_detection():
    """On TR/CH/FC, dip is the ground slope at the start point -- a positive
    value genuinely means uphill and must survive."""
    dips = [16, 8, 12]
    types = ["TR", "CH", "FC"]
    assert detect_dip_convention(dips, types) == SIGNED


def test_drilled_holes_decide_even_when_trenches_are_present():
    dips = [70, 60, 16]
    types = ["DD", "RC", "TR"]
    assert detect_dip_convention(dips, types) == POSITIVE_DOWN


# ---------------------------------------------------------------------------
# Normalisation
# ---------------------------------------------------------------------------

def test_normalize_makes_positive_dips_downward():
    assert normalize_dip(70, POSITIVE_DOWN) == -70
    assert normalize_dip(-70, POSITIVE_DOWN) == -70, "already-negative stays put"


def test_normalize_is_a_noop_for_signed_data():
    assert normalize_dip(70, SIGNED) == 70
    assert normalize_dip(-70, SIGNED) == -70


def test_normalize_survey_dips_flips_a_whole_batch():
    surveys = [
        {"hole_id": "A", "depth": 45.5, "dip": 70, "azimuth": 30},
        {"hole_id": "B", "depth": 53.3, "dip": 60, "azimuth": 30},
    ]
    out, convention = normalize_survey_dips(surveys)
    assert convention == POSITIVE_DOWN
    assert [s["dip"] for s in out] == [-70, -60]


def test_normalize_survey_dips_preserves_trench_slope():
    surveys = [
        {"hole_id": "DD1", "depth": 40, "dip": 70, "azimuth": 30},
        {"hole_id": "TR1", "depth": 145, "dip": 16, "azimuth": 100},
    ]
    out, convention = normalize_survey_dips(surveys, {"DD1": "DD", "TR1": "TR"})
    assert convention == POSITIVE_DOWN
    assert out[0]["dip"] == -70, "drillhole is flipped"
    assert out[1]["dip"] == 16, "trench ground slope is preserved"


# ---------------------------------------------------------------------------
# The symptom this prevents
# ---------------------------------------------------------------------------

def _elevation_at(dip, depth):
    trace = compute_minimum_curvature_trace(
        0.0, 0.0, 0.0,
        [{"depth": 0.0, "dip": dip, "azimuth": 30.0},
         {"depth": 100.0, "dip": dip, "azimuth": 30.0}],
    )
    for i in range(1, len(trace)):
        if trace[i - 1]["depth"] <= depth <= trace[i]["depth"]:
            d1, d2 = trace[i - 1]["depth"], trace[i]["depth"]
            t = (depth - d1) / (d2 - d1)
            return trace[i - 1]["z"] + t * (trace[i]["z"] - trace[i - 1]["z"])
    return trace[-1]["z"]


def test_unnormalized_positive_dip_sends_the_hole_upward():
    """The bug: a 37 m sample ends up ABOVE the collar."""
    assert _elevation_at(70.0, 37.0) > 0


def test_normalized_dip_puts_the_sample_below_the_collar():
    corrected = normalize_dip(70.0, POSITIVE_DOWN)
    elevation = _elevation_at(corrected, 37.0)
    assert elevation < 0
    # 37 m along a 70-degree hole drops ~34.8 m.
    assert elevation == pytest.approx(-34.77, abs=0.1)


# ---------------------------------------------------------------------------
# Import wiring
# ---------------------------------------------------------------------------

def test_survey_csv_normalizes_and_warns():
    from backend.src.services.csv_import import parse_survey_csv

    body = (
        "hole_id,depth,dip,azimuth\n"
        "AADD004,45.5,70,30\n"
        "AADD005,53.3,60,30\n"
    ).encode("utf-8")
    parsed, errors = parse_survey_csv(body)

    assert [s["dip"] for s in parsed] == [-70, -60]
    warnings = [e for e in errors if e.get("type") == "warning"]
    assert len(warnings) == 1
    assert "below horizontal" in warnings[0]["error"].lower()


def test_survey_csv_leaves_signed_data_untouched():
    from backend.src.services.csv_import import parse_survey_csv

    body = (
        "hole_id,depth,dip,azimuth\n"
        "MKDD001,44.3,-50,122\n"
        "MKDD002,32.4,-55,50\n"
    ).encode("utf-8")
    parsed, errors = parse_survey_csv(body)

    assert [s["dip"] for s in parsed] == [-50, -55]
    assert [e for e in errors if e.get("type") == "warning"] == []


def test_combined_csv_normalizes_drillholes_but_not_trenches():
    from backend.src.services.csv_import import parse_combined_csv

    body = (
        "Hole Id,Zone,X,Y,Z,Dip,Azimuth,Total_Length,Type\n"
        "AADD004,Adel,100,200,300,70,30,45.5,DD\n"
        "ARTR001,Adel,110,210,300,16,100,145.0,TR\n"
    ).encode("utf-8")
    parsed, errors = parse_combined_csv(body)

    by_id = {r["hole_id"]: r for r in parsed}
    assert by_id["AADD004"]["inline_survey"]["dip"] == -70
    assert by_id["ARTR001"]["inline_survey"]["dip"] == 16

    warnings = [e for e in errors if e.get("type") == "warning"]
    assert any("below horizontal" in w["error"].lower() for w in warnings)
