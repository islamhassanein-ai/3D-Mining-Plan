import pytest
import io
import os
import uuid
import zipfile
import json
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
from backend.src.models.wireframe import Wireframe
from backend.src.storage.local_filesystem import LocalFilesystemStorage

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
    db.query(Collar).delete()
    db.query(Survey).delete()
    db.query(AssayInterval).delete()
    db.query(LithologyInterval).delete()
    db.query(Wireframe).delete()
    db.commit()
    db.close()
    yield

def test_all_exports_integration():
    db = TestingSessionLocal()
    user = User(id=uuid.uuid4(), email="export_tester@example.com", role="owner")
    proj = Project(id=uuid.uuid4(), name="Export Prospect", owner_id=user.id, utm_zone="36N")
    
    # Add project metadata and a collar
    collar = Collar(
        id=uuid.uuid4(),
        project_id=proj.id,
        hole_id="DH001",
        easting=350000.0,
        northing=2800000.0,
        elevation=100.0,
        utm_zone="36N",
        import_batch_id=uuid.uuid4()
    )
    survey = Survey(
        id=uuid.uuid4(),
        collar_id=collar.id,
        depth=50.0,
        dip=-60.0,
        azimuth=180.0
    )
    
    db.add(user)
    db.add(proj)
    db.add(collar)
    db.add(survey)
    db.commit()
    
    token = create_access_token(data={"sub": user.email, "role": user.role, "user_id": str(user.id)})
    headers = {"Authorization": f"Bearer {token}"}
    
    # 1. Test CSV Export (ZIP archive)
    res_csv = client.get(f"/projects/{proj.id}/export/data.csv", headers=headers)
    assert res_csv.status_code == 200
    assert res_csv.headers["content-type"] == "application/zip"
    
    # Read zip content
    zip_data = io.BytesIO(res_csv.content)
    with zipfile.ZipFile(zip_data) as zf:
        namelist = zf.namelist()
        assert "collars.csv" in namelist
        assert "surveys.csv" in namelist
        assert "assays.csv" in namelist
        assert "lithologies.csv" in namelist
        assert "metadata.json" in namelist
        
        meta = json.loads(zf.read("metadata.json").decode('utf-8'))
        assert meta["project_name"] == "Export Prospect"
        assert meta["counts"]["collars"] == 1
        
    # 2. Test PDF Cross Section Export
    res_pdf = client.get(f"/projects/{proj.id}/export/section.pdf", headers=headers)
    assert res_pdf.status_code == 200
    assert res_pdf.headers["content-type"] == "application/pdf"
    assert res_pdf.content.startswith(b"%PDF-")
    
    # 3. Test DXF Wireframe Export (will return 400 since no DXF wireframes were seeded)
    res_dxf_empty = client.get(f"/projects/{proj.id}/export/wireframes.dxf", headers=headers)
    assert res_dxf_empty.status_code == 400
    assert "No valid parsed 3D DXF wireframes" in res_dxf_empty.text
    
    # Now seed a wireframe with companion geometry
    storage = LocalFilesystemStorage()
    file_ref = "test_wf_ref.dxf"
    geom_bytes = json.dumps({
        "vertices": [[350000, 2800000, 100], [350100, 2800000, 100], [350050, 2800050, 150]],
        "faces": [[0, 1, 2]]
    }).encode('utf-8')
    with open(os.path.join(storage.base_dir, f"{file_ref}_geom.json"), "wb") as f:
        f.write(geom_bytes)
        
    wf = Wireframe(
        id=uuid.uuid4(),
        project_id=proj.id,
        name="Mock_Vein",
        solid_type="vein_solid",
        file_ref=file_ref
    )
    db.add(wf)
    db.commit()
    
    # Run DXF export again
    res_dxf = client.get(f"/projects/{proj.id}/export/wireframes.dxf", headers=headers)
    assert res_dxf.status_code == 200
    assert res_dxf.headers["content-type"] == "application/dxf"
    assert b"SECTION" in res_dxf.content
    
    # Clean up file
    try:
        os.remove(os.path.join(storage.base_dir, f"{file_ref}_geom.json"))
    except Exception:
        pass


