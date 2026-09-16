"""Deterministische Tarif-Engine (Abschnitt 6).

Framework-unabhaengig (keine SQLAlchemy-Modelle) und ausschliesslich mit
`Decimal` (Abschnitt 6.3: keine binaeren Gleitkommazahlen fuer Geldbetraege).
Der Service-Layer wandelt ORM-`Tariff`/`TariffRule`-Objekte in `TariffDTO`
um und ruft diese Funktionen auf.

Im MVP wird ausschliesslich der Regeltyp `base_plus_km` berechnet. Alle
weiteren in `TariffRuleType` vorbereiteten Regeltypen loesen bewusst
`UnsupportedTariffRuleError` aus, statt eine falsche Berechnung
vorzutaeuschen (siehe docs/OFFENE_ENTSCHEIDUNGEN.md, Punkt 4).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.money import round_money, to_decimal


class TariffNotFoundError(Exception):
    """Kein zum Transportdatum gueltiger, freigegebener Tarif gefunden (Abschnitt 14)."""


class MultipleTariffsValidError(Exception):
    """Mehr als ein Tarif ist zum Transportdatum gueltig (Abschnitt 14)."""

    def __init__(self, tariff_ids: list[str]) -> None:
        self.tariff_ids = tariff_ids
        super().__init__(f"Mehrere gueltige Tarife gefunden: {tariff_ids}")


class UnsupportedTariffRuleError(Exception):
    """Der Regeltyp ist im Datenmodell vorbereitet, aber im MVP nicht berechenbar."""


@dataclass
class TariffRuleDTO:
    rule_type: str
    parameters: dict


@dataclass
class TariffDTO:
    id: str
    valid_from: date
    valid_to: date | None
    status: str
    rules: list[TariffRuleDTO]


@dataclass
class ExpectedPriceBreakdown:
    tariff_id: str
    base_amount: Decimal
    billable_km: Decimal
    km_amount: Decimal
    surcharge_amount: Decimal
    total_amount: Decimal


def select_applicable_tariff(tariffs: list[TariffDTO], transport_date: date, carrier_id: str | None = None) -> TariffDTO:
    """Waehlt den zum Transportdatum gueltigen, freigegebenen Tarif (Abschnitt 8.1: "Tarif").

    `tariffs` muss bereits auf den betreffenden Frachtfuehrer gefiltert sein
    (Filterung nach `carrier_id` liegt beim Aufrufer/Service-Layer, da die
    Zuordnung Frachtfuehrer<->Tarif ueber die Datenbank erfolgt).
    """
    candidates = [
        tariff
        for tariff in tariffs
        if tariff.status == "released"
        and tariff.valid_from <= transport_date
        and (tariff.valid_to is None or transport_date <= tariff.valid_to)
    ]

    if not candidates:
        raise TariffNotFoundError(
            f"Kein gueltiger, freigegebener Tarif fuer Transportdatum {transport_date}"
            + (f" und Frachtfuehrer {carrier_id}" if carrier_id else "")
        )
    if len(candidates) > 1:
        raise MultipleTariffsValidError([tariff.id for tariff in candidates])
    return candidates[0]


def _find_rule(tariff: TariffDTO, rule_type: str) -> TariffRuleDTO | None:
    matching = [rule for rule in tariff.rules if rule.rule_type == rule_type]
    return matching[0] if matching else None


def calculate_expected_price(
    tariff: TariffDTO, reference_km: Decimal, allowed_surcharge_total: Decimal = Decimal("0")
) -> ExpectedPriceBreakdown:
    """Grundformel aus Abschnitt 6.3:

        Abrechnungs-km = max(Referenz-km, Mindest-km)
        Netto-Sollpreis = Grundpreis + Abrechnungs-km * Kilometerpreis + zulaessige Zusatzfrachten
    """
    rule = _find_rule(tariff, "base_plus_km")
    if rule is None:
        raise UnsupportedTariffRuleError(
            f"Tarif {tariff.id} enthaelt keine 'base_plus_km'-Regel und keinen anderen im MVP "
            "unterstuetzten Regeltyp."
        )

    base_price = to_decimal(rule.parameters["base_price"])
    price_per_km = to_decimal(rule.parameters["price_per_km"])
    minimum_km = to_decimal(rule.parameters.get("minimum_km", "0"))

    billable_km = max(reference_km, minimum_km)
    km_amount = billable_km * price_per_km
    total = base_price + km_amount + allowed_surcharge_total

    return ExpectedPriceBreakdown(
        tariff_id=tariff.id,
        base_amount=round_money(base_price),
        billable_km=billable_km,
        km_amount=round_money(km_amount),
        surcharge_amount=round_money(allowed_surcharge_total),
        total_amount=round_money(total),
    )


@dataclass
class PriceDeviation:
    difference_amount: Decimal
    difference_percent: Decimal


def calculate_price_deviation(invoiced_amount: Decimal, expected_amount: Decimal) -> PriceDeviation:
    """Abschnitt 6.4: Preisabweichung = Rechnungsbetrag - Sollpreis."""
    if expected_amount == 0:
        raise ValueError("Sollpreis darf nicht 0 sein")
    difference_amount = invoiced_amount - expected_amount
    difference_percent = difference_amount / expected_amount * 100
    return PriceDeviation(
        difference_amount=round_money(difference_amount),
        difference_percent=difference_percent,
    )
