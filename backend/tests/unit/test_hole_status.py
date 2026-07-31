"""Planned vs drilled hole status through the combined-CSV import path."""
import pytest

from backend.src.services.csv_import import parse_combined_csv
from backend.src.services.combined_routing import route_combined_rows

_HEADER = "Hole Id,Zone,X,Y,Z,Dip,Azimuth,Total_Length,Type,Status,Sample_ID,From,To,Grade\n"


def _parse(body: str):
    parsed, errors = parse_combined_csv((_HEADER + body).encode("utf-8"))
    return parsed, [e for e in errors if e.get("type") != "warning"]


def test_status_column_routes_planned_and_drilled():
    parsed, errors = _parse(
        "MKDD001,Z,100,200,300,-50,120,44.3,DD,drilled,,,,\n"
        "MKDD900,Z,110,210,300,-60,130,80.0,DD,planned,,,,\n"
    )
    assert errors == []
    collars = route_combined_rows(parsed)["collars"]
    by_id = {c["hole_id"]: c for c in collars}
    assert by_id["MKDD001"]["hole_status"] == "drilled"
    assert by_id["MKDD900"]["hole_status"] == "planned"


@pytest.mark.parametrize("token,expected", [
    ("planned", "planned"), ("Proposed", "planned"), ("TARGET", "planned"),
    ("design", "planned"), ("yes", "planned"), ("1", "planned"), ("true", "planned"),
    ("drilled", "drilled"), ("Completed", "drilled"), ("existing", "drilled"),
    ("no", "drilled"), ("0", "drilled"), ("false", "drilled"),
])
def test_status_aliases(token, expected):
    parsed, errors = _parse(f"MKDD001,Z,100,200,300,-50,120,44.3,DD,{token},,,,\n")
    assert errors == []
    assert route_combined_rows(parsed)["collars"][0]["hole_status"] == expected


def test_invalid_status_is_an_error():
    _parsed, errors = _parse("MKDD001,Z,100,200,300,-50,120,44.3,DD,maybe,,,,\n")
    assert len(errors) == 1
    assert "Invalid status" in errors[0]["error"]


def test_status_inherits_onto_sample_continuation_rows():
    parsed, errors = _parse(
        "MKDD900,Z,110,210,300,-60,130,80.0,DD,planned,MKDD900-S01,0,2,1.4\n"
        "MKDD900,,,,,,,,,,MKDD900-S02,2,10,0.6\n"
    )
    assert errors == []
    assert all(r["hole_status"] == "planned" for r in parsed)


def test_missing_status_column_defaults_to_drilled():
    """Historical CSVs have no Status column and describe real drilled holes."""
    header = "Hole Id,Zone,X,Y,Z,Dip,Azimuth,Total_Length,Type\n"
    parsed, errors = parse_combined_csv(
        (header + "MKDD001,Z,100,200,300,-50,120,44.3,DD\n").encode("utf-8")
    )
    assert [e for e in errors if e.get("type") != "warning"] == []
    assert route_combined_rows(parsed)["collars"][0]["hole_status"] == "drilled"
