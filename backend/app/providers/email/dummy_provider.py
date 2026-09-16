"""Test-Fake fuer `EmailProvider`, liefert eine vorkonfigurierte Liste
von Nachrichten ohne echte Netzwerkverbindung."""
from __future__ import annotations

from datetime import datetime

from app.providers.base import EmailMessage


class DummyEmailProvider:
    def __init__(self, messages: list[EmailMessage] | None = None) -> None:
        self._messages = messages or []

    def fetch_messages(self, folder: str, since: datetime | None = None) -> list[EmailMessage]:
        return list(self._messages)
