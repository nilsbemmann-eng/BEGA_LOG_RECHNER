import { notFound } from "next/navigation";
import { StatusBadge } from "../../../components/StatusBadge";
import { fetchAudit, fetchShipment } from "../../../lib/api";
import type { ShipmentOut } from "../../../lib/types";

const RULE_STATUS_BADGE: Record<string, string> = {
  passed: "badge-success",
  warning: "badge-warning",
  failed: "badge-danger",
  manual_review: "badge-warning",
  error: "badge-danger",
};

export default async function AuditDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;

  let audit;
  try {
    audit = await fetchAudit(id);
  } catch {
    notFound();
  }

  let shipment: ShipmentOut | null = null;
  try {
    shipment = await fetchShipment(audit.shipment_id);
  } catch {
    shipment = null;
  }

  return (
    <>
      <h1>Pruefdetail</h1>
      <p className="subtitle">Abschnitt 12.3 - Sendung {shipment?.shipment_number ?? audit.shipment_id}</p>

      <div className="card">
        <h2>
          Status <StatusBadge status={audit.status} />
        </h2>
        <div className="explanation">{audit.explanation}</div>
      </div>

      <div className="card">
        <h2>Distanz &amp; Preis</h2>
        <div className="kv-grid">
          <div>
            <div className="kv-label">Referenzstrecke</div>
            <div className="kv-value">{audit.reference_distance_km ?? "-"} km</div>
          </div>
          <div>
            <div className="kv-label">Abgerechnete Strecke</div>
            <div className="kv-value">{audit.invoiced_distance_km ?? "-"} km</div>
          </div>
          <div>
            <div className="kv-label">Sollpreis</div>
            <div className="kv-value">{audit.expected_amount ?? "-"} EUR</div>
          </div>
          <div>
            <div className="kv-label">Rechnungsbetrag</div>
            <div className="kv-value">{audit.invoiced_amount ?? "-"} EUR</div>
          </div>
          <div>
            <div className="kv-label">Preisabweichung</div>
            <div className="kv-value">
              {audit.difference_amount ?? "-"} EUR ({audit.difference_percent ?? "-"} %)
            </div>
          </div>
          <div>
            <div className="kv-label">Tarifversion</div>
            <div className="kv-value">{audit.tariff_id ?? "kein Tarif ermittelt"}</div>
          </div>
        </div>
      </div>

      {shipment && (
        <div className="card">
          <h2>Sendungsdaten</h2>
          <div className="kv-grid">
            <div>
              <div className="kv-label">Sendungsnummer</div>
              <div className="kv-value">{shipment.shipment_number ?? "-"}</div>
            </div>
            <div>
              <div className="kv-label">Transportdatum</div>
              <div className="kv-value">{shipment.transport_date ?? "-"}</div>
            </div>
            <div>
              <div className="kv-label">Gewicht</div>
              <div className="kv-value">{shipment.weight_kg ?? "-"} kg</div>
            </div>
            <div>
              <div className="kv-label">Paletten</div>
              <div className="kv-value">{shipment.pallets ?? "-"}</div>
            </div>
          </div>
        </div>
      )}

      <div className="card">
        <h2>Ausgeloeste Pruefregeln (Abschnitt 8.1)</h2>
        <table>
          <thead>
            <tr>
              <th>Regel</th>
              <th>Status</th>
              <th>Ist-Wert</th>
              <th>Soll-Wert</th>
              <th>Begruendung</th>
            </tr>
          </thead>
          <tbody>
            {audit.rule_results.map((rule) => (
              <tr key={rule.rule_code}>
                <td>{rule.rule_name}</td>
                <td>
                  <span className={`badge ${RULE_STATUS_BADGE[rule.status] ?? "badge-info"}`}>{rule.status}</span>
                </td>
                <td>{rule.actual_value ?? "-"}</td>
                <td>{rule.expected_value ?? "-"}</td>
                <td>{rule.explanation}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
