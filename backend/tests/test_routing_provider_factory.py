import pytest
from cryptography.fernet import Fernet

from app.config import Settings
from app.providers.factory import build_routing_provider
from app.providers.routing.osrm_provider import OsrmRoutingProvider
from app.providers.routing.tomtom_provider import TomTomRoutingProvider
from app.services.integration_credential_service import CREDENTIAL_KEY_TOMTOM_API_KEY, set_credential


def test_build_routing_provider_returns_osrm_by_default():
    provider = build_routing_provider(Settings(database_url="sqlite:///:memory:"))
    assert isinstance(provider, OsrmRoutingProvider)


def test_build_routing_provider_tomtom_uses_env_var_fallback_without_db():
    settings = Settings(database_url="sqlite:///:memory:", routing_provider="tomtom", tomtom_api_key="env-key")
    provider = build_routing_provider(settings, db=None)
    assert isinstance(provider, TomTomRoutingProvider)
    assert provider._api_key == "env-key"


def test_build_routing_provider_tomtom_raises_without_any_key():
    settings = Settings(database_url="sqlite:///:memory:", routing_provider="tomtom")
    with pytest.raises(ValueError):
        build_routing_provider(settings, db=None)


def test_build_routing_provider_tomtom_prefers_db_credential_over_env_var(db_session):
    encryption_key = Fernet.generate_key().decode()
    settings = Settings(
        database_url="sqlite:///:memory:", routing_provider="tomtom",
        tomtom_api_key="env-fallback-key", credential_encryption_key=encryption_key,
    )
    set_credential(db_session, settings, CREDENTIAL_KEY_TOMTOM_API_KEY, "admin-managed-key", updated_by_user_id=None)
    db_session.commit()

    provider = build_routing_provider(settings, db=db_session)

    assert isinstance(provider, TomTomRoutingProvider)
    assert provider._api_key == "admin-managed-key"
