import pytest
import uuid
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.src.db.session import Base, get_db
from backend.src.api.main import app
from backend.src.api.auth import create_access_token
from backend.src.models.user import User
from backend.src.models.project import Project
from backend.src.models.share_link import ShareLink

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

def test_integration_share_link_flow():
  db = TestingSessionLocal()
  
  # Setup user and project
  user = User(id=uuid.uuid4(), email="share_owner@example.com", role="owner")
  project = Project(id=uuid.uuid4(), name="Prospect Delta")
  project.owner_id = user.id
  db.add(user)
  db.add(project)
  db.commit()

  token = create_access_token(data={"sub": user.email, "role": user.role, "user_id": str(user.id)})
  headers = {"Authorization": f"Bearer {token}"}

  # 1. Create Share Link
  response = client.post(f"/projects/{project.id}/share-links", headers=headers)
  assert response.status_code == 201
  data = response.json()
  assert "token" in data
  assert "share_url" in data
  link_token = data["token"]
  link_id = data["id"]
  
  # 2. View scene via token (Read-only access)
  response_scene = client.get(f"/share/{link_token}/scene")
  assert response_scene.status_code == 200
  scene_data = response_scene.json()
  assert scene_data["project_id"] == str(project.id)
  
  # 3. Write attempt via token (unauthorized) - since /projects/{id}/share-links is JWT protected, calling without headers fails
  response_unauth = client.post(f"/projects/{project.id}/share-links")
  assert response_unauth.status_code == 401
  
  # 4. Renew the active link
  response_renew = client.post(f"/projects/{project.id}/share-links/{link_id}/renew", headers=headers)
  assert response_renew.status_code == 200
  
  # 5. Revoke the link
  response_revoke = client.post(f"/projects/{project.id}/share-links/{link_id}/revoke", headers=headers)
  assert response_revoke.status_code == 200
  
  # 6. View scene via revoked token (Returns 410 Gone)
  response_scene_revoked = client.get(f"/share/{link_token}/scene")
  assert response_scene_revoked.status_code == 410
  assert response_scene_revoked.json()["detail"] == "Access no longer available"
  
  # 7. Renew a revoked link (Returns 409 Conflict)
  response_renew_revoked = client.post(f"/projects/{project.id}/share-links/{link_id}/renew", headers=headers)
  assert response_renew_revoked.status_code == 409
  assert "Cannot renew a revoked share link" in response_renew_revoked.json()["detail"]

  # 8. Project Scoping checks (returns 404 for nonexistent projects)
  fake_proj_id = uuid.uuid4()
  res_fake_share = client.post(f"/projects/{fake_proj_id}/share-links", headers=headers)
  assert res_fake_share.status_code == 404
  
  res_fake_history = client.get(f"/projects/{fake_proj_id}/history", headers=headers)
  assert res_fake_history.status_code == 404


def test_history_shows_actual_importer_and_is_owner_only():
  """Regression test, two properties: (1) the history endpoint must report who
  actually performed each import, not a hardcoded/coincidental value -- this
  is what ImportBatch.created_by exists for; (2) now that projects are
  ownership-scoped, a user who does not own the project (and has no Share
  Link) must not be able to see its history at all -- not even to see a wrong
  importing_user value."""
  db = TestingSessionLocal()

  importer = User(id=uuid.uuid4(), email="importer@example.com", role="owner")
  viewer = User(id=uuid.uuid4(), email="viewer@example.com", role="owner")
  project = Project(id=uuid.uuid4(), name="Prospect Echo")
  project.owner_id = importer.id
  db.add(importer)
  db.add(viewer)
  db.add(project)
  db.commit()

  importer_token = create_access_token(data={"sub": importer.email, "role": importer.role, "user_id": str(importer.id)})
  viewer_token = create_access_token(data={"sub": viewer.email, "role": viewer.role, "user_id": str(viewer.id)})
  importer_headers = {"Authorization": f"Bearer {importer_token}"}
  viewer_headers = {"Authorization": f"Bearer {viewer_token}"}

  collar_csv = b"hole_id,easting,northing,elevation,utm_zone\nDH01,350000.0,2800000.0,100.0,36N\n"
  files = {"collar_file": ("collars.csv", collar_csv, "text/csv")}

  # `importer` performs the import
  resp = client.post(f"/projects/{project.id}/imports", files=files, headers=importer_headers)
  assert resp.status_code == 201
  batch_id = resp.json()["import_batch_id"]
  commit_resp = client.post(
    f"/projects/{project.id}/imports/{batch_id}/commit?utm_zone_confirm=36N",
    headers=importer_headers
  )
  assert commit_resp.status_code == 200, commit_resp.text

  # `importer` (the actual owner) views their own project's history: the
  # recorded importer must be accurate, not a hardcoded/coincidental value.
  history_resp = client.get(f"/projects/{project.id}/history", headers=importer_headers)
  assert history_resp.status_code == 200
  batches = history_resp.json()["import_batches"]
  assert len(batches) == 1
  # The recorded importer is the actual authenticated user who imported it,
  # correctly persisted via ImportBatch.created_by -- never a fabricated value.
  assert batches[0]["importing_user"] == "importer@example.com"

  # `viewer` does not own this project and has no Share Link to it -- they must
  # get 404, never a peek at (correct or incorrect) history data.
  viewer_history_resp = client.get(f"/projects/{project.id}/history", headers=viewer_headers)
  assert viewer_history_resp.status_code == 404

