"""CRUD fuer den "Sondervereinbarungen"-Zuschlag je Ladelisten-Praefix
(BEGA-Finetuning, reale Preisformel), siehe
app/models/special_agreement_surcharge.py.

Versioniert (siehe Modell-Docstring): PATCH und DELETE aendern nie eine
bestehende Zeile, sondern erzeugen eine neue Version bzw. setzen die aktuelle
Version auf `is_current=False`, damit vergangene Tour-Audits nachvollziehbar
bleiben."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_role
from app.database import get_db
from app.errors import MasterDataConflictError, NotFoundError
from app.models.special_agreement_surcharge import SpecialAgreementSurcharge
from app.models.user import User, UserRole
from app.schemas import (
    SpecialAgreementSurchargeCreate,
    SpecialAgreementSurchargeOut,
    SpecialAgreementSurchargeUpdateRequest,
)

router = APIRouter(prefix="/api/special-agreement-surcharges", tags=["special-agreement-surcharges"], dependencies=[Depends(get_current_user)])

_MANAGE_ROLES = (UserRole.ADMIN, UserRole.PREISADMIN)


@router.get("", response_model=list[SpecialAgreementSurchargeOut])
def list_special_agreement_surcharges(
    include_history: bool = Query(default=False, description="Auch abgeloeste Vorgaenger-Versionen zurueckgeben"),
    db: Session = Depends(get_db),
) -> list[SpecialAgreementSurcharge]:
    query = select(SpecialAgreementSurcharge)
    if not include_history:
        query = query.where(SpecialAgreementSurcharge.is_current.is_(True))
    return list(db.execute(query.order_by(SpecialAgreementSurcharge.tour_number_prefix, SpecialAgreementSurcharge.version)).scalars().all())


@router.post("", response_model=SpecialAgreementSurchargeOut, status_code=201)
def create_special_agreement_surcharge(
    request: SpecialAgreementSurchargeCreate,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_role(*_MANAGE_ROLES)),
) -> SpecialAgreementSurcharge:
    existing = db.execute(
        select(SpecialAgreementSurcharge).where(
            SpecialAgreementSurcharge.tour_number_prefix == request.tour_number_prefix,
            SpecialAgreementSurcharge.is_current.is_(True),
        )
    ).scalars().first()
    if existing is not None:
        raise MasterDataConflictError(
            f"Fuer Praefix '{request.tour_number_prefix}' existiert bereits eine aktuelle Sondervereinbarung "
            f"(Version {existing.version}) - zum Aendern PATCH auf die bestehende Zeile verwenden."
        )

    surcharge = SpecialAgreementSurcharge(
        tour_number_prefix=request.tour_number_prefix, amount=request.amount, note=request.note
    )
    db.add(surcharge)
    db.commit()
    db.refresh(surcharge)
    return surcharge


@router.patch("/{surcharge_id}", response_model=SpecialAgreementSurchargeOut)
def update_special_agreement_surcharge(
    surcharge_id: str,
    request: SpecialAgreementSurchargeUpdateRequest,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_role(*_MANAGE_ROLES)),
) -> SpecialAgreementSurcharge:
    """Aendert eine Sondervereinbarung NICHT in-place, sondern legt eine neue
    Version an (siehe Modul-Docstring)."""
    current = db.get(SpecialAgreementSurcharge, surcharge_id)
    if current is None:
        raise NotFoundError(
            f"Sondervereinbarung {surcharge_id} nicht gefunden",
            entity_type="SpecialAgreementSurcharge", entity_id=surcharge_id,
        )
    if not current.is_current:
        raise MasterDataConflictError(
            f"Sondervereinbarung {surcharge_id} ist eine abgeloeste Version (v{current.version}) und kann "
            "nicht mehr geaendert werden - die aktuelle Version bearbeiten."
        )

    current.is_current = False
    new_version = SpecialAgreementSurcharge(
        tour_number_prefix=current.tour_number_prefix,
        amount=request.amount if request.amount is not None else current.amount,
        note=request.note if request.note is not None else current.note,
        version=current.version + 1,
        is_current=True,
    )
    db.add(new_version)
    db.commit()
    db.refresh(new_version)
    return new_version


@router.delete("/{surcharge_id}", status_code=204, response_model=None)
def delete_special_agreement_surcharge(
    surcharge_id: str,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_role(*_MANAGE_ROLES)),
) -> None:
    """Loescht nicht physisch, sondern setzt die Version auf `is_current=False`
    (Praefix hat danach keine aktive Sondervereinbarung mehr, die Historie
    bleibt aber fuer vergangene Tour-Audits nachvollziehbar)."""
    surcharge = db.get(SpecialAgreementSurcharge, surcharge_id)
    if surcharge is None:
        raise NotFoundError(
            f"Sondervereinbarung {surcharge_id} nicht gefunden",
            entity_type="SpecialAgreementSurcharge", entity_id=surcharge_id,
        )
    surcharge.is_current = False
    db.commit()
