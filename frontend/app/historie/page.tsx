"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { StatusBadge } from "../../components/StatusBadge";
import { createExport, exportDownloadUrl, fetchAudits } from "../../lib/api";
import type { AuditResultOut, AuditStatus } from "../../lib/types";

const STATUS_OPTIONS: { value: AuditStatus | ""; label: string }[] = [
  { value: "", label: "Alle Status" },
  { value: "BESTANDEN", label: "Bestanden" },
  { value: "ABWEICHUNG", label: "Abweichung" },
  { value: "MANUELLE_PRUEFUNG", label: "Manuelle Pruefung" },
  { value: "FEHLER", label: "Fehler" },
  { value: "FREIGEGEBEN", label: "Freigegeben" },
  { value: "RUECKFRAGE", label: "Rueckfrage" },
];

export default function HistoriePage() {
  const [q, setQ] = useState("");
  const [status, setStatus] = useState<AuditStatus | "">("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

  const [results, setResults] = useState<AuditResultOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [exportFormat, setExportFormat] = useState<"xlsx" | "csv">("xlsx");
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);

  async function runSearch() {
    setLoading(true);
    setLoadError(null);
    try {
      const data = await fetchAudits({
        q: q.trim() || undefined,
        status: status || undefined,
        dateFrom: dateFrom || undefined,
        dateTo: dateTo || undefined,
      });
      setResults(data);
    } catch (error) {
      setLoadError(error instanceof Error ? error.message : "Unbekannter Fehler");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    runSearch();
    // Beim ersten Laden ohne Filter - danach nur auf Benutzeraktion (Suchen-Button).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function handleSearchSubmit(event: React.FormEvent) {
    event.preventDefault();
    runSearch();
  }

  function handleReset() {
    setQ("");
    setStatus("");
    setDateFrom("");
    setDateTo("");
  }

  async function handleExport() {
    if (results.length === 0) {
      return;
    }
    setExporting(true);
    setExportError(null);
    try {
      const exportResult = await createExport(
        results.map((r) => r.id),
        exportFormat
      );
      window.location.href = exportDownloadUrl(exportResult.download_url);
    } catch (error) {
      setExportError(error instanceof Error ? error.message : "Export fehlgeschlagen");
    } finally {
      setExporting(false);
    }
  }

  return (
    <>
      <h1>Historie</h1>
      <p className="subtitle">Suche in allen Preispruefungen und Export nach XLSX oder CSV (Abschnitt 1.1, 11, 12)</p>

      <form className="filter-bar" onSubmit={handleSearchSubmit}>
        <div className="filter-field">
          <label htmlFor="q">Suche (Sendung, Auftrag, Rechnung, Frachtfuehrer)</label>
          <input id="q" type="text" value={q} onChange={(e) => setQ(e.target.value)} placeholder="z.B. SEND-1042 oder ACME" />
        </div>
        <div className="filter-field">
          <label htmlFor="status">Status</label>
          <select id="status" value={status} onChange={(e) => setStatus(e.target.value as AuditStatus | "")}>
            {STATUS_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>
        <div className="filter-field">
          <label htmlFor="dateFrom">Transportdatum von</label>
          <input id="dateFrom" type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
        </div>
        <div className="filter-field">
          <label htmlFor="dateTo">Transportdatum bis</label>
          <input id="dateTo" type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
        </div>
        <button type="submit" className="btn btn-primary" disabled={loading}>
          {loading ? "Suche laeuft..." : "Suchen"}
        </button>
        <button type="button" className="btn" onClick={handleReset} disabled={loading}>
          Zuruecksetzen
        </button>
      </form>

      <div className="export-bar">
        <select value={exportFormat} onChange={(e) => setExportFormat(e.target.value as "xlsx" | "csv")}>
          <option value="xlsx">XLSX</option>
          <option value="csv">CSV</option>
        </select>
        <button type="button" className="btn" onClick={handleExport} disabled={exporting || results.length === 0}>
          {exporting ? "Export laeuft..." : `Export (${results.length} Ergebnis${results.length === 1 ? "" : "se"})`}
        </button>
        {exportError && <span className="form-error">{exportError}</span>}
      </div>

      {loadError && <div className="empty-state">Backend nicht erreichbar ({loadError}).</div>}

      {!loadError && !loading && results.length === 0 && (
        <div className="empty-state">Keine Pruefergebnisse fuer diese Suche gefunden.</div>
      )}

      {!loadError && results.length > 0 && (
        <>
          <p className="result-count">{results.length} Treffer</p>
          <table>
            <thead>
              <tr>
                <th>Status</th>
                <th>Sendung</th>
                <th>Frachtfuehrer</th>
                <th>Transportdatum</th>
                <th>Referenz km</th>
                <th>Abgerechnet km</th>
                <th>Sollpreis</th>
                <th>Rechnungsbetrag</th>
                <th>Abweichung</th>
              </tr>
            </thead>
            <tbody>
              {results.map((audit) => (
                <tr key={audit.id}>
                  <td>
                    <Link href={`/historie/${audit.id}`}>
                      <StatusBadge status={audit.status} />
                    </Link>
                  </td>
                  <td>{audit.shipment_number ?? "-"}</td>
                  <td>{audit.carrier_name ?? "-"}</td>
                  <td>{audit.transport_date ?? "-"}</td>
                  <td>{audit.reference_distance_km ?? "-"}</td>
                  <td>{audit.invoiced_distance_km ?? "-"}</td>
                  <td>{audit.expected_amount ? `${audit.expected_amount} EUR` : "-"}</td>
                  <td>{audit.invoiced_amount ? `${audit.invoiced_amount} EUR` : "-"}</td>
                  <td>{audit.difference_amount ? `${audit.difference_amount} EUR` : "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </>
  );
}
