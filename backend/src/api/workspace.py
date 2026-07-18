from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from backend.src.db.session import get_db
from backend.src.api.auth import get_current_user
from backend.src.models.user import User
from backend.src.models.project import Project

router = APIRouter(prefix="/workspace", tags=["workspace"])

@router.get("/projects")
def list_workspace_projects(
  db: Session = Depends(get_db),
  current_user: User = Depends(get_current_user)
):
  """Lists active projects owned by the current user. Never returns another
  user's projects -- a colleague's only path to a project they don't own is an
  explicit Share Link, not the workspace list."""
  projects = db.query(Project).filter(
    Project.superseded_by.is_(None),
    Project.owner_id == current_user.id
  ).order_by(Project.created_at.desc()).all()
  return [
    {
      "id": str(p.id),
      "name": p.name,
      "commodity": p.commodity,
      "utm_zone": p.utm_zone
    }
    for p in projects
  ]
