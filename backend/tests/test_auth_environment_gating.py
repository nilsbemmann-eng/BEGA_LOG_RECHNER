"""Der Default-Admin-Fallback (kein Auth-Header -> beliebiger aktiver Admin)
ist ein reiner Entwicklungs-/Test-Komfort und darf in production NICHT
greifen (siehe app/auth.py)."""
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.database import get_db
from app.main import app
from app.models.user import User, UserRole


def test_default_admin_fallback_is_disabled_in_production(db_session):
    admin = User(name="Admin", email="admin@example.invalid", role=UserRole.ADMIN, active=True)
    db_session.add(admin)
    db_session.commit()

    def _override_get_db():
        yield db_session

    def _production_settings() -> Settings:
        return Settings(database_url="sqlite:///:memory:", environment="production")

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_settings] = _production_settings
    try:
        with TestClient(app) as client:
            response = client.get("/api/tariffs")
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_settings, None)

    assert response.status_code == 401


def test_default_admin_fallback_still_works_in_development(client, db_session):
    admin = User(name="Admin", email="admin@example.invalid", role=UserRole.ADMIN, active=True)
    db_session.add(admin)
    db_session.commit()

    response = client.get("/api/tariffs")

    assert response.status_code == 200
