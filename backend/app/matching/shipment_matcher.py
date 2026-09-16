"""Sendungszuordnung nach mehreren Kriterien (Abschnitt 4.6).

Bewusst framework-unabhaengig gehalten (keine SQLAlchemy-Modelle): die
Eingaben sind einfache Datenklassen, damit die Zuordnungslogik ohne
Datenbank getestet werden kann. Der Service-Layer (`app/services/`) wandelt
ORM-Objekte in `ShipmentCandidate` um und ruft `match_shipment` auf.

Jede automatische Zuordnung protokolliert die verwendeten Kriterien und den
Konfidenzwert (`MatchOutcome.matched_criteria` je Kandidat), damit die
Entscheidung nachvollziehbar bleibt (Abschnitt 4.6, letzter Absatz).
"""
from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal


class MatchCriterion(str, enum.Enum):
    SHIPMENT_NUMBER = "shipment_number"
    TRANSPORT_ORDER_NUMBER = "transport_order_number"
    INVOICE_NUMBER = "invoice_number"
    CARRIER = "carrier"
    ORIGIN_ADDRESS = "origin_address"
    DESTINATION_ADDRESS = "destination_address"
    TRANSPORT_DATE = "transport_date"
    INVOICE_AMOUNT = "invoice_amount"
    EMAIL_REFERENCE = "email_reference"


# Gewichte je Kriterium. Werte sind ein dokumentierter Startpunkt und ueber
# `weights=` austauschbar (siehe docs/OFFENE_ENTSCHEIDUNGEN.md).
DEFAULT_WEIGHTS: dict[MatchCriterion, float] = {
    MatchCriterion.SHIPMENT_NUMBER: 0.40,
    MatchCriterion.TRANSPORT_ORDER_NUMBER: 0.30,
    MatchCriterion.INVOICE_NUMBER: 0.30,
    MatchCriterion.CARRIER: 0.15,
    MatchCriterion.ORIGIN_ADDRESS: 0.10,
    MatchCriterion.DESTINATION_ADDRESS: 0.10,
    MatchCriterion.TRANSPORT_DATE: 0.10,
    MatchCriterion.INVOICE_AMOUNT: 0.10,
    MatchCriterion.EMAIL_REFERENCE: 0.15,
}

# Ab diesem normalisierten Score gilt ein Kandidat als "ausreichend sicher".
AUTO_ASSIGN_THRESHOLD = 0.6
# Mindestabstand zum naechstbesten Kandidaten, um automatisch zuzuordnen.
AUTO_ASSIGN_MARGIN = 0.15
# Toleranz fuer den Betragvergleich (Rechnungsbetrag kann geringfuegig vom
# Sendungsbetrag der Ladeliste abweichen).
INVOICE_AMOUNT_TOLERANCE_PERCENT = Decimal("5")
TRANSPORT_DATE_TOLERANCE_DAYS = 1


@dataclass
class MatchInput:
    shipment_number: str | None = None
    transport_order_number: str | None = None
    invoice_number: str | None = None
    carrier_code: str | None = None
    origin_address_text: str | None = None
    destination_address_text: str | None = None
    transport_date: date | None = None
    invoice_amount: Decimal | None = None
    email_subject: str | None = None
    email_body: str | None = None


@dataclass
class ShipmentCandidate:
    id: str
    shipment_number: str | None = None
    transport_order_number: str | None = None
    invoice_number: str | None = None
    carrier_code: str | None = None
    origin_address_text: str | None = None
    destination_address_text: str | None = None
    transport_date: date | None = None
    invoice_amount: Decimal | None = None


@dataclass
class CandidateScore:
    candidate: ShipmentCandidate
    score: float
    matched_criteria: list[MatchCriterion] = field(default_factory=list)


@dataclass
class MatchOutcome:
    ranked_candidates: list[CandidateScore]
    auto_assigned: ShipmentCandidate | None


def _text_matches(a: str | None, b: str | None) -> bool:
    if not a or not b:
        return False
    return a.strip().casefold() == b.strip().casefold()


def _address_similar(a: str | None, b: str | None) -> bool:
    if not a or not b:
        return False
    a_norm, b_norm = a.strip().casefold(), b.strip().casefold()
    return a_norm in b_norm or b_norm in a_norm


def _amount_within_tolerance(claimed: Decimal | None, reference: Decimal | None) -> bool:
    if claimed is None or reference is None or reference == 0:
        return False
    deviation_percent = abs(claimed - reference) / reference * 100
    return deviation_percent <= INVOICE_AMOUNT_TOLERANCE_PERCENT


