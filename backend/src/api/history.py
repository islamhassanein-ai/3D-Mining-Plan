import uuid
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional

from backend.src.db.session import get_db
from backend.src.api.auth import get_current_user
from backend.src.models.user import User
from backend.src.models.project import Project
from backend.src.models.import_batch import ImportBatch
from backend.src.models.collar import Collar
from backend.src.models.assay_interval import AssayInterval
from backend.src.models.lithology_interval import LithologyInterval
from backend.src.api.project_access import get_owned_project_or_404

router = APIRouter(prefix="/projects/{project_id}/history", tags=["history"])

@router.get("")
def get_project_history(
  project_id: str,
  entity_id: Optional[str] = Query(None),
  entity_type: Optional[str] = Query(None), # "collar", "assay", "lithology"
  db: Session = Depends(get_db),
  current_user: User = Depends(get_current_user)
):
  """Surfaces import history and allows tracing the superseded_by chain of a record."""
  project = get_owned_project_or_404(project_id, db, current_user)
  
  # Fetch all import batches for this project
  batches = db.query(ImportBatch).filter(ImportBatch.project_id == project.id).order_by(ImportBatch.import_date.desc()).all()

  import_history = []
  for b in batches:
    # created_by is nullable: batches created before this field existed have no
    # recorded importer. Show that honestly rather than attributing the import to
    # whoever happens to be viewing the history right now.
    importing_user_email = b.importing_user.email if b.importing_user else "Unknown (recorded before audit tracking was added)"
    import_history.append({
      "id": str(b.id),
      "source_file": b.source_file,
      "import_date": b.import_date.isoformat() if b.import_date else None,
      "status": b.status,
      "importing_user": importing_user_email
    })
    
  chain = []
  if entity_id and entity_type:
    try:
      ent_uuid = uuid.UUID(entity_id)
    except ValueError:
      raise HTTPException(status_code=400, detail="Invalid entity_id format")
      
    # Determine model class
    model_map = {
      "collar": Collar,
      "assay": AssayInterval,
      "lithology": LithologyInterval
    }
    model_class = model_map.get(entity_type.lower())
    if not model_class:
      raise HTTPException(status_code=400, detail="Invalid entity_type. Choose collar, assay, or lithology")
      
    # Trace the superseded_by chain forward
    curr_uuid = ent_uuid
    visited = set() # Avoid cycles
    while curr_uuid and curr_uuid not in visited:
      visited.add(curr_uuid)
      record = db.query(model_class).filter(model_class.id == curr_uuid).first()
      if not record:
        break
      
      meta = {
        "id": str(record.id),
        "status": "superseded" if record.superseded_by else "active"
      }
      # Include some entity-specific readable text
      if entity_type == "collar":
        meta["label"] = f"Drillhole {record.hole_id}"
      elif entity_type == "assay":
        meta["label"] = f"Assay Interval {record.from_depth}m - {record.to_depth}m ({record.grade_value} {record.grade_unit})"
      elif entity_type == "lithology":
        meta["label"] = f"Lithology Interval {record.from_depth}m - {record.to_depth}m ({record.lith_code})"
        
      chain.append(meta)
      curr_uuid = record.superseded_by
      
  return {
    "project_id": str(project.id),
    "import_batches": import_history,
    "supersession_chain": chain
  }
