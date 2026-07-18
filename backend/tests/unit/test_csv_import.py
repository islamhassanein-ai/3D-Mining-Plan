import pytest
from backend.src.services.csv_import import (
    parse_bdl_value,
    parse_collar_csv,
    parse_survey_csv,
    parse_assay_csv,
    parse_lithology_csv
)

def test_parse_bdl_value():
    # Standard numbers
    val, bdl, err = parse_bdl_value("1.25")
    assert val == 1.25
    assert not bdl
    assert not err

    # Below detection limit
    val, bdl, err = parse_bdl_value("<0.02")
    assert val == 0.02
    assert bdl
    assert not err

    # Whitespace handling
    val, bdl, err = parse_bdl_value(" < 0.005 ")
    assert val == 0.005
    assert bdl
    assert not err

    # Malformed text
    val, bdl, err = parse_bdl_value("xyz")
    assert val == 0.0
    assert not bdl
    assert "Could not parse" in err

def test_parse_collar_csv_basic():
    csv_data = b"hole_id,easting,northing,elevation,utm_zone\nDH01,350000,2800000,150,36N\nDH02,351000,2801000,160,36N"
    parsed, errors = parse_collar_csv(csv_data)
    assert not errors
    assert len(parsed) == 2
    assert parsed[0]["hole_id"] == "DH01"
    assert parsed[0]["easting"] == 350000.0
    assert parsed[1]["elevation"] == 160.0
    assert parsed[1]["utm_zone"] == "36N"

def test_parse_collar_csv_missing_headers():
    csv_data = b"hole_id,easting,elevation\nDH01,350000,150"
    parsed, errors = parse_collar_csv(csv_data)
    assert len(errors) == 1
    assert "Missing required headers" in errors[0]["error"]
    assert not parsed

def test_parse_assay_csv_with_bdl():
    csv_data = b"hole_id,from_depth,to_depth,grade,grade_unit\nDH01,0,2.5,<0.01,ppm\nDH01,2.5,5.0,1.25,ppm"
    parsed, errors = parse_assay_csv(csv_data)
    assert not errors
    assert len(parsed) == 2
    assert parsed[0]["below_detection_limit"] is True
    assert parsed[0]["grade_value"] == 0.01
    assert parsed[1]["below_detection_limit"] is False
    assert parsed[1]["grade_value"] == 1.25
