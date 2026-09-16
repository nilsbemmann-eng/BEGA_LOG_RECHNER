"""Bindeglied zwischen ORM-`SurchargeClaim` und `app/surcharge_engine/engine.py`."""
from __future__ import annotations

from app.models.surcharge import SurchargeClaim, SurchargeStatus
from app.surcharge_engine.engine import SurchargeClaimInput, SurchargeEvaluation, evaluate_surcharge_claim

_STATUS_MAP = {
    "allowed": SurchargeStatus.ALLOWED,
    "partially_allowed": SurchargeStatus.PARTIALLY_ALLOWED,
    "manual_review": SurchargeStatus.MANUAL_REVIEW,
}


def evaluate_and_persist_claim(claim: SurchargeClaim) -> SurchargeEvaluation:
    evaluation = evaluate_surcharge_claim(
        SurchargeClaimInput(
            surcharge_type=claim.surcharge_type.value,
            quantity=claim.quantity,
            unit_price=claim.unit_price,
            claimed_amount=claim.claimed_amount,
            has_evidence=claim.evidence_document_id is not None,
        )
    )
    claim.allowed_amount = evaluation.allowed_amount
    claim.status = _STATUS_MAP[evaluation.status]
    claim.reason = evaluation.reason
    return evaluation
