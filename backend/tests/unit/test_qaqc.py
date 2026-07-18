import pytest
import uuid
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.src.db.session import Base, get_db
from backend.src.api.main import app
from backend.src.api.auth import create_access_token
from backend.src.models.user import User
from backend.src.models.project import Project
from backend.src.models.qaqc_standard import QaqcStandard
from backend.src.services.import_validation import validate_import_batch

# SQLite in-memory test database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_overrides():
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()

@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    db.query(User).delete()
    db.query(Project).delete()
    db.query(QaqcStandard).delete()
    db.commit()
    db.close()
    yield

def test_qaqc_standards_crud():
    db = TestingSessionLocal()
    user = User(id=uuid.uuid4(), email="qaqc_tester@example.com", role="owner")
    proj = Project(id=uuid.uuid4(), name="QAQC Prospect", owner_id=user.id, utm_zone="36N")
    db.add(user)
    db.add(proj)
    db.commit()
    
    token = create_access_token(data={"sub": user.email, "role": user.role, "user_id": str(user.id)})
    headers = {"Authorization": f"Bearer {token}"}
    
    # 1. Create standard
    res_create = client.post(
        f"/projects/{proj.id}/qaqc",
        json={
            "standard_name": "STD_GOLD_01",
            "expected_grade_min": 1.2,
            "expected_grade_max": 1.5,
            "grade_unit": "ppm"
        },
        headers=headers
    )
    assert res_create.status_code == 201
    assert res_create.json()["standard_name"] == "STD_GOLD_01"
    
    # 2. Duplicate standard creation should fail 400
    res_dup = client.post(
        f"/projects/{proj.id}/qaqc",
        json={
            "standard_name": "STD_GOLD_01",
            "expected_grade_min": 1.0,
            "expected_grade_max": 2.0,
            "grade_unit": "ppm"
        },
        headers=headers
    )
    assert res_dup.status_code == 400
    assert "Standard name already exists" in res_dup.text
    
    # 3. List standards
    res_list = client.get(f"/projects/{proj.id}/qaqc", headers=headers)
    assert res_list.status_code == 200
    assert len(res_list.json()) == 1
    assert res_list.json()[0]["expected_grade_min"] == 1.2

