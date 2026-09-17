"""Deterministische Tarif-Engine (Abschnitt 6).

Framework-unabhaengig (keine SQLAlchemy-Modelle) und ausschliesslich mit
`Decimal` (Abschnitt 6.3: keine binaeren Gleitkommazahlen fuer Geldbetraege).
Der Service-Layer wandelt ORM-`Tariff`/`TariffRule`-Objekte in `TariffDTO`
um und ruft diese Funktionen auf.

Im MVP werden die Regeltypen `base_plus_km` und `all_in` berechnet (Stand:
BEGA-Finetuning, siehe docs/OFFENE_ENTSCHEIDUNGEN.md). Alle weiteren in
`TariffRuleType` vorbereiteten Regeltypen loesen bewusst
`UnsupportedTariffRuleError` aus, statt eine falsche Berechnung
vorzutaeuschen.

BEGA-spezifische Preisregeln (Finetuning-Vorgabe):

- `base_plus_km.parameters.price_per_km_by_country`: optionale Tabelle
  `{"DE": "1.05", "AT": "1.25", ...}`. Sind sowohl Herkunfts- als auch
  Zielland in der Tabelle enthalten, gilt der Satz des teureren Landes.
  Fehlt ein Land in der Tabelle, faellt die Berechnung auf
  `parameters.price_per_km` zurueck.
- `all_in.parameters.prices`: Fixfracht-Preisliste je Laenderpaar
  `[{"origin_country": "DE", "destination_country": "DE", "amount": "350.00"}, ...]`.
  Wird nur verwendet, wenn die Sendung genau 1 Entladestelle hat
  (`unloading_point_count == 1`) und ein passender Eintrag existiert; sonst
  greift `base_plus_km`. Die Zuordnung erfolgt aktuell nur auf Land-Ebene,
  nicht auf PLZ-Zonen-Ebene (dokumentierte MVP-Vereinfachung).
- Ab der 2. Entladestelle faellt pro zusaetzlicher Entladestelle ein fixer
  Zuschlag an (`additional_unloading_point_price`, Tarif-Parameter oder
  globaler Standardwert aus `app/config.py`).

Reale Preisformel aus "Preise_2026_fuer_Wolke.xlsm" (BEGA-Finetuning,
Tour-Preispruefung, siehe docs/OFFENE_ENTSCHEIDUNGEN.md): das tatsaechlich
von BEGA manuell genutzte Excel-Berechnungsblatt enthaelt zusaetzliche
Komponenten, die hier ergaenzt wurden:

- `base_plus_km.parameters.prefix_country_rate_overrides`: Liste
  `[{"tour_number_prefix": "78", "destination_countries": ["DE","DEU","D"],
     "price_per_km": "1.35"}, ...]` - manuell verhandelte Sonder-km-Saetze
  fuer bestimmte Frachtfuehrer+Ladelisten-Praefix+Zielland-Kombinationen,
  die Vorrang vor `price_per_km_by_country` haben (echte Ausnahmen aus dem
  Excel, z. B. PAWLICHA+Praefix 78+Deutschland -> 1,30 EUR/km statt des
  Standardsatzes).
- `base_plus_km.parameters.toll_exempt`: bool, Frachtfuehrer ohne Maut-Kosten
  (im Excel: BABINSKI, SANMAR).
- Maut-Kosten = `toll_km * toll_rate_per_km` (Standard 0,158 EUR/km,
  `Settings.default_toll_rate_per_km_eur`), addiert zum Sollpreis, ausser bei
  `toll_exempt`.
- Sondervereinbarungs-Zuschlag: ein fixer Betrag je Ladelisten-Praefix
  (`SpecialAgreementSurcharge`-Stammdaten, siehe
  `app/services/tour_origin_service.py`), unabhaengig von km/Entladestellen,
  wird als `special_agreement_surcharge`-Parameter uebergeben.
- `use_fixed_freight=False` deaktiviert die `all_in`-Fixfracht-Pruefung
  vollstaendig: die reale Tour-Preisformel kennt keine Fixfracht-Preisliste
  je Laenderpaar, nur den kilometerbasierten Pfad.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.money import round_money, round_up_to_whole_currency_unit, to_decimal


class TariffNotFoundError(Exception):
    """Kein zum Transportdatum gueltiger, freigegebener Tarif gefunden (Abschnitt 14)."""


class MultipleTariffsValidError(Exception):
    """Mehr als ein Tarif ist zum Transportdatum gueltig (Abschnitt 14)."""

    def __init__(self, tariff_ids: list[str]) -> None:
        self.tariff_ids = tariff_ids
        super().__init__(f"Mehrere gueltige Tarife gefunden: {tariff_ids}")


class UnsupportedTariffRuleError(Exception):
    """Der Regeltyp ist im Datenmodell vorbereitet, aber im MVP nicht berechenbar."""


class MissingCountryRateError(Exception):
    """Weder ein laenderspezifischer noch ein Standard-km-Preis ist hinterlegt (Abschnitt 14)."""


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
    price_per_km: Decimal | None
    additional_stops_amount: Decimal
    surcharge_amount: Decimal
    toll_amount: Decimal
    special_agreement_amount: Decimal
    total_amount: Decimal
    pricing_method: str  # "all_in" (Fixfracht) | "base_plus_km"


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


def _resolve_prefix_override_rate(
    rule: TariffRuleDTO, tour_number_prefix: str | None, countries_involved: set[str]
) -> Decimal | None:
    """Manuell verhandelte Sonder-km-Saetze je Praefix+Zielland (siehe
    Moduldocstring: reale Ausnahmen aus dem BEGA-Excel), haben Vorrang vor
    `price_per_km_by_country`."""
    if not tour_number_prefix:
        return None
    for entry in rule.parameters.get("prefix_country_rate_overrides", []):
        if entry.get("tour_number_prefix") != tour_number_prefix:
            continue
        if countries_involved & set(entry.get("destination_countries", [])):
            return to_decimal(entry["price_per_km"])
    return None


def _resolve_price_per_km(
    rule: TariffRuleDTO, countries_involved: set[str], tour_number_prefix: str | None = None
) -> Decimal:
    """Waehlt den km-Preis nach Land (BEGA-Finetuning).

    Prueft zuerst manuelle Praefix+Land-Ausnahmen (`prefix_country_rate_overrides`),
    dann die laenderabhaengige Preistabelle: sind mehrere Laender an der
    Sendung beteiligt (z. B. Herkunfts- und Zielland), gilt der Satz des
    teuersten hinterlegten Landes. Ist kein beteiligtes Land in der Tabelle
    hinterlegt, greift der Standardsatz `price_per_km`.
    """
    override_rate = _resolve_prefix_override_rate(rule, tour_number_prefix, countries_involved)
    if override_rate is not None:
        return override_rate

    rate_table: dict = rule.parameters.get("price_per_km_by_country") or {}
    matched_rates = [to_decimal(rate_table[country]) for country in countries_involved if country in rate_table]

    if matched_rates:
        return max(matched_rates)

    default_rate = rule.parameters.get("price_per_km")
    if default_rate is not None:
        return to_decimal(default_rate)

    raise MissingCountryRateError(
        f"Kein km-Preis fuer die beteiligten Laender {sorted(countries_involved)} hinterlegt "
        "und kein Standardsatz ('price_per_km') im Tarif konfiguriert."
    )


def _find_fixed_freight_amount(rule: TariffRuleDTO, origin_country: str | None, destination_country: str | None) -> Decimal | None:
    """Fixfracht-Nachschlag fuer genau 1 Entladestelle (BEGA-Finetuning).

    Aktuell auf Land-Ebene geschluesselt (kein PLZ-Zonen-Bezug), siehe
    docs/OFFENE_ENTSCHEIDUNGEN.md.
    """
    for entry in rule.parameters.get("prices", []):
        if entry.get("origin_country") == origin_country and entry.get("destination_country") == destination_country:
            return to_decimal(entry["amount"])
    return None


def calculate_expected_price(
    tariff: TariffDTO,
    reference_km: Decimal,
    allowed_surcharge_total: Decimal = Decimal("0"),
    origin_country: str | None = None,
    destination_country: str | None = None,
    unloading_point_count: int = 1,
    default_additional_unloading_point_price: Decimal = Decimal("50"),
    tour_number_prefix: str | None = None,
    toll_km: Decimal = Decimal("0"),
    toll_rate_per_km: Decimal = Decimal("0.158"),
    special_agreement_surcharge: Decimal = Decimal("0"),
    use_fixed_freight: bool = True,
    round_total_up_to_whole_unit: bool = False,
) -> ExpectedPriceBreakdown:
    """Sollpreisberechnung inkl. BEGA-Finetuning (mehrere Entladestellen,
    laenderabhaengiger km-Preis, Fixfracht, Maut, Sondervereinbarung):

        Abrechnungs-km = max(Referenz-km, Mindest-km)
        Basispreis = Fixfracht (bei 1 Entladestelle, falls hinterlegt und
                     use_fixed_freight=True)
                     sonst Grundpreis + Abrechnungs-km * Kilometerpreis(Land/Praefix)
        Netto-Sollpreis = Basispreis
                          + Zuschlag_zusaetzliche_Entladestellen
                          + Maut (toll_km * toll_rate_per_km, ausser toll_exempt)
                          + Sondervereinbarungs-Zuschlag
                          + zulaessige Zusatzfrachten
    """
    additional_stops = max(unloading_point_count - 1, 0)
    countries_involved = {c for c in (origin_country, destination_country) if c}

    base_plus_km_rule = _find_rule(tariff, "base_plus_km")
    fixed_freight_rule = _find_rule(tariff, "all_in")

    fixed_freight_amount = None
    if use_fixed_freight and unloading_point_count == 1 and fixed_freight_rule is not None:
        fixed_freight_amount = _find_fixed_freight_amount(fixed_freight_rule, origin_country, destination_country)

    price_per_km: Decimal | None = None
    if fixed_freight_amount is not None:
        pricing_method = "all_in"
        base_amount = fixed_freight_amount
        billable_km = Decimal("0")
        km_amount = Decimal("0")
    else:
        if base_plus_km_rule is None:
            raise UnsupportedTariffRuleError(
                f"Tarif {tariff.id} enthaelt weder eine passende 'all_in'-Fixfracht noch eine "
                "'base_plus_km'-Regel."
            )
        pricing_method = "base_plus_km"
        base_price = to_decimal(base_plus_km_rule.parameters.get("base_price", "0"))
        minimum_km = to_decimal(base_plus_km_rule.parameters.get("minimum_km", "0"))
        price_per_km = _resolve_price_per_km(base_plus_km_rule, countries_involved, tour_number_prefix)

        billable_km = max(reference_km, minimum_km)
        km_amount = billable_km * price_per_km
        base_amount = base_price

    additional_unloading_point_price = default_additional_unloading_point_price
    toll_exempt = False
    if base_plus_km_rule is not None:
        if "additional_unloading_point_price" in base_plus_km_rule.parameters:
            additional_unloading_point_price = to_decimal(base_plus_km_rule.parameters["additional_unloading_point_price"])
        toll_exempt = bool(base_plus_km_rule.parameters.get("toll_exempt", False))
    additional_stops_amount = additional_unloading_point_price * additional_stops

    toll_amount = Decimal("0") if toll_exempt else (toll_km * toll_rate_per_km)

    total = (
        base_amount
        + km_amount
        + additional_stops_amount
        + toll_amount
        + special_agreement_surcharge
        + allowed_surcharge_total
    )

    total_amount = round_up_to_whole_currency_unit(total) if round_total_up_to_whole_unit else round_money(total)

    return ExpectedPriceBreakdown(
        tariff_id=tariff.id,
        base_amount=round_money(base_amount),
        billable_km=billable_km,
        km_amount=round_money(km_amount),
        price_per_km=price_per_km,
        additional_stops_amount=round_money(additional_stops_amount),
        surcharge_amount=round_money(allowed_surcharge_total),
        toll_amount=round_money(toll_amount),
        special_agreement_amount=round_money(special_agreement_surcharge),
        total_amount=total_amount,
        pricing_method=pricing_method,
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
