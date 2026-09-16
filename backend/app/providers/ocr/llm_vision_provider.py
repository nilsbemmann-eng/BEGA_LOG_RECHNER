"""Vision-LLM-basierter OCR-Provider fuer gescannte Dokumente (Abschnitt 4.4,
Abschnitt 19: KI fuer OCR-Unterstuetzung und verstaendliche Begruendungen).

`PdfTextOcrProvider` funktioniert nur bei PDFs mit eingebetteter Textebene.
Fuer echte Scans, Fotos und PDF-Scans ohne Textebene nutzt dieser Provider ein
multimodales Claude-Modell (Anthropic API): jede Seite wird als Bild an das
Modell gegeben, das strukturiert antwortet (Tool-Aufruf statt Freitext, damit
das Ergebnis zuverlaessig parsbar ist).

Wichtig fuer die Nachvollziehbarkeit (Abschnitt 13, 19): das Modell liefert
nur den erkannten Rohwert (`original_value`) sowie eine kurze Begruendung.
Die eigentliche Zahlennormalisierung bleibt deterministisch und
wiederverwendet denselben Parser wie `pdf_text_provider.py`
(`app/normalization/numbers.py`) - das Modell rechnet nicht selbst, es liest
nur ab.

Erster Schritt Richtung Unterschriftenerkennung (siehe
docs/OFFENE_ENTSCHEIDUNGEN.md): pro Seite wird zusaetzlich erfasst, ob eine
handschriftliche Unterschrift sichtbar ist. Das ist reine Anwesenheits-
erkennung, keine Unterschriftsverifikation gegen eine Referenzunterschrift.
"""
from __future__ import annotations

import base64
import io
from dataclasses import dataclass
from typing import Any

import anthropic
from PIL import Image

from app.normalization.numbers import NumberParsingError, parse_german_decimal
from app.providers.base import DocumentInput, DocumentOcrProvider, ExtractedFieldResult, OcrPageResult, OcrResult

# Ehrlich eingeschaetzte Konfidenzstufen des Modells, abgebildet auf die
# gleichen Schwellenwerte wie bei anderen Providern (Abschnitt 8.2,
# app/config.py: ocr_min_auto_confidence=0.95, ocr_min_flagged_confidence=0.80).
_CONFIDENCE_BY_LEVEL = {
    "high": 0.97,
    "medium": 0.87,
    "low": 0.60,
}
_DEFAULT_CONFIDENCE = 0.60

_TOOL_NAME = "record_document_fields"

_SYSTEM_PROMPT = (
    "Du analysierst eine Seite eines Speditionsdokuments (Frachtrechnung, Ladeliste, "
    "Transportauftrag, Ablieferbeleg, Mautnachweis o.ae.), das als Scan oder Foto vorliegt. "
    "Transkribiere den sichtbaren Text vollstaendig und erkenne relevante Einzelfelder.\n\n"
    "Bevorzuge, wo zutreffend, diese Feldnamen: shipment_number, transport_order_number, "
    "invoice_number, invoice_date, invoice_amount, weight_kg, loading_meters, pallets, "
    "origin_address, destination_address, carrier_name. Fuer andere erkennbare Werte "
    "verwende einen kurzen, sprechenden snake_case-Namen.\n\n"
    "Gib bei Zahlen und Daten immer den Originaltext genau wie im Dokument sichtbar an "
    "(z. B. '1.234,56 EUR', '12,5 LDM', '12.06.2026') - normalisiere oder rechne NICHT selbst, "
    "das uebernimmt eine nachgelagerte, deterministische Pruefung.\n\n"
    "Bewerte pro Feld deine eigene Erkennungssicherheit ehrlich als high/medium/low "
    "(low z. B. bei unleserlicher Handschrift oder schlechtem Scan) und begruende in ein "
    "bis zwei Saetzen, woran bzw. wo im Dokument du den Wert erkannt hast.\n\n"
    "Pruefe ausserdem, ob auf der Seite eine handschriftliche Unterschrift sichtbar ist "
    "(nur Anwesenheit, keine Identitaetspruefung)."
)

_TOOL_SCHEMA: dict[str, Any] = {
    "name": _TOOL_NAME,
    "description": "Erfasst den transkribierten Text sowie alle erkannten Einzelfelder einer Dokumentseite.",
    "input_schema": {
        "type": "object",
        "properties": {
            "full_text": {"type": "string", "description": "Vollstaendiger sichtbarer Text der Seite."},
            "signature_present": {
                "type": "boolean",
                "description": "True, wenn eine handschriftliche Unterschrift auf der Seite sichtbar ist.",
            },
            "fields": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "field_name": {"type": "string"},
                        "original_value": {"type": "string"},
                        "data_type": {"type": "string", "enum": ["string", "decimal", "date", "integer"]},
                        "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                        "reasoning": {"type": "string"},
                    },
                    "required": ["field_name", "original_value", "data_type", "confidence", "reasoning"],
                },
            },
        },
        "required": ["full_text", "fields", "signature_present"],
    },
}

_NATIVE_IMAGE_MEDIA_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}


