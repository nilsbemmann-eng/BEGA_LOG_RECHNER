# Technischer Bericht
## Automatisierte Frachtpreisprüfung für Spediteure

**Version:** 1.0
**Datum:** 16. September 2026
**Zweck:** Technische und fachliche Grundlage für die Entwicklung mit Claude

---

## 1. Zielsetzung

Es soll eine webbasierte Anwendung entstehen, die eingehende E-Mails, Frachtrechnungen, Ladelisten, Transportaufträge und Nachweise automatisiert verarbeitet. Die Anwendung extrahiert relevante Daten per OCR beziehungsweise Dokumentenanalyse, ordnet Dokumente Sendungen zu, prüft die berechnete Transportstrecke über OpenStreetMap-basierte Routingdienste und vergleicht Rechnungsbeträge sowie Zusatzfrachten mit hinterlegten Tarif- und Vertragsregeln.

Die Anwendung soll nicht lediglich Daten auslesen, sondern jede Preisprüfung nachvollziehbar, reproduzierbar und revisionsfähig dokumentieren.

### 1.1 Hauptziele

- Automatisches Einlesen von Preisen aus E-Mails und Anhängen.
- OCR-Erkennung von Rechnungen, Ladelisten und weiteren Transportdokumenten.
- Extraktion von Tabellen, Positionen und Schlüsselwerten.
- Zuordnung von Dokumenten zu Sendungen oder Transportaufträgen.
- Prüfung von Start- und Zieladressen.
- Berechnung einer Referenzstrecke und Referenzfahrzeit.
- Prüfung der abgerechneten Kilometer.
- Berechnung eines Sollpreises anhand versionierter Tarife.
- Prüfung von Zusatzfrachten und erforderlichen Nachweisen.
- Darstellung von Abweichungen mit verständlicher Begründung.
- Manuelle Prüfung und Freigabe unsicherer Fälle.
- Export der Prüfergebnisse nach XLSX, CSV und optional PDF.

### 1.2 Nichtziele der ersten Version

Folgende Funktionen sind nicht Bestandteil des ersten MVP und werden als Erweiterungen vorbereitet:

- Vollständige automatische Zahlungsfreigabe.
- Vollständige ERP- oder D365-Integration.
- Automatische Vertragsinterpretation aus beliebigen PDF-Dateien.
- Vollautomatische Anerkennung von Sonderfällen ohne Nachweis.
- Globale Multi-Mandanten-Plattform.
- Vollständige Mautberechnung für alle europäischen Länder.

---

## 2. Fachlicher Prozess

Der Prozess beginnt mit dem Eingang einer E-Mail in einem konfigurierten Postfach. Die Anwendung übernimmt die E-Mail-Metadaten und Anhänge, bildet einen Datei-Hash zur Duplikaterkennung und klassifiziert die Dokumente.

Danach werden relevante Dokumente per OCR und Dokumentenanalyse verarbeitet. Die erkannten Felder werden normalisiert, mit Konfidenzwerten gespeichert und einer Sendung oder einem Transportauftrag zugeordnet.

Für jede zugeordnete Sendung wird eine Referenzroute zwischen Abhol- und Zustelladresse berechnet. Anschließend wird der Tarif ermittelt und der Sollpreis berechnet. Rechnungspreis, Kilometer, Zuschläge und Nachweise werden mit dem Sollmodell verglichen.

Das Ergebnis ist ein Prüfstatus:

- BESTANDEN
- ABWEICHUNG
- MANUELLE_PRÜFUNG
- FEHLER
- FREIGEGEBEN
- RÜCKFRAGE

### 2.1 Prozesskette

```text
E-Mail empfangen
    ↓
E-Mail und Anhänge speichern
    ↓
Duplikate erkennen
    ↓
Dokumenttyp klassifizieren
    ↓
OCR und Tabellenerkennung
    ↓
Felder normalisieren
    ↓
Sendung zuordnen
    ↓
Adressen geocodieren
    ↓
Lkw-Referenzroute berechnen
    ↓
Tarif und Zuschläge anwenden
    ↓
Rechnung und Nachweise prüfen
    ↓
Ergebnis und Begründung erzeugen
    ↓
Manuelle Freigabe, Rückfrage oder Export
```

---

## 3. Benutzerrollen

