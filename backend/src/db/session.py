import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# Auto-load .env from repo root when DATABASE_URL is not already in the environment.
# Handles worktrees and local dev without requiring python-dotenv.
if not os.getenv("DATABASE_URL"):
    _repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)
    ))))
    _env_file = os.path.join(_repo_root, ".env")
    if os.path.isfile(_env_file):
        with open(_env_file) as _fh:
            for _ln in _fh:
                _ln = _ln.strip()
                if _ln and not _ln.startswith("#") and "=" in _ln:
                    _k, _, _v = _ln.partition("=")
                    os.environ.setdefault(_k.strip(), _v.strip())

# Default to local PostgreSQL if DATABASE_URL is not set
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/mining_db")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
