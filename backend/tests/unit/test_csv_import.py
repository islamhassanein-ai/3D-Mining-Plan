import pytest
from backend.src.services.csv_import import (
    parse_bdl_value,
    parse_collar_csv,
    parse_survey_csv,
    parse_assay_csv,
    parse_lithology_csv,
    parse_combined_csv,
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


# --- Combined CSV parser (parse_combined_csv) ---

def _full_header():
    return b"Hole Id,Zone,X,Y,Z,Dip,Azimuth,Total_Length,Type\n"

def test_combined_csv_aliases_xyz_and_hole_id():
    csv_data = _full_header() + b"ARCH001,Abo elmajd,208322,2467932,297,-8,48,11,CH\n"
    parsed, errors = parse_combined_csv(csv_data)
    assert not errors
    assert len(parsed) == 1
    r = parsed[0]
    assert r["hole_id"] == "ARCH001"
    assert r["easting"] == 208322.0
    assert r["northing"] == 2467932.0
    assert r["elevation"] == 297.0
    assert r["hole_type"] == "CH"
    assert r["zone"] == "Abo elmajd"
    assert r["inline_survey"] == {"dip": -8.0, "azimuth": 48.0, "total_length": 11.0}

def test_combined_csv_hole_id_alias_hole():
    csv_data = b"hole,zone,x,y,z,dip,azimuth,length,type\nT1,Z,1,2,3,0,45,10,TR\n"
    parsed, errors = parse_combined_csv(csv_data)
    assert not errors
    assert parsed[0]["hole_id"] == "T1"
    assert parsed[0]["easting"] == 1.0
    assert parsed[0]["inline_survey"]["total_length"] == 10.0

def test_combined_csv_missing_type_column_warns_and_defaults_dd():
    # No Type column -> exactly one warning (type=='warning'), all rows DD
    csv_data = b"Hole Id,X,Y,Z,Dip,Azimuth,Total_Length\nDH1,1,2,3,-50,90,100\nDH2,4,5,6,-60,180,200\n"
    parsed, errors = parse_combined_csv(csv_data)
    warnings = [e for e in errors if e.get("type") == "warning"]
    real_errors = [e for e in errors if e.get("type", "error") != "warning"]
    assert len(warnings) == 1
    assert "Type" in warnings[0]["error"]
    assert len(real_errors) == 0
    assert all(r["hole_type"] == "DD" for r in parsed)
    assert len(parsed) == 2

def test_combined_csv_invalid_type_row_error_others_ok():
    csv_data = _full_header() + (
        b"DD1,Z,1,2,3,-50,90,100,DD\n"
        b"BAD1,Z,4,5,6,-60,180,200,XX\n"
        b"TR1,Z,7,8,9,0,180,25,TR\n"
    )
    parsed, errors = parse_combined_csv(csv_data)
    # Only the BAD row should error (row 3 = line 3 of spreadsheet; header=line1, DD1=line2, BAD1=line3)
    bad_errors = [e for e in errors if e.get("type", "error") == "error"]
    assert len(bad_errors) == 1
    assert bad_errors[0]["row"] == 3
    assert "XX" in bad_errors[0]["error"]
    assert len(parsed) == 2
    assert {r["hole_id"] for r in parsed} == {"DD1", "TR1"}

def test_combined_csv_total_length_absent_error():
    # dip/azimuth present without total_length -> error
    csv_data = b"hole_id,x,y,z,dip,azimuth,type\nT1,1,2,3,-50,90,TR\n"
    parsed, errors = parse_combined_csv(csv_data)
    real_errors = [e for e in errors if e.get("type", "error") == "error"]
    assert len(real_errors) == 1
    assert "total_length" in real_errors[0]["error"]
    assert not parsed

def test_combined_csv_total_length_zero_error():
    csv_data = _full_header() + b"TR1,Z,1,2,3,0,90,0,TR\n"
    parsed, errors = parse_combined_csv(csv_data)
    real_errors = [e for e in errors if e.get("type", "error") == "error"]
    assert len(real_errors) == 1
    assert "greater than 0" in real_errors[0]["error"]
    assert not parsed

def test_combined_csv_total_length_negative_error():
    csv_data = _full_header() + b"TR1,Z,1,2,3,0,90,-5,TR\n"
    parsed, errors = parse_combined_csv(csv_data)
    real_errors = [e for e in errors if e.get("type", "error") == "error"]
    assert len(real_errors) == 1
    assert not parsed

def test_combined_csv_length_without_dip_error():
    # total_length present without both dip and azimuth -> error
    csv_data = b"hole_id,x,y,z,total_length,type\nDD1,1,2,3,100,DD\n"
    parsed, errors = parse_combined_csv(csv_data)
    real_errors = [e for e in errors if e.get("type", "error") == "error"]
    assert len(real_errors) == 1
    assert "both" in real_errors[0]["error"]

def test_combined_csv_literal_zero_dip_and_azimuth_parse_as_zero():
    # ARTR031 has Dip=0 and ARTR008 has Azimuth=2 -- a truthiness check
    # would treat 0 as missing. Use == "" after stripping.
    csv_data = _full_header() + (
        b"ARTR031,Samir,207593.546,2467771.849,309.923,0,92,25,TR\n"
        b"ARTR008,Z,1,2,3,5,2,30,TR\n"
    )
    parsed, errors = parse_combined_csv(csv_data)
    assert not errors
    assert parsed[0]["inline_survey"]["dip"] == 0.0
    assert parsed[0]["inline_survey"]["azimuth"] == 92.0
    assert parsed[1]["inline_survey"]["azimuth"] == 2.0

def test_combined_csv_no_dip_azimuth_no_inline_survey():
    # A row with no dip/azimuth/total_length -> inline_survey is None (still valid)
    csv_data = _full_header() + b"DD1,Z,1,2,3,,100,DD\n"
    # The above has Total_Length=100 but no dip/azimuth -- that should error.
    # Build one with ALL three absent:
    csv_data = b"hole_id,x,y,z,type\nDD1,1,2,3,DD\n"
    parsed, errors = parse_combined_csv(csv_data)
    assert not errors
    assert parsed[0]["inline_survey"] is None

def test_combined_csv_zone_normalization():
    a = _full_header() + b"X1,Abo elmajd,1,2,3,0,90,10,TR\n"
    b = _full_header() + b"X2,  Abo  elmajd ,1,2,3,0,90,10,TR\n"
    pa, ea = parse_combined_csv(a)
    pb, eb = parse_combined_csv(b)
    assert not ea and not eb
    assert pa[0]["zone"] == "Abo elmajd"
    assert pb[0]["zone"] == "Abo elmajd"
    assert pa[0]["zone"] == pb[0]["zone"]

def test_combined_csv_row_numbers_match_spreadsheet_lines():
    # First data row after header should report row 2.
    csv_data = (
        _full_header()
        + b"GOOD1,Z,1,2,3,0,90,10,TR\n"
        + b"BAD1,Z,bad,2,3,0,90,10,TR\n"
    )
    parsed, errors = parse_combined_csv(csv_data)
    real_errors = [e for e in errors if e.get("type", "error") == "error"]
    assert real_errors[0]["row"] == 3  # header=1, GOOD1=2, BAD1=3

def test_combined_csv_missing_required_header_error_row_zero():
    # No coordinates at all
    csv_data = b"Hole Id,Type\nX1,TR\n"
    parsed, errors = parse_combined_csv(csv_data)
    real_errors = [e for e in errors if e.get("type", "error") == "error"]
    assert len(real_errors) == 1
    assert real_errors[0]["row"] == 0
    assert "Missing required headers" in real_errors[0]["error"]
    assert not parsed

def test_combined_csv_dip_range_error():
    csv_data = _full_header() + b"TR1,Z,1,2,3,91,90,10,TR\n"
    parsed, errors = parse_combined_csv(csv_data)
    real_errors = [e for e in errors if e.get("type", "error") == "error"]
    assert len(real_errors) == 1
    assert "Dip must be between" in real_errors[0]["error"]

def test_combined_csv_azimuth_range_error():
    csv_data = _full_header() + b"TR1,Z,1,2,3,0,361,10,TR\n"
    parsed, errors = parse_combined_csv(csv_data)
    real_errors = [e for e in errors if e.get("type", "error") == "error"]
    assert len(real_errors) == 1
    assert "Azimuth must be between" in real_errors[0]["error"]


def test_combined_csv_duplicate_alias_headers_rejected():
    # A file with both `X` and `Easting` -- two headers map to the same
    # canonical easting field. Reject the file with a clear header error
    # instead of nondeterministically picking one (item 6).
    csv_data = (
        b"Hole Id,Zone,X,Easting,Y,Z,Dip,Azimuth,Total_Length,Type\n"
        b"TR1,Z,1,2,3,4,0,90,10,TR\n"
    )
    parsed, errors = parse_combined_csv(csv_data)
    real_errors = [e for e in errors if e.get("type", "error") == "error"]
    assert len(real_errors) == 1
    assert "Duplicate header for 'easting'" in real_errors[0]["error"]
    assert parsed == []


# The HTTP 400 guard for combined_file + four-file is asserted end-to-end in
# tests/integration/test_import_flow.py::test_combined_with_four_file_rejected_400.


# --- UTF-8 BOM handling -----------------------------------------------------
# Excel on Windows writes a UTF-8 BOM. Decoding as plain utf-8 leaves it on the
# first header, so "Hole Id" cleans to "﻿hole_id" and every required-header
# check fails with a misleading "missing column" error naming a column that is
# plainly present -- rejecting 100% of rows. get_csv_reader decodes utf-8-sig.

BOM = b"\xef\xbb\xbf"


def test_combined_csv_with_utf8_bom_parses_all_rows():
    csv_data = BOM + (
        b"Hole Id,Zone,X,Y,Z,Dip,Azimuth,Total_Length,Type\n"
        b"ARTR001,Abo elmajd,208272,2467864,299.13,16,100,145,TR\n"
        b"ARDD0001,Abo elmajd,208316.223,2467944.22,301.67,-50,122,44.3,DD\n"
    )
    parsed, errors = parse_combined_csv(csv_data)
    assert errors == []
    assert len(parsed) == 2
    # The BOM must not survive onto the first field's value or its header.
    assert parsed[0]["hole_id"] == "ARTR001"
    assert parsed[0]["hole_type"] == "TR"
    assert parsed[1]["hole_id"] == "ARDD0001"


def test_parse_collar_csv_with_utf8_bom_parses_all_rows():
    # The same defect affected all five parsers via get_csv_reader, so the
    # legacy four-file flow is covered too.
    csv_data = BOM + (
        b"hole_id,easting,northing,elevation,utm_zone\n"
        b"DH01,350000,2800000,150,37N\n"
    )
    parsed, errors = parse_collar_csv(csv_data)
    assert errors == []
    assert len(parsed) == 1
    assert parsed[0]["hole_id"] == "DH01"


def test_combined_master_fixture_is_a_byte_copy_with_bom():
    # Guards against the fixture regressing to a RETYPED copy. The original
    # fixture was hand-typed without the BOM, so the whole suite passed green
    # while the real production file was rejected outright. A fixture that is
    # not byte-identical to the real export cannot catch encoding bugs.
    import os
    fixture = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "integration", "fixtures", "combined_master.csv",
    )
    with open(fixture, "rb") as f:
        raw = f.read()
    assert raw.startswith(BOM), (
        "combined_master.csv must be a byte-copy of the real Excel export, "
        "BOM included -- do not retype it."
    )
    parsed, errors = parse_combined_csv(raw)
    assert errors == []
    assert len(parsed) == 25