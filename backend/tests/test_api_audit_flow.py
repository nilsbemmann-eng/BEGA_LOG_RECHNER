from datetime import date, datetime, timezone
from decimal import Decimal

from app.api.deps import get_geocoding_provider, get_routing_provider
from app.main import app
from app.models.address import Address
from app.models.attachment import Attachment
from app.models.document import Document, DocumentType, ExtractedField, OcrStatus
from app.models.email import Email, EmailProcessingStatus
from app.models.mailbox import Mailbox
from app.models.party import Carrier
from app.models.shipment import Shipment
from app.models.user import User, UserRole
from app.providers.base import GeocodeResult, RouteResult


class _FakeGeocodingProvider:
    def geocode(self, request):
        return GeocodeResult(
            matched=True, latitude=52.0, longitude=9.0, normalized_address=request.address_text,
            country_code="DE", precision="rooftop", confidence=0.9, provider="fake",
        )


class _FakeRoutingProvider:
    def calculate_route(self, route_input):
        return RouteResult(
            origin_lat=route_input.origin_lat, origin_lon=route_input.origin_lon,
            destination_lat=route_input.destination_lat, destination_lon=route_input.destination_lon,
            distance_km=100.0, duration_minutes=90, profile=route_input.profile, provider="fake",
            calculated_at=datetime.now(timezone.utc),
        )


def _seed_admin(db_session) -> User:
    admin = User(name="Admin", email="admin@example.invalid", role=UserRole.ADMIN, active=True)
    db_session.add(admin)
    db_session.commit()
    return admin


def test_full_audit_flow_passes_when_within_tolerance(client, db_session):
    _seed_admin(db_session)

    carrier = Carrier(name="ACME Spedition", carrier_code="ACME")
    db_session.add(carrier)
    db_session.commit()

    tariff_response = client.post(
        "/api/tariffs",
        json={
            "tariff_code": "ACME-2026",
            "name": "ACME Standardtarif 2026",
            "carrier_id": carrier.id,
            "valid_from": "2026-01-01",
            "valid_to": None,
            "currency": "EUR",
            "rules": [{"rule_type": "base_plus_km", "parameters": {"base_price": "100.00", "price_per_km": "1.00", "minimum_km": "0"}, "priority": 0}],
        },
    )
    assert tariff_response.status_code == 201, tariff_response.text

    shipment = Shipment(
        shipment_number="SEND-1",
        transport_date=date(2026, 6, 1),
        carrier_id=carrier.id,
        origin_address=Address(original_text="Hannover, Deutschland"),
        destination_address=Address(original_text="Bremen, Deutschland"),
        invoiced_km=Decimal("105"),
        invoice_amount=Decimal("205.00"),
        weight_kg=Decimal("5000"),
    )
    db_session.add(shipment)
    db_session.commit()

    # Ein Dokument mit hoher OCR-Konfidenz simuliert eine bereits verarbeitete
    # Frachtrechnung, wie sie in der Praxis vor einem Audit-Lauf vorliegt
    # (Abschnitt 2: OCR erfolgt vor der Preispruefung).
    mailbox = Mailbox(name="INBOX", provider="imap", configuration_reference="test")
    db_session.add(mailbox)
    db_session.commit()
    email = Email(
        external_message_id="<msg-1@example.invalid>", mailbox_id=mailbox.id, sender="spediteur@example.invalid",
        recipients="", cc_recipients="", subject="Rechnung", received_at=datetime.now(timezone.utc),
        body_text="", processing_status=EmailProcessingStatus.PROCESSED,
    )
    attachment = Attachment(filename="rechnung.pdf", mime_type="application/pdf", file_hash="a" * 64, storage_reference="x", file_size=10)
    email.attachments.append(attachment)
    document = Document(document_type=DocumentType.FRACHTRECHNUNG, classification_confidence=0.95, ocr_status=OcrStatus.DONE, page_count=1, shipment_id=shipment.id)
    document.extracted_fields.append(
        ExtractedField(field_name="invoice_amount", original_value="205,00 EUR", normalized_value="205.00", data_type="decimal", confidence=0.97, extraction_method="pdf_text_regex")
    )
    attachment.document = document
    db_session.add(email)
    db_session.commit()

    app.dependency_overrides[get_geocoding_provider] = lambda: _FakeGeocodingProvider()
    app.dependency_overrides[get_routing_provider] = lambda: _FakeRoutingProvider()
    try:
        response = client.post("/api/audits/run", json={"shipment_id": shipment.id, "route_context": "standard"})
    finally:
        app.dependency_overrides.pop(get_geocoding_provider, None)
        app.dependency_overrides.pop(get_routing_provider, None)

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["status"] == "BESTANDEN"
    assert payload["expected_amount"] == "200.00"
    assert payload["reference_distance_km"] == "100.00"


def test_audit_run_missing_shipment_returns_404(client, db_session):
    _seed_admin(db_session)
    response = client.post("/api/audits/run", json={"shipment_id": "does-not-exist", "route_context": "standard"})
    assert response.status_code == 404
    assert response.json()["error_code"] == "not_found"
