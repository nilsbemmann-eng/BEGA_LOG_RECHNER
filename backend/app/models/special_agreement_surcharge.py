from __future__ import annotations

from sqlalchemy import Boolean, Index, Integer, Numeric, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, generate_uuid
from app.money import Money


class SpecialAgreementSurcharge(Base, TimestampMixin):
    """"Sondervereinbarungen"-Zuschlag je Ladelisten-Praefix (BEGA-Finetuning,
    reale Preisformel aus "Preise_2026_fuer_Wolke.xlsm").

    Ein fixer Betrag, der unabhaengig von km/Entladestellen zum Sollpreis
    einer Tour addiert wird, wenn die ersten 2 Ziffern der Ladelistennummer
    einem hier hinterlegten Praefix entsprechen (siehe
    `app/services/tour_origin_service.py`, `app/services/audit_service.py::run_tour_audit`).
    Im realen Excel betraf das die Praefixe 19, 36, 46, 52, 57, 79, 28, 15
    (jeweils 100 EUR) - hier als Stammdaten hinterlegt statt hart codiert,
    damit sich die Liste ohne Codeaenderung pflegen laesst.

    Versioniert analog zu `Tariff` (Abschnitt 6.2): eine Aenderung ueberschreibt
    den bestehenden Datensatz NICHT, sondern setzt ihn auf `is_current=False`
    und legt eine neue Zeile mit `version+1` an, damit vergangene Tour-Audits
    nachvollziehbar bleiben, welcher Betrag zum Pruefzeitpunkt galt (siehe
    `app/api/routers/special_agreement_surcharges.py`).
    """

    __tablename__ = "special_agreement_surcharges"
    __table_args__ = (
        Index(
            "ux_special_agreement_surcharges_current_prefix",
            "tour_number_prefix",
            unique=True,
            sqlite_where=text("is_current"),
            postgresql_where=text("is_current"),
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    tour_number_prefix: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    amount: Mapped[Money] = mapped_column(Numeric(12, 2), nullable=False)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
