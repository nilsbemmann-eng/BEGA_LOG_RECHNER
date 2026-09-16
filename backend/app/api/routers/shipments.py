from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.errors import NotFoundError
from app.matching.shipment_matcher import MatchInput
from app.models.audit_log import AuditLogEntry
from app.models.document import Document
from app.models.shipment import Shipment
from app.models.user import User
from app.schemas import ShipmentMatchCandidateOut, ShipmentMatchRequest, ShipmentMatchResponse, ShipmentOut
from app.services.matching_service import find_matching_shipments

router = APIRouter(prefix="/api/shipments", tags=["shipments"], dependencies=[Depends(get_current_user)])


@router.post("/match", response_model=ShipmentMatchResponse)
def match_shipment_endpoint(
    request: ShipmentMatchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ShipmentMatchResponse:
    match_input = MatchInput(
        shipment_number=request.shipment_number,
        transport_order_number=request.transport_order_number,
        invoice_number=request.invoice_number,
        carrier_code=request.carrier_code,
        origin_address_text=request.origin_address_text,
        destination_address_text=request.destination_address_text,
        transport_date=request.transport_date,
        invoice_amount=request.invoice_amount,
    )
    outcome = find_matching_shipments(db, match_input)

    if outcome.auto_assigned is not None:
        document = db.get(Document, request.document_id)
        if document is None:
            raise NotFoundError(f"Dokument {request.document_id} nicht gefunden", entity_type="Document", entity_id=request.document_id)
        document.shipment_id = outcome.auto_assigned.id
        db.add(
            AuditLogEntry(
                user_id=current_user.id,
                entity_type="Document",
                entity_id=document.id,
                action="auto_assign_shipment",
                new_value_json={
                    "shipment_id": outcome.auto_assigned.id,
                    "matched_criteria": [c.value for c in outcome.ranked_candidates[0].matched_criteria],
                    "score": outcome.ranked_candidates[0].score,
                },
            )
        )
        db.commit()

    return ShipmentMatchResponse(
        auto_assigned_shipment_id=outcome.auto_assigned.id if outcome.auto_assigned else None,
        candidates=[
            ShipmentMatchCandidateOut(
                shipment_id=c.candidate.id, score=round(c.score, 3), matched_criteria=[m.value for m in c.matched_criteria]
            )
            for c in outcome.ranked_candidates
        ],
    )


@router.get("", response_model=list[ShipmentOut])
def list_shipments(db: Session = Depends(get_db)) -> list[Shipment]:
    return list(db.execute(select(Shipment)).scalars().all())


@router.get("/{shipment_id}", response_model=ShipmentOut)
def get_shipment(shipment_id: str, db: Session = Depends(get_db)) -> Shipment:
    shipment = db.get(Shipment, shipment_id)
    if shipment is None:
        raise NotFoundError(f"Sendung {shipment_id} nicht gefunden", entity_type="Shipment", entity_id=shipment_id)
    return shipment
