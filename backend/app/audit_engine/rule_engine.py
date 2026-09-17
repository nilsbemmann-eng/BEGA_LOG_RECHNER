"""Pruefregel-Engine (Abschnitt 8).

Fuehrt alle Regeln aus Tabelle 8.1 gegen einen aufbereiteten `AuditRuleInput`
aus und leitet daraus den Gesamtstatus ab (Abschnitt 2). Diese Engine ist die
deterministische, versionierbare Kernkomponente aus Abschnitt 19: sie trifft
keine KI-Entscheidung, sondern wertet ausschliesslich zuvor berechnete,
nachvollziehbare Werte (Distanzabweichung, Sollpreis, Zuschlagsstatus, ...)
gegen feste Regeln aus.

Grundsatz (Abschnitt 13): ein niedriger OCR-Konfidenzwert oder ein fehlender
Nachweis fuehrt nie zu `FAILED`, sondern immer zu `MANUAL_REVIEW`.
"""
from __future__ import annotations

import enum
from dataclasses import dataclass, field
from decimal import Decimal

from app.distance_engine.deviation import DeviationClassification, DeviationOutcome


class RuleStatus(str, enum.Enum):
    PASSED = "passed"
    WARNING = "warning"
    FAILED = "failed"
    MANUAL_REVIEW = "manual_review"
    ERROR = "error"


class AuditStatus(str, enum.Enum):
    BESTANDEN = "BESTANDEN"
    ABWEICHUNG = "ABWEICHUNG"
    MANUELLE_PRUEFUNG = "MANUELLE_PRUEFUNG"
    FEHLER = "FEHLER"


@dataclass
class RuleOutcome:
    rule_code: str
    rule_name: str
    status: RuleStatus
    actual_value: str | None
    expected_value: str | None
    explanation: str


@dataclass
class AuditRuleInput:
    # Pflichtfelder
    shipment_number: str | None
    transport_date_present: bool
    origin_address_present: bool
    destination_address_present: bool
    invoice_amount_present: bool

    # OCR
    min_ocr_confidence: float | None
    ocr_auto_threshold: float
    ocr_flagged_threshold: float

    # Zuordnung
    is_unique_shipment_assignment: bool

    # Adresse
    origin_geocoded: bool
    destination_geocoded: bool

    # Distanz
    distance_outcome: DeviationOutcome | None

    # Tarif
    tariff_found: bool
    tariff_error_message: str | None

    # Preis
    price_difference_percent: Decimal | None
    price_tolerance_percent: Decimal
    # "symmetric_percent" (Standard, Abschnitt 8.1): |Abweichung| <= Toleranz-%.
    # "invoice_must_not_exceed_expected" (reale BEGA-Tour-Preisformel, siehe
    # docs/OFFENE_ENTSCHEIDUNGEN.md): Rechnungsbetrag darf den Sollpreis in
    # KEINER Hoehe uebersteigen (kein Toleranzband), ein niedrigerer
    # Rechnungsbetrag ist dagegen unbegrenzt unproblematisch.
    price_tolerance_mode: str = "symmetric_percent"

    # Zuschlag / Nachweis
    surcharge_statuses: list[str] = field(default_factory=list)  # Werte aus SurchargeEvaluationStatus

    # Duplikat
    is_duplicate: bool = False

    # Plausibilitaet
    weight_kg: Decimal | None = None
    loading_meters: Decimal | None = None
    max_plausible_weight_kg: Decimal = Decimal("24000")
    max_plausible_loading_meters: Decimal = Decimal("13.6")


def _check_mandatory_fields(data: AuditRuleInput) -> RuleOutcome:
    missing = []
    if not data.shipment_number:
        missing.append("Sendungsnummer")
    if not data.transport_date_present:
        missing.append("Transportdatum")
    if not data.origin_address_present:
        missing.append("Startadresse")
    if not data.destination_address_present:
        missing.append("Zieladresse")
    if not data.invoice_amount_present:
        missing.append("Rechnungsbetrag")

    if not missing:
        return RuleOutcome("mandatory_fields", "Pflichtfelder", RuleStatus.PASSED, "vollstaendig", "vollstaendig", "Alle Pflichtfelder sind vorhanden.")
    return RuleOutcome(
        "mandatory_fields", "Pflichtfelder", RuleStatus.MANUAL_REVIEW,
        f"fehlend: {', '.join(missing)}", "vollstaendig",
        f"Folgende Pflichtfelder fehlen und muessen manuell ergaenzt werden: {', '.join(missing)}.",
    )


