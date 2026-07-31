import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Dict, Any

from backend.src.db.session import get_db
from backend.src.api.auth import get_current_user
from backend.src.models.user import User
from backend.src.models.project import Project
from backend.src.models.collar import Collar
from backend.src.models.survey import Survey
from backend.src.models.assay_interval import AssayInterval
from backend.src.models.lithology_interval import LithologyInterval
from backend.src.models.trench import Trench
from backend.src.models.wireframe import Wireframe
from backend.src.models.structural_reading import StructuralReading

import os
import json
from backend.src.services.desurvey import compute_minimum_curvature_trace
from backend.src.services.grade_coloring import get_grade_color, is_unsampled
from backend.src.services.downhole_log import (
    compute_total_depth,
    extend_trace_to_depth,
    find_unsampled_gaps,
    interpolate_trace_position,
)
from backend.src.storage.local_filesystem import LocalFilesystemStorage
from backend.src.api.project_access import get_project_or_404, enforce_project_ownership

storage = LocalFilesystemStorage()

router = APIRouter(prefix="/projects/{project_id}/scene", tags=["scene"])

# interpolate_trace_position moved to services/downhole_log.py and re-exported
# here so existing importers (and tests) keep working.
__all__ = ["router", "interpolate_trace_position", "get_project_scene"]


