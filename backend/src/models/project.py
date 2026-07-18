import uuid
from sqlalchemy import Column, String, ForeignKey, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from backend.src.db.session import Base

class Project(Base):
    __tablename__ = "project"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    utm_zone = Column(String, nullable=True)  # nullable until first import
    commodity = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    superseded_by = Column(UUID(as_uuid=True), ForeignKey("project.id"), nullable=True)
    # Nullable because projects created before this column existed have no
    # recorded owner. Every project created going forward is owned by the
    # authenticated user who created it (see projects.py create_project).
    # Access control (workspace.py, scene.py, imports.py, collars.py, etc.) treats
    # a project with no owner_id as inaccessible to everyone except via an active
    # Share Link -- it is never treated as "public."
    owner_id = Column(UUID(as_uuid=True), ForeignKey("user_account.id"), nullable=True)

    # Relationships
    owner = relationship("User", foreign_keys=[owner_id])
    collars = relationship("Collar", back_populates="project", foreign_keys="[Collar.project_id]")
    trenches = relationship("Trench", back_populates="project")
    wireframes = relationship("Wireframe", back_populates="project")
    share_links = relationship("ShareLink", back_populates="project")
    structural_readings = relationship("StructuralReading", back_populates="project")
    qaqc_standards = relationship("QaqcStandard", back_populates="project")

