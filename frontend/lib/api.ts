import type { AuditResultOut, EmailOut, ShipmentOut } from "./types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    // MVP-Backend hat noch keine Session-Auth (siehe app/auth.py) - der Server
    // faellt in der Entwicklung auf einen Default-Admin zurueck.
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`API-Fehler ${response.status} bei ${path}`);
  }
  return response.json() as Promise<T>;
}

export function fetchEmails(): Promise<EmailOut[]> {
  return apiGet<EmailOut[]>("/api/emails");
}

export function fetchShipments(): Promise<ShipmentOut[]> {
  return apiGet<ShipmentOut[]>("/api/shipments");
}

export function fetchAudits(): Promise<AuditResultOut[]> {
  return apiGet<AuditResultOut[]>("/api/audits");
}

export function fetchAudit(id: string): Promise<AuditResultOut> {
  return apiGet<AuditResultOut>(`/api/audits/${id}`);
}

export function fetchShipment(id: string): Promise<ShipmentOut> {
  return apiGet<ShipmentOut>(`/api/shipments/${id}`);
}

export { API_BASE_URL };
