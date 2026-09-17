from app.models.user import User, UserRole


def _seed_admin(db_session) -> User:
    admin = User(name="Admin", email="admin@example.invalid", role=UserRole.ADMIN, active=True)
    db_session.add(admin)
    db_session.commit()
    return admin


def _seed_preisadmin(db_session) -> User:
    preisadmin = User(name="Preisadmin", email="preisadmin@example.invalid", role=UserRole.PREISADMIN, active=True)
    db_session.add(preisadmin)
    db_session.commit()
    return preisadmin


def test_create_list_and_delete_special_agreement_surcharge(client, db_session):
    _seed_admin(db_session)

    create_response = client.post(
        "/api/special-agreement-surcharges",
        json={"tour_number_prefix": "19", "amount": "100.00", "note": "Meble Polskie Sondervereinbarung"},
    )
    assert create_response.status_code == 201, create_response.text
    surcharge_id = create_response.json()["id"]
    assert create_response.json()["amount"] == "100.00"
    assert create_response.json()["version"] == 1
    assert create_response.json()["is_current"] is True

    list_response = client.get("/api/special-agreement-surcharges")
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1

    delete_response = client.delete(f"/api/special-agreement-surcharges/{surcharge_id}")
    assert delete_response.status_code == 204

    assert client.get("/api/special-agreement-surcharges").json() == []


def test_create_rejects_duplicate_current_prefix(client, db_session):
    _seed_admin(db_session)
    client.post("/api/special-agreement-surcharges", json={"tour_number_prefix": "19", "amount": "100.00"})

    response = client.post("/api/special-agreement-surcharges", json={"tour_number_prefix": "19", "amount": "50.00"})

    assert response.status_code == 409


def test_patch_creates_new_version_and_keeps_history(client, db_session):
    _seed_admin(db_session)
    created = client.post("/api/special-agreement-surcharges", json={"tour_number_prefix": "19", "amount": "100.00"}).json()

    patched = client.patch(f"/api/special-agreement-surcharges/{created['id']}", json={"amount": "150.00"})
    assert patched.status_code == 200, patched.text
    assert patched.json()["version"] == 2
    assert patched.json()["is_current"] is True
    assert patched.json()["id"] != created["id"]

    current = client.get("/api/special-agreement-surcharges").json()
    assert len(current) == 1
    assert current[0]["amount"] == "150.00"

    history = client.get("/api/special-agreement-surcharges?include_history=true").json()
    assert len(history) == 2
    old = next(s for s in history if s["id"] == created["id"])
    assert old["is_current"] is False
    assert old["amount"] == "100.00"


def test_patch_rejects_editing_a_superseded_version(client, db_session):
    _seed_admin(db_session)
    created = client.post("/api/special-agreement-surcharges", json={"tour_number_prefix": "19", "amount": "100.00"}).json()
    client.patch(f"/api/special-agreement-surcharges/{created['id']}", json={"amount": "150.00"})

    response = client.patch(f"/api/special-agreement-surcharges/{created['id']}", json={"amount": "200.00"})

    assert response.status_code == 409


def test_preisadmin_can_manage_surcharges_but_not_users(client, db_session):
    preisadmin = _seed_preisadmin(db_session)
    headers = {"X-User-Id": preisadmin.id}

    create_response = client.post(
        "/api/special-agreement-surcharges", json={"tour_number_prefix": "19", "amount": "100.00"}, headers=headers
    )
    assert create_response.status_code == 201, create_response.text

    users_response = client.get("/api/users", headers=headers)
    assert users_response.status_code == 403
