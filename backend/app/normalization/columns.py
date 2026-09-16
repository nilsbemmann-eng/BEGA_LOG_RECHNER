"""Konfigurierbare Spaltenerkennung fuer Ladelisten (Abschnitt 4.5).

Unbekannte Spalten werden nicht verworfen, sondern als nicht zugeordnete
Importfelder zurueckgegeben (`unmapped_columns` in `MappingResult`), damit sie
im Importprotokoll erhalten bleiben (Akzeptanzkriterium 16.2).
"""
from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field

# Tabelle aus Abschnitt 4.5. Werte sind Teilstrings (kleingeschrieben, ohne
# Umlaute), gegen die normalisierte Spaltennamen geprueft werden.
COLUMN_SYNONYMS: dict[str, list[str]] = {
    "shipment_number": ["sendung", "auftrag", "tour", "referenz"],
    "origin_address": ["absender", "beladestelle", "pickup", "abholadresse"],
    # Muss vor "destination_address" geprueft werden: "entladestelle" (Adresse)
    # ist als Teilstring auch in "Anzahl Entladestellen" (Zaehlfeld) enthalten.
    "unloading_point_count": ["anzahl entladestellen", "anzahl der entladestellen", "entladestellenanzahl", "anzahl stopps"],
    "destination_address": ["empfaenger", "entladestelle", "delivery", "zustelladresse"],
    "weight_kg": ["gewicht", "brutto", "kg"],
    "pallets": ["paletten", "packstuecke", "colli", "kolli"],
    "loading_meters": ["ldm", "lademeter"],
    "volume_m3": ["volumen", "cbm", "m3", "m³"],
    "freight_amount": ["fracht", "transportpreis", "netto"],
    "surcharge_amount": ["zusatz", "nebenleistung", "zuschlag"],
}


def _normalize(text: str) -> str:
    text = text.strip().lower()
    text = text.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    return text


@dataclass
class MappingResult:
    column_to_field: dict[str, str] = field(default_factory=dict)  # Quellspalte -> Zielfeld
    field_to_column: dict[str, str] = field(default_factory=dict)  # Zielfeld -> Quellspalte
    unmapped_columns: list[str] = field(default_factory=list)


def map_columns(header_row: list[str], synonyms: dict[str, list[str]] | None = None) -> MappingResult:
    """Bildet eine Kopfzeile auf das einheitliche Ladeliste-Datenmodell ab.

    Bei mehreren Spalten, die auf dasselbe Zielfeld passen, gewinnt die erste
    Spalte (Reihenfolge der Kopfzeile); alle weiteren bleiben unzugeordnet.
    """
    synonyms = synonyms or COLUMN_SYNONYMS
    result = MappingResult()

    for raw_column in header_row:
        normalized_column = _normalize(raw_column)
        matched_field: str | None = None
        for target_field, keywords in synonyms.items():
            if target_field in result.field_to_column:
                continue  # Zielfeld bereits belegt
            if any(_normalize(keyword) in normalized_column for keyword in keywords):
                matched_field = target_field
                break

        if matched_field:
            result.column_to_field[raw_column] = matched_field
            result.field_to_column[matched_field] = raw_column
        else:
            result.unmapped_columns.append(raw_column)

    return result
