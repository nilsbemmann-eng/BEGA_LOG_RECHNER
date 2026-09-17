import type {
  AuditHistoryFilters,
  AuditResultOut,
  CarrierCreateRequest,
  CarrierOut,
  ChangePasswordRequest,
  EmailOut,
  EmailUploadResult,
  ExportOut,
  LoginRequest,
  SetPasswordRequest,
  ShipmentOut,
  TokenOut,
  UserCreateRequest,
  UserOut,
  UserUpdateRequest,
} from "./types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

const AUTH_TOKEN_STORAGE_KEY = "bega_auth_token";

/** Token wird nur im Browser (localStorage) gehalten - Server Components
 * fuehren ihre eigenen Requests aus und nutzen den Dev-Fallback in
 * app/auth.py (siehe resolveBaseUrl). */
export function getAuthToken(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage.getItem(AUTH_TOKEN_STORAGE_KEY);
  } catch {
    return null;
  }
}

export function setAuthToken(token: string | null): void {
  if (typeof window === "undefined") return;
  try {
    if (token) {
      window.localStorage.setItem(AUTH_TOKEN_STORAGE_KEY, token);
    } else {
      window.localStorage.removeItem(AUTH_TOKEN_STORAGE_KEY);
    }
  } catch {
    // localStorage nicht verfuegbar (z.B. Privatmodus) - Login funktioniert
    // dann nur fuer die laufende Seitenansicht.
  }
}

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number
  ) {
    super(message);
    this.name = "ApiError";
  }
}

function authHeaders(): Record<string, string> {
  const token = getAuthToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

// Server Components (SSR) rufen das Backend direkt unter API_BASE_URL auf.
// Im Browser laufender Code nutzt stattdessen denselben Origin (leerer Base-
// Pfad); `next.config.js` proxied `/api/*` serverseitig zum Backend. Das
// vermeidet CORS und funktioniert auch dann, wenn der Browser das Backend
// nicht direkt erreichen kann (z. B. unterschiedliche interne Hosts/Ports).
function resolveBaseUrl(): string {
  return typeof window === "undefined" ? API_BASE_URL : "";
}

/** Liest die einheitliche Fehlerantwort aus Abschnitt 14 (`ErrorResponse`
 * in backend/app/schemas.py) aus, falls vorhanden, sonst FastAPIs Standard-
 * `{"detail": ...}` (z.B. bei Login-Fehlern), sonst einen generischen Text. */
async function extractErrorMessage(response: Response, path: string): Promise<string> {
  try {
    const body = await response.json();
    if (body && typeof body.message === "string") {
      return body.message;
    }
    if (body && typeof body.detail === "string") {
      return body.detail;
    }
  } catch {
    // Antwort war kein JSON - generische Meldung verwenden.
  }
  return `API-Fehler ${response.status} bei ${path}`;
}

async function throwApiError(response: Response, path: string): Promise<never> {
  throw new ApiError(await extractErrorMessage(response, path), response.status);
}

async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(`${resolveBaseUrl()}${path}`, {
    // Server Components faellt in der Entwicklung auf einen Default-Admin
    // zurueck (siehe app/auth.py); im Browser wird ein evtl. vorhandenes
    // JWT mitgeschickt (siehe authHeaders).
    cache: "no-store",
    headers: { ...authHeaders() },
  });
  if (!response.ok) {
    await throwApiError(response, path);
  }
  return response.json() as Promise<T>;
}

async function apiPost<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(`${resolveBaseUrl()}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    await throwApiError(response, path);
  }
  return response.json() as Promise<T>;
}

async function apiPostNoContent(path: string, body: unknown): Promise<void> {
  const response = await fetch(`${resolveBaseUrl()}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    await throwApiError(response, path);
  }
}

async function apiPatch<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(`${resolveBaseUrl()}${path}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    await throwApiError(response, path);
  }
  return response.json() as Promise<T>;
}

async function apiUpload<T>(path: string, file: File): Promise<T> {
  const formData = new FormData();
  formData.append("file", file);
  const response = await fetch(`${resolveBaseUrl()}${path}`, { method: "POST", body: formData, headers: { ...authHeaders() } });
  if (!response.ok) {
    await throwApiError(response, path);
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

export function login(credentials: LoginRequest): Promise<TokenOut> {
  return apiPost<TokenOut>("/api/auth/login", credentials);
}

export function fetchCurrentUser(): Promise<UserOut> {
  return apiGet<UserOut>("/api/auth/me");
}

export function changeOwnPassword(payload: ChangePasswordRequest): Promise<void> {
  return apiPostNoContent("/api/auth/change-password", payload);
}

export function fetchUsers(): Promise<UserOut[]> {
  return apiGet<UserOut[]>("/api/users");
}

export function createUser(payload: UserCreateRequest): Promise<UserOut> {
  return apiPost<UserOut>("/api/users", payload);
}

export function updateUser(id: string, payload: UserUpdateRequest): Promise<UserOut> {
  return apiPatch<UserOut>(`/api/users/${id}`, payload);
}

export function setUserPassword(id: string, payload: SetPasswordRequest): Promise<void> {
  return apiPostNoContent(`/api/users/${id}/set-password`, payload);
}

export function fetchCarriers(): Promise<CarrierOut[]> {
  return apiGet<CarrierOut[]>("/api/carriers");
}

export function createCarrier(payload: CarrierCreateRequest): Promise<CarrierOut> {
  return apiPost<CarrierOut>("/api/carriers", payload);
}

export { API_BASE_URL };
