from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, generate_uuid
from app.money import Money


class AuditStatus(str, enum.Enum):
    """Pruefstatus aus Abschnitt 2 / 8.3."""

    BESTANDEN = "BESTANDEN"
    ABWEICHUNG = "ABWEICHUNG"
    MANUELLE_PRUEFUNG = "MANUELLE_PRUEFUNG"
    FEHLER = "FEHLER"
    FREIGEGEBEN = "FREIGEGEBEN"
    RUECKFRAGE = "RUECKFRAGE"


class RuleStatus(str, enum.Enum):
    PASSED = "passed"
    WARNING = "warning"
    FAILED = "failed"
    MANUAL_REVIEW = "manual_review"
    ERROR = "error"


class AuditResult(Base, TimestampMixin):
    """Ergebnis einer Preispruefung fuer eine Sendung (Abschnitt 8/9).

    Speichert immer die konkret verwendete Tarifversion (`tariff_id`), damit
    spaetere Tarifaenderungen bestehende Ergebnisse nicht veraendern
    (Abschnitt 6.2, 16.6).
    """

    __tablename__ = "audit_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    shipment_id: Mapped[str] = mapped_column(ForeignKey("shipments.id"), nullable=False)
    tariff_id: Mapped[str | None] = mapped_column(ForeignKey("tariffs.id"), nullable=True)

    reference_distance_km: Mapped[Money | None] = mapped_column(Numeric(10, 2), nullable=True)
    invoiced_distance_km: Mapped[Money | None] = mapped_column(Numeric(10, 2), nullable=True)
    expected_amount: Mapped[Money | None] = mapped_column(Numeric(12, 2), nullable=True)
    invoiced_amount: Mapped[Money | None] = mapped_column(Numeric(12, 2), nullable=True)
    difference_amount: Mapped[Money | None] = mapped_column(Numeric(12, 2), nullable=True)
    difference_percent: Mapped[Money | None] = mapped_column(Numeric(7, 3), nullable=True)

    status: Mapped[AuditStatus] = mapped_column(Enum(AuditStatus, name="audit_status"), nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False, default="")

    approved_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    shipment: Mapped["Shipment"] = relationship(back_populates="audit_results")  # noqa: F821
    tariff: Mapped["Tariff | None"] = relationship()  # noqa: F821
    rule_results: Mapped[list["AuditRuleResult"]] = relationship(
        back_populates="audit_result", cascade="all, delete-orphan"
    )

    # Nur lesende Komfort-Properties fuer die Historie (Abschnitt 12, Suche/Export) -
    # keine eigenen Spalten, damit Tarifaenderungen weiterhin keine bestehenden
    # Pruefergebnisse veraendern (Abschnitt 6.2).
    @property
    def shipment_number(self) -> str | None:
        return self.shipment.shipment_number if self.shipment else None

    @property
    def carrier_name(self) -> str | None:
        return self.shipment.carrier.name if self.shipment and self.shipment.carrier else None

    @property
    def transport_date(self):  # noqa: ANN201 - Rueckgabetyp date | None, siehe Shipment.transport_date
        return self.shipment.transport_date if self.shipment else None


class AuditRuleResult(Base, TimestampMixin):
    """Einzelergebnis einer Pruefregel (Tabelle 8.1) innerhalb eines `AuditResult`."""

    __tablename__ = "audit_rule_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    audit_result_id: Mapped[str] = mapped_column(ForeignKey("audit_results.id"), nullable=False)
    rule_code: Mapped[str] = mapped_column(String(50), nullable=False)
    rule_name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[RuleStatus] = mapped_column(Enum(RuleStatus, name="audit_rule_status"), nullable=False)
    actual_value: Mapped[str | None] = mapped_column(String(500), nullable=True)
    expected_value: Mapped[str | None] = mapped_column(String(500), nullable=True)
    explanation: Mapped[str] = mapped_column(Text, nullable=False, default="")

    audit_result: Mapped["AuditResult"] = relationship(back_populates="rule_results")
