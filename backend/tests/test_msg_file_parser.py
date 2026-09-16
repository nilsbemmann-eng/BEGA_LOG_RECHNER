import io
from dataclasses import dataclass, field
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from app.providers.email.msg_file_parser import MsgParsingError, parse_msg_bytes


@dataclass
class _FakeAttachment:
    filename: str
    mimetype: str | None
    data: object

    def getFilename(self) -> str:  # noqa: N802 - Name der extract_msg-API nachgebildet
        return self.filename


@dataclass
class _FakeMsg:
    sender: str | None = "Max Muster <max@example.invalid>"
    to: str | None = "a@example.invalid; b@example.invalid"
    cc: str | None = "c@example.invalid"
    subject: str | None = "Frachtrechnung 4711"
    date: datetime | None = datetime(2026, 5, 1, 10, 30, tzinfo=timezone.utc)
    body: str | None = "Anbei die Rechnung."
    htmlBody: bytes | None = b"<html><body>Anbei die Rechnung.</body></html>"
    messageId: str | None = "<abc123@outlook.example>"
    attachments: list = field(default_factory=list)
    closed: bool = False

    def close(self) -> None:
        self.closed = True


def _msg_bytes() -> bytes:
    return b"fake-ole-compound-file-bytes"


def test_parse_msg_bytes_maps_all_fields() -> None:
    fake_msg = _FakeMsg(
        attachments=[_FakeAttachment("rechnung.pdf", "application/pdf", b"%PDF-1.4 ...")]
    )
    with patch("app.providers.email.msg_file_parser.extract_msg.openMsg", return_value=fake_msg) as mock_open:
        message = parse_msg_bytes(_msg_bytes())

    # Wird als BytesIO uebergeben (nicht als rohe bytes), damit olefile es nie
    # als Dateipfad fehlinterpretiert (siehe Kommentar in msg_file_parser.py).
    mock_open.assert_called_once()
    passed_arg = mock_open.call_args[0][0]
    assert isinstance(passed_arg, io.BytesIO)
    assert passed_arg.getvalue() == _msg_bytes()
    assert message.external_message_id == "<abc123@outlook.example>"
    assert message.sender == "Max Muster <max@example.invalid>"
    assert message.recipients == ["a@example.invalid", "b@example.invalid"]
    assert message.cc_recipients == ["c@example.invalid"]
    assert message.subject == "Frachtrechnung 4711"
    assert message.received_at == datetime(2026, 5, 1, 10, 30, tzinfo=timezone.utc)
    assert message.body_text == "Anbei die Rechnung."
    assert message.body_html == "<html><body>Anbei die Rechnung.</body></html>"
    assert len(message.attachments) == 1
    assert message.attachments[0].filename == "rechnung.pdf"
    assert message.attachments[0].mime_type == "application/pdf"
    assert message.attachments[0].content == b"%PDF-1.4 ..."
    assert fake_msg.closed is True


def test_parse_msg_bytes_falls_back_to_hash_when_no_message_id() -> None:
    fake_msg = _FakeMsg(messageId=None)
    with patch("app.providers.email.msg_file_parser.extract_msg.openMsg", return_value=fake_msg):
        message_a = parse_msg_bytes(_msg_bytes())
    with patch("app.providers.email.msg_file_parser.extract_msg.openMsg", return_value=fake_msg):
        message_b = parse_msg_bytes(_msg_bytes())

    assert message_a.external_message_id.startswith("<msg-upload-")
    # Gleicher Rohinhalt -> gleiche generierte ID, damit Duplikaterkennung stabil bleibt.
    assert message_a.external_message_id == message_b.external_message_id


def test_parse_msg_bytes_skips_embedded_message_attachments() -> None:
    embedded = _FakeAttachment("embedded.msg", None, object())  # kein bytes-Inhalt
    real = _FakeAttachment("liste.xlsx", "application/vnd.ms-excel", b"PK...")
    fake_msg = _FakeMsg(attachments=[embedded, real])

    with patch("app.providers.email.msg_file_parser.extract_msg.openMsg", return_value=fake_msg):
        message = parse_msg_bytes(_msg_bytes())

    assert len(message.attachments) == 1
    assert message.attachments[0].filename == "liste.xlsx"


def test_parse_msg_bytes_raises_msg_parsing_error_on_invalid_file() -> None:
    with patch("app.providers.email.msg_file_parser.extract_msg.openMsg", side_effect=OSError("not an OLE file")):
        with pytest.raises(MsgParsingError):
            parse_msg_bytes(b"not-a-real-msg-file")


def test_parse_msg_bytes_rejects_short_garbage_without_mocking() -> None:
    """Regressionstest (ohne Mock): olefile unterscheidet bytes-als-Inhalt von
    bytes-als-Dateipfad anhand der Laenge (< 1536 Byte = Pfad). Ohne den
    BytesIO-Wrapper in `parse_msg_bytes` wuerde eine kurze, ungueltige Datei
    faelschlich als 'Datei nicht gefunden' statt als ungueltiges Format
    gemeldet."""
    with pytest.raises(MsgParsingError) as exc_info:
        parse_msg_bytes(b"das ist definitiv keine echte .msg-Datei")
    assert "not an ole" in str(exc_info.value).lower() or "ole2" in str(exc_info.value).lower()


def test_parse_msg_bytes_handles_missing_optional_fields() -> None:
    fake_msg = _FakeMsg(sender=None, to=None, cc=None, subject=None, body=None, htmlBody=None, date=None)
    with patch("app.providers.email.msg_file_parser.extract_msg.openMsg", return_value=fake_msg):
        message = parse_msg_bytes(_msg_bytes())

    assert message.sender == ""
    assert message.recipients == []
    assert message.cc_recipients == []
    assert message.subject == ""
    assert message.body_text == ""
    assert message.body_html is None
    assert message.received_at is not None  # Fallback auf "jetzt"
