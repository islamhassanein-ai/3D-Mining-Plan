import pytest
import shapefile
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
from backend.src.models.trench import Trench
from backend.src.models.wireframe import Wireframe
from backend.src.services.shapefile_service import parse_trench_shapefile, parse_topography_shapefile, check_shapefile_crs

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
    db.query(Trench).delete()
    db.query(Wireframe).delete()
    db.commit()
    db.close()
    yield

def test_parse_trench_shapefile():
    shp = io.BytesIO()
    shx = io.BytesIO()
    dbf = io.BytesIO()
    
    w = shapefile.Writer(shp=shp, shx=shx, dbf=dbf, shapeType=shapefile.POINT)
    w.field('TRENCH_ID', 'C', size=50)
    w.field('GRADE_VAL', 'N', decimal=4)
    w.point(100.0, 200.0)
    w.record('TR001', 2.34)
    w.close()
    
    rows, errors = parse_trench_shapefile(shp.getvalue(), dbf.getvalue(), shx.getvalue())
    assert len(errors) == 0
    assert len(rows) == 1
    assert rows[0]['trench_id'] == 'TR001'
    assert rows[0]['easting'] == 100.0
    assert rows[0]['northing'] == 200.0
    assert rows[0]['grade_value'] == 2.34

def test_parse_topography_shapefile():
    shp = io.BytesIO()
    shx = io.BytesIO()
    dbf = io.BytesIO()
    
    w = shapefile.Writer(shp=shp, shx=shx, dbf=dbf, shapeType=shapefile.POINT)
    w.field('ID', 'N')
    w.point(500.0, 600.0)
    w.record(1)
    w.close()
    
    points, errors = parse_topography_shapefile(shp.getvalue(), dbf.getvalue(), shx.getvalue())
    assert len(errors) == 0
    assert len(points) == 1
    assert points[0]['easting'] == 500.0
    assert points[0]['northing'] == 600.0

def test_check_shapefile_crs():
    prj = b'PROJCS["WGS 84 / UTM zone 36N",GEOGCS["WGS 84"...]]'
    res = check_shapefile_crs(prj, "36N")
    assert res["valid"] is True
    
    res_mismatch = check_shapefile_crs(prj, "37N")
    assert res_mismatch["valid"] is False
    assert "CRS mismatch" in res_mismatch["message"]
    
    res_missing = check_shapefile_crs(None, "36N")
    assert res_missing["valid"] is False
    assert "Missing .prj file" in res_missing["message"]
    
    res_ambig = check_shapefile_crs(b'GEOGCS["GCS_WGS_1984"...]', "36N")
    assert res_ambig["valid"] is False
    assert "Ambiguous CRS" in res_ambig["message"]

def test_shapefile_trench_upload_integration():
    db = TestingSessionLocal()
    user = User(id=uuid.uuid4(), email="shp_tester@example.com", role="owner")
    proj = Project(id=uuid.uuid4(), name="Prospect Delta", owner_id=user.id, utm_zone="36N")
    db.add(user)
    db.add(proj)
    db.commit()
    
    token = create_access_token(data={"sub": user.email, "role": user.role, "user_id": str(user.id)})
    headers = {"Authorization": f"Bearer {token}"}
    
    # Create Shapefile data
    shp = io.BytesIO()
    shx = io.BytesIO()
    dbf = io.BytesIO()
    w = shapefile.Writer(shp=shp, shx=shx, dbf=dbf, shapeType=shapefile.POINT)
    w.field('TRENCH_ID', 'C', size=50)
    w.field('GRADE_VAL', 'N', decimal=4)
    w.point(350000.0, 2800000.0)
    w.record('TR01', 1.25)
    w.close()
    
    # 1. Post without PRJ and without confirm_crs (Should return 400)
    response_fail = client.post(
        f"/projects/{proj.id}/trenches/shapefile",
        files={
            "shp_file": ("trench.shp", io.BytesIO(shp.getvalue()), "application/octet-stream"),
            "dbf_file": ("trench.dbf", io.BytesIO(dbf.getvalue()), "application/octet-stream"),
            "shx_file": ("trench.shx", io.BytesIO(shx.getvalue()), "application/octet-stream")
        },
        headers=headers
    )
    assert response_fail.status_code == 400
    assert "Missing .prj file" in response_fail.text
    
    # 2. Post with confirm_crs=True (Should succeed)
    response_ok = client.post(
        f"/projects/{proj.id}/trenches/shapefile?confirm_crs=true",
        files={
            "shp_file": ("trench.shp", io.BytesIO(shp.getvalue()), "application/octet-stream"),
            "dbf_file": ("trench.dbf", io.BytesIO(dbf.getvalue()), "application/octet-stream"),
            "shx_file": ("trench.shx", io.BytesIO(shx.getvalue()), "application/octet-stream")
        },
        headers=headers
    )
    assert response_ok.status_code == 200, response_ok.text
    assert response_ok.json()["count"] == 1
    
    # Verify Trench record exists in database
    db = TestingSessionLocal()
    trenches = db.query(Trench).filter(Trench.project_id == proj.id).all()
    assert len(trenches) == 1
    assert trenches[0].trench_id == "TR01"
    assert trenches[0].easting == 350000.0
