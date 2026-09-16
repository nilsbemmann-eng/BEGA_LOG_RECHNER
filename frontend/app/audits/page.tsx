import Link from "next/link";
import { StatusBadge } from "../../components/StatusBadge";
import { fetchAudits } from "../../lib/api";
import type { AuditResultOut } from "../../lib/types";

export default async function AuditsPage() {
  let audits: AuditResultOut[] = [];
  let loadError: string | null = null;

  try {
    audits = await fetchAudits();
  } catch (error) {
    loadError = error instanceof Error ? error.message : "Unbekannter Fehler";
  }

  return (
    <>
      <h1>Pruefungen</h1>
      <p className="subtitle">Abschnitt 12.2/12.3 - alle Preispruefergebnisse</p>

      {loadError && <div className="empty-state">Backend nicht erreichbar ({loadError}).</div>}

      {!loadError && audits.length === 0 && <div className="empty-state">Noch keine Pruefergebnisse vorhanden.</div>}

      {!loadError && audits.length > 0 && (
        <table>
          <thead>
            <tr>
              <th>Status</th>
              <th>Sendung</th>
              <th>Referenz km</th>
              <th>Abgerechnet km</th>
              <th>Sollpreis</th>
              <th>Rechnungsbetrag</th>
              <th>Abweichung</th>
            </tr>
          </thead>
          <tbody>
            {audits.map((audit) => (
              <tr key={audit.id}>
                <td>
                  <Link href={`/audits/${audit.id}`}>
                    <StatusBadge status={audit.status} />
                  </Link>
                </td>
                <td>{audit.shipment_id}</td>
                <td>{audit.reference_distance_km ?? "-"}</td>
                <td>{audit.invoiced_distance_km ?? "-"}</td>
                <td>{audit.expected_amount ? `${audit.expected_amount} EUR` : "-"}</td>
                <td>{audit.invoiced_amount ? `${audit.invoiced_amount} EUR` : "-"}</td>
                <td>{audit.difference_amount ? `${audit.difference_amount} EUR` : "-"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </>
  );
}
