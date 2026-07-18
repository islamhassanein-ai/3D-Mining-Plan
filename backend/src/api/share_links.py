import uuid
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from typing import List, Dict, Any

from backend.src.db.session import get_db
from backend.src.api.auth import get_current_user
from backend.src.models.user import User
from backend.src.models.project import Project
from backend.src.models.share_link import ShareLink
from backend.src.models.collar import Collar
from backend.src.api.dependencies import get_viewer_context, ViewerContext
from backend.src.services import share_link as share_link_service
from backend.src.api.scene import get_project_scene
from backend.src.api.collars import get_collar_details, get_true_thickness
from backend.src.api.project_access import get_owned_project_or_404 as get_project_or_404

# Router for project owners to manage links
router = APIRouter(prefix="/projects/{project_id}/share-links", tags=["share-links"])

# Router for read-only token viewers
share_router = APIRouter(prefix="/share", tags=["share"])

@router.post("", status_code=status.HTTP_201_CREATED)
def create_share_link(
  project_id: str,
  request: Request,
  db: Session = Depends(get_db),
  current_user: User = Depends(get_current_user)
):
  """Generates a new read-only share link token for a project."""
  project = get_project_or_404(project_id, db, current_user)
  link = share_link_service.issue(db, project.id, current_user.id)
  
  # Construct full shareable URL
  # In production, this uses request base URL. For local dev, fall back to base URL.
  base_url = str(request.base_url).rstrip('/')
  # Make it point to the frontend index page with the token query
  share_url = f"{base_url}/?share={link.token}"
  
  return {
    "id": str(link.id),
    "token": link.token,
    "share_url": share_url,
    "expires_at": link.expires_at.isoformat() if link.expires_at else None,
    "created_at": link.created_at.isoformat() if link.created_at else None,
    "created_by": str(link.created_by)
  }

@router.get("")
def list_share_links(
  project_id: str,
  db: Session = Depends(get_db),
  current_user: User = Depends(get_current_user)
):
  """Lists all share links associated with the project."""
  project = get_project_or_404(project_id, db, current_user)
  links = db.query(ShareLink).filter(ShareLink.project_id == project.id).order_by(ShareLink.created_at.desc()).all()
  return [
    {
      "id": str(l.id),
      "token": l.token,
      "expires_at": l.expires_at.isoformat() if l.expires_at else None,
      "revoked_at": l.revoked_at.isoformat() if l.revoked_at else None,
      "created_at": l.created_at.isoformat() if l.created_at else None,
      "created_by": str(l.created_by)
    }
    for l in links
  ]

@router.post("/{link_id}/revoke")
def revoke_share_link(
  project_id: str,
  link_id: str,
  db: Session = Depends(get_db),
  current_user: User = Depends(get_current_user)
):
  """Idempotently revokes a share link."""
  project = get_project_or_404(project_id, db, current_user)
  try:
    l_uuid = uuid.UUID(link_id)
  except ValueError:
    raise HTTPException(status_code=404, detail="Share link not found")
    
  link = db.query(ShareLink).filter(ShareLink.id == l_uuid, ShareLink.project_id == project.id).first()
  if not link:
    raise HTTPException(status_code=404, detail="Share link not found")
    
  share_link_service.revoke(db, link.token)
  return {"message": "Share link successfully revoked"}

@router.post("/{link_id}/renew")
def renew_share_link(
  project_id: str,
  link_id: str,
  db: Session = Depends(get_db),
  current_user: User = Depends(get_current_user)
):
  """Extends active share link by 7 days. Returns 409 Conflict if link is dead."""
  project = get_project_or_404(project_id, db, current_user)
  try:
    l_uuid = uuid.UUID(link_id)
  except ValueError:
    raise HTTPException(status_code=404, detail="Share link not found")
    
  link = db.query(ShareLink).filter(ShareLink.id == l_uuid, ShareLink.project_id == project.id).first()
  if not link:
    raise HTTPException(status_code=404, detail="Share link not found")
    
  try:
    renewed = share_link_service.renew(db, link.token)
    return {
      "id": str(renewed.id),
      "token": renewed.token,
      "expires_at": renewed.expires_at.isoformat()
    }
  except share_link_service.LinkExpiredOrRevokedException as e:
    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

# --- Token-Authenticated Viewer Routes ---

@share_router.get("/{token}/scene")
def get_shared_scene(
  token: str,
  db: Session = Depends(get_db),
  viewer_ctx: ViewerContext = Depends(get_viewer_context)
):
  """Fetches project scene for a valid share token."""
  # Reuses existing scene loader endpoint logic, scoping it to the token's project_id
  return get_project_scene(project_id=str(viewer_ctx.project_id), db=db, current_user=None)

@share_router.get("/{token}/collars/{collar_id}")
def get_shared_collar(
  token: str,
  collar_id: str,
  db: Session = Depends(get_db),
  viewer_ctx: ViewerContext = Depends(get_viewer_context)
):
  """Fetches drillhole collar details for a valid share token."""
  # Check project scoping: collar must belong to the token's project
  try:
    c_uuid = uuid.UUID(collar_id)
  except ValueError:
    raise HTTPException(status_code=404, detail="Drillhole not found")
    
  collar = db.query(Collar).filter(Collar.id == c_uuid, Collar.project_id == viewer_ctx.project_id).first()
  if not collar or collar.superseded_by is not None:
    raise HTTPException(status_code=404, detail="Drillhole not found")
    
  return get_collar_details(collar_id=collar_id, db=db, current_user=None)

@share_router.get("/{token}/collars/{collar_id}/true-thickness")
def get_shared_true_thickness(
  token: str,
  collar_id: str,
  interval_id: str,
  dip_direction: float,
  dip: float,
  db: Session = Depends(get_db),
  viewer_ctx: ViewerContext = Depends(get_viewer_context)
):
  """Calculates JORC true thickness for a valid share token."""
  try:
    c_uuid = uuid.UUID(collar_id)
  except ValueError:
    raise HTTPException(status_code=404, detail="Drillhole not found")
    
  collar = db.query(Collar).filter(Collar.id == c_uuid, Collar.project_id == viewer_ctx.project_id).first()
  if not collar or collar.superseded_by is not None:
    raise HTTPException(status_code=404, detail="Drillhole not found")
    
  return get_true_thickness(
    collar_id=collar_id,
    interval_id=interval_id,
    dip_direction=dip_direction,
    dip=dip,
    db=db,
    current_user=None
  )
