"""Verwaltung admin-pflegbarer, verschluesselter API-Schluessel fuer externe
Provider (Nutzervorgabe: TomTom-API-Key ueber Admin-Zugang in der App
pflegbar, nicht nur per Umgebungsvariable).

`get_credential_value()` ist die einzige Stelle, die den Klartextwert
zurueckgibt - ausschliesslich fuer den internen Aufruf durch
`app/providers/factory.py`, NIE ueber die API (siehe
`app/api/routers/integration_credentials.py`, das nur meldet OB ein Wert
hinterlegt ist).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models.audit_log import AuditLogEntry
from app.models.integration_credential import IntegrationCredential
from app.services.credential_encryption import (
    CredentialDecryptionError,
    CredentialEncryptionNotConfiguredError,
    decrypt_credential,
    encrypt_credential,
)

CREDENTIAL_KEY_TOMTOM_API_KEY = "tomtom_api_key"

# Bekannte, ueber die API pflegbare Schluessel (Nutzervorgabe: erstmal nur
# TomTom - bei Bedarf erweiterbar, ohne das Datenmodell zu aendern).
KNOWN_CREDENTIAL_KEYS = (CREDENTIAL_KEY_TOMTOM_API_KEY,)


@dataclass
class CredentialStatus:
    credential_key: str
    is_configured: bool
    updated_at: datetime | None
    updated_by: str | None


def set_credential(db: Session, settings: Settings, credential_key: str, plaintext_value: str, updated_by_user_id: str | None) -> IntegrationCredential:
    if not settings.credential_encryption_key:
        raise CredentialEncryptionNotConfiguredError(
            "CREDENTIAL_ENCRYPTION_KEY ist nicht konfiguriert - admin-pflegbare Zugangsdaten "
            "koennen ohne diesen Verschluesselungsschluessel nicht sicher gespeichert werden."
        )

    encrypted_value = encrypt_credential(plaintext_value, settings.credential_encryption_key)
    credential = db.execute(
        select(IntegrationCredential).where(IntegrationCredential.credential_key == credential_key)
    ).scalars().first()

    if credential is None:
        credential = IntegrationCredential(credential_key=credential_key, encrypted_value=encrypted_value)
        db.add(credential)
    else:
        credential.encrypted_value = encrypted_value
    credential.updated_by = updated_by_user_id
    db.flush()

    # Nie den Klartextwert protokollieren - nur, DASS und von WEM er geaendert wurde.
    db.add(AuditLogEntry(
        user_id=updated_by_user_id, entity_type="IntegrationCredential", entity_id=credential.id,
        action="update_credential", new_value_json={"credential_key": credential_key},
    ))
    return credential


def delete_credential(db: Session, credential_key: str, deleted_by_user_id: str | None) -> bool:
    credential = db.execute(
        select(IntegrationCredential).where(IntegrationCredential.credential_key == credential_key)
    ).scalars().first()
    if credential is None:
        return False
    db.add(AuditLogEntry(
        user_id=deleted_by_user_id, entity_type="IntegrationCredential", entity_id=credential.id,
        action="delete_credential", old_value_json={"credential_key": credential_key},
    ))
    db.delete(credential)
    db.flush()
    return True


def get_credential_status(db: Session, credential_key: str) -> CredentialStatus:
    credential = db.execute(
        select(IntegrationCredential).where(IntegrationCredential.credential_key == credential_key)
    ).scalars().first()
    if credential is None:
        return CredentialStatus(credential_key=credential_key, is_configured=False, updated_at=None, updated_by=None)
    return CredentialStatus(
        credential_key=credential_key, is_configured=True,
        updated_at=credential.updated_at, updated_by=credential.updated_by,
    )


def get_credential_value(db: Session, settings: Settings, credential_key: str) -> str | None:
    """Klartextwert fuer den internen Gebrauch (Provider-Factory). Faellt auf
    `None` zurueck (nie eine Exception), wenn kein DB-Wert hinterlegt oder die
    Entschluesselung nicht moeglich ist - Aufrufer entscheiden selbst ueber
    einen Fallback (z. B. Bootstrap-Umgebungsvariable)."""
    credential = db.execute(
        select(IntegrationCredential).where(IntegrationCredential.credential_key == credential_key)
    ).scalars().first()
    if credential is None or not settings.credential_encryption_key:
        return None
    try:
        return decrypt_credential(credential.encrypted_value, settings.credential_encryption_key)
    except CredentialDecryptionError:
        return None
