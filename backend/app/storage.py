"""Dokumentenspeicher-Abstraktion (Abschnitt 10.1, 13).

`storage_reference` in `Attachment`/Export-Ergebnissen ist bewusst ein
opaker String, den nur die konkrete `StorageBackend`-Implementierung
interpretiert. Der MVP-Standard ist ein lokales Dateisystem
(`LocalFileSystemStorage`); fuer den produktiven Einsatz ist ein
verschluesselter Object Store (S3-kompatibel, Azure Blob Storage) zu
integrieren (siehe docs/OFFENE_ENTSCHEIDUNGEN.md).
"""
from __future__ import annotations

import hashlib
import os
from abc import ABC, abstractmethod


class StorageBackend(ABC):
    @abstractmethod
    def save(self, content: bytes, suggested_name: str) -> str:
        """Speichert Inhalte und gibt eine `storage_reference` zurueck."""

    @abstractmethod
    def load(self, storage_reference: str) -> bytes:
        """Laedt Inhalte anhand einer `storage_reference`."""


class LocalFileSystemStorage(StorageBackend):
    def __init__(self, base_path: str) -> None:
        self._base_path = base_path
        os.makedirs(self._base_path, exist_ok=True)

    def save(self, content: bytes, suggested_name: str) -> str:
        digest = hashlib.sha256(content).hexdigest()
        _, extension = os.path.splitext(suggested_name)
        relative_path = os.path.join(digest[:2], f"{digest}{extension}")
        absolute_path = os.path.join(self._base_path, relative_path)
        os.makedirs(os.path.dirname(absolute_path), exist_ok=True)
        if not os.path.exists(absolute_path):
            with open(absolute_path, "wb") as handle:
                handle.write(content)
        return relative_path

    def load(self, storage_reference: str) -> bytes:
        with open(os.path.join(self._base_path, storage_reference), "rb") as handle:
            return handle.read()


def sha256_hex(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()
