import math
from typing import List, Dict, Any

def interpolate_azimuth(az1: float, az2: float, t: float) -> float:
    """Linearly interpolates azimuths handling the 360-degree wrap-around."""
    rad1 = math.radians(az1)
    rad2 = math.radians(az2)
    
    x1 = math.cos(rad1)
    y1 = math.sin(rad1)
    x2 = math.cos(rad2)
    y2 = math.sin(rad2)
    
    x = (1.0 - t) * x1 + t * x2
    y = (1.0 - t) * y1 + t * y2
    
    # If the interpolated vector is 0 (angles are opposite), default to az1
    if abs(x) < 1e-9 and abs(y) < 1e-9:
        return az1
        
    interpolated_rad = math.atan2(y, x)
    interpolated_deg = math.degrees(interpolated_rad)
    val = interpolated_deg % 360.0
    if val >= 360.0 - 1e-7 or val <= 1e-7:
        return 0.0
    return val

def interpolate_survey(surveys: List[Dict[str, float]], target_depth: float) -> Dict[str, float]:
    """Interpolates dip and azimuth at a target depth from a list of survey stations.
    
    Assumes surveys list is sorted by depth.
    """
    if not surveys:
        raise ValueError("Cannot interpolate surveys: surveys list is empty.")
        
    # Edge case: target depth is before or at the first survey station
    if target_depth <= surveys[0]['depth']:
        return {'depth': target_depth, 'dip': surveys[0]['dip'], 'azimuth': surveys[0]['azimuth']}
        
    # Edge case: target depth is at or after the last survey station
    if target_depth >= surveys[-1]['depth']:
        return {'depth': target_depth, 'dip': surveys[-1]['dip'], 'azimuth': surveys[-1]['azimuth']}
        
    # Find the bounding survey stations
    for i in range(1, len(surveys)):
        s1 = surveys[i - 1]
        s2 = surveys[i]
        if s1['depth'] <= target_depth <= s2['depth']:
            d1, d2 = s1['depth'], s2['depth']
            if abs(d2 - d1) < 1e-9:
                return {'depth': target_depth, 'dip': s1['dip'], 'azimuth': s1['azimuth']}
                
            t = (target_depth - d1) / (d2 - d1)
            dip = s1['dip'] + t * (s2['dip'] - s1['dip'])
            azimuth = interpolate_azimuth(s1['azimuth'], s2['azimuth'], t)
            return {'depth': target_depth, 'dip': dip, 'azimuth': azimuth}
            
    # Fallback
    return {'depth': target_depth, 'dip': surveys[-1]['dip'], 'azimuth': surveys[-1]['azimuth']}

def compute_minimum_curvature_trace(
    collar_easting: float,
    collar_northing: float,
    collar_elevation: float,
    surveys: List[Dict[str, float]]
) -> List[Dict[str, float]]:
    """Computes the 3D trace coordinates along the borehole using the minimum-curvature method.
    
    Each survey in the list must be a dictionary with keys: 'depth', 'dip', 'azimuth'.
    The returned list contains dictionaries with keys: 'depth', 'x', 'y', 'z', 'dip', 'azimuth'.
    """
    if not surveys:
        return []
        
    # Sort surveys by depth
    sorted_surveys = sorted(surveys, key=lambda s: s['depth'])
    
    # If there is no survey station at depth 0, insert a virtual one with the first station's orientation
    if sorted_surveys[0]['depth'] > 0:
        virtual_first = {
            'depth': 0.0,
            'dip': sorted_surveys[0]['dip'],
            'azimuth': sorted_surveys[0]['azimuth']
        }
        sorted_surveys.insert(0, virtual_first)
    elif sorted_surveys[0]['depth'] < 0:
        # Depth should not be negative, but clamp it to 0 just in case
        sorted_surveys[0]['depth'] = 0.0

    trace = []
    
    # Initialize the first point at the collar coordinates
    x, y, z = collar_easting, collar_northing, collar_elevation
    
    # Direction cosine function
    def get_direction_cosine(dip_deg: float, az_deg: float) -> tuple:
        # dip is angle from horizontal, downward is negative (-90 is vertical down, 0 is horizontal)
        # azimuth is clockwise angle from North (0 is North, 90 is East)
        I = math.radians(dip_deg)
        A = math.radians(az_deg)
        
        dx = math.cos(I) * math.sin(A)
        dy = math.cos(I) * math.cos(A)
        dz = math.sin(I)
        return dx, dy, dz

    # Add the starting point
    s0 = sorted_surveys[0]
    trace.append({
        'depth': s0['depth'],
        'x': x,
        'y': y,
        'z': z,
        'dip': s0['dip'],
        'azimuth': s0['azimuth']
    })
    
    for i in range(1, len(sorted_surveys)):
        s_prev = sorted_surveys[i - 1]
        s_curr = sorted_surveys[i]
        
        d1, d2 = s_prev['depth'], s_curr['depth']
        delta_md = d2 - d1
        
        if delta_md <= 0:
            # Skip zero or negative length segments
            continue
            
        # Direction cosines for previous and current stations
        v1_x, v1_y, v1_z = get_direction_cosine(s_prev['dip'], s_prev['azimuth'])
        v2_x, v2_y, v2_z = get_direction_cosine(s_curr['dip'], s_curr['azimuth'])
        
        # Calculate dogleg angle beta (in radians)
        cos_beta = v1_x * v2_x + v1_y * v2_y + v1_z * v2_z
        # Clamp to avoid floating point range errors
        cos_beta = max(-1.0, min(1.0, cos_beta))
        beta = math.acos(cos_beta)
        
        # Calculate Ratio Factor (RF)
        if beta < 1e-6:
            rf = 1.0
        else:
            rf = (2.0 / beta) * math.tan(beta / 2.0)
            
        # Calculate the displacement
        dx = (delta_md / 2.0) * (v1_x + v2_x) * rf
        dy = (delta_md / 2.0) * (v1_y + v2_y) * rf
        dz = (delta_md / 2.0) * (v1_z + v2_z) * rf
        
        x += dx
        y += dy
        z += dz
        
        trace.append({
            'depth': s_curr['depth'],
            'x': x,
            'y': y,
            'z': z,
            'dip': s_curr['dip'],
            'azimuth': s_curr['azimuth']
        })
        
    return trace
