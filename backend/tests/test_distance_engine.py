from decimal import Decimal

from app.distance_engine.deviation import (
    DeviationClassification,
    DistanceToleranceConfig,
    RouteContext,
    calculate_km_deviation_percent,
    evaluate_distance,
)


def test_km_deviation_percent_from_report_example() -> None:
    # Abschnitt 8.3: 684 km abgerechnet, 542 km Referenz -> +26,2 %.
    deviation = calculate_km_deviation_percent(Decimal("684"), Decimal("542"))
    assert round(deviation, 1) == Decimal("26.2")


def test_within_standard_tolerance() -> None:
    outcome = evaluate_distance(Decimal("108"), Decimal("100"), RouteContext.STANDARD)
    assert outcome.classification == DeviationClassification.WITHIN_TOLERANCE


def test_outside_standard_tolerance_from_report_example() -> None:
    outcome = evaluate_distance(Decimal("684"), Decimal("542"), RouteContext.STANDARD)
    assert outcome.classification == DeviationClassification.OUTSIDE_TOLERANCE


def test_inner_city_uses_wider_tolerance() -> None:
    outcome = evaluate_distance(Decimal("111"), Decimal("100"), RouteContext.INNER_CITY_OR_HARD_TO_ACCESS)
    assert outcome.classification == DeviationClassification.WITHIN_TOLERANCE


def test_special_route_always_requires_manual_review() -> None:
    outcome = evaluate_distance(Decimal("101"), Decimal("100"), RouteContext.SPECIAL_ROUTE)
    assert outcome.classification == DeviationClassification.REQUIRES_MANUAL_REVIEW


def test_custom_tolerance_config() -> None:
    config = DistanceToleranceConfig(standard_percent=Decimal("2"), inner_city_percent=Decimal("5"))
    outcome = evaluate_distance(Decimal("103"), Decimal("100"), RouteContext.STANDARD, config)
    assert outcome.classification == DeviationClassification.OUTSIDE_TOLERANCE
