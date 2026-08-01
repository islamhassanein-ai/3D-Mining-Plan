import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Dict, Any

from backend.src.db.session import get_db
from backend.src.api.auth import get_current_user
from backend.src.models.user import User
from backend.src.models.collar import Collar
from backend.src.models.survey import Survey
from backend.src.models.assay_interval import AssayInterval
from backend.src.models.lithology_interval import LithologyInterval
from backend.src.models.project import Project
from backend.src.services.grade_coloring import (
    get_grade_color,
    is_unsampled,
    UNSAMPLED_COLOR,
    UNSAMPLED_LABEL,
)
from backend.src.services.downhole_log import compute_total_depth, find_unsampled_gaps
from backend.src.api.project_access import enforce_project_ownership

router = APIRouter(prefix="/collars", tags=["collars"])


def _enforce_collar_ownership(collar: Collar, db: Session, current_user) -> None:
    """No-op when current_user is None (the Share Link viewer reuse path in
    share_links.py, which has already scoped the collar to the token's own
    project_id before calling this)."""
    if current_user is None:
        return
    project = db.query(Project).filter(Project.id == collar.project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Drillhole not found")
    try:
        enforce_project_ownership(project, current_user)
    except HTTPException:
        raise HTTPException(status_code=404, detail="Drillhole not found")

def load_collar_records(collar: Collar, db: Session):
    """Fetch the active surveys / assays / lithologies for one collar."""
    surveys = db.query(Survey).filter(
        Survey.collar_id == collar.id
    ).order_by(Survey.depth).all()

    assays = db.query(AssayInterval).filter(
        AssayInterval.collar_id == collar.id,
        AssayInterval.superseded_by.is_(None)
    ).order_by(AssayInterval.from_depth).all()

    lithologies = db.query(LithologyInterval).filter(
        LithologyInterval.collar_id == collar.id,
        LithologyInterval.superseded_by.is_(None)
    ).order_by(LithologyInterval.from_depth).all()

    return surveys, assays, lithologies


def build_collar_detail_payload(collar: Collar, surveys, assays, lithologies) -> Dict[str, Any]:
    """The inspector payload for one drillhole.

    Shared by the live ``GET /collars/{id}`` endpoint and the standalone HTML
    export, so the offline viewer's downhole log is identical to the live
    one -- including the explicit unsampled rows.
    """
    # End of hole: the deepest of the surveys and any logged interval, so the
    # log below covers the whole trajectory rather than stopping at the last
    # sample.
    survey_depths = [float(s.depth) for s in surveys]
    total_depth = compute_total_depth(
        [{"depth": max(survey_depths)}] if survey_depths else [],
        [float(a.to_depth) for a in assays] + [float(l.to_depth) for l in lithologies],
    )

    # Generate merged intervals timeline
    merged_intervals = []
    for a in assays:
        unsampled = is_unsampled(a.grade_value, a.sample_id)
        merged_intervals.append({
            "type": "assay",
            "interval_id": str(a.id),
            "sample_id": a.sample_id,
            "from_depth": float(a.from_depth),
            "to_depth": float(a.to_depth),
            "value": None if unsampled else float(a.grade_value),
            "unit": a.grade_unit,
            "unsampled": unsampled,
            "below_dl": a.below_detection_limit,
            "qaqc_flag": a.qaqc_flag,
            "color": get_grade_color(a.grade_value, a.grade_unit, a.sample_id)
        })

    for l in lithologies:
        merged_intervals.append({
            "type": "lithology",
            "interval_id": str(l.id),
            "from_depth": float(l.from_depth),
            "to_depth": float(l.to_depth),
            "lith_code": l.lith_code,
            "rqd_percent": l.rqd_percent,
            "core_recovery_percent": l.core_recovery_percent
        })

    # Explicit rows for depth ranges no assay covers, so the panel reads as an
    # unbroken 0.0 m -> total_depth record. A hole whose first sample starts at
    # 37 m now shows a "No Sample" row for 0.00 - 37.00 rather than silently
    # beginning at 37.
    for g_from, g_to in find_unsampled_gaps(
        [(float(a.from_depth), float(a.to_depth)) for a in assays],
        total_depth,
    ):
        merged_intervals.append({
            "type": "unsampled",
            "interval_id": None,
            "from_depth": g_from,
            "to_depth": g_to,
            "value": None,
            "unit": None,
            "unsampled": True,
            "label": UNSAMPLED_LABEL,
            "color": UNSAMPLED_COLOR,
        })

    # Sort merged intervals by from_depth, then type (assay first, then lithology)
    merged_intervals.sort(key=lambda x: (x["from_depth"], x["to_depth"]))

    return {
        "id": str(collar.id),
        "hole_id": collar.hole_id,
        "easting": float(collar.easting),
        "northing": float(collar.northing),
        "elevation": float(collar.elevation),
        "utm_zone": collar.utm_zone,
        "hole_type": collar.hole_type,
        "hole_status": collar.hole_status or "drilled",
        "total_depth": total_depth,
        "surveys": [
            {
                "id": str(s.id),
                "depth": float(s.depth),
                "dip": float(s.dip),
                "azimuth": float(s.azimuth)
            }
            for s in surveys
        ],
        "assays": [
            {
                "id": str(a.id),
                "sample_id": a.sample_id,
                "from_depth": float(a.from_depth),
                "to_depth": float(a.to_depth),
                "grade_value": (
                    None if is_unsampled(a.grade_value, a.sample_id)
                    else float(a.grade_value)
                ),
                "grade_unit": a.grade_unit,
                "unsampled": is_unsampled(a.grade_value, a.sample_id),
                "below_detection_limit": a.below_detection_limit,
                "qaqc_flag": a.qaqc_flag,
                "color": get_grade_color(a.grade_value, a.grade_unit, a.sample_id)
            }
            for a in assays
        ],
        "lithologies": [
            {
                "id": str(l.id),
                "from_depth": float(l.from_depth),
                "to_depth": float(l.to_depth),
                "lith_code": l.lith_code,
                "rqd_percent": l.rqd_percent,
                "core_recovery_percent": l.core_recovery_percent
            }
            for l in lithologies
        ],
        "merged_intervals": merged_intervals
    }


@router.get("/{collar_id}")
def get_collar_details(
    collar_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        c_uuid = uuid.UUID(collar_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Drillhole not found")

    collar = db.query(Collar).filter(
        Collar.id == c_uuid,
        Collar.superseded_by.is_(None)
    ).first()

    if not collar:
        raise HTTPException(status_code=404, detail="Drillhole not found")

    _enforce_collar_ownership(collar, db, current_user)

    surveys, assays, lithologies = load_collar_records(collar, db)
    return build_collar_detail_payload(collar, surveys, assays, lithologies)
