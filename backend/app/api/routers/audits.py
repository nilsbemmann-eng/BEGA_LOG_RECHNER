from __future__ import annotations

from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_geocoding_provider, get_routing_provider
from app.auth import get_current_user, require_role
from app.config import Settings, get_settings
from app.database import get_db
from app.errors import NotFoundError
from app.models.audit import AuditResult, AuditStatus
from app.models.audit_log import AuditLogEntry
from app.models.party import Carrier
from app.models.shipment import Shipment
from app.models.tour import Tour
from app.models.user import User, UserRole
from app.providers.base import GeocodingProvider, RoutingProvider
from app.schemas import AuditDecisionRequest, AuditResultOut, AuditRunRequest, TourAuditRunRequest
from app.services.audit_service import run_audit, run_tour_audit

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


@router.post("/run-tour", response_model=AuditResultOut)
def run_tour_audit_endpoint(
    request: TourAuditRunRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    geocoding_provider: GeocodingProvider = Depends(get_geocoding_provider),
    routing_provider: RoutingProvider = Depends(get_routing_provider),
) -> AuditResult:
    """Preispruefung fuer eine ganze Tour/Ladeliste (BEGA-Finetuning: eine
    Frachtrechnung pro Tour statt pro Einzelsendung, siehe app/models/tour.py)."""
    audit_result = run_tour_audit(db, request.tour_id, settings, geocoding_provider, routing_provider)
    db.commit()
    db.refresh(audit_result)
    return audit_result


@router.get("", response_model=list[AuditResultOut])
def list_audits(
    db: Session = Depends(get_db),
    status: AuditStatus | None = Query(default=None, description="Filter nach Pruefstatus"),
    q: str | None = Query(
        default=None,
        description="Freitextsuche ueber Sendungsnummer, Transportauftrags-/Rechnungsnummer und Frachtfuehrername",
    ),
    carrier_id: str | None = Query(default=None, description="Filter nach Frachtfuehrer"),
    date_from: date | None = Query(default=None, description="Transportdatum von (einschliesslich)"),
    date_to: date | None = Query(default=None, description="Transportdatum bis (einschliesslich)"),
) -> list[AuditResult]:
    """Historie der Pruefergebnisse (Abschnitt 12) mit Such- und Filterfunktion.

    `AuditResult.shipment_id`/`tour_id` sind alternativ gesetzt (Tour-Pruefung,
    BEGA-Finetuning, siehe app/models/tour.py) - daher Outer-Joins auf beide
    Seiten statt eines Inner-Joins auf `Shipment`, sonst wuerden Tour-Ergebnisse
    aus der Historie verschwinden."""
    query = (
        select(AuditResult)
        .outerjoin(Shipment, AuditResult.shipment_id == Shipment.id)
        .outerjoin(Tour, AuditResult.tour_id == Tour.id)
        .outerjoin(Carrier, or_(Shipment.carrier_id == Carrier.id, Tour.carrier_id == Carrier.id))
    )

    if status is not None:
        query = query.where(AuditResult.status == status)
    if carrier_id is not None:
        query = query.where(or_(Shipment.carrier_id == carrier_id, Tour.carrier_id == carrier_id))
    if date_from is not None:
        query = query.where(or_(Shipment.transport_date >= date_from, Tour.tour_date >= date_from))
    if date_to is not None:
        query = query.where(or_(Shipment.transport_date <= date_to, Tour.tour_date <= date_to))
    if q:
        like_pattern = f"%{q.strip()}%"
        query = query.where(
            or_(
                Shipment.shipment_number.ilike(like_pattern),
                Shipment.transport_order_number.ilike(like_pattern),
                Shipment.invoice_number.ilike(like_pattern),
                Tour.tour_number.ilike(like_pattern),
                Carrier.name.ilike(like_pattern),
            )
        )

    query = query.order_by(AuditResult.created_at.desc())
    return list(db.execute(query).scalars().unique().all())


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
