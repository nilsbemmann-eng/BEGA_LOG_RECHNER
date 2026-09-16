"""Dokumentenverarbeitung: OCR + Klassifikation (Abschnitt 2, 4.3, 4.4).

Reihenfolge im MVP: zuerst OCR/Textextraktion, danach Klassifikation anhand
des extrahierten Texts plus Dateiname. Das liefert deutlich bessere
Klassifikationsergebnisse als eine Klassifikation vor der Texterkennung und
weicht damit bewusst von der rein schematischen Reihenfolge in der
Prozesskette (Abschnitt 2.1) ab; fachlich aequivalent, da beide Schritte vor
der Sendungszuordnung abgeschlossen sind.

`process_document` aktualisiert ein beim E-Mail-Import bereits angelegtes
Stub-`Document` (Status `PENDING`), damit `/documents/{id}` und
`/documents/{id}/process` (Abschnitt 11) dieselbe, stabile Dokument-ID
verwenden.
"""
from __future__ import annotations

from app.models.document import Document, DocumentPage, DocumentType, ExtractedField, OcrStatus
from app.providers.base import DocumentClassifier, DocumentInput, DocumentOcrProvider
from app.storage import StorageBackend


def process_document(
    document: Document,
    classifier: DocumentClassifier,
    ocr_provider: DocumentOcrProvider,
    storage: StorageBackend,
) -> Document:
    attachment = document.attachment
    content = storage.load(attachment.storage_reference)
    ocr_result = ocr_provider.analyze(
        DocumentInput(file_bytes=content, mime_type=attachment.mime_type, filename=attachment.filename)
    )

    combined_text = "\n".join(page.extracted_text for page in ocr_result.pages)
    classification = classifier.classify(combined_text, attachment.filename)

    document.document_type = DocumentType(classification.document_type)
    document.classification_confidence = classification.confidence
    document.ocr_status = OcrStatus.DONE
    document.page_count = len(ocr_result.pages)
    document.pages = [
        DocumentPage(page_number=page.page_number, extracted_text=page.extracted_text, ocr_json=page.raw)
        for page in ocr_result.pages
    ]
    document.extracted_fields = [
        ExtractedField(
            field_name=field.field_name,
            original_value=field.original_value,
            normalized_value=str(field.normalized_value) if field.normalized_value is not None else None,
            data_type=field.data_type,
            confidence=field.confidence,
            source_page=field.source_page,
            source_text=field.source_text,
            source_bbox=field.source_bbox,
            extraction_method=field.extraction_method,
        )
        for field in ocr_result.fields
    ]
    return document
