from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from app.config import Settings
from app.errors import NotFoundError
from app.models.address import Address
from app.models.audit import AuditStatus
from app.models.party import Carrier
from app.models.shipment import Shipment
from app.models.tariff import Tariff, TariffRule, TariffRuleType, TariffStatus
from app.models.tour import Tour
from app.models.tour_origin_mapping import TourOriginMapping
from app.providers.base import GeocodeResult, RouteResult
from app.services.audit_service import run_tour_audit


class _FakeGeocodingProvider:
    """Bestaetigt lediglich das vom Aufrufer mitgegebene Land (country_hint),
    statt es zu erraten - realistischeres Verhalten fuer Tests mit
    laenderuebergreifenden Touren als ein hart codiertes "DE" fuer jede
    Adresse."""

    def geocode(self, request):
        return GeocodeResult(
            matched=True, latitude=52.0, longitude=9.0, normalized_address=request.address_text,
            country_code=request.country_hint or "DE", precision="rooftop", confidence=0.9, provider="fake",
        )


class _FakeRoutingProvider:
    """Jede Teilstrecke ist 50 km lang (fest), damit die Gesamtstrecke
    deterministisch aus der Anzahl der Etappen (Depot->Stopps) berechenbar ist."""

    def calculate_route(self, route_input):
        return RouteResult(
            origin_lat=route_input.origin_lat, origin_lon=route_input.origin_lon,
            destination_lat=route_input.destination_lat, destination_lon=route_input.destination_lon,
            distance_km=50.0, duration_minutes=45, profile=route_input.profile, provider="fake",
            calculated_at=datetime.now(timezone.utc),
        )


def _settings() -> Settings:
    return Settings(database_url="sqlite:///:memory:")


def _carrier(db_session) -> Carrier:
    carrier = Carrier(name="Stylinart", carrier_code="STY-1")
    db_session.add(carrier)
    db_session.flush()
    return carrier


def _all_in_tariff(db_session, carrier: Carrier) -> Tariff:
    tariff = Tariff(
        tariff_code="STY-2026", name="Stylinart 2026", carrier_id=carrier.id,
        valid_from=date(2026, 1, 1), valid_to=None, status=TariffStatus.RELEASED, currency="EUR",
    )
    tariff.rules.append(
        TariffRule(
            rule_type=TariffRuleType.ALL_IN,
            parameters_json={"prices": [{"origin_country": "PL", "destination_country": "DE", "amount": "350.00"}]},
            priority=0,
        )
    )
    tariff.rules.append(
        TariffRule(
            rule_type=TariffRuleType.BASE_PLUS_KM,
            parameters_json={"base_price": "100.00", "price_per_km": "1.00", "minimum_km": "0", "additional_unloading_point_price": "50.00"},
            priority=1,
        )
    )
    db_session.add(tariff)
    db_session.flush()
    return tariff


def _origin_mapping(db_session, prefix: str = "19") -> TourOriginMapping:
    mapping = TourOriginMapping(
        tour_number_prefix=prefix,
        label="Test-Depot Polen",
        origin_address=Address(original_text="Depot, Polen", city="Stettin", country_code="PL"),
    )
    db_session.add(mapping)
    db_session.flush()
    return mapping


def _shipment(tour: Tour, carrier: Carrier, *, order: str, postal_code: str, city: str, weight_kg: str, sequence: int) -> Shipment:
    return Shipment(
        shipment_number=order,
        tour_id=tour.id,
        carrier_id=carrier.id,
        transport_date=tour.tour_date,
        destination_address=Address(
            original_text=f"Firma {order}\nMusterstr. 1\nD-{postal_code} {city}",
            postal_code=postal_code,
            city=city,
            country_code="DE",
        ),
        weight_kg=Decimal(weight_kg),
        sequence_in_tour=sequence,
    )


def _run(db_session, tour_id: str):
    return run_tour_audit(db_session, tour_id, _settings(), _FakeGeocodingProvider(), _FakeRoutingProvider())


def test_run_tour_audit_uses_fixfracht_for_single_unloading_point(db_session):
    carrier = _carrier(db_session)
    _all_in_tariff(db_session, carrier)
    _origin_mapping(db_session)

    tour = Tour(
        tour_number="1918622", carrier_id=carrier.id, tour_date=date(2026, 9, 15),
        invoiced_km=Decimal("50"), invoice_amount=Decimal("350.00"),
    )
    db_session.add(tour)
    db_session.flush()
    db_session.add(_shipment(tour, carrier, order="A1", postal_code="50259", city="Pulheim", weight_kg="35", sequence=0))
    db_session.commit()

    result = _run(db_session, tour.id)

    assert result.expected_amount == Decimal("350.00")
    assert result.reference_distance_km == Decimal("50")  # 1 Etappe Depot -> Pulheim, je Etappe 50 km (Fake-Provider)
    assert result.status == AuditStatus.BESTANDEN


