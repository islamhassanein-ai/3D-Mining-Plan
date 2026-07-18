import os
import io
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
from backend.src.models.assay_interval import AssayInterval
from backend.src.models.lithology_interval import LithologyInterval

# SQLite in-memory test database
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Load all models and create tables
import backend.src.models
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

# Helper to create a user and get a valid JWT header
def get_auth_headers(db_session):
    user = db_session.query(User).filter(User.email == "owner@example.com").first()
    if not user:
        import uuid
        user = User(id=uuid.uuid4(), email="owner@example.com", role="owner")
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        
    token = create_access_token(data={
        "sub": user.email,
        "role": user.role,
        "user_id": str(user.id)
    })
    return {"Authorization": f"Bearer {token}"}

def test_full_import_commit_flow():
    db = TestingSessionLocal()
    headers = get_auth_headers(db)
    
    # 1. Create Project
    response = client.post("/projects", json={"name": "Test Prospect", "commodity": "Gold"}, headers=headers)
    assert response.status_code == 201
    proj_data = response.json()
    proj_id = proj_data["id"]
    assert proj_data["name"] == "Test Prospect"
    assert proj_data["utm_zone"] is None
    
    # 2. Upload CSV files (multipart)
    fixtures_dir = os.path.join(os.path.dirname(__file__), "fixtures")
    
    collar_path = os.path.join(fixtures_dir, "collars.csv")
    survey_path = os.path.join(fixtures_dir, "surveys.csv")
    assay_path = os.path.join(fixtures_dir, "assays.csv")
    lith_path = os.path.join(fixtures_dir, "lithologies.csv")
    
    with open(collar_path, "rb") as fc, open(survey_path, "rb") as fs, \
         open(assay_path, "rb") as fa, open(lith_path, "rb") as fl:
         
         files = {
             "collar_file": ("collars.csv", fc, "text/csv"),
             "survey_file": ("surveys.csv", fs, "text/csv"),
             "assay_file": ("assays.csv", fa, "text/csv"),
             "lithology_file": ("lithologies.csv", fl, "text/csv"),
         }
         
         response_upload = client.post(
             f"/projects/{proj_id}/imports",
             files=files,
             headers=headers
         )
         
    assert response_upload.status_code == 201
    upload_data = response_upload.json()
    batch_id = upload_data["import_batch_id"]
    assert upload_data["status"] == "pending_review"
    assert upload_data["validation"]["valid"] is True
    
    # Check that it detected UTM zone 36N
    assert upload_data["validation"]["detected_utm_zone"] == "36N"
    
    # 3. Commit the batch
    response_commit = client.post(
        f"/projects/{proj_id}/imports/{batch_id}/commit?utm_zone_confirm=36N",
        headers=headers
    )
    assert response_commit.status_code == 200
    assert response_commit.json()["message"] == "Import batch committed successfully"
    
    # 4. Verify data was persisted in database
    # Fetch project and check UTM zone was updated
    project = db.query(Project).filter(Project.id == uuid.UUID(proj_id)).first()
    assert project.utm_zone == "36N"
    
    # Verify collars
    db_collars = db.query(Collar).filter(Collar.project_id == uuid.UUID(proj_id)).all()
    assert len(db_collars) == 2
    hole_ids = {c.hole_id for c in db_collars}
    assert hole_ids == {"DH01", "DH02"}
    
    dh01_collar = next(c for c in db_collars if c.hole_id == "DH01")
    assert dh01_collar.easting == 350000.0
    assert dh01_collar.northing == 2800000.0
    assert dh01_collar.elevation == 100.0
    
    # Verify surveys
    dh01_surveys = db.query(Survey).filter(Survey.collar_id == dh01_collar.id).all()
    assert len(dh01_surveys) == 2
    assert any(math_close(s.depth, 100.0) and math_close(s.dip, -89.9) for s in dh01_surveys)
    
    # Verify assays
    dh01_assays = db.query(AssayInterval).filter(AssayInterval.collar_id == dh01_collar.id).all()
    assert len(dh01_assays) == 2
    
    # Verify lithology
    dh01_liths = db.query(LithologyInterval).filter(LithologyInterval.collar_id == dh01_collar.id).all()
    assert len(dh01_liths) == 1
    assert dh01_liths[0].lith_code == "SND"

def math_close(a, b, tol=1e-5):
    return abs(a - b) < tol


