"""CRUD fuer den "Sondervereinbarungen"-Zuschlag je Ladelisten-Praefix
(BEGA-Finetuning, reale Preisformel), siehe
app/models/special_agreement_surcharge.py."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_role
from app.database import get_db
from app.errors import NotFoundError
from app.models.special_agreement_surcharge import SpecialAgreementSurcharge
from app.models.user import User, UserRole
from app.schemas import SpecialAgreementSurchargeCreate, SpecialAgreementSurchargeOut

router = APIRouter(prefix="/api/special-agreement-surcharges", tags=["special-agreement-surcharges"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[SpecialAgreementSurchargeOut])
def list_special_agreement_surcharges(db: Session = Depends(get_db)) -> list[SpecialAgreementSurcharge]:
    return list(db.execute(select(SpecialAgreementSurcharge)).scalars().all())


@router.post("", response_model=SpecialAgreementSurchargeOut, status_code=201)
def create_special_agreement_surcharge(
    request: SpecialAgreementSurchargeCreate,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_role(UserRole.ADMIN)),
) -> SpecialAgreementSurcharge:
    surcharge = SpecialAgreementSurcharge(
        tour_number_prefix=request.tour_number_prefix, amount=request.amount, note=request.note
    )
    db.add(surcharge)
    db.commit()
    db.refresh(surcharge)
    return surcharge


@router.delete("/{surcharge_id}", status_code=204, response_model=None)
def delete_special_agreement_surcharge(
    surcharge_id: str,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_role(UserRole.ADMIN)),
) -> None:
    surcharge = db.get(SpecialAgreementSurcharge, surcharge_id)
    if surcharge is None:
        raise NotFoundError(
            f"Sondervereinbarung {surcharge_id} nicht gefunden",
            entity_type="SpecialAgreementSurcharge", entity_id=surcharge_id,
        )
    db.delete(surcharge)
    db.commit()