def test_run_tour_audit_dedups_unloading_points_by_postal_code_and_city(db_session):
    """Zwei Auftraege mit unterschiedlichem Adresstext, aber gleicher PLZ/Ort,
    zaehlen als EINE Entladestelle (Nutzerbestaetigung, siehe
    docs/OFFENE_ENTSCHEIDUNGEN.md) - die Fixfracht fuer 1 Entladestelle bleibt
    also anwendbar, und die Route hat nur 1 Etappe (nicht 2)."""
    carrier = _carrier(db_session)
    _all_in_tariff(db_session, carrier)
    _origin_mapping(db_session)

    tour = Tour(
        tour_number="1918622", carrier_id=carrier.id, tour_date=date(2026, 9, 15),
        invoiced_km=Decimal("50"), invoice_amount=Decimal("350.00"),
    )
    db_session.add(tour)
    db_session.flush()
    db_session.add(_shipment(tour, carrier, order="A1", postal_code="50259", city="Pulheim", weight_kg="35", sequence=0))
    db_session.add(_shipment(tour, carrier, order="A2", postal_code="50259", city="Pulheim", weight_kg="34", sequence=1))
    db_session.commit()

    result = _run(db_session, tour.id)

    assert result.expected_amount == Decimal("350.00")  # weiterhin Fixfracht, kein Zuschlag
    assert result.reference_distance_km == Decimal("50")  # nur 1 Etappe, nicht 2


def test_run_tour_audit_applies_surcharge_for_additional_unloading_points(db_session):
    carrier = _carrier(db_session)
    _all_in_tariff(db_session, carrier)
    _origin_mapping(db_session)

    tour = Tour(
        tour_number="1918628", carrier_id=carrier.id, tour_date=date(2026, 9, 15),
        invoiced_km=Decimal("150"), invoice_amount=Decimal("400.00"),
    )
    db_session.add(tour)
    db_session.flush()
    db_session.add(_shipment(tour, carrier, order="A1", postal_code="06188", city="Sietzsch", weight_kg="130", sequence=0))
    db_session.add(_shipment(tour, carrier, order="A2", postal_code="06116", city="Halle", weight_kg="246", sequence=1))
    db_session.add(_shipment(tour, carrier, order="A3", postal_code="42304", city="Teutschenthal", weight_kg="100", sequence=2))
    db_session.commit()

    result = _run(db_session, tour.id)

    # base_plus_km greift (3 Entladestellen -> keine Fixfracht): 100 + 150*1.00 + 2*50 = 350
    assert result.reference_distance_km == Decimal("150")  # 3 Etappen Depot->1->2->3, je 50 km
    assert result.expected_amount == Decimal("350.00")
    assert result.status == AuditStatus.ABWEICHUNG  # Rechnung (400) weicht vom Sollpreis (350) ab


def test_run_tour_audit_flags_multiple_destination_countries_for_manual_review(db_session):
    carrier = _carrier(db_session)
    _all_in_tariff(db_session, carrier)
    _origin_mapping(db_session)

    tour = Tour(tour_number="1918699", carrier_id=carrier.id, tour_date=date(2026, 9, 15), invoice_amount=Decimal("350.00"))
    db_session.add(tour)
    db_session.flush()
    shipment_de = _shipment(tour, carrier, order="A1", postal_code="50259", city="Pulheim", weight_kg="35", sequence=0)
    shipment_fr = _shipment(tour, carrier, order="A2", postal_code="75000", city="Paris", weight_kg="35", sequence=1)
    shipment_fr.destination_address.country_code = "FR"
    db_session.add(shipment_de)
    db_session.add(shipment_fr)
    db_session.commit()

    result = _run(db_session, tour.id)

    assert result.status == AuditStatus.MANUELLE_PRUEFUNG
    assert result.expected_amount is None
    assert any("mehreren Laendern" in r.explanation for r in result.rule_results)


def test_run_tour_audit_falls_back_to_manual_review_without_origin_mapping(db_session):
    """Kein Praefix in der Absender-Matrix hinterlegt -> keine Route berechenbar,
    ehrlich MANUELLE_PRUEFUNG statt eine Adresse zu erfinden (Nutzervorgabe:
    "LL Kreise - Absender Matrix bauen", siehe docs/OFFENE_ENTSCHEIDUNGEN.md)."""
    carrier = _carrier(db_session)
    _all_in_tariff(db_session, carrier)
    # Keine TourOriginMapping angelegt.

    tour = Tour(
        tour_number="1918622", carrier_id=carrier.id, tour_date=date(2026, 9, 15),
        invoiced_km=Decimal("50"), invoice_amount=Decimal("350.00"),
    )
    db_session.add(tour)
    db_session.flush()
    db_session.add(_shipment(tour, carrier, order="A1", postal_code="50259", city="Pulheim", weight_kg="35", sequence=0))
    db_session.commit()

    result = _run(db_session, tour.id)

    assert result.reference_distance_km is None
    assert result.status == AuditStatus.MANUELLE_PRUEFUNG
    # Der Tarif greift trotzdem (Fixfracht faellt auf den globalen Standard-Ursprungsland
    # zurueck), nur die Kilometerpruefung selbst bleibt offen.
    assert result.expected_amount == Decimal("350.00")


def test_run_tour_audit_raises_not_found_for_unknown_tour(db_session):
    with pytest.raises(NotFoundError):
        _run(db_session, "does-not-exist")
