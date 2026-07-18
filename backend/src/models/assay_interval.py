import uuid
from sqlalchemy import Column, ForeignKey, Float, Boolean, String, Numeric, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from backend.src.db.session import Base

class AssayInterval(Base):
    __tablename__ = "assay_interval"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    collar_id = Column(UUID(as_uuid=True), ForeignKey("collar.id"), nullable=False, index=True)
    from_depth = Column(Float, nullable=False)
    to_depth = Column(Float, nullable=False)
    grade_value = Column(Numeric, nullable=False)
    grade_unit = Column(String, nullable=False)
    below_detection_limit = Column(Boolean, nullable=False, default=False)
    qaqc_flag = Column(String, nullable=True)
    import_batch_id = Column(UUID(as_uuid=True), ForeignKey("import_batch.id"), nullable=False)
    superseded_by = Column(UUID(as_uuid=True), ForeignKey("assay_interval.id"), nullable=True)

    # Relationships
    collar = relationship("Collar", back_populates="assay_intervals")
    import_batch = relationship("ImportBatch", back_populates="assay_intervals")

    __table_args__ = (
        Index("idx_assay_collar_depths", "collar_id", "from_depth", "to_depth"),
    )
