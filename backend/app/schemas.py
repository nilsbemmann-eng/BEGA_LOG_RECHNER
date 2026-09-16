"""Pydantic-Schemas fuer die API (Abschnitt 11).

In einer Datei gebuendelt, um Ueberblick ueber den API-Vertrag des MVP zu
behalten; bei wachsendem Umfang je Ressource in `app/schemas/` aufteilen.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- E-Mails -----------------------------------------------------------------


class EmailOut(ORMModel):
    id: str
    external_message_id: str
    sender: str
    subject: str
    received_at: datetime
    processing_status: str


class EmailSyncResult(BaseModel):
    mailbox_id: str
    fetched_count: int
    imported_count: int
    duplicate_count: int


# --- Dokumente -----------------------------------------------------------------


class ExtractedFieldOut(ORMModel):
    id: str
    field_name: str
    original_value: str
    normalized_value: str | None
    corrected_value: str | None
    data_type: str
    confidence: float
    source_page: int | None
    source_text: str | None
    extraction_method: str


class ExtractedFieldCorrection(BaseModel):
    corrected_value: str


class DocumentOut(ORMModel):
    id: str
    attachment_id: str
    document_type: str
    classification_confidence: float
    ocr_status: str
    page_count: int
    shipment_id: str | None
    extracted_fields: list[ExtractedFieldOut] = []


# --- Sendungen -----------------------------------------------------------------


class ShipmentOut(ORMModel):
    id: str
    shipment_number: str | None
    transport_order_number: str | None
    invoice_number: str | None
    transport_date: date | None
    carrier_id: str | None
    customer_id: str | None
    weight_kg: Decimal | None
    pallets: int | None
    loading_meters: Decimal | None
    invoiced_km: Decimal | None
    invoice_amount: Decimal | None
    currency: str


class ShipmentMatchRequest(BaseModel):
    document_id: str
    shipment_number: str | None = None
    transport_order_number: str | None = None
    invoice_number: str | None = None
    carrier_code: str | None = None
    origin_address_text: str | None = None
    destination_address_text: str | None = None
    transport_date: date | None = None
    invoice_amount: Decimal | None = None


class ShipmentMatchCandidateOut(BaseModel):
    shipment_id: str
    score: float
    matched_criteria: list[str]


class ShipmentMatchResponse(BaseModel):
    auto_assigned_shipment_id: str | None
    candidates: list[ShipmentMatchCandidateOut]


# --- Routing -----------------------------------------------------------------


class RouteCalculationRequest(BaseModel):
    shipment_id: str | None = None
    origin_address_text: str
    destination_address_text: str
    profile: str = "truck"


class RouteCalculationResponse(BaseModel):
    origin_lat: float
    origin_lon: float
    destination_lat: float
    destination_lon: float
    distance_km: float
    duration_minutes: int
    profile: str
    provider: str
    calculated_at: datetime
    from_cache: bool


# --- Tarife -----------------------------------------------------------------


class TariffRuleIn(BaseModel):
    rule_type: str
    parameters: dict
    priority: int = 0


class TariffRuleOut(ORMModel):
    id: str
    rule_type: str
    parameters_json: dict
    priority: int


class TariffCreate(BaseModel):
    tariff_code: str
    name: str
    carrier_id: str | None = None
    valid_from: date
    valid_to: date | None = None
    currency: str = "EUR"
    rules: list[TariffRuleIn]


class TariffOut(ORMModel):
    id: str
    tariff_code: str
    name: str
    carrier_id: str | None
    valid_from: date
    valid_to: date | None
    currency: str
    status: str
    version: int
    rules: list[TariffRuleOut] = []


# --- Zusatzfrachten -----------------------------------------------------------------


class SurchargeClaimOut(ORMModel):
    id: str
    surcharge_type: str
    description: str
    quantity: Decimal
    unit: str
    unit_price: Decimal
    claimed_amount: Decimal
    allowed_amount: Decimal | None
    status: str
    reason: str | None


# --- Audits -----------------------------------------------------------------


class AuditRunRequest(BaseModel):
    shipment_id: str
    route_context: str = "standard"  # standard | inner_city_or_hard_to_access | special_route


class AuditRuleResultOut(ORMModel):
    rule_code: str
    rule_name: str
    status: str
    actual_value: str | None
    expected_value: str | None
    explanation: str


class AuditResultOut(ORMModel):
    id: str
    shipment_id: str
    tariff_id: str | None
    reference_distance_km: Decimal | None
    invoiced_distance_km: Decimal | None
    expected_amount: Decimal | None
    invoiced_amount: Decimal | None
    difference_amount: Decimal | None
    difference_percent: Decimal | None
    status: str
    explanation: str
    rule_results: list[AuditRuleResultOut] = []


class AuditDecisionRequest(BaseModel):
    comment: str | None = None


# --- Import / Export -----------------------------------------------------------------


class ImportJobOut(ORMModel):
    id: str
    source_type: str
    status: str
    records_total: int
    records_successful: int
    records_failed: int


class ExportRequestIn(BaseModel):
    audit_result_ids: list[str]
    file_format: str = "xlsx"


class ExportOut(BaseModel):
    export_id: str
    file_format: str
    row_count: int
    storage_reference: str


# --- Fehler -----------------------------------------------------------------


class ErrorResponse(BaseModel):
    error_code: str
    message: str
    entity_type: str | None = None
    entity_id: str | None = None
    retryable: bool
    timestamp: datetime
