"""Routing for the combined Master Reference CSV.

Splits the parsed rows from ``parse_combined_csv`` into the three storage
buckets the rest of the import pipeline consumes:

* ``collars``       -- one per DD/RC row, carrying ``hole_type``.
* ``surveys``       -- one per DD/RC row that has an inline survey, at
  ``depth == total_length`` (NOT 0). ``compute_minimum_curvature_trace`` at
  ``backend/src/services/desurvey.py:79`` auto-prepends a virtual station at
  depth 0 with the same orientation, producing a correct two-station trace; a
  single station at depth 0 would yield a one-point trace and an invisible hole.
* ``trench_points`` -- two horizontal points per TR/CH/FC row (``dz = 0``).

CRITICAL geological constraint: Dip/Azimuth on TR/CH/FC is the local ground
slope AT THE START POINT ONLY, not the trench trajectory. We do NOT call
``compute_minimum_curvature_trace`` for trenches -- it would apply dip along the
full length and put ARTR001 (dip +16, length 145) ~40 m in the air. Generated
trench points stay flat at collar elevation; true per-point Z arrives later
from the sampling sheet.
"""
import math
import uuid
from typing import Dict, List, Optional, Tuple

# Hole types that store as Collar (+ optional inline Survey).
_COLLAR_TYPES = {"DD", "RC"}
# Hole types that store as Trench multi-point polylines.
_TRENCH_TYPES = {"TR", "CH", "FC"}


def route_combined_rows(rows: List[Dict]) -> Dict[str, List[Dict]]:
    """Route parsed combined-CSV rows into collars, surveys, and trench points.

    Returns ``{"collars": [...], "surveys": [...], "trench_points": [...]}``.

    Each collar dict carries ``hole_type`` and ``zone`` (the caller resolves
    those to projects later). Each trench point carries ``trench_id``,
    ``point_order`` (0 = anchor/start, 1 = far end), ``hole_type``, ``zone``,
    and ``dip``/``azimuth`` on the point_order=0 row only (start-point slope
    metadata). ``grade_value`` is always ``None`` -- the combined CSV carries
    no grade column.
    """
    collars: List[Dict] = []
    surveys: List[Dict] = []
    trench_points: List[Dict] = []

    for r in rows:
        hole_type = r["hole_type"]
        hole_id = r["hole_id"]
        zone = r.get("zone")
        inline = r.get("inline_survey")

        if hole_type in _COLLAR_TYPES:
            collar = {
                "hole_id": hole_id,
                "easting": r["easting"],
                "northing": r["northing"],
                "elevation": r["elevation"],
                "utm_zone": None,  # resolved per-project at commit
                "hole_type": hole_type,
                "zone": zone,
            }
            collars.append(collar)

            if inline is not None:
                # One station at depth == total_length. The desurvey routine
                # auto-prepends a virtual depth=0 station with the same dip/
                # azimuth, producing a 2-point trace. A station at depth 0
                # alone yields a one-point trace and an invisible drillhole.
                surveys.append({
                    "hole_id": hole_id,
                    "depth": inline["total_length"],
                    "dip": inline["dip"],
                    "azimuth": inline["azimuth"],
                })

        elif hole_type in _TRENCH_TYPES:
            # Two-point, HORIZONTAL polyline. dz = 0 -- the trench follows
            # undulating terrain but with only a start coordinate we cannot
            # extrapolate Z; dip/azimuth are stored as start-point metadata
            # only. sin/cos assignment matches get_direction_cosine at
            # desurvey.py:102-105 (azimuth clockwise from North -> easting
            # takes sin, northing takes cos).
            x, y, z = r["easting"], r["northing"], r["elevation"]
            if inline is not None:
                L = inline["total_length"]
                az_rad = math.radians(inline["azimuth"])
                far_e = x + L * math.sin(az_rad)
                far_n = y + L * math.cos(az_rad)
                # far z == z (dz = 0)
                dip = inline["dip"]
                azimuth = inline["azimuth"]
            else:
                # A TR/CH/FC row with no inline survey: degenerate to a single
                # point duplicated so the polyline still has a 2-point shape
                # (zero length). The caller may treat length 0 specially.
                far_e, far_n = x, y
                dip = None
                azimuth = None

            trench_points.append({
                "trench_id": hole_id,
                "easting": x,
                "northing": y,
                "elevation": z,
                "point_order": 0,
                "hole_type": hole_type,
                "zone": zone,
                "dip": dip,
                "azimuth": azimuth,
                "grade_value": None,
            })
            trench_points.append({
                "trench_id": hole_id,
                "easting": far_e,
                "northing": far_n,
                "elevation": z,  # unchanged, dz = 0
                "point_order": 1,
                "hole_type": hole_type,
                "zone": zone,
                "dip": None,
                "azimuth": None,
                "grade_value": None,
            })

        # Any other hole_type is rejected upstream by parse_combined_csv; if it
        # somehow reaches here we silently skip rather than crash, so a bad row
        # never corrupts trench geometry.

    return {
        "collars": collars,
        "surveys": surveys,
        "trench_points": trench_points,
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
            db.flush()  # get an id without a full commit, so callers can FK it
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