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
    # utf-8-sig, not utf-8: Excel on Windows writes a UTF-8 BOM, and a plain
    # utf-8 decode leaves it on the first header, so "Hole Id" cleans to
    # "﻿hole_id" and every required-header check fails with a misleading
    # "missing column" error naming a column that is plainly present. utf-8-sig
    # strips the BOM when present and behaves identically to utf-8 when absent,
    # so the latin-1 fallback and all five parsers are unaffected.
    try:
        text = file_content.decode("utf-8-sig")
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


# Combined Master Reference CSV.
#
# Supports:
#   - One collar row per DD/RC hole (with X/Y/Z, Dip/Azi/Length), plus N sample
#     continuation rows (same hole_id, blank X/Y/Z, with Sample_ID/From/To/Grade).
#   - One or more rows per TR/CH/FC trench: each row is a sample point with
#     its own X/Y/Z, Sample_ID, From/To, and Grade, connected in CSV order.
#
# See specs/006-combined-csv-import/tasks.md for the full rationale.

_COMBINED_HEADER_ALIASES = [
    ("hole_id",       {"hole_id", "holeid", "hole", "trench_id"}),
    ("easting",       {"x", "easting", "east"}),
    ("northing",      {"y", "northing", "north"}),
    ("elevation",     {"z", "elevation", "elev", "rl"}),
    ("end_easting",   {"end_x", "end_easting", "x_end"}),
    ("end_northing",  {"end_y", "end_northing", "y_end"}),
    ("end_elevation", {"end_z", "end_elevation", "z_end", "end_elev"}),
    ("sample_id",     {"sample_id", "sample", "sampleid", "sample_no", "sample_number"}),
    ("from_depth",    {"from", "from_depth", "depth_from", "start_depth", "from_m"}),
    ("to_depth",      {"to", "to_depth", "depth_to", "end_depth", "to_m"}),
    ("grade_value",   {"grade", "grade_value", "au", "grade_ppm", "grade_pct", "assay"}),
    ("grade_unit",    {"grade_unit", "unit", "units"}),
    ("dip",           {"dip"}),
    ("azimuth",       {"azimuth", "azi", "bearing"}),
    ("total_length",  {"total_length", "total_depth", "length", "eoh"}),
    ("hole_type",     {"type", "hole_type"}),
    ("hole_status",   {"status", "hole_status", "planned", "is_planned"}),
    ("zone",          {"zone", "area", "prospect"}),
]

_VALID_HOLE_TYPES = {"DD", "RC", "TR", "CH", "FC"}

# Accepted Status values, normalised to 'drilled' / 'planned'. Blank inherits
# from the hole's first row, then defaults to 'drilled' -- historical CSVs
# have no Status column and describe holes that were actually drilled.
_HOLE_STATUS_ALIASES = {
    "drilled":   "drilled",
    "drill":     "drilled",
    "completed": "drilled",
    "complete":  "drilled",
    "existing":  "drilled",
    "actual":    "drilled",
    "false":     "drilled",
    "no":        "drilled",
    "0":         "drilled",
    "planned":   "planned",
    "plan":      "planned",
    "proposed":  "planned",
    "target":    "planned",
    "design":    "planned",
    "true":      "planned",
    "yes":       "planned",
    "1":         "planned",
}
_TRENCH_TYPES     = {"TR", "CH", "FC"}
_COLLAR_TYPES     = {"DD", "RC"}


