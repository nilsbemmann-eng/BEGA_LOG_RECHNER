# Offene fachliche Entscheidungen

Dieses Dokument verfolgt die in Abschnitt 18 des technischen Berichts geforderten
offenen Entscheidungen. Für den MVP wurde bewusst **keine** dieser Fragen
stillschweigend fachlich entschieden. Stattdessen wurde jede Frage entweder als
**konfigurierbarer Wert** mit dokumentiertem, änderbarem Startwert umgesetzt,
oder als **manueller Prüfschritt** modelliert, der nie automatisch zu einer
endgültigen Ablehnung führt. Vor dem produktiven Einsatz müssen die unten
markierten Punkte mit dem Fachbereich final festgelegt werden.

| # | Frage | Status im MVP | Ort in der Implementierung |
|---|---|---|---|
| 1 | Welches E-Mail-System wird verwendet? | Offen fuer die automatische Postfach-Synchronisation. `EmailProvider`-Interface implementiert, MVP liefert einen generischen IMAP-Provider (`app/providers/email/imap_provider.py`). Zugangsdaten ausschließlich über Umgebungsvariablen/Secret-Management (`MAILBOX_*`). Ergaenzend koennen einzelne Outlook-`.msg`-Dateien manuell hochgeladen werden (`POST /api/emails/upload`, `app/providers/email/msg_file_parser.py`) - unabhaengig vom konfigurierten Postfach, fuer den Fall dass IMAP-Zugang (noch) nicht eingerichtet ist oder eine einzelne E-Mail gezielt nachgereicht werden soll. | `app/providers/base.py`, `app/providers/email/` |
| 2 | Welche Dokumenttypen liegen tatsächlich vor? | MVP deckt alle 9 Typen aus Abschnitt 4.3 als Enum ab; Klassifikator ist stichwortbasiert und konfigurierbar. | `app/models/document.py::DocumentType`, `app/providers/classification/keyword_classifier.py` |
| 3 | Welche OCR-Qualität ist erforderlich? | Fuer Scans/Fotos umgesetzt: `LlmVisionOcrProvider` (`ocr_provider=llm_vision`) nutzt ein multimodales Claude-Modell zur Felderkennung inkl. Begründung je Feld (Abschnitt 19); Zahlen werden weiterhin deterministisch über `app/normalization/numbers.py` normalisiert, nicht vom Modell selbst berechnet. Daneben weiterhin: `PdfTextOcrProvider` fuer PDFs mit Textebene und `DummyOcrProvider` fuer Tests. Offen: welches Modell/welcher Anbieter produktiv gesetzt wird (Kosten pro Dokument, Datenschutz bei Versand an einen externen Dienst) sowie ob zusaetzlich ein guenstigerer klassischer OCR-Anbieter (Tesseract, Azure/AWS/Google) fuer einfache Faelle sinnvoll ist. | `app/providers/ocr/` |
| 4 | Welche Frachtführer und Tarifmodelle müssen zuerst unterstützt werden? | Fachlich präzisiert (BEGA-Finetuning, siehe Abschnitt "BEGA-Preislogik" unten): bis zu 100 Subunternehmer mit individuellem km-Preis (`Tariff.carrier_id`, je Frachtführer eigener Tarif); `BASE_PLUS_KM` mit optionaler länderabhängiger km-Preistabelle sowie `ALL_IN` als Fixfracht-Preisliste je Länderpaar (nur bei 1 Entladestelle) werden berechnet. Weitere Regeltypen bleiben als Enum vorbereitet, aber nicht berechnet (siehe `TariffRuleType`). | `app/models/tariff.py`, `app/tariff_engine/engine.py` |
| 5 | Werden Kilometer nach Lkw-, Pkw- oder vertraglicher Route berechnet? | Startwert: Lkw-Route (`profile=truck`), konfigurierbar je Tarif/Sendung über `routing_profile`. Referenzrouten für alle drei Varianten können parallel gespeichert werden (`RoutingResult.routing_profile`). | `app/models/routing.py`, `app/providers/routing/` |
| 6 | Welche Toleranzen gelten je Relation? | Startwerte aus Abschnitt 5.3 (±8 % Standard, ±12 % Innenstadt/schwer zugänglich, Sonderfälle → manuelle Prüfung), konfigurierbar über `DistanceToleranceConfig`. | `app/distance_engine/deviation.py`, `app/config.py` |
| 7 | Welche Nachweise sind für welche Zusatzfrachten Pflicht? | Startbelegung in `EVIDENCE_REQUIRED_SURCHARGE_TYPES` (Wartezeit, ADR, Fähre/Insel, Hebebühne, Palettentausch, Standgeld, Fehlfahrt, erfolglose Zustellung erfordern Nachweis). Muss mit Fachbereich/Vertrag abgeglichen werden. | `app/surcharge_engine/engine.py` |
| 8 | Wie werden Maut und Dieselzuschlag vertraglich berechnet? | Offen. Im MVP als generische, manuell/vertraglich hinterlegte `SurchargeType`-Positionen mit Einheitspreis modelliert (keine automatische Mautstreckenberechnung, siehe Nichtziel Abschnitt 1.2). | `app/models/surcharge.py` |
| 9 | Welche Währungen und Länder werden unterstützt? | MVP: EUR als Standardwährung, `CurrencyProvider`-Interface vorbereitet, keine Umrechnung implementiert. Länder uneingeschränkt (ISO-3166 `country_code` in `addresses`). | `app/providers/base.py::CurrencyProvider` |
| 10 | Wie lange müssen Dokumente und Prüfergebnisse aufbewahrt werden? | Offen. Konfigurierbarer Parameter `RETENTION_DAYS_DOCUMENTS` / `RETENTION_DAYS_AUDIT_RESULTS` vorbereitet, kein automatisches Löschen im MVP implementiert. | `app/config.py` |
| 11 | Soll die Anwendung mit D365, TMS, ERP oder Finanzsystemen integriert werden? | Nein, nicht im MVP (siehe Nichtziel Abschnitt 1.2). Export nach XLSX/CSV als Übergabeformat vorgesehen. | `app/providers/export/` |
| 12 | Wer darf Preise freigeben oder eine Rückfrage an den Frachtführer auslösen? | Rollenmodell `admin` / `pruefer` / `viewer` vorbereitet (Abschnitt 3), Freigabe-Endpunkte (`/audits/{id}/approve`, `/audits/{id}/request-information`) sind auf Rolle `pruefer`/`admin` beschränkt. Konkrete Freigabegrenzen (z. B. Betragsschwellen für Vier-Augen-Prinzip) sind offen. | `app/models/user.py`, `app/api/routers/audits.py` |