### 3.1 Administrator

- Benutzer und Rollen verwalten.
- Postfächer und Provider konfigurieren.
- Tarifregeln erstellen und versionieren.
- Routing- und OCR-Provider konfigurieren.
- Aufbewahrungs- und Systemparameter verwalten.
- Systemprotokolle einsehen.

### 3.2 Prüfer

- Importe und Dokumente prüfen.
- OCR-Werte korrigieren.
- Sendungszuordnungen bestätigen.
- Prüfregeln und Abweichungen bearbeiten.
- Fälle freigeben oder zur Rückfrage stellen.
- Prüfberichte exportieren.

### 3.3 Lesender Benutzer

- Ergebnisse und Dokumente anzeigen.
- Keine Änderungen an Tarif-, OCR- oder Prüfdaten vornehmen.
- Exporte nur nach entsprechender Berechtigung erstellen.

---

## 4. Funktionale Anforderungen

### 4.1 E-Mail-Import

Die Anwendung muss ein oder mehrere konfigurierte Postfächer überwachen können. Zugangsdaten und API-Schlüssel dürfen nicht im Quellcode gespeichert werden.

Zu speichernde E-Mail-Daten:

- Externe Nachrichten-ID.
- Absender.
- Empfänger und CC-Empfänger.
- Betreff.
- Empfangsdatum und -zeit.
- Text- und HTML-Inhalt.
- Anhänge.
- Verarbeitungsstatus.
- Fehler- und Verarbeitungshinweise.

Die Anwendung muss bereits verarbeitete E-Mails und Anhänge erkennen. Die Identifikation erfolgt mindestens über externe Nachrichten-ID und SHA-256-Datei-Hash.

### 4.2 Unterstützte Dateien

Der MVP muss folgende Formate unterstützen:

- PDF.
- JPG und JPEG.
- PNG.
- TIFF.
- XLSX.
- CSV.

### 4.3 Dokumentklassifikation

Dokumente sollen mindestens in folgende Typen klassifiziert werden:

- Frachtrechnung.
- Ladeliste.
- Transportauftrag.
- Ablieferbeleg.
- Preisangebot.
- Mautnachweis.
- Wartezeitnachweis.
- Palettentauschbeleg.
- Sonstiges.

Die Klassifikation muss einen Konfidenzwert speichern. Bei niedriger Sicherheit wird das Dokument zur manuellen Prüfung gestellt.

### 4.4 OCR und Dokumentenanalyse

Die OCR-Komponente muss gedruckten Text, Tabellen, Schlüssel-Wert-Paare und Rechnungspositionen erkennen. Der OCR-Provider muss über eine Schnittstelle austauschbar sein.

Für jedes extrahierte Feld sind mindestens folgende Informationen zu speichern:

- Feldname.
- Originalwert.
- Normalisierter Wert.
- Datentyp.
- Konfidenzwert.
- Ursprungsdokument.
- Ursprungsseite.
- Ursprungstext.
- Optional: Bounding Box im Dokument.
- Extraktionsmethode.

Beispiel:

```json
{
  "field_name": "weight_kg",
  "original_value": "1.240 kg",
  "normalized_value": 1240,
  "data_type": "decimal",
  "confidence": 0.91,
  "source_page": 1,
  "source_text": "Bruttogewicht: 1.240 kg",
  "extraction_method": "ocr_table"
}
```

Deutsche Zahlenformate müssen korrekt verarbeitet werden:

- `1.234,56 EUR` wird zu `1234.56`.
- `1.240 kg` wird zu `1240`.
- `12,5 LDM` wird zu `12.5`.

### 4.5 Erkennung von Ladelisten

Die Anwendung muss unterschiedliche Bezeichnungen auf ein einheitliches Datenmodell abbilden können.

| Mögliche Bezeichnung | Zielfeld |
|---|---|
| Sendung, Auftrag, Tour, Referenz | shipment_number |
| Absender, Beladestelle, Pickup | origin_address |
| Empfänger, Entladestelle, Delivery | destination_address |
| Gewicht, Brutto, kg | weight_kg |
| Paletten, Packstücke, Colli | pallets oder packages |
| LDM, Lademeter | loading_meters |
| Volumen, cbm, m³ | volume_m3 |
| Fracht, Transportpreis, Netto | freight_amount |
| Zusatz, Nebenleistung, Zuschlag | surcharge_amount |

