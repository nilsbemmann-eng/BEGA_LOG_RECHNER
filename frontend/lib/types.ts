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
