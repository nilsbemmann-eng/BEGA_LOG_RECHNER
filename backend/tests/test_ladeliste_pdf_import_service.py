from datetime import date
from decimal import Decimal
from unittest.mock import patch

from sqlalchemy import select

from app.models.import_job import ImportJobStatus
from app.models.party import Carrier
from app.models.shipment import Shipment
from app.models.tour import Tour
from app.services.ladeliste_pdf_import_service import import_ladeliste_pdf
from app.services.ladeliste_pdf_parser import LadelistePdfParsingError, ParsedAddress, ParsedLadeliste, ParsedOrder
from app.storage import LocalFileSystemStorage

_PATCH_TARGET = "app.services.ladeliste_pdf_import_service.parse_ladeliste_pdf"


def _make_parsed(tour_number: str = "1918622", carrier_name: str | None = "Stylinart") -> ParsedLadeliste:
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
        tour_number=tour_number,
        version="Version2",
        carrier_name=carrier_name,
        tour_date=date(2026, 9, 15),
        loading_date=date(2026, 9, 25),
        orders=[order],
        unloading_point_count=1,
        warnings=[],
    )


def _storage(tmp_path) -> LocalFileSystemStorage:
    return LocalFileSystemStorage(base_path=str(tmp_path / "storage"))


def test_import_creates_tour_and_shipments_and_warns_on_unknown_carrier(db_session, tmp_path):
    with patch(_PATCH_TARGET, return_value=_make_parsed()):
        job = import_ladeliste_pdf(db_session, b"%PDF-fake", "ladeliste.pdf", _storage(tmp_path), str(tmp_path / "reports"))
    db_session.commit()

    assert job.status == ImportJobStatus.COMPLETED_WITH_ERRORS
    assert job.records_total == 1
    assert job.records_successful == 1
    assert job.error_report_reference is not None  # Warnung ueber fehlenden Carrier protokolliert

    tour = db_session.execute(select(Tour)).scalars().one()
    assert tour.tour_number == "1918622"
    assert tour.carrier_id is None
    assert tour.source_document_id is not None

    shipment = db_session.execute(select(Shipment)).scalars().one()
    assert shipment.shipment_number == "A9DESO011595"
    assert shipment.tour_id == tour.id
    assert shipment.weight_kg == Decimal("35")
    assert shipment.volume_m3 == Decimal("0.499")
    assert shipment.destination_address.postal_code == "50259"
    assert shipment.destination_address.city == "Pulheim"


def test_import_matches_existing_carrier_case_insensitively(db_session, tmp_path):
    carrier = Carrier(name="stylinart", carrier_code="STY-1")
    db_session.add(carrier)
    db_session.flush()

    with patch(_PATCH_TARGET, return_value=_make_parsed(carrier_name="Stylinart")):
        job = import_ladeliste_pdf(db_session, b"%PDF-fake", "ladeliste.pdf", _storage(tmp_path), str(tmp_path / "reports"))
    db_session.commit()

    assert job.status == ImportJobStatus.COMPLETED
    assert job.error_report_reference is None

    tour = db_session.execute(select(Tour)).scalars().one()
    assert tour.carrier_id == carrier.id

    shipment = db_session.execute(select(Shipment)).scalars().one()
    assert shipment.carrier_id == carrier.id


def test_import_fails_when_tour_number_already_imported(db_session, tmp_path):
    with patch(_PATCH_TARGET, return_value=_make_parsed(tour_number="1918622")):
        import_ladeliste_pdf(db_session, b"%PDF-fake-1", "a.pdf", _storage(tmp_path), str(tmp_path / "reports"))
    db_session.commit()

    with patch(_PATCH_TARGET, return_value=_make_parsed(tour_number="1918622")):
        job = import_ladeliste_pdf(db_session, b"%PDF-fake-2", "b.pdf", _storage(tmp_path), str(tmp_path / "reports"))
    db_session.commit()

    assert job.status == ImportJobStatus.FAILED
    assert "bereits importiert" in job.error_report_reference

    tours = db_session.execute(select(Tour)).scalars().all()
    assert len(tours) == 1


def test_import_fails_on_identical_file_content(db_session, tmp_path):
    same_bytes = b"%PDF-identical-content"

    with patch(_PATCH_TARGET, return_value=_make_parsed(tour_number="1918622")):
        import_ladeliste_pdf(db_session, same_bytes, "a.pdf", _storage(tmp_path), str(tmp_path / "reports"))
    db_session.commit()

    with patch(_PATCH_TARGET, return_value=_make_parsed(tour_number="1918699")):
        job = import_ladeliste_pdf(db_session, same_bytes, "a-nochmal.pdf", _storage(tmp_path), str(tmp_path / "reports"))
    db_session.commit()

    assert job.status == ImportJobStatus.FAILED
    assert "bereits hochgeladen" in job.error_report_reference

    tours = db_session.execute(select(Tour)).scalars().all()
    assert len(tours) == 1


def test_import_fails_gracefully_on_parsing_error(db_session, tmp_path):
    with patch(_PATCH_TARGET, side_effect=LadelistePdfParsingError("kaputtes Layout")):
        job = import_ladeliste_pdf(db_session, b"not a real pdf", "broken.pdf", _storage(tmp_path), str(tmp_path / "reports"))
    db_session.commit()

    assert job.status == ImportJobStatus.FAILED
    assert "kaputtes Layout" in job.error_report_reference
    assert db_session.execute(select(Tour)).scalars().first() is None
