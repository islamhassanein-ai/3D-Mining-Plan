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
from backend.src.models.import_batch import ImportBatch
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

app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_overrides():
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()

def test_scene_empty_project():
    db = TestingSessionLocal()
    # Create test user
    user = User(id=uuid.uuid4(), email="scene_tester@example.com", role="owner")
    db.add(user)
    # Create project
    proj = Project(id=uuid.uuid4(), name="Empty Project", utm_zone="36N", owner_id=user.id)
    db.add(proj)
    db.commit()

    token = create_access_token(data={"sub": user.email, "role": user.role, "user_id": str(user.id)})
    headers = {"Authorization": f"Bearer {token}"}

    response = client.get(f"/projects/{proj.id}/scene", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Empty Project"
    assert data["drillholes"] == []
    assert data["trenches"] == []
    assert data["wireframes"] == []

def test_scene_with_drillhole():
    db = TestingSessionLocal()
    user = User(id=uuid.uuid4(), email="scene_tester2@example.com", role="owner")
    db.add(user)
    
    proj = Project(id=uuid.uuid4(), name="Drillhole Project", utm_zone="36N", owner_id=user.id)
    db.add(proj)
    db.commit()
    
    batch = ImportBatch(id=uuid.uuid4(), project_id=proj.id, source_file="dummy", status="committed")
    db.add(batch)
    db.commit()
    
    # 1. Add collar
    collar = Collar(
        id=uuid.uuid4(),
        project_id=proj.id,
        hole_id="DH_01",
        easting=100.0,
        northing=200.0,
        elevation=50.0,
        utm_zone="36N",
        import_batch_id=batch.id
    )
    db.add(collar)
    db.commit()
    
    # 2. Add surveys (curved hole)
    s1 = Survey(id=uuid.uuid4(), collar_id=collar.id, depth=0.0, dip=-90.0, azimuth=0.0)
    s2 = Survey(id=uuid.uuid4(), collar_id=collar.id, depth=100.0, dip=-45.0, azimuth=90.0) # curves East
    db.add(s1)
    db.add(s2)
    
    # 3. Add assay interval
    assay = AssayInterval(
        id=uuid.uuid4(),
        collar_id=collar.id,
        from_depth=0.0,
        to_depth=50.0,
        grade_value=2.5,
        grade_unit="ppm",
        import_batch_id=batch.id
    )
    db.add(assay)
    
    # 4. Add lithology interval
    lith = LithologyInterval(
        id=uuid.uuid4(),
        collar_id=collar.id,
        from_depth=50.0,
        to_depth=100.0,
        lith_code="SND"
    )
    db.add(lith)
    db.commit()
    
    token = create_access_token(data={"sub": user.email, "role": user.role, "user_id": str(user.id)})
    headers = {"Authorization": f"Bearer {token}"}
    
    response = client.get(f"/projects/{proj.id}/scene", headers=headers)
    assert response.status_code == 200
    data = response.json()
    
    assert len(data["drillholes"]) == 1
    dh = data["drillholes"][0]
    assert dh["hole_id"] == "DH_01"
    assert len(dh["trace"]) == 2
    
    # Assay validation
    assert len(dh["assays"]) == 1
    ass_data = dh["assays"][0]
    assert ass_data["color"] == "#fbbf24" # 2.5 ppm is Yellow/Orange
    assert ass_data["start_pos"] == [100.0, 200.0, 50.0] # start at collar
    # End pos at 50m should be interpolated somewhere between depth 0 and 100
    assert ass_data["end_pos"][2] < 50.0 # elevation should decrease
    assert ass_data["end_pos"][0] > 100.0 # easting should increase since hole curves East
    
    # Lithology validation
    assert len(dh["lithologies"]) == 1
    lith_data = dh["lithologies"][0]
    assert lith_data["lith_code"] == "SND"
    assert math_close(lith_data["start_pos"][0], ass_data["end_pos"][0])
    assert math_close(lith_data["start_pos"][2], ass_data["end_pos"][2])

def math_close(a, b, tol=1e-5):
    return abs(a - b) < tol
