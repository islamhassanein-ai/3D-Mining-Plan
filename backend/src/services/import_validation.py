from typing import List, Dict, Any, Tuple

def validate_import_batch(
    collars: List[Dict[str, Any]],
    surveys: List[Dict[str, Any]],
    assays: List[Dict[str, Any]],
    lithologies: List[Dict[str, Any]],
    project_utm_zone: str = None,
    qaqc_standards: List[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Runs all geological validation rules on the parsed CSV data before it is committed.
    
    Returns a dictionary:
    - 'valid': bool (True if there are no blocking errors; warnings do not make it invalid)
    - 'issues': list of dicts, each with keys 'type' (error/warning), 'rule', 'message', 'hole_id', 'row'
    - 'summary': dict with statistics
    """
    issues = []
    
    # 1. Map collars for fast lookup and verify unique hole_ids in this batch
    collar_holes = set()
    collar_by_hole = {}
    for i, c in enumerate(collars, start=1):
        h_id = c["hole_id"]
        if h_id in collar_holes:
            issues.append({
                "type": "error",
                "rule": "duplicate_collar",
                "message": f"Duplicate collar hole_id '{h_id}' found in the upload",
                "hole_id": h_id,
                "row": i
            })
        collar_holes.add(h_id)
        collar_by_hole[h_id] = c

    # 2. Coordinate checks (Swapped Lat/Long & UTM zone mismatch)
    from backend.src.services.crs import check_coordinate_anomalies
    eastings = [c["easting"] for c in collars]
    northings = [c["northing"] for c in collars]
    
    if collars:
        anomalies = check_coordinate_anomalies(eastings, northings)
        if anomalies["swapped"]:
            issues.append({
                "type": "error",
                "rule": "swapped_coordinates",
                "message": "Coordinates appear to be swapped: Eastings are > 1,000,000 and Northings are < 1,000,000",
                "hole_id": "",
                "row": None
            })
        if anomalies["out_of_bounds"]:
            issues.append({
                "type": "error",
                "rule": "coordinates_out_of_bounds",
                "message": "Coordinates are outside of valid UTM ranges",
                "hole_id": "",
                "row": None
            })
            
        # UTM zone checks
        for i, c in enumerate(collars, start=1):
            c_zone = c.get("utm_zone")
            if c_zone and project_utm_zone and c_zone != project_utm_zone:
                issues.append({
                    "type": "warning",
                    "rule": "utm_zone_mismatch",
                    "message": f"Collar UTM zone '{c_zone}' does not match project zone '{project_utm_zone}'",
                    "hole_id": c["hole_id"],
                    "row": i
                })

    # 3. Orphan hole_id checks (Surveys, Assays, Lithologies must have a collar in this batch)
    for i, s in enumerate(surveys, start=1):
        h_id = s["hole_id"]
        if h_id not in collar_holes:
            issues.append({
                "type": "error",
                "rule": "orphan_hole_id",
                "message": f"Survey references hole_id '{h_id}' which has no matching Collar row",
                "hole_id": h_id,
                "row": i
            })

    for i, a in enumerate(assays, start=1):
        h_id = a["hole_id"]
        if h_id not in collar_holes:
            issues.append({
                "type": "error",
                "rule": "orphan_hole_id",
                "message": f"Assay references hole_id '{h_id}' which has no matching Collar row",
                "hole_id": h_id,
                "row": i
            })

    for i, l in enumerate(lithologies, start=1):
        h_id = l["hole_id"]
        if h_id not in collar_holes:
            issues.append({
                "type": "error",
                "rule": "orphan_hole_id",
                "message": f"Lithology references hole_id '{h_id}' which has no matching Collar row",
                "hole_id": h_id,
                "row": i
            })

    # 4. BDL (Below Detection Limit) preservation check
    for i, a in enumerate(assays, start=1):
        if a.get("below_detection_limit") and a.get("grade_value", 0.0) <= 0.0:
            issues.append({
                "type": "error",
                "rule": "bdl_zero_or_negative",
                "message": "Below detection limit (BDL) rows must retain their positive detection limit value (cannot be zero or negative)",
                "hole_id": a["hole_id"],
                "row": i
            })

    # 5. Mixed grade unit checks
    grade_units = set(a.get("grade_unit") for a in assays if a.get("grade_unit"))
    if len(grade_units) > 1:
        issues.append({
            "type": "error",
            "rule": "mixed_units",
            "message": f"Mixed grade units detected within the same upload: {', '.join(grade_units)}. All rows must use the same unit.",
            "hole_id": "",
            "row": None
        })

    # 6. Overlap and Gap detection (run per hole_id)
    # Group intervals by hole_id
    assays_by_hole: Dict[str, List[Tuple[int, Dict[str, Any]]]] = {}
    liths_by_hole: Dict[str, List[Tuple[int, Dict[str, Any]]]] = {}
    
    for i, a in enumerate(assays, start=1):
        h_id = a["hole_id"]
        assays_by_hole.setdefault(h_id, []).append((i, a))
        
    for i, l in enumerate(lithologies, start=1):
        h_id = l["hole_id"]
        liths_by_hole.setdefault(h_id, []).append((i, l))

    # Detect Assay overlaps/gaps
    for h_id, intervals in assays_by_hole.items():
        # Sort by from_depth
        sorted_intervals = sorted(intervals, key=lambda pair: pair[1]["from_depth"])
        for idx in range(1, len(sorted_intervals)):
            prev_row_num, prev_a = sorted_intervals[idx - 1]
            curr_row_num, curr_a = sorted_intervals[idx]
            
            p_to = prev_a["to_depth"]
            c_from = curr_a["from_depth"]
            
            if c_from < p_to - 1e-4:  # Overlap (with small tolerance)
                issues.append({
                    "type": "warning",
                    "rule": "assay_overlap",
                    "message": f"Assay interval overlap: depth {c_from} is less than previous interval end {p_to}",
                    "hole_id": h_id,
                    "row": curr_row_num
                })
            elif c_from > p_to + 1e-4:  # Gap (with small tolerance)
                issues.append({
                    "type": "warning",
                    "rule": "assay_gap",
                    "message": f"Assay interval gap detected: gap of {c_from - p_to:.3f}m between {p_to} and {c_from}",
                    "hole_id": h_id,
                    "row": curr_row_num
                })

    # Detect Lithology overlaps/gaps
    for h_id, intervals in liths_by_hole.items():
        sorted_intervals = sorted(intervals, key=lambda pair: pair[1]["from_depth"])
        for idx in range(1, len(sorted_intervals)):
            prev_row_num, prev_l = sorted_intervals[idx - 1]
            curr_row_num, curr_l = sorted_intervals[idx]
            
            p_to = prev_l["to_depth"]
            c_from = curr_l["from_depth"]
            
            if c_from < p_to - 1e-4:  # Overlap
                issues.append({
                    "type": "warning",
                    "rule": "lithology_overlap",
                    "message": f"Lithology interval overlap: depth {c_from} is less than previous interval end {p_to}",
                    "hole_id": h_id,
                    "row": curr_row_num
                })
            elif c_from > p_to + 1e-4:  # Gap
                issues.append({
                    "type": "warning",
                    "rule": "lithology_gap",
                    "message": f"Lithology interval gap detected: gap of {c_from - p_to:.3f}m between {p_to} and {c_from}",
                    "hole_id": h_id,
                    "row": curr_row_num
                })

    # 7. Validate RQD and Core Recovery ranges (0-100%)
    for i, l in enumerate(lithologies, start=1):
        rqd = l.get("rqd_percent")
        rec = l.get("core_recovery_percent")
        
        if rqd is not None and not (0 <= rqd <= 100):
            issues.append({
                "type": "error",
                "rule": "rqd_out_of_range",
                "message": f"RQD percentage must be between 0 and 100, found {rqd}",
                "hole_id": l["hole_id"],
                "row": i
            })
            
        if rec is not None and not (0 <= rec <= 100):
            issues.append({
                "type": "error",
                "rule": "core_recovery_out_of_range",
                "message": f"Core recovery percentage must be between 0 and 100, found {rec}",
                "hole_id": l["hole_id"],
                "row": i
            })

    # 8. QA/QC sample flagging (duplicate / standard / blank), per data-model.md.
    # `qaqc_type` (from the assay CSV's QA/QC indicator column) determines the
    # sample kind. Duplicate and blank samples are flagged as-is -- there's no
    # reference range to check them against. Standard samples are additionally
    # compared against the matching QA/QC Standard Reference.
    standards_map = {std["standard_name"].lower(): std for std in (qaqc_standards or [])}
    for i, a in enumerate(assays, start=1):
        qtype = a.get("qaqc_type")

        if qtype == "duplicate":
            a["qaqc_flag"] = "duplicate"
            continue

        if qtype == "blank":
            a["qaqc_flag"] = "blank"
            continue

        if qtype != "standard":
            continue

        std_name = a.get("qaqc_standard")
        std = standards_map.get(std_name.lower()) if std_name else None
        # A match requires both the standard name AND the grade unit to agree --
        # comparing a raw numeric value against a range configured in a
        # different unit (e.g. ppm vs %) would be meaningless. If there's no
        # matching, unit-consistent reference, this must be flagged as
        # "unconfigured" per data-model.md -- never silently skipped or
        # treated as passing.
        if std is None or std.get("grade_unit") != a.get("grade_unit"):
            a["qaqc_flag"] = "unconfigured"
            issues.append({
                "type": "warning",
                "rule": "qaqc_standard_unconfigured",
                "message": f"Assay row is flagged as a QA/QC standard sample ('{std_name or 'unnamed'}') but no Standard Reference is configured for this project with a matching name and grade_unit.",
                "hole_id": a["hole_id"],
                "row": i
            })
            continue

        val = float(a["grade_value"])
        min_val = float(std["expected_grade_min"])
        max_val = float(std["expected_grade_max"])
        if not (min_val <= val <= max_val):
            a["qaqc_flag"] = "standard_failed"
            issues.append({
                "type": "warning",
                "rule": "qaqc_standard_failed",
                "message": f"QA/QC Standard '{std_name}' failed expectation: expected {min_val} to {max_val}, found {val}",
                "hole_id": a["hole_id"],
                "row": i
            })
        else:
            a["qaqc_flag"] = "standard"

    # Determine validity
    has_errors = any(issue["type"] == "error" for issue in issues)
    valid = not has_errors
    
    summary = {
        "collar_count": len(collars),
        "survey_count": len(surveys),
        "assay_count": len(assays),
        "lithology_count": len(lithologies),
        "error_count": sum(1 for issue in issues if issue["type"] == "error"),
        "warning_count": sum(1 for issue in issues if issue["type"] == "warning")
    }
    
    return {
        "valid": valid,
        "issues": issues,
        "summary": summary
    }