Die Spaltenerkennung muss konfigurierbar sein. Unbekannte Spalten dürfen nicht verloren gehen, sondern sind als nicht zugeordnete Importfelder zu speichern.

### 4.6 Sendungszuordnung

Dokumente sollen anhand mehrerer Kriterien automatisch einer Sendung zugeordnet werden:

- Sendungsnummer.
- Transportauftragsnummer.
- Rechnungsnummer.
- Frachtführer.
- Abhol- und Zustelladresse.
- Transportdatum.
- Rechnungsbetrag.
- Referenz aus E-Mail-Betreff oder Nachrichtentext.

Bei genau einer ausreichend sicheren Übereinstimmung darf automatisch zugeordnet werden. Bei mehreren möglichen Treffern muss die Anwendung eine Auswahlliste anzeigen.

Die Zuordnungsentscheidung muss mit den verwendeten Kriterien und dem Konfidenzwert protokolliert werden.

---

## 5. Kilometer- und Routenprüfung

### 5.1 Adressprüfung

Start- und Zieladressen werden normalisiert und geocodiert. Gespeichert werden die Originaladresse, die normalisierte Adresse, Koordinaten, Geocoding-Provider und Konfidenz.

Die Anwendung muss erkennen, wenn:

- eine Adresse nicht gefunden wird.
- mehrere Treffer möglich sind.
- das falsche Land erkannt wurde.
- Start- oder Zielkoordinaten offensichtlich fehlerhaft sind.
- eine Adresse nur auf Orts- oder Postleitzahlebene gefunden wurde.

### 5.2 Routing

Das Routing muss über eine austauschbare Provider-Schnittstelle erfolgen. Unterstützt werden sollen OpenStreetMap-basierte Dienste wie OSRM, GraphHopper, Valhalla oder openrouteservice.

Der Routingdatensatz muss mindestens enthalten:

```json
{
  "origin_lat": 52.4471,
  "origin_lon": 9.7342,
  "destination_lat": 53.0793,
  "destination_lon": 8.8017,
  "distance_km": 126.8,
  "duration_minutes": 103,
  "profile": "truck",
  "provider": "routing_provider",
  "calculated_at": "2026-09-16T21:46:00+02:00"
}
```

Zu unterscheiden sind:

- Luftlinienentfernung.
- Pkw-Straßenentfernung.
- Lkw-Straßenentfernung.
- abgerechnete Kilometer.
- gefahrene Kilometer aus Telematik, sofern verfügbar.
- vertraglich abrechenbare Kilometer.

Die Routingantwort muss gecacht werden. Der Cache darf nur verwendet werden, wenn Start, Ziel, Routingprofil, Provider und relevante Parameter übereinstimmen.

### 5.3 Kilometerabweichung

```text
Kilometerabweichung in Prozent =
(abgerechnete Kilometer - Referenzkilometer)
÷ Referenzkilometer × 100
```

Die Toleranz muss je Tarif, Relation oder Sonderfall konfigurierbar sein. Startwerte:

- Standardroute: ±8 %.
- Innenstadt oder schwer zugängliche Zustellung: ±12 %.
- Fähre, Insel, Baustelle oder Sonderroute: manuelle Prüfung.

Eine Abweichung ist nicht automatisch eine Ablehnung. Die Anwendung muss alternative Erklärungen anzeigen können, beispielsweise Mautvermeidung, Baustelle, zusätzliche Ladestelle oder abweichende Lkw-Beschränkung.

---

## 6. Tarif- und Preisprüfung

### 6.1 Tarifarten

Der MVP muss mindestens Grundpreis plus Kilometerpreis unterstützen. Die Architektur muss zusätzlich vorbereiten:

- Relationstarife.
- Gewichtsstaffeln.
- Palettenpreise.
- Lademeterpreise.
- Zonenpreise.
- All-in-Preise.
- Mindestfracht.
- Länder- und Grenzzuschläge.
- zeitabhängige Tarife.

### 6.2 Tarifversionierung

Jeder Tarif benötigt:

- Tarif-ID.
- Name.
- Frachtführer.
- Gültig-ab-Datum.
- Gültig-bis-Datum.
- Währung.
- Mengeneinheiten.
- Berechnungsregeln.
- Freigabestatus.
- Ersteller und Änderungszeitpunkt.

