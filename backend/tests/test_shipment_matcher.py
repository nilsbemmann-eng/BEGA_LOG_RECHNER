from datetime import date
from decimal import Decimal

from app.matching.shipment_matcher import MatchCriterion, MatchInput, ShipmentCandidate, match_shipment


def test_exact_shipment_number_match_auto_assigns() -> None:
    candidates = [
        ShipmentCandidate(id="s1", shipment_number="SEND-100", carrier_code="ACME"),
        ShipmentCandidate(id="s2", shipment_number="SEND-200", carrier_code="ACME"),
    ]
    match_input = MatchInput(shipment_number="SEND-100", carrier_code="ACME")

    outcome = match_shipment(match_input, candidates)

    assert outcome.auto_assigned is not None
    assert outcome.auto_assigned.id == "s1"
    assert MatchCriterion.SHIPMENT_NUMBER in outcome.ranked_candidates[0].matched_criteria


def test_ambiguous_match_returns_candidate_list_without_auto_assignment() -> None:
    candidates = [
        ShipmentCandidate(id="s1", origin_address_text="Hannover", transport_date=date(2026, 5, 1)),
        ShipmentCandidate(id="s2", origin_address_text="Hannover", transport_date=date(2026, 5, 1)),
    ]
    match_input = MatchInput(origin_address_text="Hannover", transport_date=date(2026, 5, 1))

    outcome = match_shipment(match_input, candidates)

    assert outcome.auto_assigned is None
    assert len(outcome.ranked_candidates) == 2


def test_no_candidates_returns_empty_outcome() -> None:
    outcome = match_shipment(MatchInput(shipment_number="X"), [])
    assert outcome.ranked_candidates == []
    assert outcome.auto_assigned is None


def test_email_reference_contributes_to_score() -> None:
    candidates = [ShipmentCandidate(id="s1", shipment_number="SEND-999")]
    match_input = MatchInput(email_subject="Rechnung zu Sendung SEND-999")

    outcome = match_shipment(match_input, candidates)

    assert MatchCriterion.EMAIL_REFERENCE in outcome.ranked_candidates[0].matched_criteria


def test_invoice_amount_within_tolerance_counts_as_match() -> None:
    candidates = [ShipmentCandidate(id="s1", shipment_number="SEND-1", invoice_amount=Decimal("1000.00"))]
    match_input = MatchInput(shipment_number="SEND-1", invoice_amount=Decimal("1010.00"))

    outcome = match_shipment(match_input, candidates)

    assert MatchCriterion.INVOICE_AMOUNT in outcome.ranked_candidates[0].matched_criteria
