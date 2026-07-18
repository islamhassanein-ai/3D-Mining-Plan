import uuid
from fastapi import Path, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from backend.src.db.session import get_db
from backend.src.services.share_link import is_valid
from backend.src.models.share_link import ShareLink

class ViewerContext(BaseModel):
  project_id: uuid.UUID
  read_only: bool = True

def get_viewer_context(
  token: str = Path(...),
  db: Session = Depends(get_db)
) -> ViewerContext:
  """Validates the Share Link token and returns a read-only viewer context.
  Raises 410 Gone if expired or revoked.
  """
  if not is_valid(db, token):
    raise HTTPException(
      status_code=status.HTTP_410_GONE,
      detail="Access no longer available"
    )
    
  link = db.query(ShareLink).filter(ShareLink.token == token).first()
  if not link:
    raise HTTPException(
      status_code=status.HTTP_410_GONE,
      detail="Access no longer available"
    )
    
  return ViewerContext(project_id=link.project_id)