Ein Prüfergebnis muss immer die konkret verwendete Tarifversion speichern. Nachträgliche Tarifänderungen dürfen alte Prüfergebnisse nicht verändern.

### 6.3 Preisberechnung

Beispielhafte Grundformel:

```text
Abrechnungs-km = max(Referenz-km, Mindest-km)

Netto-Sollpreis =
Grundpreis
+ Abrechnungs-km × Kilometerpreis
+ zulässige Zusatzfrachten
```

Optional werden anschließend Steuer- oder Währungsregeln angewendet. Geldbeträge müssen als Dezimalwerte gespeichert werden. Binäre Gleitkommazahlen dürfen für Rechnungsbeträge nicht verwendet werden.

### 6.4 Preisabweichung

```text
Preisabweichung = Rechnungsbetrag - Sollpreis

Preisabweichung in Prozent =
Preisabweichung ÷ Sollpreis × 100
```

Die Anwendung muss absolute und prozentuale Abweichungen darstellen.

---

## 7. Zusatzfrachten

Jede Zusatzfracht wird als eigene Position verarbeitet und geprüft. Ein Sammelfeld „Sonstige Zuschläge" darf nur zusätzlich, nicht anstelle der Einzelpositionen verwendet werden.

Zu unterstützende Positionen:

- Diesel- oder Energiezuschlag.
- Maut.
- ADR.
- Wartezeit.
- Zusatzladestelle.
- Zusatzentladestelle.
- Avisierung.
- Hebebühne.
- Mitnahmestapler.
- Sperrgut oder Übermaß.
- Fähre oder Insel.
- Zoll- und Grenzabfertigung.
- Nacht-, Wochenend- oder Feiertagszuschlag.
- Fehlfahrt.
- erfolglose Zustellung.
- Palettentausch.
- Standgeld.
- Express- oder Fixterminzuschlag.

Beispielstruktur:

```json
{
  "surcharge_type": "waiting_time",
  "description": "Wartezeit Beladung",
  "quantity": 2.5,
  "unit": "hours",
  "unit_price": 48.00,
  "claimed_amount": 120.00,
  "allowed_amount": 72.00,
  "evidence_document_id": "doc-12345",
  "status": "MANUAL_REVIEW",
  "reason": "Kein bestätigter Wartezeitnachweis vorhanden"
}
```

Grundregel:

```text
Zulässiger Zuschlag = nachgewiesene Menge × vertraglicher Einheitspreis
```

Fehlt ein erforderlicher Beleg, wird die Position auf `MANUELLE_PRÜFUNG` gesetzt. Sie darf nicht automatisch als falsch abgelehnt werden.

---

## 8. Prüfregeln und Statuslogik

### 8.1 Prüfregeln

| Regelbereich | Beispiel |
|---|---|
| Pflichtfelder | Sendungsnummer, Datum, Start, Ziel und Betrag vorhanden |
| OCR | Konfidenzwert über definierter Schwelle |
| Zuordnung | Eindeutige Sendungszuordnung vorhanden |
| Adresse | Start und Ziel erfolgreich geocodiert |
| Distanz | Kilometerabweichung innerhalb der Toleranz |
| Tarif | Transportdatum liegt im Gültigkeitszeitraum |
| Preis | Rechnungsbetrag liegt innerhalb der Preisgrenze |
| Zuschlag | Zuschlag ist vertraglich erlaubt |
| Nachweis | Erforderlicher Beleg liegt vor |
| Duplikat | Rechnung oder Anhang wurde nicht bereits verarbeitet |
| Plausibilität | Gewicht, Lademeter und Preis sind fachlich plausibel |

### 8.2 OCR-Schwellenwerte

- Konfidenz mindestens 0,95: automatische Weiterverarbeitung möglich.
- Konfidenz von 0,80 bis 0,949: Weiterverarbeitung mit Kennzeichnung.
- Konfidenz unter 0,80: manuelle Erfassung oder Bestätigung erforderlich.

### 8.3 Ergebnisbeispiel

