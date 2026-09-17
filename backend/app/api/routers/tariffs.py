from __future__ import annotations

from fastapi import APIRouter, Depends, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_role
from app.database import get_db
from app.errors import CarrierRateMatrixImportFailedError, UnsupportedFileFormatError
from app.models.tariff import Tariff, TariffRule, TariffRuleType, TariffStatus
from app.models.user import User, UserRole
from app.schemas import CarrierRateMatrixImportResult, TariffCreate, TariffOut
from app.services.carrier_rate_import_service import CarrierRateMatrixParsingError, import_carrier_rate_matrix

router = APIRouter(prefix="/api/tariffs", tags=["tariffs"], dependencies=[Depends(get_current_user)])

_MANAGE_ROLES = (UserRole.ADMIN, UserRole.PREISADMIN)


@router.get("", response_model=list[TariffOut])
def list_tariffs(db: Session = Depends(get_db)) -> list[Tariff]:
    return list(db.execute(select(Tariff)).scalars().all())


@router.post("", response_model=TariffOut, status_code=201)
def create_tariff(
    request: TariffCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*_MANAGE_ROLES)),
) -> Tariff:
    """Tarife anlegen ist Administrator-Aufgabe (Abschnitt 3.1). Jeder Tarif ist
    unveraenderlich: Aenderungen erfordern einen neuen Datensatz (Abschnitt 6.2)."""
    tariff = Tariff(
        tariff_code=request.tariff_code,
        name=request.name,
        carrier_id=request.carrier_id,
        valid_from=request.valid_from,
        valid_to=request.valid_to,
        currency=request.currency,
        status=TariffStatus.RELEASED,
        version=1,
        created_by=current_user.id,
        rules=[
            TariffRule(rule_type=TariffRuleType(rule.rule_type), parameters_json=rule.parameters, priority=rule.priority)
            for rule in request.rules
        ],
    )
    db.add(tariff)
    db.commit()
    db.refresh(tariff)
    return tariff


@router.post("/import-rate-matrix", response_model=CarrierRateMatrixImportResult)
async def import_carrier_rate_matrix_endpoint(
    file: UploadFile,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_role(*_MANAGE_ROLES)),
) -> CarrierRateMatrixImportResult:
    """Importiert die reale Frachtfuehrer-Preistabelle ("Stammdaten"-Blatt aus
    "Preise_2026_fuer_Wolke.xlsm", BEGA-Finetuning): legt fuer jeden Frachtfuehrer
    mit mindestens einem gueltigen km-Satz eine neue Tarifversion an (siehe
    app/services/carrier_rate_import_service.py)."""
    if not file.filename or not file.filename.lower().endswith((".xlsm", ".xlsx")):
        raise UnsupportedFileFormatError(
            f"Nicht unterstuetztes Dateiformat fuer die Preistabelle: '{file.filename}'. Erlaubt: .xlsm, .xlsx"
        )
    content = await file.read()
    try:
        imported_count = import_carrier_rate_matrix(db, content)
    except CarrierRateMatrixParsingError as exc:
        raise CarrierRateMatrixImportFailedError(str(exc)) from exc
    db.commit()
    return CarrierRateMatrixImportResult(imported_count=imported_count)
