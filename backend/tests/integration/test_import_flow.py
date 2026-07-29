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
from backend.src.models.trench import Trench
from backend.src.models.import_batch import ImportBatch

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
    
    # Check that it detected UTM zone 37N -- the global default fallback
    # (crs.py / imports.py both default to 37N now; the explicit user
    # confirm below is still 36N, which is what gets stamped on the project).
    assert upload_data["validation"]["detected_utm_zone"] == "37N"
    
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


def test_reimport_collar_only_preserves_assays_and_survey_trace():
    """T012 data-loss regression. Import collar+survey+assay+lithology, then
    re-import collar ONLY. The existing bug detached the old collar's
    Survey/Assay/Lithology rows from the scene: the supersede path left them on
    the old (now-superseded) collar, and every read path fetches children by the
    *active* collar id. With no surveys the hole collapsed to a zero-length
    point (or a fallback vertical trace) and assays vanished.

    Fix: when the batch does NOT re-supply a child type for a hole_id, re-point
    that type's active rows to the new collar. This test must FAIL before the
    fix and PASS after.
    """
    db = TestingSessionLocal()
    headers = get_auth_headers(db)

    response = client.post("/projects", json={"name": "T012 Dataloss", "commodity": "Gold"}, headers=headers)
    proj_id = response.json()["id"]

    fixtures_dir = os.path.join(os.path.dirname(__file__), "fixtures")
    collar_path = os.path.join(fixtures_dir, "collars.csv")
    survey_path = os.path.join(fixtures_dir, "surveys.csv")
    assay_path = os.path.join(fixtures_dir, "assays.csv")
    lith_path = os.path.join(fixtures_dir, "lithologies.csv")

    def upload_and_commit(files):
        resp = client.post(f"/projects/{proj_id}/imports", files=files, headers=headers)
        assert resp.status_code == 201, resp.text
        batch_id = resp.json()["import_batch_id"]
        commit_resp = client.post(
            f"/projects/{proj_id}/imports/{batch_id}/commit?utm_zone_confirm=36N",
            headers=headers
        )
        assert commit_resp.status_code == 200, commit_resp.text
        return batch_id

    # 1. Full import: collar + survey + assay + lithology
    with open(collar_path, "rb") as fc, open(survey_path, "rb") as fs, \
         open(assay_path, "rb") as fa, open(lith_path, "rb") as fl:
        files = {
            "collar_file": ("collars.csv", fc, "text/csv"),
            "survey_file": ("surveys.csv", fs, "text/csv"),
            "assay_file": ("assays.csv", fa, "text/csv"),
            "lithology_file": ("lithologies.csv", fl, "text/csv"),
        }
        upload_and_commit(files)

    db.expire_all()
    old_active = db.query(Collar).filter(
        Collar.project_id == uuid.UUID(proj_id),
        Collar.hole_id == "DH01",
        Collar.superseded_by.is_(None)
    ).first()
    assert old_active is not None
    old_surveys = db.query(Survey).filter(Survey.collar_id == old_active.id).all()
    old_assays = db.query(AssayInterval).filter(
        AssayInterval.collar_id == old_active.id,
        AssayInterval.superseded_by.is_(None)
    ).all()
    assert len(old_surveys) == 2
    assert len(old_assays) == 2

    # 2. Re-import collar ONLY (no survey/assay/lithology file).
    with open(collar_path, "rb") as fc:
        files = {"collar_file": ("collars.csv", fc, "text/csv")}
        upload_and_commit(files)

    db.expire_all()
    all_collars = db.query(Collar).filter(
        Collar.project_id == uuid.UUID(proj_id), Collar.hole_id == "DH01"
    ).all()
    assert len(all_collars) == 2  # old + new
    new_active = next(c for c in all_collars if c.superseded_by is None)
    old_superseded = next(c for c in all_collars if c.superseded_by is not None)
    assert old_superseded.superseded_by == new_active.id

    # 3. The active DH01 collar must now carry the surveys and assays that were
    # on the old collar -- re-pointed because the re-import batch supplied none.
    # Before the fix these stayed on the old collar and the active collar had
    # none, dropping them from the scene.
    new_surveys = db.query(Survey).filter(Survey.collar_id == new_active.id).all()
    new_assays = db.query(AssayInterval).filter(
        AssayInterval.collar_id == new_active.id,
        AssayInterval.superseded_by.is_(None)
    ).all()
    assert len(new_surveys) == len(old_surveys) == 2, (
        f"surveys not re-pointed: active={len(new_surveys)} old={len(old_surveys)}"
    )
    assert len(new_assays) == len(old_assays) == 2, (
        f"assays not re-pointed: active={len(new_assays)} old={len(old_assays)}"
    )

    # 4. Scene returns DH01 with its assays and a surveyed trace (>=2 points)
    # using the actual survey dip, not the no-survey vertical fallback. With the
    # bug the active collar had no surveys and the scene fell back to a
    # straight -90 vertical hole.
    scene_resp = client.get(f"/projects/{proj_id}/scene", headers=headers)
    assert scene_resp.status_code == 200
    scene = scene_resp.json()
    dh = next((d for d in scene["drillholes"] if d["hole_id"] == "DH01"), None)
    assert dh is not None
    assert len(dh["assays"]) == 2, "assays vanished from the scene after collar-only re-import"
    assert len(dh["trace"]) >= 2
    # The real survey dip is -89.9/-90, not the no-survey fallback (-90, -90, 0).
    # The surveyed trace endpoint depth is 100.0 (from surveys.csv), proving the
    # original surveys are attached to the active collar.
    last_depths = [p["depth"] for p in dh["trace"]]
    assert 100.0 in last_depths or any(abs(d - 100.0) < 1e-3 for d in last_depths), (
        f"trace does not reflect the original survey (depths={last_depths})"
    )


