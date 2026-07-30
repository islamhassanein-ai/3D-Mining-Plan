"""Routing for the combined Master Reference CSV.

Splits the parsed rows from ``parse_combined_csv`` into four storage buckets:

* ``collars``       -- one per DD/RC collar row, carrying ``hole_type``.
* ``surveys``       -- one per DD/RC collar row that has an inline survey, at
  ``depth == total_length`` (NOT 0). ``compute_minimum_curvature_trace`` at
  ``backend/src/services/desurvey.py:79`` auto-prepends a virtual station at
  depth 0 with the same orientation, producing a correct two-station trace; a
  single station at depth 0 would yield a one-point trace and an invisible hole.
* ``trench_points`` -- one per TR/CH/FC sample row, connected in CSV order.
  Multi-row trenches: each row's X/Y/Z becomes a polyline vertex.
  Single-row trenches: a computed far-end point (from inline_survey or
  end_coords) is appended so the polyline always has >= 2 points.
* ``assays``        -- one per DD/RC sample continuation row (blank X/Y/Z),
  carrying depth intervals to be committed as AssayInterval records.

CRITICAL geological constraint: Dip/Azimuth on TR/CH/FC is the local ground
slope AT THE START POINT ONLY, not the trench trajectory. We do NOT call
``compute_minimum_curvature_trace`` for trenches -- it would apply dip along the
full length and put ARTR001 (dip +16, length 145) ~40 m in the air. Generated
trench endpoint (for single-row mode) stays flat at collar elevation (dz = 0).
"""
import logging
import math
import uuid
from typing import Dict, List, Optional

_log = logging.getLogger(__name__)

# Hole types that store as Collar (+ optional inline Survey).
_COLLAR_TYPES = {"DD", "RC"}
# Hole types that store as Trench multi-point polylines.
_TRENCH_TYPES = {"TR", "CH", "FC"}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _route_single_row_trench(r: Dict) -> List[Dict]:
    """Two-point horizontal polyline from a single TR/CH/FC row.

    Start = row X/Y/Z.  End = computed from inline_survey (azimuth + length,
    dz = 0) or from ``end_coords`` if provided.  Falls back to a degenerate
    zero-length segment when neither is available.
    """
    hole_id   = r["hole_id"]
    hole_type = r["hole_type"]
    zone      = r.get("zone")
    csv_row   = r.get("csv_row")
    x, y, z   = r["easting"], r["northing"], r["elevation"]
    inline    = r.get("inline_survey")
    end_coords = r.get("end_coords")

    # Anchor point — dip/azimuth stored at point_order=0 only (start-slope metadata).
    dip0     = inline["dip"]      if inline else None
    azimuth0 = inline["azimuth"]  if inline else None

    if inline is not None:
        L      = inline["total_length"]
        az_rad = math.radians(inline["azimuth"])
        far_e  = x + L * math.sin(az_rad)
        far_n  = y + L * math.cos(az_rad)
        far_z  = z  # dz = 0
    elif end_coords is not None:
        far_e = end_coords["easting"]
        far_n = end_coords["northing"]
        far_z = end_coords["elevation"]
    else:
        _log.warning("Trench %s has no inline survey or end coords — polyline degenerates to a dot", hole_id)
        far_e, far_n, far_z = x, y, z

    return [
        {
            "trench_id":   hole_id,
            "easting":     x,
            "northing":    y,
            "elevation":   z,
            "point_order": 0,
            "hole_type":   hole_type,
            "zone":        zone,
            "dip":         dip0,
            "azimuth":     azimuth0,
            "grade_value": r.get("grade_value"),
            "sample_id":   r.get("sample_id"),
            "from_depth":  r.get("from_depth"),
            "to_depth":    r.get("to_depth"),
            "csv_row":     csv_row,
        },
        {
            "trench_id":   hole_id,
            "easting":     far_e,
            "northing":    far_n,
            "elevation":   far_z,
            "point_order": 1,
            "hole_type":   hole_type,
            "zone":        zone,
            "dip":         None,
            "azimuth":     None,
            "grade_value": None,
            "sample_id":   None,
            "from_depth":  None,
            "to_depth":    None,
            "csv_row":     csv_row,
        },
    ]