def _check_ocr_confidence(data: AuditRuleInput) -> RuleOutcome:
    if data.min_ocr_confidence is None:
        return RuleOutcome("ocr_confidence", "OCR-Konfidenz", RuleStatus.MANUAL_REVIEW, None, f">= {data.ocr_auto_threshold}", "Kein OCR-Konfidenzwert vorhanden.")

    confidence = data.min_ocr_confidence
    if confidence >= data.ocr_auto_threshold:
        return RuleOutcome("ocr_confidence", "OCR-Konfidenz", RuleStatus.PASSED, str(confidence), f">= {data.ocr_auto_threshold}", "OCR-Konfidenz ausreichend fuer automatische Weiterverarbeitung.")
    if confidence >= data.ocr_flagged_threshold:
        return RuleOutcome(
            "ocr_confidence", "OCR-Konfidenz", RuleStatus.WARNING, str(confidence),
            f">= {data.ocr_auto_threshold}",
            f"OCR-Konfidenz {confidence} liegt zwischen {data.ocr_flagged_threshold} und {data.ocr_auto_threshold} "
            "- Weiterverarbeitung mit Kennzeichnung (Abschnitt 8.2).",
        )
    return RuleOutcome(
        "ocr_confidence", "OCR-Konfidenz", RuleStatus.MANUAL_REVIEW, str(confidence), f">= {data.ocr_flagged_threshold}",
        f"OCR-Konfidenz {confidence} liegt unter {data.ocr_flagged_threshold} - manuelle Erfassung/Bestaetigung erforderlich.",
    )


def _check_assignment(data: AuditRuleInput) -> RuleOutcome:
    if data.is_unique_shipment_assignment:
        return RuleOutcome("assignment", "Zuordnung", RuleStatus.PASSED, "eindeutig", "eindeutig", "Sendung wurde eindeutig zugeordnet.")
    return RuleOutcome("assignment", "Zuordnung", RuleStatus.MANUAL_REVIEW, "nicht eindeutig", "eindeutig", "Es liegt keine eindeutige Sendungszuordnung vor - manuelle Auswahl erforderlich.")


def _check_address(data: AuditRuleInput) -> RuleOutcome:
    if data.origin_geocoded and data.destination_geocoded:
        return RuleOutcome("address_geocoded", "Adresse", RuleStatus.PASSED, "Start und Ziel geocodiert", "geocodiert", "Start- und Zieladresse wurden erfolgreich geocodiert.")
    missing = []
    if not data.origin_geocoded:
        missing.append("Start")
    if not data.destination_geocoded:
        missing.append("Ziel")
    return RuleOutcome("address_geocoded", "Adresse", RuleStatus.MANUAL_REVIEW, f"nicht geocodiert: {', '.join(missing)}", "geocodiert", f"Adresse(n) konnten nicht geocodiert werden: {', '.join(missing)}.")


def _check_distance(data: AuditRuleInput) -> RuleOutcome:
    outcome = data.distance_outcome
    if outcome is None:
        return RuleOutcome("distance_tolerance", "Distanz", RuleStatus.MANUAL_REVIEW, None, None, "Keine Referenzroute berechnet - Kilometerpruefung nicht moeglich.")

    if outcome.classification == DeviationClassification.REQUIRES_MANUAL_REVIEW:
        return RuleOutcome(
            "distance_tolerance", "Distanz", RuleStatus.MANUAL_REVIEW, f"{outcome.deviation_percent:.1f} %", None,
            "Sonderroute (Faehre/Insel/Baustelle) - Kilometerabweichung erfordert manuelle Pruefung (Abschnitt 5.3).",
        )
    if outcome.classification == DeviationClassification.WITHIN_TOLERANCE:
        return RuleOutcome(
            "distance_tolerance", "Distanz", RuleStatus.PASSED, f"{outcome.deviation_percent:.1f} %",
            f"<= {outcome.tolerance_percent} %", "Kilometerabweichung liegt innerhalb der Toleranz.",
        )
    return RuleOutcome(
        "distance_tolerance", "Distanz", RuleStatus.FAILED, f"{outcome.deviation_percent:.1f} %",
        f"<= {outcome.tolerance_percent} %",
        f"Kilometerabweichung von {outcome.deviation_percent:.1f} % ueberschreitet die Toleranz von "
        f"{outcome.tolerance_percent} %.",
    )


