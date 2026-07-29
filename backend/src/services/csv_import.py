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


# Combined Master Reference CSV -- one row per hole/trench mixing all
# exploration types, with inline Dip/Azimuth/Total_Length and a Zone column.
# See specs/006-combined-csv-import/tasks.md for the full rationale.

# Maps each canonical field to the set of cleaned header names it may appear
# under in the wild (after clean_header lowercases and underscores). The x/y/z
# aliases are MANDATORY -- the real reference file header is `X,Y,Z`, not the
# `easting/northing/elevation` parse_collar_csv expects.
_COMBINED_HEADER_ALIASES = [
    ("hole_id", {"hole_id", "holeid", "hole", "trench_id"}),
    ("easting", {"x", "easting", "east"}),
    ("northing", {"y", "northing", "north"}),
    ("elevation", {"z", "elevation", "elev", "rl"}),
    ("dip", {"dip"}),
    ("azimuth", {"azimuth", "azi", "bearing"}),
    ("total_length", {"total_length", "total_depth", "length", "eoh"}),
    ("hole_type", {"type", "hole_type"}),
    ("zone", {"zone", "area", "prospect"}),
]

_VALID_HOLE_TYPES = {"DD", "RC", "TR", "CH", "FC"}


def parse_combined_csv(file_content: bytes) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Parses a combined Master Reference CSV.

    Required columns: ``hole_id`` plus easting/northing/elevation (under any of
    their aliases, including ``x``/``y``/``z``). ``hole_type`` defaults to ``DD``
    with a single file-level warning when the column is absent. ``Dip``,
    ``Azimuth`` and ``Total_Length`` are optional but coupled: they must all be
    present together or all absent (see task spec rules).

    Returns ``(parsed, errors)`` under the same convention as the other parsers.
    The missing-``Type``-column warning is emitted into ``errors`` with a
    ``"type": "warning"`` field so callers can surface it without treating it as
    a blocking row error; row-level errors carry no ``type`` field (matching the
    other parsers and the existing ``add_parse_errors`` default of "error").

    Row numbers in errors match spreadsheet line numbers (header = line 1, so
    the first data row is line 2) via ``enumerate(reader, start=2)``.
    """
    reader, _ = get_csv_reader(file_content)
    parsed = []
    errors = []

    raw_fields = list(reader.fieldnames or [])

    # Build a canonical -> original-fieldname lookup so we can read each row by
    # canonical key regardless of which alias the file used. Iterate
    # reader.fieldnames IN ORDER (not a set) so alias resolution is
    # deterministic. If two different headers map to the same canonical field
    # (e.g. a file has both `X` and `Easting`), reject the file with a clear
    # header-level error rather than silently picking one nondeterministically.
    canonical_to_original = {}
    field_to_canonical = {}
    for original in raw_fields:
        for canonical, aliases in _COMBINED_HEADER_ALIASES:
            if original in aliases:
                if canonical in canonical_to_original and canonical_to_original[canonical] != original:
                    errors.append({
                        "row": 0,
                        "error": (
                            f"Duplicate header for '{canonical}': both "
                            f"'{canonical_to_original[canonical]}' and '{original}' "
                            f"are present. Remove one."
                        ),
                        "raw_data": {}
                    })
                    return parsed, errors
                # Prefer the canonical name itself when present; otherwise take
                # the first alias seen in header order.
                if canonical not in canonical_to_original or original == canonical:
                    canonical_to_original[canonical] = original
                field_to_canonical[original] = canonical
                break

    canonical_present = set(canonical_to_original.keys())

    required = {"hole_id", "easting", "northing", "elevation"}
    missing_required = required - canonical_present
    if not raw_fields or missing_required:
        errors.append({
            "row": 0,
            "error": (
                "Missing required headers: "
                + ", ".join(sorted(missing_required))
            ),
            "raw_data": {}
        })
        return parsed, errors

    # hole_type column handling: absent -> one file-level warning, default DD
    # for every row. Present-but-blank is treated as an invalid value per-row.
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
        # O(1) reverse-dict lookup instead of a per-field linear scan.
        original = canonical_to_original.get(canonical)
        return row.get(original, "") if original else ""

    for i, row in enumerate(reader, start=2):
        try:
            hole_id = get_canonical(row, "hole_id").strip()
            if not hole_id:
                errors.append({"row": i, "error": "hole_id is required and cannot be empty", "raw_data": row})
                continue

            e_str = get_canonical(row, "easting").strip()
            n_str = get_canonical(row, "northing").strip()
            el_str = get_canonical(row, "elevation").strip()

            try:
                easting = float(e_str)
                northing = float(n_str)
                elevation = float(el_str)
            except ValueError:
                errors.append({"row": i, "error": "Easting, Northing, and Elevation must be numeric values", "raw_data": row})
                continue

            # hole_type
            if hole_type_absent:
                hole_type = "DD"
            else:
                ht_raw = get_canonical(row, "hole_type").strip().upper()
                if ht_raw not in _VALID_HOLE_TYPES:
                    errors.append({"row": i, "error": f"Invalid hole_type '{ht_raw}'. Must be one of: {', '.join(sorted(_VALID_HOLE_TYPES))}", "raw_data": row})
                    continue
                hole_type = ht_raw

            # dip / azimuth / total_length -- coupled optionality.
            # Distinguish an empty string from a literal 0: a truthiness check
            # ("if not dip_str") wrongly treats ARTR031's Dip=0 and ARTR008's
            # Azimuth=2 as missing. Compare against "" after stripping.
            dip_str = get_canonical(row, "dip").strip()
            az_str = get_canonical(row, "azimuth").strip()
            tl_str = get_canonical(row, "total_length").strip()

            dip_present = dip_str != ""
            az_present = az_str != ""
            tl_present = tl_str != ""

            if (dip_present or az_present) and not tl_present:
                errors.append({"row": i, "error": "Dip/Azimuth present without total_length; all three are required together", "raw_data": row})
                continue
            if tl_present and not (dip_present and az_present):
                errors.append({"row": i, "error": "total_length present without both dip and azimuth; all three are required together", "raw_data": row})
                continue

            inline_survey = None
            if tl_present:
                try:
                    dip = float(dip_str)
                    azimuth = float(az_str)
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

                inline_survey = {
                    "dip": dip,
                    "azimuth": azimuth,
                    "total_length": total_length
                }

            # zone: collapse internal whitespace and strip. Blank or column
            # absent -> None; the caller falls back to the URL project.
            zone_raw = get_canonical(row, "zone").strip()
            if zone_raw != "":
                zone = " ".join(zone_raw.split())
                # if it reduced to empty (was all whitespace), treat as None
                if zone == "":
                    zone = None
            else:
                zone = None

            parsed.append({
                "hole_id": hole_id,
                "easting": easting,
                "northing": northing,
                "elevation": elevation,
                "hole_type": hole_type,
                "zone": zone,
                "inline_survey": inline_survey,
                "csv_row": i,
            })
        except Exception as e:
            errors.append({"row": i, "error": f"Unexpected error: {str(e)}", "raw_data": row})

    return parsed, errors
