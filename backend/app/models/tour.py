from __future__ import annotations

from datetime import date

from sqlalchemy import Date, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, generate_uuid
from app.money import Money


class Tour(Base, TimestampMixin):
    """Tour/Ladeliste eines Frachtfuehrers (BEGA-Finetuning, Ladelisten-Import).

    Bildet den Fall ab, dass EINE Frachtrechnung sich auf eine ganze Tour mit
    mehreren Auftraegen/Entladestellen bezieht (mehrere `Shipment`-Zeilen
    gehoeren zu einer Tour). Jeder Auftrag aus der Ladeliste wird weiterhin
    als eigene `Shipment` gespeichert (Gewicht, Menge, Entladestelle); die
    Preispruefung (Fixfracht/km-Preis + Zuschlag je zusaetzlicher
    Entladestelle) laeuft aber auf Ebene der Tour, nicht der Einzelsendung
    (siehe `app/services/audit_service.py::run_tour_audit`).
    """

    __tablename__ = "tours"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    tour_number: Mapped[str] = mapped_column(String(100), nullable=False, index=True, unique=True)
    version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    carrier_id: Mapped[str | None] = mapped_column(ForeignKey("carriers.id"), nullable=True)
    tour_date: Mapped[date | None] = mapped_column(Date, nullable=True)  # Ladelistendatum
    loading_date: Mapped[date | None] = mapped_column(Date, nullable=True)  # Ladedatum
    source_document_id: Mapped[str | None] = mapped_column(ForeignKey("documents.id"), nullable=True)

    invoiced_km: Mapped[Money | None] = mapped_column(Numeric(10, 2), nullable=True)
    invoice_amount: Mapped[Money | None] = mapped_column(Numeric(12, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="EUR")

    carrier: Mapped["Carrier | None"] = relationship()  # noqa: F821
    shipments: Mapped[list["Shipment"]] = relationship(back_populates="tour")  # noqa: F821
    audit_results: Mapped[list["AuditResult"]] = relationship(  # noqa: F821
        back_populates="tour", cascade="all, delete-orphan"
    )

    @property
    def shipment_count(self) -> int:
        return len(self.shipments)
