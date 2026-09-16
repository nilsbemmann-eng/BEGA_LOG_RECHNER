from __future__ import annotations

import enum

from sqlalchemy import Enum, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, generate_uuid
from app.money import Money


class SurchargeType(str, enum.Enum):
    """Zusatzfracht-Positionen aus Abschnitt 7. Ein Sammeltyp existiert bewusst
    zusaetzlich zu, nicht anstelle der Einzelpositionen (siehe `OTHER`)."""

    DIESEL_ENERGY = "diesel_energy"
    TOLL = "toll"
    ADR = "adr"
    WAITING_TIME = "waiting_time"
    ADDITIONAL_LOADING_POINT = "additional_loading_point"
    ADDITIONAL_UNLOADING_POINT = "additional_unloading_point"
    NOTIFICATION = "notification"
    LIFTING_PLATFORM = "lifting_platform"
    FORKLIFT_ESCORT = "forklift_escort"
    OVERSIZE_BULKY_GOODS = "oversize_bulky_goods"
    FERRY_ISLAND = "ferry_island"
    CUSTOMS_BORDER_CLEARANCE = "customs_border_clearance"
    NIGHT_WEEKEND_HOLIDAY = "night_weekend_holiday"
    FAILED_TRIP = "failed_trip"
    FAILED_DELIVERY = "failed_delivery"
    PALLET_EXCHANGE = "pallet_exchange"
    DEMURRAGE = "demurrage"
    EXPRESS_FIXED_DATE = "express_fixed_date"
    OTHER = "other"


class SurchargeStatus(str, enum.Enum):
    PENDING = "pending"
    ALLOWED = "allowed"
    PARTIALLY_ALLOWED = "partially_allowed"
    REJECTED = "rejected"
    MANUAL_REVIEW = "manual_review"


class SurchargeClaim(Base, TimestampMixin):
    """Geltend gemachte Zusatzfracht (Abschnitt 7).

    Regel: `allowed_amount = nachgewiesene Menge x vertraglicher Einheitspreis`.
    Fehlt ein erforderlicher Nachweis, wird der Status `MANUAL_REVIEW` gesetzt -
    niemals automatisch `REJECTED` (siehe `app/surcharge_engine/engine.py`).
    """

    __tablename__ = "surcharge_claims"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    shipment_id: Mapped[str] = mapped_column(ForeignKey("shipments.id"), nullable=False)
    surcharge_type: Mapped[SurchargeType] = mapped_column(Enum(SurchargeType, name="surcharge_type"), nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    quantity: Mapped[Money] = mapped_column(Numeric(12, 3), nullable=False)
    unit: Mapped[str] = mapped_column(String(20), nullable=False)
    unit_price: Mapped[Money] = mapped_column(Numeric(12, 2), nullable=False)
    claimed_amount: Mapped[Money] = mapped_column(Numeric(12, 2), nullable=False)
    allowed_amount: Mapped[Money | None] = mapped_column(Numeric(12, 2), nullable=True)
    evidence_document_id: Mapped[str | None] = mapped_column(ForeignKey("documents.id"), nullable=True)
    status: Mapped[SurchargeStatus] = mapped_column(
        Enum(SurchargeStatus, name="surcharge_status"), nullable=False, default=SurchargeStatus.PENDING
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    shipment: Mapped["Shipment"] = relationship(back_populates="surcharge_claims")  # noqa: F821
