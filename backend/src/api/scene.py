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
from backend.src.services.grade_coloring import get_grade_color
from backend.src.storage.local_filesystem import LocalFilesystemStorage
from backend.src.api.project_access import get_project_or_404, enforce_project_ownership

storage = LocalFilesystemStorage()

router = APIRouter(prefix="/projects/{project_id}/scene", tags=["scene"])

def interpolate_trace_position(trace: List[Dict[str, float]], depth: float) -> List[float]:
    """Linearly interpolates 3D position along a pre-computed desurveyed trace."""
    if not trace:
        return [0.0, 0.0, 0.0]
        
    if depth <= trace[0]['depth']:
        return [trace[0]['x'], trace[0]['y'], trace[0]['z']]
        
    if depth >= trace[-1]['depth']:
        return [trace[-1]['x'], trace[-1]['y'], trace[-1]['z']]
        
    for i in range(1, len(trace)):
        p1 = trace[i - 1]
        p2 = trace[i]
        if p1['depth'] <= depth <= p2['depth']:
            d1, d2 = p1['depth'], p2['depth']
            if abs(d2 - d1) < 1e-9:
                return [p1['x'], p1['y'], p1['z']]
            t = (depth - d1) / (d2 - d1)
            return [
                p1['x'] + t * (p2['x'] - p1['x']),
                p1['y'] + t * (p2['y'] - p1['y']),
                p1['z'] + t * (p2['z'] - p1['z'])
            ]
            
    return [trace[-1]['x'], trace[-1]['y'], trace[-1]['z']]

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
        ).all()
        
        scene_assays = []
        for a in assays:
            start_pos = interpolate_trace_position(trace, a.from_depth)
            end_pos = interpolate_trace_position(trace, a.to_depth)
            color = get_grade_color(a.grade_value, a.grade_unit)
            
            scene_assays.append({
                "id": str(a.id),
                "from_depth": a.from_depth,
                "to_depth": a.to_depth,
                "grade_value": float(a.grade_value),
                "grade_unit": a.grade_unit,
                "below_detection_limit": a.below_detection_limit,
                "qaqc_flag": a.qaqc_flag,
                "color": color,
                "start_pos": start_pos,
                "end_pos": end_pos
            })
            
        # Fetch active lithology intervals
        lithologies = db.query(LithologyInterval).filter(
            LithologyInterval.collar_id == collar.id,
            LithologyInterval.superseded_by.is_(None)
        ).all()
        
        scene_lithologies = []
        for l in lithologies:
            start_pos = interpolate_trace_position(trace, l.from_depth)
            end_pos = interpolate_trace_position(trace, l.to_depth)
            
            scene_lithologies.append({
                "id": str(l.id),
                "from_depth": l.from_depth,
                "to_depth": l.to_depth,
                "lith_code": l.lith_code,
                "rqd_percent": l.rqd_percent,
                "core_recovery_percent": l.core_recovery_percent,
                "start_pos": start_pos,
                "end_pos": end_pos
            })
            
        scene_drillholes.append({
            "collar_id": str(collar.id),
            "hole_id": collar.hole_id,
            "easting": collar.easting,
            "northing": collar.northing,
            "elevation": collar.elevation,
            "trace": trace,
            "assays": scene_assays,
            "lithologies": scene_lithologies
        })
        
    # Fetch trenches
    trenches = db.query(Trench).filter(Trench.project_id == project.id).all()
    scene_trenches = [
        {
            "id": str(t.id),
            "trench_id": t.trench_id,
            "easting": t.easting,
            "northing": t.northing,
            "grade_value": float(t.grade_value) if t.grade_value is not None else None
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
