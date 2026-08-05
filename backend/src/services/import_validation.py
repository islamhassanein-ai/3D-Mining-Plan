from statistics import median
from typing import List, Dict, Any, Tuple

# --- Spatial outlier detection ------------------------------------------------
# A hole/trench this many times further from the batch's centre than a typical
# hole is treated as misplaced rather than merely remote.
_OUTLIER_FACTOR = 10.0
# ...but never flag anything closer than this, so a genuinely regional survey
# with holes a few kilometres apart is not reported. A coordinate typo displaces
# a hole by tens to thousands of kilometres, far beyond this floor.
_OUTLIER_FLOOR_M = 10_000.0
# Below this many holes there is no cluster to be an outlier from.
_OUTLIER_MIN_HOLES = 3


def _check_spatial_outliers(
    collars: List[Dict[str, Any]],
    trenches: List[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Flags holes/trenches sitting far outside the cluster formed by the batch.

    A single mistyped coordinate passes every per-value check -- 208651 is a
    perfectly valid UTM northing -- yet it wrecks the 3D view, because the
    camera frames the bounding box of all visible geometry
    (``frontend/src/scene/scene_loader.js`` ``visibleBounds``). One hole
    displaced 2000 km stretches that box ~15,000x, shrinking the real prospect
    to a fraction of a pixel: the scene looks blank until the offending layer
    is switched off.

    Detection is median-based so that a group of bad rows cannot drag the
    reference centre along with it: an outlying HOLE is measured against the
    median hole position, and the cutoff is a multiple of the median hole
    distance. Holes are scored once, by their own median point, so a 75-row
    trench yields one issue rather than 75.
    """
    points: Dict[str, Dict[str, Any]] = {}

    def add(hole_id, easting, northing, row):
        if not hole_id or easting is None or northing is None:
            return
        entry = points.setdefault(hole_id, {"e": [], "n": [], "row": row})
        entry["e"].append(easting)
        entry["n"].append(northing)
        if entry["row"] is None:
            entry["row"] = row

    for i, c in enumerate(collars or [], start=1):
        add(c.get("hole_id"), c.get("easting"), c.get("northing"), c.get("csv_row", i))
    for j, t in enumerate(trenches or [], start=1):
        add(t.get("trench_id"), t.get("easting"), t.get("northing"), t.get("csv_row", j))

    if len(points) < _OUTLIER_MIN_HOLES:
        return []

    centres = {h: (median(v["e"]), median(v["n"])) for h, v in points.items()}
    mid_e = median(e for e, _ in centres.values())
    mid_n = median(n for _, n in centres.values())

    distances = {
        h: ((e - mid_e) ** 2 + (n - mid_n) ** 2) ** 0.5
        for h, (e, n) in centres.items()
    }
    cutoff = max(_OUTLIER_FLOOR_M, _OUTLIER_FACTOR * median(distances.values()))

    issues = []
    for hole_id, dist in sorted(distances.items(), key=lambda kv: -kv[1]):
        if dist <= cutoff:
            continue
        e, n = centres[hole_id]
        issues.append({
            "type": "warning",
            "rule": "spatial_outlier",
            "message": (
                f"'{hole_id}' sits {dist / 1000:.1f} km from the centre of this batch "
                f"(E {e:,.0f}, N {n:,.0f}). Check its Easting/Northing for a typo -- a "
                "hole this far out stretches the 3D camera bounds until the rest of the "
                "site is too small to see."
            ),
            "hole_id": hole_id,
            "row": points[hole_id]["row"],
        })
    return issues


def validate_import_batch(
    collars: List[Dict[str, Any]],
    surveys: List[Dict[str, Any]],
    assays: List[Dict[str, Any]],
    lithologies: List[Dict[str, Any]],
    project_utm_zone: str = None,
    qaqc_standards: List[Dict[str, Any]] = None,
    trenches: List[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Runs all geological validation rules on the parsed CSV data before it is committed.

    Returns a dictionary:
    - 'valid': bool (True if there are no blocking errors; warnings do not make it invalid)
    - 'issues': list of dicts, each with keys 'type' (error/warning), 'rule', 'message', 'hole_id', 'row'
    - 'summary': dict with statistics

    ``trenches`` (combined-CSV path only): trench point rows routed by
    ``route_combined_rows``. When supplied, trench rows are kept OUT of the
    ``collars`` list and their inline dip/azimuth OUT of ``surveys`` by the
    caller, so the ``orphan_hole_id`` rule never fires for them. We additionally
    enforce: the same ``hole_id`` under two different zones is an error
    (ambiguous routing), and the same ``hole_id`` with two different
    ``hole_type``s is an error. ``check_coordinate_anomalies`` is run per zone
    group (collars + trench points) rather than once for the whole file, so a
    zone with swapped coordinates is reported against that zone alone.

    ``_check_spatial_outliers`` then runs across the whole batch (both paths,
    all zones) to catch a mistyped coordinate that is individually valid but
    lands the hole far from every other one.
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

    # 1b. Combined-CSV routing rules: the same hole_id under two different
    # zones, or with two different hole_types, is ambiguous and must block.
    if trenches is not None:
        seen_routing: Dict[str, Dict[str, Any]] = {}
        for i, c in enumerate(collars, start=1):
            h_id = c["hole_id"]
            entry = {"zone": c.get("zone"), "hole_type": c.get("hole_type"), "row": c.get("csv_row", i)}
            if h_id in seen_routing:
                prev = seen_routing[h_id]
                if prev["zone"] != entry["zone"]:
                    issues.append({
                        "type": "error",
                        "rule": "ambiguous_zone",
                        "message": f"hole_id '{h_id}' appears under two different zones ('{prev['zone']}' and '{entry['zone']}')",
                        "hole_id": h_id,
                        "row": i
                    })
                if prev["hole_type"] != entry["hole_type"]:
                    issues.append({
                        "type": "error",
                        "rule": "ambiguous_hole_type",
                        "message": f"hole_id '{h_id}' appears with two different hole_types ('{prev['hole_type']}' and '{entry['hole_type']}')",
                        "hole_id": h_id,
                        "row": i
                    })
            else:
                seen_routing[h_id] = entry
        for j, t in enumerate(trenches, start=1):
            h_id = t["trench_id"]
            entry = {"zone": t.get("zone"), "hole_type": t.get("hole_type"), "row": t.get("csv_row", j)}
            if h_id in seen_routing:
                prev = seen_routing[h_id]
                if prev["zone"] != entry["zone"]:
                    issues.append({
                        "type": "error",
                        "rule": "ambiguous_zone",
                        "message": f"hole_id '{h_id}' appears under two different zones ('{prev['zone']}' and '{entry['zone']}')",
                        "hole_id": h_id,
                        "row": j
                    })
                if prev["hole_type"] != entry["hole_type"]:
                    issues.append({
                        "type": "error",
                        "rule": "ambiguous_hole_type",
                        "message": f"hole_id '{h_id}' appears with two different hole_types ('{prev['hole_type']}' and '{entry['hole_type']}')",
                        "hole_id": h_id,
                        "row": j
                    })
            else:
                seen_routing[h_id] = entry

    # 2. Coordinate checks (Swapped Lat/Long & UTM zone mismatch)
    from backend.src.services.crs import check_coordinate_anomalies

    if trenches is not None:
        # Combined path: run check_coordinate_anomalies PER zone group (collars
        # + trench points), rather than once for the whole file. Rows with
        # zone=None group together (they fall back to the URL project). The
        # per-row collar-vs-project UTM mismatch warning is skipped here because
        # combined rows carry no row-level utm_zone -- the resolved project zone
        # is applied at commit, and per-zone coordinate bounds are the relevant
        # guard.
        groups: Dict[str, List[Tuple[float, float]]] = {}
        for c in collars:
            groups.setdefault(str(c.get("zone")), []).append((c["easting"], c["northing"]))
        for t in trenches:
            if t.get("easting") is None or t.get("northing") is None:
                continue
            groups.setdefault(str(t.get("zone")), []).append((t["easting"], t["northing"]))
        for zone_key, coords in groups.items():
            eastings = [e for e, _ in coords]
            northings = [n for _, n in coords]
            anomalies = check_coordinate_anomalies(eastings, northings)
            if anomalies["swapped"]:
                issues.append({
                    "type": "error",
                    "rule": "swapped_coordinates",
                    "message": f"Coordinates in zone '{zone_key}' appear to be swapped: Eastings are > 1,000,000 and Northings are < 1,000,000",
                    "hole_id": "",
                    "row": None
                })
            if anomalies["out_of_bounds"]:
                issues.append({
                    "type": "error",
                    "rule": "coordinates_out_of_bounds",
                    "message": f"Coordinates in zone '{zone_key}' are outside of valid UTM ranges",
                    "hole_id": "",
                    "row": None
                })
    else:
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

            # UTM zone checks (legacy four-file path: rows carry their own
            # utm_zone column, compared against the single project zone).
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

    # 2b. Spatial outliers. Runs on both paths and across zones, since a typo
    # that lands a hole in the wrong zone group is exactly what this catches.
    issues.extend(_check_spatial_outliers(collars, trenches))

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
    if trenches is not None:
        summary["trench_count"] = len(trenches)
    
    return {
        "valid": valid,
        "issues": issues,
        "summary": summary
    }
