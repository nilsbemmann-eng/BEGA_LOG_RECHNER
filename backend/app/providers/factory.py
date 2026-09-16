"""Waehlt konkrete Provider-Implementierungen anhand der Konfiguration aus.

Dies ist die einzige Stelle, die Provider-Implementierungen instanziiert -
API-Router und Services haengen nur von den Interfaces in
`app/providers/base.py` ab (Abschnitt 10.2).
"""
from __future__ import annotations

from app.config import Settings
from app.providers.base import DocumentClassifier, DocumentOcrProvider, EmailProvider, ExportProvider, GeocodingProvider, RoutingProvider
from app.providers.classification.keyword_classifier import KeywordDocumentClassifier
from app.providers.export.tabular_export_provider import TabularExportProvider
from app.providers.geocoding.nominatim_provider import NominatimGeocodingProvider
from app.providers.ocr.dummy_provider import DummyOcrProvider
from app.providers.ocr.pdf_text_provider import PdfTextOcrProvider
from app.providers.routing.osrm_provider import OsrmRoutingProvider


def build_geocoding_provider(settings: Settings) -> GeocodingProvider:
    if settings.geocoding_provider == "nominatim":
        return NominatimGeocodingProvider(
            base_url=settings.nominatim_base_url, user_agent=settings.nominatim_user_agent
        )
    raise ValueError(f"Unbekannter geocoding_provider: {settings.geocoding_provider}")


def build_routing_provider(settings: Settings) -> RoutingProvider:
    if settings.routing_provider == "osrm":
        return OsrmRoutingProvider(base_url=settings.osrm_base_url)
    raise ValueError(f"Unbekannter routing_provider: {settings.routing_provider}")


def build_ocr_provider(settings: Settings) -> DocumentOcrProvider:
    if settings.ocr_provider == "pdf_text":
        return PdfTextOcrProvider()
    if settings.ocr_provider == "dummy":
        return DummyOcrProvider()
    if settings.ocr_provider == "llm_vision":
        from app.providers.ocr.llm_vision_provider import LlmVisionOcrProvider

        if not settings.anthropic_api_key:
            raise ValueError(
                "ocr_provider=llm_vision benoetigt ANTHROPIC_API_KEY als Umgebungsvariable "
                "bzw. ueber das Secret-Management."
            )
        return LlmVisionOcrProvider(
            api_key=settings.anthropic_api_key,
            model=settings.ocr_vision_model,
            max_pages=settings.ocr_vision_max_pages,
        )
    raise ValueError(f"Unbekannter ocr_provider: {settings.ocr_provider}")


def build_document_classifier(settings: Settings) -> DocumentClassifier:  # noqa: ARG001 - settings reserviert fuer Erweiterung
    return KeywordDocumentClassifier()


def build_export_provider(settings: Settings) -> ExportProvider:
    return TabularExportProvider(storage_path=settings.export_storage_path)


def build_email_provider(settings: Settings) -> EmailProvider:
    from app.providers.email.imap_provider import ImapEmailProvider

    if not settings.mailbox_host or not settings.mailbox_user or not settings.mailbox_password:
        raise ValueError(
            "Postfach nicht konfiguriert: MAILBOX_HOST, MAILBOX_USER und MAILBOX_PASSWORD muessen "
            "als Umgebungsvariablen bzw. ueber das Secret-Management gesetzt sein."
        )
    return ImapEmailProvider(
        host=settings.mailbox_host,
        user=settings.mailbox_user,
        password=settings.mailbox_password,
        use_ssl=settings.mailbox_use_ssl,
    )
