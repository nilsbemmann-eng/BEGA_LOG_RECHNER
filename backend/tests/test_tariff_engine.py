from datetime import date
from decimal import Decimal

import pytest

from app.tariff_engine.engine import (
    MissingCountryRateError,
    MultipleTariffsValidError,
    TariffDTO,
    TariffNotFoundError,
    TariffRuleDTO,
    UnsupportedTariffRuleError,
    calculate_expected_price,
    calculate_price_deviation,
    select_applicable_tariff,
)


def _base_plus_km_tariff(tariff_id: str = "t1", valid_from=date(2026, 1, 1), valid_to=None) -> TariffDTO:
    return TariffDTO(
        id=tariff_id,
        valid_from=valid_from,
        valid_to=valid_to,
        status="released",
        rules=[TariffRuleDTO(rule_type="base_plus_km", parameters={"base_price": "150.00", "price_per_km": "1.05", "minimum_km": "50"})],
    )


def test_select_applicable_tariff_returns_single_match() -> None:
    tariff = _base_plus_km_tariff()
    selected = select_applicable_tariff([tariff], date(2026, 6, 1))
    assert selected.id == "t1"


def test_select_applicable_tariff_raises_not_found() -> None:
    tariff = _base_plus_km_tariff(valid_from=date(2027, 1, 1))
    with pytest.raises(TariffNotFoundError):
        select_applicable_tariff([tariff], date(2026, 6, 1))


def test_select_applicable_tariff_raises_on_multiple_matches() -> None:
    t1 = _base_plus_km_tariff("t1")
    t2 = _base_plus_km_tariff("t2")
    with pytest.raises(MultipleTariffsValidError):
        select_applicable_tariff([t1, t2], date(2026, 6, 1))


def test_calculate_expected_price_from_report_example() -> None:
    # Nachgestelltes Beispiel angelehnt an Abschnitt 8.3 (Sollpreis 1.184,00 EUR
    # bei 542 Referenz-km), mit glatten Tarifparametern.
    tariff = TariffDTO(
        id="t1", valid_from=date(2026, 1, 1), valid_to=None, status="released",
        rules=[TariffRuleDTO(rule_type="base_plus_km", parameters={"base_price": "100.00", "price_per_km": "2.00", "minimum_km": "0"})],
    )
    breakdown = calculate_expected_price(tariff, reference_km=Decimal("542"))
    assert breakdown.total_amount == Decimal("1184.00")


def test_calculate_expected_price_applies_minimum_km() -> None:
    tariff = _base_plus_km_tariff()
    breakdown = calculate_expected_price(tariff, reference_km=Decimal("10"))
    assert breakdown.billable_km == Decimal("50")
    assert breakdown.total_amount == Decimal("202.50")


def test_calculate_expected_price_adds_surcharges() -> None:
    tariff = _base_plus_km_tariff()
    breakdown = calculate_expected_price(tariff, reference_km=Decimal("100"), allowed_surcharge_total=Decimal("72.00"))
    assert breakdown.total_amount == Decimal("327.00")


def test_calculate_expected_price_raises_for_unsupported_rule_type() -> None:
    tariff = TariffDTO(id="t1", valid_from=date(2026, 1, 1), valid_to=None, status="released", rules=[TariffRuleDTO(rule_type="zone", parameters={})])
    with pytest.raises(UnsupportedTariffRuleError):
        calculate_expected_price(tariff, reference_km=Decimal("100"))


def test_calculate_price_deviation_from_report_example() -> None:
    deviation = calculate_price_deviation(invoiced_amount=Decimal("1436.00"), expected_amount=Decimal("1184.00"))
    assert deviation.difference_amount == Decimal("252.00")
    assert round(deviation.difference_percent, 1) == Decimal("21.3")


# --- BEGA-Finetuning: laenderabhaengiger km-Preis, Fixfracht, Mehrfach-Entladestellen ---


def _country_priced_tariff() -> TariffDTO:
    return TariffDTO(
        id="t1", valid_from=date(2026, 1, 1), valid_to=None, status="released",
        rules=[
            TariffRuleDTO(
                rule_type="base_plus_km",
                parameters={
                    "base_price": "0.00",
                    "price_per_km": "1.00",
                    "price_per_km_by_country": {"DE": "1.00", "AT": "1.50", "FR": "1.20"},
                    "minimum_km": "0",
                },
            )
        ],
    )


