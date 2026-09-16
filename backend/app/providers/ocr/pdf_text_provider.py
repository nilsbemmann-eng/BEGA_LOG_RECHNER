"""`DocumentOcrProvider` fuer PDFs mit eingebetteter Textebene.

Nutzt `pdfplumber`, um Text und Tabellen direkt aus dem PDF zu extrahieren
(kein Bild-OCR). Deckt damit den haeufigsten MVP-Fall ab: digital erzeugte
Frachtrechnungen/Ladelisten als PDF. Fuer gescannte, reine Bilddokumente
(JPG/PNG/TIFF oder eingescannte PDFs ohne Textebene) liefert dieser Provider
keine Felder - dafuer ist eine Bild-OCR-Engine (Tesseract, Azure Document
Intelligence, AWS Textract, Google Document AI) als zusaetzlicher, austauschbarer
`DocumentOcrProvider` zu ergaenzen (siehe docs/OFFENE_ENTSCHEIDUNGEN.md, Punkt 3).

Die Felderkennung ist regelbasiert (Label + Regex), damit jedes Ergebnis fuer
den Pruefer nachvollziehbar bleibt (Ursprungstext wird immer mitgespeichert).
"""
from __future__ import annotations

import io
import re
from dataclasses import dataclass

import pdfplumber

from app.normalization.numbers import NumberParsingError, parse_german_decimal
from app.providers.base import DocumentInput, DocumentOcrProvider, ExtractedFieldResult, OcrPageResult, OcrResult

_LABEL_CONFIDENCE = 0.92


@dataclass
class _FieldPattern:
    field_name: str
    data_type: str
    pattern: re.Pattern[str]
    parse_numeric: bool = False


_FIELD_PATTERNS: list[_FieldPattern] = [
    _FieldPattern(
        "invoice_number", "string",
        re.compile(r"Rechnungs(?:-|\s)?(?:nummer|nr\.?)\s*[:#]?\s*([A-Za-z0-9/\-]+)", re.IGNORECASE),
    ),
    _FieldPattern(
        "shipment_number", "string",
        re.compile(
            r"(?:Sendungs(?:-|\s)?(?:nummer|nr\.?)|Auftrags(?:-|\s)?(?:nummer|nr\.?)|Tour(?:-|\s)?(?:nummer|nr\.?))"
            r"\s*[:#]?\s*([A-Za-z0-9/\-]+)",
            re.IGNORECASE,
        ),
    ),
    _FieldPattern(
        "invoice_date", "date",
        re.compile(r"Rechnungsdatum\s*[:#]?\s*(\d{1,2}\.\d{1,2}\.\d{2,4})", re.IGNORECASE),
    ),
    _FieldPattern(
        "invoice_amount", "decimal",
        re.compile(
            r"(?:Rechnungsbetrag|Gesamtbetrag|Endbetrag)\s*[:#]?\s*([\d.,]+)\s*(?:EUR|€)?",
            re.IGNORECASE,
        ),
        parse_numeric=True,
    ),
    _FieldPattern(
        "weight_kg", "decimal",
        re.compile(r"(?:Bruttogewicht|Gewicht)\s*[:#]?\s*([\d.,]+)\s*kg", re.IGNORECASE),
        parse_numeric=True,
    ),
    _FieldPattern(
        "loading_meters", "decimal",
        re.compile(r"(?:Lademeter|LDM)\s*[:#]?\s*([\d.,]+)", re.IGNORECASE),
        parse_numeric=True,
    ),
]


class PdfTextOcrProvider(DocumentOcrProvider):
    def analyze(self, document: DocumentInput) -> OcrResult:
        pages: list[OcrPageResult] = []
        fields: list[ExtractedFieldResult] = []

        with pdfplumber.open(io.BytesIO(document.file_bytes)) as pdf:
            for page_number, page in enumerate(pdf.pages, start=1):
                text = page.extract_text() or ""
                tables = page.extract_tables() or []
                pages.append(OcrPageResult(page_number=page_number, extracted_text=text, raw={"tables": tables}))
                fields.extend(self._extract_fields_from_text(text, page_number))

        return OcrResult(pages=pages, fields=fields)

    @staticmethod
    def _extract_fields_from_text(text: str, page_number: int) -> list[ExtractedFieldResult]:
        found: list[ExtractedFieldResult] = []
        for spec in _FIELD_PATTERNS:
            match = spec.pattern.search(text)
            if not match:
                continue
            original_value = match.group(1)
            normalized_value: str | None = original_value
            if spec.parse_numeric:
                try:
                    normalized_value = str(parse_german_decimal(original_value))
                except NumberParsingError:
                    normalized_value = None
            found.append(
                ExtractedFieldResult(
                    field_name=spec.field_name,
                    original_value=original_value,
                    normalized_value=normalized_value,
                    data_type=spec.data_type,
                    confidence=_LABEL_CONFIDENCE,
                    source_page=page_number,
                    source_text=match.group(0),
                    extraction_method="pdf_text_regex",
                )
            )
        return found
