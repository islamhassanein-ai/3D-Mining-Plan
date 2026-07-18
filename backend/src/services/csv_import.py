import csv
import io
from typing import List, Dict, Any, Tuple

def clean_header(header: str) -> str:
    return header.strip().lower().replace(" ", "_")

def parse_bdl_value(val_str: str) -> Tuple[float, bool, str]:
    """Parses a grade string, detecting Below Detection Limit (BDL) notation like '<0.01'.
    
    Returns a tuple of (parsed_float_value, below_detection_limit_boolean, error_message).
    """
    val_str = val_str.strip()
    if not val_str:
        return 0.0, False, "Value is empty"
        
    below_dl = False
    
    if val_str.startswith("<"):
        below_dl = True
        num_part = val_str[1:].strip()
    else:
        num_part = val_str
        
    try:
        val = float(num_part)
        return val, below_dl, ""
    except ValueError:
        return 0.0, False, f"Could not parse '{val_str}' as a numeric grade"

def get_csv_reader(file_content: bytes) -> Tuple[csv.DictReader, str]:
    """Decodes bytes and returns a csv.DictReader with standardized lowercase headers."""
    # Try decoding as utf-8, fallback to latin-1
    try:
        text = file_content.decode("utf-8")
    except UnicodeDecodeError:
        text = file_content.decode("latin-1")
        
    # Auto-detect delimiter
    delimiter = ","
    if text:
        first_line = text.split("\n")[0]
        if ";" in first_line and "," not in first_line:
            delimiter = ";"
            
    f = io.StringIO(text)
    reader = csv.DictReader(f, delimiter=delimiter)
    # Standardize fieldnames to lowercase and stripped
    if reader.fieldnames:
        reader.fieldnames = [clean_header(h) for h in reader.fieldnames]
    return reader, delimiter

def parse_collar_csv(file_content: bytes) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Parses Collar CSV. Required columns: hole_id, easting, northing, elevation."""
    reader, _ = get_csv_reader(file_content)
    parsed = []
    errors = []
    
    required = {"hole_id", "easting", "northing", "elevation"}
    if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
        missing = required - set(reader.fieldnames or [])
        errors.append({
            "row": 0,
            "error": f"Missing required headers: {', '.join(missing)}",
            "raw_data": {}
        })
        return parsed, errors
        
    for i, row in enumerate(reader, start=1):
        try:
            hole_id = row.get("hole_id", "").strip()
            if not hole_id:
                errors.append({"row": i, "error": "hole_id is required and cannot be empty", "raw_data": row})
                continue
                
            e_str = row.get("easting", "").strip()
            n_str = row.get("northing", "").strip()
            el_str = row.get("elevation", "").strip()
            
            try:
                easting = float(e_str)
                northing = float(n_str)
                elevation = float(el_str)
            except ValueError:
                errors.append({"row": i, "error": "Easting, Northing, and Elevation must be numeric values", "raw_data": row})
                continue
                
            utm_zone = row.get("utm_zone", "").strip()
            
            parsed.append({
                "hole_id": hole_id,
                "easting": easting,
                "northing": northing,
                "elevation": elevation,
                "utm_zone": utm_zone
            })
        except Exception as e:
            errors.append({"row": i, "error": f"Unexpected error: {str(e)}", "raw_data": row})
            
    return parsed, errors

def parse_survey_csv(file_content: bytes) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Parses Survey CSV. Required columns: hole_id, depth, dip, azimuth."""
    reader, _ = get_csv_reader(file_content)
    parsed = []
    errors = []
    
    required = {"hole_id", "depth", "dip", "azimuth"}
    if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
        missing = required - set(reader.fieldnames or [])
        errors.append({
            "row": 0,
            "error": f"Missing required headers: {', '.join(missing)}",
            "raw_data": {}
        })
        return parsed, errors
        
    for i, row in enumerate(reader, start=1):
        try:
            hole_id = row.get("hole_id", "").strip()
            if not hole_id:
                errors.append({"row": i, "error": "hole_id is required and cannot be empty", "raw_data": row})
                continue
                
            d_str = row.get("depth", "").strip()
            dip_str = row.get("dip", "").strip()
            az_str = row.get("azimuth", "").strip()
            
            try:
                depth = float(d_str)
                dip = float(dip_str)
                azimuth = float(az_str)
            except ValueError:
                errors.append({"row": i, "error": "Depth, Dip, and Azimuth must be numeric values", "raw_data": row})
                continue
                
            if depth < 0.0:
                errors.append({"row": i, "error": "Depth cannot be negative", "raw_data": row})
                continue
                
            if not (-90.0 <= dip <= 90.0):
                errors.append({"row": i, "error": "Dip must be between -90 and 90 degrees", "raw_data": row})
                continue
                
            if not (0.0 <= azimuth <= 360.0):
                errors.append({"row": i, "error": "Azimuth must be between 0 and 360 degrees", "raw_data": row})
                continue
                
            parsed.append({
                "hole_id": hole_id,
                "depth": depth,
                "dip": dip,
                "azimuth": azimuth
            })
        except Exception as e:
            errors.append({"row": i, "error": f"Unexpected error: {str(e)}", "raw_data": row})
            
    return parsed, errors

