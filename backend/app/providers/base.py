"""Austauschbare Provider-Schnittstellen (Abschnitt 10.2).

Jede externe Abhaengigkeit (E-Mail, OCR, Geocoding, Routing, Waehrung, Export)
wird ausschliesslich ueber eine dieser Schnittstellen angesprochen. Die
konkrete Implementierung wird ueber Konfiguration ausgewaehlt
(`app/config.py`, `app/providers/factory.py`) und ist in Unit-Tests durch
Fakes/Dummies ersetzbar.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Protocol


# --- E-Mail ---------------------------------------------------------------


@dataclass
class EmailAttachmentData:
    filename: str
    mime_type: str
    content: bytes


@dataclass
class EmailMessage:
    external_message_id: str
    sender: str
    recipients: list[str]
    cc_recipients: list[str]
    subject: str
    received_at: datetime
    body_text: str
    body_html: str | None
    attachments: list[EmailAttachmentData] = field(default_factory=list)
    raw_metadata: dict = field(default_factory=dict)


class EmailProvider(Protocol):
    def fetch_messages(self, folder: str, since: datetime | None = None) -> list[EmailMessage]:
        """Liest neue Nachrichten aus dem konfigurierten Postfach (Abschnitt 4.1)."""
        ...


# --- Dokumentenklassifikation ----------------------------------------------


@dataclass
class ClassificationResult:
    document_type: str  # Wert aus app.models.document.DocumentType
    confidence: float
    scores: dict[str, float] = field(default_factory=dict)


class DocumentClassifier(Protocol):
    def classify(self, text: str, filename: str) -> ClassificationResult:
        """Ordnet ein Dokument einem Typ aus Abschnitt 4.3 zu."""
        ...


# --- OCR / Dokumentenanalyse -------------------------------------------------


@dataclass
class DocumentInput:
    file_bytes: bytes
    mime_type: str
    filename: str


@dataclass
class ExtractedFieldResult:
    field_name: str
    original_value: str
    normalized_value: str | Decimal | None
    data_type: str
    confidence: float
    source_page: int | None
    source_text: str | None
    extraction_method: str
    source_bbox: dict | None = None


@dataclass
class OcrPageResult:
    page_number: int
    extracted_text: str
    raw: dict = field(default_factory=dict)


@dataclass
class OcrResult:
    pages: list[OcrPageResult]
    fields: list[ExtractedFieldResult]


class DocumentOcrProvider(ABC):
    @abstractmethod
    def analyze(self, document: DocumentInput) -> OcrResult:
        """Erkennt Text, Tabellen und Schluessel-Wert-Paare (Abschnitt 4.4)."""
        raise NotImplementedError


# --- Geocoding --------------------------------------------------------------


@dataclass
class GeocodeInput:
    address_text: str
    country_hint: str | None = None


@dataclass
class GeocodeResult:
    matched: bool
    latitude: float | None
    longitude: float | None
    normalized_address: str | None
    country_code: str | None
    precision: str | None  # "rooftop" | "street" | "city" | "postal_code"
    confidence: float
    provider: str
    ambiguous: bool = False
    candidate_count: int = 0


class GeocodingProvider(ABC):
    @abstractmethod
    def geocode(self, request: GeocodeInput) -> GeocodeResult:
        """Ermittelt Koordinaten fuer eine Adresse (Abschnitt 5.1)."""
        raise NotImplementedError


# --- Routing -----------------------------------------------------------------


@dataclass
class RouteInput:
    origin_lat: float
    origin_lon: float
    destination_lat: float
    destination_lon: float
    profile: str = "truck"  # "air" | "car" | "truck"


@dataclass
class RouteResult:
    origin_lat: float
    origin_lon: float
    destination_lat: float
    destination_lon: float
    distance_km: float
    duration_minutes: int
    profile: str
    provider: str
    calculated_at: datetime


class RoutingProvider(ABC):
    @abstractmethod
    def calculate_route(self, route_input: RouteInput) -> RouteResult:
        """Berechnet eine Referenzroute (Abschnitt 5.2)."""
        raise NotImplementedError


# --- Waehrung (optional, Abschnitt 10.2) -------------------------------------


class CurrencyProvider(Protocol):
    def convert(self, amount: Decimal, from_currency: str, to_currency: str, as_of: datetime) -> Decimal:
        """Waehrungsumrechnung. Im MVP nicht produktiv angebunden
        (siehe docs/OFFENE_ENTSCHEIDUNGEN.md, Punkt 9)."""
        ...


# --- Export -------------------------------------------------------------------


@dataclass
class ExportRequest:
    export_id: str
    file_format: str  # "xlsx" | "csv" | "pdf"
    rows: list[dict]


@dataclass
class ExportResult:
    storage_reference: str
    file_format: str
    row_count: int


class ExportProvider(ABC):
    @abstractmethod
    def export(self, request: ExportRequest) -> ExportResult:
        """Erzeugt eine Exportdatei (Abschnitt 1.1, 11)."""
        raise NotImplementedError
