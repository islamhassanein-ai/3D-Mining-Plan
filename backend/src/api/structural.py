from fastapi import APIRouter, Depends, HTTPException, Query, status, UploadFile, File
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import List, Optional
import uuid
import csv
import io

from backend.src.db.session import get_db
from backend.src.api.auth import get_current_user
from backend.src.models.user import User
from backend.src.models.project import Project
from backend.src.models.structural_reading import StructuralReading
from backend.src.models.import_batch import ImportBatch
from backend.src.api.project_access import get_owned_project_or_404

router = APIRouter(prefix="/projects/{project_id}/structural", tags=["structural"])

class StructuralReadingBase(BaseModel):
    reading_type: str = Field(..., description="e.g., fault_trace, dip_strike")
    easting: float
    northing: float
    elevation: float
    dip: Optional[float] = None
    strike: Optional[float] = None

class StructuralReadingCreate(StructuralReadingBase):
    pass

class StructuralReadingResponse(StructuralReadingBase):
    id: str
    project_id: str
    import_batch_id: str

@router.get("", response_model=List[StructuralReadingResponse])
def list_structural_readings(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    project = get_owned_project_or_404(project_id, db, current_user)
    readings = db.query(StructuralReading).filter(
        StructuralReading.project_id == project.id,
        StructuralReading.superseded_by.is_(None)
    ).all()
    
    return [
        StructuralReadingResponse(
            id=str(r.id),
            project_id=str(r.project_id),
            reading_type=r.reading_type,
            easting=r.easting,
            northing=r.northing,
            elevation=r.elevation,
            dip=r.dip,
            strike=r.strike,
            import_batch_id=str(r.import_batch_id)
        )
        for r in readings
    ]

@router.post("", response_model=StructuralReadingResponse, status_code=status.HTTP_201_CREATED)
def create_structural_reading(
    project_id: str,
    reading_in: StructuralReadingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    project = get_owned_project_or_404(project_id, db, current_user)
    
    # Validate dip/strike requirement for dip_strike reading_type
    if reading_in.reading_type == "dip_strike":
        if reading_in.dip is None or reading_in.strike is None:
            raise HTTPException(
                status_code=400,
                detail="Dip and strike are required when reading_type is 'dip_strike'."
            )

    # Validate dip/strike ranges if provided
    if reading_in.dip is not None and not (0 <= reading_in.dip <= 90):
        raise HTTPException(status_code=400, detail="Dip must be between 0 and 90 degrees.")
    if reading_in.strike is not None and not (0 <= reading_in.strike <= 360):
        raise HTTPException(status_code=400, detail="Strike must be between 0 and 360 degrees.")
        
    batch = ImportBatch(
        id=uuid.uuid4(),
        project_id=project.id,
        source_file="manual_entry",
        status="committed",
        created_by=current_user.id
    )
    db.add(batch)
    
    reading = StructuralReading(
        id=uuid.uuid4(),
        project_id=project.id,
        reading_type=reading_in.reading_type,
        easting=reading_in.easting,
        northing=reading_in.northing,
        elevation=reading_in.elevation,
        dip=reading_in.dip,
        strike=reading_in.strike,
        import_batch_id=batch.id
    )
    db.add(reading)
    db.commit()
    db.refresh(reading)
    
    return StructuralReadingResponse(
        id=str(reading.id),
        project_id=str(reading.project_id),
        reading_type=reading.reading_type,
        easting=reading.easting,
        northing=reading.northing,
        elevation=reading.elevation,
        dip=reading.dip,
        strike=reading.strike,
        import_batch_id=str(reading.import_batch_id)
    )

@router.delete("/{reading_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_structural_reading(
    project_id: str,
    reading_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retires one reading.

    This is a soft delete: the row is marked superseded rather than removed, so
    the import batch that produced it still explains what was loaded and when.
    Every read path already filters `superseded_by IS NULL`, so a retired
    reading leaves the scene and the planner immediately.

    superseded_by is a self-FK and needs a target row. A reading that is
    retired outright has no replacement, so it points at itself -- the
    "superseded" test is `IS NOT NULL`, which a self-reference satisfies, and
    the history walker stops on a record whose successor is itself.
    """
    project = get_owned_project_or_404(project_id, db, current_user)

    try:
        reading_uuid = uuid.UUID(reading_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Structural reading not found")

    reading = db.query(StructuralReading).filter(
        StructuralReading.id == reading_uuid,
        StructuralReading.project_id == project.id,
        StructuralReading.superseded_by.is_(None)
    ).first()

    if not reading:
        raise HTTPException(status_code=404, detail="Structural reading not found")

    reading.superseded_by = reading.id
    db.add(reading)
    db.commit()
    return None


@router.delete("", status_code=status.HTTP_200_OK)
def delete_all_structural_readings(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retires every active reading in the project.

    The escape hatch for a project that has accumulated duplicates from
    repeated CSV imports: clear the slate, then import the corrected file once.
    """
    project = get_owned_project_or_404(project_id, db, current_user)
    count = _supersede_active_readings(db, project.id)
    db.commit()
    return {"message": f"Removed {count} structural readings", "count": count}


def _supersede_active_readings(db, project_id, replacement_id=None):
    """Marks all active readings in the project superseded. Returns the count.

    `replacement_id` records what replaced them (a replace-mode import points
    the old rows at the first new one, preserving the lineage the history panel
    walks). With no replacement, each row points at itself -- see
    delete_structural_reading for why.

    Uses per-row assignment rather than a bulk Query.update() because the
    self-referencing case needs each row's own id.
    """
    active = db.query(StructuralReading).filter(
        StructuralReading.project_id == project_id,
        StructuralReading.superseded_by.is_(None)
    ).all()
    for row in active:
        row.superseded_by = replacement_id if replacement_id is not None else row.id
        db.add(row)
    return len(active)


@router.post("/import", status_code=status.HTTP_201_CREATED)
async def import_structural_readings(
    project_id: str,
    file: UploadFile = File(...),
    mode: str = Query(
        "append",
        pattern="^(append|replace)$",
        description="'append' adds to the existing readings; 'replace' retires "
                    "every current reading first, so a corrected CSV does not "
                    "leave the old rows behind as duplicates."
    ),
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
    required = {"reading_type", "easting", "northing", "elevation"}
    if not required.issubset(set(reader.fieldnames)):
        raise HTTPException(
            status_code=400,
            detail=f"Missing required columns in CSV: {required - set(reader.fieldnames)}"
        )
        
    batch = ImportBatch(
        id=uuid.uuid4(),
        project_id=project.id,
        source_file=file.filename,
        status="committed",
        created_by=current_user.id
    )
    db.add(batch)

    # Replace mode: snapshot the rows to retire BEFORE inserting the new ones.
    # The "active" filter would otherwise also match the rows this import is
    # about to add, and the import would supersede its own output.
    old_rows = []
    if mode == "replace":
        old_rows = db.query(StructuralReading).filter(
            StructuralReading.project_id == project.id,
            StructuralReading.superseded_by.is_(None)
        ).all()

    count = 0
    first_new_id = None
    for row in reader:
        try:
            reading_type = row["reading_type"].strip()
            easting = float(row["easting"])
            northing = float(row["northing"])
            elevation = float(row["elevation"])
            
            dip = float(row["dip"]) if row.get("dip") and row["dip"].strip() else None
            strike = float(row["strike"]) if row.get("strike") and row["strike"].strip() else None
            
            if reading_type == "dip_strike":
                if dip is None or strike is None:
                    continue
            
            if dip is not None and not (0 <= dip <= 90):
                continue
            if strike is not None and not (0 <= strike <= 360):
                continue
                
            reading = StructuralReading(
                id=uuid.uuid4(),
                project_id=project.id,
                reading_type=reading_type,
                easting=easting,
                northing=northing,
                elevation=elevation,
                dip=dip,
                strike=strike,
                import_batch_id=batch.id
            )
            db.add(reading)
            if first_new_id is None:
                first_new_id = reading.id
            count += 1
        except ValueError:
            continue

    replaced = 0
    if mode == "replace":
        if count == 0:
            # Every row was rejected. Retiring the existing readings here would
            # leave the project with no structural data at all off the back of
            # a file that turned out to be unusable -- refuse instead.
            db.rollback()
            raise HTTPException(
                status_code=400,
                detail="No valid readings in the CSV, so nothing was replaced. "
                       "The existing readings were left untouched."
            )
        # Flush first so the new rows exist and the superseded_by FK on the old
        # rows has something to point at.
        db.flush()
        for old in old_rows:
            old.superseded_by = first_new_id
            db.add(old)
        replaced = len(old_rows)

    db.commit()

    if mode == "replace":
        message = f"Imported {count} structural readings, replacing {replaced}"
    else:
        message = f"Successfully imported {count} structural readings"
    return {"message": message, "count": count, "replaced": replaced}
