import pytest
import io
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
from backend.src.models.structural_reading import StructuralReading
from backend.src.models.import_batch import ImportBatch

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
    # Delete children before parents so FK enforcement (conftest.py PRAGMA,
    # matching PostgreSQL) does not reject the cleanup.
    from backend.src.models.collar import Collar
    from backend.src.models.survey import Survey
    from backend.src.models.assay_interval import AssayInterval
    from backend.src.models.lithology_interval import LithologyInterval
    from backend.src.models.share_link import ShareLink
    from backend.src.models.qaqc_standard import QaqcStandard
    from backend.src.models.wireframe import Wireframe
    from backend.src.models.trench import Trench
    db.query(AssayInterval).delete()
    db.query(LithologyInterval).delete()
    db.query(Survey).delete()
    db.query(Collar).delete()
    db.query(Trench).delete()
    db.query(Wireframe).delete()
    db.query(StructuralReading).delete()
    db.query(QaqcStandard).delete()
    db.query(ShareLink).delete()
    db.query(ImportBatch).delete()
    db.query(Project).delete()
    db.query(User).delete()
    db.commit()
    db.close()
    yield

def test_structural_reading_validation_and_creation():
    db = TestingSessionLocal()
    user = User(id=uuid.uuid4(), email="struct_tester@example.com", role="owner")
    proj = Project(id=uuid.uuid4(), name="Struct Prospect", owner_id=user.id, utm_zone="36N")
    db.add(user)
    db.add(proj)
    db.commit()
    
    token = create_access_token(data={"sub": user.email, "role": user.role, "user_id": str(user.id)})
    headers = {"Authorization": f"Bearer {token}"}
    
    # 1. Post with invalid dip (Should fail 400)
    res_bad_dip = client.post(
        f"/projects/{proj.id}/structural",
        json={
            "reading_type": "fault_trace",
            "easting": 350000.0,
            "northing": 2800000.0,
            "elevation": 100.0,
            "dip": 95.0,
            "strike": 180.0
        },
        headers=headers
    )
    assert res_bad_dip.status_code == 400
    assert "Dip must be between" in res_bad_dip.text
    
    # 2. Post with invalid strike (Should fail 400)
    res_bad_strike = client.post(
        f"/projects/{proj.id}/structural",
        json={
            "reading_type": "fault_trace",
            "easting": 350000.0,
            "northing": 2800000.0,
            "elevation": 100.0,
            "dip": 45.0,
            "strike": 370.0
        },
        headers=headers
    )
    assert res_bad_strike.status_code == 400
    assert "Strike must be between" in res_bad_strike.text
    
    # 3. Post valid reading (Should succeed 201)
    res_ok = client.post(
        f"/projects/{proj.id}/structural",
        json={
            "reading_type": "fault_trace",
            "easting": 350000.0,
            "northing": 2800000.0,
            "elevation": 100.0,
            "dip": 45.0,
            "strike": 180.0
        },
        headers=headers
    )
    assert res_ok.status_code == 201
    res_data = res_ok.json()
    assert res_data["reading_type"] == "fault_trace"
    
    # 4. List structural readings
    res_list = client.get(f"/projects/{proj.id}/structural", headers=headers)
    assert res_list.status_code == 200
    list_data = res_list.json()
    assert len(list_data) == 1
    assert list_data[0]["dip"] == 45.0

def test_structural_reading_bulk_import():
    db = TestingSessionLocal()
    user = User(id=uuid.uuid4(), email="struct_tester2@example.com", role="owner")
    proj = Project(id=uuid.uuid4(), name="Struct Prospect 2", owner_id=user.id, utm_zone="36N")
    db.add(user)
    db.add(proj)
    db.commit()
    
    token = create_access_token(data={"sub": user.email, "role": user.role, "user_id": str(user.id)})
    headers = {"Authorization": f"Bearer {token}"}
    
    csv_data = b"reading_type,easting,northing,elevation,dip,strike\ndip_strike,350000,2800000,105,30,120\nfault_trace,350100,2800100,110,60,240"
    file_payload = io.BytesIO(csv_data)
    
    res_import = client.post(
        f"/projects/{proj.id}/structural/import",
        files={"file": ("readings.csv", file_payload, "text/csv")},
        headers=headers
    )
    assert res_import.status_code == 201, res_import.text
    assert res_import.json()["count"] == 2
    
    # List and verify import
    res_list = client.get(f"/projects/{proj.id}/structural", headers=headers)
    assert res_list.status_code == 200
    list_data = res_list.json()
    assert len(list_data) == 2
    assert list_data[0]["reading_type"] == "dip_strike"
    assert list_data[1]["reading_type"] == "fault_trace"


