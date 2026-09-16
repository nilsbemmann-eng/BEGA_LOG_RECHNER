# BEGA Frachtpreisrechner

Automatisierte Frachtpreispruefung fuer Spediteure. Verarbeitet eingehende
E-Mails, Frachtrechnungen, Ladelisten und Nachweise, prueft die abgerechnete
Strecke gegen eine OpenStreetMap-basierte Referenzroute und vergleicht den
Rechnungsbetrag mit einem versionierten, deterministisch berechneten
Sollpreis. Jede Preispruefung ist aus gespeicherten Eingangswerten, einer
Tarifversion, Routingdaten und angewendeten Pruefregeln reproduzierbar.

Fachliche und technische Grundlage: [`docs/technischer_bericht.md`](docs/technischer_bericht.md).
Offene, noch zu bestaetigende Geschaeftsregeln: [`docs/OFFENE_ENTSCHEIDUNGEN.md`](docs/OFFENE_ENTSCHEIDUNGEN.md).

## Architektur

```text
frontend/   Next.js/TypeScript-Oberflaeche (Dashboard, Historie mit Suche/Export, Pruefdetail).
            Client-seitige Aufrufe gehen an denselben Origin unter /api/* und
            werden per next.config.js-Rewrite serverseitig zum Backend
            weitergeleitet (kein CORS noetig, siehe BACKEND_INTERNAL_URL).
backend/    FastAPI/Python-Backend
  app/models/            SQLAlchemy-Datenmodell (Abschnitt 9)
  app/providers/         Austauschbare Schnittstellen: E-Mail, OCR, Klassifikation,
                         Geocoding, Routing, Export (Abschnitt 10.2) + Implementierungen
  app/normalization/     Deutsche Zahlenformate, Ladeliste-Spaltenerkennung (Abschnitt 4.4/4.5)
  app/matching/          Sendungszuordnung nach mehreren Kriterien (Abschnitt 4.6)
  app/distance_engine/   Kilometerabweichung und Toleranzen (Abschnitt 5.3)
  app/tariff_engine/     Tarifauswahl und Sollpreisberechnung (Abschnitt 6)
  app/surcharge_engine/  Pruefung von Zusatzfrachten (Abschnitt 7)
  app/audit_engine/      Pruefregel-Engine, leitet den Gesamtstatus ab (Abschnitt 8)
  app/services/          Bindeglied zwischen ORM und den obigen Engines
  app/api/routers/       FastAPI-Endpunkte (Abschnitt 11)
  tests/                 pytest-Suite (Unit- und API-Tests)
docker-compose.yml        Postgres + Backend + Frontend fuer die lokale Entwicklung
```

Die Geschaeftslogik liegt vollstaendig im Backend (nicht im Frontend, siehe
Abschnitt 10.3). Die Kernberechnungen (Distanz, Tarif, Zuschlag, Pruefregeln)
sind bewusst framework-unabhaengig implementiert (keine SQLAlchemy-Abhaengigkeit)
und dadurch ohne Datenbank/HTTP testbar - das ist die deterministische,
versionierbare Kernkomponente aus Abschnitt 19. KI/Heuristiken kommen nur in
den austauschbaren Providern zum Einsatz (Dokumentklassifikation, OCR-Feldextraktion).

## Lokale Entwicklung

### Backend

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # Werte anpassen, siehe Kommentare in der Datei

# Datenbank-Migrationen anwenden (benoetigt eine erreichbare Postgres-Instanz,
# siehe docker-compose.yml, oder eine lokale SQLite-URL in DATABASE_URL)
alembic upgrade head

uvicorn app.main:app --reload
```

API-Dokumentation danach unter `http://localhost:8000/docs`.

Tests ausfuehren:

```bash
cd backend
source .venv/bin/activate
pytest
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Erwartet das Backend unter `NEXT_PUBLIC_API_BASE_URL` (Standard `http://localhost:8000`).

### Mit Docker Compose

```bash
cp backend/.env.example backend/.env   # Werte anpassen
docker compose up --build
```

Startet Postgres, Backend (Port 8000) und Frontend (Port 3000).

## MVP-Umfang (Abschnitt 15)

Umgesetzt:

