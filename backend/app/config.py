"""Zentrale Anwendungskonfiguration.

Alle sicherheitsrelevanten Werte (Zugangsdaten, API-Schluessel) werden
ausschliesslich aus Umgebungsvariablen bzw. einem vorgelagerten
Secret-Management-System gelesen (Abschnitt 13 des technischen Berichts).
Es duerfen keine Zugangsdaten im Quellcode oder in Default-Werten stehen.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Allgemein ---
    environment: str = "development"
    app_name: str = "BEGA Frachtpreisrechner"

    # --- Datenbank ---
    database_url: str = "postgresql+psycopg2://bega:bega@localhost:5432/bega_frachtpreis"

    # --- Auth (Platzhalter, siehe docs/OFFENE_ENTSCHEIDUNGEN.md) ---
    jwt_secret_key: str = "CHANGE_ME_IN_ENV"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 480

    # --- Dokumentenspeicher ---
    document_storage_backend: str = "local"  # local | s3 (siehe app/storage.py)
    document_storage_path: str = "./local_storage/documents"

    # --- E-Mail-Postfach (IMAP), siehe app/providers/email ---
    mailbox_host: str | None = None
    mailbox_user: str | None = None
    mailbox_password: str | None = None
    mailbox_folder: str = "INBOX"
    mailbox_use_ssl: bool = True

    # --- Geocoding-Provider ---
    geocoding_provider: str = "nominatim"
    nominatim_base_url: str = "https://nominatim.openstreetmap.org"
    nominatim_user_agent: str = "bega-frachtpreisrechner/1.0 (contact: ops@example.invalid)"

    # --- Routing-Provider ---
    routing_provider: str = "osrm"
    osrm_base_url: str = "https://router.project-osrm.org"
    default_routing_profile: str = "truck"  # siehe docs/OFFENE_ENTSCHEIDUNGEN.md Punkt 5

    # --- OCR-Provider ---
    ocr_provider: str = "pdf_text"  # pdf_text | dummy (siehe docs/OFFENE_ENTSCHEIDUNGEN.md Punkt 3)
    ocr_min_auto_confidence: float = 0.95
    ocr_min_flagged_confidence: float = 0.80

    # --- Kilometertoleranzen (Abschnitt 5.3), konfigurierbar ---
    km_tolerance_standard_percent: float = 8.0
    km_tolerance_inner_city_percent: float = 12.0

    # --- Preistoleranz fuer Regel "Preis" (Abschnitt 8.1). Der Bericht nennt
    # hierfuer keinen Startwert - 5 % ist eine dokumentierte Annahme und muss
    # vor Produktivbetrieb bestaetigt werden (siehe docs/OFFENE_ENTSCHEIDUNGEN.md).
    price_deviation_tolerance_percent: float = 5.0

    # --- Plausibilitaetsgrenzen (Abschnitt 8.1, Regel "Plausibilitaet") ---
    plausibility_max_weight_kg: float = 24000.0
    plausibility_max_loading_meters: float = 13.6

    # --- Zuschlag "zusaetzliche Entladestelle" (BEGA-Finetuning, siehe
    # docs/OFFENE_ENTSCHEIDUNGEN.md): einheitlicher Standardwert, je Tarif
    # ueber TariffRule-Parameter "additional_unloading_point_price" ueberschreibbar.
    default_additional_unloading_point_price_eur: float = 50.0

    # --- Aufbewahrung (Punkt 10 offene Entscheidungen) ---
    retention_days_documents: int | None = None
    retention_days_audit_results: int | None = None

    # --- Export ---
    export_storage_path: str = "./local_storage/exports"

    # --- CORS: kommagetrennte Liste erlaubter Frontend-Origins ---
    cors_allowed_origins: str = "http://localhost:3000"

    @property
    def cors_allowed_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_allowed_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
