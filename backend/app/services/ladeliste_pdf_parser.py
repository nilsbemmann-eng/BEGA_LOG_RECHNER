"""Parser fuer Ladelisten-PDFs (BEGA-Finetuning, reale Stylinart-Belege).

Eine Ladeliste listet die Auftraege (Sendungen) einer ganzen Tour auf, jeweils
mit Menge/Gewicht/Volumen und der Entladestelle (Zieladresse). Mehrere
Tabellenzeilen koennen zu ein und demselben Auftrag gehoeren (mehrere
Positionen), und mehrere Auftraege koennen dieselbe physische Entladestelle
teilen - erkennbar an gleicher PLZ/Ort, auch wenn der Adresstext (Name1/Name2
der Kundenadresse) variiert (Nutzerbestaetigung, siehe
docs/OFFENE_ENTSCHEIDUNGEN.md). Die Zaehlung "Anzahl Entladestellen" fuer die
Tour-Preispruefung basiert daher auf eindeutigen (PLZ, Ort)-Paaren.

Zahlenformat-Besonderheit dieser PDFs (weicht von der sonstigen deutschen
Konvention in `app/normalization/numbers.py` ab, siehe
docs/OFFENE_ENTSCHEIDUNGEN.md): in der Spalte "kg / cbm" ist die kg-Zeile
immer eine Ganzzahl mit Punkt als Tausendertrennzeichen, die cbm-Zeile immer
ein Dezimalwert mit Punkt als Dezimaltrennzeichen (fix 3 Nachkommastellen).
"""
from __future__ import annotations

import io
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

import pdfplumber

_HEADER_ROW = [
    "Auftrags-Nr.",
    "Konto",
    "Menge",
    "Modell",
    "Bezeichnung",
    "Value Added Services",
    "kg\ncbm",
    "Entladestelle",
]
_EXPECTED_COLUMNS = len(_HEADER_ROW)

# Laenderpraefix + PLZ + Ort, z. B. "D-50259 Pulheim".
_PLZ_CITY_RE = re.compile(r"^([A-Z]{1,3})-(\d{4,6})\s+(.+)$")
_COUNTRY_PREFIX_MAP = {"D": "DE"}


class LadelistePdfParsingError(ValueError):
    """Wird geworfen, wenn die PDF-Struktur nicht der erwarteten Ladeliste entspricht."""


@dataclass
class ParsedAddress:
    original_text: str
    street: str | None
    postal_code: str | None
    city: str | None
    country_code: str | None


@dataclass
class ParsedOrder:
    """Ein Auftrag (Auftrags-Nr.) der Ladeliste, ueber alle seine Positionen aufsummiert."""

    order_number: str
    quantity_total: int = 0
    weight_kg: Decimal = field(default_factory=lambda: Decimal("0"))
    volume_m3: Decimal = field(default_factory=lambda: Decimal("0"))
    address: ParsedAddress | None = None
    models: list[str] = field(default_factory=list)


@dataclass
class ParsedLadeliste:
    tour_number: str
    version: str | None
    carrier_name: str | None
    tour_date: date | None
    loading_date: date | None
    orders: list[ParsedOrder]
    unloading_point_count: int
    warnings: list[str] = field(default_factory=list)


def parse_ladeliste_pdf(pdf_bytes: bytes) -> ParsedLadeliste:
    header, data_rows = _extract_header_and_rows(pdf_bytes)
    return _build_parsed_ladeliste(header, data_rows)


def _extract_header_and_rows(pdf_bytes: bytes) -> tuple[dict, list[list[str]]]:
    """Reine PDF-Extraktion (pdfplumber) - getrennt von der Geschaeftslogik in
    `_build_parsed_ladeliste`, damit Letztere mit synthetischen Tabellenzeilen
    getestet werden kann, ohne echte PDF-Bytes erzeugen zu muessen."""
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        if not pdf.pages:
            raise LadelistePdfParsingError("PDF enthaelt keine Seiten")

        header = _parse_header(pdf.pages[0].extract_text() or "")

        data_rows: list[list[str]] = []
        for page in pdf.pages:
            for table in page.extract_tables():
                if not table or len(table[0]) != _EXPECTED_COLUMNS:
                    continue  # Kopf-/Infoblock (1 Spalte), keine Auftragstabelle
                first_row = [(cell or "").strip() for cell in table[0]]
                data_rows.extend(table[1:] if first_row == _HEADER_ROW else table)

    if not data_rows:
        raise LadelistePdfParsingError(
            "Keine Auftragstabelle in der Ladeliste gefunden - unerwartetes PDF-Layout?"
        )
    return header, data_rows


