"""Parity test: drives _compute_true_thickness_math against the shared fixture.

The same fixture is consumed by frontend/tests/true_thickness_parity.test.mjs.
Both tests must fail if either implementation is edited in isolation.
"""
import json
from pathlib import Path

import pytest

from backend.src.api.collars import _compute_true_thickness_math


FIXTURE_PATH = (
    Path(__file__).parents[3]
    / "specs/006-standalone-html-export/fixtures/true_thickness_vectors.json"
)


def load_fixture():
    with open(FIXTURE_PATH) as f:
        return json.load(f)


@pytest.mark.parametrize("case", load_fixture()["cases"], ids=[c["name"] for c in load_fixture()["cases"]])
def test_true_thickness_parity(case):
    tolerance = load_fixture()["tolerance"]
    result = _compute_true_thickness_math(
        from_depth=case["from_depth"],
        to_depth=case["to_depth"],
        surveys_data=case["surveys"],
        dip_direction=case["dip_direction"],
        dip=case["vein_dip"],
    )
    exp = case["expected"]
    assert abs(result["apparent_thickness"] - exp["apparent_thickness"]) <= tolerance, (
        f"apparent_thickness: got {result['apparent_thickness']}, expected {exp['apparent_thickness']}"
    )
    assert abs(result["true_thickness"] - exp["true_thickness"]) <= tolerance, (
        f"true_thickness: got {result['true_thickness']}, expected {exp['true_thickness']}"
    )
    assert abs(result["hole_dip"] - exp["hole_dip"]) <= tolerance, (
        f"hole_dip: got {result['hole_dip']}, expected {exp['hole_dip']}"
    )
    assert abs(result["hole_azimuth"] - exp["hole_azimuth"]) <= tolerance, (
        f"hole_azimuth: got {result['hole_azimuth']}, expected {exp['hole_azimuth']}"
    )
