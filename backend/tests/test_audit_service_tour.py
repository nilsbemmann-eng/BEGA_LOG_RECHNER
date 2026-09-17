from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from app.config import Settings
from app.errors import NotFoundError
from app.models.address import Address
from app.models.audit import AuditStatus
from app.models.party import Carrier
from app.models.shipment import Shipment
from app.models.special_agreement_surcharge import SpecialAgreementSurcharge
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


def _carrier(db_session, name: str = "Stylinart") -> Carrier:
    carrier = Carrier(name=name, carrier_code=name.upper()[:10])
    db_session.add(carrier)
    db_session.flush()
    return carrier


def _tariff(db_session, carrier: Carrier, **extra_params) -> Tariff:
    """base_plus_km-Tarif nach realer BEGA-Preisformel: kein Grundpreis, nur
    km-Preis + Entladestellen-Zuschlag (siehe app/tariff_engine/engine.py)."""
    params = {"base_price": "0", "price_per_km": "1.00", "minimum_km": "0", "additional_unloading_point_price": "50.00"}
    params.update(extra_params)
    tariff = Tariff(
        tariff_code=f"{carrier.carrier_code}-2026", name=f"{carrier.name} 2026", carrier_id=carrier.id,
        valid_from=date(2026, 1, 1), valid_to=None, status=TariffStatus.RELEASED, currency="EUR",
    )
    tariff.rules.append(TariffRule(rule_type=TariffRuleType.BASE_PLUS_KM, parameters_json=params, priority=0))
    db_session.add(tariff)
    db_session.flush()
    return tariff


