from __future__ import annotations

from fastapi import APIRouter, Depends, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import get_storage_backend
from app.auth import get_current_user
from app.config import Settings, get_settings
from app.database import get_db
from app.errors import UnsupportedFileFormatError
from app.models.import_job import ImportJob
from app.schemas import ImportJobOut
from app.services.import_service import import_ladeliste
from app.services.ladeliste_pdf_import_service import import_ladeliste_pdf
from app.storage import StorageBackend

router = APIRouter(prefix="/api/imports", tags=["imports"], dependencies=[Depends(get_current_user)])

_SUPPORTED_SUFFIXES = (".csv", ".xlsx", ".pdf")


@router.post("", response_model=ImportJobOut)
async def import_file(
    file: UploadFile,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    storage: StorageBackend = Depends(get_storage_backend),
) -> ImportJob:
    if not file.filename or not file.filename.lower().endswith(_SUPPORTED_SUFFIXES):
        raise UnsupportedFileFormatError(
            f"Nicht unterstuetztes Dateiformat fuer Ladeliste: '{file.filename}'. Erlaubt: {_SUPPORTED_SUFFIXES}."
        )

    content = await file.read()
    report_storage_path = f"{settings.document_storage_path}/import_reports"

    if file.filename.lower().endswith(".pdf"):
        # Ladeliste-PDF (Tour mit ggf. vielen Auftraegen/Entladestellen,
        # BEGA-Finetuning) statt CSV/XLSX-Einzelsendungsliste.
        job = import_ladeliste_pdf(db, content, file.filename, storage, report_storage_path)
    else:
        job = import_ladeliste(db, content, file.filename, report_storage_path)

    db.commit()
    db.refresh(job)
    return job
