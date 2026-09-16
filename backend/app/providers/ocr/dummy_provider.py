"""Test-Fake fuer `DocumentOcrProvider`: liefert leere oder vorkonfigurierte
Ergebnisse, ohne eine echte OCR-Engine aufzurufen."""
from __future__ import annotations

from app.providers.base import DocumentInput, DocumentOcrProvider, OcrResult


class DummyOcrProvider(DocumentOcrProvider):
    def __init__(self, result: OcrResult | None = None) -> None:
        self._result = result or OcrResult(pages=[], fields=[])

    def analyze(self, document: DocumentInput) -> OcrResult:
        return self._result
