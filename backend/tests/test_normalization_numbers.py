from decimal import Decimal

import pytest

from app.normalization.numbers import NumberParsingError, parse_german_decimal


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("1.234,56 EUR", Decimal("1234.56")),
        ("1.240 kg", Decimal("1240")),
        ("12,5 LDM", Decimal("12.5")),
        ("42", Decimal("42")),
        ("-15,30 EUR", Decimal("-15.30")),
        ("1.234.567,89", Decimal("1234567.89")),
    ],
)
def test_parse_german_decimal(raw: str, expected: Decimal) -> None:
    assert parse_german_decimal(raw) == expected


def test_parse_german_decimal_raises_on_no_number() -> None:
    with pytest.raises(NumberParsingError):
        parse_german_decimal("kein wert")
