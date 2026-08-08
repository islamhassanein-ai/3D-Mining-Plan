"""Integration tests for the grade-analysis and grade-shell endpoints."""
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.src.api.auth import create_access_token
from backend.src.api.main import app
from backend.src.db.session import Base, get_db
from backend.src.models.assay_interval import AssayInterval
from backend.src.models.collar import Collar
from backend.src.models.import_batch import ImportBatch
from backend.src.models.project import Project
from backend.src.models.survey import Survey
from backend.src.models.user import User
from backend.src.models.wireframe import Wireframe

engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)


def _override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def _overrides():
    app.dependency_overrides[get_db] = _override_get_db
    yield
    app.dependency_overrides.clear()


client = TestClient(app)


def _ellipsoid(major=40.0, semi=40.0, minor=40.0, azimuth=0.0, dip=0.0):
    return {
        "range_major": major, "range_semi": semi, "range_minor": minor,
        "strike_azimuth": azimuth, "dip": dip,
    }


def _request(**overrides):
    body = {
        "name": "Test shell",
        "threshold": 1.0,
        "ellipsoid": _ellipsoid(),
        "sample_type_weights": {"DDH": 1.0},
        "cell_size": 10.0,
        "padding": 20.0,
        "min_samples": 1,
    }
    body.update(overrides)
    return body


@pytest.fixture
def project():
    """A project with a high-grade core inside a barren halo."""
    db = TestingSessionLocal()
    user = User(id=uuid.uuid4(), email=f"gs_{uuid.uuid4().hex}@example.com",
                role="owner")
    db.add(user)
    db.commit()

    proj = Project(id=uuid.uuid4(), name=f"GS {uuid.uuid4().hex[:6]}",
                   utm_zone="37N", owner_id=user.id)
    db.add(proj)
    db.commit()

    batch = ImportBatch(id=uuid.uuid4(), project_id=proj.id,
                        source_file="gs.csv", status="committed")
    db.add(batch)
    db.commit()

    # Nine vertical holes on a 40 m grid; the middle one is mineralised.
    for index, (east, north) in enumerate(
        [(e, n) for e in (0.0, 40.0, 80.0) for n in (0.0, 40.0, 80.0)]
    ):
        collar = Collar(
            id=uuid.uuid4(), project_id=proj.id, hole_id=f"DDH-{index:03d}",
            easting=east, northing=north, elevation=100.0, utm_zone="37N",
            import_batch_id=batch.id, hole_type="DD", hole_status="drilled",
        )
        db.add(collar)
        for depth in (0.0, 60.0):
            db.add(Survey(id=uuid.uuid4(), collar_id=collar.id, depth=depth,
                          dip=-90.0, azimuth=0.0,
                          desurvey_method="minimum_curvature"))
        mineralised = (east, north) == (40.0, 40.0)
        for from_depth in range(0, 60, 10):
            db.add(AssayInterval(
                id=uuid.uuid4(), collar_id=collar.id,
                from_depth=float(from_depth), to_depth=float(from_depth + 10),
                grade_value=8.0 if mineralised else 0.05,
                grade_unit="g/t", below_detection_limit=False,
                import_batch_id=batch.id,
            ))
    db.commit()

    # Detach before closing: the ORM objects expire with the session, so the
    # test gets plain values it can still read.
    project_id = proj.id
    token = create_access_token(data={"sub": user.email, "role": user.role,
                                      "user_id": str(user.id)})
    headers = {"Authorization": f"Bearer {token}"}
    db.close()
    return project_id, headers


# --- analysis ----------------------------------------------------------------