def parse_assay_csv(file_content: bytes) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Parses Assay CSV. Required columns: hole_id, from_depth, to_depth, grade_value."""
    reader, _ = get_csv_reader(file_content)
    parsed = []
    errors = []
    
    # We allow both grade_value or grade (flexibility)
    if reader.fieldnames:
        if "grade" in reader.fieldnames and "grade_value" not in reader.fieldnames:
            # map grade -> grade_value
            reader.fieldnames = ["grade_value" if h == "grade" else h for h in reader.fieldnames]
            
    required = {"hole_id", "from_depth", "to_depth", "grade_value"}
    if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
        missing = required - set(reader.fieldnames or [])
        errors.append({
            "row": 0,
            "error": f"Missing required headers: {', '.join(missing)}",
            "raw_data": {}
        })
        return parsed, errors
        
    for i, row in enumerate(reader, start=1):
        try:
            hole_id = row.get("hole_id", "").strip()
            if not hole_id:
                errors.append({"row": i, "error": "hole_id is required", "raw_data": row})
                continue
                
            f_str = row.get("from_depth", "").strip()
            t_str = row.get("to_depth", "").strip()
            g_str = row.get("grade_value", "").strip()
            
            try:
                from_depth = float(f_str)
                to_depth = float(t_str)
            except ValueError:
                errors.append({"row": i, "error": "From/To depths must be numeric", "raw_data": row})
                continue
                
            if from_depth < 0.0 or to_depth < 0.0:
                errors.append({"row": i, "error": "Depths cannot be negative", "raw_data": row})
                continue
                
            if to_depth <= from_depth:
                errors.append({"row": i, "error": "to_depth must be greater than from_depth", "raw_data": row})
                continue
                
            grade_val, below_dl, parse_err = parse_bdl_value(g_str)
            if parse_err:
                errors.append({"row": i, "error": parse_err, "raw_data": row})
                continue
                
            grade_unit = row.get("grade_unit", "").strip()
            qaqc_std = row.get("qaqc_standard", "").strip() or None

            # QA/QC sample type indicator: duplicate / standard / blank, or empty
            # for a regular sample. Accept either "qaqc_type" or "qaqc" as the
            # column name for flexibility, mirroring the grade/grade_value alias.
            qaqc_type_raw = (row.get("qaqc_type") or row.get("qaqc") or "").strip().lower()
            qaqc_type = qaqc_type_raw if qaqc_type_raw in ("duplicate", "standard", "blank") else None

            parsed.append({
                "hole_id": hole_id,
                "from_depth": from_depth,
                "to_depth": to_depth,
                "grade_value": grade_val,
                "grade_unit": grade_unit,
                "below_detection_limit": below_dl,
                "qaqc_type": qaqc_type,
                "qaqc_standard": qaqc_std
            })
        except Exception as e:
            errors.append({"row": i, "error": f"Unexpected error: {str(e)}", "raw_data": row})
            
    return parsed, errors

def parse_lithology_csv(file_content: bytes) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Parses Lithology CSV. Required columns: hole_id, from_depth, to_depth, lith_code."""
    reader, _ = get_csv_reader(file_content)
    parsed = []
    errors = []
    
    required = {"hole_id", "from_depth", "to_depth", "lith_code"}
    if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
        missing = required - set(reader.fieldnames or [])
        errors.append({
            "row": 0,
            "error": f"Missing required headers: {', '.join(missing)}",
            "raw_data": {}
        })
        return parsed, errors
        
    for i, row in enumerate(reader, start=1):
        try:
            hole_id = row.get("hole_id", "").strip()
            if not hole_id:
                errors.append({"row": i, "error": "hole_id is required", "raw_data": row})
                continue
                
            f_str = row.get("from_depth", "").strip()
            t_str = row.get("to_depth", "").strip()
            lith_code = row.get("lith_code", "").strip()
            
            try:
                from_depth = float(f_str)
                to_depth = float(t_str)
            except ValueError:
                errors.append({"row": i, "error": "From/To depths must be numeric", "raw_data": row})
                continue
                
            if from_depth < 0.0 or to_depth < 0.0:
                errors.append({"row": i, "error": "Depths cannot be negative", "raw_data": row})
                continue
                
            if to_depth <= from_depth:
                errors.append({"row": i, "error": "to_depth must be greater than from_depth", "raw_data": row})
                continue
                
            if not lith_code:
                errors.append({"row": i, "error": "lith_code cannot be empty", "raw_data": row})
                continue
                
            # Optional columns
            rqd = None
            if "rqd_percent" in row and row["rqd_percent"].strip():
                try:
                    rqd = int(row["rqd_percent"].strip())
                except ValueError:
                    pass
                    
            rec = None
            if "core_recovery_percent" in row and row["core_recovery_percent"].strip():
                try:
                    rec = int(row["core_recovery_percent"].strip())
                except ValueError:
                    pass
                    
            parsed.append({
                "hole_id": hole_id,
                "from_depth": from_depth,
                "to_depth": to_depth,
                "lith_code": lith_code,
                "rqd_percent": rqd,
                "core_recovery_percent": rec
            })
        except Exception as e:
            errors.append({"row": i, "error": f"Unexpected error: {str(e)}", "raw_data": row})
            
    return parsed, errors
