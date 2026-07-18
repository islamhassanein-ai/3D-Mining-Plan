import pytest
import math
from backend.src.services.desurvey import (
    interpolate_azimuth,
    interpolate_survey,
    compute_minimum_curvature_trace
)

def test_interpolate_azimuth_basic():
    # Simple midpoint interpolation
    assert math.isclose(interpolate_azimuth(0.0, 90.0, 0.5), 45.0)
    assert math.isclose(interpolate_azimuth(90.0, 180.0, 0.5), 135.0)

def test_interpolate_azimuth_wrap():
    # Wrap-around across 360/0 boundary
    # Midpoint between 350 and 10 should be 0 (or 360)
    assert math.isclose(interpolate_azimuth(350.0, 10.0, 0.5), 0.0, abs_tol=1e-7)
    # Midpoint between 10 and 350 should be 0 (or 360)
    assert math.isclose(interpolate_azimuth(10.0, 350.0, 0.5), 0.0, abs_tol=1e-7)
    # Midpoint between 355 and 5 should be 0 (or 360)
    assert math.isclose(interpolate_azimuth(355.0, 5.0, 0.5), 0.0, abs_tol=1e-7)

def test_interpolate_survey_clamp():
    surveys = [
        {'depth': 10.0, 'dip': -45.0, 'azimuth': 90.0},
        {'depth': 50.0, 'dip': -30.0, 'azimuth': 180.0}
    ]
    # Before first station
    res1 = interpolate_survey(surveys, 5.0)
    assert res1['depth'] == 5.0
    assert res1['dip'] == -45.0
    assert res1['azimuth'] == 90.0

    # After last station
    res2 = interpolate_survey(surveys, 60.0)
    assert res2['depth'] == 60.0
    assert res2['dip'] == -30.0
    assert res2['azimuth'] == 180.0

def test_interpolate_survey_midpoint():
    surveys = [
        {'depth': 0.0, 'dip': -90.0, 'azimuth': 0.0},
        {'depth': 100.0, 'dip': -60.0, 'azimuth': 90.0}
    ]
    res = interpolate_survey(surveys, 50.0)
    assert res['depth'] == 50.0
    assert math.isclose(res['dip'], -75.0)
    assert math.isclose(res['azimuth'], 45.0)

def test_vertical_borehole():
    # Straight vertical downward borehole starting at elevation 100
    surveys = [
        {'depth': 0.0, 'dip': -90.0, 'azimuth': 0.0},
        {'depth': 100.0, 'dip': -90.0, 'azimuth': 0.0}
    ]
    trace = compute_minimum_curvature_trace(1000.0, 5000.0, 100.0, surveys)
    
    assert len(trace) == 2
    # Start point
    assert trace[0]['depth'] == 0.0
    assert math.isclose(trace[0]['x'], 1000.0)
    assert math.isclose(trace[0]['y'], 5000.0)
    assert math.isclose(trace[0]['z'], 100.0)
    # End point
    assert trace[1]['depth'] == 100.0
    assert math.isclose(trace[1]['x'], 1000.0)
    assert math.isclose(trace[1]['y'], 5000.0)
    assert math.isclose(trace[1]['z'], 0.0) # went down 100m

def test_horizontal_borehole():
    # Straight horizontal borehole pointing East (azimuth 90)
    surveys = [
        {'depth': 0.0, 'dip': 0.0, 'azimuth': 90.0},
        {'depth': 100.0, 'dip': 0.0, 'azimuth': 90.0}
    ]
    trace = compute_minimum_curvature_trace(1000.0, 5000.0, 100.0, surveys)
    
    assert len(trace) == 2
    # Start point
    assert trace[0]['depth'] == 0.0
    assert math.isclose(trace[0]['x'], 1000.0)
    assert math.isclose(trace[0]['y'], 5000.0)
    assert math.isclose(trace[0]['z'], 100.0)
    # End point
    assert trace[1]['depth'] == 100.0
    assert math.isclose(trace[1]['x'], 1100.0) # went East 100m
    assert math.isclose(trace[1]['y'], 5000.0)
    assert math.isclose(trace[1]['z'], 100.0)

def test_near_vertical_and_horizontal_edge_cases():
    # Near-vertical station (dip ≈ -89.999)
    surveys_vert = [
        {'depth': 0.0, 'dip': -90.0, 'azimuth': 0.0},
        {'depth': 100.0, 'dip': -89.999, 'azimuth': 45.0}
    ]
    trace_vert = compute_minimum_curvature_trace(0.0, 0.0, 0.0, surveys_vert)
    assert len(trace_vert) == 2
    for p in trace_vert:
        assert not math.isnan(p['x'])
        assert not math.isnan(p['y'])
        assert not math.isnan(p['z'])

    # Near-horizontal station (dip ≈ 0.001)
    surveys_horiz = [
        {'depth': 0.0, 'dip': 0.0, 'azimuth': 90.0},
        {'depth': 100.0, 'dip': 0.001, 'azimuth': 90.0}
    ]
    trace_horiz = compute_minimum_curvature_trace(0.0, 0.0, 0.0, surveys_horiz)
    assert len(trace_horiz) == 2
    for p in trace_horiz:
        assert not math.isnan(p['x'])
        assert not math.isnan(p['y'])
        assert not math.isnan(p['z'])

def test_curved_borehole():
    # Borehole starting vertical and curving to horizontal East
    surveys = [
        {'depth': 0.0, 'dip': -90.0, 'azimuth': 0.0},
        {'depth': 100.0, 'dip': 0.0, 'azimuth': 90.0}
    ]
    trace = compute_minimum_curvature_trace(0.0, 0.0, 0.0, surveys)
    assert len(trace) == 2
    # Verify end point goes down (Z decrease) and East/North (X/Y increase)
    assert trace[1]['z'] < 0.0
    assert trace[1]['x'] > 0.0
    # Minimum curvature must not produce NaN or infinite values
    assert all(not math.isnan(trace[1][k]) for k in ['x', 'y', 'z'])
