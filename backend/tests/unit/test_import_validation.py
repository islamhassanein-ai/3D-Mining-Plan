import pytest
from backend.src.services.import_validation import validate_import_batch

def test_validate_clean_batch():
    collars = [{"hole_id": "DH01", "easting": 350000.0, "northing": 2800000.0, "elevation": 100.0, "utm_zone": "36N"}]
    surveys = [{"hole_id": "DH01", "depth": 0.0, "dip": -90.0, "azimuth": 0.0}]
    assays = [{"hole_id": "DH01", "from_depth": 0.0, "to_depth": 2.0, "grade_value": 1.5, "grade_unit": "ppm", "below_detection_limit": False}]
    lithologies = [{"hole_id": "DH01", "from_depth": 0.0, "to_depth": 2.0, "lith_code": "SND"}]
    
    res = validate_import_batch(collars, surveys, assays, lithologies, "36N")
    assert res["valid"] is True
    assert not res["issues"]
    assert res["summary"]["error_count"] == 0

def test_validate_orphan_hole():
    collars = [{"hole_id": "DH01", "easting": 350000.0, "northing": 2800000.0, "elevation": 100.0}]
    surveys = [{"hole_id": "DH02", "depth": 0.0, "dip": -90.0, "azimuth": 0.0}] # DH02 is orphan
    assays = []
    lithologies = []
    
    res = validate_import_batch(collars, surveys, assays, lithologies)
    assert res["valid"] is False
    assert len(res["issues"]) == 1
    assert res["issues"][0]["rule"] == "orphan_hole_id"
    assert res["issues"][0]["type"] == "error"

def test_validate_bdl_zero():
    collars = [{"hole_id": "DH01", "easting": 350000.0, "northing": 2800000.0, "elevation": 100.0}]
    surveys = []
    # BDL row but grade_value is zero (violates rule)
    assays = [{"hole_id": "DH01", "from_depth": 0.0, "to_depth": 2.0, "grade_value": 0.0, "grade_unit": "ppm", "below_detection_limit": True}]
    lithologies = []
    
    res = validate_import_batch(collars, surveys, assays, lithologies)
    assert res["valid"] is False
    assert len(res["issues"]) == 1
    assert res["issues"][0]["rule"] == "bdl_zero_or_negative"

def test_validate_mixed_units():
    collars = [{"hole_id": "DH01", "easting": 350000.0, "northing": 2800000.0, "elevation": 100.0}]
    surveys = []
    assays = [
        {"hole_id": "DH01", "from_depth": 0.0, "to_depth": 2.0, "grade_value": 1.5, "grade_unit": "ppm"},
        {"hole_id": "DH01", "from_depth": 2.0, "to_depth": 4.0, "grade_value": 0.05, "grade_unit": "%"} # mixed unit!
    ]
    lithologies = []
    
    res = validate_import_batch(collars, surveys, assays, lithologies)
    assert res["valid"] is False
    assert len(res["issues"]) == 1
    assert res["issues"][0]["rule"] == "mixed_units"

def test_validate_overlaps_and_gaps():
    collars = [{"hole_id": "DH01", "easting": 350000.0, "northing": 2800000.0, "elevation": 100.0}]
    surveys = []
    assays = [
        {"hole_id": "DH01", "from_depth": 0.0, "to_depth": 2.0, "grade_value": 1.5, "grade_unit": "ppm"},
        {"hole_id": "DH01", "from_depth": 1.5, "to_depth": 3.5, "grade_value": 2.0, "grade_unit": "ppm"}, # Overlap (1.5 < 2.0)
        {"hole_id": "DH01", "from_depth": 4.5, "to_depth": 6.0, "grade_value": 0.5, "grade_unit": "ppm"}  # Gap (3.5 to 4.5)
    ]
    lithologies = []
    
    res = validate_import_batch(collars, surveys, assays, lithologies)
    # Warnings do NOT block overall validation validity
    assert res["valid"] is True
    assert len(res["issues"]) == 2
    rules = [issue["rule"] for issue in res["issues"]]
    assert "assay_overlap" in rules
    assert "assay_gap" in rules

def test_validate_swapped_coordinates():
    # Easting and Northing values swapped
    collars = [{"hole_id": "DH01", "easting": 2800000.0, "northing": 350000.0, "elevation": 100.0}]
    surveys = []
    assays = []
    lithologies = []
    
    res = validate_import_batch(collars, surveys, assays, lithologies)
    assert res["valid"] is False
    assert any(issue["rule"] == "swapped_coordinates" for issue in res["issues"])