def _route_multi_row_trench(rows: List[Dict]) -> List[Dict]:
    """N-point polyline from multiple TR/CH/FC rows with the same hole_id.

    Each row contributes one vertex at its own X/Y/Z.  dip/azimuth from the
    first row's inline_survey go onto point_order=0 only; subsequent points
    get dip=None/azimuth=None.
    """
    points = []
    first_inline = rows[0].get("inline_survey")
    for order, r in enumerate(rows):
        points.append({
            "trench_id":   r["hole_id"],
            "easting":     r["easting"],
            "northing":    r["northing"],
            "elevation":   r["elevation"],
            "point_order": order,
            "hole_type":   r["hole_type"],
            "zone":        r.get("zone"),
            "dip":         first_inline["dip"]     if order == 0 and first_inline else None,
            "azimuth":     first_inline["azimuth"] if order == 0 and first_inline else None,
            "grade_value": r.get("grade_value"),
            "sample_id":   r.get("sample_id"),
            "from_depth":  r.get("from_depth"),
            "to_depth":    r.get("to_depth"),
            "csv_row":     r.get("csv_row"),
        })
    return points


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def route_combined_rows(rows: List[Dict]) -> Dict[str, List[Dict]]:
    """Route parsed combined-CSV rows into collars, surveys, trench_points, assays.

    Accepts rows produced by ``parse_combined_csv`` (which include a
    ``"row_kind"`` field) **and** plain dicts without ``"row_kind"`` (legacy
    test fixtures); in the latter case the kind is inferred from ``hole_type``.

    Returns::

        {
            "collars":       [...],
            "surveys":       [...],
            "trench_points": [...],   # one per polyline vertex, ordered
            "assays":        [...],   # DD/RC sample continuation rows
        }
    """
    collars: List[Dict]        = []
    surveys: List[Dict]        = []
    trench_rows: Dict[str, List[Dict]] = {}  # hole_id -> ordered list of trench rows
    trench_order: List[str]    = []           # preserves first-seen insertion order
    assays: List[Dict]         = []

    for r in rows:
        hole_type = r["hole_type"]
        hole_id   = r["hole_id"]
        zone      = r.get("zone")
        inline    = r.get("inline_survey")
        csv_row   = r.get("csv_row")

        # Infer row_kind when caller omits it (legacy test fixtures).
        row_kind = r.get("row_kind")
        if row_kind is None:
            row_kind = "trench" if hole_type in _TRENCH_TYPES else "collar"

        if row_kind == "collar":
            collars.append({
                "hole_id":   hole_id,
                "easting":   r["easting"],
                "northing":  r["northing"],
                "elevation": r["elevation"],
                "utm_zone":  None,   # resolved per-project at commit
                "hole_type": hole_type,
                "zone":      zone,
                "csv_row":   csv_row,
            })
            if inline is not None:
                # One station at depth == total_length; desurvey prepends depth=0.
                surveys.append({
                    "hole_id": hole_id,
                    "depth":   inline["total_length"],
                    "dip":     inline["dip"],
                    "azimuth": inline["azimuth"],
                })
            # When the collar row itself carries sample data (Sample_ID + From/To),
            # emit an assay so interval S01 is not silently dropped.
            if r.get("sample_id") and r.get("from_depth") is not None and r.get("to_depth") is not None:
                assays.append({
                    "hole_id":     hole_id,
                    "sample_id":   r.get("sample_id"),
                    "from_depth":  r.get("from_depth"),
                    "to_depth":    r.get("to_depth"),
                    "grade_value": r.get("grade_value"),
                    "grade_unit":  r.get("grade_unit", "g/t"),
                    "csv_row":     csv_row,
                })

        elif row_kind == "assay":
            assays.append({
                "hole_id":     hole_id,
                "sample_id":   r.get("sample_id"),
                "from_depth":  r.get("from_depth"),
                "to_depth":    r.get("to_depth"),
                "grade_value": r.get("grade_value"),
                "grade_unit":  r.get("grade_unit", "g/t"),
                "csv_row":     csv_row,
            })

        elif row_kind == "trench":
            if hole_id not in trench_rows:
                trench_rows[hole_id] = []
                trench_order.append(hole_id)
            trench_rows[hole_id].append(r)

    # Build trench_points preserving hole insertion order, then point order.
    trench_points: List[Dict] = []
    for hid in trench_order:
        group = trench_rows[hid]
        if len(group) == 1:
            trench_points.extend(_route_single_row_trench(group[0]))
        else:
            trench_points.extend(_route_multi_row_trench(group))

    return {
        "collars":       collars,
        "surveys":       surveys,
        "trench_points": trench_points,
        "assays":        assays,
    }


