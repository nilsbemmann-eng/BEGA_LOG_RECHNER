from datetime import date
from decimal import Decimal

import pytest

from app.tariff_engine.engine import (
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
