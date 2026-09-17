from __future__ import annotations

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, generate_uuid


class TourOriginMapping(Base, TimestampMixin):
    """"Absender-Matrix" (BEGA-Finetuning, Nutzervorgabe): ordnet die ersten
    2 Ziffern der Ladelistennummer ("Kreis") einer Absender-/Beladeadresse zu.

    Ladelisten enthalten selbst keine Beladeadresse (siehe
    `app/services/ladeliste_pdf_parser.py`, docs/OFFENE_ENTSCHEIDUNGEN.md).
    Diese Tabelle ist der einzige Ort, an dem diese Zuordnung gepflegt wird
    (Stammdaten, analog zu `Carrier`/`Tariff`) - `run_tour_audit` nutzt sie,
    um einen echten Startpunkt fuer die Mehrstopp-Kilometerpruefung (OSRM) zu
    erhalten. Ist ein Praefix nicht hinterlegt, bleibt die Kilometerpruefung
    fuer betroffene Touren bewusst `MANUELLE_PRUEFUNG`, statt eine Adresse zu
    erfinden.
    """

    __tablename__ = "tour_origin_mappings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    tour_number_prefix: Mapped[str] = mapped_column(String(10), nullable=False, unique=True, index=True)
    label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    origin_address_id: Mapped[str] = mapped_column(ForeignKey("addresses.id"), nullable=False)

    origin_address: Mapped["Address"] = relationship()  # noqa: F821
