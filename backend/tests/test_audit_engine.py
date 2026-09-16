from decimal import Decimal

from app.audit_engine.rule_engine import (
    AuditRuleInput,
    AuditStatus,
    RuleStatus,
    build_explanation,
    derive_overall_status,
    run_audit_rules,
)
from app.distance_engine.deviation import DeviationClassification, DeviationOutcome


def _complete_input(**overrides) -> AuditRuleInput:
    defaults = dict(
        shipment_number="SEND-1",
        transport_date_present=True,
        origin_address_present=True,
        destination_address_present=True,
        invoice_amount_present=True,
        min_ocr_confidence=0.97,
        ocr_auto_threshold=0.95,
        ocr_flagged_threshold=0.80,
        is_unique_shipment_assignment=True,
        origin_geocoded=True,
        destination_geocoded=True,
        distance_outcome=DeviationOutcome(
            reference_km=Decimal("100"), invoiced_km=Decimal("105"), deviation_percent=Decimal("5"),
            tolerance_percent=Decimal("8"), classification=DeviationClassification.WITHIN_TOLERANCE,
        ),
        tariff_found=True,
        tariff_error_message=None,
        price_difference_percent=Decimal("1"),
        price_tolerance_percent=Decimal("5"),
        surcharge_statuses=[],
        is_duplicate=False,
        weight_kg=Decimal("5000"),
        loading_meters=Decimal("6"),
    )
    defaults.update(overrides)
    return AuditRuleInput(**defaults)


def test_all_rules_pass_yields_bestanden() -> None:
    outcomes = run_audit_rules(_complete_input())
    assert all(o.status == RuleStatus.PASSED for o in outcomes)
    assert derive_overall_status(outcomes) == AuditStatus.BESTANDEN


def test_missing_evidence_yields_manuelle_pruefung_not_failed() -> None:
    outcomes = run_audit_rules(_complete_input(surcharge_statuses=["manual_review"]))
    assert derive_overall_status(outcomes) == AuditStatus.MANUELLE_PRUEFUNG
    evidence_result = next(o for o in outcomes if o.rule_code == "evidence_present")
    assert evidence_result.status == RuleStatus.MANUAL_REVIEW


def test_distance_outside_tolerance_yields_abweichung() -> None:
    outside = DeviationOutcome(
        reference_km=Decimal("542"), invoiced_km=Decimal("684"), deviation_percent=Decimal("26.2"),
        tolerance_percent=Decimal("8"), classification=DeviationClassification.OUTSIDE_TOLERANCE,
    )
    outcomes = run_audit_rules(_complete_input(distance_outcome=outside))
    assert derive_overall_status(outcomes) == AuditStatus.ABWEICHUNG


def test_low_ocr_confidence_never_produces_failed_status() -> None:
    outcomes = run_audit_rules(_complete_input(min_ocr_confidence=0.5))
    ocr_result = next(o for o in outcomes if o.rule_code == "ocr_confidence")
    assert ocr_result.status == RuleStatus.MANUAL_REVIEW
    assert derive_overall_status(outcomes) == AuditStatus.MANUELLE_PRUEFUNG


def test_duplicate_invoice_yields_abweichung() -> None:
    outcomes = run_audit_rules(_complete_input(is_duplicate=True))
    assert derive_overall_status(outcomes) == AuditStatus.ABWEICHUNG


def test_build_explanation_lists_only_problematic_rules() -> None:
    outcomes = run_audit_rules(_complete_input(is_duplicate=True))
    explanation = build_explanation(outcomes)
    assert "Duplikat" in explanation
    assert "Zuordnung" not in explanation
