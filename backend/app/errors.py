"""Einheitliche Fehlerbehandlung (Abschnitt 14).

Jeder ueber `AppError` gemeldete Fehler liefert dem Client:
Fehlercode, verstaendliche Beschreibung, betroffene Entitaet, Zeitpunkt und
ob eine Wiederholung sinnvoll ist. Technische Details (Tracebacks) landen nur
im Server-Log, nie in der API-Antwort.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger("bega.errors")


class AppError(Exception):
    """Basisklasse fuer alle fachlichen Fehler aus Abschnitt 14."""

    error_code = "internal_error"
    status_code = 500
    retryable = False

    def __init__(self, message: str, *, entity_type: str | None = None, entity_id: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.entity_type = entity_type
        self.entity_id = entity_id

    def to_payload(self) -> dict:
        return {
            "error_code": self.error_code,
            "message": self.message,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "retryable": self.retryable,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


class MailboxUnavailableError(AppError):
    error_code = "mailbox_unavailable"
    status_code = 502
    retryable = True


class AttachmentCorruptError(AppError):
    error_code = "attachment_corrupt"
    status_code = 422
    retryable = False


class UnsupportedFileFormatError(AppError):
    error_code = "unsupported_file_format"
    status_code = 422
    retryable = False


class EmailFileCorruptError(AppError):
    """Entspricht 'Anhang beschaedigt' aus Abschnitt 14, hier fuer die
    hochgeladene E-Mail-Datei selbst (z. B. eine ungueltige .msg-Datei)."""

    error_code = "email_file_corrupt"
    status_code = 422
    retryable = False


class OcrProviderUnavailableError(AppError):
    error_code = "ocr_provider_unavailable"
    status_code = 502
    retryable = True


class MandatoryFieldMissingError(AppError):
    error_code = "mandatory_field_missing"
    status_code = 422
    retryable = False


class AddressNotGeocodableError(AppError):
    error_code = "address_not_geocodable"
    status_code = 422
    retryable = True


class RoutingNotPossibleError(AppError):
    error_code = "routing_not_possible"
    status_code = 502
    retryable = True


class TariffNotFoundApiError(AppError):
    error_code = "tariff_not_found"
    status_code = 422
    retryable = False


class MultipleTariffsValidApiError(AppError):
    error_code = "multiple_tariffs_valid"
    status_code = 422
    retryable = False


class ShipmentNotUniquelyAssignedError(AppError):
    error_code = "shipment_not_uniquely_assigned"
    status_code = 409
    retryable = False


class UnsupportedCurrencyError(AppError):
    error_code = "unsupported_currency"
    status_code = 422
    retryable = False


class EvidenceMissingError(AppError):
    error_code = "evidence_missing"
    status_code = 422
    retryable = False


class NotFoundError(AppError):
    error_code = "not_found"
    status_code = 404
    retryable = False


class TourOriginMatrixImportFailedError(AppError):
    """Die hochgeladene "Gebietsrelationen"-Excel-Datei entspricht nicht der
    erwarteten Spaltenstruktur (siehe app/services/tour_origin_import_service.py)."""

    error_code = "tour_origin_matrix_import_failed"
    status_code = 422
    retryable = False


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _handle_app_error(request: Request, exc: AppError) -> JSONResponse:  # noqa: ARG001
        logger.warning("AppError %s: %s", exc.error_code, exc.message)
        return JSONResponse(status_code=exc.status_code, content=exc.to_payload())

    @app.exception_handler(Exception)
    async def _handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:  # noqa: ARG001
        logger.exception("Unerwarteter Fehler")
        fallback = AppError(
            "Ein unerwarteter Fehler ist aufgetreten. Bitte spaeter erneut versuchen."
        )
        fallback.retryable = True
        return JSONResponse(status_code=500, content=fallback.to_payload())
