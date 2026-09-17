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
    routing_provider: str = "osrm"  # osrm | tomtom (Nutzervorgabe: TomTom fuer Routing)
    osrm_base_url: str = "https://router.project-osrm.org"
    default_routing_profile: str = "truck"  # siehe docs/OFFENE_ENTSCHEIDUNGEN.md Punkt 5

    # --- TomTom (nur bei routing_provider=tomtom) ---
    # tomtom_api_key ist nur der Bootstrap-Fallback (z. B. fuer lokale
    # Entwicklung) - im Betrieb wird der Schluessel bevorzugt admin-pflegbar
    # ueber /api/integration-credentials verschluesselt in der DB gespeichert
    # (siehe app/services/integration_credential_service.py, Nutzervorgabe).
    tomtom_api_key: str | None = None
    tomtom_base_url: str = "https://api.tomtom.com"

    # --- Verschluesselung admin-pflegbarer Zugangsdaten (Abschnitt 13) ---
    # Muss eine Umgebungsvariable sein (Fernet.generate_key()), niemals in der
    # Datenbank - siehe app/services/credential_encryption.py.
    credential_encryption_key: str | None = None

    # --- OCR-Provider ---
    # pdf_text: nur PDFs mit eingebetteter Textebene (kein echter Scan).
    # llm_vision: Claude-Vision-basierte Erkennung fuer Scans/Fotos, benoetigt
    # ANTHROPIC_API_KEY (siehe docs/OFFENE_ENTSCHEIDUNGEN.md Punkt 3).
    # dummy: fuer Tests.
    ocr_provider: str = "pdf_text"
    ocr_min_auto_confidence: float = 0.95
    ocr_min_flagged_confidence: float = 0.80

    # --- Vision-LLM-OCR (nur bei ocr_provider=llm_vision) ---
    anthropic_api_key: str | None = None
    ocr_vision_model: str = "claude-sonnet-5"
    ocr_vision_max_pages: int = 5

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

    # --- Tour-Preispruefung (BEGA-Finetuning, Ladelisten-Import) ---
    # Ladelisten enthalten keine Beladeadresse/kein Ursprungsland (nur
    # Entladestellen). Nutzerangabe: der Frachtfuehrer laedt "in der Regel"
    # in Polen; eine feinere Zuordnung ueber die ersten 2 Ziffern der
    # Ladelistennummer ist angekuendigt, aber die Zuordnungstabelle liegt
    # noch nicht vor (siehe docs/OFFENE_ENTSCHEIDUNGEN.md). Bis dahin gilt
    # dieser globale Standardwert fuer alle Touren.
    default_tour_origin_country_code: str = "PL"

    # --- Maut (BEGA-Finetuning, reale Preisformel aus
    # "Preise_2026_fuer_Wolke.xlsm"): Kosten je mautpflichtigem km in
    # Deutschland (Tour.toll_km), je Tarif ueberschreibbar via
    # TariffRule-Parameter "toll_exempt" (siehe app/tariff_engine/engine.py).
    default_toll_rate_per_km_eur: float = 0.158

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
