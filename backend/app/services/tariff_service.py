"""Bindeglied zwischen ORM-`Tariff`/`TariffRule` und der framework-unabhaengigen
Tarif-Engine (`app/tariff_engine/engine.py`)."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.tariff import Tariff
from app.tariff_engine.engine import (
    ExpectedPriceBreakdown,
    TariffDTO,
    TariffRuleDTO,
    calculate_expected_price,
    select_applicable_tariff,
)


def _to_dto(tariff: Tariff) -> TariffDTO:
    return TariffDTO(
        id=tariff.id,
        valid_from=tariff.valid_from,
        valid_to=tariff.valid_to,
        status=tariff.status.value,
        rules=[TariffRuleDTO(rule_type=rule.rule_type.value, parameters=rule.parameters_json) for rule in tariff.rules],
    )


def select_tariff_for_shipment(db: Session, carrier_id: str | None, transport_date: date) -> Tariff:
    query = select(Tariff)
    if carrier_id:
        query = query.where(Tariff.carrier_id == carrier_id)
    orm_tariffs = db.execute(query).scalars().all()

    dtos = [_to_dto(t) for t in orm_tariffs]
    selected_dto = select_applicable_tariff(dtos, transport_date, carrier_id)
    return next(t for t in orm_tariffs if t.id == selected_dto.id)


def calculate_expected_price_for_tariff(
    tariff: Tariff,
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
    return calculate_expected_price(
        _to_dto(tariff),
        reference_km,
        allowed_surcharge_total,
        origin_country=origin_country,
        destination_country=destination_country,
        unloading_point_count=unloading_point_count,
        default_additional_unloading_point_price=default_additional_unloading_point_price,
        tour_number_prefix=tour_number_prefix,
        toll_km=toll_km,
        toll_rate_per_km=toll_rate_per_km,
        special_agreement_surcharge=special_agreement_surcharge,
        use_fixed_freight=use_fixed_freight,
        round_total_up_to_whole_unit=round_total_up_to_whole_unit,
    )
