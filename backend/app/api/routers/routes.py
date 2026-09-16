from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_geocoding_provider, get_routing_provider
from app.auth import get_current_user
from app.config import Settings, get_settings
from app.database import get_db
from app.errors import AddressNotGeocodableError
from app.providers.base import GeocodeInput, GeocodingProvider, RoutingProvider
from app.schemas import RouteCalculationRequest, RouteCalculationResponse
from app.services.routing_service import get_or_calculate_route

router = APIRouter(prefix="/api/routes", tags=["routes"], dependencies=[Depends(get_current_user)])


@router.post("/calculate", response_model=RouteCalculationResponse)
def calculate_route(
    request: RouteCalculationRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    geocoding_provider: GeocodingProvider = Depends(get_geocoding_provider),
    routing_provider: RoutingProvider = Depends(get_routing_provider),
) -> RouteCalculationResponse:
    origin_geocode = geocoding_provider.geocode(GeocodeInput(address_text=request.origin_address_text))
    if not origin_geocode.matched:
        raise AddressNotGeocodableError(f"Startadresse konnte nicht geocodiert werden: '{request.origin_address_text}'")

    destination_geocode = geocoding_provider.geocode(GeocodeInput(address_text=request.destination_address_text))
    if not destination_geocode.matched:
        raise AddressNotGeocodableError(f"Zieladresse konnte nicht geocodiert werden: '{request.destination_address_text}'")

    routing_result, from_cache = get_or_calculate_route(
        db,
        origin_lat=origin_geocode.latitude, origin_lon=origin_geocode.longitude,
        destination_lat=destination_geocode.latitude, destination_lon=destination_geocode.longitude,
        profile=request.profile, provider=routing_provider, provider_name=settings.routing_provider,
        shipment_id=request.shipment_id,
    )
    db.commit()

    return RouteCalculationResponse(
        origin_lat=routing_result.origin_latitude,
        origin_lon=routing_result.origin_longitude,
        destination_lat=routing_result.destination_latitude,
        destination_lon=routing_result.destination_longitude,
        distance_km=routing_result.distance_km,
        duration_minutes=routing_result.duration_minutes,
        profile=routing_result.routing_profile,
        provider=routing_result.provider,
        calculated_at=routing_result.calculated_at,
        from_cache=from_cache,
    )
