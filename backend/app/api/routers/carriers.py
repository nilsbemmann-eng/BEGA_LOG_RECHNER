"""Erfassungsmaske fuer Spediteure (Frachtfuehrer): manuelles Anlegen/Pflegen
von Stammdaten, ergaenzend zum automatischen Anlegen beim
Preistabellen-Import (`app/services/carrier_rate_import_service.py`). Zugriff
fuer Admin und den Sub-Admin "Preisadmin" (Frachtpreise pflegen)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_role
from app.database import get_db
from app.errors import CarrierAlreadyExistsError, NotFoundError
from app.models.party import Carrier
from app.models.user import User, UserRole
from app.schemas import CarrierCreateRequest, CarrierOut, CarrierUpdateRequest
from app.services.carrier_service import generate_unique_carrier_code

router = APIRouter(prefix="/api/carriers", tags=["carriers"], dependencies=[Depends(get_current_user)])

_MANAGE_ROLES = (UserRole.ADMIN, UserRole.PREISADMIN)


@router.get("", response_model=list[CarrierOut])
def list_carriers(db: Session = Depends(get_db)) -> list[Carrier]:
    return list(db.execute(select(Carrier).order_by(Carrier.name)).scalars().all())


@router.post("", response_model=CarrierOut, status_code=201)
def create_carrier(
    request: CarrierCreateRequest,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_role(*_MANAGE_ROLES)),
) -> Carrier:
    if db.execute(select(Carrier).where(Carrier.name == request.name)).scalars().first() is not None:
        raise CarrierAlreadyExistsError(f"Spediteur '{request.name}' ist bereits angelegt.")

    carrier = Carrier(
        name=request.name,
        carrier_code=generate_unique_carrier_code(db, request.name),
        billing_rules_reference=request.billing_rules_reference,
    )
    db.add(carrier)
    db.commit()
    db.refresh(carrier)
    return carrier


@router.patch("/{carrier_id}", response_model=CarrierOut)
def update_carrier(
    carrier_id: str,
    request: CarrierUpdateRequest,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_role(*_MANAGE_ROLES)),
) -> Carrier:
    carrier = db.get(Carrier, carrier_id)
    if carrier is None:
        raise NotFoundError(f"Spediteur {carrier_id} nicht gefunden", entity_type="Carrier", entity_id=carrier_id)

    if request.name is not None:
        carrier.name = request.name
    if request.billing_rules_reference is not None:
        carrier.billing_rules_reference = request.billing_rules_reference
    db.commit()
    db.refresh(carrier)
    return carrier
