import uuid
from sqlalchemy import Column, ForeignKey, Float, Integer, String, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from backend.src.db.session import Base

class LithologyInterval(Base):
    __tablename__ = "lithology_interval"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    collar_id = Column(UUID(as_uuid=True), ForeignKey("collar.id"), nullable=False, index=True)
    from_depth = Column(Float, nullable=False)
    to_depth = Column(Float, nullable=False)
    lith_code = Column(String, nullable=False)
    rqd_percent = Column(Integer, nullable=True)
    core_recovery_percent = Column(Integer, nullable=True)
    superseded_by = Column(UUID(as_uuid=True), ForeignKey("lithology_interval.id"), nullable=True)

    # Relationships
    collar = relationship("Collar", back_populates="lithology_intervals")

    __table_args__ = (
        Index("idx_lith_collar_depths", "collar_id", "from_depth", "to_depth"),
    )