@router.get("")
def get_project_scene(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    project = get_project_or_404(project_id, db)
    # No-op when current_user is None (the Share Link viewer reuse path in
    # share_links.py, where authorization already happened via the token).
    enforce_project_ownership(project, current_user)
    
    # Fetch active collars
    collars = db.query(Collar).filter(
        Collar.project_id == project.id,
        Collar.superseded_by.is_(None)
    ).all()
    
    scene_drillholes = []
    
    for collar in collars:
        # Fetch surveys
        surveys = db.query(Survey).filter(
            Survey.collar_id == collar.id
        ).order_by(Survey.depth).all()
        
        surveys_list = [
            {"depth": s.depth, "dip": s.dip, "azimuth": s.azimuth}
            for s in surveys
        ]
        
        # Fallback: if no surveys exist, assume straight vertical downward hole
        if not surveys_list:
            surveys_list = [
                {"depth": 0.0, "dip": -90.0, "azimuth": 0.0},
                {"depth": 1000.0, "dip": -90.0, "azimuth": 0.0}
            ]
            
        # Compute trace points
        trace = compute_minimum_curvature_trace(
            collar.easting, collar.northing, collar.elevation, surveys_list
        )

        # Fetch active assay intervals
        assays = db.query(AssayInterval).filter(
            AssayInterval.collar_id == collar.id,
            AssayInterval.superseded_by.is_(None)
        ).order_by(AssayInterval.from_depth).all()

        # Fetch active lithology intervals
        lithologies = db.query(LithologyInterval).filter(
            LithologyInterval.collar_id == collar.id,
            LithologyInterval.superseded_by.is_(None)
        ).order_by(LithologyInterval.from_depth).all()

        # End-of-hole depth drives both the trace extension and the unsampled
        # gap list. Surveys frequently stop short of the deepest logged
        # interval; without extending, every interval past the last station
        # would clamp onto the same coordinate.
        interval_depths = [float(a.to_depth) for a in assays]
        interval_depths += [float(l.to_depth) for l in lithologies]
        total_depth = compute_total_depth(trace, interval_depths)
        trace = extend_trace_to_depth(trace, total_depth)

        scene_assays = []
        for a in assays:
            # from_depth/to_depth are absolute distances from the collar
            # (0.0 m), so an interval logged at 37 m - 38 m lands 37 m down the
            # desurveyed curve regardless of how much of the hole above it was
            # left unsampled.
            start_pos = interpolate_trace_position(trace, float(a.from_depth))
            end_pos = interpolate_trace_position(trace, float(a.to_depth))
            unsampled = is_unsampled(a.grade_value, a.sample_id)

            scene_assays.append({
                "id": str(a.id),
                "sample_id": a.sample_id,
                "from_depth": float(a.from_depth),
                "to_depth": float(a.to_depth),
                "grade_value": None if unsampled else float(a.grade_value),
                "grade_unit": a.grade_unit,
                "unsampled": unsampled,
                "below_detection_limit": a.below_detection_limit,
                "qaqc_flag": a.qaqc_flag,
                "color": get_grade_color(a.grade_value, a.grade_unit, a.sample_id),
                "start_pos": start_pos,
                "end_pos": end_pos
            })

        scene_lithologies = []
        for l in lithologies:
            start_pos = interpolate_trace_position(trace, float(l.from_depth))
            end_pos = interpolate_trace_position(trace, float(l.to_depth))

            scene_lithologies.append({
                "id": str(l.id),
                "from_depth": float(l.from_depth),
                "to_depth": float(l.to_depth),
                "lith_code": l.lith_code,
                "rqd_percent": l.rqd_percent,
                "core_recovery_percent": l.core_recovery_percent,
                "start_pos": start_pos,
                "end_pos": end_pos
            })

        # Depth ranges with no assay coverage. The 3D viewer renders only the
        # bare trace line through these -- no interval tube -- while the
        # inspector lists them as explicit "No Sample" rows.
        unsampled_gaps = [
            {
                "from_depth": g_from,
                "to_depth": g_to,
                "start_pos": interpolate_trace_position(trace, g_from),
                "end_pos": interpolate_trace_position(trace, g_to),
            }
            for g_from, g_to in find_unsampled_gaps(
                [(float(a.from_depth), float(a.to_depth)) for a in assays],
                total_depth,
            )
        ]

        scene_drillholes.append({
            "collar_id": str(collar.id),
            "hole_id": collar.hole_id,
            "easting": collar.easting,
            "northing": collar.northing,
            "elevation": collar.elevation,
            "hole_type": collar.hole_type,
            "hole_status": collar.hole_status or "drilled",
            "total_depth": total_depth,
            "trace": trace,
            "assays": scene_assays,
            "lithologies": scene_lithologies,
            "unsampled_gaps": unsampled_gaps,
        })
        
    # Fetch trenches -- only active (non-superseded) rows, ordered so the
    # frontend can reconstruct polyline order. superseded_by points at the
    # replacement anchor (point_order=0) row; reads must filter it out so a
    # re-import of the combined CSV doesn't render both the old and new
    # overlapping polylines.
    trenches = db.query(Trench).filter(
        Trench.project_id == project.id,
        Trench.superseded_by.is_(None)
    ).order_by(Trench.trench_id, Trench.point_order).all()
    scene_trenches = [
        {
            "id": str(t.id),
            "trench_id": t.trench_id,
            "easting": t.easting,
            "northing": t.northing,
            "elevation": t.elevation,
            "grade_value": float(t.grade_value) if t.grade_value is not None else None,
            "point_order": t.point_order,
            "hole_type": t.hole_type,
            "dip": t.dip,
            "azimuth": t.azimuth,
            "sample_id": t.sample_id,
            "from_depth": t.from_depth,
            "to_depth": t.to_depth,
        }
        for t in trenches
    ]
    
    # Fetch wireframes
    wireframes = db.query(Wireframe).filter(Wireframe.project_id == project.id).all()
    scene_wireframes = []
    for w in wireframes:
        item = {
            "id": str(w.id),
            "name": w.name,
            "solid_type": w.solid_type,
            "file_ref": w.file_ref
        }
        # Check if companion geom JSON exists
        geom_filename = f"{w.file_ref}_geom.json"
        geom_path = os.path.join(storage.base_dir, geom_filename)
        if os.path.exists(geom_path):
            try:
                with open(geom_path, "r", encoding="utf-8") as f:
                    geom_data = json.load(f)
                    item["vertices"] = geom_data.get("vertices", [])
                    item["faces"] = geom_data.get("faces", [])
            except Exception as e:
                print(f"Error loading companion geometry for {w.name}: {e}")
        scene_wireframes.append(item)
    
    # We will include project topography placeholder reference if exists (Phase 0 supplementary data)
    # Check if there is an active topography file ref
    topography_ref = None
    # (Topography info will be queried from wireframe or project variables later if needed,
    # but for now we look for a wireframe with solid_type='topography' or similar)
    topo_wireframe = db.query(Wireframe).filter(
        Wireframe.project_id == project.id,
        Wireframe.solid_type == "topography"
    ).first()
    if topo_wireframe:
        topography_ref = topo_wireframe.file_ref
        
    # Fetch structural readings
    structural_readings = db.query(StructuralReading).filter(
        StructuralReading.project_id == project.id,
        StructuralReading.superseded_by.is_(None)
    ).all()
    scene_structural = [
        {
            "id": str(s.id),
            "reading_type": s.reading_type,
            "easting": s.easting,
            "northing": s.northing,
            "elevation": s.elevation,
            "dip": s.dip,
            "strike": s.strike
        }
        for s in structural_readings
    ]
        
    return {
        "project_id": str(project.id),
        "name": project.name,
        "utm_zone": project.utm_zone,
        "drillholes": scene_drillholes,
        "trenches": scene_trenches,
        "wireframes": scene_wireframes,
        "topography_ref": topography_ref,
        "structural_readings": scene_structural
    }
