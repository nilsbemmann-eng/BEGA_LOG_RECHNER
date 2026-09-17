"""Orchestriert einen vollstaendigen Pruefdurchlauf (Abschnitt 2, 8).

Verbindet Distanz-, Tarif- und Zuschlags-Engine sowie die Pruefregel-Engine zu
einem `AuditResult`. Diese Funktion ist absichtlich die einzige Stelle, an der
alle Engines gemeinsam aufgerufen werden - damit jede Preisberechnung aus
gespeicherten Eingangswerten, einer Tarifversion, Routingdaten und
angewendeten Pruefregeln reproduzierbar bleibt (Abschnitt 17, letzter Satz).
"""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from app.audit_engine.rule_engine import AuditRuleInput, RuleOutcome, build_explanation, derive_overall_status, run_audit_rules
from app.config import Settings
from app.distance_engine.deviation import DistanceToleranceConfig, RouteContext, evaluate_distance
from app.errors import NotFoundError
from app.models.audit import AuditResult, AuditRuleResult, AuditStatus, RuleStatus
from app.models.shipment import Shipment
from app.models.tour import Tour
from app.providers.base import GeocodingProvider, RoutingProvider
from app.services.address_service import geocode_address_if_needed, is_precisely_geocoded
from app.services.routing_service import get_or_calculate_route
from app.services.surcharge_service import evaluate_and_persist_claim
from app.services.tariff_service import calculate_expected_price_for_tariff, select_tariff_for_shipment
from app.services.tour_origin_service import resolve_tour_origin_address
from app.tariff_engine.engine import MultipleTariffsValidError, TariffNotFoundError, calculate_price_deviation

# Ladelisten-PDFs werden ueber eine strikte Tabellen-/Regex-Extraktion
# geparst (`app/services/ladeliste_pdf_parser.py`): jedes Feld ist entweder
# exakt (z. B. PLZ/Ort-Zeile per Regex) oder der Import schlaegt fehl bzw.
# vermerkt eine Warnung - es gibt keine abgestufte Bild-OCR-Unsicherheit wie
# bei Scans. Daher volle Konfidenz statt `None` (das wuerde jede Tour
# ungerechtfertigt auf MANUELLE_PRUEFUNG setzen).
_TOUR_PARSE_CONFIDENCE = 1.0

_ROUTE_CONTEXT_MAP = {
    "standard": RouteContext.STANDARD,
    "inner_city_or_hard_to_access": RouteContext.INNER_CITY_OR_HARD_TO_ACCESS,
    "special_route": RouteContext.SPECIAL_ROUTE,
}


def _min_ocr_confidence(shipment: Shipment) -> float | None:
    confidences = [field.confidence for document in shipment.documents for field in document.extracted_fields]
    return min(confidences) if confidences else None


