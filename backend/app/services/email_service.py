"""E-Mail-Synchronisation mit Duplikaterkennung (Abschnitt 4.1).

Duplikate werden ueber die Kombination `mailbox_id` + `external_message_id`
(Datenbank-`UniqueConstraint`, siehe `app/models/email.py`) sowie den
SHA-256-Hash jedes Anhangs erkannt.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.attachment import Attachment
from app.models.document import Document, DocumentType, OcrStatus
from app.models.email import Email, EmailProcessingStatus
from app.models.mailbox import Mailbox
from app.providers.base import EmailProvider
from app.storage import StorageBackend, sha256_hex


def sync_mailbox(db: Session, mailbox: Mailbox, provider: EmailProvider, storage: StorageBackend) -> tuple[int, int, int]:
    """Gibt `(fetched_count, imported_count, duplicate_count)` zurueck."""
    messages = provider.fetch_messages(folder=mailbox.name, since=mailbox.last_sync_at)
    imported = 0
    duplicates = 0

    for message in messages:
        existing = db.execute(
            select(Email).where(Email.mailbox_id == mailbox.id, Email.external_message_id == message.external_message_id)
        ).scalars().first()
        if existing is not None:
            duplicates += 1
            continue

        email = Email(
            external_message_id=message.external_message_id,
            mailbox_id=mailbox.id,
            sender=message.sender,
            recipients=", ".join(message.recipients),
            cc_recipients=", ".join(message.cc_recipients),
            subject=message.subject,
            received_at=message.received_at,
            body_text=message.body_text,
            body_html=message.body_html,
            processing_status=EmailProcessingStatus.RECEIVED,
            raw_metadata=message.raw_metadata,
        )
        for attachment_data in message.attachments:
            file_hash = sha256_hex(attachment_data.content)
            storage_reference = storage.save(attachment_data.content, attachment_data.filename)
            attachment = Attachment(
                filename=attachment_data.filename,
                mime_type=attachment_data.mime_type,
                file_hash=file_hash,
                storage_reference=storage_reference,
                file_size=len(attachment_data.content),
            )
            # Stub-Dokument je Anhang, damit /documents/{id}/process ueber eine
            # stabile Dokument-ID angesprochen werden kann (Abschnitt 11).
            attachment.document = Document(document_type=DocumentType.SONSTIGES, ocr_status=OcrStatus.PENDING, page_count=0)
            email.attachments.append(attachment)
        db.add(email)
        imported += 1

    mailbox.last_sync_at = datetime.now(timezone.utc)
    db.flush()
    return len(messages), imported, duplicates
