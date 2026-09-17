from app.models.user import User, UserRole


def _seed_admin(db_session) -> User:
    admin = User(name="Admin", email="admin@example.invalid", role=UserRole.ADMIN, active=True)
    db_session.add(admin)
    db_session.commit()
    return admin


def test_set_credential_requires_encryption_key_configured(client, db_session, monkeypatch):
    _seed_admin(db_session)
    monkeypatch.delenv("CREDENTIAL_ENCRYPTION_KEY", raising=False)

    response = client.put("/api/integration-credentials/tomtom_api_key", json={"value": "secret"})

    assert response.status_code == 503, response.text


def test_set_list_and_delete_credential_never_exposes_value(client, db_session, monkeypatch):
    from cryptography.fernet import Fernet

    monkeypatch.setenv("CREDENTIAL_ENCRYPTION_KEY", Fernet.generate_key().decode())
    from app.config import get_settings
    get_settings.cache_clear()
    _seed_admin(db_session)

    try:
        set_response = client.put("/api/integration-credentials/tomtom_api_key", json={"value": "tomtom-secret-key"})
        assert set_response.status_code == 200, set_response.text
        payload = set_response.json()
        assert payload["is_configured"] is True
        assert "tomtom-secret-key" not in str(payload)
        assert "value" not in payload

        list_response = client.get("/api/integration-credentials")
        assert list_response.status_code == 200
        entries = list_response.json()
        assert any(e["credential_key"] == "tomtom_api_key" and e["is_configured"] for e in entries)
        assert "tomtom-secret-key" not in str(entries)

        delete_response = client.delete("/api/integration-credentials/tomtom_api_key")
        assert delete_response.status_code == 204

        list_after_delete = client.get("/api/integration-credentials").json()
        assert not any(e["credential_key"] == "tomtom_api_key" and e["is_configured"] for e in list_after_delete)
    finally:
        get_settings.cache_clear()
