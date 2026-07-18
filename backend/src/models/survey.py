import uuid
from sqlalchemy import Column, ForeignKey, Float, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from backend.src.db.session import Base

class Survey(Base):
    __tablename__ = "survey"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    collar_id = Column(UUID(as_uuid=True), ForeignKey("collar.id"), nullable=False, index=True)
    depth = Column(Float, nullable=False)
    dip = Column(Float, nullable=False)
    azimuth = Column(Float, nullable=False)
    desurvey_method = Column(String, nullable=False, default="minimum_curvature")

    # Relationships
    collar = relationship("Collar", back_populates="surveys")
