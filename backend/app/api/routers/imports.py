from __future__ import annotations

from fastapi import APIRouter, Depends, UploadFile
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.config import Settings, get_settings
from app.database import get_db
from app.errors import UnsupportedFileFormatError
from app.models.import_job import ImportJob
from app.schemas import ImportJobOut
from app.services.import_service import import_ladeliste

router = APIRouter(prefix="/api/imports", tags=["imports"], dependencies=[Depends(get_current_user)])

_SUPPORTED_SUFFIXES = (".csv", ".xlsx")


@router.post("", response_model=ImportJobOut)
async def import_file(
    file: UploadFile,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> ImportJob:
    if not file.filename or not file.filename.lower().endswith(_SUPPORTED_SUFFIXES):
        raise UnsupportedFileFormatError(
            f"Nicht unterstuetztes Dateiformat fuer Ladeliste: '{file.filename}'. Erlaubt: {_SUPPORTED_SUFFIXES}."
        )

    content = await file.read()
    report_storage_path = f"{settings.document_storage_path}/import_reports"
    job = import_ladeliste(db, content, file.filename, report_storage_path)
    db.commit()
    db.refresh(job)
    return job
