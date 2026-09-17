from __future__ import annotations

from datetime import date

from sqlalchemy import Date, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, generate_uuid
from app.money import Money


class Shipment(Base, TimestampMixin):
    __tablename__ = "shipments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    shipment_number: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    transport_order_number: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    invoice_number: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    transport_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    customer_id: Mapped[str | None] = mapped_column(ForeignKey("customers.id"), nullable=True)
    carrier_id: Mapped[str | None] = mapped_column(ForeignKey("carriers.id"), nullable=True)
    origin_address_id: Mapped[str | None] = mapped_column(ForeignKey("addresses.id"), nullable=True)
    destination_address_id: Mapped[str | None] = mapped_column(ForeignKey("addresses.id"), nullable=True)
    # Gruppiert mehrere Auftraege einer Ladeliste zu einer Tour, wenn die
    # Frachtrechnung sich auf die gesamte Tour bezieht statt auf die
    # Einzelsendung (siehe app/models/tour.py).
    tour_id: Mapped[str | None] = mapped_column(ForeignKey("tours.id"), nullable=True)

    weight_kg: Mapped[Money | None] = mapped_column(Numeric(12, 3), nullable=True)
    pallets: Mapped[int | None] = mapped_column(Integer, nullable=True)
    packages: Mapped[int | None] = mapped_column(Integer, nullable=True)
    loading_meters: Mapped[Money | None] = mapped_column(Numeric(6, 2), nullable=True)
    volume_m3: Mapped[Money | None] = mapped_column(Numeric(10, 3), nullable=True)

    invoiced_km: Mapped[Money | None] = mapped_column(Numeric(10, 2), nullable=True)
    invoice_amount: Mapped[Money | None] = mapped_column(Numeric(12, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="EUR")

    # Anzahl Entladestellen (BEGA-Finetuning): die erste Entladestelle ist im
    # Grund-/Fixfrachtpreis enthalten, ab der 2. faellt je Entladestelle ein
    # Zuschlag an (siehe app/tariff_engine/engine.py, docs/OFFENE_ENTSCHEIDUNGEN.md).
    unloading_point_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    customer: Mapped["Customer | None"] = relationship()  # noqa: F821
    carrier: Mapped["Carrier | None"] = relationship()  # noqa: F821
    origin_address: Mapped["Address | None"] = relationship(foreign_keys=[origin_address_id])  # noqa: F821
    destination_address: Mapped["Address | None"] = relationship(foreign_keys=[destination_address_id])  # noqa: F821
    tour: Mapped["Tour | None"] = relationship(back_populates="shipments")  # noqa: F821

    documents: Mapped[list["Document"]] = relationship(back_populates="shipment")  # noqa: F821
    routing_results: Mapped[list["RoutingResult"]] = relationship(  # noqa: F821
        back_populates="shipment", cascade="all, delete-orphan"
    )
    surcharge_claims: Mapped[list["SurchargeClaim"]] = relationship(  # noqa: F821
        back_populates="shipment", cascade="all, delete-orphan"
    )
    audit_results: Mapped[list["AuditResult"]] = relationship(  # noqa: F821
        back_populates="shipment", cascade="all, delete-orphan"
    )
