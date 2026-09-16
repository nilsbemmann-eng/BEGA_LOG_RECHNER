"""Kilometer- und Routenpruefung (Abschnitt 5.3).

Eine Abweichung ist nicht automatisch eine Ablehnung: das Ergebnis ist immer
ein `DeviationOutcome` mit Prozentwert und einer von drei Einordnungen
(`WITHIN_TOLERANCE`, `OUTSIDE_TOLERANCE`, `REQUIRES_MANUAL_REVIEW`) - eine
inhaltliche Wuerdigung moeglicher Erklaerungen (Mautvermeidung, Baustelle,
zusaetzliche Ladestelle) bleibt dem Pruefer vorbehalten (Abschnitt 5.3).
"""
from __future__ import annotations

import enum
from dataclasses import dataclass
from decimal import Decimal


class RouteContext(str, enum.Enum):
    STANDARD = "standard"
    INNER_CITY_OR_HARD_TO_ACCESS = "inner_city_or_hard_to_access"
    SPECIAL_ROUTE = "special_route"  # Faehre, Insel, Baustelle, Sonderroute


class DeviationClassification(str, enum.Enum):
    WITHIN_TOLERANCE = "within_tolerance"
    OUTSIDE_TOLERANCE = "outside_tolerance"
    REQUIRES_MANUAL_REVIEW = "requires_manual_review"


@dataclass
class DistanceToleranceConfig:
    """Startwerte aus Abschnitt 5.3, ueber `app/config.py` konfigurierbar."""

    standard_percent: Decimal = Decimal("8")
    inner_city_percent: Decimal = Decimal("12")


@dataclass
class DeviationOutcome:
    reference_km: Decimal
    invoiced_km: Decimal
    deviation_percent: Decimal
    tolerance_percent: Decimal | None
    classification: DeviationClassification


def calculate_km_deviation_percent(invoiced_km: Decimal, reference_km: Decimal) -> Decimal:
    """`(abgerechnete km - Referenz-km) / Referenz-km * 100` (Abschnitt 5.3)."""
    if reference_km == 0:
        raise ValueError("Referenzkilometer duerfen nicht 0 sein")
    return (invoiced_km - reference_km) / reference_km * 100


def evaluate_distance(
    invoiced_km: Decimal,
    reference_km: Decimal,
    route_context: RouteContext = RouteContext.STANDARD,
    tolerance_config: DistanceToleranceConfig | None = None,
) -> DeviationOutcome:
    tolerance_config = tolerance_config or DistanceToleranceConfig()
    deviation_percent = calculate_km_deviation_percent(invoiced_km, reference_km)

    if route_context == RouteContext.SPECIAL_ROUTE:
        return DeviationOutcome(
            reference_km=reference_km,
            invoiced_km=invoiced_km,
            deviation_percent=deviation_percent,
            tolerance_percent=None,
            classification=DeviationClassification.REQUIRES_MANUAL_REVIEW,
        )

    tolerance_percent = (
        tolerance_config.inner_city_percent
        if route_context == RouteContext.INNER_CITY_OR_HARD_TO_ACCESS
        else tolerance_config.standard_percent
    )

    classification = (
        DeviationClassification.WITHIN_TOLERANCE
        if abs(deviation_percent) <= tolerance_percent
        else DeviationClassification.OUTSIDE_TOLERANCE
    )

    return DeviationOutcome(
        reference_km=reference_km,
        invoiced_km=invoiced_km,
        deviation_percent=deviation_percent,
        tolerance_percent=tolerance_percent,
        classification=classification,
    )
