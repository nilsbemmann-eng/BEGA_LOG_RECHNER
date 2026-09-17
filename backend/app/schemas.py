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


# --- Login/Benutzerverwaltung (Abschnitt 3, 10.3) ---------------------------


class UserOut(ORMModel):
    id: str
    name: str
    email: str
    role: str
    active: bool


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_minutes: int
    user: UserOut


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class UserCreateRequest(BaseModel):
    name: str
    email: str
    password: str
    role: str = "viewer"


class UserUpdateRequest(BaseModel):
    name: str | None = None
    role: str | None = None
    active: bool | None = None


class SetPasswordRequest(BaseModel):
    new_password: str


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


class EmailUploadResult(BaseModel):
    email_id: str | None
    is_duplicate: bool
    subject: str
    attachment_count: int


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
    unloading_point_count: int


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


# --- Spediteure (Frachtfuehrer) -----------------------------------------------


class CarrierCreateRequest(BaseModel):
    name: str
    billing_rules_reference: str | None = None


class CarrierUpdateRequest(BaseModel):
    name: str | None = None
    billing_rules_reference: str | None = None


class CarrierOut(ORMModel):
    id: str
    name: str
    carrier_code: str
    billing_rules_reference: str | None


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


# --- Touren (BEGA-Finetuning: eine Frachtrechnung pro Tour/Ladeliste) --------


class TourShipmentOut(ORMModel):
    id: str
    shipment_number: str | None
    weight_kg: Decimal | None
    volume_m3: Decimal | None
    packages: int | None
    destination_postal_code: str | None = None
    destination_city: str | None = None

    @classmethod
    def from_orm_shipment(cls, shipment: "Shipment") -> "TourShipmentOut":  # noqa: F821
        return cls(
            id=shipment.id,
            shipment_number=shipment.shipment_number,
            weight_kg=shipment.weight_kg,
            volume_m3=shipment.volume_m3,
            packages=shipment.packages,
            destination_postal_code=shipment.destination_address.postal_code if shipment.destination_address else None,
            destination_city=shipment.destination_address.city if shipment.destination_address else None,
        )


class TourOut(ORMModel):
    id: str
    tour_number: str
    version: str | None
    carrier_id: str | None
    carrier_name: str | None = None
    tour_date: date | None
    loading_date: date | None
    invoiced_km: Decimal | None
    invoice_amount: Decimal | None
    currency: str
    shipment_count: int
    shipments: list[TourShipmentOut] = []

    @classmethod
    def from_orm_tour(cls, tour: "Tour") -> "TourOut":  # noqa: F821
        return cls(
            id=tour.id,
            tour_number=tour.tour_number,
            version=tour.version,
            carrier_id=tour.carrier_id,
            carrier_name=tour.carrier.name if tour.carrier else None,
            tour_date=tour.tour_date,
            loading_date=tour.loading_date,
            invoiced_km=tour.invoiced_km,
            invoice_amount=tour.invoice_amount,
            currency=tour.currency,
            shipment_count=tour.shipment_count,
            shipments=[TourShipmentOut.from_orm_shipment(s) for s in tour.shipments],
        )


# --- Absender-Matrix (BEGA-Finetuning: LL-Nummer-Praefix -> Beladeadresse) ---


class TourOriginMappingCreate(BaseModel):
    tour_number_prefix: str
    matchcode: str
    description: str | None = None
    street: str | None = None
    postal_code: str | None = None
    city: str | None = None
    country_code: str | None = None


class TourOriginMappingUpdateRequest(BaseModel):
    description: str | None = None
    street: str | None = None
    postal_code: str | None = None
    city: str | None = None
    country_code: str | None = None


class TourOriginMappingOut(ORMModel):
    id: str
    tour_number_prefix: str
    matchcode: str
    description: str | None
    street: str | None = None
    postal_code: str | None = None
    city: str | None = None
    country_code: str | None = None
    version: int
    is_current: bool

    @classmethod
    def from_orm_mapping(cls, mapping: "TourOriginMapping") -> "TourOriginMappingOut":  # noqa: F821
        address = mapping.origin_address
        return cls(
            id=mapping.id,
            tour_number_prefix=mapping.tour_number_prefix,
            matchcode=mapping.matchcode,
            description=mapping.description,
            street=address.street if address else None,
            postal_code=address.postal_code if address else None,
            city=address.city if address else None,
            country_code=address.country_code if address else None,
            version=mapping.version,
            is_current=mapping.is_current,
        )


class TourOriginMatrixImportResult(BaseModel):
    imported_count: int


class CarrierRateMatrixImportResult(BaseModel):
    imported_count: int


class SpecialAgreementSurchargeCreate(BaseModel):
    tour_number_prefix: str
    amount: Decimal
    note: str | None = None


class SpecialAgreementSurchargeUpdateRequest(BaseModel):
    amount: Decimal | None = None
    note: str | None = None


class SpecialAgreementSurchargeOut(ORMModel):
    id: str
    tour_number_prefix: str
    amount: Decimal
    note: str | None
    version: int
    is_current: bool


# --- Audits -----------------------------------------------------------------


class AuditRunRequest(BaseModel):
    shipment_id: str
    route_context: str = "standard"  # standard | inner_city_or_hard_to_access | special_route


class TourAuditRunRequest(BaseModel):
    tour_id: str


class AuditRuleResultOut(ORMModel):
    rule_code: str
    rule_name: str
    status: str
    actual_value: str | None
    expected_value: str | None
    explanation: str


class AuditResultOut(ORMModel):
    id: str
    shipment_id: str | None
    tour_id: str | None = None
    shipment_number: str | None
    carrier_name: str | None
    transport_date: date | None
    tariff_id: str | None
    reference_distance_km: Decimal | None
    invoiced_distance_km: Decimal | None
    expected_amount: Decimal | None
    invoiced_amount: Decimal | None
    difference_amount: Decimal | None
    difference_percent: Decimal | None
    status: str
    explanation: str
    created_at: datetime
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
    download_url: str


# --- Admin-pflegbare Zugangsdaten (z. B. TomTom-API-Key, Nutzervorgabe) -----


class IntegrationCredentialSetRequest(BaseModel):
    value: str


class IntegrationCredentialStatusOut(BaseModel):
    credential_key: str
    is_configured: bool
    updated_at: datetime | None
    updated_by: str | None


# --- Fehler -----------------------------------------------------------------


class ErrorResponse(BaseModel):
    error_code: str
    message: str
    entity_type: str | None = None
    entity_id: str | None = None
    retryable: bool
    timestamp: datetime
