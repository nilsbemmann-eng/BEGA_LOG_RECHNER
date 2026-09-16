from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, generate_uuid


class EmailProcessingStatus(str, enum.Enum):
    RECEIVED = "received"
    PROCESSING = "processing"
    PROCESSED = "processed"
    DUPLICATE = "duplicate"
    ERROR = "error"


class Email(Base, TimestampMixin):
    """Eingehende E-Mail (Abschnitt 4.1).

    Duplikaterkennung erfolgt ueber `external_message_id` (siehe UniqueConstraint).
    """

    __tablename__ = "emails"
    __table_args__ = (UniqueConstraint("mailbox_id", "external_message_id", name="uq_email_mailbox_message"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    external_message_id: Mapped[str] = mapped_column(String(998), nullable=False, index=True)
    mailbox_id: Mapped[str] = mapped_column(ForeignKey("mailboxes.id"), nullable=False)
    sender: Mapped[str] = mapped_column(String(320), nullable=False)
    recipients: Mapped[str] = mapped_column(Text, nullable=False, default="")
    cc_recipients: Mapped[str] = mapped_column(Text, nullable=False, default="")
    subject: Mapped[str] = mapped_column(String(998), nullable=False, default="")
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    body_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    body_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    processing_status: Mapped[EmailProcessingStatus] = mapped_column(
        Enum(EmailProcessingStatus, name="email_processing_status"),
        nullable=False,
        default=EmailProcessingStatus.RECEIVED,
    )
    processing_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_metadata: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    attachments: Mapped[list["Attachment"]] = relationship(back_populates="email", cascade="all, delete-orphan")
