import pytest
from backend.src.services.crs import detect_utm_zone, check_coordinate_anomalies

def test_crs_detect_zone_default():
    assert detect_utm_zone([350000.0], [2800000.0], "36N") == "36N"
    assert detect_utm_zone([], [], "35N") == "35N"

def test_crs_normal_coordinates():
    # Valid Easting and Northing values for Egypt
    eastings = [350000.0, 360000.0, 370000.0]
    northings = [2800000.0, 2810000.0, 2820000.0]
    
    anomalies = check_coordinate_anomalies(eastings, northings)
    assert anomalies["swapped"] is False
    assert anomalies["out_of_bounds"] is False

def test_crs_swapped_coordinates():
    # Easting and Northing values are swapped
    eastings = [2800000.0, 2810000.0]
    northings = [350000.0, 360000.0]
    
    anomalies = check_coordinate_anomalies(eastings, northings)
    assert anomalies["swapped"] is True
    assert anomalies["out_of_bounds"] is False

def test_crs_out_of_bounds_coordinates():
    # Invalid coordinates
    eastings = [950000.0] # standard Easting is 100k to 900k
    northings = [2800000.0]
    
    anomalies = check_coordinate_anomalies(eastings, northings)
    assert anomalies["out_of_bounds"] is True
    
    # Swapped but also out of bounds
    eastings = [12000000.0] # > 10,000,000
    northings = [350000.0]
    anomalies = check_coordinate_anomalies(eastings, northings)
    assert anomalies["swapped"] is True
    assert anomalies["out_of_bounds"] is True
