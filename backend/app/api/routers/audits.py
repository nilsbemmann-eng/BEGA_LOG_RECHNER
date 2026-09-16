from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_geocoding_provider, get_routing_provider
from app.auth import get_current_user, require_role
from app.config import Settings, get_settings
from app.database import get_db
from app.errors import NotFoundError
from app.models.audit import AuditResult, AuditStatus
from app.models.audit_log import AuditLogEntry
from app.models.user import User, UserRole
from app.providers.base import GeocodingProvider, RoutingProvider
from app.schemas import AuditDecisionRequest, AuditResultOut, AuditRunRequest
from app.services.audit_service import run_audit

router = APIRouter(prefix="/api/audits", tags=["audits"], dependencies=[Depends(get_current_user)])


@router.post("/run", response_model=AuditResultOut)
def run_audit_endpoint(
    request: AuditRunRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    geocoding_provider: GeocodingProvider = Depends(get_geocoding_provider),
    routing_provider: RoutingProvider = Depends(get_routing_provider),
) -> AuditResult:
    audit_result = run_audit(db, request.shipment_id, request.route_context, settings, geocoding_provider, routing_provider)
    db.commit()
    db.refresh(audit_result)
    return audit_result


@router.get("", response_model=list[AuditResultOut])
def list_audits(db: Session = Depends(get_db)) -> list[AuditResult]:
    return list(db.execute(select(AuditResult).order_by(AuditResult.created_at.desc())).scalars().all())


@router.get("/{audit_result_id}", response_model=AuditResultOut)
def get_audit(audit_result_id: str, db: Session = Depends(get_db)) -> AuditResult:
    audit_result = db.get(AuditResult, audit_result_id)
    if audit_result is None:
        raise NotFoundError(f"Pruefergebnis {audit_result_id} nicht gefunden", entity_type="AuditResult", entity_id=audit_result_id)
    return audit_result


@router.post("/{audit_result_id}/approve", response_model=AuditResultOut)
def approve_audit(
    audit_result_id: str,
    decision: AuditDecisionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PRUEFER, UserRole.ADMIN)),
) -> AuditResult:
    """Freigabe durch Rolle Pruefer/Administrator (Abschnitt 3.2, 18 Punkt 12)."""
    audit_result = db.get(AuditResult, audit_result_id)
    if audit_result is None:
        raise NotFoundError(f"Pruefergebnis {audit_result_id} nicht gefunden", entity_type="AuditResult", entity_id=audit_result_id)

    previous_status = audit_result.status
    audit_result.status = AuditStatus.FREIGEGEBEN
    audit_result.approved_by = current_user.id
    audit_result.approved_at = datetime.now(timezone.utc)
    db.add(
        AuditLogEntry(
            user_id=current_user.id, entity_type="AuditResult", entity_id=audit_result.id, action="approve",
            old_value_json={"status": previous_status.value, "comment": decision.comment},
            new_value_json={"status": AuditStatus.FREIGEGEBEN.value},
        )
    )
    db.commit()
    db.refresh(audit_result)
    return audit_result


@router.post("/{audit_result_id}/request-information", response_model=AuditResultOut)
def request_information(
    audit_result_id: str,
    decision: AuditDecisionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PRUEFER, UserRole.ADMIN)),
) -> AuditResult:
    audit_result = db.get(AuditResult, audit_result_id)
    if audit_result is None:
        raise NotFoundError(f"Pruefergebnis {audit_result_id} nicht gefunden", entity_type="AuditResult", entity_id=audit_result_id)

    previous_status = audit_result.status
    audit_result.status = AuditStatus.RUECKFRAGE
    db.add(
        AuditLogEntry(
            user_id=current_user.id, entity_type="AuditResult", entity_id=audit_result.id, action="request_information",
            old_value_json={"status": previous_status.value},
            new_value_json={"status": AuditStatus.RUECKFRAGE.value, "comment": decision.comment},
        )
    )
    db.commit()
    db.refresh(audit_result)
    return audit_result
