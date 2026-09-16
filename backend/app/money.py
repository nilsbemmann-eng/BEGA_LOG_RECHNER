"""Geld- und Mengenwerte werden ausschliesslich als `Decimal` verarbeitet.

Abschnitt 6.3 des technischen Berichts verbietet binaere Gleitkommazahlen
(`float`) fuer Rechnungsbetraege. `Money` ist ein Alias fuer `Decimal`, der an
allen Stellen verwendet wird, an denen Geld- oder Mengenwerte durch das System
fliessen (Datenbankspalten, Engines, API-Schemas).
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

Money = Decimal

TWO_PLACES = Decimal("0.01")


def round_money(value: Decimal) -> Decimal:
    """Rundet kaufmaennisch auf zwei Nachkommastellen (EUR-Cent-Genauigkeit)."""
    return value.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def to_decimal(value: str | float | int | Decimal) -> Decimal:
    """Wandelt einen Wert sicher in `Decimal` um, ohne den `float`-Umweg fuer Strings."""
    if isinstance(value, Decimal):
        return value
    if isinstance(value, str):
        return Decimal(value)
    return Decimal(str(value))
