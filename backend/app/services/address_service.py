"""Adressverifizierung und Geocoding (Abschnitt 5.1)."""
from __future__ import annotations

from app.errors import AddressNotGeocodableError
from app.models.address import Address
from app.providers.base import GeocodeInput, GeocodingProvider

# Nur bis zu dieser Praezisionsstufe gilt eine Adresse als ausreichend genau
# geocodiert (Abschnitt 5.1: "nur auf Orts- oder Postleitzahlebene gefunden").
_INSUFFICIENT_PRECISIONS = {"city", "postal_code", "unknown", None}


def geocode_address_if_needed(address: Address, provider: GeocodingProvider) -> Address:
    if address.latitude is not None and address.longitude is not None:
        return address

    result = provider.geocode(GeocodeInput(address_text=address.original_text, country_hint=address.country_code))

    if not result.matched:
        raise AddressNotGeocodableError(
            f"Adresse konnte nicht geocodiert werden: '{address.original_text}'",
            entity_type="Address", entity_id=address.id,
        )

    address.latitude = result.latitude
    address.longitude = result.longitude
    address.geocoding_provider = result.provider
    address.geocoding_confidence = result.confidence
    address.geocoding_precision = result.precision
    if result.normalized_address:
        address.city = address.city or None
    if result.country_code:
        address.country_code = result.country_code
    return address


def is_precisely_geocoded(address: Address) -> bool:
    return (
        address.latitude is not None
        and address.longitude is not None
        and address.geocoding_precision not in _INSUFFICIENT_PRECISIONS
    )
