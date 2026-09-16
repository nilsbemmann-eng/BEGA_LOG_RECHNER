"use client";

import { useRef, useState } from "react";
import { uploadEmailFile } from "../lib/api";
import type { EmailUploadResult } from "../lib/types";

export function MsgUploadForm() {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<EmailUploadResult | null>(null);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    const file = fileInputRef.current?.files?.[0];
    if (!file) {
      return;
    }

    setUploading(true);
    setError(null);
    setResult(null);
    try {
      const uploadResult = await uploadEmailFile(file);
      setResult(uploadResult);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload fehlgeschlagen");
    } finally {
      setUploading(false);
    }
  }

  return (
    <div className="card">
      <h2>E-Mail aus Outlook hochladen (.msg)</h2>
      <p className="kv-label">
        Eine als .msg exportierte Outlook-E-Mail wird genauso verarbeitet wie eine
        per Postfach-Synchronisation abgeholte Nachricht (Anhaenge, Duplikaterkennung).
      </p>
      <form onSubmit={handleSubmit} className="filter-bar">
        <div className="filter-field">
          <label htmlFor="msg-file">.msg-Datei</label>
          <input id="msg-file" ref={fileInputRef} type="file" accept=".msg" required />
        </div>
        <button type="submit" className="btn btn-primary" disabled={uploading}>
          {uploading ? "Wird hochgeladen..." : "Hochladen"}
        </button>
      </form>

      {error && <p className="form-error">{error}</p>}

      {result && !error && (
        <p className={result.is_duplicate ? "kv-label" : "result-count"}>
          {result.is_duplicate
            ? `Bereits vorhanden (Duplikat): "${result.subject}"`
            : `Importiert: "${result.subject}" (${result.attachment_count} Anhang${result.attachment_count === 1 ? "" : "e"})`}
        </p>
      )}
    </div>
  );
}
