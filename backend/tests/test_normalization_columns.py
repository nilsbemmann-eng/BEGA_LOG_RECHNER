from app.normalization.columns import map_columns


def test_map_columns_with_varying_german_headers() -> None:
    header = ["Auftrag", "Beladestelle", "Entladestelle", "Brutto kg", "Colli", "Sonderfeld X"]
    result = map_columns(header)

    assert result.column_to_field["Auftrag"] == "shipment_number"
    assert result.column_to_field["Beladestelle"] == "origin_address"
    assert result.column_to_field["Entladestelle"] == "destination_address"
    assert result.column_to_field["Brutto kg"] == "weight_kg"
    assert result.column_to_field["Colli"] == "pallets"
    assert "Sonderfeld X" in result.unmapped_columns


def test_map_columns_keeps_first_match_when_duplicate_targets() -> None:
    header = ["Sendung", "Referenz"]
    result = map_columns(header)

    assert result.field_to_column["shipment_number"] == "Sendung"
    assert "Referenz" in result.unmapped_columns


def test_map_columns_distinguishes_unloading_point_count_from_destination_address() -> None:
    # "Entladestelle" (Adresse) und "Anzahl Entladestellen" (Zaehlfeld,
    # BEGA-Finetuning) duerfen sich nicht gegenseitig ueberschreiben.
    header = ["Entladestelle", "Anzahl Entladestellen"]
    result = map_columns(header)

    assert result.column_to_field["Entladestelle"] == "destination_address"
    assert result.column_to_field["Anzahl Entladestellen"] == "unloading_point_count"