```text
Status: MANUELLE PRÜFUNG

Abgerechnete Strecke: 684 km
Referenzstrecke: 542 km
Kilometerabweichung: +26,2 %

Sollpreis: 1.184,00 EUR
Rechnungsbetrag: 1.436,00 EUR
Preisabweichung: +252,00 EUR

Grund:
Die Kilometerabweichung überschreitet die Toleranz von 8 %. Zusätzlich wurde
Wartezeit berechnet, aber kein unterschriebener Wartezeitnachweis erkannt.
```

---

## 9. Datenmodell

Die Anwendung benötigt mindestens folgende Tabellen beziehungsweise Entitäten: siehe `backend/app/models/`.

---

## 10. Systemarchitektur

### 10.1 Komponenten

```text
Web-Frontend
    ↓
Backend-API
    ├── E-Mail-Connector
    ├── Dokumentenklassifikation
    ├── OCR-Provider
    ├── Normalisierung
    ├── Matching-Engine
    ├── Geocoding-Provider
    ├── Routing-Provider
    ├── Tarif-Engine
    ├── Prüfregel-Engine
    ├── Export-Service
    └── Audit-Log-Service
    ↓
Relationale Datenbank
    ↓
Dokumentenspeicher
```

### 10.2 Provider-Schnittstellen

Folgende Komponenten müssen austauschbar sein:

- `EmailProvider`.
- `DocumentClassifier`.
- `DocumentOcrProvider`.
- `GeocodingProvider`.
- `RoutingProvider`.
- `CurrencyProvider`, sofern erforderlich.
- `ExportProvider`.

### 10.3 Technologieempfehlung

- Frontend: React oder Next.js.
- Backend: Node.js mit TypeScript oder Python mit FastAPI.
- Datenbank: PostgreSQL.
- Dokumentenspeicher: verschlüsselter Object Storage.
- Hintergrundverarbeitung: Redis Queue, RabbitMQ oder vergleichbare Job Queue.
- Authentifizierung: OAuth2 beziehungsweise OpenID Connect.
- Deployment: Containerisierte Umgebung.

Die Geschäftslogik darf nicht ausschließlich im Frontend liegen.

---

## 11. API-Struktur

Siehe `backend/app/api/routers/`.

---

## 12. Benutzeroberfläche

Siehe `frontend/`.

---

## 13. Sicherheit, Datenschutz und Nachvollziehbarkeit

- Zugangsdaten und API-Schlüssel ausschließlich über Secret Management verwalten.
- Dokumente verschlüsselt speichern.
- Rollenbasierte Zugriffskontrolle umsetzen.
- Mandantentrennung vorbereiten.
- E-Mail- und Dokumentenzugriffe protokollieren.
- Änderungen an OCR-Werten, Tarifen und Ergebnissen auditieren.
- Ursprungsdokumente unverändert aufbewahren.
- Lösch- und Aufbewahrungsfristen konfigurierbar machen.
- Personenbezogene Daten minimieren.
- Keine endgültige Ablehnung ausschließlich aufgrund eines niedrigen OCR-Konfidenzwerts.
- Externe Provider und deren Datenverarbeitung dokumentieren.

---

## 14. Fehlerbehandlung

Siehe `docs/OFFENE_ENTSCHEIDUNGEN.md` und `backend/app/errors.py`.

---

## 15. MVP-Abgrenzung

Siehe `README.md`, Abschnitt "MVP-Umfang".

---

## 16. Akzeptanzkriterien

Siehe `backend/tests/`.

---

## 17. Arbeitsauftrag für Claude

Siehe `README.md`, Abschnitt "Roadmap".

---

## 18. Offene fachliche Entscheidungen

Siehe `docs/OFFENE_ENTSCHEIDUNGEN.md`.

---

## 19. Technische Leitentscheidung

Die Anwendung soll KI für Klassifikation, OCR-Unterstützung, Feldextraktion und verständliche Begründungen einsetzen. Die verbindliche Preisberechnung und die abschließende Prüfentscheidung müssen jedoch durch deterministische, versionierte Regeln erfolgen.

Damit bleibt die Anwendung für Spediteur, Verlader, Finanzabteilung und Revision nachvollziehbar. Claude soll daher keine monolithische KI-Lösung erzeugen, sondern eine modulare Prüfplattform mit klaren Datenquellen, testbaren Berechnungen und einem dokumentierten manuellen Kontrollprozess.
