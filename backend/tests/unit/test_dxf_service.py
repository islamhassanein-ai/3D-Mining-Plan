import pytest
import ezdxf
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
from backend.src.models.wireframe import Wireframe
from backend.src.services.dxf_service import parse_dxf_wireframe

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
    # Make sure all tables are created
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    # Clean tables
    db.query(User).delete()
    db.query(Project).delete()
    db.query(Wireframe).delete()
    db.commit()
    db.close()
    yield

def test_parse_valid_dxf_3dface():
    doc = ezdxf.new('R2000')
    msp = doc.modelspace()
    
    # Add a quad 3DFACE (which should split into 2 triangles)
    msp.add_3dface([(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1.0, 0.0), (0.0, 1.0, 0.0)])
    
    # Add a triangle 3DFACE (which should be 1 triangle)
    msp.add_3dface([(0.0, 0.0, 1.0), (1.0, 0.0, 1.0), (0.0, 1.0, 1.0), (0.0, 1.0, 1.0)])
    
    out = io.StringIO()
    doc.write(out)
    dxf_bytes = out.getvalue().encode('utf-8')
    
    vertices, faces, errors = parse_dxf_wireframe(dxf_bytes)
    assert len(errors) == 0
    assert len(vertices) == 7
    assert len(faces) == 3

def test_parse_invalid_dxf():
    vertices, faces, errors = parse_dxf_wireframe(b"corrupt dxf file content")
    assert len(errors) > 0
    assert len(vertices) == 0
    assert len(faces) == 0

def test_parse_empty_dxf():
    doc = ezdxf.new('R2000')
    out = io.StringIO()
    doc.write(out)
    dxf_bytes = out.getvalue().encode('utf-8')
    
    vertices, faces, errors = parse_dxf_wireframe(dxf_bytes)
    assert len(errors) > 0
    assert "No 3D geometry" in errors[0]

def test_dxf_upload_integration():
    db = TestingSessionLocal()
    user = User(id=uuid.uuid4(), email="dxf_tester@example.com", role="owner")
    proj = Project(id=uuid.uuid4(), name="Prospect Epsilon", owner_id=user.id)
    db.add(user)
    db.add(proj)
    db.commit()
    
    token = create_access_token(data={"sub": user.email, "role": user.role, "user_id": str(user.id)})
    headers = {"Authorization": f"Bearer {token}"}
    
    # 1. Create a valid DXF drawing
    doc = ezdxf.new('R2000')
    msp = doc.modelspace()
    msp.add_3dface([(10.0, 20.0, 30.0), (11.0, 20.0, 30.0), (11.0, 21.0, 30.0), (10.0, 21.0, 30.0)])
    out = io.StringIO()
    doc.write(out)
    dxf_bytes = out.getvalue().encode('utf-8')
    
    # 2. Upload wireframe DXF
    file_payload = io.BytesIO(dxf_bytes)
    res_upload = client.post(
        f"/projects/{proj.id}/wireframes?name=Vein_DXF&solid_type=vein_solid",
        files={"file": ("vein.dxf", file_payload, "application/octet-stream")},
        headers=headers
    )
    assert res_upload.status_code == 200, res_upload.text
    upload_data = res_upload.json()
    assert upload_data["name"] == "Vein_DXF"
    
    # 3. Retrieve project scene and verify it contains pre-parsed vertices/faces
    res_scene = client.get(f"/projects/{proj.id}/scene", headers=headers)
    assert res_scene.status_code == 200
    scene_data = res_scene.json()
    assert len(scene_data["wireframes"]) == 1
    wire = scene_data["wireframes"][0]
    assert wire["name"] == "Vein_DXF"
    assert "vertices" in wire
    assert "faces" in wire
    assert len(wire["vertices"]) == 4
    assert len(wire["faces"]) == 2
