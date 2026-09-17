from app.models.user import User, UserRole


def _seed_admin(db_session) -> User:
    admin = User(name="Admin", email="admin@example.invalid", role=UserRole.ADMIN, active=True)
    db_session.add(admin)
    db_session.commit()
    return admin


def test_create_list_and_delete_special_agreement_surcharge(client, db_session):
    _seed_admin(db_session)

    create_response = client.post(
        "/api/special-agreement-surcharges",
        json={"tour_number_prefix": "19", "amount": "100.00", "note": "Meble Polskie Sondervereinbarung"},
    )
    assert create_response.status_code == 201, create_response.text
    surcharge_id = create_response.json()["id"]
    assert create_response.json()["amount"] == "100.00"

    list_response = client.get("/api/special-agreement-surcharges")
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1

    delete_response = client.delete(f"/api/special-agreement-surcharges/{surcharge_id}")
    assert delete_response.status_code == 204

    assert client.get("/api/special-agreement-surcharges").json() == []
