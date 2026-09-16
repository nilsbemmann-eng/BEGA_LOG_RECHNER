from datetime import date

from decimal import Decimal

from app.config import get_settings
from app.main import app
from app.models.audit import AuditResult, AuditStatus
from app.models.party import Carrier
from app.models.shipment import Shipment
from app.models.user import User, UserRole


def _seed_admin(db_session) -> User:
    admin = User(name="Admin", email="admin@example.invalid", role=UserRole.ADMIN, active=True)
    db_session.add(admin)
    db_session.commit()
    return admin


def _seed_history(db_session) -> tuple[AuditResult, AuditResult]:
    acme = Carrier(name="ACME Spedition", carrier_code="ACME")
    beta = Carrier(name="Beta Logistik", carrier_code="BETA")
    db_session.add_all([acme, beta])
    db_session.commit()

    shipment1 = Shipment(shipment_number="A-1", carrier_id=acme.id, transport_date=date(2026, 1, 10), invoice_amount=Decimal("200.00"))
    shipment2 = Shipment(shipment_number="B-2", carrier_id=beta.id, transport_date=date(2026, 2, 15), invoice_amount=Decimal("300.00"))
    db_session.add_all([shipment1, shipment2])
    db_session.commit()

    audit1 = AuditResult(shipment_id=shipment1.id, status=AuditStatus.BESTANDEN, explanation="ok", expected_amount=Decimal("200.00"), invoiced_amount=Decimal("200.00"))
    audit2 = AuditResult(shipment_id=shipment2.id, status=AuditStatus.ABWEICHUNG, explanation="Preisabweichung", expected_amount=Decimal("250.00"), invoiced_amount=Decimal("300.00"))
    db_session.add_all([audit1, audit2])
    db_session.commit()
    return audit1, audit2


def test_list_audits_includes_shipment_and_carrier_details(client, db_session):
    _seed_admin(db_session)
    audit1, _audit2 = _seed_history(db_session)

    response = client.get("/api/audits")
    assert response.status_code == 200
    by_id = {row["id"]: row for row in response.json()}
    assert by_id[audit1.id]["shipment_number"] == "A-1"
    assert by_id[audit1.id]["carrier_name"] == "ACME Spedition"


def test_search_filters_by_status(client, db_session):
    _seed_admin(db_session)
    audit1, audit2 = _seed_history(db_session)

    response = client.get("/api/audits", params={"status": "ABWEICHUNG"})
    ids = [row["id"] for row in response.json()]
    assert ids == [audit2.id]
    assert audit1.id not in ids


def test_search_filters_by_free_text_carrier_name(client, db_session):
    _seed_admin(db_session)
    audit1, audit2 = _seed_history(db_session)

    response = client.get("/api/audits", params={"q": "Beta"})
    ids = [row["id"] for row in response.json()]
    assert ids == [audit2.id]


def test_search_filters_by_free_text_shipment_number(client, db_session):
    _seed_admin(db_session)
    audit1, audit2 = _seed_history(db_session)

    response = client.get("/api/audits", params={"q": "a-1"})
    ids = [row["id"] for row in response.json()]
    assert ids == [audit1.id]


def test_search_filters_by_date_range(client, db_session):
    _seed_admin(db_session)
    audit1, audit2 = _seed_history(db_session)

    response = client.get("/api/audits", params={"date_from": "2026-02-01"})
    ids = [row["id"] for row in response.json()]
    assert ids == [audit2.id]


def test_export_and_download_csv(client, db_session, tmp_path):
    _seed_admin(db_session)
    audit1, audit2 = _seed_history(db_session)

    base_settings = get_settings()
    export_settings = base_settings.model_copy(update={"export_storage_path": str(tmp_path)})
    app.dependency_overrides[get_settings] = lambda: export_settings
    try:
        create_response = client.post(
            "/api/exports", json={"audit_result_ids": [audit1.id, audit2.id], "file_format": "csv"}
        )
        assert create_response.status_code == 200, create_response.text
        export_payload = create_response.json()
        assert export_payload["row_count"] == 2
        assert export_payload["download_url"].endswith(f"/api/exports/{export_payload['export_id']}/download")

        download_response = client.get(export_payload["download_url"])
        assert download_response.status_code == 200
        assert download_response.headers["content-type"].startswith("text/csv")
        body = download_response.content.decode("utf-8-sig")
        assert "A-1" in body
        assert "B-2" in body
    finally:
        app.dependency_overrides.pop(get_settings, None)


def test_export_download_unknown_id_returns_404(client, db_session):
    _seed_admin(db_session)
    response = client.get("/api/exports/does-not-exist/download")
    assert response.status_code == 404
