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
| 1 | Welches E-Mail-System wird verwendet? | Offen. `EmailProvider`-Interface implementiert, MVP liefert einen generischen IMAP-Provider (`app/providers/email/imap_provider.py`). Zugangsdaten ausschließlich über Umgebungsvariablen/Secret-Management (`MAILBOX_*`). | `app/providers/base.py`, `app/providers/email/` |
| 2 | Welche Dokumenttypen liegen tatsächlich vor? | MVP deckt alle 9 Typen aus Abschnitt 4.3 als Enum ab; Klassifikator ist stichwortbasiert und konfigurierbar. | `app/models/document.py::DocumentType`, `app/providers/classification/keyword_classifier.py` |
| 3 | Welche OCR-Qualität ist erforderlich? | Offen. MVP enthält `DocumentOcrProvider`-Interface plus zwei Implementierungen: einen Text-/Tabellen-Extraktor für PDFs mit Textebene (`pdf_text_provider.py`) und einen `DummyOcrProvider` für Tests. Cloud-OCR (Azure Document Intelligence, AWS Textract, Google Document AI) oder Tesseract für gescannte Bilder ist als Erweiterung vorgesehen, aber nicht produktiv angebunden. | `app/providers/ocr/` |
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

**Grundsatz:** Kein Fall wird aufgrund eines fehlenden Nachweises oder eines
niedrigen OCR-Konfidenzwerts automatisch endgültig abgelehnt. Das Ergebnis ist
in diesen Fällen immer `MANUELLE_PRÜFUNG` (siehe `app/audit_engine/`).
