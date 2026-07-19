import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.src.db.session import Base, get_db
from backend.src.api.main import app

from sqlalchemy.pool import StaticPool

# Setup an in-memory SQLite database for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create tables
import backend.src.models
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

def test_magic_link_flow(monkeypatch):
    import backend.src.api.auth as auth_module
    monkeypatch.setattr(auth_module, "ALLOWED_SIGNUP_EMAILS", {"test@example.com"})

    # 1. Request magic link
    email = "test@example.com"
    response = client.post("/auth/magic-link", json={"email": email})
    assert response.status_code == 202
    body = response.json()
    assert body["message"] == "Magic link sent"
    assert "dev_token" in body

    # Extract the token from the active tokens list inside the module
    assert len(auth_module.MAGIC_TOKENS) == 1
    token = list(auth_module.MAGIC_TOKENS.keys())[0]
    assert auth_module.MAGIC_TOKENS[token] == email
    assert body["dev_token"] == token

    # 2. Verify token
    response_verify = client.get(f"/auth/verify?token={token}")
    assert response_verify.status_code == 200
    res_data = response_verify.json()
    assert "access_token" in res_data
    assert res_data["token_type"] == "bearer"
    assert res_data["user"]["email"] == email
    assert res_data["user"]["role"] == "owner"

    # Verify token consumption
    assert token not in auth_module.MAGIC_TOKENS

def test_verify_invalid_token():
    response = client.get("/auth/verify?token=invalid_token")
    assert response.status_code == 401

def test_magic_link_rejects_non_allowlisted_new_email(monkeypatch):
    import backend.src.api.auth as auth_module
    monkeypatch.setattr(auth_module, "ALLOWED_SIGNUP_EMAILS", set())
    monkeypatch.setattr(auth_module, "ALLOWED_SIGNUP_DOMAINS", set())

    response = client.post("/auth/magic-link", json={"email": "intruder@evil.com"})
    assert response.status_code == 403
    # No token should have been generated for a rejected signup attempt
    assert not any(v == "intruder@evil.com" for v in auth_module.MAGIC_TOKENS.values())

def test_magic_link_allows_domain_allowlisted_new_email(monkeypatch):
    import backend.src.api.auth as auth_module
    monkeypatch.setattr(auth_module, "ALLOWED_SIGNUP_EMAILS", set())
    monkeypatch.setattr(auth_module, "ALLOWED_SIGNUP_DOMAINS", {"monark.com"})

    response = client.post("/auth/magic-link", json={"email": "newgeologist@monark.com"})
    assert response.status_code == 202

def test_magic_link_always_allows_existing_user(monkeypatch):
    import backend.src.api.auth as auth_module
    from backend.src.models.user import User
    import uuid as uuid_module

    # Lock the allowlist down completely -- an existing user must still be able to log in
    monkeypatch.setattr(auth_module, "ALLOWED_SIGNUP_EMAILS", set())
    monkeypatch.setattr(auth_module, "ALLOWED_SIGNUP_DOMAINS", set())

    db = TestingSessionLocal()
    db.add(User(id=uuid_module.uuid4(), email="already-a-user@example.com", role="owner"))
    db.commit()
    db.close()

    response = client.post("/auth/magic-link", json={"email": "already-a-user@example.com"})
    assert response.status_code == 202

    token = list(auth_module.MAGIC_TOKENS.keys())[-1]
    response_verify = client.get(f"/auth/verify?token={token}")
    assert response_verify.status_code == 200
    assert response_verify.json()["user"]["email"] == "already-a-user@example.com"