## Weitere im Bericht geforderte, aber nicht endgültig entschiedene Punkte

- **Authentifizierung**: Abschnitt 10.3 fordert OAuth2/OIDC. Der MVP enthält nur
  eine Rollenmodellierung in der Datenbank sowie einen austauschbaren
  Auth-Dependency-Stub (`app/auth.py`); die Anbindung an einen konkreten
  Identity Provider (Azure AD, Keycloak, Auth0 …) ist offen und muss vor dem
  produktiven Einsatz ergänzt werden.
- **Objektspeicher/Verschlüsselung**: Anhänge werden im MVP über eine
  `StorageBackend`-Abstraktion referenziert (`storage_reference`); die
  produktive Anbindung an einen verschlüsselten Object Store (S3-kompatibel,
  Azure Blob …) ist vorbereitet, aber nicht implementiert (lokales
  Dateisystem als Dev-Fallback).
- **Mandantentrennung**: Datenmodell sieht keine Mandanten-ID vor MVP-Umfang
  vor; als Erweiterung dokumentiert (Nichtziel Abschnitt 1.2).
- **Hintergrundverarbeitung**: Lang laufende Jobs (E-Mail-Sync, OCR, Routing,
  Import, Export) sind im MVP als synchrone Service-Funktionen implementiert,
  die aus einer Job-Queue (Redis/RabbitMQ, siehe Abschnitt 10.3) heraus
  aufrufbar sind. Die eigentliche Queue-Anbindung ist nicht Teil des MVP.
