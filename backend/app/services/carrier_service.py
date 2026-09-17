"""Gemeinsame Spediteur(Carrier)-Logik: manuelle Erfassung
(`app/api/routers/carriers.py`) und automatisches Anlegen beim
Preistabellen-Import (`app/services/carrier_rate_import_service.py`) nutzen
denselben eindeutigen `carrier_code`-Generator, damit ein manuell erfasster
Spediteur beim naechsten Excel-Import ueber `Carrier.name` wiedererkannt statt
doppelt angelegt wird."""
from __future__ import annotations

import re
import unicodedata

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.party import Carrier


def slugify_carrier_code(name: str) -> str:
    normalized = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^A-Za-z0-9]+", "-", normalized).strip("-").upper()
    return slug or "CARRIER"


def generate_unique_carrier_code(db: Session, name: str) -> str:
    base_code = slugify_carrier_code(name)
    code = base_code
    suffix = 1
    while db.execute(select(Carrier).where(Carrier.carrier_code == code)).scalars().first() is not None:
        suffix += 1
        code = f"{base_code}-{suffix}"
    return code


def find_or_create_carrier(db: Session, name: str) -> Carrier:
    carrier = db.execute(select(Carrier).where(Carrier.name == name)).scalars().first()
    if carrier is not None:
        return carrier

    carrier = Carrier(name=name, carrier_code=generate_unique_carrier_code(db, name))
    db.add(carrier)
    db.flush()
    return carrier
