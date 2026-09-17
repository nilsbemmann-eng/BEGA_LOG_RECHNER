from app.models.user import User, UserRole
from app.security_passwords import hash_password


def _create_user_with_password(db_session, *, email="admin@example.invalid", password="supersecret123", role=UserRole.ADMIN, active=True) -> User:
    user = User(name="Test User", email=email, role=role, active=active, password_hash=hash_password(password))
    db_session.add(user)
    db_session.commit()
    return user


def test_login_with_correct_credentials_returns_token(client, db_session):
    _create_user_with_password(db_session, password="correct-password")

    response = client.post("/api/auth/login", json={"email": "admin@example.invalid", "password": "correct-password"})

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["token_type"] == "bearer"
    assert payload["access_token"]
    assert payload["user"]["email"] == "admin@example.invalid"


def test_login_with_wrong_password_is_rejected(client, db_session):
    _create_user_with_password(db_session, password="correct-password")

    response = client.post("/api/auth/login", json={"email": "admin@example.invalid", "password": "wrong-password"})

    assert response.status_code == 401


def test_login_with_unknown_email_is_rejected_with_same_message_as_wrong_password(client, db_session):
    _create_user_with_password(db_session, password="correct-password")

    known_wrong = client.post("/api/auth/login", json={"email": "admin@example.invalid", "password": "wrong-password"})
    unknown = client.post("/api/auth/login", json={"email": "nobody@example.invalid", "password": "irrelevant"})

    assert known_wrong.status_code == unknown.status_code == 401
    assert known_wrong.json()["detail"] == unknown.json()["detail"]


def test_login_rejects_deactivated_user(client, db_session):
    _create_user_with_password(db_session, password="correct-password", active=False)

    response = client.post("/api/auth/login", json={"email": "admin@example.invalid", "password": "correct-password"})

    assert response.status_code == 403


def test_token_from_login_authenticates_subsequent_requests(client, db_session):
    _create_user_with_password(db_session, password="correct-password")
    login_response = client.post("/api/auth/login", json={"email": "admin@example.invalid", "password": "correct-password"})
    token = login_response.json()["access_token"]

    me_response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert me_response.status_code == 200
    assert me_response.json()["email"] == "admin@example.invalid"


def test_invalid_bearer_token_is_rejected(client, db_session):
    _create_user_with_password(db_session)

    response = client.get("/api/auth/me", headers={"Authorization": "Bearer not-a-real-token"})

    assert response.status_code == 401


def test_change_password_requires_correct_current_password(client, db_session):
    _create_user_with_password(db_session, password="old-password")
    login_response = client.post("/api/auth/login", json={"email": "admin@example.invalid", "password": "old-password"})
    token = login_response.json()["access_token"]

    wrong_current = client.post(
        "/api/auth/change-password",
        json={"current_password": "totally-wrong", "new_password": "new-password-123"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert wrong_current.status_code == 401

    correct = client.post(
        "/api/auth/change-password",
        json={"current_password": "old-password", "new_password": "new-password-123"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert correct.status_code == 204

    old_login = client.post("/api/auth/login", json={"email": "admin@example.invalid", "password": "old-password"})
    assert old_login.status_code == 401
    new_login = client.post("/api/auth/login", json={"email": "admin@example.invalid", "password": "new-password-123"})
    assert new_login.status_code == 200
