import uuid
from sqlalchemy import Column, String, ForeignKey, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from backend.src.db.session import Base

class ShareLink(Base):
  __tablename__ = "share_link"

  id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
  project_id = Column(UUID(as_uuid=True), ForeignKey("project.id"), nullable=False, index=True)
  token = Column(String, nullable=False, unique=True, index=True)
  created_by = Column(UUID(as_uuid=True), ForeignKey("user_account.id"), nullable=False)
  created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
  expires_at = Column(DateTime(timezone=True), nullable=False)
  revoked_at = Column(DateTime(timezone=True), nullable=True)

  # Relationships
  project = relationship("Project", back_populates="share_links")
  creator = relationship("User")
