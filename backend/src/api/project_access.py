import uuid
from typing import Optional
from fastapi import HTTPException
from sqlalchemy.orm import Session
from backend.src.models.project import Project
from backend.src.models.user import User


def get_project_or_404(project_id: str, db: Session) -> Project:
    """Fetches a Project by id, 404 if it doesn't exist or has been superseded.

    Pure existence check -- does NOT enforce ownership. Callers that reach this
    on behalf of an already-authorized-by-other-means caller (e.g. a validated
    Share Link token) should call this alone. Callers acting on behalf of a
    logged-in user MUST also call enforce_project_ownership() below.
    """
    try:
        p_uuid = uuid.UUID(project_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Project not found")
    project = db.query(Project).filter(Project.id == p_uuid).first()
    if not project or project.superseded_by is not None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


def enforce_project_ownership(project: Project, current_user: Optional[User]) -> None:
    """Raises 404 (never 403, to avoid leaking existence) if current_user does
    not own the project.

    A `current_user` of None means authorization already happened by another
    means for this request (e.g. a validated Share Link token in
    share_links.py's token-authenticated viewer routes) -- this is a
    deliberate no-op in that case, not a bypass, since those routes already
    scope every query to the token's own project_id before ever reaching
    shared logic like this.

    A project with no owner_id (created before ownership tracking existed) is
    treated as inaccessible to every logged-in user, never as public.
    """
    if current_user is None:
        return
    if project.owner_id is None or project.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Project not found")


def get_owned_project_or_404(project_id: str, db: Session, current_user: Optional[User]) -> Project:
    """Convenience wrapper: fetch + enforce ownership in one call."""
    project = get_project_or_404(project_id, db)
    enforce_project_ownership(project, current_user)
    return project
