import pytest
from cryptography.fernet import Fernet

from app.config import Settings
from app.models.audit_log import AuditLogEntry
from app.models.user import User, UserRole
from app.services.credential_encryption import CredentialEncryptionNotConfiguredError
from app.services.integration_credential_service import (
    CREDENTIAL_KEY_TOMTOM_API_KEY,
    delete_credential,
    get_credential_status,
    get_credential_value,
    set_credential,
)


def _settings(encryption_key: str | None) -> Settings:
    return Settings(database_url="sqlite:///:memory:", credential_encryption_key=encryption_key)


def _admin(db_session) -> User:
    admin = User(name="Admin", email="admin@example.invalid", role=UserRole.ADMIN, active=True)
    db_session.add(admin)
    db_session.flush()
    return admin


def test_set_and_get_credential_round_trips(db_session):
    key = Fernet.generate_key().decode()
    admin = _admin(db_session)

    set_credential(db_session, _settings(key), CREDENTIAL_KEY_TOMTOM_API_KEY, "tomtom-secret", admin.id)
    db_session.commit()

    value = get_credential_value(db_session, _settings(key), CREDENTIAL_KEY_TOMTOM_API_KEY)
    assert value == "tomtom-secret"


def test_set_credential_without_encryption_key_raises(db_session):
    admin = _admin(db_session)
    with pytest.raises(CredentialEncryptionNotConfiguredError):
        set_credential(db_session, _settings(None), CREDENTIAL_KEY_TOMTOM_API_KEY, "tomtom-secret", admin.id)


def test_get_credential_value_returns_none_without_encryption_key(db_session):
    key = Fernet.generate_key().decode()
    admin = _admin(db_session)
    set_credential(db_session, _settings(key), CREDENTIAL_KEY_TOMTOM_API_KEY, "tomtom-secret", admin.id)
    db_session.commit()

    # Schluessel nachtraeglich "entfernt" (z. B. fehlkonfigurierte Umgebung) -
    # darf nicht crashen, sondern liefert bewusst None.
    value = get_credential_value(db_session, _settings(None), CREDENTIAL_KEY_TOMTOM_API_KEY)
    assert value is None


def test_reset_credential_updates_existing_row_not_duplicate(db_session):
    key = Fernet.generate_key().decode()
    admin = _admin(db_session)

    set_credential(db_session, _settings(key), CREDENTIAL_KEY_TOMTOM_API_KEY, "first-value", admin.id)
    db_session.commit()
    set_credential(db_session, _settings(key), CREDENTIAL_KEY_TOMTOM_API_KEY, "second-value", admin.id)
    db_session.commit()

    assert get_credential_value(db_session, _settings(key), CREDENTIAL_KEY_TOMTOM_API_KEY) == "second-value"


def test_set_credential_never_logs_plaintext_value(db_session):
    key = Fernet.generate_key().decode()
    admin = _admin(db_session)

    set_credential(db_session, _settings(key), CREDENTIAL_KEY_TOMTOM_API_KEY, "top-secret-value", admin.id)
    db_session.commit()

    log_entries = db_session.query(AuditLogEntry).all()
    assert len(log_entries) == 1
    entry = log_entries[0]
    assert "top-secret-value" not in str(entry.old_value_json)
    assert "top-secret-value" not in str(entry.new_value_json)


def test_get_credential_status_reports_configuration_without_value(db_session):
    key = Fernet.generate_key().decode()
    admin = _admin(db_session)

    status_before = get_credential_status(db_session, CREDENTIAL_KEY_TOMTOM_API_KEY)
    assert status_before.is_configured is False

    set_credential(db_session, _settings(key), CREDENTIAL_KEY_TOMTOM_API_KEY, "tomtom-secret", admin.id)
    db_session.commit()

    status_after = get_credential_status(db_session, CREDENTIAL_KEY_TOMTOM_API_KEY)
    assert status_after.is_configured is True
    assert status_after.updated_by == admin.id
    assert not hasattr(status_after, "value")


def test_delete_credential_removes_it(db_session):
    key = Fernet.generate_key().decode()
    admin = _admin(db_session)
    set_credential(db_session, _settings(key), CREDENTIAL_KEY_TOMTOM_API_KEY, "tomtom-secret", admin.id)
    db_session.commit()

    deleted = delete_credential(db_session, CREDENTIAL_KEY_TOMTOM_API_KEY, admin.id)
    db_session.commit()

    assert deleted is True
    assert get_credential_status(db_session, CREDENTIAL_KEY_TOMTOM_API_KEY).is_configured is False
