import uuid
from sqlalchemy import Column, String, ForeignKey, Float, Numeric, Integer, Index
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
    elevation = Column(Float, nullable=True)
    grade_value = Column(Numeric, nullable=True)

    # Combined-CSV polyline support. All nullable: the two legacy trench
    # uploaders in backend/src/api/projects.py never set these, and existing
    # rows have no values. point_order arrives now so the future Sampling/Assay
    # Sheet can populate points 1..N without another migration.
    point_order = Column(Integer, nullable=True)
    hole_type = Column(String(10), nullable=True)
    import_batch_id = Column(UUID(as_uuid=True), ForeignKey("import_batch.id"), nullable=True)
    # superseded_by points at the REPLACEMENT polyline's point_order = 0 row
    # (the anchor), NOT a per-point counterpart -- point counts change between
    # imports, so there is no 1:1 mapping. Reads only ever filter
    # `superseded_by IS NULL`; this FK serves audit lineage alone.
    superseded_by = Column(UUID(as_uuid=True), ForeignKey("trench.id"), nullable=True)
    # Start-point ground-slope metadata for TR/CH/FC rows. dip/azimuth describe
    # the local ground slope AT THE COLLAR POINT ONLY, not the trench trajectory;
    # generated trench points keep dz = 0 (flat at collar elevation). See the
    # "Key geological constraint" note in specs/006-combined-csv-import/tasks.md.
    dip = Column(Float, nullable=True)
    azimuth = Column(Float, nullable=True)
    # Per-sample fields for TR/CH/FC sample rows from the combined CSV.
    sample_id  = Column(String, nullable=True)
    from_depth = Column(Float, nullable=True)
    to_depth   = Column(Float, nullable=True)

    # Relationships
    project = relationship("Project", back_populates="trenches")
    import_batch = relationship("ImportBatch", back_populates="trenches")

    __table_args__ = (
        Index("idx_trench_project_trench_order", "project_id", "trench_id", "point_order"),
    )