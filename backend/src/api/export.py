from fastapi import APIRouter, Depends, HTTPException, Query

from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
import io
import json
import os

from backend.src.db.session import get_db
from backend.src.api.auth import get_current_user
from backend.src.models.user import User
from backend.src.models.project import Project
from backend.src.models.collar import Collar
from backend.src.models.survey import Survey
from backend.src.models.assay_interval import AssayInterval
from backend.src.models.lithology_interval import LithologyInterval
from backend.src.models.wireframe import Wireframe
from backend.src.api.project_access import get_owned_project_or_404
from backend.src.storage.local_filesystem import LocalFilesystemStorage

from backend.src.services.dxf_service import export_wireframes_to_dxf
from backend.src.services.pdf_service import export_section_to_pdf
from backend.src.services.csv_service import (
    export_drillholes_to_csv,
    export_collars_csv,
    export_surveys_csv,
    export_assays_csv,
    export_lithologies_csv
)

router = APIRouter(prefix="/projects/{project_id}/export", tags=["export"])

@router.get("/wireframes.dxf")
def export_dxf(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    project = get_owned_project_or_404(project_id, db, current_user)
    
    wireframes = db.query(Wireframe).filter(
        Wireframe.project_id == project.id,
        Wireframe.solid_type != "topography"
    ).all()
    
    storage = LocalFilesystemStorage()
    wireframes_data = []
    
    for w in wireframes:
        geom_path = os.path.join(storage.base_dir, f"{w.file_ref}_geom.json")
        if os.path.exists(geom_path):
            try:
                with open(geom_path, "r", encoding="utf-8") as f:
                    geom_data = json.load(f)
                    wireframes_data.append({
                        "name": w.name,
                        "vertices": geom_data.get("vertices", []),
                        "faces": geom_data.get("faces", [])
                    })
            except Exception:
                pass
                
    if not wireframes_data:
        raise HTTPException(status_code=400, detail="No valid parsed 3D DXF wireframes found in project to export.")
        
    dxf_bytes = export_wireframes_to_dxf(wireframes_data)
    
    return StreamingResponse(
        io.BytesIO(dxf_bytes),
        media_type="application/dxf",
        headers={"Content-Disposition": f"attachment; filename={project.name.replace(' ', '_')}_wireframes.dxf"}
    )

@router.get("/data.csv")
def export_csv(
    project_id: str,
    entity: str = Query(default=None, description="collars|surveys|assays|lithologies -- omit to get all four bundled as a ZIP"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    project = get_owned_project_or_404(project_id, db, current_user)

    if entity is not None and entity not in ("collars", "surveys", "assays", "lithologies"):
        raise HTTPException(status_code=400, detail="entity must be one of: collars, surveys, assays, lithologies")

    collars = db.query(Collar).filter(Collar.project_id == project.id).all()
    surveys = db.query(Survey).join(Collar).filter(Collar.project_id == project.id).all()
    assays = db.query(AssayInterval).join(Collar).filter(Collar.project_id == project.id, AssayInterval.superseded_by.is_(None)).all()
    lithologies = db.query(LithologyInterval).join(Collar).filter(Collar.project_id == project.id, LithologyInterval.superseded_by.is_(None)).all()
    
    collars_data = [{"hole_id": c.hole_id, "easting": c.easting, "northing": c.northing, "elevation": c.elevation} for c in collars]
    surveys_data = [{"hole_id": s.collar.hole_id, "depth": float(s.depth), "dip": float(s.dip), "azimuth": float(s.azimuth)} for s in surveys]
    assays_data = [
        {
            "hole_id": a.collar.hole_id,
            "from_depth": float(a.from_depth),
            "to_depth": float(a.to_depth),
            "grade_value": float(a.grade_value) if a.grade_value is not None else None,
            "grade_unit": a.grade_unit,
            "below_detection_limit": a.below_detection_limit
        }
        for a in assays
    ]
    
    lithologies_data = []
    for l in lithologies:
        lithologies_data.append({
            "hole_id": l.collar.hole_id,
            "from_depth": float(l.from_depth),
            "to_depth": float(l.to_depth),
            "lithology_code": l.lith_code,
            "rqd": float(l.rqd_percent) if l.rqd_percent is not None else None,
            "recovery": float(l.core_recovery_percent) if l.core_recovery_percent is not None else None
        })
        
    if entity is not None:
        entity_exporters = {
            "collars": (export_collars_csv, (collars_data, project.utm_zone or "36N")),
            "surveys": (export_surveys_csv, (surveys_data,)),
            "assays": (export_assays_csv, (assays_data,)),
            "lithologies": (export_lithologies_csv, (lithologies_data,)),
        }
        exporter, args = entity_exporters[entity]
        csv_bytes = exporter(*args)
        return StreamingResponse(
            io.BytesIO(csv_bytes),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={project.name.replace(' ', '_')}_{entity}.csv"}
        )

    zip_bytes = export_drillholes_to_csv(
        project.name,
        project.utm_zone or "36N",
        collars_data,
        surveys_data,
        assays_data,
        lithologies_data
    )

    return StreamingResponse(
        io.BytesIO(zip_bytes),
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={project.name.replace(' ', '_')}_drillholes.zip"}
    )

@router.get("/section.pdf")
def export_pdf(
    project_id: str,
    plane_type: str = Query(default=None, description="EW, NS, or AZIMUTH -- the active slicing plane type. Omit for a full-project view."),
    offset: float = Query(default=0.0),
    thickness: float = Query(default=20.0),
    azimuth: float = Query(default=0.0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    project = get_owned_project_or_404(project_id, db, current_user)

    from backend.src.services.desurvey import compute_minimum_curvature_trace

    collars = db.query(Collar).filter(Collar.project_id == project.id).all()
    collars_data = [{"hole_id": c.hole_id, "easting": c.easting, "northing": c.northing, "elevation": c.elevation} for c in collars]

    traces = []
    for c in collars:
        surveys = db.query(Survey).filter(Survey.collar_id == c.id).order_by(Survey.depth).all()
        if surveys:
            survey_rows = [{"depth": float(s.depth), "dip": float(s.dip), "azimuth": float(s.azimuth)} for s in surveys]
            pts = compute_minimum_curvature_trace(
                c.easting, c.northing, c.elevation, survey_rows
            )
            traces.append({
                "hole_id": c.hole_id,
                "points": pts
            })

    wireframes = db.query(Wireframe).filter(
        Wireframe.project_id == project.id,
        Wireframe.solid_type != "topography"
    ).all()

    storage = LocalFilesystemStorage()
    wireframe_intersects = []

    for w in wireframes:
        geom_path = os.path.join(storage.base_dir, f"{w.file_ref}_geom.json")
        if os.path.exists(geom_path):
            try:
                with open(geom_path, "r", encoding="utf-8") as f:
                    geom_data = json.load(f)
                    verts = geom_data.get("vertices", [])
                    if len(verts) > 2:
                        wireframe_intersects.append({
                            "name": w.name,
                            "points": verts[:10]
                        })
            except Exception:
                pass

    plane_params = None
    section_name = "Central Cross-Section View (A-A')"
    if plane_type:
        plane_params = {"type": plane_type, "offset": offset, "thickness": thickness, "azimuth": azimuth}
        section_name = f"{plane_type} Slice @ offset={offset:.0f}m, thickness={thickness:.0f}m"
        if plane_type == "AZIMUTH":
            section_name += f", azimuth={azimuth:.0f}°"

    pdf_bytes = export_section_to_pdf(
        project.name,
        section_name,
        collars_data,
        traces,
        wireframe_intersects,
        plane_params
    )

    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={project.name.replace(' ', '_')}_section.pdf"}
    )
