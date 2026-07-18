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
from backend.src.services.grade_coloring import get_grade_color
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

    # Fetch surveys
    surveys = db.query(Survey).filter(
        Survey.collar_id == collar.id
    ).order_by(Survey.depth).all()
    
    # Fetch assays
    assays = db.query(AssayInterval).filter(
        AssayInterval.collar_id == collar.id,
        AssayInterval.superseded_by.is_(None)
    ).order_by(AssayInterval.from_depth).all()
    
    # Fetch lithologies
    lithologies = db.query(LithologyInterval).filter(
        LithologyInterval.collar_id == collar.id,
        LithologyInterval.superseded_by.is_(None)
    ).order_by(LithologyInterval.from_depth).all()
    
    # Generate merged intervals timeline
    merged_intervals = []
    for a in assays:
        merged_intervals.append({
            "type": "assay",
            "from_depth": float(a.from_depth),
            "to_depth": float(a.to_depth),
            "value": float(a.grade_value),
            "unit": a.grade_unit,
            "below_dl": a.below_detection_limit,
            "qaqc_flag": a.qaqc_flag,
            "color": get_grade_color(a.grade_value, a.grade_unit)
        })
        
    for l in lithologies:
        merged_intervals.append({
            "type": "lithology",
            "from_depth": float(l.from_depth),
            "to_depth": float(l.to_depth),
            "lith_code": l.lith_code,
            "rqd_percent": l.rqd_percent,
            "core_recovery_percent": l.core_recovery_percent
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
                "from_depth": float(a.from_depth),
                "to_depth": float(a.to_depth),
                "grade_value": float(a.grade_value),
                "grade_unit": a.grade_unit,
                "below_detection_limit": a.below_detection_limit,
                "qaqc_flag": a.qaqc_flag,
                "color": get_grade_color(a.grade_value, a.grade_unit)
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

@router.get("/{collar_id}/true-thickness")
def get_true_thickness(
    collar_id: str,
    interval_id: str,
    dip_direction: float,
    dip: float,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    import math
    try:
        c_uuid = uuid.UUID(collar_id)
        i_uuid = uuid.UUID(interval_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID format")
        
    collar = db.query(Collar).filter(Collar.id == c_uuid, Collar.superseded_by.is_(None)).first()
    if not collar:
        raise HTTPException(status_code=404, detail="Collar not found")

    _enforce_collar_ownership(collar, db, current_user)

    # Check Assay first
    interval = db.query(AssayInterval).filter(AssayInterval.id == i_uuid).first()
    if not interval:
        # Check Lithology
        interval = db.query(LithologyInterval).filter(LithologyInterval.id == i_uuid).first()
        
    if not interval:
        raise HTTPException(status_code=404, detail="Interval not found")
        
    from_depth = float(interval.from_depth)
    to_depth = float(interval.to_depth)
    apparent_thickness = to_depth - from_depth
    mid_depth = (from_depth + to_depth) / 2.0
    
    # Fetch surveys to interpolate orientation
    surveys = db.query(Survey).filter(Survey.collar_id == collar.id).order_by(Survey.depth).all()
    
    # Defaults if no surveys
    hole_dip = -90.0
    hole_az = 0.0
    
    if len(surveys) == 1:
        hole_dip = float(surveys[0].dip)
        hole_az = float(surveys[0].azimuth)
    elif len(surveys) > 1:
        # Interpolate
        s1 = surveys[0]
        s2 = surveys[-1]
        
        if mid_depth <= s1.depth:
            hole_dip = float(s1.dip)
            hole_az = float(s1.azimuth)
        elif mid_depth >= s2.depth:
            hole_dip = float(s2.dip)
            hole_az = float(s2.azimuth)
        else:
            # Find bounding surveys
            for i in range(1, len(surveys)):
                prev_s = surveys[i-1]
                curr_s = surveys[i]
                if prev_s.depth <= mid_depth <= curr_s.depth:
                    d1, d2 = float(prev_s.depth), float(curr_s.depth)
                    t = (mid_depth - d1) / (d2 - d1) if abs(d2 - d1) > 1e-9 else 0.0
                    
                    # Interpolate Dip
                    hole_dip = float(prev_s.dip) + t * (float(curr_s.dip) - float(prev_s.dip))
                    
                    # Interpolate Azimuth on unit circle
                    a1 = math.radians(float(prev_s.azimuth))
                    a2 = math.radians(float(curr_s.azimuth))
                    x = (1 - t) * math.cos(a1) + t * math.cos(a2)
                    y = (1 - t) * math.sin(a1) + t * math.sin(a2)
                    hole_az = math.degrees(math.atan2(y, x)) % 360.0
                    break
                    
    # Compute true thickness
    hd_rad = math.radians(hole_dip)
    ha_rad = math.radians(hole_az)
    
    dx = math.cos(hd_rad) * math.sin(ha_rad)
    dy = math.cos(hd_rad) * math.cos(ha_rad)
    dz = math.sin(hd_rad)
    
    # Convert vein dip direction and dip to normal vector
    alpha = math.radians(dip_direction)
    delta = math.radians(dip)
    
    # Normal vector of vein plane:
    nx = math.sin(delta) * math.sin(alpha)
    ny = math.sin(delta) * math.cos(alpha)
    nz = -math.cos(delta)
    
    # Dot product
    cos_theta = dx * nx + dy * ny + dz * nz
    true_thickness = apparent_thickness * abs(cos_theta)
    
    return {
        "collar_id": collar_id,
        "interval_id": interval_id,
        "apparent_thickness": apparent_thickness,
        "true_thickness": true_thickness,
        "hole_dip": hole_dip,
        "hole_azimuth": hole_az,
        "vein_dip_direction": dip_direction,
        "vein_dip": dip,
        "intersection_angle_deg": math.degrees(math.acos(min(1.0, max(-1.0, abs(cos_theta)))))
    }