def test_csv_export_per_entity():
    """contracts/api.md specifies ?entity=collars|surveys|assays|lithologies
    for a single-entity CSV download, distinct from the all-in-one ZIP."""
    db = TestingSessionLocal()
    user = User(id=uuid.uuid4(), email="export_entity_tester@example.com", role="owner")
    proj = Project(id=uuid.uuid4(), name="Entity Export Prospect", owner_id=user.id, utm_zone="36N")
    collar = Collar(
        id=uuid.uuid4(),
        project_id=proj.id,
        hole_id="DH001",
        easting=350000.0,
        northing=2800000.0,
        elevation=100.0,
        utm_zone="36N",
        import_batch_id=uuid.uuid4()
    )
    survey = Survey(id=uuid.uuid4(), collar_id=collar.id, depth=10.0, dip=-60.0, azimuth=90.0)
    db.add(user)
    db.add(proj)
    db.add(collar)
    db.add(survey)
    db.commit()

    token = create_access_token(data={"sub": user.email, "role": user.role, "user_id": str(user.id)})
    headers = {"Authorization": f"Bearer {token}"}

    res = client.get(f"/projects/{proj.id}/export/data.csv?entity=collars", headers=headers)
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/csv")
    text = res.content.decode("utf-8")
    assert "hole_id" in text.splitlines()[0]
    assert "DH001" in text

    res_surveys = client.get(f"/projects/{proj.id}/export/data.csv?entity=surveys", headers=headers)
    assert res_surveys.status_code == 200
    assert "depth" in res_surveys.content.decode("utf-8").splitlines()[0]

    res_bad = client.get(f"/projects/{proj.id}/export/data.csv?entity=not_a_real_entity", headers=headers)
    assert res_bad.status_code == 400


def test_csv_export_preserves_grade_unit_and_bdl_status():
    """Regression test: the assay CSV export was silently dropping grade_unit
    and below_detection_limit. Re-importing that export would silently corrupt
    the data -- units would default to a wrong value and BDL rows would
    silently become non-BDL rows -- directly violating the constitution's
    Geological Data Integrity principle, even though the round-trip wouldn't
    raise any error."""
    from backend.src.services.csv_import import parse_assay_csv

    db = TestingSessionLocal()
    user = User(id=uuid.uuid4(), email="export_bdl_tester@example.com", role="owner")
    proj = Project(id=uuid.uuid4(), name="BDL Export Prospect", owner_id=user.id, utm_zone="36N")
    collar = Collar(
        id=uuid.uuid4(),
        project_id=proj.id,
        hole_id="DH001",
        easting=350000.0,
        northing=2800000.0,
        elevation=100.0,
        utm_zone="36N",
        import_batch_id=uuid.uuid4()
    )
    # A below-detection-limit sample reported in "%", to prove both fields
    # survive the export -- if either is dropped, this specific combination
    # would silently corrupt on re-import (unit defaults to "ppm", BDL flag
    # defaults to False).
    assay = AssayInterval(
        id=uuid.uuid4(),
        collar_id=collar.id,
        from_depth=0.0,
        to_depth=2.0,
        grade_value=0.01,
        grade_unit="%",
        below_detection_limit=True,
        import_batch_id=uuid.uuid4()
    )
    db.add(user)
    db.add(proj)
    db.add(collar)
    db.add(assay)
    db.commit()

    token = create_access_token(data={"sub": user.email, "role": user.role, "user_id": str(user.id)})
    headers = {"Authorization": f"Bearer {token}"}

    res_csv = client.get(f"/projects/{proj.id}/export/data.csv", headers=headers)
    assert res_csv.status_code == 200

    with zipfile.ZipFile(io.BytesIO(res_csv.content)) as zf:
        assays_csv_bytes = zf.read("assays.csv")

    header = assays_csv_bytes.decode("utf-8").splitlines()[0]
    assert "grade_unit" in header
    assert "below_detection_limit" in header

    # Prove it actually round-trips through the real Phase 0 CSV import parser,
    # not just that the column names are present.
    parsed_rows, errors = parse_assay_csv(assays_csv_bytes)
    assert not errors
    assert len(parsed_rows) == 1
    assert parsed_rows[0]["grade_unit"] == "%"
    assert parsed_rows[0]["below_detection_limit"] is True