def test_km_price_uses_rate_of_most_expensive_involved_country() -> None:
    tariff = _country_priced_tariff()
    breakdown = calculate_expected_price(
        tariff, reference_km=Decimal("100"), origin_country="DE", destination_country="AT"
    )
    # teuerstes beteiligtes Land (AT, 1.50 EUR/km) gewinnt, nicht das Herkunftsland
    assert breakdown.price_per_km == Decimal("1.50")
    assert breakdown.total_amount == Decimal("150.00")


def test_km_price_falls_back_to_default_when_country_unknown() -> None:
    tariff = _country_priced_tariff()
    breakdown = calculate_expected_price(
        tariff, reference_km=Decimal("100"), origin_country="CH", destination_country="CH"
    )
    assert breakdown.price_per_km == Decimal("1.00")


def test_km_price_raises_when_no_country_rate_and_no_default() -> None:
    tariff = TariffDTO(
        id="t1", valid_from=date(2026, 1, 1), valid_to=None, status="released",
        rules=[TariffRuleDTO(rule_type="base_plus_km", parameters={"base_price": "0.00", "price_per_km_by_country": {"DE": "1.00"}})],
    )
    with pytest.raises(MissingCountryRateError):
        calculate_expected_price(tariff, reference_km=Decimal("100"), origin_country="CH", destination_country="CH")


def _fixed_freight_tariff() -> TariffDTO:
    return TariffDTO(
        id="t1", valid_from=date(2026, 1, 1), valid_to=None, status="released",
        rules=[
            TariffRuleDTO(
                rule_type="all_in",
                parameters={"prices": [{"origin_country": "DE", "destination_country": "DE", "amount": "350.00"}]},
            ),
            TariffRuleDTO(rule_type="base_plus_km", parameters={"base_price": "0.00", "price_per_km": "2.00"}),
        ],
    )


def test_fixed_freight_used_for_single_unloading_point_with_matching_relation() -> None:
    tariff = _fixed_freight_tariff()
    breakdown = calculate_expected_price(
        tariff, reference_km=Decimal("999"), origin_country="DE", destination_country="DE", unloading_point_count=1
    )
    assert breakdown.pricing_method == "all_in"
    assert breakdown.total_amount == Decimal("350.00")


def test_fixed_freight_ignored_when_relation_not_listed_falls_back_to_km() -> None:
    tariff = _fixed_freight_tariff()
    breakdown = calculate_expected_price(
        tariff, reference_km=Decimal("100"), origin_country="DE", destination_country="FR", unloading_point_count=1
    )
    assert breakdown.pricing_method == "base_plus_km"
    assert breakdown.total_amount == Decimal("200.00")


def test_fixed_freight_not_used_when_multiple_unloading_points() -> None:
    tariff = _fixed_freight_tariff()
    breakdown = calculate_expected_price(
        tariff, reference_km=Decimal("100"), origin_country="DE", destination_country="DE", unloading_point_count=2
    )
    assert breakdown.pricing_method == "base_plus_km"


def test_additional_unloading_points_add_default_surcharge() -> None:
    tariff = _base_plus_km_tariff()  # base 150, 1.05/km, min 50 km
    breakdown = calculate_expected_price(
        tariff, reference_km=Decimal("50"), unloading_point_count=3, default_additional_unloading_point_price=Decimal("50")
    )
    # Grundpreis 150 + 50km*1.05=52.50 + 2 zusaetzliche Entladestellen * 50 EUR
    assert breakdown.additional_stops_amount == Decimal("100.00")
    assert breakdown.total_amount == Decimal("302.50")


def test_tariff_specific_additional_unloading_point_price_overrides_default() -> None:
    tariff = TariffDTO(
        id="t1", valid_from=date(2026, 1, 1), valid_to=None, status="released",
        rules=[
            TariffRuleDTO(
                rule_type="base_plus_km",
                parameters={"base_price": "0.00", "price_per_km": "1.00", "additional_unloading_point_price": "75.00"},
            )
        ],
    )
    breakdown = calculate_expected_price(
        tariff, reference_km=Decimal("100"), unloading_point_count=2, default_additional_unloading_point_price=Decimal("50")
    )
    assert breakdown.additional_stops_amount == Decimal("75.00")
