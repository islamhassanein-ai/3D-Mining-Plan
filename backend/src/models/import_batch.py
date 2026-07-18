import uuid
from sqlalchemy import Column, String, ForeignKey, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from backend.src.db.session import Base

class ImportBatch(Base):
    __tablename__ = "import_batch"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("project.id"), nullable=False)
    source_file = Column(String, nullable=False)
    import_date = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    status = Column(String, nullable=False)  # pending_review, committed, rejected
    # Nullable because batches created before this column existed have no value;
    # every batch created going forward is populated from the authenticated user
    # performing the import (see imports.py create_import).
    created_by = Column(UUID(as_uuid=True), ForeignKey("user_account.id"), nullable=True)

    # Relationships
    collars = relationship("Collar", back_populates="import_batch")
    assay_intervals = relationship("AssayInterval", back_populates="import_batch")
    importing_user = relationship("User", foreign_keys=[created_by])
