from __future__ import annotations

from sqlalchemy import Float, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, generate_uuid


class Address(Base, TimestampMixin):
    """Geokodierte Adresse (Abschnitt 5.1)."""

    __tablename__ = "addresses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    original_text: Mapped[str] = mapped_column(String(500), nullable=False)
    street: Mapped[str | None] = mapped_column(String(255), nullable=True)
    house_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    postal_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    city: Mapped[str | None] = mapped_column(String(255), nullable=True)
    country_code: Mapped[str | None] = mapped_column(String(2), nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    geocoding_provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    geocoding_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    # z. B. "rooftop", "street", "city", "postal_code" - fuer Regel "nur auf Ortsebene gefunden" (Abschnitt 5.1)
    geocoding_precision: Mapped[str | None] = mapped_column(String(30), nullable=True)
