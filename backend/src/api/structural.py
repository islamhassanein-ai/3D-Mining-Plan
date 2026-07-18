from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
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

@router.post("/import", status_code=status.HTTP_201_CREATED)
async def import_structural_readings(
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
    
    count = 0
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
            count += 1
        except ValueError:
            continue
            
    db.commit()
    return {"message": f"Successfully imported {count} structural readings", "count": count}
