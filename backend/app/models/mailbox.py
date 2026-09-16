from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, generate_uuid


class Mailbox(Base, TimestampMixin):
    """Konfiguriertes Postfach (Abschnitt 4.1).

    `configuration_reference` verweist auf einen Eintrag im Secret-Management
    (z. B. Schluesselname in Azure Key Vault / AWS Secrets Manager) - niemals
    auf im Quellcode oder in der Datenbank gespeicherte Klartext-Zugangsdaten.
    """

    __tablename__ = "mailboxes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False, default="imap")
    configuration_reference: Mapped[str] = mapped_column(String(255), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
