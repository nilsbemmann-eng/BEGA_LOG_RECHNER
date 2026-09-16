"""`RoutingProvider`-Implementierung fuer OSRM (Open Source Routing Machine).

Wichtige Einschraenkung (siehe docs/OFFENE_ENTSCHEIDUNGEN.md, Punkt 5): der
oeffentliche OSRM-Demo-Server (`router.project-osrm.org`) unterstuetzt nur die
Profile `driving`, `walking` und `cycling`, kein dediziertes Lkw-Profil. Fuer
eine echte Lkw-Referenzroute (Hoehen-, Gewichts- und Durchfahrtsbeschraenkungen)
wird ein selbst gehosteter OSRM-Server mit einem Lkw-Profil (z. B. basierend
auf `osrm-backend`-Lua-Profilen fuer Lkw) oder ein alternativer Dienst wie
GraphHopper/openrouteservice mit `profile=truck` benoetigt. Bis dahin wird das
Profil `truck` auf `driving` abgebildet und diese Vereinfachung im
Ergebnis (`provider`-Feld bleibt `osrm`) dokumentiert, statt sie zu verstecken.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone

import httpx

from app.providers.base import RouteInput, RouteResult

_OSRM_PROFILE_BY_INTERNAL_PROFILE = {
    "truck": "driving",
    "car": "driving",
}


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_km = 6371.0088
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return radius_km * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


class OsrmRoutingProvider:
    def __init__(self, base_url: str, timeout_seconds: float = 15.0) -> None:
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

        osrm_profile = _OSRM_PROFILE_BY_INTERNAL_PROFILE.get(route_input.profile, "driving")
        coordinates = (
            f"{route_input.origin_lon},{route_input.origin_lat};"
            f"{route_input.destination_lon},{route_input.destination_lat}"
        )
        response = httpx.get(
            f"{self._base_url}/route/v1/{osrm_profile}/{coordinates}",
            params={"overview": "false", "alternatives": "false"},
            timeout=self._timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("code") != "Ok" or not payload.get("routes"):
            raise RoutingNotPossibleError(f"OSRM konnte keine Route berechnen: {payload.get('code')}")

        route = payload["routes"][0]
        return RouteResult(
            origin_lat=route_input.origin_lat,
            origin_lon=route_input.origin_lon,
            destination_lat=route_input.destination_lat,
            destination_lon=route_input.destination_lon,
            distance_km=round(route["distance"] / 1000, 2),
            duration_minutes=round(route["duration"] / 60),
            profile=route_input.profile,
            provider="osrm",
            calculated_at=datetime.now(timezone.utc),
        )


class RoutingNotPossibleError(RuntimeError):
    """Entspricht dem Fehler 'Routing nicht moeglich' aus Abschnitt 14."""
