from fastapi import APIRouter, Depends, HTTPException, Query, Response

from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from datetime import datetime
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
from backend.src.services.html_export import (
    build_standalone_html,
    ExportTooLargeError,
    parse_topography_csv,
    decimate_topography,
)
from backend.src.services.grade_coloring import get_grade_color

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)
))))
_FRONTEND_DIR = os.path.join(_REPO_ROOT, "frontend")

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

    from backend.src.services.grade_coloring import get_grade_color

    def _interp_pos(trace, depth):
        if not trace:
            return (0.0, 0.0, 0.0)
        if depth <= trace[0]['depth']:
            p = trace[0]
        elif depth >= trace[-1]['depth']:
            p = trace[-1]
        else:
            p = trace[-1]
            for i in range(1, len(trace)):
                p1, p2 = trace[i - 1], trace[i]
                if p1['depth'] <= depth <= p2['depth']:
                    d1, d2 = p1['depth'], p2['depth']
                    if abs(d2 - d1) < 1e-9:
                        p = p1
                        break
                    t = (depth - d1) / (d2 - d1)
                    return (
                        p1['x'] + t * (p2['x'] - p1['x']),
                        p1['y'] + t * (p2['y'] - p1['y']),
                        p1['z'] + t * (p2['z'] - p1['z'])
                    )
        return (p['x'], p['y'], p['z'])

    traces = []
    assay_segments = []
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

            assays = db.query(AssayInterval).filter(
                AssayInterval.collar_id == c.id,
                AssayInterval.superseded_by.is_(None)
            ).all()
            for a in assays:
                start = _interp_pos(pts, float(a.from_depth))
                end = _interp_pos(pts, float(a.to_depth))
                assay_segments.append({
                    "hole_id": c.hole_id,
                    "start": {"x": start[0], "y": start[1], "z": start[2]},
                    "end": {"x": end[0], "y": end[1], "z": end[2]},
                    "grade_value": float(a.grade_value),
                    "grade_unit": a.grade_unit,
                    "color": get_grade_color(float(a.grade_value), a.grade_unit)
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
        plane_params,
        assay_segments
    )

    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename={project.name.replace(' ', '_')}_section.pdf",
            "Cache-Control": "no-store"
        }
    )


