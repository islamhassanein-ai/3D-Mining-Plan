import shapefile
import io
import re
from typing import List, Tuple, Dict, Any, Optional

def check_shapefile_crs(prj_bytes: Optional[bytes], expected_zone: str) -> Dict[str, Any]:
    """
    Checks if the Shapefile's coordinate reference system (PRJ) matches the project's UTM zone.
    """
    if not prj_bytes:
        return {"valid": False, "message": "Missing .prj file. Coordinate reference system is ambiguous."}
    
    try:
        prj_text = prj_bytes.decode('utf-8', errors='ignore').upper()
    except Exception:
        return {"valid": False, "message": "Failed to decode .prj file."}
        
    # Standard UTM projections in PRJ look like "...UTM ZONE 36N..." or "...UTM_ZONE_36N..."
    clean_zone = expected_zone.upper()
    
    zone_match = re.search(r'UTM\s*ZONE\s*(\d+)([NS]?)', prj_text) or re.search(r'UTM_ZONE_(\d+)([NS]?)', prj_text)
    
    if not zone_match:
        return {"valid": False, "message": "Ambiguous CRS: WKT does not specify a UTM projection zone."}
    
    detected_num = zone_match.group(1)
    detected_hemi = zone_match.group(2) or "N"
    detected_zone = f"{detected_num}{detected_hemi}"
    
    if detected_zone != clean_zone:
        return {"valid": False, "message": f"CRS mismatch: Shapefile is in UTM Zone {detected_zone}, but Project is in UTM Zone {clean_zone}."}
        
    return {"valid": True, "message": "CRS matches project."}


def parse_trench_shapefile(shp_bytes: bytes, dbf_bytes: bytes, shx_bytes: bytes) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Parses trench sample points from Shapefile bytes.
    Returns (rows, errors).
    """
    rows = []
    errors = []
    
    try:
        shp_io = io.BytesIO(shp_bytes)
        dbf_io = io.BytesIO(dbf_bytes)
        shx_io = io.BytesIO(shx_bytes)
        reader = shapefile.Reader(shp=shp_io, dbf=dbf_io, shx=shx_io)
    except Exception as e:
        errors.append(f"Failed to open trench Shapefile: {str(e)}")
        return [], errors

    fields = [f[0].lower() for f in reader.fields[1:]]
    
    # Try to map field indices based on common names
    trench_id_idx = -1
    grade_idx = -1
    elevation_idx = -1
    
    for i, name in enumerate(fields):
        if "trench" in name or "id" in name:
            trench_id_idx = i
        if "grade" in name or "val" in name:
            grade_idx = i
        if "elev" in name or "z" in name or "alt" in name:
            elevation_idx = i

    # Fallbacks if field names are not matched
    if trench_id_idx == -1 and len(fields) > 0:
        trench_id_idx = 0
    if grade_idx == -1 and len(fields) > 1:
        grade_idx = 1

    for idx, shape_record in enumerate(reader.shapeRecords()):
        try:
            shape = shape_record.shape
            record = shape_record.record
            
            if not shape.points:
                continue
                
            x, y = shape.points[0]
            z = shape.z[0] if (hasattr(shape, 'z') and len(shape.z) > 0) else 0.0
            
            if elevation_idx != -1 and len(record) > elevation_idx:
                try:
                    z = float(record[elevation_idx])
                except (ValueError, TypeError):
                    pass
            
            t_id = str(record[trench_id_idx]).strip() if (trench_id_idx != -1 and len(record) > trench_id_idx) else f"TR_{idx+1}"
            
            grade_val = None
            if grade_idx != -1 and len(record) > grade_idx:
                try:
                    grade_val = float(record[grade_idx]) if record[grade_idx] is not None else None
                except (ValueError, TypeError):
                    pass

            rows.append({
                "trench_id": t_id,
                "easting": float(x),
                "northing": float(y),
                "elevation": float(z),
                "grade_value": grade_val
            })
        except Exception as e:
            errors.append(f"Error parsing shape record {idx}: {str(e)}")
            
    return rows, errors

def parse_topography_shapefile(shp_bytes: bytes, dbf_bytes: bytes, shx_bytes: bytes) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Parses topography surface vertices from Shapefile bytes.
    Returns (points, errors).
    """
    points = []
    errors = []
    
    try:
        shp_io = io.BytesIO(shp_bytes)
        dbf_io = io.BytesIO(dbf_bytes)
        shx_io = io.BytesIO(shx_bytes)
        reader = shapefile.Reader(shp=shp_io, dbf=dbf_io, shx=shx_io)
    except Exception as e:
        errors.append(f"Failed to open topography Shapefile: {str(e)}")
        return [], errors

    for idx, shape_record in enumerate(reader.shapeRecords()):
        try:
            shape = shape_record.shape
            if not shape.points:
                continue
            
            has_z = hasattr(shape, 'z') and len(shape.z) == len(shape.points)
            for pt_idx, (x, y) in enumerate(shape.points):
                z = shape.z[pt_idx] if has_z else 0.0
                points.append({
                    "easting": float(x),
                    "northing": float(y),
                    "elevation": float(z)
                })
        except Exception as e:
            errors.append(f"Error parsing shape record {idx}: {str(e)}")
            
    if not points and not errors:
        errors.append("No 3D vertices found in topography Shapefile.")
        
    return points, errors
