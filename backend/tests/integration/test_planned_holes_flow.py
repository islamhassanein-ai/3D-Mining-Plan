"""Saving a drill pattern into the project as planned holes.

The safety rule under test is the one that matters: a plan must never overwrite
drilling. Re-saving a pattern is meant to be routine, so a planned hole replaces
an earlier planned hole of the same name -- but if that name belongs to a hole
somebody actually drilled, the whole save is refused before anything is written.
"""
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.src.db.session import Base, get_db
from backend.src.api.main import app
from backend.src.api.auth import create_access_token
from backend.src.models.user import User
from backend.src.models.project import Project
from backend.src.models.collar import Collar
from backend.src.models.survey import Survey
from backend.src.models.import_batch import ImportBatch

SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def setup_overrides():
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()


client = TestClient(app)


@pytest.fixture
def project_ctx():
    db = TestingSessionLocal()
    user = User(id=uuid.uuid4(), email=f"planner_{uuid.uuid4().hex[:8]}@example.com", role="owner")
    db.add(user)
    project = Project(id=uuid.uuid4(), name="Pattern Test", utm_zone="37N", owner_id=user.id)
    db.add(project)
    db.commit()
    token = create_access_token(
        data={"sub": user.email, "role": user.role, "user_id": str(user.id)}
    )
    ctx = {
        "headers": {"Authorization": f"Bearer {token}"},
        "project_id": str(project.id),
        "user_id": user.id,
    }
    db.close()
    return ctx


def _hole(hole_id, depth=85.0):
    return {
        "hole_id": hole_id,
        "easting": 208720.3,
        "northing": 2467784.8,
        "elevation": 313.0,
        "azimuth": 17.0,
        "dip": 50.0,
        "total_depth": depth,
    }


def _post(ctx, holes):
    return client.post(
        f"/projects/{ctx['project_id']}/planned-holes",
        json={"holes": holes},
        headers=ctx["headers"],
    )


def test_a_pattern_saves_as_planned_holes_with_surveys(project_ctx):
    response = _post(project_ctx, [_hole("PLAN_01A"), _hole("PLAN_01B", 96.0)])
    assert response.status_code == 201, response.text

    body = response.json()
    assert body["created"] == 2
    assert body["replaced"] == 0

    db = TestingSessionLocal()
    collars = db.query(Collar).filter(
        Collar.project_id == uuid.UUID(project_ctx["project_id"]),
        Collar.superseded_by.is_(None),
    ).all()
    assert {c.hole_id for c in collars} == {"PLAN_01A", "PLAN_01B"}

    for collar in collars:
        assert collar.hole_status == "planned"
        assert collar.hole_type == "DD"
        assert collar.utm_zone == "37N", "inherits the project's zone"

        surveys = db.query(Survey).filter(Survey.collar_id == collar.id).order_by(Survey.depth).all()
        # Two stations, so the hole desurveys to its planned length instead of
        # collapsing to a stub at the collar.
        assert len(surveys) == 2
        assert surveys[0].depth == 0.0
        assert surveys[1].depth == (96.0 if collar.hole_id == "PLAN_01B" else 85.0)
        # Stored signed: negative is below horizontal, which is what the
        # desurvey expects.
        assert all(s.dip == -50.0 for s in surveys)
        assert all(s.azimuth == 17.0 for s in surveys)
    db.close()


def test_planned_holes_carry_no_invented_assays(project_ctx):
    """A hole nobody has drilled must not contribute grade rows."""
    from backend.src.models.assay_interval import AssayInterval

    _post(project_ctx, [_hole("PLAN_01A")])

    db = TestingSessionLocal()
    collar = db.query(Collar).filter(Collar.hole_id == "PLAN_01A").first()
    assays = db.query(AssayInterval).filter(AssayInterval.collar_id == collar.id).all()
    assert assays == []
    db.close()


