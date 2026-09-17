"""Admin-pflegbare, verschluesselte API-Schluessel fuer externe Provider
(Nutzervorgabe: TomTom-API-Key ueber Admin-Zugang in der App pflegbar).

Der Klartextwert wird ueber diese API NIE zurueckgegeben - nur, ob und wann
ein Wert hinterlegt wurde (siehe
`app/services/integration_credential_service.py`)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_role
from app.config import Settings, get_settings
from app.database import get_db
from app.errors import CredentialEncryptionNotConfiguredApiError
from app.models.user import User, UserRole
from app.schemas import IntegrationCredentialSetRequest, IntegrationCredentialStatusOut
from app.services.credential_encryption import CredentialEncryptionNotConfiguredError
from app.services.integration_credential_service import (
    KNOWN_CREDENTIAL_KEYS,
    delete_credential,
    get_credential_status,
    set_credential,
)

router = APIRouter(prefix="/api/integration-credentials", tags=["integration-credentials"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[IntegrationCredentialStatusOut])
def list_integration_credentials(
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_role(UserRole.ADMIN)),
) -> list[IntegrationCredentialStatusOut]:
    return [
        IntegrationCredentialStatusOut(**vars(get_credential_status(db, key)))
        for key in KNOWN_CREDENTIAL_KEYS
    ]


@router.put("/{credential_key}", response_model=IntegrationCredentialStatusOut)
def set_integration_credential(
    credential_key: str,
    request: IntegrationCredentialSetRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
) -> IntegrationCredentialStatusOut:
    try:
        set_credential(db, settings, credential_key, request.value, current_user.id)
    except CredentialEncryptionNotConfiguredError as exc:
        raise CredentialEncryptionNotConfiguredApiError(str(exc)) from exc
    db.commit()
    return IntegrationCredentialStatusOut(**vars(get_credential_status(db, credential_key)))


@router.delete("/{credential_key}", status_code=204, response_model=None)
def delete_integration_credential(
    credential_key: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
) -> None:
    delete_credential(db, credential_key, current_user.id)
    db.commit()
