"""CRUD fuer die "Absender-Matrix" (BEGA-Finetuning, Nutzervorgabe): ordnet
LL-Nummer-Praefixe Beladeadressen zu (siehe
`app/services/tour_origin_service.py`, docs/OFFENE_ENTSCHEIDUNGEN.md)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_role
from app.database import get_db
from app.errors import NotFoundError
from app.models.address import Address
from app.models.tour_origin_mapping import TourOriginMapping
from app.models.user import User, UserRole
from app.schemas import TourOriginMappingCreate, TourOriginMappingOut

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
    mapping = TourOriginMapping(
        tour_number_prefix=request.tour_number_prefix,
        label=request.label,
        origin_address=Address(
            original_text=f"{request.street or ''}, {request.postal_code or ''} {request.city}".strip(", "),
            street=request.street,
            postal_code=request.postal_code,
            city=request.city,
            country_code=request.country_code,
        ),
    )
    db.add(mapping)
    db.commit()
    db.refresh(mapping)
    return TourOriginMappingOut.from_orm_mapping(mapping)


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