def _check_tariff(data: AuditRuleInput) -> RuleOutcome:
    if data.tariff_found:
        return RuleOutcome("tariff_validity", "Tarif", RuleStatus.PASSED, "gueltig", "gueltig", "Transportdatum liegt im Gueltigkeitszeitraum eines eindeutigen, freigegebenen Tarifs.")
    return RuleOutcome(
        "tariff_validity", "Tarif", RuleStatus.MANUAL_REVIEW, data.tariff_error_message or "kein Tarif gefunden",
        "genau ein gueltiger Tarif", data.tariff_error_message or "Kein eindeutiger gueltiger Tarif gefunden.",
    )


def _check_price(data: AuditRuleInput) -> RuleOutcome:
    if data.price_difference_percent is None:
        return RuleOutcome("price_limit", "Preis", RuleStatus.MANUAL_REVIEW, None, None, "Sollpreis konnte nicht berechnet werden.")

    if data.price_tolerance_mode == "invoice_must_not_exceed_expected":
        if data.price_difference_percent <= 0:
            return RuleOutcome(
                "price_limit", "Preis", RuleStatus.PASSED, f"{data.price_difference_percent:.2f} %",
                "<= 0 %", "Rechnungsbetrag liegt nicht ueber dem Sollpreis.",
            )
        return RuleOutcome(
            "price_limit", "Preis", RuleStatus.FAILED, f"{data.price_difference_percent:.2f} %", "<= 0 %",
            f"Rechnungsbetrag liegt {data.price_difference_percent:.2f} % ueber dem Sollpreis - "
            "die reale Tour-Preisformel kennt kein Toleranzband nach oben.",
        )

    if abs(data.price_difference_percent) <= data.price_tolerance_percent:
        return RuleOutcome(
            "price_limit", "Preis", RuleStatus.PASSED, f"{data.price_difference_percent:.2f} %",
            f"<= {data.price_tolerance_percent} %", "Rechnungsbetrag liegt innerhalb der Preisgrenze.",
        )
    return RuleOutcome(
        "price_limit", "Preis", RuleStatus.FAILED, f"{data.price_difference_percent:.2f} %",
        f"<= {data.price_tolerance_percent} %",
        f"Preisabweichung von {data.price_difference_percent:.2f} % ueberschreitet die Toleranz von "
        f"{data.price_tolerance_percent} %.",
    )


def _check_surcharges(data: AuditRuleInput) -> RuleOutcome:
    if not data.surcharge_statuses:
        return RuleOutcome("surcharge_allowed", "Zuschlag", RuleStatus.PASSED, "keine Zusatzfrachten", "keine Zusatzfrachten", "Keine Zusatzfrachten geltend gemacht.")
    if any(status == "manual_review" for status in data.surcharge_statuses):
        return RuleOutcome("surcharge_allowed", "Zuschlag", RuleStatus.MANUAL_REVIEW, "manuelle Pruefung ausstehend", "vertraglich gedeckt", "Mindestens eine Zusatzfracht erfordert manuelle Pruefung (siehe Nachweis-Regel).")
    if any(status == "partially_allowed" for status in data.surcharge_statuses):
        return RuleOutcome("surcharge_allowed", "Zuschlag", RuleStatus.WARNING, "teilweise gedeckt", "vollstaendig gedeckt", "Mindestens eine Zusatzfracht ist nur teilweise vertraglich gedeckt.")
    return RuleOutcome("surcharge_allowed", "Zuschlag", RuleStatus.PASSED, "vollstaendig gedeckt", "vollstaendig gedeckt", "Alle Zusatzfrachten sind vertraglich gedeckt.")


