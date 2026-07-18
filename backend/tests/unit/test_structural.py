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
    db.query(User).delete()
    db.query(Project).delete()
    db.query(StructuralReading).delete()
    db.query(ImportBatch).delete()
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
