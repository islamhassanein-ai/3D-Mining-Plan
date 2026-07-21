import uuid
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from backend.src.db.session import get_db
from backend.src.models.project import Project
from backend.src.api.auth import get_current_user
from backend.src.api.project_access import get_owned_project_or_404
from backend.src.models.user import User
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/projects", tags=["projects"])

class ProjectCreate(BaseModel):
    name: str
    commodity: Optional[str] = None

@router.post("", status_code=status.HTTP_201_CREATED)
def create_project(
    project_in: ProjectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    project = Project(
        id=uuid.uuid4(),
        name=project_in.name,
        commodity=project_in.commodity,
        utm_zone=None,  # Left unset until first committed import
        owner_id=current_user.id
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return {
        "id": str(project.id),
        "name": project.name,
        "utm_zone": project.utm_zone,
        "commodity": project.commodity,
        "created_at": project.created_at.isoformat() if project.created_at else None
    }

class ProjectUpdate(BaseModel):
    utm_zone: Optional[str] = None
    name: Optional[str] = None
    commodity: Optional[str] = None

@router.patch("/{project_id}")
def update_project(
    project_id: str,
    project_in: ProjectUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    project = get_owned_project_or_404(project_id, db, current_user)

    if project_in.utm_zone is not None:
        project.utm_zone = project_in.utm_zone.strip() or None
    if project_in.name is not None:
        project.name = project_in.name.strip() or project.name
    if project_in.commodity is not None:
        project.commodity = project_in.commodity.strip() or None

    db.add(project)
    db.commit()
    db.refresh(project)
    return {
        "id": str(project.id),
        "name": project.name,
        "utm_zone": project.utm_zone,
        "commodity": project.commodity,
        "created_at": project.created_at.isoformat() if project.created_at else None
    }

@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    project = get_owned_project_or_404(project_id, db, current_user)

    from backend.src.models.collar import Collar
    from backend.src.models.survey import Survey
    from backend.src.models.assay_interval import AssayInterval
    from backend.src.models.lithology_interval import LithologyInterval
    from backend.src.models.import_batch import ImportBatch
    from backend.src.models.structural_reading import StructuralReading
    from backend.src.models.qaqc_standard import QaqcStandard
    from backend.src.models.share_link import ShareLink

    collar_ids = db.query(Collar.id).filter(Collar.project_id == project.id)
    # Children reference collar_id, not project_id, so they're deleted via
    # a subquery on this project's collars first.
    db.query(AssayInterval).filter(AssayInterval.collar_id.in_(collar_ids)).delete(synchronize_session=False)
    db.query(LithologyInterval).filter(LithologyInterval.collar_id.in_(collar_ids)).delete(synchronize_session=False)
    db.query(Survey).filter(Survey.collar_id.in_(collar_ids)).delete(synchronize_session=False)
    db.query(Collar).filter(Collar.project_id == project.id).delete(synchronize_session=False)
    db.query(Trench).filter(Trench.project_id == project.id).delete(synchronize_session=False)
    db.query(Wireframe).filter(Wireframe.project_id == project.id).delete(synchronize_session=False)
    db.query(StructuralReading).filter(StructuralReading.project_id == project.id).delete(synchronize_session=False)
    db.query(QaqcStandard).filter(QaqcStandard.project_id == project.id).delete(synchronize_session=False)
    db.query(ShareLink).filter(ShareLink.project_id == project.id).delete(synchronize_session=False)
    # ImportBatch is referenced by Collar/StructuralReading via NOT NULL FKs,
    # so it must be deleted after those, not before.
    db.query(ImportBatch).filter(ImportBatch.project_id == project.id).delete(synchronize_session=False)

    db.delete(project)
    db.commit()
    return None

@router.get("/{project_id}")
def get_project(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    project = get_owned_project_or_404(project_id, db, current_user)
    return {
        "id": str(project.id),
        "name": project.name,
        "utm_zone": project.utm_zone,
        "commodity": project.commodity,
        "created_at": project.created_at.isoformat() if project.created_at else None
    }

from fastapi import UploadFile, File
from backend.src.models.trench import Trench
from backend.src.models.wireframe import Wireframe
from backend.src.storage.local_filesystem import LocalFilesystemStorage
import csv
import io

storage = LocalFilesystemStorage()

@router.post("/{project_id}/topography")
async def upload_topography(
    project_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    project = get_owned_project_or_404(project_id, db, current_user)
    
    content = await file.read()
    file_ref = storage.save(content, f"topo_{uuid.uuid4().hex}_{file.filename}")
    
    # We store topography as a wireframe of solid_type="topography"
    # Delete old topography wireframe if exists
    db.query(Wireframe).filter(
        Wireframe.project_id == project.id,
        Wireframe.solid_type == "topography"
    ).delete()
    
    wireframe = Wireframe(
        id=uuid.uuid4(),
        project_id=project.id,
        name=file.filename,
        solid_type="topography",
        file_ref=file_ref
    )
    db.add(wireframe)
    db.commit()
    db.refresh(wireframe)
    
    return {
        "id": str(wireframe.id),
        "name": wireframe.name,
        "solid_type": wireframe.solid_type,
        "file_ref": wireframe.file_ref
    }

@router.post("/{project_id}/trenches")
async def upload_trenches(
    project_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    project = get_owned_project_or_404(project_id, db, current_user)
    
    content = await file.read()
    text = content.decode("utf-8")
    
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise HTTPException(status_code=400, detail="Empty CSV or missing headers")
        
    reader.fieldnames = [h.strip().lower().replace(" ", "_") for h in reader.fieldnames]
    required = {"trench_id", "easting", "northing"}
    if not required.issubset(set(reader.fieldnames)):
        raise HTTPException(
            status_code=400,
            detail=f"Missing required columns in CSV: {required - set(reader.fieldnames)}"
        )
        
    # Delete old trenches for this project
    db.query(Trench).filter(Trench.project_id == project.id).delete()
    
    count = 0
    for i, row in enumerate(reader, start=1):
        try:
            t_id = row["trench_id"].strip()
            easting = float(row["easting"])
            northing = float(row["northing"])
            elevation = float(row["elevation"]) if row.get("elevation") and row["elevation"].strip() else None
            grade_value = float(row["grade_value"]) if row.get("grade_value") and row["grade_value"].strip() else None
        except ValueError:
            continue

        new_id = uuid.uuid4()
        new_t = Trench(
            id=new_id,
            project_id=project.id,
            trench_id=t_id,
            easting=easting,
            northing=northing,
            elevation=elevation,
            grade_value=grade_value
        )
        db.add(new_t)
        count += 1
        
    db.commit()
    return {"message": f"Successfully processed {count} trenches", "count": count}

@router.post("/{project_id}/wireframes")
async def upload_wireframe(
    project_id: str,
    name: str,
    solid_type: str = "vein_solid",
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    project = get_owned_project_or_404(project_id, db, current_user)
    
    content = await file.read()
    
    # Check if DXF and parse
    is_dxf = file.filename.lower().endswith(".dxf")
    if is_dxf:
        import json
        from backend.src.services.dxf_service import parse_dxf_wireframe
        vertices, faces, errors = parse_dxf_wireframe(content)
        if errors:
            raise HTTPException(status_code=400, detail=f"DXF parse errors: {'; '.join(errors)}")
            
    file_ref = storage.save(content, f"wireframe_{uuid.uuid4().hex}_{file.filename}")
    
    if is_dxf:
        import os
        geom_bytes = json.dumps({"vertices": vertices, "faces": faces}).encode("utf-8")
        with open(os.path.join(storage.base_dir, f"{file_ref}_geom.json"), "wb") as f:
            f.write(geom_bytes)
    
    wireframe = Wireframe(
        id=uuid.uuid4(),
        project_id=project.id,
        name=name,
        solid_type=solid_type,
        file_ref=file_ref
    )
    db.add(wireframe)
    db.commit()
    db.refresh(wireframe)
    
    return {
        "id": str(wireframe.id),
        "name": wireframe.name,
        "solid_type": wireframe.solid_type,
        "file_ref": wireframe.file_ref
    }

@router.post("/{project_id}/trenches/shapefile")
async def upload_trenches_shapefile(
    project_id: str,
    shp_file: UploadFile = File(...),
    dbf_file: UploadFile = File(...),
    shx_file: UploadFile = File(...),
    prj_file: Optional[UploadFile] = File(None),
    confirm_crs: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    project = get_owned_project_or_404(project_id, db, current_user)
    
    shp_bytes = await shp_file.read()
    dbf_bytes = await dbf_file.read()
    shx_bytes = await shx_file.read()
    
    prj_bytes = None
    if prj_file:
        prj_bytes = await prj_file.read()
        
    if not confirm_crs:
        from backend.src.services.shapefile_service import check_shapefile_crs
        proj_zone = project.utm_zone or "36N"
        crs_res = check_shapefile_crs(prj_bytes, proj_zone)
        if not crs_res["valid"]:
            raise HTTPException(status_code=400, detail=crs_res["message"])
            
    from backend.src.services.shapefile_service import parse_trench_shapefile
    rows, errors = parse_trench_shapefile(shp_bytes, dbf_bytes, shx_bytes)
    if errors:
        raise HTTPException(status_code=400, detail=f"Shapefile parse errors: {'; '.join(errors)}")
        
    db.query(Trench).filter(Trench.project_id == project.id).delete()
    
    count = 0
    for r in rows:
        trench = Trench(
            id=uuid.uuid4(),
            project_id=project.id,
            trench_id=r["trench_id"],
            easting=r["easting"],
            northing=r["northing"],
            grade_value=r["grade_value"]
        )
        db.add(trench)
        count += 1
        
    if not project.utm_zone and rows:
        project.utm_zone = "36N"
        
    db.commit()
    return {"message": f"Successfully processed {count} trenches from Shapefile", "count": count}

@router.post("/{project_id}/topography/shapefile")
async def upload_topography_shapefile(
    project_id: str,
    shp_file: UploadFile = File(...),
    dbf_file: UploadFile = File(...),
    shx_file: UploadFile = File(...),
    prj_file: Optional[UploadFile] = File(None),
    confirm_crs: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    project = get_owned_project_or_404(project_id, db, current_user)
    
    shp_bytes = await shp_file.read()
    dbf_bytes = await dbf_file.read()
    shx_bytes = await shx_file.read()
    
    prj_bytes = None
    if prj_file:
        prj_bytes = await prj_file.read()
        
    if not confirm_crs:
        from backend.src.services.shapefile_service import check_shapefile_crs
        proj_zone = project.utm_zone or "36N"
        crs_res = check_shapefile_crs(prj_bytes, proj_zone)
        if not crs_res["valid"]:
            raise HTTPException(status_code=400, detail=crs_res["message"])
            
    from backend.src.services.shapefile_service import parse_topography_shapefile
    points, errors = parse_topography_shapefile(shp_bytes, dbf_bytes, shx_bytes)
    if errors:
        raise HTTPException(status_code=400, detail=f"Shapefile parse errors: {'; '.join(errors)}")
        
    csv_lines = ["easting,northing,elevation"]
    for p in points:
        csv_lines.append(f"{p['easting']},{p['northing']},{p['elevation']}")
    csv_content = "\n".join(csv_lines).encode("utf-8")
    
    file_ref = storage.save(csv_content, f"topo_{uuid.uuid4().hex}_{shp_file.filename}.csv")
    
    db.query(Wireframe).filter(
        Wireframe.project_id == project.id,
        Wireframe.solid_type == "topography"
    ).delete()
    
    wireframe = Wireframe(
        id=uuid.uuid4(),
        project_id=project.id,
        name=shp_file.filename,
        solid_type="topography",
        file_ref=file_ref
    )
    db.add(wireframe)
    
    if not project.utm_zone and points:
        project.utm_zone = "36N"
        
    db.commit()
    db.refresh(wireframe)
    
    return {
        "id": str(wireframe.id),
        "name": wireframe.name,
        "solid_type": wireframe.solid_type,
        "file_ref": wireframe.file_ref
    }