1. Datenmodell fuer alle in Abschnitt 9 geforderten Entitaeten inkl. Alembic-Migration.
2. Austauschbare Provider-Schnittstellen fuer E-Mail (IMAP), OCR (PDF-Text/Tabellen
   via `pdfplumber` fuer PDFs mit Textebene; Claude-Vision-basierte Erkennung
   fuer Scans/Fotos inkl. Begruendung je Feld und erster
   Unterschriften-Anwesenheitserkennung, siehe
   `app/providers/ocr/llm_vision_provider.py`), Dokumentklassifikation
   (stichwortbasiert), Geocoding (OpenStreetMap Nominatim), Routing (OSRM) und
   Export (XLSX/CSV). Zusaetzlich zum IMAP-Postfach koennen einzelne
   Outlook-`.msg`-Dateien manuell hochgeladen werden (`POST /api/emails/upload`,
   Dashboard-Upload-Formular) und durchlaufen dieselbe Verarbeitung wie eine
   per IMAP abgeholte E-Mail.
3. Deutsche Zahlenformat-Normalisierung und konfigurierbare Ladeliste-Spaltenerkennung.
4. Mehrkriterien-Sendungszuordnung mit Protokollierung der Zuordnungsentscheidung.
5. Kilometerabweichungspruefung mit konfigurierbaren Toleranzen und Routing-Cache.
6. Tarif-Engine (Grundpreis + Kilometerpreis, versioniert) mit Decimal-Arithmetik.
7. Zusatzfracht-Pruefung inkl. Nachweispflicht ohne automatische Ablehnung.
8. Pruefregel-Engine, die alle Regeln aus Tabelle 8.1 auswertet und einen der
   sechs Status aus Abschnitt 2 ableitet.
9. FastAPI-Endpunkte gemaess Abschnitt 11, inkl. einheitlicher Fehlerantworten
   (Abschnitt 14) und rollenbasierter Freigabe-/Rueckfrage-Aktionen (Abschnitt 3).
10. Audit-Log fuer OCR-Korrekturen, Sendungszuordnungen, Freigaben und Rueckfragen.
11. Next.js-Frontend mit Dashboard, Historie (Suche nach Sendung/Auftrag/
    Rechnung/Frachtfuehrer, Status- und Zeitraumfilter, Export nach XLSX/CSV
    mit direktem Download) und Pruefdetail (Abschnitt 12).
12. pytest-Suite: Unit-Tests je Engine plus End-to-End-API-Tests des
    vollstaendigen Audit-Durchlaufs sowie der Historie-Suche und des
    Exports/Downloads.

Bewusst nicht im MVP (siehe Abschnitt 1.2, 15 und `docs/OFFENE_ENTSCHEIDUNGEN.md`):
automatische Zahlungsfreigabe, ERP/D365-Integration, vollstaendige
Mautberechnung, produktive OIDC-Anmeldung, verschluesselter Object Store,
Mandantentrennung, Hintergrundjob-Queue, weitere Tarifregeltypen ausser
Grundpreis+km.

## Roadmap (Abschnitt 17)

Die Bearbeitungsreihenfolge aus dem technischen Bericht wurde eingehalten:
Anforderungen/offene Annahmen (`docs/OFFENE_ENTSCHEIDUNGEN.md`) → Datenmodell →
Provider-Schnittstellen → API-Vertrag → Import-/Dokumentenpipeline →
OCR-Normalisierung → Sendungs-Matching → Geocoding/Routing → Tarif-Engine →
Zusatzfrachtpruefung → Pruefregel-Engine → Benutzeroberflaeche → Tests.

Naechste sinnvolle Schritte fuer den produktiven Einsatz:

- OIDC-Anbindung anstelle des Auth-Platzhalters in `app/auth.py`.
- Unterschriftenerkennung ueber reine Anwesenheitspruefung hinaus erweitern
  (Lokalisierung, Verifikation gegen Referenzunterschrift), falls in der
  Praxis benoetigt - siehe docs/OFFENE_ENTSCHEIDUNGEN.md.
- Verschluesselten Object Store statt lokalem Dateisystem anbinden (`app/storage.py`).
- Hintergrundjob-Queue (Redis/RabbitMQ) fuer E-Mail-Sync, OCR, Routing, Import, Export.
- Weitere Tarifregeltypen (Relation, Gewichtsstaffel, Zone, ...) in
  `app/tariff_engine/engine.py` implementieren.
- Dokumenten-Listen-Endpunkt fuer vollstaendige Dashboard-Kennzahlen (Abschnitt 12.1).
- Alle in `docs/OFFENE_ENTSCHEIDUNGEN.md` markierten Punkte mit dem Fachbereich final klaeren.
