"""CRUD fuer die "Absender-Matrix"/"Gebietsrelationen" (BEGA-Finetuning,
Nutzervorgabe): ordnet Matchcodes/LL-Nummer-Praefixe Beladeadressen zu (siehe
`app/services/tour_origin_service.py`, docs/OFFENE_ENTSCHEIDUNGEN.md).

Versioniert (siehe Modell-Docstring): PATCH und DELETE aendern nie eine
bestehende Zeile, sondern erzeugen eine neue Version bzw. setzen die aktuelle
Version auf `is_current=False`."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_role
from app.database import get_db
from app.errors import (
    MasterDataConflictError,
    NotFoundError,
    TourOriginMatrixImportFailedError,
    UnsupportedFileFormatError,
)
from app.models.address import Address
from app.models.tour_origin_mapping import TourOriginMapping
from app.models.user import User, UserRole
from app.schemas import (
    TourOriginMappingCreate,
    TourOriginMappingOut,
    TourOriginMappingUpdateRequest,
    TourOriginMatrixImportResult,
)
from app.services.tour_origin_import_service import TourOriginMatrixParsingError, import_tour_origin_matrix

router = APIRouter(prefix="/api/tour-origin-mappings", tags=["tour-origin-mappings"], dependencies=[Depends(get_current_user)])

_MANAGE_ROLES = (UserRole.ADMIN, UserRole.PREISADMIN)


def _build_origin_address(street: str | None, postal_code: str | None, city: str | None, country_code: str | None) -> Address | None:
    if not city:
        return None
    return Address(
        original_text=f"{street or ''}, {postal_code or ''} {city}".strip(", "),
        street=street,
        postal_code=postal_code,
        city=city,
        country_code=country_code,
    )


@router.get("", response_model=list[TourOriginMappingOut])
def list_tour_origin_mappings(
    include_history: bool = Query(default=False, description="Auch abgeloeste Vorgaenger-Versionen zurueckgeben"),
    db: Session = Depends(get_db),
) -> list[TourOriginMappingOut]:
    query = select(TourOriginMapping)
    if not include_history:
        query = query.where(TourOriginMapping.is_current.is_(True))
    mappings = db.execute(query.order_by(TourOriginMapping.tour_number_prefix, TourOriginMapping.matchcode, TourOriginMapping.version)).scalars().all()
    return [TourOriginMappingOut.from_orm_mapping(m) for m in mappings]


@router.post("", response_model=TourOriginMappingOut, status_code=201)
def create_tour_origin_mapping(
    request: TourOriginMappingCreate,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_role(*_MANAGE_ROLES)),
) -> TourOriginMappingOut:
    """Anlegen ist Administrator-/Preisadmin-Aufgabe, analog zu Carrier/Tariff-Stammdaten."""
    existing = db.execute(
        select(TourOriginMapping).where(
            TourOriginMapping.tour_number_prefix == request.tour_number_prefix,
            TourOriginMapping.matchcode == request.matchcode,
            TourOriginMapping.is_current.is_(True),
        )
    ).scalars().first()
    if existing is not None:
        raise MasterDataConflictError(
            f"Fuer Praefix '{request.tour_number_prefix}' + Matchcode '{request.matchcode}' existiert bereits "
            f"eine aktuelle Zuordnung (Version {existing.version}) - zum Aendern PATCH verwenden."
        )

    mapping = TourOriginMapping(
        tour_number_prefix=request.tour_number_prefix,
        matchcode=request.matchcode,
        description=request.description,
        origin_address=_build_origin_address(request.street, request.postal_code, request.city, request.country_code),
    )
    db.add(mapping)
    db.commit()
    db.refresh(mapping)
    return TourOriginMappingOut.from_orm_mapping(mapping)


@router.patch("/{mapping_id}", response_model=TourOriginMappingOut)
def update_tour_origin_mapping(
    mapping_id: str,
    request: TourOriginMappingUpdateRequest,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_role(*_MANAGE_ROLES)),
) -> TourOriginMappingOut:
    current = db.get(TourOriginMapping, mapping_id)
    if current is None:
        raise NotFoundError(
            f"Absender-Zuordnung {mapping_id} nicht gefunden", entity_type="TourOriginMapping", entity_id=mapping_id
        )
    if not current.is_current:
        raise MasterDataConflictError(
            f"Absender-Zuordnung {mapping_id} ist eine abgeloeste Version (v{current.version}) und kann nicht "
            "mehr geaendert werden - die aktuelle Version bearbeiten."
        )

    description = request.description if request.description is not None else current.description
    street = request.street if request.street is not None else (current.origin_address.street if current.origin_address else None)
    postal_code = request.postal_code if request.postal_code is not None else (current.origin_address.postal_code if current.origin_address else None)
    city = request.city if request.city is not None else (current.origin_address.city if current.origin_address else None)
    country_code = request.country_code if request.country_code is not None else (current.origin_address.country_code if current.origin_address else None)

    current.is_current = False
    new_version = TourOriginMapping(
        tour_number_prefix=current.tour_number_prefix,
        matchcode=current.matchcode,
        description=description,
        origin_address=_build_origin_address(street, postal_code, city, country_code),
        version=current.version + 1,
        is_current=True,
    )
    db.add(new_version)
    db.commit()
    db.refresh(new_version)
    return TourOriginMappingOut.from_orm_mapping(new_version)


@router.post("/import", response_model=TourOriginMatrixImportResult)
async def import_tour_origin_matrix_endpoint(
    file: UploadFile,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_role(*_MANAGE_ROLES)),
) -> TourOriginMatrixImportResult:
    """Ersetzt die aktuelle Absender-Matrix durch den Inhalt der hochgeladenen
    "Gebietsrelationen"-Excel-Datei (vollstaendige Referenztabelle). Bisherige
    Zeilen werden dabei nicht geloescht, sondern versioniert abgeloest (siehe
    app/services/tour_origin_import_service.py)."""
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
    _current_user: User = Depends(require_role(*_MANAGE_ROLES)),
) -> None:
    """Loescht nicht physisch, sondern setzt die Version auf `is_current=False`
    (Historie bleibt fuer vergangene Tour-Audits nachvollziehbar)."""
    mapping = db.get(TourOriginMapping, mapping_id)
    if mapping is None:
        raise NotFoundError(
            f"Absender-Zuordnung {mapping_id} nicht gefunden", entity_type="TourOriginMapping", entity_id=mapping_id
        )
    mapping.is_current = False
    db.commit()
