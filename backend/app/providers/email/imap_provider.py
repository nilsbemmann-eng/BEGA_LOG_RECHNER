"""IMAP-basierter `EmailProvider` (Abschnitt 4.1, 10.2).

Zugangsdaten kommen ausschliesslich aus `Settings` (Umgebungsvariablen /
Secret-Management), niemals aus Konstanten in diesem Modul (Abschnitt 13).
Unterstuetzt handelsuebliche IMAP-Postfaecher (Exchange/O365 IMAP, Gmail,
generische IMAP-Server). Fuer Microsoft Graph oder proprietaere APIs ist ein
eigener `EmailProvider` zu implementieren (siehe docs/OFFENE_ENTSCHEIDUNGEN.md,
Punkt 1).
"""
from __future__ import annotations

import email as email_lib
import imaplib
from datetime import datetime
from email.header import decode_header
from email.utils import parsedate_to_datetime

from app.providers.base import EmailAttachmentData, EmailMessage


class ImapEmailProvider:
    def __init__(self, host: str, user: str, password: str, use_ssl: bool = True) -> None:
        self._host = host
        self._user = user
        self._password = password
        self._use_ssl = use_ssl

    def _connect(self) -> imaplib.IMAP4:
        client: imaplib.IMAP4 = imaplib.IMAP4_SSL(self._host) if self._use_ssl else imaplib.IMAP4(self._host)
        client.login(self._user, self._password)
        return client

    def fetch_messages(self, folder: str, since: datetime | None = None) -> list[EmailMessage]:
        client = self._connect()
        try:
            client.select(folder, readonly=True)
            search_criteria = "ALL"
            if since is not None:
                search_criteria = f'(SINCE "{since.strftime("%d-%b-%Y")}")'
            status, data = client.search(None, search_criteria)
            if status != "OK":
                return []
            messages: list[EmailMessage] = []
            for message_id in data[0].split():
                status, message_data = client.fetch(message_id, "(RFC822)")
                if status != "OK" or not message_data or message_data[0] is None:
                    continue
                raw_bytes = message_data[0][1]
                messages.append(self._parse_message(raw_bytes))
            return messages
        finally:
            client.logout()

    @staticmethod
    def _decode(value: str | None) -> str:
        if not value:
            return ""
        parts = decode_header(value)
        decoded = ""
        for text, charset in parts:
            if isinstance(text, bytes):
                decoded += text.decode(charset or "utf-8", errors="replace")
            else:
                decoded += text
        return decoded

    def _parse_message(self, raw_bytes: bytes) -> EmailMessage:
        msg = email_lib.message_from_bytes(raw_bytes)
        body_text = ""
        body_html: str | None = None
        attachments: list[EmailAttachmentData] = []

        if msg.is_multipart():
            for part in msg.walk():
                content_disposition = str(part.get("Content-Disposition") or "")
                content_type = part.get_content_type()
                if "attachment" in content_disposition or part.get_filename():
                    filename = self._decode(part.get_filename()) or "attachment"
                    payload = part.get_payload(decode=True) or b""
                    attachments.append(
                        EmailAttachmentData(filename=filename, mime_type=content_type, content=payload)
                    )
                elif content_type == "text/plain" and body_text == "":
                    body_text = self._decode_payload(part)
                elif content_type == "text/html" and body_html is None:
                    body_html = self._decode_payload(part)
        else:
            body_text = self._decode_payload(msg)

        received_at = datetime.utcnow()
        date_header = msg.get("Date")
        if date_header:
            try:
                received_at = parsedate_to_datetime(date_header)
            except (TypeError, ValueError):
                pass

        return EmailMessage(
            external_message_id=(msg.get("Message-ID") or "").strip(),
            sender=self._decode(msg.get("From")),
            recipients=[addr.strip() for addr in self._decode(msg.get("To")).split(",") if addr.strip()],
            cc_recipients=[addr.strip() for addr in self._decode(msg.get("Cc")).split(",") if addr.strip()],
            subject=self._decode(msg.get("Subject")),
            received_at=received_at,
            body_text=body_text,
            body_html=body_html,
            attachments=attachments,
            raw_metadata={"headers": dict(msg.items())},
        )

    @staticmethod
    def _decode_payload(part) -> str:
        payload = part.get_payload(decode=True)
        if payload is None:
            return ""
        charset = part.get_content_charset() or "utf-8"
        return payload.decode(charset, errors="replace")
