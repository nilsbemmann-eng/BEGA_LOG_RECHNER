from app.models.user import User, UserRole
from app.security_passwords import hash_password, verify_password


def _seed_admin(db_session) -> User:
    admin = User(name="Admin", email="admin@example.invalid", role=UserRole.ADMIN, active=True)
    db_session.add(admin)
    db_session.commit()
    return admin


def _seed_viewer(db_session) -> User:
    viewer = User(name="Viewer", email="viewer@example.invalid", role=UserRole.VIEWER, active=True)
    db_session.add(viewer)
    db_session.commit()
    return viewer


def test_admin_can_create_list_and_update_user(client, db_session):
    _seed_admin(db_session)

    create_response = client.post(
        "/api/users",
        json={"name": "Peter Pruefer", "email": "pruefer@example.invalid", "password": "initial-password", "role": "pruefer"},
    )
    assert create_response.status_code == 201, create_response.text
    user_id = create_response.json()["id"]
    assert create_response.json()["role"] == "pruefer"
    assert "password" not in create_response.json()
    assert "password_hash" not in create_response.json()

    list_response = client.get("/api/users")
    assert list_response.status_code == 200
    assert any(u["email"] == "pruefer@example.invalid" for u in list_response.json())

    update_response = client.patch(f"/api/users/{user_id}", json={"active": False})
    assert update_response.status_code == 200
    assert update_response.json()["active"] is False


def test_create_user_rejects_duplicate_email(client, db_session):
    _seed_admin(db_session)
    client.post("/api/users", json={"name": "A", "email": "dup@example.invalid", "password": "password123", "role": "viewer"})

    response = client.post("/api/users", json={"name": "B", "email": "dup@example.invalid", "password": "password123", "role": "viewer"})

    assert response.status_code == 409


def test_non_admin_cannot_manage_users(client, db_session):
    viewer = _seed_viewer(db_session)

    response = client.get("/api/users", headers={"X-User-Id": viewer.id})

    assert response.status_code == 403


def test_admin_can_set_users_password(client, db_session):
    admin = _seed_admin(db_session)
    target = User(name="X", email="x@example.invalid", role=UserRole.VIEWER, active=True, password_hash=hash_password("old-pw"))
    db_session.add(target)
    db_session.commit()

    response = client.post(f"/api/users/{target.id}/set-password", json={"new_password": "brand-new-password"})
    assert response.status_code == 204

    db_session.refresh(target)
    assert verify_password("brand-new-password", target.password_hash)
    assert not verify_password("old-pw", target.password_hash)