def _project_with_token(email, name):
    db = TestingSessionLocal()
    user = User(id=uuid.uuid4(), email=email, role="owner")
    proj = Project(id=uuid.uuid4(), name=name, owner_id=user.id, utm_zone="36N")
    db.add(user)
    db.add(proj)
    db.commit()
    token = create_access_token(data={"sub": user.email, "role": user.role, "user_id": str(user.id)})
    proj_id = proj.id
    db.close()
    return proj_id, {"Authorization": f"Bearer {token}"}


CSV_TWO_ROWS = (
    b"reading_type,easting,northing,elevation,dip,strike\n"
    b"dip_strike,350000,2800000,105,30,120\n"
    b"fault_trace,350100,2800100,110,60,240"
)


def test_delete_single_structural_reading():
    proj_id, headers = _project_with_token("struct_del@example.com", "Struct Delete")

    created = client.post(
        f"/projects/{proj_id}/structural",
        json={"reading_type": "fault_trace", "easting": 1.0, "northing": 2.0,
              "elevation": 3.0, "dip": 45.0, "strike": 180.0},
        headers=headers
    ).json()

    res = client.delete(f"/projects/{proj_id}/structural/{created['id']}", headers=headers)
    assert res.status_code == 204, res.text

    # Gone from the read path that feeds the scene and the planner.
    assert client.get(f"/projects/{proj_id}/structural", headers=headers).json() == []

    # Deleting it again is a 404, not a second silent success.
    assert client.delete(f"/projects/{proj_id}/structural/{created['id']}", headers=headers).status_code == 404
    # A non-UUID id is a miss, not a 500.
    assert client.delete(f"/projects/{proj_id}/structural/not-a-uuid", headers=headers).status_code == 404


def test_delete_all_structural_readings():
    proj_id, headers = _project_with_token("struct_delall@example.com", "Struct Delete All")

    client.post(
        f"/projects/{proj_id}/structural/import",
        files={"file": ("readings.csv", io.BytesIO(CSV_TWO_ROWS), "text/csv")},
        headers=headers
    )
    res = client.delete(f"/projects/{proj_id}/structural", headers=headers)
    assert res.status_code == 200, res.text
    assert res.json()["count"] == 2
    assert client.get(f"/projects/{proj_id}/structural", headers=headers).json() == []


def test_import_replace_mode_supersedes_instead_of_duplicating():
    """The duplicate-on-re-import case: a corrected CSV must not stack."""
    proj_id, headers = _project_with_token("struct_replace@example.com", "Struct Replace")

    client.post(
        f"/projects/{proj_id}/structural/import",
        files={"file": ("readings.csv", io.BytesIO(CSV_TWO_ROWS), "text/csv")},
        headers=headers
    )

    # Default (append) stacks -- this is the behaviour replace mode exists to avoid.
    client.post(
        f"/projects/{proj_id}/structural/import",
        files={"file": ("readings.csv", io.BytesIO(CSV_TWO_ROWS), "text/csv")},
        headers=headers
    )
    assert len(client.get(f"/projects/{proj_id}/structural", headers=headers).json()) == 4

    corrected = (
        b"reading_type,easting,northing,elevation,dip,strike\n"
        b"dip_strike,350000,2800000,105,35,125"
    )
    res = client.post(
        f"/projects/{proj_id}/structural/import?mode=replace",
        files={"file": ("corrected.csv", io.BytesIO(corrected), "text/csv")},
        headers=headers
    )
    assert res.status_code == 201, res.text
    assert res.json()["count"] == 1
    assert res.json()["replaced"] == 4

    remaining = client.get(f"/projects/{proj_id}/structural", headers=headers).json()
    assert len(remaining) == 1
    assert remaining[0]["dip"] == 35.0


def test_import_replace_mode_refuses_to_wipe_on_an_empty_csv():
    proj_id, headers = _project_with_token("struct_empty@example.com", "Struct Empty")

    client.post(
        f"/projects/{proj_id}/structural/import",
        files={"file": ("readings.csv", io.BytesIO(CSV_TWO_ROWS), "text/csv")},
        headers=headers
    )

    # Header present so it parses, but every data row is unusable.
    junk = (
        b"reading_type,easting,northing,elevation,dip,strike\n"
        b"dip_strike,350000,2800000,105,,\n"
    )
    res = client.post(
        f"/projects/{proj_id}/structural/import?mode=replace",
        files={"file": ("junk.csv", io.BytesIO(junk), "text/csv")},
        headers=headers
    )
    assert res.status_code == 400
    assert "left untouched" in res.text
    # The original readings survived.
    assert len(client.get(f"/projects/{proj_id}/structural", headers=headers).json()) == 2
