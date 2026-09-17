import io
from datetime import date, datetime, timezone
from decimal import Decimal

from openpyxl import Workbook

from app.api.deps import get_geocoding_provider, get_routing_provider
from app.main import app
from app.models.address import Address
from app.models.audit import AuditResult, AuditStatus
from app.models.party import Carrier
from app.models.tariff import Tariff, TariffRule, TariffRuleType, TariffStatus
from app.models.tour import Tour
from app.models.user import User, UserRole
from app.providers.base import GeocodeResult, RouteResult


class _FakeGeocodingProvider:
    def geocode(self, request):
        return GeocodeResult(
            matched=True, latitude=52.0, longitude=9.0, normalized_address=request.address_text,
            country_code=request.country_hint or "DE", precision="rooftop", confidence=0.9, provider="fake",
        )


class _FakeRoutingProvider:
    def calculate_route(self, route_input):
        return RouteResult(
            origin_lat=route_input.origin_lat, origin_lon=route_input.origin_lon,
            destination_lat=route_input.destination_lat, destination_lon=route_input.destination_lon,
            distance_km=50.0, duration_minutes=45, profile=route_input.profile, provider="fake",
            calculated_at=datetime.now(timezone.utc),
        )


def _seed_admin(db_session) -> User:
    admin = User(name="Admin", email="admin@example.invalid", role=UserRole.ADMIN, active=True)
    db_session.add(admin)
    db_session.commit()
    return admin


def test_create_and_list_tour_origin_mapping(client, db_session):
    _seed_admin(db_session)

    response = client.post(
        "/api/tour-origin-mappings",
        json={"tour_number_prefix": "19", "matchcode": "MP", "description": "Meble Polskie", "city": "Stettin", "country_code": "PL"},
    )
    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["tour_number_prefix"] == "19"
    assert payload["matchcode"] == "MP"
    assert payload["city"] == "Stettin"

    list_response = client.get("/api/tour-origin-mappings")
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1


def test_run_tour_audit_endpoint_and_tour_endpoints(client, db_session):
    _seed_admin(db_session)

    carrier = Carrier(name="Stylinart", carrier_code="STY-1")
    db_session.add(carrier)
    db_session.commit()

    tariff_response = client.post(
        "/api/tariffs",
        json={
            "tariff_code": "STY-2026",
            "name": "Stylinart 2026",
            "carrier_id": carrier.id,
            "valid_from": "2026-01-01",
            "valid_to": None,
            "currency": "EUR",
            "rules": [
                {
                    "rule_type": "base_plus_km",
                    "parameters": {"base_price": "0", "price_per_km": "1.00", "minimum_km": "0"},
                    "priority": 0,
                }
            ],
        },
    )
    assert tariff_response.status_code == 201, tariff_response.text

    mapping_response = client.post(
        "/api/tour-origin-mappings",
        json={"tour_number_prefix": "19", "matchcode": "MP", "city": "Stettin", "country_code": "PL"},
    )
    assert mapping_response.status_code == 201, mapping_response.text

    tour = Tour(
        tour_number="1918622", carrier_id=carrier.id, tour_date=date(2026, 9, 15),
        invoiced_km=Decimal("50"), invoice_amount=Decimal("50.00"),
    )
    db_session.add(tour)
    db_session.flush()
    from app.models.shipment import Shipment

    db_session.add(
        Shipment(
            shipment_number="A1", tour_id=tour.id, carrier_id=carrier.id, transport_date=tour.tour_date,
            destination_address=Address(original_text="x", postal_code="50259", city="Pulheim", country_code="DE"),
            weight_kg=Decimal("35"), sequence_in_tour=0,
        )
    )
    db_session.commit()

    tours_response = client.get("/api/tours")
    assert tours_response.status_code == 200
    assert tours_response.json()[0]["tour_number"] == "1918622"
    assert tours_response.json()[0]["shipment_count"] == 1

    tour_detail_response = client.get(f"/api/tours/{tour.id}")
    assert tour_detail_response.status_code == 200
    assert tour_detail_response.json()["shipments"][0]["destination_city"] == "Pulheim"

    app.dependency_overrides[get_geocoding_provider] = lambda: _FakeGeocodingProvider()
    app.dependency_overrides[get_routing_provider] = lambda: _FakeRoutingProvider()
    try:
        response = client.post("/api/audits/run-tour", json={"tour_id": tour.id})
    finally:
        app.dependency_overrides.pop(get_geocoding_provider, None)
        app.dependency_overrides.pop(get_routing_provider, None)

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["status"] == "BESTANDEN"
    assert payload["expected_amount"] == "50.00"
    assert payload["shipment_id"] is None
    assert payload["tour_id"] == tour.id
    assert payload["shipment_number"] == "1918622"  # faellt auf die Tour-Nummer zurueck


def test_historie_includes_tour_audit_results(client, db_session):
    """Regressionstest fuer den Outer-Join-Fix in list_audits: Tour-Pruefungen
    (shipment_id=None) duerfen aus der Historie nicht verschwinden."""
    _seed_admin(db_session)

    tour = Tour(tour_number="1918622", tour_date=date(2026, 9, 15))
    db_session.add(tour)
    db_session.flush()
    db_session.add(
        AuditResult(tour_id=tour.id, status=AuditStatus.BESTANDEN, explanation="Alle Pruefregeln wurden erfolgreich bestanden.")
    )
    db_session.commit()

    response = client.get("/api/audits")
    assert response.status_code == 200
    results = response.json()
    assert len(results) == 1
    assert results[0]["tour_id"] == tour.id
    assert results[0]["shipment_id"] is None
    assert results[0]["shipment_number"] == "1918622"


def test_import_tour_origin_matrix_endpoint(client, db_session):
    _seed_admin(db_session)

    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["Matchcode", "Bezeichnung", "Präfix", "Absender", "Absenderadresse"])
    sheet.append(["MP", "Meble Polskie", 19, "Meble Polskie Janusz Fijalek", "PL 22-400 Zamosc ul. Strefowa 10"])
    buffer = io.BytesIO()
    workbook.save(buffer)

    response = client.post(
        "/api/tour-origin-mappings/import",
        files={"file": ("Gebietsrelationen.xlsx", buffer.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )

    assert response.status_code == 200, response.text
    assert response.json()["imported_count"] == 1

    list_response = client.get("/api/tour-origin-mappings")
    assert len(list_response.json()) == 1
    assert list_response.json()[0]["matchcode"] == "MP"
