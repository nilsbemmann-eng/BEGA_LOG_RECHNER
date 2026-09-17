import io

from openpyxl import Workbook

from app.models.user import User, UserRole


def _seed_admin(db_session) -> User:
    admin = User(name="Admin", email="admin@example.invalid", role=UserRole.ADMIN, active=True)
    db_session.add(admin)
    db_session.commit()
    return admin


def _stammdaten_workbook() -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Stammdaten"
    sheet.append(["Versendet", None, "Land", "Deutschland"])
    sheet.append(["Bestaetigt", None, "Kfz-Zeichen", "D"])
    sheet.append(["Preise ok", None, "ISO Code 1 (alpha-2)", "DE"])
    sheet.append(["STORNO", None, "ISO Code 2 (alpha-3)", "DEU"])
    sheet.append(["Angemahnt", None, "ISO Code 3 (numeric)", 276])
    sheet.append([None, None, "ATB", 1.4])
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def test_import_rate_matrix_endpoint_creates_tariff(client, db_session):
    _seed_admin(db_session)

    response = client.post(
        "/api/tariffs/import-rate-matrix",
        files={"file": ("Preise_2026.xlsm", _stammdaten_workbook(), "application/vnd.ms-excel.sheet.macroEnabled.12")},
    )

    assert response.status_code == 200, response.text
    assert response.json()["imported_count"] == 1

    tariffs_response = client.get("/api/tariffs")
    assert tariffs_response.status_code == 200
    assert len(tariffs_response.json()) == 1
