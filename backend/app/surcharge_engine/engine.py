"""Pruefung von Zusatzfrachten (Abschnitt 7).

Grundregel: `Zulaessiger Zuschlag = nachgewiesene Menge x vertraglicher
Einheitspreis`. Fehlt ein erforderlicher Nachweis, wird die Position auf
`MANUAL_REVIEW` gesetzt - niemals automatisch abgelehnt (Abschnitt 7, letzter
Absatz; Abschnitt 13: "Keine endgueltige Ablehnung ausschliesslich aufgrund
eines niedrigen OCR-Konfidenzwerts" gilt sinngemaess auch fuer fehlende
Nachweise).
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.money import round_money

# Startbelegung, welche Zusatzfracht-Typen einen Nachweis erfordern
# (docs/OFFENE_ENTSCHEIDUNGEN.md, Punkt 7). Muss vor Produktivbetrieb mit dem
# Fachbereich/den Frachtfuehrervertraegen abgeglichen werden.
EVIDENCE_REQUIRED_SURCHARGE_TYPES: set[str] = {
    "waiting_time",
    "adr",
    "ferry_island",
    "lifting_platform",
    "pallet_exchange",
    "demurrage",
    "failed_trip",
    "failed_delivery",
}


class SurchargeEvaluationStatus:
    ALLOWED = "allowed"
    PARTIALLY_ALLOWED = "partially_allowed"
    MANUAL_REVIEW = "manual_review"


@dataclass
class SurchargeClaimInput:
    surcharge_type: str
    quantity: Decimal
    unit_price: Decimal
    claimed_amount: Decimal
    has_evidence: bool


@dataclass
class SurchargeEvaluation:
    allowed_amount: Decimal | None
    status: str
    reason: str


def evaluate_surcharge_claim(
    claim: SurchargeClaimInput, evidence_required_types: set[str] = EVIDENCE_REQUIRED_SURCHARGE_TYPES
) -> SurchargeEvaluation:
    requires_evidence = claim.surcharge_type in evidence_required_types

    if requires_evidence and not claim.has_evidence:
        return SurchargeEvaluation(
            allowed_amount=None,
            status=SurchargeEvaluationStatus.MANUAL_REVIEW,
            reason=(
                f"Fuer Zusatzfracht '{claim.surcharge_type}' ist ein Nachweis erforderlich, "
                "es wurde jedoch kein bestaetigter Nachweis erkannt."
            ),
        )

    allowed_amount = round_money(claim.quantity * claim.unit_price)

    if allowed_amount >= claim.claimed_amount:
        return SurchargeEvaluation(
            allowed_amount=round_money(claim.claimed_amount),
            status=SurchargeEvaluationStatus.ALLOWED,
            reason="Geltend gemachter Betrag liegt innerhalb des vertraglich zulaessigen Betrags.",
        )

    return SurchargeEvaluation(
        allowed_amount=allowed_amount,
        status=SurchargeEvaluationStatus.PARTIALLY_ALLOWED,
        reason=(
            f"Nur {allowed_amount} EUR sind vertraglich gedeckt "
            f"(nachgewiesene Menge {claim.quantity} x Einheitspreis {claim.unit_price}); "
            f"geltend gemacht wurden {claim.claimed_amount} EUR."
        ),
    )


def total_allowed_amount(evaluations: list[SurchargeEvaluation]) -> Decimal:
    """Summe der zulaessigen Zusatzfrachten fuer die Sollpreisberechnung (Abschnitt 6.3).

    Positionen in `MANUAL_REVIEW` fliessen mit 0 in den Sollpreis ein, bis der
    Pruefer entschieden hat - sie werden dadurch nicht verworfen, sondern
    bleiben als offene Position sichtbar (siehe `AuditRuleResult`).
    """
    return round_money(sum((e.allowed_amount or Decimal("0") for e in evaluations), start=Decimal("0")))
