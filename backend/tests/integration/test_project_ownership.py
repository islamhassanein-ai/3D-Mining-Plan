import io
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.src.db.session import Base, get_db
from backend.src.api.main import app
from backend.src.api.auth import create_access_token
from backend.src.models.user import User

# SQLite in-memory test database
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def setup_overrides():
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()


client = TestClient(app)


def _headers_for(email):
    db = TestingSessionLocal()
    user = db.query(User).filter(User.email == email).first()
    if not user:
        user = User(id=uuid.uuid4(), email=email, role="owner")
        db.add(user)
        db.commit()
        db.refresh(user)
    token = create_access_token(data={"sub": user.email, "role": user.role, "user_id": str(user.id)})
    return {"Authorization": f"Bearer {token}"}, user


def test_project_ownership_isolation_across_endpoints():
    """Regression test for the finding: 'any authenticated user could see and
    modify every project in the system.' Two distinct users must never see or
    reach each other's projects through the workspace list, direct project
    fetch, scene, collar detail, or import history -- only 404, never data."""
    owner_headers, owner = _headers_for("owner_iso@example.com")
    other_headers, other = _headers_for("other_iso@example.com")

    # `owner` creates a project and commits a drillhole into it.
    resp = client.post("/projects", json={"name": "Isolated Prospect", "commodity": "Gold"}, headers=owner_headers)
    assert resp.status_code == 201
    project_id = resp.json()["id"]

    collar_csv = b"hole_id,easting,northing,elevation,utm_zone\nDH01,350000.0,2800000.0,100.0,36N\n"
    files = {"collar_file": ("collars.csv", collar_csv, "text/csv")}
    resp = client.post(f"/projects/{project_id}/imports", files=files, headers=owner_headers)
    assert resp.status_code == 201
    batch_id = resp.json()["import_batch_id"]
    resp = client.post(
        f"/projects/{project_id}/imports/{batch_id}/commit?utm_zone_confirm=36N",
        headers=owner_headers
    )
    assert resp.status_code == 200, resp.text

    scene = client.get(f"/projects/{project_id}/scene", headers=owner_headers).json()
    collar_id = scene["drillholes"][0]["collar_id"]

    # --- `owner` can see and use everything about their own project ---
    assert client.get("/workspace/projects", headers=owner_headers).json()
    owned_ids = {p["id"] for p in client.get("/workspace/projects", headers=owner_headers).json()}
    assert project_id in owned_ids
    assert client.get(f"/projects/{project_id}", headers=owner_headers).status_code == 200
    assert client.get(f"/projects/{project_id}/scene", headers=owner_headers).status_code == 200
    assert client.get(f"/collars/{collar_id}", headers=owner_headers).status_code == 200
    assert client.get(f"/projects/{project_id}/history", headers=owner_headers).status_code == 200

    # --- `other` (a different authenticated user, no share link) must be
    # blocked from every one of the same operations ---
    other_ids = {p["id"] for p in client.get("/workspace/projects", headers=other_headers).json()}
    assert project_id not in other_ids, "workspace list must never leak another user's project"

    assert client.get(f"/projects/{project_id}", headers=other_headers).status_code == 404
    assert client.get(f"/projects/{project_id}/scene", headers=other_headers).status_code == 404
    assert client.get(f"/collars/{collar_id}", headers=other_headers).status_code == 404
    assert client.get(f"/projects/{project_id}/history", headers=other_headers).status_code == 404

    # `other` cannot import into a project they don't own, either.
    resp = client.post(f"/projects/{project_id}/imports", files=files, headers=other_headers)
    assert resp.status_code == 404

    # `other` cannot manage share links for a project they don't own.
    resp = client.post(f"/projects/{project_id}/share-links", headers=other_headers)
    assert resp.status_code == 404


def test_share_link_access_is_unaffected_by_ownership():
    """A colleague accessing a project through a legitimate, owner-issued Share
    Link must still work exactly as before -- ownership scoping must not have
    accidentally broken the one real "explicitly granted access" path."""
    owner_headers, owner = _headers_for("share_owner_iso@example.com")

    resp = client.post("/projects", json={"name": "Shared Isolated Prospect"}, headers=owner_headers)
    project_id = resp.json()["id"]

    link_resp = client.post(f"/projects/{project_id}/share-links", headers=owner_headers)
    assert link_resp.status_code == 201
    token = link_resp.json()["token"]

    # No Authorization header at all -- a share link needs none.
    scene_resp = client.get(f"/share/{token}/scene")
    assert scene_resp.status_code == 200
    assert scene_resp.json()["project_id"] == project_id
