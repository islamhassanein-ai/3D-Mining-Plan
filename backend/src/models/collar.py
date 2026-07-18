import uuid
from sqlalchemy import Column, String, ForeignKey, DateTime, Float, Index, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from backend.src.db.session import Base

class Collar(Base):
    __tablename__ = "collar"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("project.id"), nullable=False, index=True)
    hole_id = Column(String, nullable=False)
    easting = Column(Float, nullable=False)
    northing = Column(Float, nullable=False)
    elevation = Column(Float, nullable=False)
    utm_zone = Column(String, nullable=False)
    import_batch_id = Column(UUID(as_uuid=True), ForeignKey("import_batch.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    superseded_by = Column(UUID(as_uuid=True), ForeignKey("collar.id"), nullable=True)

    # Relationships
    project = relationship("Project", back_populates="collars", foreign_keys=[project_id])
    import_batch = relationship("ImportBatch", back_populates="collars")
    surveys = relationship("Survey", back_populates="collar")
    assay_intervals = relationship("AssayInterval", back_populates="collar")
    lithology_intervals = relationship("LithologyInterval", back_populates="collar")

    __table_args__ = (
        Index("idx_collar_project_hole", "project_id", "hole_id"),
    )
