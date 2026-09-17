from __future__ import annotations

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, generate_uuid


class IntegrationCredential(Base, TimestampMixin):
    """Admin-pflegbarer, verschluesselt gespeicherter API-Schluessel fuer
    externe Provider (aktuell: TomTom-Routing, siehe
    `app/services/integration_credential_service.py`).

    `encrypted_value` ist NIE der Klartext - siehe
    `app/services/credential_encryption.py`. Wird ueber `/api/integration-credentials`
    gepflegt (Administrator-Rolle); der Klartextwert wird ueber die API nie
    zurueckgegeben, nur ob/wann ein Wert hinterlegt wurde.
    """

    __tablename__ = "integration_credentials"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    credential_key: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    encrypted_value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
