from decimal import Decimal

from app.surcharge_engine.engine import (
    SurchargeClaimInput,
    SurchargeEvaluationStatus,
    evaluate_surcharge_claim,
    total_allowed_amount,
)


def test_waiting_time_without_evidence_requires_manual_review() -> None:
    claim = SurchargeClaimInput(
        surcharge_type="waiting_time", quantity=Decimal("2.5"), unit_price=Decimal("48.00"),
        claimed_amount=Decimal("120.00"), has_evidence=False,
    )
    evaluation = evaluate_surcharge_claim(claim)
    assert evaluation.status == SurchargeEvaluationStatus.MANUAL_REVIEW
    assert evaluation.allowed_amount is None


def test_waiting_time_with_evidence_partially_allowed_from_report_example() -> None:
    # Abschnitt 7, Beispielstruktur: 2,5 h x 48,00 EUR = 120,00 EUR geltend
    # gemacht, aber nur 72,00 EUR nachgewiesene Menge x Einheitspreis zulaessig.
    claim = SurchargeClaimInput(
        surcharge_type="waiting_time", quantity=Decimal("1.5"), unit_price=Decimal("48.00"),
        claimed_amount=Decimal("120.00"), has_evidence=True,
    )
    evaluation = evaluate_surcharge_claim(claim)
    assert evaluation.status == SurchargeEvaluationStatus.PARTIALLY_ALLOWED
    assert evaluation.allowed_amount == Decimal("72.00")


def test_diesel_surcharge_without_evidence_requirement_is_allowed() -> None:
    claim = SurchargeClaimInput(
        surcharge_type="diesel_energy", quantity=Decimal("1"), unit_price=Decimal("50.00"),
        claimed_amount=Decimal("50.00"), has_evidence=False,
    )
    evaluation = evaluate_surcharge_claim(claim)
    assert evaluation.status == SurchargeEvaluationStatus.ALLOWED
    assert evaluation.allowed_amount == Decimal("50.00")


def test_total_allowed_amount_sums_and_ignores_manual_review() -> None:
    evaluations = [
        evaluate_surcharge_claim(SurchargeClaimInput("diesel_energy", Decimal("1"), Decimal("50"), Decimal("50"), True)),
        evaluate_surcharge_claim(SurchargeClaimInput("waiting_time", Decimal("2"), Decimal("48"), Decimal("96"), False)),
    ]
    assert total_allowed_amount(evaluations) == Decimal("50.00")