def test_reimport_supersedes_collar_without_fk_error():
    """Regression test: re-importing an existing hole_id must not attempt to set
    AssayInterval.superseded_by / LithologyInterval.superseded_by to a Collar id
    (that column is a foreign key into their own tables, not into collar). The old
    collar's intervals must remain untouched and reachable only through the old,
    now-superseded collar."""
    db = TestingSessionLocal()
    headers = get_auth_headers(db)

    response = client.post("/projects", json={"name": "Reimport Test", "commodity": "Gold"}, headers=headers)
    proj_id = response.json()["id"]

    fixtures_dir = os.path.join(os.path.dirname(__file__), "fixtures")
    collar_path = os.path.join(fixtures_dir, "collars.csv")
    survey_path = os.path.join(fixtures_dir, "surveys.csv")
    assay_path = os.path.join(fixtures_dir, "assays.csv")
    lith_path = os.path.join(fixtures_dir, "lithologies.csv")

    def upload_and_commit():
        with open(collar_path, "rb") as fc, open(survey_path, "rb") as fs, \
             open(assay_path, "rb") as fa, open(lith_path, "rb") as fl:
            files = {
                "collar_file": ("collars.csv", fc, "text/csv"),
                "survey_file": ("surveys.csv", fs, "text/csv"),
                "assay_file": ("assays.csv", fa, "text/csv"),
                "lithology_file": ("lithologies.csv", fl, "text/csv"),
            }
            resp = client.post(f"/projects/{proj_id}/imports", files=files, headers=headers)
        assert resp.status_code == 201
        batch_id = resp.json()["import_batch_id"]
        commit_resp = client.post(
            f"/projects/{proj_id}/imports/{batch_id}/commit?utm_zone_confirm=36N",
            headers=headers
        )
        assert commit_resp.status_code == 200, commit_resp.text
        return batch_id

    # First import
    upload_and_commit()
    old_collars = db.query(Collar).filter(Collar.project_id == uuid.UUID(proj_id)).all()
    assert len(old_collars) == 2
    old_dh01 = next(c for c in old_collars if c.hole_id == "DH01")
    old_dh01_assays = db.query(AssayInterval).filter(AssayInterval.collar_id == old_dh01.id).all()
    assert len(old_dh01_assays) == 2

    # Re-import the same hole_ids -- this must not raise and must supersede correctly
    upload_and_commit()

    # The commit happened through a *different* SQLAlchemy session (the request's
    # own get_db-provided session), so this test's long-lived `db` session's
    # identity map is holding stale, pre-reimport attribute values for objects it
    # already loaded above. Expire them so the next query re-reads current state.
    db.expire_all()

    all_collars = db.query(Collar).filter(Collar.project_id == uuid.UUID(proj_id)).all()
    assert len(all_collars) == 4  # 2 original + 2 new
    current_collars = [c for c in all_collars if c.superseded_by is None]
    assert len(current_collars) == 2
    assert {c.hole_id for c in current_collars} == {"DH01", "DH02"}

    # The old DH01 collar must now be marked superseded, pointing at the new one
    db.refresh(old_dh01)
    assert old_dh01.superseded_by is not None
    new_dh01 = next(c for c in current_collars if c.hole_id == "DH01")
    assert old_dh01.superseded_by == new_dh01.id

    # The old collar's intervals must be untouched (superseded_by still None on
    # the interval itself -- they are excluded from "current" data via their
    # parent collar's supersession, not their own superseded_by field)
    for a in old_dh01_assays:
        db.refresh(a)
        assert a.superseded_by is None
        assert a.collar_id == old_dh01.id

    # The new DH01 collar has its own fresh, unsuperseded intervals
    new_dh01_assays = db.query(AssayInterval).filter(AssayInterval.collar_id == new_dh01.id).all()
    assert len(new_dh01_assays) == 2
    assert all(a.superseded_by is None for a in new_dh01_assays)


def test_commit_requires_acknowledgment_for_warnings():
    """Overlapping/gapped intervals are warnings, not errors, so `valid` stays
    True -- but per data-model.md and contracts/api.md the commit must still be
    rejected (422) unless the client explicitly acknowledges the warnings."""
    db = TestingSessionLocal()
    headers = get_auth_headers(db)

    response = client.post("/projects", json={"name": "Warning Ack Test", "commodity": "Gold"}, headers=headers)
    proj_id = response.json()["id"]

    collar_csv = b"hole_id,easting,northing,elevation,utm_zone\nDH01,350000.0,2800000.0,100.0,36N\n"
    assay_csv = (
        b"hole_id,from_depth,to_depth,grade,grade_unit\n"
        b"DH01,0.0,2.0,1.5,ppm\n"
        b"DH01,1.5,3.5,2.0,ppm\n"  # overlaps the row above -> warning, not error
    )

    files = {
        "collar_file": ("collars.csv", io.BytesIO(collar_csv), "text/csv"),
        "assay_file": ("assays.csv", io.BytesIO(assay_csv), "text/csv"),
    }
    resp = client.post(f"/projects/{proj_id}/imports", files=files, headers=headers)
    assert resp.status_code == 201
    validation = resp.json()["validation"]
    assert validation["valid"] is True  # warnings don't flip `valid`
    assert any(i["rule"] == "assay_overlap" for i in validation["issues"])
    batch_id = resp.json()["import_batch_id"]

    # Commit WITHOUT acknowledging the warning must be rejected
    commit_resp = client.post(
        f"/projects/{proj_id}/imports/{batch_id}/commit?utm_zone_confirm=36N",
        headers=headers
    )
    assert commit_resp.status_code == 422

    # Commit WITH explicit acknowledgment must succeed
    commit_resp_ack = client.post(
        f"/projects/{proj_id}/imports/{batch_id}/commit?utm_zone_confirm=36N&acknowledge_warnings=true",
        headers=headers
    )
    assert commit_resp_ack.status_code == 200, commit_resp_ack.text
