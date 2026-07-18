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

def test_get_collar_not_found():
    db = TestingSessionLocal()
    user = User(id=uuid.uuid4(), email="collar_tester@example.com", role="owner")
    db.add(user)
    db.commit()
    
    token = create_access_token(data={"sub": user.email, "role": user.role, "user_id": str(user.id)})
    headers = {"Authorization": f"Bearer {token}"}
    
    dummy_id = str(uuid.uuid4())
    response = client.get(f"/collars/{dummy_id}", headers=headers)
    assert response.status_code == 404

def test_get_collar_details_success():
    db = TestingSessionLocal()
    user = User(id=uuid.uuid4(), email="collar_tester2@example.com", role="owner")
    db.add(user)
    
    proj = Project(id=uuid.uuid4(), name="Prospect A", owner_id=user.id)
    db.add(proj)
    db.commit()
    
    batch = ImportBatch(id=uuid.uuid4(), project_id=proj.id, source_file="src", status="committed")
    db.add(batch)
    db.commit()
    
    collar = Collar(
        id=uuid.uuid4(),
        project_id=proj.id,
        hole_id="DH_99",
        easting=500.0,
        northing=600.0,
        elevation=20.0,
        utm_zone="36N",
        import_batch_id=batch.id
    )
    db.add(collar)
    db.commit()
    
    # Add survey
    s = Survey(id=uuid.uuid4(), collar_id=collar.id, depth=0.0, dip=-90.0, azimuth=0.0)
    db.add(s)
    
    # Add assay
    a = AssayInterval(
        id=uuid.uuid4(),
        collar_id=collar.id,
        from_depth=0.0,
        to_depth=2.5,
        grade_value=1.8,
        grade_unit="ppm",
        import_batch_id=batch.id
    )
    db.add(a)
    
    # Add lithology
    l = LithologyInterval(
        id=uuid.uuid4(),
        collar_id=collar.id,
        from_depth=2.5,
        to_depth=10.0,
        lith_code="SHL"
    )
    db.add(l)
    db.commit()
    
    token = create_access_token(data={"sub": user.email, "role": user.role, "user_id": str(user.id)})
    headers = {"Authorization": f"Bearer {token}"}
    
    response = client.get(f"/collars/{collar.id}", headers=headers)
    assert response.status_code == 200
    data = response.json()
    
    assert data["hole_id"] == "DH_99"
    assert data["easting"] == 500.0
    assert len(data["surveys"]) == 1
    assert len(data["assays"]) == 1
    assert len(data["lithologies"]) == 1
    
    # Test merged_intervals ordering
    merged = data["merged_intervals"]
    assert len(merged) == 2
    assert merged[0]["type"] == "assay"
    assert merged[0]["from_depth"] == 0.0
    assert merged[0]["to_depth"] == 2.5
    assert merged[1]["type"] == "lithology"
    assert merged[1]["from_depth"] == 2.5

def test_get_true_thickness_success():
    db = TestingSessionLocal()
    user = User(id=uuid.uuid4(), email="collar_tester3@example.com", role="owner")
    db.add(user)
    
    proj = Project(id=uuid.uuid4(), name="Prospect B", owner_id=user.id)
    db.add(proj)
    db.commit()
    
    batch = ImportBatch(id=uuid.uuid4(), project_id=proj.id, source_file="src", status="committed")
    db.add(batch)
    db.commit()
    
    collar = Collar(
        id=uuid.uuid4(),
        project_id=proj.id,
        hole_id="DH_99_TT",
        easting=500.0,
        northing=600.0,
        elevation=20.0,
        utm_zone="36N",
        import_batch_id=batch.id
    )
    db.add(collar)
    db.commit()
    
    # Vertical survey: dip = -90
    s = Survey(id=uuid.uuid4(), collar_id=collar.id, depth=0.0, dip=-90.0, azimuth=0.0)
    db.add(s)
    
    # 5m long assay interval
    a = AssayInterval(
        id=uuid.uuid4(),
        collar_id=collar.id,
        from_depth=0.0,
        to_depth=5.0,
        grade_value=2.0,
        grade_unit="ppm",
        import_batch_id=batch.id
    )
    db.add(a)
    db.commit()
    
    token = create_access_token(data={"sub": user.email, "role": user.role, "user_id": str(user.id)})
    headers = {"Authorization": f"Bearer {token}"}
    
    # Fetch true thickness for a horizontal vein (dip = 0, dip_dir = 0)
    # Perpendicular intersection, true thickness = apparent thickness (5.0m)
    response = client.get(
        f"/collars/{collar.id}/true-thickness?interval_id={a.id}&dip_direction=0&dip=0",
        headers=headers
    )
    assert response.status_code == 200
    data = response.json()
    assert abs(data["apparent_thickness"] - 5.0) < 1e-5
    assert abs(data["true_thickness"] - 5.0) < 1e-5
    
    # Fetch true thickness for an inclined vein (dip = 45, dip_dir = 90)
    # Cos(45) = 0.7071
    # True thickness = 5.0 * 0.7071 = 3.5355m
    response2 = client.get(
        f"/collars/{collar.id}/true-thickness?interval_id={a.id}&dip_direction=90&dip=45",
        headers=headers
    )
    assert response2.status_code == 200
    data2 = response2.json()
    assert abs(data2["true_thickness"] - (5.0 * math_cos(math_rad(45)))) < 1e-5

def math_rad(d):
    import math
    return math.radians(d)

def math_cos(r):
    import math
    return math.cos(r)