@router.get("/standalone.html")
def export_standalone_html(
    project_id: str,
    include_topography: bool = Query(default=True),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    from backend.src.api.scene import get_project_scene

    project = get_owned_project_or_404(project_id, db, current_user)
    storage = LocalFilesystemStorage()

    # 1. Scene (full rendering data — same shape as the live /scene endpoint)
    scene = get_project_scene(project_id, db, current_user)

    # 2. Collar details keyed by hole_id (full inspector payload for every collar)
    collars = db.query(Collar).filter(
        Collar.project_id == project.id,
        Collar.superseded_by.is_(None)
    ).all()

    collar_details: dict = {}
    for c in collars:
        surveys = db.query(Survey).filter(
            Survey.collar_id == c.id
        ).order_by(Survey.depth).all()
        assays = db.query(AssayInterval).filter(
            AssayInterval.collar_id == c.id,
            AssayInterval.superseded_by.is_(None)
        ).order_by(AssayInterval.from_depth).all()
        lithologies = db.query(LithologyInterval).filter(
            LithologyInterval.collar_id == c.id,
            LithologyInterval.superseded_by.is_(None)
        ).order_by(LithologyInterval.from_depth).all()

        merged: list = []
        for a in assays:
            merged.append({
                "type": "assay",
                "from_depth": float(a.from_depth),
                "to_depth": float(a.to_depth),
                "value": float(a.grade_value),
                "unit": a.grade_unit,
                "below_dl": a.below_detection_limit,
                "qaqc_flag": a.qaqc_flag,
                "color": get_grade_color(a.grade_value, a.grade_unit),
            })
        for l in lithologies:
            merged.append({
                "type": "lithology",
                "from_depth": float(l.from_depth),
                "to_depth": float(l.to_depth),
                "lith_code": l.lith_code,
                "rqd_percent": l.rqd_percent,
                "core_recovery_percent": l.core_recovery_percent,
            })
        merged.sort(key=lambda x: (x["from_depth"], x["to_depth"]))

        collar_details[c.hole_id] = {
            "id": str(c.id),
            "hole_id": c.hole_id,
            "easting": float(c.easting),
            "northing": float(c.northing),
            "elevation": float(c.elevation),
            "utm_zone": c.utm_zone,
            "surveys": [
                {"id": str(s.id), "depth": float(s.depth),
                 "dip": float(s.dip), "azimuth": float(s.azimuth)}
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
                    "color": get_grade_color(a.grade_value, a.grade_unit),
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
                    "core_recovery_percent": l.core_recovery_percent,
                }
                for l in lithologies
            ],
            "merged_intervals": merged,
        }

    # 3. Topography (decimated CSV → [[e, n, el], …])
    topo: dict = {"included": False, "point_count": 0, "points": []}
    topo_raw_count = 0
    notices: list = []
    if include_topography:
        topo_wf = db.query(Wireframe).filter(
            Wireframe.project_id == project.id,
            Wireframe.solid_type == "topography"
        ).first()
        if topo_wf:
            try:
                csv_bytes = storage.load(topo_wf.file_ref)
                raw_points = parse_topography_csv(
                    csv_bytes.decode("utf-8", errors="replace")
                )
                topo_raw_count = len(raw_points)
                decimated = decimate_topography(raw_points)
                topo = {
                    "included": True,
                    "point_count": len(decimated),
                    "points": decimated,
                }
                if topo_raw_count > len(decimated):
                    notices.append(
                        f"Topography decimated from {topo_raw_count:,} "
                        f"to {len(decimated):,} points for export."
                    )
            except Exception:
                notices.append("Topography could not be included (file read error).")

    # 4. Wireframes (geometry pre-baked; topography excluded)
    wireframes_list: list = []
    for w in db.query(Wireframe).filter(
        Wireframe.project_id == project.id,
        Wireframe.solid_type != "topography"
    ).all():
        geom_path = os.path.join(storage.base_dir, f"{w.file_ref}_geom.json")
        if not os.path.exists(geom_path):
            continue
        try:
            with open(geom_path, "r", encoding="utf-8") as fh:
                geom = json.load(fh)
            wireframes_list.append({
                "id": str(w.id),
                "name": w.name,
                "solid_type": w.solid_type,
                "vertices": geom.get("vertices", []),
                "faces": geom.get("faces", []),
            })
        except Exception:
            pass

    # 5. Static viewer assets (must be built before calling this endpoint)
    try:
        with open(os.path.join(_FRONTEND_DIR, "dist", "export_viewer.js"),
                  "r", encoding="utf-8") as fh:
            bundle_js = fh.read()
        with open(os.path.join(_FRONTEND_DIR, "styles", "app.css"),
                  "r", encoding="utf-8") as fh:
            css_text = fh.read()
        with open(os.path.join(_FRONTEND_DIR, "src", "export", "shell.html"),
                  "r", encoding="utf-8") as fh:
            shell_html = fh.read()
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Viewer bundle not built: {exc.filename}. "
                   "Run 'npm run build:export' in the frontend directory."
        )

    # 6. Assemble payload
    payload = {
        "format_version": 1,
        "project": {"name": project.name, "utm_zone": project.utm_zone or ""},
        "scene": scene,
        "collar_details": collar_details,
        "topography": topo,
        "wireframes": wireframes_list,
        "export_meta": {
            "exported_at": datetime.utcnow().isoformat() + "Z",
            "exported_by": current_user.email,
            "notices": notices,
        },
    }

    # 7. Build HTML document
    try:
        html_bytes = build_standalone_html(payload, shell_html, css_text, bundle_js)
    except ExportTooLargeError as exc:
        raise HTTPException(status_code=413, detail=str(exc))

    safe_name = project.name.replace(" ", "_")
    return Response(
        content=html_bytes,
        media_type="text/html",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{safe_name} - 3D Standalone.html"'
            ),
            "Cache-Control": "no-store",
        },
    )
