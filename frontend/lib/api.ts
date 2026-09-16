import type { AuditHistoryFilters, AuditResultOut, EmailOut, EmailUploadResult, ExportOut, ShipmentOut } from "./types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

// Server Components (SSR) rufen das Backend direkt unter API_BASE_URL auf.
// Im Browser laufender Code nutzt stattdessen denselben Origin (leerer Base-
// Pfad); `next.config.js` proxied `/api/*` serverseitig zum Backend. Das
// vermeidet CORS und funktioniert auch dann, wenn der Browser das Backend
// nicht direkt erreichen kann (z. B. unterschiedliche interne Hosts/Ports).
function resolveBaseUrl(): string {
  return typeof window === "undefined" ? API_BASE_URL : "";
}

/** Liest die einheitliche Fehlerantwort aus Abschnitt 14 (`ErrorResponse`
 * in backend/app/schemas.py) aus, falls vorhanden, sonst einen generischen Text. */
async function extractErrorMessage(response: Response, path: string): Promise<string> {
  try {
    const body = await response.json();
    if (body && typeof body.message === "string") {
      return body.message;
    }
  } catch {
    // Antwort war kein JSON - generische Meldung verwenden.
  }
  return `API-Fehler ${response.status} bei ${path}`;
}

async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(`${resolveBaseUrl()}${path}`, {
    // MVP-Backend hat noch keine Session-Auth (siehe app/auth.py) - der Server
    // faellt in der Entwicklung auf einen Default-Admin zurueck.
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(await extractErrorMessage(response, path));
  }
  return response.json() as Promise<T>;
}

async function apiPost<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(`${resolveBaseUrl()}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    throw new Error(await extractErrorMessage(response, path));
  }
  return response.json() as Promise<T>;
}

async function apiUpload<T>(path: string, file: File): Promise<T> {
  const formData = new FormData();
  formData.append("file", file);
  const response = await fetch(`${resolveBaseUrl()}${path}`, { method: "POST", body: formData });
  if (!response.ok) {
    throw new Error(await extractErrorMessage(response, path));
  }
  return response.json() as Promise<T>;
}

export function fetchEmails(): Promise<EmailOut[]> {
  return apiGet<EmailOut[]>("/api/emails");
}

export function fetchShipments(): Promise<ShipmentOut[]> {
  return apiGet<ShipmentOut[]>("/api/shipments");
}

export function fetchAudits(filters: AuditHistoryFilters = {}): Promise<AuditResultOut[]> {
  const params = new URLSearchParams();
  if (filters.q) params.set("q", filters.q);
  if (filters.status) params.set("status", filters.status);
  if (filters.dateFrom) params.set("date_from", filters.dateFrom);
  if (filters.dateTo) params.set("date_to", filters.dateTo);
  const query = params.toString();
  return apiGet<AuditResultOut[]>(`/api/audits${query ? `?${query}` : ""}`);
}

export function fetchAudit(id: string): Promise<AuditResultOut> {
  return apiGet<AuditResultOut>(`/api/audits/${id}`);
}

export function fetchShipment(id: string): Promise<ShipmentOut> {
  return apiGet<ShipmentOut>(`/api/shipments/${id}`);
}

export function createExport(auditResultIds: string[], fileFormat: "xlsx" | "csv"): Promise<ExportOut> {
  return apiPost<ExportOut>("/api/exports", { audit_result_ids: auditResultIds, file_format: fileFormat });
}

/** `downloadUrl` kommt bereits als serverrelativer Pfad vom Backend
 * (`/api/exports/{id}/download`) - im Browser genuegt eine gleichartige
 * same-origin Navigation, die von `next.config.js` zum Backend proxied wird. */
export function exportDownloadUrl(downloadUrl: string): string {
  return downloadUrl;
}

/** Laedt eine Outlook-.msg-Datei hoch (Abschnitt 4.1/4.2) - wird serverseitig
 * genauso verarbeitet wie eine per IMAP abgeholte E-Mail. */
export function uploadEmailFile(file: File): Promise<EmailUploadResult> {
  return apiUpload<EmailUploadResult>("/api/emails/upload", file);
}

export { API_BASE_URL };