def test_qaqc_import_validation():
    collars = [{"hole_id": "DH01", "easting": 350000.0, "northing": 2800000.0, "elevation": 100.0}]
    surveys = []
    lithologies = []
    
    # QA/QC Standards registry
    qaqc_standards = [
        {
            "standard_name": "STD_GOLD_01",
            "expected_grade_min": 1.2,
            "expected_grade_max": 1.5,
            "grade_unit": "ppm"
        }
    ]
    
    # 1. Assay row with matching standard within range
    assays_ok = [
        {
            "hole_id": "DH01",
            "from_depth": 0.0,
            "to_depth": 2.0,
            "grade_value": 1.35,
            "grade_unit": "ppm",
            "below_detection_limit": False,
            "qaqc_type": "standard",
            "qaqc_standard": "STD_GOLD_01"
        }
    ]
    res_ok = validate_import_batch(collars, surveys, assays_ok, lithologies, qaqc_standards=qaqc_standards)
    assert res_ok["valid"] is True
    assert not res_ok["issues"]
    assert assays_ok[0].get("qaqc_flag") == "standard"

    # 2. Assay row with matching standard outside range (should flag warning but remain valid overall)
    assays_bad = [
        {
            "hole_id": "DH01",
            "from_depth": 0.0,
            "to_depth": 2.0,
            "grade_value": 2.5, # > 1.5 expected
            "grade_unit": "ppm",
            "below_detection_limit": False,
            "qaqc_type": "standard",
            "qaqc_standard": "STD_GOLD_01"
        }
    ]
    res_bad = validate_import_batch(collars, surveys, assays_bad, lithologies, qaqc_standards=qaqc_standards)
    assert res_bad["valid"] is True # Warning does not block import
    assert len(res_bad["issues"]) == 1
    assert res_bad["issues"][0]["rule"] == "qaqc_standard_failed"
    assert assays_bad[0].get("qaqc_flag") == "standard_failed"

    # 3. Assay row referencing a standard name with no configured reference at
    # all must be flagged "unconfigured", never silently skipped.
    assays_unconfigured = [
        {
            "hole_id": "DH01",
            "from_depth": 0.0,
            "to_depth": 2.0,
            "grade_value": 1.35,
            "grade_unit": "ppm",
            "below_detection_limit": False,
            "qaqc_type": "standard",
            "qaqc_standard": "STD_NOT_REGISTERED"
        }
    ]
    res_unconf = validate_import_batch(collars, surveys, assays_unconfigured, lithologies, qaqc_standards=qaqc_standards)
    assert res_unconf["issues"][0]["rule"] == "qaqc_standard_unconfigured"
    assert assays_unconfigured[0].get("qaqc_flag") == "unconfigured"

    # 4. Assay row referencing a real standard name but reported in a
    # *different* grade unit than the configured reference must also be
    # "unconfigured" -- a raw numeric comparison across units (e.g. ppm vs %)
    # would be meaningless.
    assays_wrong_unit = [
        {
            "hole_id": "DH01",
            "from_depth": 0.0,
            "to_depth": 2.0,
            "grade_value": 1.35,
            "grade_unit": "%",  # standard is configured in "ppm"
            "below_detection_limit": False,
            "qaqc_type": "standard",
            "qaqc_standard": "STD_GOLD_01"
        }
    ]
    res_wrong_unit = validate_import_batch(collars, surveys, assays_wrong_unit, lithologies, qaqc_standards=qaqc_standards)
    assert res_wrong_unit["issues"][0]["rule"] == "qaqc_standard_unconfigured"
    assert assays_wrong_unit[0].get("qaqc_flag") == "unconfigured"

    # 5. Duplicate and blank sample indicators are flagged as-is, with no
    # range comparison (there is no expected range for them).
    assays_dup_blank = [
        {
            "hole_id": "DH01",
            "from_depth": 0.0,
            "to_depth": 2.0,
            "grade_value": 1.30,
            "grade_unit": "ppm",
            "below_detection_limit": False,
            "qaqc_type": "duplicate",
            "qaqc_standard": None
        },
        {
            "hole_id": "DH01",
            "from_depth": 2.0,
            "to_depth": 4.0,
            "grade_value": 0.01,
            "grade_unit": "ppm",
            "below_detection_limit": False,
            "qaqc_type": "blank",
            "qaqc_standard": None
        },
        {
            "hole_id": "DH01",
            "from_depth": 4.0,
            "to_depth": 6.0,
            "grade_value": 0.9,
            "grade_unit": "ppm",
            "below_detection_limit": False,
            "qaqc_type": None,
            "qaqc_standard": None
        }
    ]
    res_dup_blank = validate_import_batch(collars, surveys, assays_dup_blank, lithologies, qaqc_standards=qaqc_standards)
    assert res_dup_blank["valid"] is True
    assert not res_dup_blank["issues"]
    assert assays_dup_blank[0].get("qaqc_flag") == "duplicate"
    assert assays_dup_blank[1].get("qaqc_flag") == "blank"
    assert assays_dup_blank[2].get("qaqc_flag") is None


