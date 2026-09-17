"""CRUD fuer die "Absender-Matrix"/"Gebietsrelationen" (BEGA-Finetuning,
Nutzervorgabe): ordnet Matchcodes/LL-Nummer-Praefixe Beladeadressen zu (siehe
`app/services/tour_origin_service.py`, docs/OFFENE_ENTSCHEIDUNGEN.md)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_role
from app.database import get_db
from app.errors import NotFoundError, TourOriginMatrixImportFailedError, UnsupportedFileFormatError
from app.models.address import Address
from app.models.tour_origin_mapping import TourOriginMapping
from app.models.user import User, UserRole
from app.schemas import TourOriginMappingCreate, TourOriginMappingOut, TourOriginMatrixImportResult
from app.services.tour_origin_import_service import TourOriginMatrixParsingError, import_tour_origin_matrix

router = APIRouter(prefix="/api/tour-origin-mappings", tags=["tour-origin-mappings"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[TourOriginMappingOut])
def list_tour_origin_mappings(db: Session = Depends(get_db)) -> list[TourOriginMappingOut]:
    mappings = db.execute(select(TourOriginMapping)).scalars().all()
    return [TourOriginMappingOut.from_orm_mapping(m) for m in mappings]


@router.post("", response_model=TourOriginMappingOut, status_code=201)
def create_tour_origin_mapping(
    request: TourOriginMappingCreate,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_role(UserRole.ADMIN)),
) -> TourOriginMappingOut:
    """Anlegen ist Administrator-Aufgabe, analog zu Carrier/Tariff-Stammdaten."""
    origin_address = None
    if request.city:
        origin_address = Address(
            original_text=f"{request.street or ''}, {request.postal_code or ''} {request.city}".strip(", "),
            street=request.street,
            postal_code=request.postal_code,
            city=request.city,
            country_code=request.country_code,
        )
    mapping = TourOriginMapping(
        tour_number_prefix=request.tour_number_prefix,
        matchcode=request.matchcode,
        description=request.description,
        origin_address=origin_address,
    )
    db.add(mapping)
    db.commit()
    db.refresh(mapping)
    return TourOriginMappingOut.from_orm_mapping(mapping)


@router.post("/import", response_model=TourOriginMatrixImportResult)
async def import_tour_origin_matrix_endpoint(
    file: UploadFile,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_role(UserRole.ADMIN)),
) -> TourOriginMatrixImportResult:
    """Ersetzt die gesamte Absender-Matrix durch den Inhalt der hochgeladenen
    "Gebietsrelationen"-Excel-Datei (vollstaendige Referenztabelle, kein
    inkrementelles Update - siehe app/services/tour_origin_import_service.py)."""
    if not file.filename or not file.filename.lower().endswith(".xlsx"):
        raise UnsupportedFileFormatError(
            f"Nicht unterstuetztes Dateiformat fuer die Absender-Matrix: '{file.filename}'. Erlaubt: .xlsx"
        )
    content = await file.read()
    try:
        imported_count = import_tour_origin_matrix(db, content)
    except TourOriginMatrixParsingError as exc:
        raise TourOriginMatrixImportFailedError(str(exc)) from exc
    db.commit()
    return TourOriginMatrixImportResult(imported_count=imported_count)


@router.delete("/{mapping_id}", status_code=204, response_model=None)
def delete_tour_origin_mapping(
    mapping_id: str,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_role(UserRole.ADMIN)),
) -> None:
    mapping = db.get(TourOriginMapping, mapping_id)
    if mapping is None:
        raise NotFoundError(
            f"Absender-Zuordnung {mapping_id} nicht gefunden", entity_type="TourOriginMapping", entity_id=mapping_id
        )
    db.delete(mapping)
    db.commit()
