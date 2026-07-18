import uuid
from sqlalchemy import Column, String, ForeignKey, DateTime, Float, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from backend.src.db.session import Base

class StructuralReading(Base):
    __tablename__ = "structural_reading"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("project.id"), nullable=False, index=True)
    reading_type = Column(String, nullable=False)  # e.g., "fault_trace", "dip_strike"
    easting = Column(Float, nullable=False)
    northing = Column(Float, nullable=False)
    elevation = Column(Float, nullable=False)
    dip = Column(Float, nullable=True)     # degrees
    strike = Column(Float, nullable=True)  # degrees
    import_batch_id = Column(UUID(as_uuid=True), ForeignKey("import_batch.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    superseded_by = Column(UUID(as_uuid=True), ForeignKey("structural_reading.id"), nullable=True)

    # Relationships
    project = relationship("Project", back_populates="structural_readings", foreign_keys=[project_id])
    import_batch = relationship("ImportBatch")
