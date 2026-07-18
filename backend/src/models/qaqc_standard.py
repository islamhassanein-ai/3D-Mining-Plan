import uuid
from sqlalchemy import Column, String, ForeignKey, Float, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from backend.src.db.session import Base

class QaqcStandard(Base):
    __tablename__ = "qaqc_standard"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("project.id"), nullable=False, index=True)
    standard_name = Column(String, nullable=False)
    expected_grade_min = Column(Float, nullable=False)
    expected_grade_max = Column(Float, nullable=False)
    grade_unit = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    # Relationships
    project = relationship("Project", back_populates="qaqc_standards", foreign_keys=[project_id])
