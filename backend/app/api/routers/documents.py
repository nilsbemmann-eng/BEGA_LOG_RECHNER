from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_document_classifier, get_ocr_provider, get_storage_backend
from app.auth import get_current_user
from app.database import get_db
from app.errors import NotFoundError, OcrProviderUnavailableError
from app.models.document import Document, OcrStatus
from app.providers.base import DocumentClassifier, DocumentOcrProvider
from app.schemas import DocumentOut
from app.services.document_service import process_document
from app.storage import StorageBackend

router = APIRouter(prefix="/api/documents", tags=["documents"], dependencies=[Depends(get_current_user)])


@router.post("/{document_id}/process", response_model=DocumentOut)
def process_document_endpoint(
    document_id: str,
    db: Session = Depends(get_db),
    classifier: DocumentClassifier = Depends(get_document_classifier),
    ocr_provider: DocumentOcrProvider = Depends(get_ocr_provider),
    storage: StorageBackend = Depends(get_storage_backend),
) -> Document:
    document = db.get(Document, document_id)
    if document is None:
        raise NotFoundError(f"Dokument {document_id} nicht gefunden", entity_type="Document", entity_id=document_id)

    try:
        document.ocr_status = OcrStatus.PROCESSING
        process_document(document, classifier, ocr_provider, storage)
    except Exception as exc:  # noqa: BLE001
        document.ocr_status = OcrStatus.ERROR
        db.commit()
        raise OcrProviderUnavailableError(
            f"Dokumentenverarbeitung fehlgeschlagen: {exc}", entity_type="Document", entity_id=document_id
        ) from exc

    db.commit()
    db.refresh(document)
    return document


@router.get("/{document_id}", response_model=DocumentOut)
def get_document(document_id: str, db: Session = Depends(get_db)) -> Document:
    document = db.get(Document, document_id)
    if document is None:
        raise NotFoundError(f"Dokument {document_id} nicht gefunden", entity_type="Document", entity_id=document_id)
    return document
