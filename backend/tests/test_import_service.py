from decimal import Decimal

from sqlalchemy import select

from app.models.shipment import Shipment
from app.services.import_service import import_ladeliste


def test_import_ladeliste_csv_maps_german_columns_and_keeps_unmapped(db_session, tmp_path):
    csv_content = (
        "Auftrag;Beladestelle;Entladestelle;Brutto kg;Colli;Sonderfeld\n"
        "A-1;Hannover;Bremen;1.240;5;Extrawert\n"
    ).encode("utf-8-sig")

    job = import_ladeliste(db_session, csv_content, "ladeliste.csv", str(tmp_path))
    db_session.commit()

    assert job.records_total == 1
    assert job.records_successful == 1
    assert job.records_failed == 0
    assert job.error_report_reference is not None  # Sonderfeld wurde protokolliert

    shipment = db_session.execute(select(Shipment)).scalars().one()
    assert shipment.shipment_number == "A-1"
    assert shipment.weight_kg == Decimal("1240")
    assert shipment.pallets == 5
    assert shipment.origin_address.original_text == "Hannover"
    assert shipment.destination_address.original_text == "Bremen"
    assert shipment.unloading_point_count == 1  # keine Spalte vorhanden -> Standardwert


def test_import_ladeliste_csv_reads_unloading_point_count(db_session, tmp_path):
    csv_content = (
        "Auftrag;Beladestelle;Entladestelle;Anzahl Entladestellen\n"
        "A-2;Hannover;Bremen;3\n"
    ).encode("utf-8-sig")

    import_ladeliste(db_session, csv_content, "ladeliste.csv", str(tmp_path))
    db_session.commit()

    shipment = db_session.execute(select(Shipment)).scalars().one()
    assert shipment.unloading_point_count == 3