def _date_within_tolerance(claimed: date | None, reference: date | None) -> bool:
    if claimed is None or reference is None:
        return False
    return abs((claimed - reference).days) <= TRANSPORT_DATE_TOLERANCE_DAYS


def score_candidate(
    match_input: MatchInput, candidate: ShipmentCandidate, weights: dict[MatchCriterion, float] = DEFAULT_WEIGHTS
) -> CandidateScore:
    matched: list[MatchCriterion] = []
    achievable_weight = 0.0
    achieved_weight = 0.0

    checks: list[tuple[MatchCriterion, bool, bool]] = [
        (
            MatchCriterion.SHIPMENT_NUMBER,
            bool(match_input.shipment_number and candidate.shipment_number),
            _text_matches(match_input.shipment_number, candidate.shipment_number),
        ),
        (
            MatchCriterion.TRANSPORT_ORDER_NUMBER,
            bool(match_input.transport_order_number and candidate.transport_order_number),
            _text_matches(match_input.transport_order_number, candidate.transport_order_number),
        ),
        (
            MatchCriterion.INVOICE_NUMBER,
            bool(match_input.invoice_number and candidate.invoice_number),
            _text_matches(match_input.invoice_number, candidate.invoice_number),
        ),
        (
            MatchCriterion.CARRIER,
            bool(match_input.carrier_code and candidate.carrier_code),
            _text_matches(match_input.carrier_code, candidate.carrier_code),
        ),
        (
            MatchCriterion.ORIGIN_ADDRESS,
            bool(match_input.origin_address_text and candidate.origin_address_text),
            _address_similar(match_input.origin_address_text, candidate.origin_address_text),
        ),
        (
            MatchCriterion.DESTINATION_ADDRESS,
            bool(match_input.destination_address_text and candidate.destination_address_text),
            _address_similar(match_input.destination_address_text, candidate.destination_address_text),
        ),
        (
            MatchCriterion.TRANSPORT_DATE,
            bool(match_input.transport_date and candidate.transport_date),
            _date_within_tolerance(match_input.transport_date, candidate.transport_date),
        ),
        (
            MatchCriterion.INVOICE_AMOUNT,
            bool(match_input.invoice_amount is not None and candidate.invoice_amount is not None),
            _amount_within_tolerance(match_input.invoice_amount, candidate.invoice_amount),
        ),
    ]

    for criterion, is_applicable, is_match in checks:
        if not is_applicable:
            continue
        weight = weights[criterion]
        achievable_weight += weight
        if is_match:
            achieved_weight += weight
            matched.append(criterion)

    email_text = f"{match_input.email_subject or ''} {match_input.email_body or ''}".casefold()
    for reference in (candidate.shipment_number, candidate.transport_order_number, candidate.invoice_number):
        if reference and reference.casefold() in email_text:
            weight = weights[MatchCriterion.EMAIL_REFERENCE]
            achievable_weight += weight
            achieved_weight += weight
            matched.append(MatchCriterion.EMAIL_REFERENCE)
            break

    score = achieved_weight / achievable_weight if achievable_weight > 0 else 0.0
    return CandidateScore(candidate=candidate, score=score, matched_criteria=matched)


def match_shipment(
    match_input: MatchInput,
    candidates: list[ShipmentCandidate],
    weights: dict[MatchCriterion, float] = DEFAULT_WEIGHTS,
) -> MatchOutcome:
    """Bewertet alle Kandidaten und entscheidet, ob automatisch zugeordnet werden darf.

    Automatische Zuordnung nur bei genau einem Kandidaten oberhalb von
    `AUTO_ASSIGN_THRESHOLD` mit ausreichendem Abstand zum naechstbesten
    Kandidaten (`AUTO_ASSIGN_MARGIN`) - sonst muss der Pruefer manuell
    auswaehlen (Abschnitt 4.6).
    """
    scored = [score_candidate(match_input, candidate, weights) for candidate in candidates]
    ranked = sorted(scored, key=lambda item: item.score, reverse=True)

    auto_assigned: ShipmentCandidate | None = None
    if ranked and ranked[0].score >= AUTO_ASSIGN_THRESHOLD:
        runner_up_score = ranked[1].score if len(ranked) > 1 else 0.0
        if ranked[0].score - runner_up_score >= AUTO_ASSIGN_MARGIN:
            auto_assigned = ranked[0].candidate

    return MatchOutcome(ranked_candidates=ranked, auto_assigned=auto_assigned)
