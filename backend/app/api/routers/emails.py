from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_storage_backend
from app.auth import get_current_user
from app.config import Settings, get_settings
from app.database import get_db
from app.errors import MailboxUnavailableError, NotFoundError
from app.models.email import Email
from app.models.mailbox import Mailbox
from app.providers.factory import build_email_provider
from app.schemas import EmailOut, EmailSyncResult
from app.services.email_service import sync_mailbox
from app.storage import StorageBackend

router = APIRouter(prefix="/api/emails", tags=["emails"], dependencies=[Depends(get_current_user)])


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


@router.get("", response_model=list[EmailOut])
def list_emails(db: Session = Depends(get_db)) -> list[Email]:
    return list(db.execute(select(Email).order_by(Email.received_at.desc())).scalars().all())


@router.get("/{email_id}", response_model=EmailOut)
def get_email(email_id: str, db: Session = Depends(get_db)) -> Email:
    email = db.get(Email, email_id)
    if email is None:
        raise NotFoundError(f"E-Mail {email_id} nicht gefunden", entity_type="Email", entity_id=email_id)
    return email