- **Preistoleranz (Regel "Preis", Tabelle 8.1)**: Der Bericht nennt fuer die
  Preisgrenze keinen Startwert (anders als bei der Kilometertoleranz,
  Abschnitt 5.3). Startwert im MVP: ±5 % Abweichung zwischen Rechnungsbetrag
  und Sollpreis (`PRICE_DEVIATION_TOLERANCE_PERCENT`). Muss vor
  Produktivbetrieb fachlich bestaetigt werden.
- **Plausibilitaetsgrenzen (Regel "Plausibilitaet", Tabelle 8.1)**: Startwerte
  im MVP sind Gewicht ≤ 24.000 kg und Lademeter ≤ 13,6 (Standard-Sattelauflieger).
  Beide Werte sind ueber `app/config.py` konfigurierbar und muessen an die
  tatsaechlich eingesetzte Fahrzeugflotte angepasst werden.

## BEGA-Preislogik (Finetuning-Gespräch)

Auf Rückfrage wurden folgende Praxisregeln bestätigt und wie folgt umgesetzt
(`app/tariff_engine/engine.py`):

- **Grundprinzip**: Bei genau 1 Entladestelle kann eine Fixfracht-Preisliste
  (`TariffRuleType.ALL_IN`, Parameter `prices`) gelten; existiert kein
  passender Eintrag oder gibt es mehr als 1 Entladestelle, wird stattdessen
  `base_plus_km` gerechnet. Beide Regeltypen können im selben Tarif
  nebeneinander existieren ("situationsabhängig", je nach Frachtführer/Relation).