# ---------------------------------------------------------------------------
# T017 — Combined-CSV import integration tests
# ---------------------------------------------------------------------------

ZONE_NAMES = ["Abo elmajd", "Adel", "Tallat", "Nabil", "Samir"]


# T017 tests all import the same zone names; since tests share one in-memory
# SQLite engine, using the fixed "owner@example.com" user would let a later
# test's `resolve_or_create_zone_projects` APPEND to an earlier test's "Abo
# elmajd" project (same owner, same normalized name) and contaminate counts.
# Each T017 test therefore authenticates as its OWN user so project resolution
# is fully isolated.
_test_user_counter = [0]


def get_auth_headers_unique(db):
    _test_user_counter[0] += 1
    email = f"combined_{_test_user_counter[0]}_user@example.com"
    user = User(id=uuid.uuid4(), email=email, role="owner")
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_access_token(data={"sub": user.email, "role": user.role, "user_id": str(user.id)})
    return {"Authorization": f"Bearer {token}"}, user


def _upload_combined_and_commit(proj_id, csv_path=None, utm="37N", headers=None, ack=False):
    """Upload the combined Master CSV through the import panel and commit.
    Returns (batch_id, validation_payload, commit_result_json)."""
    if csv_path is None:
        csv_path = os.path.join(os.path.dirname(__file__), "fixtures", "combined_master.csv")
    with open(csv_path, "rb") as fc:
        files = {"combined_file": ("combined_master.csv", fc, "text/csv")}
        resp = client.post(f"/projects/{proj_id}/imports", files=files, headers=headers)
    assert resp.status_code == 201, resp.text
    batch_id = resp.json()["import_batch_id"]
    validation = resp.json()["validation"]
    ack_param = "&acknowledge_warnings=true" if ack else ""
    commit_resp = client.post(
        f"/projects/{proj_id}/imports/{batch_id}/commit?utm_zone_confirm={utm}{ack_param}",
        headers=headers
    )
    assert commit_resp.status_code == 200, commit_resp.text
    return batch_id, validation, commit_resp.json()


