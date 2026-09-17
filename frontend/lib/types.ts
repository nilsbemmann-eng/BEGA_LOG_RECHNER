// Entspricht den Pydantic-Schemas in backend/app/schemas.py (Abschnitt 11).

export interface EmailOut {
  id: string;
  external_message_id: string;
  sender: string;
  subject: string;
  received_at: string;
  processing_status: string;
}

export interface ShipmentOut {
  id: string;
  shipment_number: string | null;
  transport_order_number: string | null;
  invoice_number: string | null;
  transport_date: string | null;
  carrier_id: string | null;
  customer_id: string | null;
  weight_kg: string | null;
  pallets: number | null;
  loading_meters: string | null;
  invoiced_km: string | null;
  invoice_amount: string | null;
  currency: string;
  unloading_point_count: number;
}

export interface AuditRuleResultOut {
  rule_code: string;
  rule_name: string;
  status: string;
  actual_value: string | null;
  expected_value: string | null;
  explanation: string;
}

export type AuditStatus =
  | "BESTANDEN"
  | "ABWEICHUNG"
  | "MANUELLE_PRUEFUNG"
  | "FEHLER"
  | "FREIGEGEBEN"
  | "RUECKFRAGE";

export interface AuditResultOut {
  id: string;
  shipment_id: string;
  shipment_number: string | null;
  carrier_name: string | null;
  transport_date: string | null;
  tariff_id: string | null;
  reference_distance_km: string | null;
  invoiced_distance_km: string | null;
  expected_amount: string | null;
  invoiced_amount: string | null;
  difference_amount: string | null;
  difference_percent: string | null;
  status: AuditStatus;
  explanation: string;
  created_at: string;
  rule_results: AuditRuleResultOut[];
}

export interface AuditHistoryFilters {
  q?: string;
  status?: AuditStatus;
  dateFrom?: string;
  dateTo?: string;
}

export interface ExportOut {
  export_id: string;
  file_format: string;
  row_count: number;
  storage_reference: string;
  download_url: string;
}

export interface EmailUploadResult {
  email_id: string | null;
  is_duplicate: boolean;
  subject: string;
  attachment_count: number;
}

// --- Login / Benutzerverwaltung (Abschnitt 3) --------------------------------

export type UserRole = "admin" | "preisadmin" | "pruefer" | "viewer";

export interface UserOut {
  id: string;
  name: string;
  email: string;
  role: UserRole;
  active: boolean;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface TokenOut {
  access_token: string;
  token_type: string;
  expires_in_minutes: number;
  user: UserOut;
}

export interface ChangePasswordRequest {
  current_password: string;
  new_password: string;
}

export interface UserCreateRequest {
  name: string;
  email: string;
  password: string;
  role: UserRole;
}

export interface UserUpdateRequest {
  name?: string;
  role?: UserRole;
  active?: boolean;
}

export interface SetPasswordRequest {
  new_password: string;
}

// --- Spediteure (Frachtfuehrer) -----------------------------------------------

export interface CarrierOut {
  id: string;
  name: string;
  carrier_code: string;
  billing_rules_reference: string | null;
}

export interface CarrierCreateRequest {
  name: string;
  billing_rules_reference?: string | null;
}