# ---------------------------------------------------------------------------
# Zone resolution (T007)
# ---------------------------------------------------------------------------

def _normalize_zone_key(zone: str) -> str:
    """Match key for a zone name: collapse internal whitespace and casefold.

    "Abo elmajd", "Abo Elmajd", and "abo elmajd " all resolve to one project.
    """
    return " ".join(zone.split()).casefold()


def _match_existing_zone_project(db, current_user, normalized_key: str):
    """Finds an existing, non-superseded project owned by current_user whose
    name normalizes to ``normalized_key``.

    Project.name has no unique constraint, so without the owner + supersession
    filters an import could land in a superseded project or another user's
    project. Returns the matched Project or None.
    """
    from backend.src.models.project import Project

    candidates = db.query(Project).filter(
        Project.owner_id == current_user.id,
        Project.superseded_by.is_(None),
    ).all()
    for p in candidates:
        if p.name is None:
            continue
        if _normalize_zone_key(p.name) == normalized_key:
            return p
    return None


def resolve_or_create_zone_projects(
    db,
    zones: List[Optional[str]],
    current_user,
    utm_zone: str = "37N",
    commodity: str = "Gold",
) -> Dict[str, Dict]:
    """Resolve each distinct non-null zone to an existing or newly created
    project owned by ``current_user``.

    Returns ``{normalized_zone_key: {"project": Project, "action":
    "created"|"appended", "name": first_seen_original_casing}}``.

    - Match key: ``_normalize_zone_key``. The FIRST-seen original casing for a
      key is stored as the project name on create.
    - An existing project matches only when owner_id == current_user.id AND
      superseded_by IS NULL.
    - On create: owner_id = current_user.id, commodity = ``commodity``,
      utm_zone = ``utm_zone``. A null owner makes a project inaccessible to
      everyone (see project.py:16-22), so owner_id is always set.
    - Rows with zone=None are skipped here; the caller routes them to the URL
      project that already exists.

    NOTE: This function MUTATES the database (creates Project rows). The
    preview path (create_import) must not call it -- use
    ``preview_zone_projects`` instead.
    """
    from backend.src.models.project import Project

    resolved: Dict[str, Dict] = {}
    for zone in zones:
        if zone is None:
            continue
        key = _normalize_zone_key(zone)
        if key in resolved:
            continue  # first-seen casing preserved; duplicates collapse
        existing = _match_existing_zone_project(db, current_user, key)
        if existing is not None:
            resolved[key] = {"project": existing, "action": "appended", "name": existing.name}
        else:
            project = Project(
                id=uuid.uuid4(),
                name=zone,  # first-seen original casing
                commodity=commodity,
                utm_zone=utm_zone,
                owner_id=current_user.id,
            )
            db.add(project)
            db.flush()
            # Re-check after flush: a concurrent transaction could have created
            # the same zone project between our read and this insert.  If so,
            # expunge the duplicate and use the one that already exists.
            rival = _match_existing_zone_project(db, current_user, key)
            if rival is not None and rival.id != project.id:
                db.expunge(project)
                resolved[key] = {"project": rival, "action": "appended", "name": rival.name}
            else:
                resolved[key] = {"project": project, "action": "created", "name": zone}
    return resolved


def preview_zone_projects(db, zones: List[Optional[str]], current_user) -> Dict[str, Dict]:
    """Read-only preview of what ``resolve_or_create_zone_projects`` WOULD do.

    Returns ``{normalized_zone_key: {"project": Project|None, "action":
    "created"|"appended", "name": first_seen_original_casing}}``. ``project``
    is None for zones that would be newly created. Does NOT mutate the
    database -- the preview must not create projects (T009).
    """
    resolved: Dict[str, Dict] = {}
    for zone in zones:
        if zone is None:
            continue
        key = _normalize_zone_key(zone)
        if key in resolved:
            continue
        existing = _match_existing_zone_project(db, current_user, key)
        if existing is not None:
            resolved[key] = {"project": existing, "action": "appended", "name": existing.name}
        else:
            resolved[key] = {"project": None, "action": "created", "name": zone}
    return resolved