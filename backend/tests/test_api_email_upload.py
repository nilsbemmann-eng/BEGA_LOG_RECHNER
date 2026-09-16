from datetime import datetime, timezone
from unittest.mock import patch

from sqlalchemy import select

from app.models.document import Document
from app.models.email import Email
from app.models.mailbox import Mailbox
from app.models.user import User, UserRole
from app.providers.base import EmailAttachmentData, EmailMessage
from app.providers.email.msg_file_parser import MsgParsingError


def _seed_admin(db_session) -> User:
    admin = User(name="Admin", email="admin@example.invalid", role=UserRole.ADMIN, active=True)
    db_session.add(admin)
    db_session.commit()
    return admin


def _sample_message(**overrides) -> EmailMessage:
    defaults = dict(
        external_message_id="<msg-1@outlook.example>",
        sender="Spediteur <spediteur@example.invalid>",
        recipients=["buchhaltung@example.invalid"],
        cc_recipients=[],
        subject="Frachtrechnung 4711",
        received_at=datetime(2026, 5, 1, 10, 0, tzinfo=timezone.utc),
        body_text="Anbei die Rechnung.",
        body_html=None,
        attachments=[EmailAttachmentData(filename="rechnung.pdf", mime_type="application/pdf", content=b"%PDF-1.4 fake")],
        raw_metadata={"source": "msg_upload"},
    )
    defaults.update(overrides)
    return EmailMessage(**defaults)


def test_upload_msg_creates_email_with_attachment_and_document_stub(client, db_session):
    _seed_admin(db_session)

    with patch("app.api.routers.emails.parse_msg_bytes", return_value=_sample_message()):
        response = client.post(
            "/api/emails/upload",
            files={"file": ("rechnung.msg", b"fake-ole-bytes", "application/vnd.ms-outlook")},
        )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["is_duplicate"] is False
    assert payload["subject"] == "Frachtrechnung 4711"
    assert payload["attachment_count"] == 1
    assert payload["email_id"] is not None

    email = db_session.get(Email, payload["email_id"])
    assert email is not None
    assert email.sender == "Spediteur <spediteur@example.invalid>"
    assert len(email.attachments) == 1
    attachment = email.attachments[0]
    assert attachment.filename == "rechnung.pdf"

    # Stub-Dokument wurde automatisch angelegt (wie beim IMAP-Import).
    document = db_session.execute(select(Document).where(Document.attachment_id == attachment.id)).scalars().one()
    assert document.ocr_status == "pending"

    # Nachrichten landen in einer eigenen Pseudo-Mailbox fuer manuelle Uploads.
    mailbox = db_session.get(Mailbox, email.mailbox_id)
    assert mailbox.provider == "manual_upload"


def test_upload_same_msg_twice_is_detected_as_duplicate(client, db_session):
    _seed_admin(db_session)

    with patch("app.api.routers.emails.parse_msg_bytes", return_value=_sample_message()):
        first = client.post("/api/emails/upload", files={"file": ("rechnung.msg", b"fake-ole-bytes", "application/vnd.ms-outlook")})
        second = client.post("/api/emails/upload", files={"file": ("rechnung.msg", b"fake-ole-bytes", "application/vnd.ms-outlook")})

    assert first.json()["is_duplicate"] is False
    assert second.json()["is_duplicate"] is True
    assert second.json()["email_id"] is None

    emails = db_session.execute(select(Email)).scalars().all()
    assert len(emails) == 1


def test_upload_rejects_unsupported_extension(client, db_session):
    _seed_admin(db_session)

    response = client.post("/api/emails/upload", files={"file": ("rechnung.eml", b"irrelevant", "message/rfc822")})

    assert response.status_code == 422
    assert response.json()["error_code"] == "unsupported_file_format"


def test_upload_rejects_corrupt_msg_file(client, db_session):
    _seed_admin(db_session)

    with patch("app.api.routers.emails.parse_msg_bytes", side_effect=MsgParsingError("kaputt")):
        response = client.post("/api/emails/upload", files={"file": ("kaputt.msg", b"garbage", "application/vnd.ms-outlook")})

    assert response.status_code == 422
    assert response.json()["error_code"] == "email_file_corrupt"