def _origin_mapping(db_session, prefix: str = "19") -> TourOriginMapping:
    mapping = TourOriginMapping(
        tour_number_prefix=prefix,
        matchcode="TEST-DEPOT",
        description="Test-Depot Polen",
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


def test_run_tour_audit_calculates_km_based_price_for_single_unloading_point(db_session):
    carrier = _carrier(db_session)
    _tariff(db_session, carrier)
    _origin_mapping(db_session)

    tour = Tour(
        tour_number="1918622", carrier_id=carrier.id, tour_date=date(2026, 9, 15),
        invoiced_km=Decimal("50"), invoice_amount=Decimal("50.00"),
    )
    db_session.add(tour)
    db_session.flush()
    db_session.add(_shipment(tour, carrier, order="A1", postal_code="50259", city="Pulheim", weight_kg="35", sequence=0))
    db_session.commit()

    result = _run(db_session, tour.id)

    # 1 Etappe Depot -> Pulheim (Fake-Provider: 50 km) * 1,00 EUR/km, keine Fixfracht mehr (reale Formel)
    assert result.reference_distance_km == Decimal("50")
    assert result.expected_amount == Decimal("50")
    assert result.status == AuditStatus.BESTANDEN


def test_run_tour_audit_dedups_unloading_points_by_postal_code_and_city(db_session):
    """Zwei Auftraege mit unterschiedlichem Adresstext, aber gleicher PLZ/Ort,
    zaehlen als EINE Entladestelle (Nutzerbestaetigung, siehe
    docs/OFFENE_ENTSCHEIDUNGEN.md) - nur 1 Etappe, kein Entladestellen-Zuschlag."""
    carrier = _carrier(db_session)
    _tariff(db_session, carrier)
    _origin_mapping(db_session)

    tour = Tour(
        tour_number="1918622", carrier_id=carrier.id, tour_date=date(2026, 9, 15),
        invoiced_km=Decimal("50"), invoice_amount=Decimal("50.00"),
    )
    db_session.add(tour)
    db_session.flush()
    db_session.add(_shipment(tour, carrier, order="A1", postal_code="50259", city="Pulheim", weight_kg="35", sequence=0))
    db_session.add(_shipment(tour, carrier, order="A2", postal_code="50259", city="Pulheim", weight_kg="34", sequence=1))
    db_session.commit()

    result = _run(db_session, tour.id)

    assert result.reference_distance_km == Decimal("50")  # nur 1 Etappe, nicht 2
    assert result.expected_amount == Decimal("50")  # kein Zuschlag fuer nur 1 Entladestelle


def test_run_tour_audit_applies_surcharge_for_additional_unloading_points(db_session):
    carrier = _carrier(db_session)
    _tariff(db_session, carrier)
    _origin_mapping(db_session)

    tour = Tour(
        tour_number="1918628", carrier_id=carrier.id, tour_date=date(2026, 9, 15),
        invoiced_km=Decimal("150"), invoice_amount=Decimal("250.00"),
    )
    db_session.add(tour)
    db_session.flush()
    db_session.add(_shipment(tour, carrier, order="A1", postal_code="06188", city="Sietzsch", weight_kg="130", sequence=0))
    db_session.add(_shipment(tour, carrier, order="A2", postal_code="06116", city="Halle", weight_kg="246", sequence=1))
    db_session.add(_shipment(tour, carrier, order="A3", postal_code="42304", city="Teutschenthal", weight_kg="100", sequence=2))
    db_session.commit()

    result = _run(db_session, tour.id)

    # 3 Etappen Depot->1->2->3 (je 50 km) * 1,00 EUR/km + 2 zusaetzliche Entladestellen * 50 EUR = 150+100 = 250
    assert result.reference_distance_km == Decimal("150")
    assert result.expected_amount == Decimal("250")
    assert result.status == AuditStatus.BESTANDEN


def test_run_tour_audit_adds_toll_cost(db_session):
    carrier = _carrier(db_session)
    _tariff(db_session, carrier)
    _origin_mapping(db_session)

    tour = Tour(
        tour_number="1918622", carrier_id=carrier.id, tour_date=date(2026, 9, 15),
        invoiced_km=Decimal("50"), toll_km=Decimal("100"), invoice_amount=Decimal("66.00"),
    )
    db_session.add(tour)
    db_session.flush()
    db_session.add(_shipment(tour, carrier, order="A1", postal_code="50259", city="Pulheim", weight_kg="35", sequence=0))
    db_session.commit()

    result = _run(db_session, tour.id)

    # km-Preis 50 + Maut 100 km * 0,158 EUR/km = 15,8 -> 65,8 -> aufgerundet auf 66 (reale Formel: ROUNDUP)
    assert result.expected_amount == Decimal("66")
    assert result.status == AuditStatus.BESTANDEN


def test_run_tour_audit_toll_exempt_carrier_ignores_toll_km(db_session):
    carrier = _carrier(db_session, name="BABINSKI")
    _tariff(db_session, carrier, toll_exempt=True)
    _origin_mapping(db_session)

    tour = Tour(
        tour_number="1918622", carrier_id=carrier.id, tour_date=date(2026, 9, 15),
        invoiced_km=Decimal("50"), toll_km=Decimal("100"), invoice_amount=Decimal("50.00"),
    )
    db_session.add(tour)
    db_session.flush()
    db_session.add(_shipment(tour, carrier, order="A1", postal_code="50259", city="Pulheim", weight_kg="35", sequence=0))
    db_session.commit()

    result = _run(db_session, tour.id)

    assert result.expected_amount == Decimal("50")  # keine Maut trotz toll_km=100
    assert result.status == AuditStatus.BESTANDEN


def test_run_tour_audit_adds_special_agreement_surcharge_by_prefix(db_session):
    carrier = _carrier(db_session)
    _tariff(db_session, carrier)
    _origin_mapping(db_session)
    db_session.add(SpecialAgreementSurcharge(tour_number_prefix="19", amount=Decimal("100.00")))

    tour = Tour(
        tour_number="1918622", carrier_id=carrier.id, tour_date=date(2026, 9, 15),
        invoiced_km=Decimal("50"), invoice_amount=Decimal("150.00"),
    )
    db_session.add(tour)
    db_session.flush()
    db_session.add(_shipment(tour, carrier, order="A1", postal_code="50259", city="Pulheim", weight_kg="35", sequence=0))
    db_session.commit()

    result = _run(db_session, tour.id)

    assert result.expected_amount == Decimal("150")  # 50 km-Preis + 100 Sondervereinbarung
    assert result.status == AuditStatus.BESTANDEN


def test_run_tour_audit_applies_prefix_country_rate_override(db_session):
    """Reale Ausnahme aus dem BEGA-Excel: bestimmte Frachtfuehrer+Praefix+Land-
    Kombinationen haben einen manuell verhandelten Sonder-km-Satz, der
    Vorrang vor dem Standardsatz hat (siehe docs/OFFENE_ENTSCHEIDUNGEN.md)."""
    carrier = _carrier(db_session, name="PAWLICHA")
    _tariff(db_session, carrier, prefix_country_rate_overrides=[
        {"tour_number_prefix": "78", "destination_countries": ["DE"], "price_per_km": "1.35"},
    ])
    _origin_mapping(db_session, prefix="78")

    tour = Tour(
        tour_number="7818622", carrier_id=carrier.id, tour_date=date(2026, 9, 15),
        invoiced_km=Decimal("50"), invoice_amount=Decimal("67.50"),
    )
    db_session.add(tour)
    db_session.flush()
    db_session.add(_shipment(tour, carrier, order="A1", postal_code="50259", city="Pulheim", weight_kg="35", sequence=0))
    db_session.commit()

    result = _run(db_session, tour.id)

    assert result.expected_amount == Decimal("68")  # 50 km * 1,35 EUR/km = 67,5 -> aufgerundet auf 68
    assert result.status == AuditStatus.BESTANDEN


def test_run_tour_audit_approves_invoice_below_expected_by_any_margin(db_session):
    """Reale Genehmigungsregel: kein Toleranzband, ein niedrigerer
    Rechnungsbetrag ist unbegrenzt unproblematisch."""
    carrier = _carrier(db_session)
    _tariff(db_session, carrier)
    _origin_mapping(db_session)

    tour = Tour(
        tour_number="1918622", carrier_id=carrier.id, tour_date=date(2026, 9, 15),
        invoiced_km=Decimal("50"), invoice_amount=Decimal("1.00"),
    )
    db_session.add(tour)
    db_session.flush()
    db_session.add(_shipment(tour, carrier, order="A1", postal_code="50259", city="Pulheim", weight_kg="35", sequence=0))
    db_session.commit()

    result = _run(db_session, tour.id)

    assert result.expected_amount == Decimal("50")
    assert result.status == AuditStatus.BESTANDEN


def test_run_tour_audit_fails_when_invoice_exceeds_expected_even_slightly(db_session):
    carrier = _carrier(db_session)
    _tariff(db_session, carrier)
    _origin_mapping(db_session)

    tour = Tour(
        tour_number="1918622", carrier_id=carrier.id, tour_date=date(2026, 9, 15),
        invoiced_km=Decimal("50"), invoice_amount=Decimal("50.01"),
    )
    db_session.add(tour)
    db_session.flush()
    db_session.add(_shipment(tour, carrier, order="A1", postal_code="50259", city="Pulheim", weight_kg="35", sequence=0))
    db_session.commit()

    result = _run(db_session, tour.id)

    assert result.expected_amount == Decimal("50")
    assert result.status == AuditStatus.ABWEICHUNG


def test_run_tour_audit_flags_multiple_destination_countries_for_manual_review(db_session):
    carrier = _carrier(db_session)
    _tariff(db_session, carrier)
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
    _tariff(db_session, carrier)
    # Keine TourOriginMapping angelegt.

    tour = Tour(
        tour_number="1918622", carrier_id=carrier.id, tour_date=date(2026, 9, 15),
        invoiced_km=Decimal("50"), invoice_amount=Decimal("50.00"),
    )
    db_session.add(tour)
    db_session.flush()
    db_session.add(_shipment(tour, carrier, order="A1", postal_code="50259", city="Pulheim", weight_kg="35", sequence=0))
    db_session.commit()

    result = _run(db_session, tour.id)

    assert result.reference_distance_km is None
    assert result.status == AuditStatus.MANUELLE_PRUEFUNG
    # Der Tarif greift trotzdem (km-Preis faellt auf tour.invoiced_km zurueck,
    # Land faellt auf den globalen Standardwert zurueck), nur die
    # Kilometerpruefung selbst bleibt offen.
    assert result.expected_amount == Decimal("50")


def test_run_tour_audit_falls_back_to_manual_review_on_ambiguous_matchcodes(db_session):
    """Realer Fall aus Gebietsrelationen.xlsx: derselbe Praefix (z. B. '12')
    kann mehreren Matchcodes mit UNTERSCHIEDLICHEN Absenderadressen zugeordnet
    sein - Nutzervorgabe: bei Mehrdeutigkeit bleibt es MANUELLE_PRUEFUNG,
    statt eine der Adressen zu raten."""
    carrier = _carrier(db_session)
    _tariff(db_session, carrier)
    db_session.add(TourOriginMapping(
        tour_number_prefix="12", matchcode="SHUTTLESER", description="Shuttle Dabrowka (UA)",
        origin_address=Address(original_text="UA 80200 Radekhiv", city="Radekhiv", country_code="UA"),
    ))
    db_session.add(TourOriginMapping(
        tour_number_prefix="12", matchcode="OTTO D", description="OTTO NORD SUED",
        origin_address=Address(original_text="PL 39-300 Mielec", city="Mielec", country_code="PL"),
    ))
    db_session.flush()

    tour = Tour(
        tour_number="1218622", carrier_id=carrier.id, tour_date=date(2026, 9, 15),
        invoiced_km=Decimal("50"), invoice_amount=Decimal("50.00"),
    )
    db_session.add(tour)
    db_session.flush()
    db_session.add(_shipment(tour, carrier, order="A1", postal_code="50259", city="Pulheim", weight_kg="35", sequence=0))
    db_session.commit()

    result = _run(db_session, tour.id)

    assert result.reference_distance_km is None
    assert result.status == AuditStatus.MANUELLE_PRUEFUNG
    assert "mehrdeutig" in result.explanation
    assert "SHUTTLESER" in result.explanation
    assert "OTTO D" in result.explanation


def test_run_tour_audit_raises_not_found_for_unknown_tour(db_session):
    with pytest.raises(NotFoundError):
        _run(db_session, "does-not-exist")
