from __future__ import annotations

import enum
from datetime import date

from sqlalchemy import JSON, Date, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, generate_uuid


class TariffStatus(str, enum.Enum):
    DRAFT = "draft"
    RELEASED = "released"
    ARCHIVED = "archived"


class TariffRuleType(str, enum.Enum):
    """Regeltypen aus Abschnitt 6.1.

    `BASE_PLUS_KM` (mit optionaler laenderabhaengiger km-Preistabelle) und
    `ALL_IN` (als Fixfracht-Preisliste je Laenderpaar, nur bei 1 Entladestelle)
    werden im MVP tatsaechlich berechnet (`app/tariff_engine/engine.py`,
    BEGA-Finetuning). Die uebrigen Typen sind im Datenmodell vorbereitet, ihre
    Berechnung ist eine dokumentierte Erweiterung
    (siehe docs/OFFENE_ENTSCHEIDUNGEN.md, Punkt 4).
    """

    BASE_PLUS_KM = "base_plus_km"
    RELATION = "relation"
    WEIGHT_BRACKET = "weight_bracket"
    PALLET = "pallet"
    LOADING_METER = "loading_meter"
    ZONE = "zone"
    ALL_IN = "all_in"
    MINIMUM_FREIGHT = "minimum_freight"
    COUNTRY_BORDER_SURCHARGE = "country_border_surcharge"
    TIME_DEPENDENT = "time_dependent"


class Tariff(Base, TimestampMixin):
    """Versionierter Tarif (Abschnitt 6.2).

    Ein Tarif ist unveraenderlich, sobald er in einem `AuditResult` referenziert
    wurde: Aenderungen erfordern eine neue Tarifversion (neue Zeile), damit
    bestehende Pruefergebnisse reproduzierbar bleiben (Abschnitt 6.2, 16.6).
    """

    __tablename__ = "tariffs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    tariff_code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    carrier_id: Mapped[str | None] = mapped_column(ForeignKey("carriers.id"), nullable=True)
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    valid_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="EUR")
    status: Mapped[TariffStatus] = mapped_column(Enum(TariffStatus, name="tariff_status"), nullable=False, default=TariffStatus.DRAFT)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    carrier: Mapped["Carrier | None"] = relationship()  # noqa: F821
    rules: Mapped[list["TariffRule"]] = relationship(back_populates="tariff", cascade="all, delete-orphan")


class TariffRule(Base, TimestampMixin):
    """Berechnungsregel eines Tarifs.

    `parameters_json` enthaelt je nach `rule_type` unterschiedliche Felder,
    z. B. fuer `base_plus_km`:
    `{"base_price": "150.00", "price_per_km": "1.05", "minimum_km": "0"}`.
    """

    __tablename__ = "tariff_rules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    tariff_id: Mapped[str] = mapped_column(ForeignKey("tariffs.id"), nullable=False)
    rule_type: Mapped[TariffRuleType] = mapped_column(Enum(TariffRuleType, name="tariff_rule_type"), nullable=False)
    parameters_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    tariff: Mapped["Tariff"] = relationship(back_populates="rules")
