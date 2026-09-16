from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, generate_uuid


class RoutingResult(Base, TimestampMixin):
    """Gecachtes Routing-Ergebnis (Abschnitt 5.2).

    Der Cache (siehe `app/providers/routing/cache.py`) darf nur verwendet
    werden, wenn Start, Ziel, `routing_profile` und `provider` uebereinstimmen.
    """

    __tablename__ = "routing_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    shipment_id: Mapped[str | None] = mapped_column(ForeignKey("shipments.id"), nullable=True)

    origin_latitude: Mapped[float] = mapped_column(Float, nullable=False)
    origin_longitude: Mapped[float] = mapped_column(Float, nullable=False)
    destination_latitude: Mapped[float] = mapped_column(Float, nullable=False)
    destination_longitude: Mapped[float] = mapped_column(Float, nullable=False)

    distance_km: Mapped[float] = mapped_column(Float, nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    # "air" (Luftlinie), "car" (Pkw-Strasse), "truck" (Lkw-Strasse) - siehe Abschnitt 5.2
    routing_profile: Mapped[str] = mapped_column(String(30), nullable=False, default="truck")
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    shipment: Mapped["Shipment | None"] = relationship(back_populates="routing_results")  # noqa: F821