- **Länderabhängiger km-Preis**: `base_plus_km.parameters.price_per_km_by_country`
  hält einen Satz je Land. Sind Herkunfts- **und** Zielland hinterlegt, gilt
  der Satz des **teureren** Landes (Bestätigung: "bei mehreren Ländern gilt
  der Tarif des teuersten Landes"). **Offen/vereinfacht:** bei mehr als einer
  Entladestelle mit unterschiedlichen Ländern wird aktuell nur
  Herkunfts-/Erst-Zielland betrachtet, da einzelne Zwischenstopps noch nicht
  als eigene Adressen modelliert sind (nur `unloading_point_count` als Zahl,
  siehe unten). Muss bestätigt werden, sobald Mehrfach-Entladestellen mit
  unterschiedlichen Ländern in der Praxis vorkommen.
- **Zusätzliche Entladestellen**: `Shipment.unloading_point_count` (Standard 1)
  erfasst die Gesamtzahl der Entladestellen einer Sendung. Ab der 2. wird pro
  Stopp ein fixer Zuschlag berechnet - Standardwert 50 EUR
  (`DEFAULT_ADDITIONAL_UNLOADING_POINT_PRICE_EUR`), je Tarif über den
  Parameter `additional_unloading_point_price` überschreibbar. Dieser Zuschlag
  ist Teil der deterministischen Sollpreisberechnung (nicht der
  Zusatzfracht-Prüfung aus Abschnitt 7) und erfordert daher keinen Nachweis.
- **Fixfracht-Granularität**: `ALL_IN`-Preislisten sind aktuell nur nach
  Länderpaar geschlüsselt (`origin_country`/`destination_country`), nicht nach
  PLZ-Zone oder konkreter Relation. Falls die realen Fixfracht-Tabellen feiner
  gestaffelt sind (z. B. je Postleitzahlengebiet), muss das Schema in
  `all_in.parameters.prices` entsprechend erweitert werden.
- **Bis zu 100 Subunternehmer**: unterstützt ohne Codeänderung - jeder
  Subunternehmer ist ein `Carrier`-Datensatz mit eigenem/eigenen `Tariff`(en)
  und damit eigenem km-Preis/eigener Fixfracht-Tabelle.

## Scan-Erkennung und Unterschriften (Finetuning-Gespräch)

- **Vision-LLM-OCR**: `app/providers/ocr/llm_vision_provider.py` erkennt
  Felder auf Scans/Fotos (nicht nur PDFs mit Textebene) über ein multimodales
  Claude-Modell, inkl. kurzer Begründung je Feld (`ExtractedField.source_text`)
  und ehrlich eingeschätzter Konfidenz (high/medium/low, siehe
  `_CONFIDENCE_BY_LEVEL`). Bewusstes Architekturprinzip (Abschnitt 19): das
  Modell liest nur ab, es rechnet nicht - Zahlen werden serverseitig
  deterministisch über den gleichen Parser normalisiert wie beim
  PDF-Text-Provider.
- **Unterschriftenerkennung (perspektivisch)**: erster Schritt bereits
  umgesetzt - pro Seite wird eine reine Anwesenheitserkennung
  (`signature_present: true/false`) als `ExtractedField` gespeichert, z. B.
  fuer die Nachweis-Prüfung bei Ablieferbelegen. **Nicht** enthalten und noch
  offen:
  - Lokalisierung der Unterschrift (Bounding Box) auf der Seite.
  - Verifikation/Abgleich gegen eine hinterlegte Referenzunterschrift
    (Identitaetspruefung) - das waere ein eigenes, deutlich aufwendigeres
    Feature (spezialisiertes Modell oder Cloud-Dienst) und nur sinnvoll, wenn
    die reine Anwesenheitspruefung in der Praxis nicht ausreicht.
- **Kosten/Datenschutz**: jede Scan-Seite wird als Bild an die Anthropic-API
  gesendet. Vor Produktivbetrieb klären: Kosten pro Dokument/Seite (begrenzt
  ueber `OCR_VISION_MAX_PAGES`), Auftragsverarbeitungsvertrag mit Anthropic,
  und ob personenbezogene Daten auf den Scans das zulassen (Abschnitt 13).

**Grundsatz:** Kein Fall wird aufgrund eines fehlenden Nachweises oder eines
niedrigen OCR-Konfidenzwerts automatisch endgültig abgelehnt. Das Ergebnis ist
in diesen Fällen immer `MANUELLE_PRÜFUNG` (siehe `app/audit_engine/`).

## Tour-Preisprüfung / Ladelisten-PDF-Import (Finetuning-Gespräch, reale Stylinart-PDFs)

- **Eine Rechnung pro Tour**: Nutzerbestätigung - eine Frachtrechnung bezieht
  sich auf die gesamte Tour/Ladeliste (potenziell viele Aufträge/Entladestellen),
  nicht auf eine Einzelsendung. Neues `Tour`-Modell (`app/models/tour.py`)
  bündelt mehrere `Shipment`-Zeilen; `AuditResult.shipment_id` ist jetzt
  nullable, `AuditResult.tour_id` alternativ gesetzt (siehe
  `app/services/audit_service.py::run_tour_audit`).
- **Entladestellen-Deduplizierung**: mehrere Auftrags-Nr. können dieselbe
  physische Entladestelle teilen, und dieselbe Adresse kann mit
  unterschiedlichen Name1/Name2-Zeilen erscheinen (z. B. "Mitnahmelager
  Pulheim" vs. "Hans Segmüller GmbH & Co. KG" für dieselbe Adresse in
  D-50259 Pulheim) - Nutzerbestätigung: das ist reine Namens-Granularität der
  Kundenadresse, keine getrennten Stopps. Die Zählung "Anzahl Entladestellen"
  je Tour erfolgt daher über eindeutige (PLZ, Ort)-Paare, nicht über
  Adresstext oder Auftrags-Nr.
- **Zahlenformat im Ladelisten-PDF weicht vom sonstigen "deutschen Format" ab**:
  In der Spalte "kg / cbm" ist die kg-Zeile immer eine Ganzzahl (Punkt als
  Tausendertrennzeichen, z. B. "3.504" = 3504 kg), die cbm-Zeile dagegen immer
  ein Dezimalwert mit Punkt als Dezimaltrennzeichen und fixen 3 Nachkommastellen
  (z. B. "0.499" = 0,499 m³) - **nicht** die sonst im Projekt verwendete
  deutsche Konvention (Komma=Dezimal, Punkt=Tausender, siehe
  `app/normalization/numbers.py`). Ein einzelner realer Beleg enthielt zudem
  einen Ausreißer mit Komma statt Punkt ("3,893" statt vermutlich "3.893");
  der Parser (`app/services/ladeliste_pdf_parser.py`) behandelt Komma und
  Punkt in der kg-Zeile daher gleichwertig als Tausendertrennzeichen. Das ist
  eine reale, unsaubere Quelldatenabweichung, kein Parserfehler - Summen
  können dadurch in Einzelfällen um 1 kg von der gedruckten SUMME abweichen.
- **Ursprungsadresse/-land für Fixfracht-Zuordnung und km-Prüfung ("Absender-Matrix")**:
  Ladelisten enthalten keine Beladeadresse. Nutzervorgabe: die ersten 2
  Ziffern der Ladelistennummer ("Präfix") bestimmen den Abgangsort - dafür
  wurde die reale Stammdatentabelle "Gebietsrelationen.xlsx" bereitgestellt
  und als `TourOriginMapping`-Modell abgebildet
  (`app/services/tour_origin_service.py`, `app/services/tour_origin_import_service.py`,
  Import über `POST /api/tour-origin-mappings/import`, CRUD über
  `/api/tour-origin-mappings`).
  - **Wichtige Erkenntnis aus den echten Daten**: ein Präfix ist NICHT
    eindeutig einem Absender zugeordnet - mehrere "Matchcodes" (Relationen)
    können denselben Präfix teilen, teils mit unterschiedlichen Adressen
    (z. B. Präfix 12: ein Matchcode zeigt in die Ukraine, ein anderer nach
    Mielec/Polen). Ein Matchcode selbst ist ebenfalls nicht global eindeutig
    (kann bei unterschiedlichen Präfixen wiederkehren).
  - **Nutzervorgabe zur Auflösung**: zeigen alle für einen Präfix hinterlegten
    Zeilen mit Adresse auf dieselbe Adresse, wird sie automatisch verwendet.
    Bei widersprüchlichen Adressen unter demselben Präfix bleibt die Tour
    bewusst `MANUELLE_PRUEFUNG` (keine Adresse wird geraten) - die
    widersprüchlichen Matchcodes werden in der Prüfbegründung genannt.
  - Fehlt jede Zuordnung für einen Präfix, greift für die Fixfracht-Länderpaar-
    Zuordnung weiterhin der globale Standardwert
    `Settings.default_tour_origin_country_code` (`"PL"`) - nur die
    Kilometerprüfung selbst bleibt dann offen (kein Startpunkt für die Route).
  - Ein Import der Excel-Datei **ersetzt die gesamte Absender-Matrix**
    (vollständige Referenztabelle, kein inkrementelles Update).
- **Kilometerprüfung über OSM für Touren (Nutzervorgabe "km Prüfung über OSM")**:
  `run_tour_audit()` berechnet die Referenzstrecke als Summe der Einzeletappen
  Depot -> Entladestelle 1 -> ... -> Entladestelle N (Ladelisten-Reihenfolge,
  über PLZ/Ort dedupliziert), sofern ein eindeutiger Startpunkt (Absender-Matrix)
  und alle Entladestellen geokodierbar sind - **nicht** eine einzelne
  OSRM-Mehrstopp-Anfrage. Das ist eine dokumentierte Näherung (Summe der
  Teilstrecken kann geringfügig von einer echten Rundtour-Optimierung
  abweichen). Ohne auflösbaren Startpunkt bleibt die Kilometerprüfung
  `MANUELLE_PRUEFUNG`, die Preis-/Tarifprüfung läuft davon unabhängig weiter.

## Reale Tour-Preisformel (Finetuning: "Preise_2026_fuer_Wolke.xlsm")

Der Nutzer hat BEGAs aktuelles, manuell in Excel gepflegtes Preisprüfblatt für
2026 bereitgestellt (ein Tabellenblatt je Kalenderwoche + Stammdaten). Die
darin enthaltenen Formeln sind die tatsächliche, bislang manuelle
Geschäftslogik und wurden 1:1 nachgebaut (`app/tariff_engine/engine.py`,
`app/services/audit_service.py::run_tour_audit`), soweit automatisierbar:

```
FrachtpreisBEGA = ROUNDUP(
    stops_surcharge(Spedition, alleStops)
  + Gesamtstrecke * €/km(Spedition, Praefix, Land)
  + MautstreckeGermany * 0,158 €/km
  + Sondervereinbarung_Zuschlag(Praefix)
, 0)

genehmigt = "Ok" wenn FrachtpreisBEGA >= Frachtpreisallin (Rechnungsbetrag), sonst "notok"
```

Wichtigste Unterschiede zur vorherigen MVP-Annahme (jetzt korrigiert):

- **Keine Fixfracht/`all_in`-Preisliste je Länderpaar** in der realen Formel -
  `run_tour_audit` ruft `calculate_expected_price(..., use_fixed_freight=False)`
  auf, sodass Touren immer über den kilometerbasierten Pfad (`base_plus_km`)
  berechnet werden. Die `all_in`-Regel bleibt im Datenmodell erhalten (falls
  doch einmal eine echte Fixfracht-Vereinbarung existiert), wird aber für
  Touren nicht mehr automatisch verwendet.
- **Maut-Kosten**: neues Feld `Tour.toll_km` (mautpflichtige Teilstrecke in
  Deutschland, analog zu `MautstreckeGermany`) × `Settings.default_toll_rate_per_km_eur`
  (Standard 0,158 EUR/km). Frachtführer mit `toll_exempt: true` im
  `base_plus_km`-Tarifparameter (real: BABINSKI, SANMAR) zahlen keine Maut.
  `toll_km` wird aktuell nicht automatisch berechnet (keine
  Land-Zuordnung je Streckenabschnitt in der Routing-Engine) - Eingabe manuell
  oder aus einer künftigen Anbindung an das im Excel referenzierte
  "BegaPlanningModul" (Tour-Planungssoftware), **offen**.
- **Sondervereinbarungs-Zuschlag**: neues Stammdaten-Modell
  `SpecialAgreementSurcharge` (Praefix -> fixer Betrag, CRUD über
  `/api/special-agreement-surcharges`) statt hart codierter Präfix-Liste im
  Excel (real: 19, 36, 46, 52, 57, 79, 28, 15, je 100 EUR) - damit ohne
  Codeänderung pflegbar.
- **Carrier-spezifischer Entladestellen-Zuschlag** (real: BABINSKI 60 EUR,
  MAGPOL 70 EUR, Zieja 0 EUR, sonst 50 EUR) war über
  `TariffRule.parameters["additional_unloading_point_price"]` bereits
  abbildbar - nur die tatsächlichen Werte müssen je Frachtführer-Tarif
  gepflegt werden.
- **Manuelle Praefix+Land-Sonder-km-Sätze**: neuer Tarifparameter
  `base_plus_km.parameters.prefix_country_rate_overrides` (siehe
  `app/tariff_engine/engine.py`) für Ausnahmen wie PAWLICHA+Präfix 78+DE
  → 1,30 EUR/km statt Standardsatz. **Offene Frage, nicht vom Nutzer
  beantwortet**: die Ausnahmeliste unterscheidet sich zwischen den
  Excel-Tabellenblättern `BLANKO` (3 Ausnahmen) und `Vergleich` (dieselben 3
  plus eine zusätzliche PASTERNAK+Präfix{29,78}+AT-Regel) - es wurde die
  **Vereinigungsmenge** beider Listen als Ausgangsbasis übernommen
  (pragmatische Annahme, da vollständiger als beide Einzellisten); vor
  Produktivbetrieb mit dem Nutzer verifizieren, welche Liste aktuell gültig
  ist.
- **Genehmigungsregel ist einseitig, ohne Toleranzband**: neuer
  `AuditRuleInput.price_tolerance_mode = "invoice_must_not_exceed_expected"`
  (siehe `app/audit_engine/rule_engine.py`) - der Rechnungsbetrag darf den
  Sollpreis in keiner Höhe übersteigen (`FAILED`), ein niedrigerer Betrag ist
  unbegrenzt unproblematisch (`PASSED`). Wird bislang nur von
  `run_tour_audit` verwendet; `run_audit` (Einzelsendungen aus CSV/XLSX-Import)
  bleibt beim bisherigen symmetrischen Prozent-Toleranzband, da für diesen
  Ablauf keine gegenteilige reale Evidenz vorliegt.
- **Rundung auf den vollen Euro (`ROUNDUP`)**: neue Hilfsfunktion
  `app/money.py::round_up_to_whole_currency_unit` (kaufmännisches Runden auf
  2 Nachkommastellen bleibt für alle anderen Preisberechnungen im Projekt
  unverändert Standard) - nur `run_tour_audit` rundet den Gesamt-Sollpreis
  wie im Excel auf den nächsten vollen Euro auf.
- **Frachtführer-Preistabelle ("Stammdaten")**: ca. 90 Frachtführer × ca. 52
  Länder EUR/km-Matrix, importierbar über
  `POST /api/tariffs/import-rate-matrix` (.xlsm/.xlsx,
  `app/services/carrier_rate_import_service.py`). Nicht-numerische Zellen
  ("keine" = kein Service, "zu teuer", "Sonderregelung", "?") werden bewusst
  übersprungen statt als 0 interpretiert. Jeder Import legt pro Frachtführer
  eine neue Tarifversion an (Tarife sind unveränderlich, siehe
  `app/models/tariff.py`) und übernimmt `additional_unloading_point_price`/
  `toll_exempt`/`prefix_country_rate_overrides` der vorherigen Version
  unverändert, da diese Parameter nicht aus der Stammdaten-Tabelle stammen.
- **`Gesamtstrecke`/`MautstreckeGermany` sind im heutigen manuellen Prozess
  extern befüllt** (vermutlich aus dem im Excel referenzierten
  "BegaPlanningModul", einer separaten Tourenplanungssoftware), nicht live
  berechnet - unsere OSM/OSRM-basierte automatische Kilometerermittlung ist
  also eine echte Weiterentwicklung, keine Nachbildung des Ist-Zustands.

## Routing-Provider: TomTom (Nutzervorgabe)

- **TomTom statt/zusätzlich zu OSRM**: neuer `TomTomRoutingProvider`
  (`app/providers/routing/tomtom_provider.py`), austauschbar über
  `Settings.routing_provider = "tomtom"` (Provider-Pattern, siehe
  `app/providers/factory.py`) - unterstützt echtes Lkw-Routing
  (`travelMode=truck`) über TomToms Calculate-Route-API, im Gegensatz zum
  öffentlichen OSRM-Demo-Server, der nur `driving` kennt.
- **API-Key admin-pflegbar statt nur Umgebungsvariable** (Nutzervorgabe):
  neues Modell `IntegrationCredential` speichert den TomTom-API-Key
  verschlüsselt (Fernet, `app/services/credential_encryption.py`) in der
  Datenbank, pflegbar über `PUT/DELETE /api/integration-credentials/{key}`
  (nur Administrator-Rolle). Der Klartextwert wird über die API **nie**
  zurückgegeben - nur ob/wann ein Wert hinterlegt wurde. Der
  Verschlüsselungsschlüssel selbst (`CREDENTIAL_ENCRYPTION_KEY`) bleibt eine
  reine Umgebungsvariable (darf nie in der Datenbank stehen, sonst wäre die
  Verschlüsselung wertlos). `Settings.tomtom_api_key` (Umgebungsvariable)
  bleibt als Bootstrap-Fallback bestehen, falls noch kein
  `CREDENTIAL_ENCRYPTION_KEY` konfiguriert oder noch kein Wert über die API
  gesetzt ist - der DB-Wert hat Vorrang, sobald er existiert.
- **Offen**: der Nutzer hat einen echten TomTom-API-Key über einen
  Claude-MCP-Connector bereitgestellt, nicht direkt im Chat oder als
  Umgebungsvariable - ein MCP-Connector ist nur für Claude selbst innerhalb
  dieser Unterhaltung nutzbar, nicht für das laufende Backend. Der
  tatsächliche Schlüssel muss vom Nutzer selbst über
  `PUT /api/integration-credentials/tomtom_api_key` eingetragen werden
  (Admin-Rolle erforderlich), sobald `CREDENTIAL_ENCRYPTION_KEY` konfiguriert
  ist.