def _build_parsed_ladeliste(header: dict, data_rows: list[list[str]]) -> ParsedLadeliste:
    warnings: list[str] = []
    orders: dict[str, ParsedOrder] = {}
    current_address: ParsedAddress | None = None

    for row in data_rows:
        cells = [(cell or "").strip() for cell in row] + [""] * _EXPECTED_COLUMNS
        order_number, _konto, menge, modell, _bezeichnung, value_added_services, kg_cbm, entladestelle = cells[
            :_EXPECTED_COLUMNS
        ]

        if value_added_services.upper().startswith("SUMME"):
            continue  # Zwischen-/Tour-Summe, keine eigene Auftragszeile

        if not order_number:
            continue  # defensiv: unerwartete Leerzeile

        if entladestelle:
            try:
                current_address = _parse_address_block(entladestelle)
            except LadelistePdfParsingError as exc:
                warnings.append(f"Auftrag {order_number}: {exc}")
                current_address = ParsedAddress(entladestelle, None, None, None, None)

        try:
            weight_kg, volume_m3 = _parse_kg_cbm_cell(kg_cbm)
        except (LadelistePdfParsingError, InvalidOperation) as exc:
            warnings.append(f"Auftrag {order_number}: kg/cbm konnte nicht gelesen werden ({exc})")
            weight_kg, volume_m3 = Decimal("0"), Decimal("0")

        try:
            quantity = int(menge) if menge else 0
        except ValueError:
            quantity = 0

        order = orders.get(order_number)
        if order is None:
            order = ParsedOrder(order_number=order_number, address=current_address)
            orders[order_number] = order

        order.quantity_total += quantity
        order.weight_kg += weight_kg
        order.volume_m3 += volume_m3
        if modell:
            order.models.append(modell)

    unloading_keys = {
        (order.address.postal_code, order.address.city)
        for order in orders.values()
        if order.address and order.address.postal_code and order.address.city
    }
    if not unloading_keys:
        warnings.append("Keine Entladestelle mit erkennbarer PLZ/Ort in der gesamten Ladeliste gefunden")

    return ParsedLadeliste(
        tour_number=header["tour_number"],
        version=header["version"],
        carrier_name=header["carrier_name"],
        tour_date=header["tour_date"],
        loading_date=header["loading_date"],
        orders=list(orders.values()),
        unloading_point_count=len(unloading_keys),
        warnings=warnings,
    )


def _parse_header(page_text: str) -> dict:
    def find(pattern: str) -> str | None:
        match = re.search(pattern, page_text)
        return match.group(1).strip() if match else None

    tour_number = find(r"Ladelistennummer\s+(\S+)")
    if not tour_number:
        raise LadelistePdfParsingError(
            "Ladelistennummer nicht gefunden - kein gueltiges Ladelisten-PDF?"
        )

    return {
        "tour_number": tour_number,
        "version": find(r"Versionsnummer\s+(\S+)"),
        "carrier_name": find(r"Spediteur\s+(.+)"),
        "tour_date": _parse_date(find(r"Ladelistendatum\s+(\d{2}\.\d{2}\.\d{4})")),
        "loading_date": _parse_date(find(r"Ladedatum\s+(\d{2}\.\d{2}\.\d{4})")),
    }


def _parse_date(raw: str | None) -> date | None:
    if not raw:
        return None
    return datetime.strptime(raw, "%d.%m.%Y").date()


def _parse_address_block(text: str) -> ParsedAddress:
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    plz_idx = next((i for i, line in enumerate(lines) if _PLZ_CITY_RE.match(line)), None)

    if plz_idx is None or plz_idx == 0:
        raise LadelistePdfParsingError(f"Keine PLZ/Ort-Zeile in Entladestelle-Block gefunden: {text!r}")

    match = _PLZ_CITY_RE.match(lines[plz_idx])
    country_prefix, postal_code, city = match.group(1), match.group(2), match.group(3).strip()

    return ParsedAddress(
        original_text=text,
        street=lines[plz_idx - 1],
        postal_code=postal_code,
        city=city,
        country_code=_COUNTRY_PREFIX_MAP.get(country_prefix.upper(), country_prefix.upper()),
    )


def _parse_kg_cbm_cell(raw: str) -> tuple[Decimal, Decimal]:
    lines = [line.strip() for line in raw.split("\n") if line.strip()]
    if len(lines) < 2:
        raise LadelistePdfParsingError(f"kg/cbm-Zelle hat nicht das erwartete 2-Zeilen-Format: {raw!r}")
    return _parse_kg(lines[0]), _parse_cbm(lines[1])


def _parse_kg(raw: str) -> Decimal:
    """kg ist immer eine Ganzzahl; Punkt UND (bei einem realen Ausreisser
    beobachtet) Komma werden gleichwertig als Tausendertrennzeichen behandelt
    (siehe docs/OFFENE_ENTSCHEIDUNGEN.md)."""
    cleaned = raw.rstrip("kg").strip().replace(".", "").replace(",", "")
    return Decimal(cleaned)


def _parse_cbm(raw: str) -> Decimal:
    """cbm ist immer ein Dezimalwert mit Punkt als Dezimaltrennzeichen (fix 3
    Nachkommastellen); zusaetzliche Punkte vor dem letzten waeren
    Tausendertrennzeichen (in der Praxis bislang nicht beobachtet, cbm-Werte
    bleiben pro Tour deutlich unter 1000)."""
    cleaned = raw.rstrip("m³").strip().replace(",", ".")
    if cleaned.count(".") > 1:
        head, _, tail = cleaned.rpartition(".")
        cleaned = head.replace(".", "") + "." + tail
    return Decimal(cleaned)