def _check_evidence(data: AuditRuleInput) -> RuleOutcome:
    missing_evidence_count = sum(1 for status in data.surcharge_statuses if status == "manual_review")
    if missing_evidence_count == 0:
        return RuleOutcome("evidence_present", "Nachweis", RuleStatus.PASSED, "vollstaendig", "vollstaendig", "Alle erforderlichen Nachweise liegen vor.")
    return RuleOutcome(
        "evidence_present", "Nachweis", RuleStatus.MANUAL_REVIEW, f"{missing_evidence_count} fehlend", "vollstaendig",
        f"Fuer {missing_evidence_count} Zusatzfracht(en) fehlt ein erforderlicher Nachweis.",
    )


def _check_duplicate(data: AuditRuleInput) -> RuleOutcome:
    if data.is_duplicate:
        return RuleOutcome("duplicate_check", "Duplikat", RuleStatus.FAILED, "Duplikat erkannt", "kein Duplikat", "Diese Rechnung bzw. dieser Anhang wurde bereits verarbeitet.")
    return RuleOutcome("duplicate_check", "Duplikat", RuleStatus.PASSED, "kein Duplikat", "kein Duplikat", "Kein Duplikat erkannt.")


def _check_plausibility(data: AuditRuleInput) -> RuleOutcome:
    issues = []
    if data.weight_kg is not None and (data.weight_kg <= 0 or data.weight_kg > data.max_plausible_weight_kg):
        issues.append(f"Gewicht {data.weight_kg} kg ausserhalb des plausiblen Bereichs (0, {data.max_plausible_weight_kg}]")
    if data.loading_meters is not None and (data.loading_meters <= 0 or data.loading_meters > data.max_plausible_loading_meters):
        issues.append(f"Lademeter {data.loading_meters} ausserhalb des plausiblen Bereichs (0, {data.max_plausible_loading_meters}]")

    if not issues:
        return RuleOutcome("plausibility", "Plausibilitaet", RuleStatus.PASSED, "plausibel", "plausibel", "Gewicht und Lademeter sind fachlich plausibel.")
    return RuleOutcome("plausibility", "Plausibilitaet", RuleStatus.MANUAL_REVIEW, "; ".join(issues), "plausibel", "; ".join(issues))


_ALL_CHECKS = [
    _check_mandatory_fields,
    _check_ocr_confidence,
    _check_assignment,
    _check_address,
    _check_distance,
    _check_tariff,
    _check_price,
    _check_surcharges,
    _check_evidence,
    _check_duplicate,
    _check_plausibility,
]


def run_audit_rules(data: AuditRuleInput) -> list[RuleOutcome]:
    return [check(data) for check in _ALL_CHECKS]


# Rangfolge fuer die Ableitung des Gesamtstatus: der "schlechteste" Einzelstatus
# gewinnt (Abschnitt 8.3: eine einzelne verletzte Regel reicht fuer
# MANUELLE_PRUEFUNG bzw. ABWEICHUNG).
_STATUS_SEVERITY = {
    RuleStatus.PASSED: 0,
    RuleStatus.WARNING: 1,
    RuleStatus.FAILED: 2,
    RuleStatus.MANUAL_REVIEW: 3,
    RuleStatus.ERROR: 4,
}


def derive_overall_status(rule_outcomes: list[RuleOutcome]) -> AuditStatus:
    if any(outcome.status == RuleStatus.ERROR for outcome in rule_outcomes):
        return AuditStatus.FEHLER
    if any(outcome.status == RuleStatus.MANUAL_REVIEW for outcome in rule_outcomes):
        return AuditStatus.MANUELLE_PRUEFUNG
    if any(outcome.status in (RuleStatus.FAILED, RuleStatus.WARNING) for outcome in rule_outcomes):
        return AuditStatus.ABWEICHUNG
    return AuditStatus.BESTANDEN


def build_explanation(rule_outcomes: list[RuleOutcome]) -> str:
    """Erzeugt eine fuer den Sachbearbeiter verstaendliche Gesamtbegruendung
    (Abschnitt 8.3, Akzeptanzkriterium 16.5)."""
    problematic = [o for o in rule_outcomes if o.status != RuleStatus.PASSED]
    if not problematic:
        return "Alle Pruefregeln wurden erfolgreich bestanden."
    return " ".join(f"[{o.rule_name}] {o.explanation}" for o in problematic)