def test_grade_analysis_returns_evidence(project):
    project_id, headers = project

    response = client.get(f"/projects/{project_id}/grade-analysis", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["extraction"]["grade_unit"] == "g/t"
    assert body["extraction"]["n_ddh_composites"] > 0
    assert body["metal_capture_all"]
    assert body["log_probability"]["points"]
    assert "DDH" in body["populations"]


def test_grade_analysis_writes_nothing(project):
    project_id, headers = project
    db = TestingSessionLocal()
    before = db.query(Wireframe).filter(Wireframe.project_id == project_id).count()
    db.close()

    client.get(f"/projects/{project_id}/grade-analysis", headers=headers)

    db = TestingSessionLocal()
    assert db.query(Wireframe).filter(
        Wireframe.project_id == project_id).count() == before
    db.close()


def test_contact_analysis_endpoint(project):
    project_id, headers = project

    response = client.get(
        f"/projects/{project_id}/grade-analysis/contact",
        params={"threshold": 1.0}, headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["threshold"] == 1.0
    assert "bins" in body
    assert "self-fulfilling" in body["note"]


# --- generation --------------------------------------------------------------

def test_generating_a_shell_creates_one_wireframe(project):
    project_id, headers = project

    response = client.post(f"/projects/{project_id}/grade-shells",
                           json=_request(), headers=headers)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["wireframe"] is not None
    assert body["wireframe"]["solid_type"] == "grade_shell"

    db = TestingSessionLocal()
    shells = db.query(Wireframe).filter(
        Wireframe.project_id == project_id,
        Wireframe.solid_type == "grade_shell").all()
    db.close()
    assert len(shells) == 1


def test_the_stored_obj_parses_back_into_geometry(project):
    from backend.src.services.obj_geometry import parse_obj
    from backend.src.storage.local_filesystem import LocalFilesystemStorage

    project_id, headers = project
    response = client.post(f"/projects/{project_id}/grade-shells",
                           json=_request(), headers=headers)
    file_ref = response.json()["wireframe"]["file_ref"]

    parsed = parse_obj(LocalFilesystemStorage().load(file_ref).decode("utf-8"))

    assert parsed["vertices"]
    assert parsed["faces"]


def test_parameters_are_persisted_and_round_trip(project):
    project_id, headers = project

    response = client.post(
        f"/projects/{project_id}/grade-shells",
        json=_request(threshold=1.5, ellipsoid=_ellipsoid(azimuth=45.0, dip=-70.0)),
        headers=headers,
    )
    shell_id = response.json()["wireframe"]["id"]

    db = TestingSessionLocal()
    stored = db.query(Wireframe).filter(Wireframe.id == uuid.UUID(shell_id)).first()
    db.close()

    assert stored.parameters["threshold"] == 1.5
    assert stored.parameters["ellipsoid"]["strike_azimuth"] == 45.0
    assert stored.parameters["ellipsoid"]["dip"] == -70.0
    assert stored.parameters["sample_type_weights"] == {"DDH": 1.0}
    assert "validation" in stored.parameters


def test_the_validation_report_comes_back_with_the_shell(project):
    project_id, headers = project

    body = client.post(f"/projects/{project_id}/grade-shells",
                       json=_request(), headers=headers).json()

    validation = body["validation"]
    assert validation["geometry"]["is_watertight"] is True
    assert validation["geometry"]["total_volume_m3"] > 0
    assert validation["statistics"]["metal_capture"] is not None
    assert validation["statistics"]["by_sample_type"]


def test_listing_grade_shells(project):
    project_id, headers = project
    client.post(f"/projects/{project_id}/grade-shells", json=_request(),
                headers=headers)

    response = client.get(f"/projects/{project_id}/grade-shells", headers=headers)

    assert response.status_code == 200
    shells = response.json()["grade_shells"]
    assert len(shells) == 1
    assert shells[0]["parameters"]["threshold"] == 1.0


def test_a_generated_shell_appears_in_the_scene(project):
    project_id, headers = project
    client.post(f"/projects/{project_id}/grade-shells", json=_request(),
                headers=headers)

    scene = client.get(f"/projects/{project_id}/scene", headers=headers)

    assert scene.status_code == 200
    types = [w.get("solid_type") for w in scene.json()["wireframes"]]
    assert "grade_shell" in types


# --- refusals ----------------------------------------------------------------

def test_a_threshold_above_everything_returns_200_and_writes_nothing(project):
    project_id, headers = project

    response = client.post(f"/projects/{project_id}/grade-shells",
                           json=_request(threshold=999.0), headers=headers)

    assert response.status_code == 200
    assert response.json()["wireframe"] is None
    assert "No material meets" in response.json()["message"]

    db = TestingSessionLocal()
    assert db.query(Wireframe).filter(
        Wireframe.project_id == project_id,
        Wireframe.solid_type == "grade_shell").count() == 0
    db.close()


def test_a_runaway_grid_is_refused_before_anything_is_written(project):
    project_id, headers = project

    response = client.post(f"/projects/{project_id}/grade-shells",
                           json=_request(cell_size=0.001), headers=headers)

    assert response.status_code == 400
    assert "grid nodes" in response.json()["detail"]

    db = TestingSessionLocal()
    assert db.query(Wireframe).filter(
        Wireframe.project_id == project_id,
        Wireframe.solid_type == "grade_shell").count() == 0
    db.close()


def test_a_missing_sample_type_weight_is_refused(project):
    project_id, headers = project

    response = client.post(
        f"/projects/{project_id}/grade-shells",
        json=_request(sample_type_weights={"TR": 1.0}), headers=headers,
    )

    assert response.status_code == 422
    assert "No weight given" in response.json()["detail"]


def test_invalid_parameters_are_rejected(project):
    project_id, headers = project

    assert client.post(f"/projects/{project_id}/grade-shells",
                       json=_request(threshold=-1.0),
                       headers=headers).status_code == 422
    assert client.post(f"/projects/{project_id}/grade-shells",
                       json=_request(cell_size=0.0),
                       headers=headers).status_code == 422
    assert client.post(f"/projects/{project_id}/grade-shells",
                       json=_request(ellipsoid=_ellipsoid(major=0.0)),
                       headers=headers).status_code == 422
    assert client.post(f"/projects/{project_id}/grade-shells",
                       json=_request(ellipsoid=_ellipsoid(dip=-120.0)),
                       headers=headers).status_code == 422
    assert client.post(f"/projects/{project_id}/grade-shells",
                       json=_request(sample_type_weights={}),
                       headers=headers).status_code == 422
    assert client.post(f"/projects/{project_id}/grade-shells",
                       json=_request(min_samples=8, max_samples=4),
                       headers=headers).status_code == 422


def test_an_empty_project_is_refused():
    db = TestingSessionLocal()
    user = User(id=uuid.uuid4(), email=f"empty_{uuid.uuid4().hex}@example.com",
                role="owner")
    db.add(user)
    db.commit()
    proj = Project(id=uuid.uuid4(), name=f"Empty {uuid.uuid4().hex[:6]}",
                   utm_zone="37N", owner_id=user.id)
    db.add(proj)
    db.commit()
    empty_project_id = proj.id
    token = create_access_token(data={"sub": user.email, "role": user.role,
                                      "user_id": str(user.id)})
    db.close()

    response = client.post(
        f"/projects/{empty_project_id}/grade-shells", json=_request(),
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 400
    assert "No assayed intervals" in response.json()["detail"]


def test_another_users_project_is_not_reachable(project):
    project_id, _headers = project
    db = TestingSessionLocal()
    intruder = User(id=uuid.uuid4(),
                    email=f"intruder_{uuid.uuid4().hex}@example.com",
                    role="owner")
    db.add(intruder)
    db.commit()
    token = create_access_token(data={"sub": intruder.email,
                                      "role": intruder.role,
                                      "user_id": str(intruder.id)})
    db.close()
    headers = {"Authorization": f"Bearer {token}"}

    assert client.get(f"/projects/{project_id}/grade-analysis",
                      headers=headers).status_code == 404
    assert client.post(f"/projects/{project_id}/grade-shells", json=_request(),
                       headers=headers).status_code == 404
    assert client.get(f"/projects/{project_id}/grade-shells",
                      headers=headers).status_code == 404


def test_no_response_field_describes_the_output_as_a_resource(project):
    # Decision D3: this is a grade-domain envelope, not a resource estimate.
    project_id, headers = project

    body = client.post(f"/projects/{project_id}/grade-shells", json=_request(),
                       headers=headers).text.lower()

    for banned in ("resource", "reserve", "measured", "indicated", "inferred",
                   "jorc", "43-101", "tonnage", "tonnes"):
        assert banned not in body, f"response describes output as {banned!r}"
