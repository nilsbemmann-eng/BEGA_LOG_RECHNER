from __future__ import annotations

from fastapi import Depends
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database import get_db
from app.providers.base import DocumentClassifier, DocumentOcrProvider, ExportProvider, GeocodingProvider, RoutingProvider
from app.providers.factory import (
    build_document_classifier,
    build_export_provider,
    build_geocoding_provider,
    build_ocr_provider,
    build_routing_provider,
)
from app.storage import LocalFileSystemStorage, StorageBackend


def get_geocoding_provider(settings: Settings = Depends(get_settings)) -> GeocodingProvider:
    return build_geocoding_provider(settings)


def get_routing_provider(settings: Settings = Depends(get_settings), db: Session = Depends(get_db)) -> RoutingProvider:
    return build_routing_provider(settings, db)


def get_ocr_provider(settings: Settings = Depends(get_settings)) -> DocumentOcrProvider:
    return build_ocr_provider(settings)


def get_document_classifier(settings: Settings = Depends(get_settings)) -> DocumentClassifier:
    return build_document_classifier(settings)


def get_export_provider(settings: Settings = Depends(get_settings)) -> ExportProvider:
    return build_export_provider(settings)


def get_storage_backend(settings: Settings = Depends(get_settings)) -> StorageBackend:
    return LocalFileSystemStorage(base_path=settings.document_storage_path)
