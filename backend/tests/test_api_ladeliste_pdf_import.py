from datetime import date
from decimal import Decimal
from unittest.mock import patch

from sqlalchemy import select

from app.models.tour import Tour
from app.models.user import User, UserRole
from app.services.ladeliste_pdf_parser import ParsedAddress, ParsedLadeliste, ParsedOrder

_PATCH_TARGET = "app.services.ladeliste_pdf_import_service.parse_ladeliste_pdf"


def _seed_admin(db_session) -> User:
    admin = User(name="Admin", email="admin@example.invalid", role=UserRole.ADMIN, active=True)
    db_session.add(admin)
    db_session.commit()
    return admin


def _make_parsed() -> ParsedLadeliste:
    address = ParsedAddress(
        original_text="Musterfirma\nMusterstr. 1\nD-50259 Pulheim",
        street="Musterstr. 1",
        postal_code="50259",
        city="Pulheim",
        country_code="DE",
    )
    order = ParsedOrder(
        order_number="A9DESO011595",
        quantity_total=1,
        weight_kg=Decimal("35"),
        volume_m3=Decimal("0.499"),
        address=address,
        models=["16HRP162"],
    )
    return ParsedLadeliste(
        tour_number="1918622",
        version="Version2",
        carrier_name="Stylinart",
        tour_date=date(2026, 9, 15),
        loading_date=date(2026, 9, 25),
        orders=[order],
        unloading_point_count=1,
        warnings=[],
    )


def test_upload_ladeliste_pdf_creates_tour(client, db_session):
    _seed_admin(db_session)

    with patch(_PATCH_TARGET, return_value=_make_parsed()):
        response = client.post(
            "/api/imports",
            files={"file": ("ladeliste.pdf", b"%PDF-fake", "application/pdf")},
        )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["records_total"] == 1
    assert payload["records_successful"] == 1

    tour = db_session.execute(select(Tour)).scalars().one()
    assert tour.tour_number == "1918622"


def test_upload_unsupported_file_format_is_rejected(client, db_session):
    _seed_admin(db_session)

    response = client.post(
        "/api/imports",
        files={"file": ("ladeliste.txt", b"irrelevant", "text/plain")},
    )
    assert response.status_code == 422