def _zone_project_ids(commit_result):
    """The ids of the zone projects created/appended by this combined commit
    (excludes the URL/hub project which carries no rows). Use these to scope
    cross-test DB assertions -- tests share one in-memory SQLite engine, so an
    unfiltered count would aggregate rows from every test."""
    ids = []
    for b in commit_result.get("batches", []):
        if b.get("project_name") in ZONE_NAMES:
            ids.append(uuid.UUID(b["project_id"]))
    return ids


def test_combined_full_file_creates_five_projects_three_collars_44_trench_rows():
    db = TestingSessionLocal()
    headers, user = get_auth_headers_unique(db)

    # Pre-create "Abo elmajd" owned by the importing user -> must be APPENDED,
    # not duplicated.
    pre = client.post("/projects", json={"name": "Abo elmajd", "commodity": "Gold"}, headers=headers)
    assert pre.status_code == 201
    abo_pre_id = pre.json()["id"]

    hub = client.post("/projects", json={"name": "Master Hub", "commodity": "Gold"}, headers=headers)
    hub_id = hub.json()["id"]

    _batch_id, validation, commit_result = _upload_combined_and_commit(hub_id, headers=headers)
    zone_ids = _zone_project_ids(commit_result)

    # zones preview surfaces 5 zones (4 to create + 1 appended for Abo elmajd)
    zones = validation.get("zones") or []
    assert len(zones) == 5, zones
    abo_entry = next(z for z in zones if z["zone"] == "Abo elmajd")
    assert abo_entry["action"] == "appended", abo_entry

    db.expire_all()
    # Exactly one project per zone name owned by the importing user, and the
    # Abo elmajd one is the pre-created project (appended, not duplicated).
    zone_projects = db.query(Project).filter(Project.id.in_(zone_ids)).all()
    assert {p.name for p in zone_projects} == set(ZONE_NAMES)
    assert len(zone_projects) == 5
    abo_proj = next(p for p in zone_projects if p.name == "Abo elmajd")
    assert abo_proj.id == uuid.UUID(abo_pre_id)

    # 3 collars, all DD, all in the Abo elmajd project
    active_collars = db.query(Collar).filter(
        Collar.project_id.in_(zone_ids),
        Collar.superseded_by.is_(None)
    ).all()
    assert len(active_collars) == 3
    assert {c.hole_id for c in active_collars} == {"ARDD0001", "ARDD0001A", "ARDD0003"}
    assert all(c.hole_type == "DD" for c in active_collars)
    assert all(c.project_id == abo_proj.id for c in active_collars)

    # 22 trenches x 2 points = 44 active trench rows across these projects
    active_trench_rows = db.query(Trench).filter(
        Trench.project_id.in_(zone_ids),
        Trench.superseded_by.is_(None)
    ).all()
    assert len(active_trench_rows) == 44
    trench_ids = {t.trench_id for t in active_trench_rows}
    assert len(trench_ids) == 22  # 21 TR + 1 CH

    # ARTR001 (dip +16, length 145) -- the floating-trench guard: the far-end
    # point (point_order=1) sits at the SAME elevation as the collar (dz=0),
    # NOT ~339m in the air.
    artr_points = [t for t in active_trench_rows if t.trench_id == "ARTR001"]
    assert len(artr_points) == 2
    p0 = next(t for t in artr_points if t.point_order == 0)
    p1 = next(t for t in artr_points if t.point_order == 1)
    assert abs(p0.elevation - 299.13) < 1e-2
    assert abs(p1.elevation - 299.13) < 1e-2, (
        f"ARTR001 far end is floating at z={p1.elevation}, not collar elevation 299.13"
    )
    assert p0.dip == 16.0 and p0.azimuth == 100.0
    assert p1.dip is None and p1.azimuth is None


