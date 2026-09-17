from datetime import date
from decimal import Decimal

import pytest

from app.services.ladeliste_pdf_parser import (
    LadelistePdfParsingError,
    _build_parsed_ladeliste,
    _parse_address_block,
    _parse_cbm,
    _parse_header,
    _parse_kg,
    _parse_kg_cbm_cell,
)

_HEADER = {
    "tour_number": "1918622",
    "version": "Version2",
    "carrier_name": "Stylinart",
    "tour_date": date(2026, 9, 15),
    "loading_date": date(2026, 9, 25),
}


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("35", Decimal("35")),
        ("35kg", Decimal("35")),
        ("3.504", Decimal("3504")),
        ("3.504kg", Decimal("3504")),
        # Realer Ausreisser (Komma statt Punkt) - siehe docs/OFFENE_ENTSCHEIDUNGEN.md
        ("3,893", Decimal("3893")),
    ],
)
def test_parse_kg(raw: str, expected: Decimal) -> None:
    assert _parse_kg(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("0.499", Decimal("0.499")),
        ("0.499m³", Decimal("0.499")),
        ("69.716", Decimal("69.716")),
        ("74.646m³", Decimal("74.646")),
    ],
)
def test_parse_cbm(raw: str, expected: Decimal) -> None:
    assert _parse_cbm(raw) == expected


def test_parse_kg_cbm_cell() -> None:
    weight, volume = _parse_kg_cbm_cell("35\n0.499")
    assert weight == Decimal("35")
    assert volume == Decimal("0.499")


def test_parse_kg_cbm_cell_raises_on_missing_line() -> None:
    with pytest.raises(LadelistePdfParsingError):
        _parse_kg_cbm_cell("35")


def test_parse_address_block_with_opening_hours() -> None:
    text = (
        "Mitnahmelager Beispielstadt Fil.-/Lager-Nr. 45\n"
        "Musterstr. 1\n"
        "D-50259 Pulheim\n"
        "Mo-Do 07:00-16:00+Fr 07:00-12:00"
    )
    address = _parse_address_block(text)
    assert address.street == "Musterstr. 1"
    assert address.postal_code == "50259"
    assert address.city == "Pulheim"
    assert address.country_code == "DE"


def test_parse_address_block_without_opening_hours() -> None:
    text = "Musterfirma GmbH\nDenekamper Str. 185\nD-48529 Nordhorn"
    address = _parse_address_block(text)
    assert address.street == "Denekamper Str. 185"
    assert address.postal_code == "48529"
    assert address.city == "Nordhorn"


def test_parse_address_block_raises_without_plz_city_line() -> None:
    with pytest.raises(LadelistePdfParsingError):
        _parse_address_block("Nur ein Name\nOhne PLZ-Zeile")


def test_parse_header_extracts_all_fields() -> None:
    text = (
        "LADELISTE\n"
        "Bei Rückfragen bitte unbedingt angeben\n"
        "Ladelistennummer 1918622 Seite 1/2\n"
        "Ladelistendatum 15.09.2026\n"
        "Spediteur Stylinart\n"
        "Ladedatum 25.09.2026\n"
        "Versionsnummer Version2\n"
        "Tourinfo"
    )
    header = _parse_header(text)
    assert header == _HEADER


def test_parse_header_raises_without_tour_number() -> None:
    with pytest.raises(LadelistePdfParsingError):
        _parse_header("Kein gueltiges Layout")


def test_build_parsed_ladeliste_groups_line_items_by_order_number() -> None:
    rows = [
        ["A1", "Konto", "1", "MODELL-A", "Bezeichnung A", "", "34\n0.439", "Musterfirma\nMusterstr. 1\nD-50259 Pulheim"],
        # Fortsetzungszeile desselben Auftrags - Entladestelle bleibt leer (forward-fill)
        ["A1", "Konto", "2", "MODELL-A2", "Bezeichnung A2", "", "68\n0.878", ""],
    ]
    result = _build_parsed_ladeliste(_HEADER, rows)

    assert len(result.orders) == 1
    order = result.orders[0]
    assert order.order_number == "A1"
    assert order.quantity_total == 3
    assert order.weight_kg == Decimal("102")
    assert order.volume_m3 == Decimal("1.317")
    assert order.address is not None
    assert order.address.postal_code == "50259"
    assert result.unloading_point_count == 1
    assert result.warnings == []


def test_build_parsed_ladeliste_dedups_by_postal_code_and_city_despite_different_name_lines() -> None:
    """Nutzerbestaetigung: unterschiedliche Name1/Name2-Zeilen derselben
    Kundenadresse sind KEINE getrennten Entladestellen (siehe
    docs/OFFENE_ENTSCHEIDUNGEN.md)."""
    rows = [
        ["A1", "Konto", "1", "M1", "B1", "", "35\n0.499", "Mitnahmelager Beispielstadt\nMusterstr. 1\nD-50259 Pulheim"],
        ["A2", "Konto", "1", "M2", "B2", "", "34\n0.439", "Ganz anderer Firmenname GmbH\nMusterstr. 1\nD-50259 Pulheim"],
    ]
    result = _build_parsed_ladeliste(_HEADER, rows)

    assert len(result.orders) == 2
    assert result.unloading_point_count == 1


def test_build_parsed_ladeliste_counts_distinct_unloading_points() -> None:
    rows = [
        ["A1", "Konto", "1", "M1", "B1", "", "35\n0.499", "Firma A\nStr. 1\nD-50259 Pulheim"],
        ["A2", "Konto", "1", "M2", "B2", "", "34\n0.439", "Firma B\nStr. 2\nD-24568 Kaltenkirchen"],
    ]
    result = _build_parsed_ladeliste(_HEADER, rows)
    assert result.unloading_point_count == 2


def test_build_parsed_ladeliste_skips_summe_rows() -> None:
    rows = [
        ["A1", "Konto", "1", "M1", "B1", "", "35\n0.499", "Firma A\nStr. 1\nD-50259 Pulheim"],
        ["", "", "", "", "", "SUMME\nEntladestelle", "35kg\n0.499m³", ""],
        ["", "", "", "", "", "SUMME Tour\nEntladestelle", "35kg\n0.499m³", ""],
    ]
    result = _build_parsed_ladeliste(_HEADER, rows)
    assert len(result.orders) == 1


def test_build_parsed_ladeliste_warns_on_unparseable_address_but_keeps_order() -> None:
    rows = [
        ["A1", "Konto", "1", "M1", "B1", "", "35\n0.499", "Nur ein Name\nOhne PLZ-Zeile"],
    ]
    result = _build_parsed_ladeliste(_HEADER, rows)
    assert len(result.orders) == 1
    assert result.orders[0].address is not None
    assert result.orders[0].address.postal_code is None
    assert result.unloading_point_count == 0
    assert len(result.warnings) == 2  # Adress-Parsing + "keine Entladestelle gefunden"
