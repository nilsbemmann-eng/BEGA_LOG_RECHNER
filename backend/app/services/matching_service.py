"""Bindeglied zwischen ORM-`Shipment` und `app/matching/shipment_matcher.py`."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.matching.shipment_matcher import MatchInput, MatchOutcome, ShipmentCandidate, match_shipment
from app.models.shipment import Shipment


def _to_candidate(shipment: Shipment) -> ShipmentCandidate:
    return ShipmentCandidate(
        id=shipment.id,
        shipment_number=shipment.shipment_number,
        transport_order_number=shipment.transport_order_number,
        invoice_number=shipment.invoice_number,
        carrier_code=shipment.carrier.carrier_code if shipment.carrier else None,
        origin_address_text=shipment.origin_address.original_text if shipment.origin_address else None,
        destination_address_text=shipment.destination_address.original_text if shipment.destination_address else None,
        transport_date=shipment.transport_date,
        invoice_amount=shipment.invoice_amount,
    )


def find_matching_shipments(db: Session, match_input: MatchInput) -> MatchOutcome:
    shipments = db.execute(select(Shipment)).scalars().all()
    candidates = [_to_candidate(s) for s in shipments]
    return match_shipment(match_input, candidates)
