import type { AuditStatus } from "../lib/types";

const STYLE_BY_STATUS: Record<AuditStatus, string> = {
  BESTANDEN: "badge-success",
  FREIGEGEBEN: "badge-success",
  ABWEICHUNG: "badge-warning",
  MANUELLE_PRUEFUNG: "badge-warning",
  RUECKFRAGE: "badge-info",
  FEHLER: "badge-danger",
};

export function StatusBadge({ status }: { status: AuditStatus }) {
  const className = STYLE_BY_STATUS[status] ?? "badge-info";
  return <span className={`badge ${className}`}>{status}</span>;
}