def test_combined_zone_project_owned_by_different_user_is_not_matched():
    db = TestingSessionLocal()
    headers, importer = get_auth_headers_unique(db)

    # Abo elmajd owned by a DIFFERENT user -> must NOT be matched.
    other = db.query(User).filter(User.email == "other@example.com").first()
    if not other:
        other = User(id=uuid.uuid4(), email="other@example.com", role="owner")
        db.add(other)
        db.commit()
        db.refresh(other)
    other_proj = Project(id=uuid.uuid4(), name="Abo elmajd", owner_id=other.id, commodity="Gold")
    db.add(other_proj)
    db.commit()

    hub = client.post("/projects", json={"name": "Master Hub B", "commodity": "Gold"}, headers=headers)
    hub_id = hub.json()["id"]

    _b, _v, commit_result = _upload_combined_and_commit(hub_id, headers=headers)
    db.expire_all()
    zone_ids = _zone_project_ids(commit_result)

    # The importer gets a brand-new Abo elmajd project (not the other user's).
    importer_abo = [db.query(Project).get(zid) for zid in zone_ids]
    importer_abo = [p for p in importer_abo if p and p.name == "Abo elmajd"]
    assert len(importer_abo) == 1
    assert importer_abo[0].id != other_proj.id

    other_proj_again = db.query(Project).filter(Project.id == other_proj.id).first()
    assert other_proj_again is not None
    assert other_proj_again.owner_id == other.id  # untouched


def test_combined_reupload_no_duplicates_prior_trenches_superseded():
    """T011 regression: re-uploading the master CSV must not duplicate trench
    polylines and must supersede the prior trench rows."""
    db = TestingSessionLocal()
    headers, _user = get_auth_headers_unique(db)
    hub = client.post("/projects", json={"name": "Reupload Hub", "commodity": "Gold"}, headers=headers)
    hub_id = hub.json()["id"]

    _b, _v, commit1 = _upload_combined_and_commit(hub_id, headers=headers)
    zone_ids = _zone_project_ids(commit1)

    db.expire_all()
    active_after_first = db.query(Trench).filter(
        Trench.project_id.in_(zone_ids), Trench.superseded_by.is_(None)
    ).all()
    assert len(active_after_first) == 44
    # remember an anchor id for ARTR001 to check it gets superseded later
    first_artr_anchor_id = next(
        t.id for t in active_after_first if t.trench_id == "ARTR001" and t.point_order == 0
    )

    # Re-upload the identical file
    _upload_combined_and_commit(hub_id, headers=headers)
    db.expire_all()

    active_after_second = db.query(Trench).filter(
        Trench.project_id.in_(zone_ids), Trench.superseded_by.is_(None)
    ).all()
    assert len(active_after_second) == 44, "re-upload duplicated trench rows"
    assert len({t.trench_id for t in active_after_second}) == 22

    # The initial ARTR001 anchor must now be superseded.
    first_artr_anchor = db.query(Trench).get(first_artr_anchor_id)
    assert first_artr_anchor.superseded_by is not None

    # Collars: still exactly 3 active (old superseded), with 6 total collar rows
    all_dd = db.query(Collar).filter(
        Collar.project_id.in_(zone_ids),
        Collar.hole_id.in_(["ARDD0001", "ARDD0001A", "ARDD0003"])
    ).all()
    assert len(all_dd) == 6  # 3 original + 3 new
    active_dd = [c for c in all_dd if c.superseded_by is None]
    assert len(active_dd) == 3

    # T012 per-child-pointing: the combined re-import supplies inline surveys for
    # DD holes, so the OLD surveys stay on the old (superseded) collar and the
    # NEW collar gets the new inline survey (NOT re-pointed, because the batch
    # supplies surveys for that hole_id).
    new_dd = {c.hole_id: c for c in active_dd}
    for h in ("ARDD0001", "ARDD0001A", "ARDD0003"):
        new_surveys = db.query(Survey).filter(Survey.collar_id == new_dd[h].id).all()
        assert len(new_surveys) == 1, f"{h} new collar should have 1 inline survey"


