"""Verwaltung der "Absender-Matrix"/"Gebietsrelationen" (BEGA-Finetuning,
Nutzervorgabe): ordnet Matchcodes/Praefixe der Ladelistennummer einer
Beladeadresse zu, da Ladelisten selbst keine Beladeadresse enthalten (siehe
`app/services/ladeliste_pdf_parser.py`, docs/OFFENE_ENTSCHEIDUNGEN.md).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from decimal import Decimal

from app.models.address import Address
from app.models.special_agreement_surcharge import SpecialAgreementSurcharge
from app.models.tour_origin_mapping import TourOriginMapping

PREFIX_LENGTH = 2


@dataclass
class OriginResolution:
    address: Address | None
    # Bei mehreren Matchcodes mit unterschiedlichen Adressen fuer denselben
    # Praefix (real vorkommend, siehe Gebietsrelationen.xlsx) bleibt die
    # Aufloesung bewusst offen (Nutzervorgabe: "Bei Mehrdeutigkeit: manuelle
    # Pruefung") - hier werden die widerspruechlichen Matchcodes fuer die
    # Pruefbegruendung mitgegeben.
    ambiguous_matchcodes: list[str] = field(default_factory=list)


def _address_identity(address: Address) -> tuple:
    return (address.country_code, address.postal_code, address.city, address.street)


def resolve_tour_origin_address(db: Session, tour_number: str) -> OriginResolution:
    prefix = tour_number[:PREFIX_LENGTH]
    mappings = db.execute(
        select(TourOriginMapping).where(TourOriginMapping.tour_number_prefix == prefix)
    ).scalars().all()

    candidates = [m for m in mappings if m.origin_address is not None]
    if not candidates:
        return OriginResolution(address=None)

    distinct_addresses: dict[tuple, TourOriginMapping] = {}
    for mapping in candidates:
        distinct_addresses.setdefault(_address_identity(mapping.origin_address), mapping)

    if len(distinct_addresses) == 1:
        resolved_mapping = next(iter(distinct_addresses.values()))
        return OriginResolution(address=resolved_mapping.origin_address)

    return OriginResolution(
        address=None,
        ambiguous_matchcodes=sorted({m.matchcode for m in candidates}),
    )


def resolve_special_agreement_surcharge(db: Session, tour_number: str) -> Decimal:
    """"Sondervereinbarungen"-Zuschlag (reale BEGA-Preisformel, siehe
    `app/models/special_agreement_surcharge.py`) - 0, wenn fuer den Praefix
    kein Zuschlag hinterlegt ist."""
    prefix = tour_number[:PREFIX_LENGTH]
    surcharge = db.execute(
        select(SpecialAgreementSurcharge).where(SpecialAgreementSurcharge.tour_number_prefix == prefix)
    ).scalars().first()
    return surcharge.amount if surcharge else Decimal("0")
