"""Import der "Gebietsrelationen"-Stammdatentabelle (BEGA-Finetuning,
Nutzervorgabe) in die Absender-Matrix (`TourOriginMapping`).

Erwartete Spalten (siehe reale Vorlage "Gebietsrelationen.xlsx"):
Matchcode | Bezeichnung | Praefix | Absender | Absenderadresse

`Absenderadresse` hat das Format "<Laendercode> <PLZ> <Ort> <Strasse>", z. B.
"PL 39-300 Mielec ul. Wojska Polskiego 3" oder "D 21129 Hamburg Am Ballinkai 1".
Diese Tabelle ist die vollstaendige, aktuelle Referenz (kein inkrementelles
Update) - ein Import ersetzt daher den gesamten bisherigen Inhalt der
Absender-Matrix, analog zu einem periodischen Stammdatenabgleich.
"""
from __future__ import annotations

import io
import re

from openpyxl import load_workbook
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.models.address import Address
from app.models.tour_origin_mapping import TourOriginMapping

_EXPECTED_HEADER = ["Matchcode", "Bezeichnung", "Präfix", "Absender", "Absenderadresse"]
_ADDRESS_RE = re.compile(r"^([A-Z]{1,2})\s+(\S+)\s+(\S+)\s*(.*)$")
_COUNTRY_PREFIX_MAP = {"D": "DE"}


class TourOriginMatrixParsingError(ValueError):
    """Wird geworfen, wenn die Excel-Struktur nicht der erwarteten Vorlage entspricht."""


def _parse_absenderadresse(raw: str) -> Address:
    match = _ADDRESS_RE.match(raw.strip())
    if not match:
        raise TourOriginMatrixParsingError(f"Absenderadresse konnte nicht geparst werden: {raw!r}")
    country_prefix, postal_code, city, street = match.groups()
    return Address(
        original_text=raw,
        street=street or None,
        postal_code=postal_code,
        city=city,
        country_code=_COUNTRY_PREFIX_MAP.get(country_prefix.upper(), country_prefix.upper()),
    )


def import_tour_origin_matrix(db: Session, file_bytes: bytes) -> int:
    workbook = load_workbook(io.BytesIO(file_bytes), read_only=True, data_only=True)
    sheet = workbook.active
    rows = [list(row) for row in sheet.iter_rows(values_only=True)]
    if not rows:
        raise TourOriginMatrixParsingError("Datei enthaelt keine Zeilen")

    header = [str(cell).strip() if cell is not None else "" for cell in rows[0]]
    if header[: len(_EXPECTED_HEADER)] != _EXPECTED_HEADER:
        raise TourOriginMatrixParsingError(
            f"Unerwartete Spaltenkopfzeile {header} - erwartet: {_EXPECTED_HEADER}"
        )

    db.execute(delete(TourOriginMapping))

    imported = 0
    for row in rows[1:]:
        if not row or row[0] is None:
            continue
        matchcode, description, prefix, _absender, absenderadresse = (list(row) + [None] * 5)[:5]

        origin_address = _parse_absenderadresse(str(absenderadresse)) if absenderadresse else None
        db.add(
            TourOriginMapping(
                tour_number_prefix=str(prefix).strip(),
                matchcode=str(matchcode).strip(),
                description=str(description).strip() if description else None,
                origin_address=origin_address,
            )
        )
        imported += 1

    db.flush()
    return imported