def test_combined_batch_project_fk_matches_collar_project_and_delete_succeeds():
    """T010: every collar's import_batch_id resolves to a batch whose
    project_id equals that collar's project_id; delete_project then succeeds on
    all projects (no IntegrityError from a cross-project FK)."""
    db = TestingSessionLocal()
    headers, _user = get_auth_headers_unique(db)
    hub = client.post("/projects", json={"name": "FK Hub", "commodity": "Gold"}, headers=headers)
    hub_id = hub.json()["id"]

    _b, _v, commit1 = _upload_combined_and_commit(hub_id, headers=headers)
    zone_ids = _zone_project_ids(commit1)
    db.expire_all()

    collars = db.query(Collar).filter(
        Collar.project_id.in_(zone_ids), Collar.superseded_by.is_(None)
    ).all()
    assert collars
    batches = {b.id: b for b in db.query(ImportBatch).all()}
    for c in collars:
        b = batches.get(c.import_batch_id)
        assert b is not None, f"collar {c.hole_id} batch missing"
        assert b.project_id == c.project_id, (
            f"collar {c.hole_id} batch.project_id {b.project_id} != collar.project_id {c.project_id}"
        )

    trenches = db.query(Trench).filter(
        Trench.project_id.in_(zone_ids), Trench.superseded_by.is_(None)
    ).all()
    for t in trenches:
        if t.import_batch_id is None:
            continue
        b = batches.get(t.import_batch_id)
        assert b is not None
        assert b.project_id == t.project_id

    # delete every zone project created by this import + the hub.
    user = db.query(User).filter(User.email == "owner@example.com").first()
    own_ids = set(zone_ids) | {uuid.UUID(hub_id)}
    owned = db.query(Project).filter(Project.id.in_(own_ids)).all()
    assert len(owned) == len(own_ids)
    for p in owned:
        r = client.delete(f"/projects/{p.id}", headers=headers)
        assert r.status_code == 204, f"delete_project failed for {p.name}: {r.text}"


def test_combined_no_type_column_imports_as_all_dd_with_warning_and_commits():
    db = TestingSessionLocal()
    headers, _user = get_auth_headers_unique(db)
    hub = client.post("/projects", json={"name": "NoType Hub", "commodity": "Gold"}, headers=headers)
    hub_id = hub.json()["id"]

    csv_no_type = (
        b"Hole Id,Zone,X,Y,Z,Dip,Azimuth,Total_Length\n"
        b"DH001,Abo elmajd,208322,2467932,297,-50,122,44.3\n"
        b"DH002,Adel,208667,2467880,270,-60,90,30\n"
    )
    files = {"combined_file": ("no_type.csv", io.BytesIO(csv_no_type), "text/csv")}
    resp = client.post(f"/projects/{hub_id}/imports", files=files, headers=headers)
    assert resp.status_code == 201, resp.text
    validation = resp.json()["validation"]
    # exactly one warning about the missing Type column, and it's a warning not error
    parse_warns = [i for i in validation["issues"] if i["rule"] == "parse_error" and i["type"] == "warning"]
    assert len(parse_warns) == 1
    assert validation["valid"] is True  # warning does not block
    assert validation["summary"]["collar_count"] == 2
    assert validation["summary"]["survey_count"] == 2  # one inline survey each

    batch_id = resp.json()["import_batch_id"]
    # Commit with acknowledge_warnings=true -- the missing-Type warning is a
    # warning, and warnings must be acknowledged to commit (per the existing
    # contract). The point of this test is that it CAN commit (no error block).
    commit_resp = client.post(
        f"/projects/{hub_id}/imports/{batch_id}/commit?utm_zone_confirm=37N&acknowledge_warnings=true",
        headers=headers
    )
    assert commit_resp.status_code == 200, commit_resp.text
    db.expire_all()

    commit_zone_ids = _zone_project_ids(commit_resp.json())
    collars = db.query(Collar).filter(
        Collar.project_id.in_(commit_zone_ids), Collar.superseded_by.is_(None)
    ).all()
    assert len(collars) == 2
    assert all(c.hole_type == "DD" for c in collars)


