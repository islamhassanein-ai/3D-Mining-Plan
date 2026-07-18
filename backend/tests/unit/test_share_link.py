import pytest
import uuid
from datetime import datetime, timedelta, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.src.db.session import Base
from backend.src.models.user import User
from backend.src.models.project import Project
from backend.src.models.share_link import ShareLink
from backend.src.services.share_link import (
  issue,
  is_valid,
  revoke,
  renew,
  LinkExpiredOrRevokedException
)

# SQLite in-memory test database
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
  SQLALCHEMY_DATABASE_URL,
  connect_args={"check_same_thread": False},
  poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)

@pytest.fixture
def db():
  session = TestingSessionLocal()
  try:
    yield session
  finally:
    session.close()

def test_share_link_lifecycle(db):
  # 1. Setup User and Project
  user_id = uuid.uuid4()
  proj_id = uuid.uuid4()
  
  user = User(id=user_id, email="geo_share@example.com", role="owner")
  project = Project(id=proj_id, name="Share Prospect")
  db.add(user)
  db.add(project)
  db.commit()

  # 2. Issue a share link
  link = issue(db, proj_id, user_id)
  assert link.id is not None
  assert len(link.token) >= 43 # secrets.token_urlsafe(32) yields at least 43 chars
  assert link.project_id == proj_id
  assert link.created_by == user_id
  
  # Default expiry is approximately 7 days out
  expected_expiry = datetime.now(timezone.utc) + timedelta(days=7)
  assert abs((link.expires_at.replace(tzinfo=timezone.utc) - expected_expiry).total_seconds()) < 5.0
  
  # 3. Check is_valid on new link
  assert is_valid(db, link.token) is True
  assert is_valid(db, "nonexistent_token") is False

  # 4. Renew the active link
  old_expiry = link.expires_at.replace(tzinfo=timezone.utc)
  # Sleep/advance time mock not needed since we check relative to now
  renewed = renew(db, link.token)
  assert renewed.expires_at.replace(tzinfo=timezone.utc) > old_expiry
  assert is_valid(db, link.token) is True

  # 5. Revoke the link
  revoke(db, link.token)
  assert is_valid(db, link.token) is False
  
  # 6. Revoking again is a no-op (idempotent)
  revoke(db, link.token)
  
  # 7. Attempting to renew a revoked link raises Exception
  with pytest.raises(LinkExpiredOrRevokedException):
    renew(db, link.token)

def test_share_link_expired(db):
  user_id = uuid.uuid4()
  proj_id = uuid.uuid4()
  
  user = User(id=user_id, email="geo_expiry@example.com", role="owner")
  project = Project(id=proj_id, name="Expiry Prospect")
  db.add(user)
  db.add(project)
  db.commit()

  link = issue(db, proj_id, user_id)
  
  # Mock expiry to be in the past
  link.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
  db.add(link)
  db.commit()

  # Should be invalid
  assert is_valid(db, link.token) is False

  # Attempting to renew an expired link raises Exception
  with pytest.raises(LinkExpiredOrRevokedException):
    renew(db, link.token)
