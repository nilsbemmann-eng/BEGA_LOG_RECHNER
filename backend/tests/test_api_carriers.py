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


def _seed_viewer(db_session) -> User:
    viewer = User(name="Viewer", email="viewer@example.invalid", role=UserRole.VIEWER, active=True)
    db_session.add(viewer)
    db_session.commit()
    return viewer


def test_admin_can_create_and_list_carrier(client, db_session):
    _seed_admin(db_session)

    create_response = client.post(
        "/api/carriers", json={"name": "Spedition Mustermann", "billing_rules_reference": "siehe Rahmenvertrag 2026"}
    )
    assert create_response.status_code == 201, create_response.text
    body = create_response.json()
    assert body["name"] == "Spedition Mustermann"
    assert body["carrier_code"] == "SPEDITION-MUSTERMANN"
    assert body["billing_rules_reference"] == "siehe Rahmenvertrag 2026"

    list_response = client.get("/api/carriers")
    assert list_response.status_code == 200
    assert any(c["name"] == "Spedition Mustermann" for c in list_response.json())


def test_create_carrier_rejects_duplicate_name(client, db_session):
    _seed_admin(db_session)
    client.post("/api/carriers", json={"name": "Spedition Mustermann"})

    response = client.post("/api/carriers", json={"name": "Spedition Mustermann"})

    assert response.status_code == 409


def test_create_carrier_generates_unique_code_for_similar_names(client, db_session):
    _seed_admin(db_session)
    first = client.post("/api/carriers", json={"name": "Spedition Müller"}).json()
    second = client.post("/api/carriers", json={"name": "Spedition Mueller"}).json()

    assert first["carrier_code"] != second["carrier_code"]


def test_preisadmin_can_create_carrier(client, db_session):
    preisadmin = _seed_preisadmin(db_session)

    response = client.post(
        "/api/carriers", json={"name": "Preisadmin Spedition"}, headers={"X-User-Id": preisadmin.id}
    )

    assert response.status_code == 201, response.text


def test_viewer_cannot_create_carrier(client, db_session):
    viewer = _seed_viewer(db_session)

    response = client.post("/api/carriers", json={"name": "Verboten"}, headers={"X-User-Id": viewer.id})

    assert response.status_code == 403


def test_update_carrier(client, db_session):
    _seed_admin(db_session)
    created = client.post("/api/carriers", json={"name": "Alter Name"}).json()

    response = client.patch(f"/api/carriers/{created['id']}", json={"name": "Neuer Name"})

    assert response.status_code == 200, response.text
    assert response.json()["name"] == "Neuer Name"
