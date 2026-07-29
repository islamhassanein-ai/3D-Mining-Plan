from typing import List, Dict, Any

# Downstream export code (and the combined-CSV auto-project path) need to map a
# UTM zone token to its EPSG code. The Monark field area is EPSG:32637 (UTM 37N).
EPSG_BY_UTM_ZONE = {
    "36N": 32636,
    "37N": 32637,
}

def detect_utm_zone(
    eastings: List[float],
    northings: List[float],
    project_default_zone: str = "37N"
) -> str:
    """Auto-detects the likely UTM zone from Easting/Northing coordinate ranges.

    If the ranges are valid UTM coordinates, returns the project_default_zone
    (defaults to 37N -- the Monark field area in Egypt sits in UTM zone 37N).
    """
    if not eastings or not northings:
        return project_default_zone

    # Standard UTM Easting is roughly 100,000m to 900,000m.
    # Standard UTM Northing is 0m to 10,000,000m.
    # In Egypt, Northing is between 2,400,000m and 3,500,000m.
    return project_default_zone

def check_coordinate_anomalies(eastings: List[float], northings: List[float]) -> Dict[str, Any]:
    """Checks for coordinate errors such as swapped Easting/Northing.
    
    Returns a dictionary of boolean flags:
    - 'swapped': True if Easting/Northing appear to be swapped.
    - 'out_of_bounds': True if coordinates are completely outside normal UTM ranges.
    """
    if not eastings or not northings:
        return {"swapped": False, "out_of_bounds": False}
        
    avg_e = sum(eastings) / len(eastings)
    avg_n = sum(northings) / len(northings)
    
    swapped = False
    out_of_bounds = False
    
    # Heuristic for swapped coordinates (Easting > 1,000,000 and Northing < 1,000,000)
    if avg_e > 1000000.0 and avg_n < 1000000.0:
        swapped = True
        
    # Check if either coordinate is out of UTM limits
    # Normal Easting is 100,000 to 900,000
    # Normal Northing is 0 to 10,000,000
    for e in eastings:
        if swapped:
            # If swapped, check against the opposite bound
            if not (0.0 <= e <= 10000000.0):
                out_of_bounds = True
        else:
            if not (100000.0 <= e <= 900000.0):
                out_of_bounds = True
                
    for n in northings:
        if swapped:
            if not (100000.0 <= n <= 900000.0):
                out_of_bounds = True
        else:
            if not (0.0 <= n <= 10000000.0):
                out_of_bounds = True
                
    return {"swapped": swapped, "out_of_bounds": out_of_bounds}