def run_audit(
    db: Session,
    shipment_id: str,
    route_context: str,
    settings: Settings,
    geocoding_provider: GeocodingProvider,
    routing_provider: RoutingProvider,
) -> AuditResult:
    shipment = db.get(Shipment, shipment_id)
    if shipment is None:
        raise NotFoundError(f"Sendung {shipment_id} nicht gefunden", entity_type="Shipment", entity_id=shipment_id)

    origin_geocoded = destination_geocoded = False
    reference_km: Decimal | None = None

    if shipment.origin_address is not None:
        try:
            geocode_address_if_needed(shipment.origin_address, geocoding_provider)
            origin_geocoded = is_precisely_geocoded(shipment.origin_address)
        except Exception:  # noqa: BLE001 - Geocoding-Fehler fliesst als Regelverstoss ein, nicht als Exception
            origin_geocoded = False

    if shipment.destination_address is not None:
        try:
            geocode_address_if_needed(shipment.destination_address, geocoding_provider)
            destination_geocoded = is_precisely_geocoded(shipment.destination_address)
        except Exception:  # noqa: BLE001
            destination_geocoded = False

    distance_outcome = None
    if origin_geocoded and destination_geocoded and shipment.invoiced_km is not None:
        routing_result, _ = get_or_calculate_route(
            db,
            origin_lat=shipment.origin_address.latitude, origin_lon=shipment.origin_address.longitude,
            destination_lat=shipment.destination_address.latitude, destination_lon=shipment.destination_address.longitude,
            profile=settings.default_routing_profile, provider=routing_provider, provider_name=settings.routing_provider,
            shipment_id=shipment.id,
        )
        reference_km = Decimal(str(routing_result.distance_km))
        distance_outcome = evaluate_distance(
            invoiced_km=shipment.invoiced_km,
            reference_km=reference_km,
            route_context=_ROUTE_CONTEXT_MAP.get(route_context, RouteContext.STANDARD),
            tolerance_config=DistanceToleranceConfig(
                standard_percent=Decimal(str(settings.km_tolerance_standard_percent)),
                inner_city_percent=Decimal(str(settings.km_tolerance_inner_city_percent)),
            ),
        )

    surcharge_evaluations = [evaluate_and_persist_claim(claim) for claim in shipment.surcharge_claims]
    allowed_surcharge_total = sum((e.allowed_amount or Decimal("0") for e in surcharge_evaluations), start=Decimal("0"))

    tariff_orm = None
    tariff_found = False
    tariff_error_message: str | None = None
    expected_amount: Decimal | None = None

    if shipment.transport_date is not None:
        try:
            tariff_orm = select_tariff_for_shipment(db, shipment.carrier_id, shipment.transport_date)
            tariff_found = True
            price_reference_km = reference_km if reference_km is not None else (shipment.invoiced_km or Decimal("0"))
            breakdown = calculate_expected_price_for_tariff(
                tariff_orm,
                price_reference_km,
                allowed_surcharge_total,
                origin_country=shipment.origin_address.country_code if shipment.origin_address else None,
                destination_country=shipment.destination_address.country_code if shipment.destination_address else None,
                unloading_point_count=shipment.unloading_point_count,
                default_additional_unloading_point_price=Decimal(str(settings.default_additional_unloading_point_price_eur)),
            )
            expected_amount = breakdown.total_amount
        except (TariffNotFoundError, MultipleTariffsValidError) as exc:
            tariff_error_message = str(exc)

    price_difference_percent = None
    difference_amount = None
    if expected_amount is not None and shipment.invoice_amount is not None:
        deviation = calculate_price_deviation(shipment.invoice_amount, expected_amount)
        price_difference_percent = deviation.difference_percent
        difference_amount = deviation.difference_amount

    rule_input = AuditRuleInput(
        shipment_number=shipment.shipment_number,
        transport_date_present=shipment.transport_date is not None,
        origin_address_present=shipment.origin_address_id is not None,
        destination_address_present=shipment.destination_address_id is not None,
        invoice_amount_present=shipment.invoice_amount is not None,
        min_ocr_confidence=_min_ocr_confidence(shipment),
        ocr_auto_threshold=settings.ocr_min_auto_confidence,
        ocr_flagged_threshold=settings.ocr_min_flagged_confidence,
        is_unique_shipment_assignment=True,  # Zuordnung erfolgte bereits ueber /shipments/match
        origin_geocoded=origin_geocoded,
        destination_geocoded=destination_geocoded,
        distance_outcome=distance_outcome,
        tariff_found=tariff_found,
        tariff_error_message=tariff_error_message,
        price_difference_percent=price_difference_percent,
        price_tolerance_percent=Decimal(str(settings.price_deviation_tolerance_percent)),
        surcharge_statuses=[e.status for e in surcharge_evaluations],
        is_duplicate=False,  # Duplikate werden bereits beim E-Mail-/Anhang-Import verhindert (Abschnitt 4.1)
        weight_kg=shipment.weight_kg,
        loading_meters=shipment.loading_meters,
        max_plausible_weight_kg=Decimal(str(settings.plausibility_max_weight_kg)),
        max_plausible_loading_meters=Decimal(str(settings.plausibility_max_loading_meters)),
    )

    rule_outcomes: list[RuleOutcome] = run_audit_rules(rule_input)
    overall_status = derive_overall_status(rule_outcomes)
    explanation = build_explanation(rule_outcomes)

    audit_result = AuditResult(
        shipment_id=shipment.id,
        tariff_id=tariff_orm.id if tariff_orm else None,
        reference_distance_km=reference_km,
        invoiced_distance_km=shipment.invoiced_km,
        expected_amount=expected_amount,
        invoiced_amount=shipment.invoice_amount,
        difference_amount=difference_amount,
        difference_percent=price_difference_percent,
        status=AuditStatus(overall_status.value),
        explanation=explanation,
    )
    for outcome in rule_outcomes:
        audit_result.rule_results.append(
            AuditRuleResult(
                rule_code=outcome.rule_code,
                rule_name=outcome.rule_name,
                status=RuleStatus(outcome.status.value),
                actual_value=outcome.actual_value,
                expected_value=outcome.expected_value,
                explanation=outcome.explanation,
            )
        )

    db.add(audit_result)
    db.flush()
    return audit_result