def test_validate_rqd_and_core_recovery():
    collars = [{"hole_id": "DH01", "easting": 350000.0, "northing": 2800000.0, "elevation": 100.0}]
    surveys = []
    assays = []
    
    # 1. Invalid RQD (> 100)
    lithologies_bad_rqd = [{"hole_id": "DH01", "from_depth": 0.0, "to_depth": 2.0, "lith_code": "SND", "rqd_percent": 110}]
    res = validate_import_batch(collars, surveys, assays, lithologies_bad_rqd)
    assert res["valid"] is False
    assert any(issue["rule"] == "rqd_out_of_range" for issue in res["issues"])
    
    # 2. Invalid Core Recovery (< 0)
    lithologies_bad_rec = [{"hole_id": "DH01", "from_depth": 0.0, "to_depth": 2.0, "lith_code": "SND", "core_recovery_percent": -5}]
    res2 = validate_import_batch(collars, surveys, assays, lithologies_bad_rec)
    assert res2["valid"] is False
    assert any(issue["rule"] == "core_recovery_out_of_range" for issue in res2["issues"])
    
    # 3. Valid (range 0 to 100)
    lithologies_ok = [{"hole_id": "DH01", "from_depth": 0.0, "to_depth": 2.0, "lith_code": "SND", "rqd_percent": 85, "core_recovery_percent": 98}]
    res3 = validate_import_batch(collars, surveys, assays, lithologies_ok)
    assert res3["valid"] is True
    assert not res3["issues"]



# --- Spatial outlier detection (rule: spatial_outlier) ---

def _site_collar(hole_id, easting, northing, row):
    return {
        "hole_id": hole_id, "easting": easting, "northing": northing,
        "elevation": 300.0, "hole_type": "DD", "zone": "Adel", "csv_row": row,
    }

def test_spatial_outlier_flags_hole_far_from_the_batch():
    # DH04's northing was typed as a copy of its easting -- valid UTM, but
    # ~2,259 km south of the site.
    collars = [
        _site_collar("DH01", 208650.0, 2467800.0, 2),
        _site_collar("DH02", 208700.0, 2467850.0, 3),
        _site_collar("DH03", 208750.0, 2467900.0, 4),
        _site_collar("DH04", 208651.0, 208651.0, 5),
    ]
    res = validate_import_batch(collars, [], [], [])
    outliers = [i for i in res["issues"] if i["rule"] == "spatial_outlier"]
    assert len(outliers) == 1
    assert outliers[0]["hole_id"] == "DH04"
    assert outliers[0]["row"] == 5
    assert outliers[0]["type"] == "warning"
    assert "2259" in outliers[0]["message"].replace(".", "")
    # A warning must not block the import.
    assert res["valid"] is True

def test_spatial_outlier_silent_on_a_tight_site():
    collars = [
        _site_collar("DH01", 208650.0, 2467800.0, 2),
        _site_collar("DH02", 208700.0, 2467850.0, 3),
        _site_collar("DH03", 208750.0, 2467900.0, 4),
    ]
    res = validate_import_batch(collars, [], [], [])
    assert not [i for i in res["issues"] if i["rule"] == "spatial_outlier"]

def test_spatial_outlier_silent_on_a_regional_survey():
    # Holes several km apart are legitimate; the 10 km floor keeps them quiet.
    collars = [
        _site_collar("DH01", 200000.0, 2460000.0, 2),
        _site_collar("DH02", 203000.0, 2463000.0, 3),
        _site_collar("DH03", 206000.0, 2466000.0, 4),
        _site_collar("DH04", 209000.0, 2469000.0, 5),
    ]
    res = validate_import_batch(collars, [], [], [])
    assert not [i for i in res["issues"] if i["rule"] == "spatial_outlier"]

def test_spatial_outlier_reports_a_multi_point_trench_once():
    # A 60-point trench with a bad northing yields ONE issue, not 60.
    collars = [
        _site_collar("DH01", 208650.0, 2467800.0, 2),
        _site_collar("DH02", 208700.0, 2467850.0, 3),
        _site_collar("DH03", 208750.0, 2467900.0, 4),
    ]
    trenches = [
        {"trench_id": "TR01", "easting": 208660.0 + i, "northing": 208660.0 + i,
         "elevation": 290.0, "hole_type": "TR", "zone": "Adel", "csv_row": 100 + i}
        for i in range(60)
    ]
    res = validate_import_batch(collars, [], [], [], trenches=trenches)
    outliers = [i for i in res["issues"] if i["rule"] == "spatial_outlier"]
    assert len(outliers) == 1
    assert outliers[0]["hole_id"] == "TR01"

def test_spatial_outlier_needs_a_cluster_to_compare_against():
    # Two holes cannot establish a centre; no issue either way.
    collars = [
        _site_collar("DH01", 208650.0, 2467800.0, 2),
        _site_collar("DH02", 208651.0, 208651.0, 3),
    ]
    res = validate_import_batch(collars, [], [], [])
    assert not [i for i in res["issues"] if i["rule"] == "spatial_outlier"]