class VisionOcrError(RuntimeError):
    """Die Anthropic-API konnte nicht erfolgreich abgefragt werden (Abschnitt 14)."""


@dataclass
class _PageImage:
    media_type: str
    base64_data: str


class LlmVisionOcrProvider(DocumentOcrProvider):
    def __init__(self, api_key: str, model: str, max_pages: int = 5) -> None:
        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model
        self._max_pages = max_pages

    def analyze(self, document: DocumentInput) -> OcrResult:
        page_images = self._render_pages(document)
        pages: list[OcrPageResult] = []
        fields: list[ExtractedFieldResult] = []

        for page_number, page_image in enumerate(page_images[: self._max_pages], start=1):
            extraction = self._extract_page(page_image)
            pages.append(
                OcrPageResult(page_number=page_number, extracted_text=extraction.get("full_text", ""), raw=extraction)
            )
            for field in extraction.get("fields", []):
                fields.append(self._to_extracted_field(field, page_number))
            fields.append(self._signature_field(extraction, page_number))

        return OcrResult(pages=pages, fields=fields)

    def _to_extracted_field(self, field: dict, page_number: int) -> ExtractedFieldResult:
        confidence = _CONFIDENCE_BY_LEVEL.get(field.get("confidence", ""), _DEFAULT_CONFIDENCE)
        data_type = field.get("data_type", "string")
        original_value = field.get("original_value", "")
        normalized_value: str | None = original_value

        if data_type == "decimal":
            try:
                normalized_value = str(parse_german_decimal(original_value))
            except NumberParsingError:
                normalized_value = None
                confidence = min(confidence, _CONFIDENCE_BY_LEVEL["low"])

        return ExtractedFieldResult(
            field_name=field.get("field_name", "unknown"),
            original_value=original_value,
            normalized_value=normalized_value,
            data_type=data_type,
            confidence=confidence,
            source_page=page_number,
            source_text=field.get("reasoning"),
            extraction_method="claude_vision",
        )

    @staticmethod
    def _signature_field(extraction: dict, page_number: int) -> ExtractedFieldResult:
        signature_present = bool(extraction.get("signature_present", False))
        return ExtractedFieldResult(
            field_name="signature_present",
            original_value=str(signature_present),
            normalized_value=str(signature_present),
            data_type="boolean",
            confidence=_CONFIDENCE_BY_LEVEL["high"],
            source_page=page_number,
            source_text=None,
            extraction_method="claude_vision",
        )

    def _extract_page(self, page_image: _PageImage) -> dict:
        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=4096,
                system=_SYSTEM_PROMPT,
                tools=[_TOOL_SCHEMA],
                tool_choice={"type": "tool", "name": _TOOL_NAME},
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": page_image.media_type,
                                    "data": page_image.base64_data,
                                },
                            },
                            {"type": "text", "text": "Analysiere dieses Dokument gemaess den Systemanweisungen."},
                        ],
                    }
                ],
            )
        except anthropic.APIError as exc:
            raise VisionOcrError(f"Anthropic-API-Fehler bei der Dokumentenanalyse: {exc}") from exc

        tool_use_block = next((block for block in response.content if block.type == "tool_use"), None)
        if tool_use_block is None:
            raise VisionOcrError("Modellantwort enthielt keinen erwarteten Tool-Aufruf.")
        return tool_use_block.input

    def _render_pages(self, document: DocumentInput) -> list[_PageImage]:
        if document.mime_type == "application/pdf":
            return self._render_pdf_pages(document.file_bytes)
        return self._render_image_pages(document.file_bytes, document.mime_type)

    def _render_pdf_pages(self, file_bytes: bytes) -> list[_PageImage]:
        import pdfplumber

        images: list[_PageImage] = []
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page in pdf.pages[: self._max_pages]:
                pil_image = page.to_image(resolution=200).original
                images.append(self._encode_png(pil_image))
        return images

    def _render_image_pages(self, file_bytes: bytes, mime_type: str) -> list[_PageImage]:
        if mime_type in _NATIVE_IMAGE_MEDIA_TYPES:
            return [_PageImage(media_type=mime_type, base64_data=base64.b64encode(file_bytes).decode("ascii"))]

        # TIFF (und alles sonst Unbekannte) ueber Pillow in PNG konvertieren -
        # Claude Vision unterstuetzt kein TIFF direkt (Abschnitt 4.2).
        pil_image = Image.open(io.BytesIO(file_bytes))
        pages: list[_PageImage] = []
        frame_index = 0
        try:
            while frame_index < self._max_pages:
                pil_image.seek(frame_index)
                pages.append(self._encode_png(pil_image.convert("RGB")))
                frame_index += 1
        except EOFError:
            pass
        return pages or [self._encode_png(pil_image.convert("RGB"))]

    @staticmethod
    def _encode_png(pil_image: Image.Image) -> _PageImage:
        buffer = io.BytesIO()
        pil_image.save(buffer, format="PNG")
        return _PageImage(media_type="image/png", base64_data=base64.b64encode(buffer.getvalue()).decode("ascii"))