def test_qaqc_flag_is_persisted_through_full_commit_flow():
    """Regression test: the QA/QC flag computed during import validation was
    being discarded when the import was actually committed -- every committed
    AssayInterval.qaqc_flag was NULL regardless of what validation computed.
    This exercises the real create_import -> commit_import path, not just the
    validate_import_batch pure function, since that's exactly where the bug
    was hiding."""
    from backend.src.models.collar import Collar
    from backend.src.models.assay_interval import AssayInterval

    db = TestingSessionLocal()
    user = User(id=uuid.uuid4(), email="qaqc_persist_tester@example.com", role="owner")
    proj = Project(id=uuid.uuid4(), name="QAQC Persistence Prospect", owner_id=user.id, utm_zone="36N")
    db.add(user)
    db.add(proj)
    db.commit()

    token = create_access_token(data={"sub": user.email, "role": user.role, "user_id": str(user.id)})
    headers = {"Authorization": f"Bearer {token}"}

    # Register a standard that this import's sample will fail against.
    client.post(
        f"/projects/{proj.id}/qaqc",
        json={
            "standard_name": "STD_GOLD_01",
            "expected_grade_min": 1.2,
            "expected_grade_max": 1.5,
            "grade_unit": "ppm"
        },
        headers=headers
    )

    collar_csv = b"hole_id,easting,northing,elevation,utm_zone\nDH01,350000.0,2800000.0,100.0,36N\n"
    # grade_value 2.5 is outside the standard's 1.2-1.5 range -> should persist as "standard_failed"
    assay_csv = b"hole_id,from_depth,to_depth,grade,grade_unit,qaqc_type,qaqc_standard\nDH01,0.0,2.0,2.5,ppm,standard,STD_GOLD_01\n"
    files = {
        "collar_file": ("collars.csv", collar_csv, "text/csv"),
        "assay_file": ("assays.csv", assay_csv, "text/csv"),
    }
    resp = client.post(f"/projects/{proj.id}/imports", files=files, headers=headers)
    assert resp.status_code == 201
    batch_id = resp.json()["import_batch_id"]

    commit_resp = client.post(
        f"/projects/{proj.id}/imports/{batch_id}/commit?utm_zone_confirm=36N&acknowledge_warnings=true",
        headers=headers
    )
    assert commit_resp.status_code == 200, commit_resp.text

    collar = db.query(Collar).filter(Collar.project_id == proj.id).first()
    assay = db.query(AssayInterval).filter(AssayInterval.collar_id == collar.id).first()
    assert assay.qaqc_flag == "standard_failed", (
        "qaqc_flag must survive the commit, not be silently dropped and left NULL"
    )


def test_qaqc_duplicate_and_blank_flags_persist_through_commit():
    """Duplicate and blank sample indicators in the assay CSV must produce a
    persisted qaqc_flag, not just the 'standard' path."""
    from backend.src.models.collar import Collar
    from backend.src.models.assay_interval import AssayInterval

    db = TestingSessionLocal()
    user = User(id=uuid.uuid4(), email="qaqc_dupblank_tester@example.com", role="owner")
    proj = Project(id=uuid.uuid4(), name="QAQC DupBlank Prospect", owner_id=user.id, utm_zone="36N")
    db.add(user)
    db.add(proj)
    db.commit()

    token = create_access_token(data={"sub": user.email, "role": user.role, "user_id": str(user.id)})
    headers = {"Authorization": f"Bearer {token}"}

    collar_csv = b"hole_id,easting,northing,elevation,utm_zone\nDH01,350000.0,2800000.0,100.0,36N\n"
    assay_csv = (
        b"hole_id,from_depth,to_depth,grade,grade_unit,qaqc_type\n"
        b"DH01,0.0,2.0,1.30,ppm,duplicate\n"
        b"DH01,2.0,4.0,0.01,ppm,blank\n"
    )
    files = {
        "collar_file": ("collars.csv", collar_csv, "text/csv"),
        "assay_file": ("assays.csv", assay_csv, "text/csv"),
    }
    resp = client.post(f"/projects/{proj.id}/imports", files=files, headers=headers)
    assert resp.status_code == 201
    batch_id = resp.json()["import_batch_id"]

    commit_resp = client.post(
        f"/projects/{proj.id}/imports/{batch_id}/commit?utm_zone_confirm=36N",
        headers=headers
    )
    assert commit_resp.status_code == 200, commit_resp.text

    collar = db.query(Collar).filter(Collar.project_id == proj.id).first()
    assays = db.query(AssayInterval).filter(AssayInterval.collar_id == collar.id).order_by(AssayInterval.from_depth).all()
    assert assays[0].qaqc_flag == "duplicate"
    assert assays[1].qaqc_flag == "blank"
