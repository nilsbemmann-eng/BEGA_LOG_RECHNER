import io

import pytest
from openpyxl import Workbook
from sqlalchemy import select

from app.models.tour_origin_mapping import TourOriginMapping
from app.services.tour_origin_import_service import TourOriginMatrixParsingError, import_tour_origin_matrix
from app.services.tour_origin_service import resolve_tour_origin_address

_HEADER = ["Matchcode", "Bezeichnung", "Präfix", "Absender", "Absenderadresse"]


def _workbook_bytes(rows: list[tuple]) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(_HEADER)
    for row in rows:
        sheet.append(row)
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def test_import_parses_real_column_structure(db_session):
    content = _workbook_bytes([
        ("MP", "Meble Polskie", 19, "Meble Polskie Janusz Fijalek", "PL 22-400 Zamosc ul. Strefowa 10"),
        ("SHUTTLEI", "Shuttle Ilawa Inbound", 11, None, None),
    ])

    imported = import_tour_origin_matrix(db_session, content)
    db_session.commit()

    assert imported == 2
    mappings = db_session.execute(select(TourOriginMapping)).scalars().all()
    assert len(mappings) == 2

    mp = next(m for m in mappings if m.matchcode == "MP")
    assert mp.tour_number_prefix == "19"
    assert mp.origin_address.country_code == "PL"
    assert mp.origin_address.postal_code == "22-400"
    assert mp.origin_address.city == "Zamosc"
    assert mp.origin_address.street == "ul. Strefowa 10"

    no_address = next(m for m in mappings if m.matchcode == "SHUTTLEI")
    assert no_address.origin_address is None


def test_import_maps_german_country_prefix_to_iso_code(db_session):
    content = _workbook_bytes([
        ("CTN", "Container ab Importhafen", 15, "Container Terminal", "D 21129 Hamburg Am Ballinkai 1"),
    ])
    import_tour_origin_matrix(db_session, content)
    db_session.commit()

    mapping = db_session.execute(select(TourOriginMapping)).scalars().one()
    assert mapping.origin_address.country_code == "DE"
    assert mapping.origin_address.city == "Hamburg"


def test_import_replaces_current_matrix_but_keeps_history(db_session):
    """Ein erneuter Import ersetzt die AKTUELLE Absender-Matrix, loescht aber
    keine Zeilen physisch (Versionierung, siehe app/models/tour_origin_mapping.py) -
    die alte Zuordnung bleibt mit is_current=False fuer vergangene Tour-Audits
    nachvollziehbar erhalten."""
    import_tour_origin_matrix(db_session, _workbook_bytes([("OLD", "Alt", 1, "X", "PL 00-000 Alt Altstr. 1")]))
    db_session.commit()

    import_tour_origin_matrix(db_session, _workbook_bytes([("NEW", "Neu", 2, "Y", "PL 00-001 Neu Neustr. 2")]))
    db_session.commit()

    current = db_session.execute(select(TourOriginMapping).where(TourOriginMapping.is_current.is_(True))).scalars().all()
    assert len(current) == 1
    assert current[0].matchcode == "NEW"

    all_mappings = db_session.execute(select(TourOriginMapping)).scalars().all()
    assert len(all_mappings) == 2
    old = next(m for m in all_mappings if m.matchcode == "OLD")
    assert old.is_current is False


def test_import_raises_on_unexpected_header(db_session):
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["Falsche", "Spalten"])
    buffer = io.BytesIO()
    workbook.save(buffer)

    with pytest.raises(TourOriginMatrixParsingError):
        import_tour_origin_matrix(db_session, buffer.getvalue())


def test_resolve_is_unambiguous_when_single_row_for_prefix(db_session):
    content = _workbook_bytes([
        ("MP", "Meble Polskie", 19, "x", "PL 22-400 Zamosc ul. Strefowa 10"),
    ])
    import_tour_origin_matrix(db_session, content)
    db_session.commit()

    resolution = resolve_tour_origin_address(db_session, "1918622")
    assert resolution.address is not None
    assert resolution.address.city == "Zamosc"
    assert resolution.ambiguous_matchcodes == []


def test_resolve_is_ambiguous_when_prefix_has_conflicting_addresses(db_session):
    """Realer Fall (Praefix 12 in Gebietsrelationen.xlsx): mehrere Matchcodes
    mit unterschiedlichen Adressen unter demselben Praefix."""
    content = _workbook_bytes([
        ("SHUTTLESER", "Shuttle Dabrowka (UA)", 12, "x", "UA 80200 Radekhiv Vytkivska street 44"),
        ("OTTO D", "OTTO NORD SUED", 12, "y", "PL 39-300 Mielec ul. Wojska Polskiego 3"),
    ])
    import_tour_origin_matrix(db_session, content)
    db_session.commit()

    resolution = resolve_tour_origin_address(db_session, "1218622")
    assert resolution.address is None
    assert set(resolution.ambiguous_matchcodes) == {"SHUTTLESER", "OTTO D"}


def test_resolve_ignores_duplicate_matchcodes_with_identical_address(db_session):
    """Mehrere Matchcodes unter demselben Praefix mit IDENTISCHER Adresse sind
    nicht mehrdeutig (realer Fall Praefix 30: mehrere Otto-Mosina-Varianten,
    alle im selben BEGA-Lager)."""
    content = _workbook_bytes([
        ("OTTOMO", "Otto Mosina", 30, "x", "PL 62-070 Dabrowka ul. Logistyczna 7"),
        ("OTTOMOBBK", "Otto Mosina BBK", 30, "x", "PL 62-070 Dabrowka ul. Logistyczna 7"),
    ])
    import_tour_origin_matrix(db_session, content)
    db_session.commit()

    resolution = resolve_tour_origin_address(db_session, "3018622")
    assert resolution.address is not None
    assert resolution.ambiguous_matchcodes == []
