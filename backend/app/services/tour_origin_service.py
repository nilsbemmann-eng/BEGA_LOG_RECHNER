"""Verwaltung der "Absender-Matrix" (BEGA-Finetuning, Nutzervorgabe): ordnet
die ersten 2 Ziffern der Ladelistennummer einer Beladeadresse zu, da
Ladelisten selbst keine Beladeadresse enthalten (siehe
`app/services/ladeliste_pdf_parser.py`, docs/OFFENE_ENTSCHEIDUNGEN.md).
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.address import Address
from app.models.tour_origin_mapping import TourOriginMapping

PREFIX_LENGTH = 2


def resolve_tour_origin_address(db: Session, tour_number: str) -> Address | None:
    prefix = tour_number[:PREFIX_LENGTH]
    mapping = db.execute(
        select(TourOriginMapping).where(TourOriginMapping.tour_number_prefix == prefix)
    ).scalars().first()
    return mapping.origin_address if mapping else None
