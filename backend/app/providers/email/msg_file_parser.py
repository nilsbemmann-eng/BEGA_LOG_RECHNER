"""Parser fuer Outlook-.msg-Dateien (manueller Upload, Abschnitt 4.1/4.2).

`.msg` ist Outlooks natives Format (eine OLE-Compound-Datei), kein rohes
RFC822-Format wie `.eml`. `extract-msg` liest die interne Struktur, und diese
Funktion bildet das Ergebnis auf dieselbe `EmailMessage`-Datenklasse ab, die
auch der IMAP-Provider liefert - dadurch durchlaeuft eine hochgeladene
`.msg`-Datei dieselbe Weiterverarbeitung (Duplikaterkennung, Anhang-Import,
OCR/Klassifikation) wie eine per IMAP abgeholte E-Mail (Abschnitt 2).
"""
from __future__ import annotations

import hashlib
import io
import re
from datetime import datetime, timezone

import extract_msg

from app.providers.base import EmailAttachmentData, EmailMessage

_RECIPIENT_SPLIT_RE = re.compile(r"[;,]")


class MsgParsingError(ValueError):
    """Die Datei konnte nicht als gueltige Outlook-.msg-Datei gelesen werden (Abschnitt 14)."""


def _split_recipients(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [part.strip() for part in _RECIPIENT_SPLIT_RE.split(raw) if part.strip()]


def _fallback_message_id(file_bytes: bytes) -> str:
    """Manche .msg-Dateien (z. B. nie versendete Entwuerfe) haben keine
    Message-ID. Ein Hash der Rohdaten haelt die Duplikaterkennung trotzdem
    stabil (Abschnitt 4.1: Erkennung ueber externe Nachrichten-ID)."""
    return f"<msg-upload-{hashlib.sha256(file_bytes).hexdigest()}@local>"


def parse_msg_bytes(file_bytes: bytes) -> EmailMessage:
    # olefile (von extract-msg verwendet) unterscheidet bytes-als-Inhalt von
    # bytes-als-Dateipfad anhand der Laenge (>= 1536 Byte = Inhalt, siehe
    # olefile.OleFileIO.open). Kurze oder beschaedigte Dateien wuerden sonst
    # faelschlich als Dateipfad interpretiert. Ein BytesIO-Objekt ist immer
    # eindeutig als Inhalt erkennbar, unabhaengig von der Groesse.
    try:
        msg = extract_msg.openMsg(io.BytesIO(file_bytes))
    except Exception as exc:  # noqa: BLE001 - extract_msg wirft diverse, teils undokumentierte Fehlertypen
        raise MsgParsingError(f"Datei konnte nicht als .msg gelesen werden: {exc}") from exc

    try:
        attachments: list[EmailAttachmentData] = []
        for attachment in msg.attachments:
            content = attachment.data
            if not isinstance(content, bytes):
                # Eingebettete .msg-Anhaenge (verschachtelte E-Mails) werden im
                # MVP uebersprungen - nur echte Dateianhaenge werden uebernommen.
                continue
            filename = attachment.getFilename() or "attachment"
            attachments.append(
                EmailAttachmentData(
                    filename=filename,
                    mime_type=attachment.mimetype or "application/octet-stream",
                    content=content,
                )
            )

        received_at = msg.date or datetime.now(timezone.utc)
        external_message_id = msg.messageId or _fallback_message_id(file_bytes)

        return EmailMessage(
            external_message_id=external_message_id.strip(),
            sender=msg.sender or "",
            recipients=_split_recipients(msg.to),
            cc_recipients=_split_recipients(msg.cc),
            subject=msg.subject or "",
            received_at=received_at,
            body_text=msg.body or "",
            body_html=msg.htmlBody.decode("utf-8", errors="replace") if msg.htmlBody else None,
            attachments=attachments,
            raw_metadata={"source": "msg_upload"},
        )
    finally:
        msg.close()
