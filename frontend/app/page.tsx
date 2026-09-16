import Link from "next/link";
import { fetchAudits, fetchEmails, fetchShipments } from "../lib/api";
import type { AuditResultOut, EmailOut, ShipmentOut } from "../lib/types";

async function loadDashboardData(): Promise<
  | { ok: true; emails: EmailOut[]; shipments: ShipmentOut[]; audits: AuditResultOut[] }
  | { ok: false; error: string }
> {
  try {
    const [emails, shipments, audits] = await Promise.all([fetchEmails(), fetchShipments(), fetchAudits()]);
    return { ok: true, emails, shipments, audits };
  } catch (error) {
    return { ok: false, error: error instanceof Error ? error.message : "Unbekannter Fehler" };
  }
}

function sumAbsolute(values: (number | null)[]): number {
  return values.reduce<number>(
    (total, value) => total + (value === null || Number.isNaN(value) ? 0 : Math.abs(value)),
    0
  );
}

export default async function DashboardPage() {
  const data = await loadDashboardData();

  if (!data.ok) {
    return (
      <>
        <h1>Dashboard</h1>
        <p className="subtitle">Abschnitt 12.1</p>
        <div className="empty-state">
          Backend nicht erreichbar ({data.error}). Bitte pruefen, ob die API unter
          NEXT_PUBLIC_API_BASE_URL laeuft.
        </div>
      </>
    );
  }

  const { emails, shipments, audits } = data;

  const newEmails = emails.filter((e) => e.processing_status === "received").length;
  const manualReview = audits.filter((a) => a.status === "MANUELLE_PRUEFUNG").length;
  const passed = audits.filter((a) => a.status === "BESTANDEN" || a.status === "FREIGEGEBEN").length;
  const errors = audits.filter((a) => a.status === "FEHLER").length;

  const priceDeviationSum = sumAbsolute(audits.map((a) => (a.difference_amount ? Number(a.difference_amount) : null)));
  const kmDeviationSum = sumAbsolute(
    audits.map((a) =>
      a.reference_distance_km && a.invoiced_distance_km
        ? Number(a.invoiced_distance_km) - Number(a.reference_distance_km)
        : null
    )
  );

  return (
    <>
      <h1>Dashboard</h1>
      <p className="subtitle">Abschnitt 12.1 - Uebersicht ueber Importe und Pruefungen</p>

      <div className="stat-grid">
        <div className="stat-card">
          <div className="stat-value">{newEmails}</div>
          <div className="stat-label">Neue E-Mails</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{shipments.length}</div>
          <div className="stat-label">Sendungen</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{audits.length}</div>
          <div className="stat-label">Geprueft (gesamt)</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{passed}</div>
          <div className="stat-label">Bestanden / freigegeben</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{manualReview}</div>
          <div className="stat-label">Offene manuelle Pruefungen</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{errors}</div>
          <div className="stat-label">Fehlerhafte Pruefungen</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{priceDeviationSum.toFixed(2)} EUR</div>
          <div className="stat-label">Summe Preisabweichungen</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{kmDeviationSum.toFixed(1)} km</div>
          <div className="stat-label">Summe Kilometerabweichungen</div>
        </div>
      </div>

      <p className="subtitle">
        Hinweis: Kennzahlen zu offenen OCR-Pruefungen, offenen Zuordnungen und
        Dokumenten mit Fehlerstatus benoetigen einen zusaetzlichen
        Dokumenten-Listen-Endpunkt, der im MVP-API-Vertrag (Abschnitt 11) noch
        nicht vorgesehen ist.
      </p>

      <Link href="/audits">Alle Pruefungen ansehen &rarr;</Link>
    </>
  );
}
