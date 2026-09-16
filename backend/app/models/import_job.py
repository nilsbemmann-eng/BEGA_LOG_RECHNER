from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, generate_uuid


class ImportSourceType(str, enum.Enum):
    EMAIL_SYNC = "email_sync"
    LADELISTE_UPLOAD = "ladeliste_upload"
    MANUAL_UPLOAD = "manual_upload"


class ImportJobStatus(str, enum.Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    COMPLETED_WITH_ERRORS = "completed_with_errors"
    FAILED = "failed"


class ImportJob(Base, TimestampMixin):
    __tablename__ = "import_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    source_type: Mapped[ImportSourceType] = mapped_column(Enum(ImportSourceType, name="import_source_type"), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[ImportJobStatus] = mapped_column(
        Enum(ImportJobStatus, name="import_job_status"), nullable=False, default=ImportJobStatus.RUNNING
    )
    records_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    records_successful: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    records_failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_report_reference: Mapped[str | None] = mapped_column(String(1000), nullable=True)
