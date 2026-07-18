import uuid
import json
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional

from backend.src.db.session import get_db
from backend.src.api.auth import get_current_user
from backend.src.models.user import User
from backend.src.models.project import Project
from backend.src.models.import_batch import ImportBatch
from backend.src.models.collar import Collar
from backend.src.models.survey import Survey
from backend.src.models.assay_interval import AssayInterval
from backend.src.models.lithology_interval import LithologyInterval
from backend.src.models.qaqc_standard import QaqcStandard

from backend.src.storage.local_filesystem import LocalFilesystemStorage
from backend.src.services.csv_import import (
    parse_collar_csv,
    parse_survey_csv,
    parse_assay_csv,
    parse_lithology_csv
)
from backend.src.services.import_validation import validate_import_batch
from backend.src.services.crs import detect_utm_zone
from backend.src.services.desurvey import compute_minimum_curvature_trace
from backend.src.api.project_access import get_owned_project_or_404 as get_project_or_404

router = APIRouter(prefix="/projects/{project_id}/imports", tags=["imports"])
storage = LocalFilesystemStorage()

@router.post("", status_code=status.HTTP_201_CREATED)
async def create_import(
    project_id: str,
    collar_file: Optional[UploadFile] = File(None),
    survey_file: Optional[UploadFile] = File(None),
    assay_file: Optional[UploadFile] = File(None),
    lithology_file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    project = get_project_or_404(project_id, db, current_user)
    
    collars, surveys, assays, lithologies = [], [], [], []
    issues = []
    
    # Helper to clean parsing issues
    def add_parse_errors(errors: list, file_type: str):
        for err in errors:
            issues.append({
                "type": "error",
                "rule": "parse_error",
                "message": f"{file_type} CSV parse error on row {err['row']}: {err['error']}",
                "hole_id": err['raw_data'].get('hole_id', '') if isinstance(err['raw_data'], dict) else '',
                "row": err['row']
            })

    # Read and parse files
    source_files = []
    if collar_file:
        content = await collar_file.read()
        collars, c_errs = parse_collar_csv(content)
        add_parse_errors(c_errs, "Collar")
        source_files.append(collar_file.filename)
    if survey_file:
        content = await survey_file.read()
        surveys, s_errs = parse_survey_csv(content)
        add_parse_errors(s_errs, "Survey")
        source_files.append(survey_file.filename)
    if assay_file:
        content = await assay_file.read()
        assays, a_errs = parse_assay_csv(content)
        add_parse_errors(a_errs, "Assay")
        source_files.append(assay_file.filename)
    if lithology_file:
        content = await lithology_file.read()
        lithologies, l_errs = parse_lithology_csv(content)
        add_parse_errors(l_errs, "Lithology")
        source_files.append(lithology_file.filename)

    # 1. Run geological validations
    db_standards = db.query(QaqcStandard).filter(QaqcStandard.project_id == project.id).all()
    qaqc_standards_list = [
        {
            "standard_name": s.standard_name,
            "expected_grade_min": s.expected_grade_min,
            "expected_grade_max": s.expected_grade_max,
            "grade_unit": s.grade_unit
        }
        for s in db_standards
    ]
    validation_res = validate_import_batch(
        collars, surveys, assays, lithologies, project.utm_zone, qaqc_standards_list
    )
    issues.extend(validation_res["issues"])
    
    # Determine overall validity
    has_errors = any(issue["type"] == "error" for issue in issues)
    valid = not has_errors
    
    # 2. Auto-detect UTM zone
    detected_zone = detect_utm_zone(
        [c["easting"] for c in collars],
        [c["northing"] for c in collars],
        project.utm_zone or "36N"
    )
    
    # Create diff/validation payload
    payload = {
        "valid": valid,
        "detected_utm_zone": detected_zone,
        "issues": issues,
        "data": {
            "collars": collars,
            "surveys": surveys,
            "assays": assays,
            "lithologies": lithologies
        },
        "summary": {
            "collar_count": len(collars),
            "survey_count": len(surveys),
            "assay_count": len(assays),
            "lithology_count": len(lithologies),
            "error_count": sum(1 for issue in issues if issue["type"] == "error"),
            "warning_count": sum(1 for issue in issues if issue["type"] == "warning")
        }
    }
    
    # 3. Store batch JSON payload in object storage
    payload_bytes = json.dumps(payload).encode("utf-8")
    source_filename = ", ".join(source_files) if source_files else "empty_batch"
    file_ref = storage.save(payload_bytes, f"{uuid.uuid4().hex}.json")
    
    # Create ImportBatch in database
    import_batch = ImportBatch(
        id=uuid.uuid4(),
        project_id=project.id,
        source_file=file_ref,
        status="pending_review",
        created_by=current_user.id
    )
    db.add(import_batch)
    db.commit()
    db.refresh(import_batch)
    
    return {
        "import_batch_id": str(import_batch.id),
        "status": import_batch.status,
        "validation": payload
    }

@router.get("/{import_batch_id}")
def get_import(
    project_id: str,
    import_batch_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    project = get_project_or_404(project_id, db, current_user)
    try:
        b_uuid = uuid.UUID(import_batch_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Import batch not found")
        
    batch = db.query(ImportBatch).filter(
        ImportBatch.id == b_uuid,
        ImportBatch.project_id == project.id
    ).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Import batch not found")
        
    # Read the payload from storage
    try:
        payload_bytes = storage.load(batch.source_file)
        payload = json.loads(payload_bytes.decode("utf-8"))
    except Exception:
        raise HTTPException(status_code=500, detail="Could not load batch data from storage")
        
    return {
        "import_batch_id": str(batch.id),
        "status": batch.status,
        "validation": payload
    }

@router.post("/{import_batch_id}/commit")
def commit_import(
    project_id: str,
    import_batch_id: str,
    utm_zone_confirm: str = Query(...),  # User must confirm/select the UTM zone
    acknowledge_warnings: bool = Query(False),  # Must be explicitly set when
    # warning-level issues (e.g. overlapping/gapped intervals) are present
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    project = get_project_or_404(project_id, db, current_user)
    try:
        b_uuid = uuid.UUID(import_batch_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Import batch not found")
        
    batch = db.query(ImportBatch).filter(
        ImportBatch.id == b_uuid,
        ImportBatch.project_id == project.id
    ).first()
    
    if not batch:
        raise HTTPException(status_code=404, detail="Import batch not found")
    if batch.status != "pending_review":
        raise HTTPException(status_code=400, detail=f"Cannot commit batch in status: {batch.status}")
        
    # Load parsed data from storage
    try:
        payload_bytes = storage.load(batch.source_file)
        payload = json.loads(payload_bytes.decode("utf-8"))
    except Exception:
        raise HTTPException(status_code=500, detail="Could not load batch data from storage")
        
    # Verify there are no blocking errors
    has_errors = any(issue["type"] == "error" for issue in payload["issues"])
    if has_errors:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Cannot commit import batch with unresolved validation errors"
        )

    # Warning-level issues (e.g. overlapping/gapped intervals) do not block a
    # commit outright, but per data-model.md and contracts/api.md they must be
    # explicitly acknowledged by the client before commit proceeds — silently
    # committing unreviewed overlaps/gaps would defeat the point of flagging them.
    has_warnings = any(issue["type"] == "warning" for issue in payload["issues"])
    if has_warnings and not acknowledge_warnings:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="This batch has unacknowledged warnings (e.g. overlapping or "
                   "gapped intervals). Review them and resubmit with "
                   "acknowledge_warnings=true to commit anyway."
        )

    # Apply UTM zone confirmation to project
    if not project.utm_zone:
        project.utm_zone = utm_zone_confirm
        db.add(project)
        
    # Commit collar data & check replacements
    data = payload["data"]
    
    collar_id_map = {} # hole_id -> new_collar_id
    
    # Process collars
    for c_data in data["collars"]:
        hole_id = c_data["hole_id"]
        
        # Check if there is an existing active collar for this project/hole_id
        old_collar = db.query(Collar).filter(
            Collar.project_id == project.id,
            Collar.hole_id == hole_id,
            Collar.superseded_by.is_(None)
        ).first()
        
        new_collar_id = uuid.uuid4()
        collar_id_map[hole_id] = new_collar_id
        
        if old_collar:
            old_collar.superseded_by = new_collar_id
            db.add(old_collar)
            # Note: old_collar's Assay/Lithology intervals are NOT individually
            # superseded here. AssayInterval.superseded_by and
            # LithologyInterval.superseded_by are foreign keys into their own
            # tables (not into collar), so they must never be set to a Collar id.
            # They stay correctly attributed to old_collar, which is itself now
            # superseded — every read path (see scene.py, collars.py) already
            # filters intervals by their parent Collar.superseded_by IS NULL, so
            # old intervals are excluded transitively without needing their own
            # superseded_by set.

        # Create new collar
        new_collar = Collar(
            id=new_collar_id,
            project_id=project.id,
            hole_id=hole_id,
            easting=c_data["easting"],
            northing=c_data["northing"],
            elevation=c_data["elevation"],
            utm_zone=utm_zone_confirm,
            import_batch_id=batch.id
        )
        db.add(new_collar)
        
    # Process surveys
    for s_data in data["surveys"]:
        h_id = s_data["hole_id"]
        collar_id = collar_id_map.get(h_id)
        if collar_id:
            new_survey = Survey(
                id=uuid.uuid4(),
                collar_id=collar_id,
                depth=s_data["depth"],
                dip=s_data["dip"],
                azimuth=s_data["azimuth"],
                desurvey_method="minimum_curvature"
            )
            db.add(new_survey)
            
    # Process assays
    for a_data in data["assays"]:
        h_id = a_data["hole_id"]
        collar_id = collar_id_map.get(h_id)
        if collar_id:
            new_assay = AssayInterval(
                id=uuid.uuid4(),
                collar_id=collar_id,
                from_depth=a_data["from_depth"],
                to_depth=a_data["to_depth"],
                grade_value=a_data["grade_value"],
                grade_unit=a_data["grade_unit"] or "ppm", # Default if empty
                below_detection_limit=a_data["below_detection_limit"],
                qaqc_flag=a_data.get("qaqc_flag"),
                import_batch_id=batch.id
            )
            db.add(new_assay)
            
    # Process lithologies
    for l_data in data["lithologies"]:
        h_id = l_data["hole_id"]
        collar_id = collar_id_map.get(h_id)
        if collar_id:
            new_lith = LithologyInterval(
                id=uuid.uuid4(),
                collar_id=collar_id,
                from_depth=l_data["from_depth"],
                to_depth=l_data["to_depth"],
                lith_code=l_data["lith_code"],
                rqd_percent=l_data.get("rqd_percent"),
                core_recovery_percent=l_data.get("core_recovery_percent")
            )
            db.add(new_lith)
            
    # Update batch status
    batch.status = "committed"
    db.add(batch)
    db.commit()
    
    return {"message": "Import batch committed successfully", "import_batch_id": str(batch.id)}

@router.post("/{import_batch_id}/reject")
def reject_import(
    project_id: str,
    import_batch_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    project = get_project_or_404(project_id, db, current_user)
    try:
        b_uuid = uuid.UUID(import_batch_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Import batch not found")
        
    batch = db.query(ImportBatch).filter(
        ImportBatch.id == b_uuid,
        ImportBatch.project_id == project.id
    ).first()
    
    if not batch:
        raise HTTPException(status_code=404, detail="Import batch not found")
    if batch.status != "pending_review":
        raise HTTPException(status_code=400, detail=f"Cannot reject batch in status: {batch.status}")
        
    batch.status = "rejected"
    db.add(batch)
    db.commit()
    
    return {"message": "Import batch rejected successfully", "import_batch_id": str(batch.id)}