def test_resaving_a_pattern_replaces_rather_than_duplicates(project_ctx):
    _post(project_ctx, [_hole("PLAN_01A", 85.0)])
    second = _post(project_ctx, [_hole("PLAN_01A", 120.0)])

    assert second.status_code == 201
    assert second.json()["replaced"] == 1

    db = TestingSessionLocal()
    active = db.query(Collar).filter(
        Collar.project_id == uuid.UUID(project_ctx["project_id"]),
        Collar.hole_id == "PLAN_01A",
        Collar.superseded_by.is_(None),
    ).all()
    assert len(active) == 1, "re-saving must not leave two live holes with one name"

    surveys = db.query(Survey).filter(Survey.collar_id == active[0].id).all()
    assert max(s.depth for s in surveys) == 120.0, "the new depth wins"

    # The old one survives as history rather than being deleted.
    superseded = db.query(Collar).filter(
        Collar.hole_id == "PLAN_01A",
        Collar.superseded_by.isnot(None),
    ).all()
    assert len(superseded) == 1
    assert superseded[0].superseded_by == active[0].id
    db.close()


def test_a_plan_never_overwrites_a_drilled_hole(project_ctx):
    """The rule that protects real data."""
    db = TestingSessionLocal()
    batch = ImportBatch(
        id=uuid.uuid4(),
        project_id=uuid.UUID(project_ctx["project_id"]),
        source_file="real_drilling.csv",
        status="committed",
        created_by=project_ctx["user_id"],
    )
    db.add(batch)
    drilled = Collar(
        id=uuid.uuid4(),
        project_id=uuid.UUID(project_ctx["project_id"]),
        hole_id="AADD010",
        easting=1.0, northing=2.0, elevation=3.0,
        utm_zone="37N",
        import_batch_id=batch.id,
        hole_type="DD",
        hole_status="drilled",
    )
    db.add(drilled)
    db.commit()
    drilled_id = drilled.id
    db.close()

    response = _post(project_ctx, [_hole("PLAN_NEW"), _hole("AADD010")])
    assert response.status_code == 409
    assert "AADD010" in response.json()["detail"]

    db = TestingSessionLocal()
    still_there = db.query(Collar).filter(Collar.id == drilled_id).first()
    assert still_there.superseded_by is None, "the drilled hole is untouched"
    assert still_there.hole_status == "drilled"
    # A refused save writes nothing at all -- not even the holes that were fine.
    assert db.query(Collar).filter(Collar.hole_id == "PLAN_NEW").count() == 0
    db.close()


def test_duplicate_hole_ids_in_one_request_are_rejected(project_ctx):
    response = _post(project_ctx, [_hole("PLAN_01A"), _hole("PLAN_01A")])
    assert response.status_code == 400
    assert "PLAN_01A" in response.json()["detail"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("total_depth", 0),
        ("total_depth", -10),
        ("azimuth", 360),
        ("azimuth", -1),
        ("dip", 91),
        ("hole_id", "   "),
    ],
)
def test_invalid_holes_are_refused(project_ctx, field, value):
    hole = _hole("PLAN_BAD")
    hole[field] = value
    assert _post(project_ctx, [hole]).status_code == 422


def test_dip_is_stored_downward_whichever_sign_arrives(project_ctx):
    """Both dip conventions appear in this project's data; a surface hole can
    only mean 'down' either way."""
    hole = _hole("PLAN_SIGNED")
    hole["dip"] = -50.0
    _post(project_ctx, [hole])

    db = TestingSessionLocal()
    collar = db.query(Collar).filter(Collar.hole_id == "PLAN_SIGNED").first()
    surveys = db.query(Survey).filter(Survey.collar_id == collar.id).all()
    assert all(s.dip == -50.0 for s in surveys)
    db.close()


def test_another_users_project_is_not_reachable(project_ctx):
    other = TestingSessionLocal()
    stranger = User(id=uuid.uuid4(), email=f"stranger_{uuid.uuid4().hex[:6]}@example.com", role="owner")
    other.add(stranger)
    other.commit()
    token = create_access_token(
        data={"sub": stranger.email, "role": stranger.role, "user_id": str(stranger.id)}
    )
    other.close()

    response = client.post(
        f"/projects/{project_ctx['project_id']}/planned-holes",
        json={"holes": [_hole("PLAN_X")]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404