def test_combined_with_four_file_rejected_400():
    """Item 5: supplying combined_file together with any of collar_file et al.
    returns HTTP 400, not silent discard."""
    db = TestingSessionLocal()
    headers, _user = get_auth_headers_unique(db)
    hub = client.post("/projects", json={"name": "Mix Hub", "commodity": "Gold"}, headers=headers)
    hub_id = hub.json()["id"]

    fixtures_dir = os.path.join(os.path.dirname(__file__), "fixtures")
    combined_csv_path = os.path.join(fixtures_dir, "combined_master.csv")

    with open(combined_csv_path, "rb") as fcomb, \
         open(os.path.join(fixtures_dir, "collars.csv"), "rb") as fcollar:
        files = {
            "combined_file": ("combined_master.csv", fcomb, "text/csv"),
            "collar_file": ("collars.csv", fcollar, "text/csv"),
        }
        resp = client.post(f"/projects/{hub_id}/imports", files=files, headers=headers)
    assert resp.status_code == 400, resp.text
    assert "not both" in resp.json()["detail"].lower()


def test_combined_trench_reimport_under_fk_enforcement():
    """NEW test (b). Import the combined file TWICE. Assert the second commit
    returns 200, the active trench row count is unchanged, and the NEW rows
    have superseded_by IS NULL while the OLD rows point at the new anchor.

    Under FK enforcement the naive supersede-then-insert ordering throws
    `FOREIGN KEY constraint failed` on the second import (Blocker 2). The naive
    "move the UPDATE after the inserts" variant supersedes the new rows against
    themselves, leaving zero active rows -- this test catches both failures."""
    db = TestingSessionLocal()
    headers, _user = get_auth_headers_unique(db)
    hub = client.post("/projects", json={"name": "FK Reimport Hub", "commodity": "Gold"}, headers=headers)
    hub_id = hub.json()["id"]

    _b1, _v1, commit1 = _upload_combined_and_commit(hub_id, headers=headers)
    zone_ids = _zone_project_ids(commit1)

    db.expire_all()
    active_after_first = db.query(Trench).filter(
        Trench.project_id.in_(zone_ids), Trench.superseded_by.is_(None)
    ).all()
    assert len(active_after_first) == 44
    first_active_ids = {t.id for t in active_after_first}

    # Second (identical) import -- the FK-ordered path that Blocker 2 broke.
    _b2, _v2, commit2 = _upload_combined_and_commit(hub_id, headers=headers)
    assert commit2 is not None  # commit returned 200 (asserted inside helper)

    db.expire_all()
    active_after_second = db.query(Trench).filter(
        Trench.project_id.in_(zone_ids), Trench.superseded_by.is_(None)
    ).all()
    assert len(active_after_second) == 44, "second import changed the active row count"
    assert len({t.trench_id for t in active_after_second}) == 22

    # NEW rows are active (superseded_by IS NULL); the first-import rows must
    # now point at the new anchors.
    second_active_ids = {t.id for t in active_after_second}
    superseded_rows = db.query(Trench).filter(
        Trench.project_id.in_(zone_ids), Trench.superseded_by.is_not(None)
    ).all()
    assert len(superseded_rows) == 44
    # All first-import row ids must now be superseded (pointing at a new anchor
    # id that is itself an active row).
    anchors_targeted = {s.superseded_by for s in superseded_rows}
    assert anchors_targeted.issubset(second_active_ids), (
        "old rows must point at one of the new active anchor rows"
    )
    # And the first-import ids are NO LONGER active.
    assert first_active_ids.isdisjoint(second_active_ids), (
        "first-import trench rows must be superseded, not still active"
    )


