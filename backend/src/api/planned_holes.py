"""Save a planned drill pattern into the project as planned holes.

No new tables. `Collar.hole_status = 'planned'` already exists end to end -- the
dashed trace renderer, the "Planned Boreholes" layer toggle, the PLANNED hover
tag, the scene payload and the exporters all understand it -- so a saved pattern
is picked up by every one of them for free.

Two rules shape this endpoint.

**A planned hole must never overwrite a drilled one.** Re-saving a pattern has
to be safe to do repeatedly, so a planned hole replaces an earlier planned hole
with the same id. But if that id belongs to a hole that has actually been
drilled, replacing it would supersede real assay and survey data with a
proposal. That is refused outright, for the whole request, before anything is
written -- reporting the clash rather than silently renaming, because a
collision means the geologist believes something about the hole names that is
not true.

**No fabricated assays.** A planned hole gets a collar and two survey stations,
which is enough to desurvey and draw it. It deliberately gets no assay
intervals: inventing grade rows for a hole nobody has drilled would feed the
project's own grade statistics with fiction.
"""
import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from backend.src.db.session import get_db
from backend.src.api.auth import get_current_user
from backend.src.api.project_access import get_owned_project_or_404
from backend.src.models.user import User
from backend.src.models.collar import Collar
from backend.src.models.survey import Survey
from backend.src.models.import_batch import ImportBatch

router = APIRouter(prefix="/projects/{project_id}/planned-holes", tags=["planned-holes"])


class PlannedHoleIn(BaseModel):
    hole_id: str = Field(..., min_length=1, max_length=64)
    easting: float
    northing: float
    elevation: float
    azimuth: float
    dip: float
    total_depth: float

    @field_validator("hole_id")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("hole_id cannot be blank")
        return v

    @field_validator("azimuth")
    @classmethod
    def _azimuth_range(cls, v: float) -> float:
        if not (0 <= v < 360):
            raise ValueError("azimuth must be in [0, 360)")
        return v

    @field_validator("dip")
    @classmethod
    def _dip_downward(cls, v: float) -> float:
        # Both conventions turn up in this project's data (see
        # services/dip_convention.py). A planned surface hole always goes down,
        # so "60" and "-60" can only mean the same thing, and both are stored as
        # the signed -60 the desurvey expects.
        if abs(v) > 90:
            raise ValueError("dip must be between -90 and 90 degrees")
        return -abs(v)

    @field_validator("total_depth")
    @classmethod
    def _positive_depth(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("total_depth must be greater than zero")
        return v


class PlannedHolesRequest(BaseModel):
    holes: List[PlannedHoleIn] = Field(..., min_length=1)
    source: str = Field("depth planner", max_length=200)


class PlannedHolesResponse(BaseModel):
    created: int
    replaced: int
    batch_id: str
    hole_ids: List[str]


@router.post("", response_model=PlannedHolesResponse, status_code=status.HTTP_201_CREATED)
def create_planned_holes(
    project_id: str,
    payload: PlannedHolesRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = get_owned_project_or_404(project_id, db, current_user)

    incoming = [h.hole_id for h in payload.holes]
    duplicates = sorted({h for h in incoming if incoming.count(h) > 1})
    if duplicates:
        raise HTTPException(
            status_code=400,
            detail=f"Duplicate hole_id values in the request: {', '.join(duplicates)}",
        )

    # Look up every clashing active collar in one query, then refuse the whole
    # request if any of them is real drilling. Checking up front means a
    # rejected save writes nothing at all, rather than half a pattern.
    existing = db.query(Collar).filter(
        Collar.project_id == project.id,
        Collar.hole_id.in_(incoming),
        Collar.superseded_by.is_(None),
    ).all()
    by_hole_id = {c.hole_id: c for c in existing}

    drilled_clashes = sorted(
        hole_id for hole_id, c in by_hole_id.items()
        if (c.hole_status or "drilled") != "planned"
    )
    if drilled_clashes:
        raise HTTPException(
            status_code=409,
            detail=(
                "These hole IDs already belong to drilled holes and will not be "
                f"overwritten by a plan: {', '.join(drilled_clashes)}. "
                "Change the hole ID prefix and save again."
            ),
        )

    batch = ImportBatch(
        id=uuid.uuid4(),
        project_id=project.id,
        source_file=payload.source,
        status="committed",
        created_by=current_user.id,
    )
    db.add(batch)
    db.flush()

    replaced = 0
    for hole in payload.holes:
        new_id = uuid.uuid4()

        collar = Collar(
            id=new_id,
            project_id=project.id,
            hole_id=hole.hole_id,
            easting=hole.easting,
            northing=hole.northing,
            elevation=hole.elevation,
            utm_zone=project.utm_zone,
            import_batch_id=batch.id,
            hole_type="DD",
            hole_status="planned",
        )
        db.add(collar)
        # Flush before the supersede UPDATE: session.py disables autoflush, so
        # the self-referential collar.superseded_by FK would otherwise point at
        # a row that does not exist yet. Same ordering constraint as
        # imports.py::_apply_collar.
        db.flush()

        previous = by_hole_id.get(hole.hole_id)
        if previous is not None:
            previous.superseded_by = new_id
            db.add(previous)
            db.flush()
            replaced += 1

        # Two stations is all a straight proposal needs, and it is what makes
        # the hole desurvey to its full planned length instead of collapsing to
        # a stub at the collar.
        for depth in (0.0, hole.total_depth):
            db.add(Survey(
                id=uuid.uuid4(),
                collar_id=new_id,
                depth=depth,
                dip=hole.dip,
                azimuth=hole.azimuth,
                desurvey_method="minimum_curvature",
            ))

    db.commit()

    return PlannedHolesResponse(
        created=len(payload.holes),
        replaced=replaced,
        batch_id=str(batch.id),
        hole_ids=incoming,
    )
