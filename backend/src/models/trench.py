import uuid
from sqlalchemy import Column, String, ForeignKey, Float, Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from backend.src.db.session import Base

class Trench(Base):
    __tablename__ = "trench"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("project.id"), nullable=False, index=True)
    trench_id = Column(String, nullable=False)
    easting = Column(Float, nullable=True)
    northing = Column(Float, nullable=True)
    grade_value = Column(Numeric, nullable=True)

    # Relationships
    project = relationship("Project", back_populates="trenches")
