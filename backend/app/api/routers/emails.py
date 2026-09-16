from __future__ import annotations

from fastapi import APIRouter, Depends, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_storage_backend
from app.auth import get_current_user
from app.config import Settings, get_settings
from app.database import get_db
from app.errors import EmailFileCorruptError, MailboxUnavailableError, NotFoundError, UnsupportedFileFormatError
from app.models.email import Email
from app.models.mailbox import Mailbox
from app.providers.email.msg_file_parser import MsgParsingError, parse_msg_bytes
from app.providers.factory import build_email_provider
from app.schemas import EmailOut, EmailSyncResult, EmailUploadResult
from app.services.email_service import get_or_create_manual_upload_mailbox, persist_message, sync_mailbox
from app.storage import StorageBackend

router = APIRouter(prefix="/api/emails", tags=["emails"], dependencies=[Depends(get_current_user)])

_SUPPORTED_UPLOAD_SUFFIXES = (".msg",)


@router.post("/sync", response_model=EmailSyncResult)
def sync_emails(
    mailbox_id: str,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    storage: StorageBackend = Depends(get_storage_backend),
) -> EmailSyncResult:
    mailbox = db.get(Mailbox, mailbox_id)
    if mailbox is None:
        raise NotFoundError(f"Postfach {mailbox_id} nicht gefunden", entity_type="Mailbox", entity_id=mailbox_id)

    try:
        provider = build_email_provider(settings)
        fetched, imported, duplicates = sync_mailbox(db, mailbox, provider, storage)
    except (ValueError, OSError, ConnectionError) as exc:
        raise MailboxUnavailableError(f"Postfach nicht erreichbar: {exc}", entity_type="Mailbox", entity_id=mailbox_id) from exc

    db.commit()
    return EmailSyncResult(mailbox_id=mailbox.id, fetched_count=fetched, imported_count=imported, duplicate_count=duplicates)


@router.post("/upload", response_model=EmailUploadResult)
async def upload_email_file(
    file: UploadFile,
    db: Session = Depends(get_db),
    storage: StorageBackend = Depends(get_storage_backend),
) -> EmailUploadResult:
    """Manueller Upload einer Outlook-`.msg`-Datei (Abschnitt 4.1, 4.2).

    Die Nachricht wird ueber `persist_message` genau wie eine per IMAP
    abgeholte E-Mail verarbeitet (gleiche Duplikaterkennung, gleiche
    Anhang-/Dokument-Stub-Erzeugung).
    """
    if not file.filename or not file.filename.lower().endswith(_SUPPORTED_UPLOAD_SUFFIXES):
        raise UnsupportedFileFormatError(
            f"Nicht unterstuetztes Dateiformat fuer E-Mail-Upload: '{file.filename}'. Erlaubt: {_SUPPORTED_UPLOAD_SUFFIXES}."
        )

    content = await file.read()
    try:
        message = parse_msg_bytes(content)
    except MsgParsingError as exc:
        raise EmailFileCorruptError(str(exc), entity_type="Email") from exc

    mailbox = get_or_create_manual_upload_mailbox(db)
    email, is_duplicate = persist_message(db, mailbox, message, storage)
    db.commit()

    return EmailUploadResult(
        email_id=email.id if email else None,
        is_duplicate=is_duplicate,
        subject=message.subject,
        attachment_count=len(message.attachments),
    )


@router.get("", response_model=list[EmailOut])
def list_emails(db: Session = Depends(get_db)) -> list[Email]:
    return list(db.execute(select(Email).order_by(Email.received_at.desc())).scalars().all())


@router.get("/{email_id}", response_model=EmailOut)
def get_email(email_id: str, db: Session = Depends(get_db)) -> Email:
    email = db.get(Email, email_id)
    if email is None:
        raise NotFoundError(f"E-Mail {email_id} nicht gefunden", entity_type="Email", entity_id=email_id)
    return email
