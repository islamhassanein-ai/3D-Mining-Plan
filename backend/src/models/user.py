import uuid
from sqlalchemy import Column, String
from sqlalchemy.dialects.postgresql import UUID
from backend.src.db.session import Base

class User(Base):
    __tablename__ = "user_account"  # data_model_spec.md specifies user_account

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, nullable=False)
    role = Column(String, nullable=False)  # owner, editor, viewer
