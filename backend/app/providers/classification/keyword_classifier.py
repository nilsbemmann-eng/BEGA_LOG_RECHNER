"""Stichwortbasierter `DocumentClassifier` (Abschnitt 4.3).

Bewusst einfach und deterministisch gehalten: die Zuordnung ist fuer den
Pruefer nachvollziehbar (`scores` enthaelt die Rohwerte je Dokumenttyp) und
die Stichwortlisten sind konfigurierbar, ohne Code aendern zu muessen. Eine
Erweiterung um ein trainiertes Klassifikationsmodell ist moeglich, ohne die
`DocumentClassifier`-Schnittstelle zu aendern (Abschnitt 19: KI-Unterstuetzung
ja, aber austauschbar und nachvollziehbar).
"""
from __future__ import annotations

import re

from app.providers.base import ClassificationResult

# Reihenfolge relevant fuer Tie-Breaking bei gleicher Punktzahl: spezifischere
# Typen vor "sonstiges".
KEYWORDS_BY_DOCUMENT_TYPE: dict[str, list[str]] = {
    "frachtrechnung": ["rechnung", "invoice", "rechnungsnummer", "rechnungsbetrag", "netto", "brutto", "ust-idnr"],
    "ladeliste": ["ladeliste", "beladeliste", "packliste", "kolli", "colli", "sendungsliste", "tourenliste"],
    "transportauftrag": ["transportauftrag", "frachtauftrag", "auftragsbestaetigung", "spediteurauftrag"],
    "ablieferbeleg": ["ablieferbeleg", "empfangsbestaetigung", "pod", "proof of delivery", "unterschrift empfaenger"],
    "preisangebot": ["angebot", "kostenvoranschlag", "preisangebot", "offerte"],
    "mautnachweis": ["maut", "toll", "mautbeleg", "toll collect"],
    "wartezeitnachweis": ["wartezeit", "standzeit", "standgeld nachweis", "wartezeitbescheinigung"],
    "palettentauschbeleg": ["palettenschein", "palettentausch", "palettenkonto", "epal"],
}

_WORD_RE = re.compile(r"[a-zA-ZäöüßÄÖÜ]+")


class KeywordDocumentClassifier:
    def __init__(self, keywords_by_type: dict[str, list[str]] | None = None) -> None:
        self._keywords_by_type = keywords_by_type or KEYWORDS_BY_DOCUMENT_TYPE

    def classify(self, text: str, filename: str) -> ClassificationResult:
        haystack = f"{text}\n{filename}".lower()
        scores: dict[str, float] = {}
        for document_type, keywords in self._keywords_by_type.items():
            hits = sum(1 for keyword in keywords if keyword in haystack)
            scores[document_type] = hits / len(keywords) if keywords else 0.0

        best_type = max(scores, key=scores.get) if scores else "sonstiges"
        best_score = scores.get(best_type, 0.0)

        if best_score <= 0.0:
            return ClassificationResult(document_type="sonstiges", confidence=0.3, scores=scores)

        # Konfidenz: Anteil der Treffer, gedeckelt auf 0.98 (nie 1.0 - Modell bleibt unsicher).
        confidence = min(0.5 + best_score, 0.98)
        return ClassificationResult(document_type=best_type, confidence=confidence, scores=scores)
