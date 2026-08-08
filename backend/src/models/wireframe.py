import uuid
from sqlalchemy import Column, String, ForeignKey, Index, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from backend.src.db.session import Base

class Wireframe(Base):
    __tablename__ = "wireframe"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("project.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    # 'vein_solid', 'topography', or 'grade_shell'. The last is the marker the
    # viewer keys on to give generated shells their own layer.
    solid_type = Column(String, nullable=False)
    file_ref = Column(String, nullable=False)
    # How a generated solid was produced -- threshold, search ellipsoid, sample
    # weights, and the validation report. NULL for imported wireframes, which
    # carry their provenance in the file they came from. A shell whose
    # threshold and orientation are unknown cannot be reproduced or defended.
    parameters = Column(JSON, nullable=True)

    # Relationships
    project = relationship("Project", back_populates="wireframes")

    __table_args__ = (
        Index("idx_wireframe_project_type", "project_id", "solid_type"),
    )
