import uuid
import secrets
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from backend.src.models.share_link import ShareLink

class LinkExpiredOrRevokedException(Exception):
  """Raised when attempting to renew a share link that is already revoked or expired."""
  pass

def issue(db: Session, project_id: uuid.UUID, created_by_id: uuid.UUID) -> ShareLink:
  """Issues a new unguessable 7-day share link token for a project."""
  now = datetime.now(timezone.utc)
  token = secrets.token_urlsafe(32)
  expires_at = now + timedelta(days=7)

  link = ShareLink(
    id=uuid.uuid4(),
    project_id=project_id,
    token=token,
    created_by=created_by_id,
    created_at=now,
    expires_at=expires_at,
    revoked_at=None
  )
  db.add(link)
  db.commit()
  db.refresh(link)
  return link

def is_valid(db: Session, token: str) -> bool:
  """Returns True if the token exists, is not revoked, and is not expired."""
  link = db.query(ShareLink).filter(ShareLink.token == token).first()
  if not link:
    return False
  
  if link.revoked_at is not None:
    return False
  
  now = datetime.now(timezone.utc)
  # Ensure expires_at has timezone info if compared with now
  expires_at = link.expires_at
  if expires_at.tzinfo is None:
    expires_at = expires_at.replace(tzinfo=timezone.utc)
    
  if expires_at <= now:
    return False
    
  return True

def revoke(db: Session, token: str) -> None:
  """Idempotently revokes an active share link."""
  link = db.query(ShareLink).filter(ShareLink.token == token).first()
  if not link:
    return
  
  if link.revoked_at is None:
    link.revoked_at = datetime.now(timezone.utc)
    db.add(link)
    db.commit()

def renew(db: Session, token: str) -> ShareLink:
  """Extends the expiry of a valid link by 7 days. Raises LinkExpiredOrRevokedException if not active."""
  link = db.query(ShareLink).filter(ShareLink.token == token).first()
  if not link:
    raise LinkExpiredOrRevokedException("Share link not found")
    
  # Check if valid first
  if link.revoked_at is not None:
    raise LinkExpiredOrRevokedException("Cannot renew a revoked share link")
    
  now = datetime.now(timezone.utc)
  expires_at = link.expires_at
  if expires_at.tzinfo is None:
    expires_at = expires_at.replace(tzinfo=timezone.utc)
    
  if expires_at <= now:
    raise LinkExpiredOrRevokedException("Cannot renew an expired share link")
    
  link.expires_at = now + timedelta(days=7)
  db.add(link)
  db.commit()
  db.refresh(link)
  return link
