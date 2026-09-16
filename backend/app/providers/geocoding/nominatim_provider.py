"""`GeocodingProvider`-Implementierung auf Basis von OpenStreetMap Nominatim.

Beachtet die Nominatim-Nutzungsrichtlinien: eindeutiger `User-Agent`,
maximal eine Anfrage pro Sekunde (siehe `_MIN_INTERVAL_SECONDS`). Fuer
produktiven Einsatz mit hoeherem Volumen ist ein selbst gehosteter
Nominatim-Server oder ein kommerzieller OSM-basierter Dienst vorzusehen
(Abschnitt 5.2).
"""
from __future__ import annotations

import time

import httpx

from app.providers.base import GeocodeInput, GeocodeResult

_MIN_INTERVAL_SECONDS = 1.0

# Nominatim liefert eine `type`/`class`-Kombination, aus der sich die
# Praezision der Trefferauswahl ableiten laesst (Abschnitt 5.1).
_PRECISION_BY_OSM_TYPE = {
    "house": "rooftop",
    "building": "rooftop",
    "residential": "street",
    "road": "street",
    "postcode": "postal_code",
    "city": "city",
    "town": "city",
    "village": "city",
    "administrative": "city",
}


class NominatimGeocodingProvider:
    def __init__(self, base_url: str, user_agent: str, timeout_seconds: float = 10.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._user_agent = user_agent
        self._timeout_seconds = timeout_seconds
        self._last_request_at: float = 0.0

    def _respect_rate_limit(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < _MIN_INTERVAL_SECONDS:
            time.sleep(_MIN_INTERVAL_SECONDS - elapsed)
        self._last_request_at = time.monotonic()

    def geocode(self, request: GeocodeInput) -> GeocodeResult:
        self._respect_rate_limit()
        params = {
            "q": request.address_text,
            "format": "jsonv2",
            "addressdetails": 1,
            "limit": 5,
        }
        if request.country_hint:
            params["countrycodes"] = request.country_hint.lower()

        response = httpx.get(
            f"{self._base_url}/search",
            params=params,
            headers={"User-Agent": self._user_agent},
            timeout=self._timeout_seconds,
        )
        response.raise_for_status()
        results = response.json()

        if not results:
            return GeocodeResult(
                matched=False,
                latitude=None,
                longitude=None,
                normalized_address=None,
                country_code=None,
                precision=None,
                confidence=0.0,
                provider="nominatim",
            )

        best = results[0]
        osm_type = best.get("type") or best.get("class") or ""
        precision = _PRECISION_BY_OSM_TYPE.get(osm_type, "unknown")
        importance = float(best.get("importance", 0.5))

        return GeocodeResult(
            matched=True,
            latitude=float(best["lat"]),
            longitude=float(best["lon"]),
            normalized_address=best.get("display_name"),
            country_code=(best.get("address", {}) or {}).get("country_code", "").upper() or None,
            precision=precision,
            confidence=min(importance, 1.0),
            provider="nominatim",
            ambiguous=len(results) > 1,
            candidate_count=len(results),
        )
