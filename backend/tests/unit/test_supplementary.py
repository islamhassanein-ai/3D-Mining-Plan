import pytest
import uuid
import io
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.src.db.session import Base, get_db
from backend.src.api.main import app
from backend.src.api.auth import create_access_token
from backend.src.models.user import User
from backend.src.models.project import Project
from backend.src.models.trench import Trench
from backend.src.models.wireframe import Wireframe

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

def test_supplementary_uploads_and_scene_integration():
    db = TestingSessionLocal()
    # Create test user
    user = User(id=uuid.uuid4(), email="supp_tester@example.com", role="owner")
    db.add(user)
    # Create project
    proj = Project(id=uuid.uuid4(), name="Supplementary Test Project", owner_id=user.id)
    db.add(proj)
    db.commit()

    token = create_access_token(data={"sub": user.email, "role": user.role, "user_id": str(user.id)})
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Upload Topography
    topo_file = io.BytesIO(b"easting,northing,elevation\n350000,2800000,105\n350100,2800100,110")
    response_topo = client.post(
        f"/projects/{proj.id}/topography",
        files={"file": ("topo.csv", topo_file, "text/csv")},
        headers=headers
    )
    assert response_topo.status_code == 200
    topo_data = response_topo.json()
    assert topo_data["solid_type"] == "topography"
    assert "topo.csv" in topo_data["name"]

    # 2. Upload Trenches
    trench_csv = b"trench_id,easting,northing,elevation,grade_value\nTR01,350000,2800000,102,1.25\nTR02,350010,2800010,103,2.5"
    trench_file = io.BytesIO(trench_csv)
    response_trench = client.post(
        f"/projects/{proj.id}/trenches",
        files={"file": ("trenches.csv", trench_file, "text/csv")},
        headers=headers
    )
    assert response_trench.status_code == 200
    assert response_trench.json()["count"] == 2

    # 3. Upload Wireframe
    wire_file = io.BytesIO(b"v 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 3")
    response_wire = client.post(
        f"/projects/{proj.id}/wireframes?name=Main_Vein_Solid&solid_type=vein_solid",
        files={"file": ("vein.obj", wire_file, "application/octet-stream")},
        headers=headers
    )
    assert response_wire.status_code == 200
    wire_data = response_wire.json()
    assert wire_data["name"] == "Main_Vein_Solid"
    assert wire_data["solid_type"] == "vein_solid"

    # 4. Fetch Scene and verify integrated lists
    response_scene = client.get(f"/projects/{proj.id}/scene", headers=headers)
    assert response_scene.status_code == 200
    scene_data = response_scene.json()
    
    assert scene_data["topography_ref"] == topo_data["file_ref"]
    assert len(scene_data["trenches"]) == 2
    assert scene_data["trenches"][0]["trench_id"] == "TR01"
    assert scene_data["trenches"][0]["grade_value"] == 1.25
    
    # We should have 2 wireframes in total (one for topography and one for vein solid)
    assert len(scene_data["wireframes"]) == 2
    wireframe_names = {w["name"] for w in scene_data["wireframes"]}
    assert "Main_Vein_Solid" in wireframe_names
