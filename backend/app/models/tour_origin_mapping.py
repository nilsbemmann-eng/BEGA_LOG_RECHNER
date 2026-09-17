from __future__ import annotations

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, generate_uuid


class TourOriginMapping(Base, TimestampMixin):
    """"Absender-Matrix"/"Gebietsrelationen" (BEGA-Finetuning, Nutzervorgabe):
    ordnet einen Matchcode (Relation/Route) einer Absender-/Beladeadresse zu,
    gruppiert ueber die ersten 2 Ziffern der Ladelistennummer ("Praefix").

    Reale Stammdaten (siehe hochgeladene "Gebietsrelationen.xlsx") zeigen:
    ein Praefix ist NICHT eindeutig einem Absender zugeordnet - mehrere
    Matchcodes koennen denselben Praefix teilen, teils mit unterschiedlichen
    Adressen (z. B. Praefix 12: Ukraine- und Polen-Absender). Ein Matchcode
    ist selbst ebenfalls nicht global eindeutig (kann bei unterschiedlichen
    Praefixen wiederkehren, z. B. "SHUTTLEI" bei 11 und 14) - daher keine
    Unique-Constraints auf einzelnen Spalten, nur eine Zeile je Excel-Zeile.

    Ladelisten enthalten selbst keine Beladeadresse (siehe
    `app/services/ladeliste_pdf_parser.py`, docs/OFFENE_ENTSCHEIDUNGEN.md).
    `run_tour_audit`/`app/services/tour_origin_service.py` loesen einen
    Praefix nur dann automatisch auf, wenn ALLE dafuer hinterlegten Zeilen mit
    einer Adresse auf dieselbe Adresse zeigen; bei widersprechenden Adressen
    bleibt die Tour bewusst MANUELLE_PRUEFUNG (Nutzervorgabe), statt eine
    Adresse zu erraten.
    """

    __tablename__ = "tour_origin_mappings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    tour_number_prefix: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    matchcode: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Nullable: einige reale Matchcodes haben (noch) keine hinterlegte Adresse
    # (siehe Gebietsrelationen.xlsx, z. B. "HSF", "CTNEX").
    origin_address_id: Mapped[str | None] = mapped_column(ForeignKey("addresses.id"), nullable=True)

    origin_address: Mapped["Address | None"] = relationship()  # noqa: F821
