from __future__ import annotations

import os

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_export_provider
from app.auth import get_current_user
from app.config import Settings, get_settings
from app.database import get_db
from app.errors import NotFoundError
from app.models.audit import AuditResult
from app.providers.base import ExportProvider
from app.schemas import ExportOut, ExportRequestIn
from app.services.export_service import export_audit_results

router = APIRouter(prefix="/api/exports", tags=["exports"], dependencies=[Depends(get_current_user)])


@router.post("", response_model=ExportOut)
def create_export(
    request: ExportRequestIn,
    db: Session = Depends(get_db),
    export_provider: ExportProvider = Depends(get_export_provider),
) -> ExportOut:
    audit_results = list(
        db.execute(select(AuditResult).where(AuditResult.id.in_(request.audit_result_ids))).scalars().all()
    )
    result = export_audit_results(audit_results, request.file_format, export_provider)
    export_id = os.path.splitext(os.path.basename(result.storage_reference))[0].split("_")[-1]
    return ExportOut(
        export_id=export_id, file_format=result.file_format, row_count=result.row_count,
        storage_reference=result.storage_reference,
    )


@router.get("/{export_id}", response_model=ExportOut)
def get_export(export_id: str, settings: Settings = Depends(get_settings)) -> ExportOut:
    if not os.path.isdir(settings.export_storage_path):
        raise NotFoundError(f"Export {export_id} nicht gefunden", entity_type="Export", entity_id=export_id)

    for filename in os.listdir(settings.export_storage_path):
        name_without_ext, ext = os.path.splitext(filename)
        if name_without_ext.endswith(export_id):
            path = os.path.join(settings.export_storage_path, filename)
            return ExportOut(export_id=export_id, file_format=ext.lstrip("."), row_count=-1, storage_reference=path)

    raise NotFoundError(f"Export {export_id} nicht gefunden", entity_type="Export", entity_id=export_id)
