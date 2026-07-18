from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import List
import uuid

from backend.src.db.session import get_db
from backend.src.api.auth import get_current_user
from backend.src.models.user import User
from backend.src.models.project import Project
from backend.src.models.qaqc_standard import QaqcStandard
from backend.src.api.project_access import get_owned_project_or_404

router = APIRouter(prefix="/projects/{project_id}/qaqc", tags=["qaqc"])

class QaqcStandardBase(BaseModel):
    standard_name: str
    expected_grade_min: float
    expected_grade_max: float
    grade_unit: str

class QaqcStandardCreate(QaqcStandardBase):
    pass

class QaqcStandardResponse(QaqcStandardBase):
    id: str
    project_id: str

@router.get("", response_model=List[QaqcStandardResponse])
def list_qaqc_standards(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    project = get_owned_project_or_404(project_id, db, current_user)
    standards = db.query(QaqcStandard).filter(QaqcStandard.project_id == project.id).all()
    
    return [
        QaqcStandardResponse(
            id=str(s.id),
            project_id=str(s.project_id),
            standard_name=s.standard_name,
            expected_grade_min=s.expected_grade_min,
            expected_grade_max=s.expected_grade_max,
            grade_unit=s.grade_unit
        )
        for s in standards
    ]

@router.post("", response_model=QaqcStandardResponse, status_code=status.HTTP_201_CREATED)
def create_qaqc_standard(
    project_id: str,
    standard_in: QaqcStandardCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    project = get_owned_project_or_404(project_id, db, current_user)
    
    existing = db.query(QaqcStandard).filter(
        QaqcStandard.project_id == project.id,
        QaqcStandard.standard_name == standard_in.standard_name
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Standard name already exists in this project.")
        
    standard = QaqcStandard(
        id=uuid.uuid4(),
        project_id=project.id,
        standard_name=standard_in.standard_name,
        expected_grade_min=standard_in.expected_grade_min,
        expected_grade_max=standard_in.expected_grade_max,
        grade_unit=standard_in.grade_unit
    )
    db.add(standard)
    db.commit()
    db.refresh(standard)
    
    return QaqcStandardResponse(
        id=str(standard.id),
        project_id=str(standard.project_id),
        standard_name=standard.standard_name,
        expected_grade_min=standard.expected_grade_min,
        expected_grade_max=standard.expected_grade_max,
        grade_unit=standard.grade_unit
    )
