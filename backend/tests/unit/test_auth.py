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

def test_magic_link_flow():
    # 1. Request magic link
    email = "test@example.com"
    response = client.post("/auth/magic-link", json={"email": email})
    assert response.status_code == 202
    assert response.json() == {"message": "Magic link sent"}

    # Extract the token from the active tokens list inside the module
    from backend.src.api.auth import MAGIC_TOKENS
    assert len(MAGIC_TOKENS) == 1
    token = list(MAGIC_TOKENS.keys())[0]
    assert MAGIC_TOKENS[token] == email

    # 2. Verify token
    response_verify = client.get(f"/auth/verify?token={token}")
    assert response_verify.status_code == 200
    res_data = response_verify.json()
    assert "access_token" in res_data
    assert res_data["token_type"] == "bearer"
    assert res_data["user"]["email"] == email
    assert res_data["user"]["role"] == "owner"

    # Verify token consumption
    assert token not in MAGIC_TOKENS

def test_verify_invalid_token():
    response = client.get("/auth/verify?token=invalid_token")
    assert response.status_code == 401