def _unique_ordered_stops(shipments: list[Shipment]) -> list[Shipment]:
    """Eindeutige Entladestellen in Ladelisten-Reihenfolge (`sequence_in_tour`),
    dedupliziert ueber (PLZ, Ort) - Namensvarianten derselben Adresse
    (Name1/Name2) zaehlen nicht doppelt und werden nicht zweimal angefahren
    (Nutzerbestaetigung, siehe docs/OFFENE_ENTSCHEIDUNGEN.md)."""
    ordered = sorted(shipments, key=lambda s: (s.sequence_in_tour is None, s.sequence_in_tour or 0))
    seen: set[tuple[str, str]] = set()
    stops: list[Shipment] = []
    for shipment in ordered:
        address = shipment.destination_address
        if not address or not address.postal_code or not address.city:
            continue
        key = (address.postal_code, address.city)
        if key in seen:
            continue
        seen.add(key)
        stops.append(shipment)
    return stops


def run_tour_audit(
    db: Session,
    tour_id: str,
    settings: Settings,
    geocoding_provider: GeocodingProvider,
    routing_provider: RoutingProvider,
) -> AuditResult:
    """Preispruefung fuer eine ganze Tour/Ladeliste (BEGA-Finetuning: eine
    Frachtrechnung bezieht sich auf die gesamte Tour, nicht auf eine
    Einzelsendung, siehe `app/models/tour.py`).

    Kilometerpruefung (Nutzervorgabe "km Pruefung ueber OSM"): der Startpunkt
    (Beladeort) wird ueber die "Absender-Matrix" aufgeloest
    (`app/services/tour_origin_service.py`, Praefix = erste 2 Ziffern der
    Ladelistennummer). Ist kein Praefix hinterlegt oder schlaegt die
    Geokodierung fehl, bleibt die Kilometerpruefung ehrlich unmoeglich
    (`distance_outcome=None` -> MANUELLE_PRUEFUNG) statt eine Adresse zu
    erfinden. Die Referenzstrecke ist die Summe der Einzelstrecken
    Depot -> Entladestelle 1 -> ... -> Entladestelle N (Ladelisten-Reihenfolge,
    dedupliziert), nicht eine echte OSRM-Mehrstopp-Route in einem Aufruf -
    das ist eine dokumentierte Naeherung (siehe docs/OFFENE_ENTSCHEIDUNGEN.md).

    "Anzahl Entladestellen" wird ueber eindeutige (PLZ, Ort)-Paare der
    Sendungen dieser Tour gezaehlt (Namensvarianten derselben Adresse zaehlen
    nicht doppelt, siehe `app/services/ladeliste_pdf_parser.py`).
    """
    tour = db.get(Tour, tour_id)
    if tour is None:
        raise NotFoundError(f"Tour {tour_id} nicht gefunden", entity_type="Tour", entity_id=tour_id)

    stops = _unique_ordered_stops(tour.shipments)
    unloading_point_count = len(stops)

    destination_countries = {
        s.destination_address.country_code for s in stops if s.destination_address.country_code
    }

    origin_address = resolve_tour_origin_address(db, tour.tour_number)
    origin_geocoded = False
    if origin_address is not None:
        try:
            geocode_address_if_needed(origin_address, geocoding_provider)
            origin_geocoded = is_precisely_geocoded(origin_address)
        except Exception:  # noqa: BLE001 - Geocoding-Fehler fliesst als Regelverstoss ein, nicht als Exception
            origin_geocoded = False

    destination_geocoded_flags: list[bool] = []
    for stop in stops:
        try:
            geocode_address_if_needed(stop.destination_address, geocoding_provider)
            destination_geocoded_flags.append(is_precisely_geocoded(stop.destination_address))
        except Exception:  # noqa: BLE001
            destination_geocoded_flags.append(False)
    all_destinations_geocoded = bool(stops) and all(destination_geocoded_flags)

    reference_km: Decimal | None = None
    distance_outcome = None
    if origin_address is not None and origin_geocoded and all_destinations_geocoded and tour.invoiced_km is not None:
        waypoints = [(origin_address.latitude, origin_address.longitude)] + [
            (s.destination_address.latitude, s.destination_address.longitude) for s in stops
        ]
        try:
            total_km = Decimal("0")
            for (lat1, lon1), (lat2, lon2) in zip(waypoints, waypoints[1:]):
                routing_result, _ = get_or_calculate_route(
                    db, origin_lat=lat1, origin_lon=lon1, destination_lat=lat2, destination_lon=lon2,
                    profile=settings.default_routing_profile, provider=routing_provider,
                    provider_name=settings.routing_provider,
                )
                total_km += Decimal(str(routing_result.distance_km))
            reference_km = total_km
            distance_outcome = evaluate_distance(
                invoiced_km=tour.invoiced_km,
                reference_km=reference_km,
                route_context=RouteContext.STANDARD,
                tolerance_config=DistanceToleranceConfig(
                    standard_percent=Decimal(str(settings.km_tolerance_standard_percent)),
                    inner_city_percent=Decimal(str(settings.km_tolerance_inner_city_percent)),
                ),
            )
        except Exception:  # noqa: BLE001 - Routing-Fehler fliesst als Regelverstoss ein, nicht als Exception
            reference_km = None
            distance_outcome = None

    origin_country = (
        origin_address.country_code if origin_address and origin_address.country_code
        else settings.default_tour_origin_country_code
    )

    tariff_orm = None
    tariff_found = False
    tariff_error_message: str | None = None
    expected_amount: Decimal | None = None

    if tour.tour_date is not None:
        if len(destination_countries) > 1:
            tariff_error_message = (
                f"Tour {tour.tour_number} hat Entladestellen in mehreren Laendern "
                f"({', '.join(sorted(destination_countries))}) - automatische Preisberechnung ueber "
                "mehrere Zielaender je Tour ist nicht unterstuetzt (siehe docs/OFFENE_ENTSCHEIDUNGEN.md)."
            )
        else:
            destination_country = next(iter(destination_countries), None)
            try:
                tariff_orm = select_tariff_for_shipment(db, tour.carrier_id, tour.tour_date)
                tariff_found = True
                price_reference_km = reference_km if reference_km is not None else (tour.invoiced_km or Decimal("0"))
                breakdown = calculate_expected_price_for_tariff(
                    tariff_orm,
                    price_reference_km,
                    Decimal("0"),  # keine Zusatzfracht-Pruefung auf Tour-Ebene (MVP)
                    origin_country=origin_country,
                    destination_country=destination_country,
                    unloading_point_count=unloading_point_count,
                    default_additional_unloading_point_price=Decimal(str(settings.default_additional_unloading_point_price_eur)),
                )
                expected_amount = breakdown.total_amount
            except (TariffNotFoundError, MultipleTariffsValidError) as exc:
                tariff_error_message = str(exc)

    price_difference_percent = None
    difference_amount = None
    if expected_amount is not None and tour.invoice_amount is not None:
        deviation = calculate_price_deviation(tour.invoice_amount, expected_amount)
        price_difference_percent = deviation.difference_percent
        difference_amount = deviation.difference_amount

    total_weight_kg = sum((s.weight_kg for s in tour.shipments if s.weight_kg is not None), Decimal("0"))

    rule_input = AuditRuleInput(
        shipment_number=tour.tour_number,
        transport_date_present=tour.tour_date is not None,
        origin_address_present=origin_address is not None,
        destination_address_present=unloading_point_count > 0,
        invoice_amount_present=tour.invoice_amount is not None,
        min_ocr_confidence=_TOUR_PARSE_CONFIDENCE,
        ocr_auto_threshold=settings.ocr_min_auto_confidence,
        ocr_flagged_threshold=settings.ocr_min_flagged_confidence,
        is_unique_shipment_assignment=True,
        origin_geocoded=origin_geocoded,
        destination_geocoded=all_destinations_geocoded,
        distance_outcome=distance_outcome,
        tariff_found=tariff_found,
        tariff_error_message=tariff_error_message,
        price_difference_percent=price_difference_percent,
        price_tolerance_percent=Decimal(str(settings.price_deviation_tolerance_percent)),
        surcharge_statuses=[],
        is_duplicate=False,
        weight_kg=total_weight_kg or None,
        loading_meters=None,
        max_plausible_weight_kg=Decimal(str(settings.plausibility_max_weight_kg)),
        max_plausible_loading_meters=Decimal(str(settings.plausibility_max_loading_meters)),
    )

    rule_outcomes: list[RuleOutcome] = run_audit_rules(rule_input)
    overall_status = derive_overall_status(rule_outcomes)
    explanation = build_explanation(rule_outcomes)

    audit_result = AuditResult(
        tour_id=tour.id,
        tariff_id=tariff_orm.id if tariff_orm else None,
        reference_distance_km=reference_km,
        invoiced_distance_km=tour.invoiced_km,
        expected_amount=expected_amount,
        invoiced_amount=tour.invoice_amount,
        difference_amount=difference_amount,
        difference_percent=price_difference_percent,
        status=AuditStatus(overall_status.value),
        explanation=explanation,
    )
    for outcome in rule_outcomes:
        audit_result.rule_results.append(
            AuditRuleResult(
                rule_code=outcome.rule_code,
                rule_name=outcome.rule_name,
                status=RuleStatus(outcome.status.value),
                actual_value=outcome.actual_value,
                expected_value=outcome.expected_value,
                explanation=outcome.explanation,
            )
        )

    db.add(audit_result)
    db.flush()
    return audit_result