def parse_combined_csv(file_content: bytes) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Parses a combined Master Reference CSV.

    Required columns: ``hole_id`` plus easting/northing/elevation (under any
    alias). On **sample continuation rows** for DD/RC (same hole_id, no X/Y/Z),
    easting/northing/elevation are allowed to be blank.

    **Multi-row TR/CH/FC**: each row is a sample point with its own X/Y/Z and
    optional Grade/Sample_ID/From/To. Rows connect in CSV order.

    **DD/RC sample rows**: continuation rows after the collar row carry
    Sample_ID, From, To, Grade and are routed as assay intervals.

    Returns ``(parsed, errors)``.  Each parsed dict has a ``"row_kind"`` key:
      - ``"collar"``  for the first/only row of a DD/RC hole
      - ``"assay"``   for DD/RC sample continuation rows
      - ``"trench"``  for all TR/CH/FC rows
    """
    reader, _ = get_csv_reader(file_content)
    parsed = []
    errors = []

    raw_fields = list(reader.fieldnames or [])

    canonical_to_original: Dict[str, str] = {}
    for original in raw_fields:
        for canonical, aliases in _COMBINED_HEADER_ALIASES:
            if original in aliases:
                if canonical in canonical_to_original and canonical_to_original[canonical] != original:
                    errors.append({
                        "row": 0,
                        "error": (
                            f"Duplicate header for '{canonical}': both "
                            f"'{canonical_to_original[canonical]}' and '{original}' present."
                        ),
                        "raw_data": {}
                    })
                    return parsed, errors
                if canonical not in canonical_to_original or original == canonical:
                    canonical_to_original[canonical] = original
                break

    canonical_present = set(canonical_to_original.keys())

    required = {"hole_id", "easting", "northing", "elevation"}
    missing_required = required - canonical_present
    if not raw_fields or missing_required:
        errors.append({
            "row": 0,
            "error": "Missing required headers: " + ", ".join(sorted(missing_required)),
            "raw_data": {}
        })
        return parsed, errors

    hole_type_absent = "hole_type" not in canonical_present
    if hole_type_absent:
        errors.append({
            "row": 0,
            "error": (
                "No 'Type' column found; defaulting all rows to hole_type 'DD'. "
                "Supply a Type column (DD/RC/TR/CH/FC) to route rows correctly."
            ),
            "raw_data": {},
            "type": "warning"
        })

    def get_canonical(row, canonical):
        original = canonical_to_original.get(canonical)
        return row.get(original, "") if original else ""

    # Track first-seen metadata for multi-row holes.
    # collar_ids: hole_ids registered as DD/RC collars
    # trench_ids: hole_ids registered as TR/CH/FC
    # Both store {"hole_type", "zone"} for type/zone inheritance on continuation rows.
    collar_meta: Dict[str, Dict] = {}
    trench_meta: Dict[str, Dict] = {}
    # hole_id -> 'drilled' | 'planned', so continuation rows inherit the
    # status declared on the hole's first row.
    hole_status_meta: Dict[str, str] = {}

    for i, row in enumerate(reader, start=2):
        try:
            hole_id = get_canonical(row, "hole_id").strip()
            if not hole_id:
                errors.append({"row": i, "error": "hole_id is required and cannot be empty", "raw_data": row})
                continue

            # --- Resolve hole_type (blank on continuation rows inherits) ---
            if hole_type_absent:
                hole_type = "DD"
            else:
                ht_raw = get_canonical(row, "hole_type").strip().upper()
                if ht_raw == "":
                    if hole_id in collar_meta:
                        hole_type = collar_meta[hole_id]["hole_type"]
                    elif hole_id in trench_meta:
                        hole_type = trench_meta[hole_id]["hole_type"]
                    else:
                        errors.append({"row": i, "error": f"hole_type is blank and '{hole_id}' has no prior row to inherit from", "raw_data": row})
                        continue
                elif ht_raw not in _VALID_HOLE_TYPES:
                    errors.append({"row": i, "error": f"Invalid hole_type '{ht_raw}'. Must be one of: {', '.join(sorted(_VALID_HOLE_TYPES))}", "raw_data": row})
                    continue
                else:
                    hole_type = ht_raw

            # --- Type-conflict detection ---
            if hole_id in collar_meta and hole_type in _TRENCH_TYPES:
                errors.append({"row": i, "error": f"hole_id '{hole_id}' was registered as {collar_meta[hole_id]['hole_type']}; cannot reuse as {hole_type}", "raw_data": row})
                continue
            if hole_id in trench_meta and hole_type in _COLLAR_TYPES:
                errors.append({"row": i, "error": f"hole_id '{hole_id}' was registered as {trench_meta[hole_id]['hole_type']}; cannot reuse as {hole_type}", "raw_data": row})
                continue
            if hole_id in trench_meta and hole_type != trench_meta[hole_id]["hole_type"]:
                errors.append({"row": i, "error": f"hole_id '{hole_id}' type mismatch: first row was {trench_meta[hole_id]['hole_type']}, this row is {hole_type}", "raw_data": row})
                continue

            # --- Coordinates (optional on DD/RC sample continuation rows) ---
            e_str  = get_canonical(row, "easting").strip()
            n_str  = get_canonical(row, "northing").strip()
            el_str = get_canonical(row, "elevation").strip()
            coords_blank = (e_str == "" and n_str == "" and el_str == "")
            is_dd_rc_continuation = hole_type in _COLLAR_TYPES and hole_id in collar_meta

            if coords_blank and not is_dd_rc_continuation:
                errors.append({"row": i, "error": "Easting, Northing, Elevation are required for the first row of each hole/trench", "raw_data": row})
                continue

            easting = northing = elevation = None
            if not coords_blank:
                try:
                    easting   = float(e_str)
                    northing  = float(n_str)
                    elevation = float(el_str)
                except ValueError:
                    errors.append({"row": i, "error": "Easting, Northing, and Elevation must be numeric values", "raw_data": row})
                    continue

            # --- DD/RC: duplicate collar check ---
            if hole_type in _COLLAR_TYPES and hole_id in collar_meta and not coords_blank:
                errors.append({"row": i, "error": f"Duplicate DD/RC collar '{hole_id}': collar coordinates already registered. Omit X/Y/Z on sample rows.", "raw_data": row})
                continue

            # --- End coordinates (TR/CH/FC single-row mode) ---
            end_e_str  = get_canonical(row, "end_easting").strip()
            end_n_str  = get_canonical(row, "end_northing").strip()
            end_el_str = get_canonical(row, "end_elevation").strip()
            end_coords = None
            if end_e_str and end_n_str and end_el_str:
                try:
                    end_coords = {
                        "easting":   float(end_e_str),
                        "northing":  float(end_n_str),
                        "elevation": float(end_el_str),
                    }
                except ValueError:
                    errors.append({"row": i, "error": "End_X, End_Y, End_Z must be numeric values", "raw_data": row})
                    continue
            elif end_e_str or end_n_str or end_el_str:
                errors.append({"row": i, "error": "End coordinates are incomplete; End_X, End_Y, and End_Z must all be provided together", "raw_data": row})
                continue

            # --- Sample_ID / From / To ---
            sample_id = get_canonical(row, "sample_id").strip() or None
            from_str  = get_canonical(row, "from_depth").strip()
            to_str    = get_canonical(row, "to_depth").strip()
            from_present = from_str != ""
            to_present   = to_str   != ""
            if from_present != to_present:
                errors.append({"row": i, "error": "From and To depths must both be present or both absent", "raw_data": row})
                continue
            from_depth = to_depth = None
            if from_present:
                try:
                    from_depth = float(from_str)
                    to_depth   = float(to_str)
                except ValueError:
                    errors.append({"row": i, "error": "From and To depths must be numeric values", "raw_data": row})
                    continue
                if from_depth < 0 or to_depth < 0:
                    errors.append({"row": i, "error": "From and To depths must be >= 0", "raw_data": row})
                    continue
                if to_depth <= from_depth:
                    errors.append({"row": i, "error": f"To depth ({to_depth}) must be greater than From depth ({from_depth})", "raw_data": row})
                    continue

            # --- Grade / Grade unit ---
            grade_str = get_canonical(row, "grade_value").strip()
            grade_value = None
            if grade_str:
                try:
                    grade_value = float(grade_str)
                except ValueError:
                    errors.append({"row": i, "error": f"Grade value '{grade_str}' is not a valid number", "raw_data": row})
                    continue

            grade_unit_raw = get_canonical(row, "grade_unit").strip()
            grade_unit = grade_unit_raw if grade_unit_raw else "g/t"

            # --- Dip / Azimuth / Total_Length (collar and first-row metadata) ---
            dip_str = get_canonical(row, "dip").strip()
            az_str  = get_canonical(row, "azimuth").strip()
            tl_str  = get_canonical(row, "total_length").strip()
            dip_present = dip_str != ""
            az_present  = az_str  != ""
            tl_present  = tl_str  != ""

            if (dip_present or az_present) and not tl_present:
                errors.append({"row": i, "error": "Dip/Azimuth present without total_length; all three are required together", "raw_data": row})
                continue
            if tl_present and not (dip_present and az_present):
                errors.append({"row": i, "error": "total_length present without both dip and azimuth; all three are required together", "raw_data": row})
                continue

            inline_survey = None
            if tl_present:
                try:
                    dip          = float(dip_str)
                    azimuth      = float(az_str)
                    total_length = float(tl_str)
                except ValueError:
                    errors.append({"row": i, "error": "Dip, Azimuth, and Total_Length must be numeric values", "raw_data": row})
                    continue
                if total_length <= 0.0:
                    errors.append({"row": i, "error": "Total_Length must be greater than 0", "raw_data": row})
                    continue
                if not (-90.0 <= dip <= 90.0):
                    errors.append({"row": i, "error": "Dip must be between -90 and 90 degrees", "raw_data": row})
                    continue
                if not (0.0 <= azimuth <= 360.0):
                    errors.append({"row": i, "error": "Azimuth must be between 0 and 360 degrees", "raw_data": row})
                    continue
                inline_survey = {"dip": dip, "azimuth": azimuth, "total_length": total_length}

            # --- Hole status (inherits from first row on continuation) ---
            status_raw = get_canonical(row, "hole_status").strip().lower()
            if status_raw != "":
                if status_raw not in _HOLE_STATUS_ALIASES:
                    errors.append({
                        "row": i,
                        "error": (
                            f"Invalid status '{status_raw}'. Use 'drilled' or 'planned'."
                        ),
                        "raw_data": row,
                    })
                    continue
                hole_status = _HOLE_STATUS_ALIASES[status_raw]
            else:
                hole_status = hole_status_meta.get(hole_id, "drilled")
            hole_status_meta.setdefault(hole_id, hole_status)

            # --- Zone (inherits from first row on continuation) ---
            zone_raw = get_canonical(row, "zone").strip()
            if zone_raw != "":
                zone = " ".join(zone_raw.split()) or None
            elif hole_type in _COLLAR_TYPES and hole_id in collar_meta:
                zone = collar_meta[hole_id]["zone"]
            elif hole_type in _TRENCH_TYPES and hole_id in trench_meta:
                zone = trench_meta[hole_id]["zone"]
            else:
                zone = None

            # --- Register first-seen metadata ---
            if hole_type in _COLLAR_TYPES and hole_id not in collar_meta:
                collar_meta[hole_id] = {"hole_type": hole_type, "zone": zone}
            if hole_type in _TRENCH_TYPES and hole_id not in trench_meta:
                trench_meta[hole_id] = {"hole_type": hole_type, "zone": zone}

            # --- Determine row_kind and emit ---
            if hole_type in _TRENCH_TYPES:
                row_kind = "trench"
            elif hole_type in _COLLAR_TYPES and hole_id in collar_meta and is_dd_rc_continuation:
                row_kind = "assay"
            else:
                row_kind = "collar"

            parsed.append({
                "row_kind":     row_kind,
                "hole_id":      hole_id,
                "easting":      easting,
                "northing":     northing,
                "elevation":    elevation,
                "hole_type":    hole_type,
                "hole_status":  hole_status,
                "zone":         zone,
                "inline_survey": inline_survey,
                "end_coords":   end_coords,
                "sample_id":    sample_id,
                "from_depth":   from_depth,
                "to_depth":     to_depth,
                "grade_value":  grade_value,
                "grade_unit":   grade_unit,
                "csv_row":      i,
            })
        except Exception as e:
            errors.append({"row": i, "error": f"Unexpected error: {str(e)}", "raw_data": row})

    return parsed, errors