def test_full_resupply_reimport_passes_under_fk():
    """NEW test (d) -- Blocker 3: collar+survey+assay re-import (FULL resupply)
    must not throw the self-referential collar.superseded_by FK error. The
    existing four-file path predates this feature and was structurally broken
    on PostgreSQL; this test pins it under FK enforcement."""
    db = TestingSessionLocal()
    headers = get_auth_headers(db)
    response = client.post("/projects", json={"name": "Full Resupply FK", "commodity": "Gold"}, headers=headers)
    proj_id = response.json()["id"]

    fixtures_dir = os.path.join(os.path.dirname(__file__), "fixtures")
    collar_path = os.path.join(fixtures_dir, "collars.csv")
    survey_path = os.path.join(fixtures_dir, "surveys.csv")
    assay_path = os.path.join(fixtures_dir, "assays.csv")

    def upload_and_commit():
        with open(collar_path, "rb") as fc, open(survey_path, "rb") as fs, \
             open(assay_path, "rb") as fa:
            files = {
                "collar_file": ("collars.csv", fc, "text/csv"),
                "survey_file": ("surveys.csv", fs, "text/csv"),
                "assay_file": ("assays.csv", fa, "text/csv"),
            }
            resp = client.post(f"/projects/{proj_id}/imports", files=files, headers=headers)
        assert resp.status_code == 201, resp.text
        batch_id = resp.json()["import_batch_id"]
        commit_resp = client.post(
            f"/projects/{proj_id}/imports/{batch_id}/commit?utm_zone_confirm=36N",
            headers=headers
        )
        assert commit_resp.status_code == 200, commit_resp.text
        return batch_id

    # First full import (creates collars, no supersede).
    upload_and_commit()
    # Second full import -- FULL resupply; every hole_id is re-supplied so the
    # T012 re-point branch is skipped. This isolates Blocker 3: the collar
    # supersede UPDATE colliding with the self-FK under autoflush=False.
    upload_and_commit()

    db.expire_all()
    all_collars = db.query(Collar).filter(Collar.project_id == uuid.UUID(proj_id)).all()
    # 2 original (superseded) + 2 new (active) = 4
    assert len(all_collars) == 4
    active = [c for c in all_collars if c.superseded_by is None]
    superseded = [c for c in all_collars if c.superseded_by is not None]
    assert len(active) == 2
    assert len(superseded) == 2
    # Each superseded collar points at one of the active collars (same hole_id).
    active_by_hole = {c.hole_id: c for c in active}
    for s in superseded:
        new = active_by_hole.get(s.hole_id)
        assert new is not None
        assert s.superseded_by == new.id


