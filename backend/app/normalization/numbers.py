"""Normalisierung deutscher Zahlenformate (Abschnitt 4.4).

Im deutschen Format ist das Komma das Dezimaltrennzeichen und der Punkt das
Tausendertrennzeichen - umgekehrt zum englischen Format. Diese Funktionen
wandeln OCR-Rohwerte in `Decimal` um, niemals in `float`
(siehe `app/money.py`).

Beispiele aus Abschnitt 4.4:
    "1.234,56 EUR" -> Decimal("1234.56")
    "1.240 kg"     -> Decimal("1240")
    "12,5 LDM"     -> Decimal("12.5")
"""
from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

_NUMBER_RE = re.compile(r"-?\d[\d.,]*")


class NumberParsingError(ValueError):
    """Wird geworfen, wenn kein Zahlenwert aus dem Rohtext extrahiert werden kann."""


def parse_german_decimal(raw: str) -> Decimal:
    """Extrahiert einen Dezimalwert aus einem deutschsprachigen Rohtext.

    Die Funktion ist bewusst tolerant gegenueber angehaengten Einheiten oder
    Waehrungssymbolen (z. B. "kg", "EUR", "LDM", "%"), da OCR-Rohwerte diese
    haeufig enthalten.
    """
    if raw is None:
        raise NumberParsingError("Kein Wert zum Parsen vorhanden")

    match = _NUMBER_RE.search(raw.strip())
    if not match:
        raise NumberParsingError(f"Kein Zahlenwert in '{raw}' gefunden")

    number_str = match.group(0)
    has_comma = "," in number_str
    has_dot = "." in number_str

    if has_comma:
        integer_part, _, fractional_part = number_str.rpartition(",")
        integer_part = integer_part.replace(".", "") or "0"
        normalized = f"{integer_part}.{fractional_part}"
    elif has_dot:
        groups = number_str.split(".")
        looks_like_thousands_grouping = len(groups) > 2 or (len(groups) == 2 and len(groups[1]) == 3)
        normalized = number_str.replace(".", "") if looks_like_thousands_grouping else number_str
    else:
        normalized = number_str

    try:
        return Decimal(normalized)
    except InvalidOperation as exc:
        raise NumberParsingError(f"'{raw}' konnte nicht als Zahl interpretiert werden") from exc


def parse_german_weight_kg(raw: str) -> Decimal:
    return parse_german_decimal(raw)


def parse_german_loading_meters(raw: str) -> Decimal:
    return parse_german_decimal(raw)


def parse_german_currency_amount(raw: str) -> Decimal:
    return parse_german_decimal(raw)
