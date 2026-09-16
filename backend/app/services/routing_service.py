"""Routing mit Cache (Abschnitt 5.2).

Der Cache verwendet gerundete Koordinaten (5 Nachkommastellen ~ 1,1 m
Genauigkeit) zusammen mit Profil und Provider als Schluessel, wie in
Abschnitt 5.2 gefordert ("nur verwenden, wenn Start, Ziel, Routingprofil,
Provider ... uebereinstimmen").
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.routing import RoutingResult
from app.providers.base import RouteInput, RoutingProvider

_CACHE_COORDINATE_PRECISION = 5


def _round_coord(value: float) -> float:
    return round(value, _CACHE_COORDINATE_PRECISION)


def get_or_calculate_route(
    db: Session,
    origin_lat: float,
    origin_lon: float,
    destination_lat: float,
    destination_lon: float,
    profile: str,
    provider: RoutingProvider,
    provider_name: str,
    shipment_id: str | None = None,
) -> tuple[RoutingResult, bool]:
    """Gibt `(RoutingResult, from_cache)` zurueck."""
    cached = db.execute(
        select(RoutingResult).where(
            RoutingResult.origin_latitude == _round_coord(origin_lat),
            RoutingResult.origin_longitude == _round_coord(origin_lon),
            RoutingResult.destination_latitude == _round_coord(destination_lat),
            RoutingResult.destination_longitude == _round_coord(destination_lon),
            RoutingResult.routing_profile == profile,
            RoutingResult.provider == provider_name,
        )
    ).scalars().first()
    if cached is not None:
        return cached, True

    route_result = provider.calculate_route(
        RouteInput(
            origin_lat=origin_lat, origin_lon=origin_lon,
            destination_lat=destination_lat, destination_lon=destination_lon, profile=profile,
        )
    )

    routing_result = RoutingResult(
        shipment_id=shipment_id,
        origin_latitude=_round_coord(origin_lat),
        origin_longitude=_round_coord(origin_lon),
        destination_latitude=_round_coord(destination_lat),
        destination_longitude=_round_coord(destination_lon),
        distance_km=route_result.distance_km,
        duration_minutes=route_result.duration_minutes,
        routing_profile=route_result.profile,
        provider=route_result.provider,
        calculated_at=route_result.calculated_at,
    )
    db.add(routing_result)
    db.flush()
    return routing_result, False