def test_combined_real_file_end_to_end():
    r"""End-to-end verification of the four manual checks using the real production
    file (F:\Monark\15_Leapfrog\CSV\Collar.csv, BOM included), exercising:
    1. Preview lists 5 zones before commit
    2. 3 DD holes render with visible 2-point traces (not zero-length)
    3. 22 trenches render flat at collar elevation, not floating
    4. Re-upload changes no counts, duplicates nothing
    """
    import os
    db = TestingSessionLocal()
    headers = get_auth_headers(db)

    proj_id = client.post(
        "/projects", json={"name": "Real File Test", "commodity": "Gold"}, headers=headers
    ).json()["id"]

    # Load the real production file (byte-copy with UTF-8 BOM)
    fixture_dir = os.path.join(os.path.dirname(__file__), "fixtures")
    real_file = os.path.join(fixture_dir, "combined_master.csv")
    raw = open(real_file, "rb").read()
    assert raw.startswith(b"\xef\xbb\xbf"), "fixture must be byte-copy with BOM"

    def upload_and_commit():
        r = client.post(
            f"/projects/{proj_id}/imports",
            files={"combined_file": ("Collar.csv", raw, "text/csv")},
            headers=headers,
        )
        assert r.status_code == 201, r.text
        v = r.json()["validation"]
        bid = r.json()["import_batch_id"]
        c = client.post(
            f"/projects/{proj_id}/imports/{bid}/commit"
            f"?utm_zone_confirm=37N&acknowledge_warnings=true",
            headers=headers,
        )
        assert c.status_code == 200, c.text
        return v, c.json()

    # CHECK 1: preview lists 5 zones before commit
    validation, commit1 = upload_and_commit()
    zones = validation["zones"]
    assert len({z["zone"] for z in zones}) == 5, "expected 5 distinct zones"
    assert validation["valid"] is True
    assert sum(z["collar_count"] for z in zones) == 3, "expected 3 collars"
    assert sum(z["trench_count"] for z in zones) == 22, "expected 22 trenches, not 44 points"

    # CHECK 2: 3 DD holes render with visible 2-point traces
    scene_projects = [b["project_id"] for b in commit1["batches"]]
    total_dd, traces = 0, []
    for pid in scene_projects:
        sc = client.get(f"/projects/{pid}/scene", headers=headers)
        assert sc.status_code == 200, sc.text
        for dh in sc.json()["drillholes"]:
            total_dd += 1
            traces.append((dh["hole_id"], len(dh["trace"])))
    assert total_dd == 3, f"expected 3 DD holes, got {total_dd}"
    assert all(n >= 2 for _, n in traces), f"a 1-point trace renders as invisible: {traces}"

    # Scope all DB queries to THIS test's zone projects (shared module-level DB means
    # other tests may have left rows for the same trench IDs in different projects).
    zone_project_ids = [uuid.UUID(b["project_id"]) for b in commit1["batches"]]

    # CHECK 3: trenches flat; ARTR001 far end at Z 299.13, not ~339
    db.expire_all()
    artr = db.query(Trench).filter(
        Trench.trench_id == "ARTR001",
        Trench.project_id.in_(zone_project_ids),
        Trench.superseded_by.is_(None),
    ).order_by(Trench.point_order).all()
    assert len(artr) == 2, f"expected 2 ARTR001 points, got {len(artr)}"
    zs = [t.elevation for t in artr]
    assert abs(zs[0] - 299.13) < 1e-6, f"start elevation mismatch: {zs[0]}"
    assert abs(zs[1] - 299.13) < 1e-6, f"end elevation should equal start (flat), got {zs}"
    # Check no trench floats (all point_order=1 have same elevation as point_order=0)
    this_test_trenches = db.query(Trench).filter(
        Trench.project_id.in_(zone_project_ids), Trench.superseded_by.is_(None)
    ).all()
    floating = [
        t.trench_id for t in this_test_trenches
        if t.point_order == 1 and t.elevation is not None
        and abs(t.elevation - next(
            x.elevation for x in db.query(Trench).filter(
                Trench.trench_id == t.trench_id,
                Trench.project_id == t.project_id,
                Trench.point_order == 0,
                Trench.superseded_by.is_(None)).all()
        )) > 1e-6
    ]
    assert floating == [], f"these trenches float above collar: {floating}"

    active_before = db.query(Trench).filter(
        Trench.project_id.in_(zone_project_ids), Trench.superseded_by.is_(None)
    ).count()
    collars_before = db.query(Collar).filter(
        Collar.project_id.in_(zone_project_ids), Collar.superseded_by.is_(None)
    ).count()
    assert active_before == 44, f"expected 44 active trench rows (22 * 2), got {active_before}"
    assert collars_before == 3, f"expected 3 active collars, got {collars_before}"

    # CHECK 4: re-upload changes no counts, no duplicates
    _, commit2 = upload_and_commit()
    db.expire_all()
    active_after = db.query(Trench).filter(
        Trench.project_id.in_(zone_project_ids), Trench.superseded_by.is_(None)
    ).count()
    collars_after = db.query(Collar).filter(
        Collar.project_id.in_(zone_project_ids), Collar.superseded_by.is_(None)
    ).count()
    zone_projects_after = db.query(Project).filter(
        Project.id.in_(zone_project_ids)
    ).count()
    assert active_after == active_before, f"re-upload duplicated trenches: {active_before}->{active_after}"
    assert collars_after == collars_before, f"re-upload duplicated collars: {collars_before}->{collars_after}"
    assert zone_projects_after == len(zone_project_ids), "re-upload must not change zone project count"
