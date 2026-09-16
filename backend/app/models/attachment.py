from __future__ import annotations

from sqlalchemy import BigInteger, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, generate_uuid


class Attachment(Base, TimestampMixin):
    """E-Mail-Anhang. Duplikaterkennung ueber SHA-256 `file_hash` (Abschnitt 4.1)."""

    __tablename__ = "attachments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    email_id: Mapped[str] = mapped_column(ForeignKey("emails.id"), nullable=False)
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(255), nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)  # SHA-256 hex digest
    storage_reference: Mapped[str] = mapped_column(String(1000), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)

    email: Mapped["Email"] = relationship(back_populates="attachments")  # noqa: F821
    document: Mapped["Document | None"] = relationship(  # noqa: F821
        back_populates="attachment", uselist=False, cascade="all, delete-orphan"
    )
