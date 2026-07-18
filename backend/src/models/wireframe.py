import uuid
from sqlalchemy import Column, String, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from backend.src.db.session import Base

class Wireframe(Base):
    __tablename__ = "wireframe"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("project.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    solid_type = Column(String, nullable=False)
    file_ref = Column(String, nullable=False)

    # Relationships
    project = relationship("Project", back_populates="wireframes")
