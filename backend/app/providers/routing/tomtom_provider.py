"""`RoutingProvider`-Implementierung fuer TomTom (Nutzervorgabe: TomTom fuer
das Routing verwenden).

TomToms Calculate-Route-API unterstuetzt echtes Lkw-Routing
(`travelMode=truck`) inkl. Hoehen-/Gewichtsbeschraenkungen (im Gegensatz zum
oeffentlichen OSRM-Demo-Server, der nur `driving` kennt, siehe
`app/providers/routing/osrm_provider.py`) - daher wird `truck` hier direkt
durchgereicht statt auf `driving` abgebildet.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone

import httpx

from app.providers.base import RouteInput, RouteResult

_TOMTOM_TRAVEL_MODE_BY_PROFILE = {
    "truck": "truck",
    "car": "car",
}


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_km = 6371.0088
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return radius_km * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


class TomTomRoutingNotPossibleError(RuntimeError):
    """Entspricht dem Fehler 'Routing nicht moeglich' aus Abschnitt 14."""


class TomTomRoutingProvider:
    def __init__(self, api_key: str, base_url: str = "https://api.tomtom.com", timeout_seconds: float = 15.0) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds

    def calculate_route(self, route_input: RouteInput) -> RouteResult:
        if route_input.profile == "air":
            distance_km = _haversine_km(
                route_input.origin_lat, route_input.origin_lon,
                route_input.destination_lat, route_input.destination_lon,
            )
            return RouteResult(
                origin_lat=route_input.origin_lat,
                origin_lon=route_input.origin_lon,
                destination_lat=route_input.destination_lat,
                destination_lon=route_input.destination_lon,
                distance_km=round(distance_km, 2),
                duration_minutes=0,
                profile="air",
                provider="haversine",
                calculated_at=datetime.now(timezone.utc),
            )

        travel_mode = _TOMTOM_TRAVEL_MODE_BY_PROFILE.get(route_input.profile, "car")
        locations = (
            f"{route_input.origin_lat},{route_input.origin_lon}:"
            f"{route_input.destination_lat},{route_input.destination_lon}"
        )
        response = httpx.get(
            f"{self._base_url}/routing/1/calculateRoute/{locations}/json",
            params={"key": self._api_key, "travelMode": travel_mode, "routeType": "fastest", "traffic": "false"},
            timeout=self._timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        routes = payload.get("routes") or []
        if not routes:
            raise TomTomRoutingNotPossibleError(
                f"TomTom konnte keine Route berechnen: {payload.get('detailedError', payload)}"
            )

        summary = routes[0]["summary"]
        return RouteResult(
            origin_lat=route_input.origin_lat,
            origin_lon=route_input.origin_lon,
            destination_lat=route_input.destination_lat,
            destination_lon=route_input.destination_lon,
            distance_km=round(summary["lengthInMeters"] / 1000, 2),
            duration_minutes=round(summary["travelTimeInSeconds"] / 60),
            profile=route_input.profile,
            provider="tomtom",
            calculated_at=datetime.now(timezone.utc),
        )
