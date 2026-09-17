"""Export von Pruefergebnissen nach XLSX/CSV (Abschnitt 1.1, 11)."""
from __future__ import annotations

from app.models.audit import AuditResult
from app.models.base import generate_uuid
from app.providers.base import ExportProvider, ExportRequest, ExportResult


def _audit_result_to_row(audit_result: AuditResult) -> dict:
    return {
        "audit_result_id": audit_result.id,
        # Faellt bei Tour-Pruefungen auf die Ladelistennummer zurueck (siehe
        # AuditResult.shipment_number in app/models/audit.py).
        "shipment_number": audit_result.shipment_number,
        "status": audit_result.status.value,
        "reference_distance_km": audit_result.reference_distance_km,
        "invoiced_distance_km": audit_result.invoiced_distance_km,
        "expected_amount": audit_result.expected_amount,
        "invoiced_amount": audit_result.invoiced_amount,
        "difference_amount": audit_result.difference_amount,
        "difference_percent": audit_result.difference_percent,
        "explanation": audit_result.explanation,
    }


def export_audit_results(audit_results: list[AuditResult], file_format: str, provider: ExportProvider) -> ExportResult:
    rows = [_audit_result_to_row(a) for a in audit_results]
    return provider.export(ExportRequest(export_id=generate_uuid(), file_format=file_format, rows=rows))
