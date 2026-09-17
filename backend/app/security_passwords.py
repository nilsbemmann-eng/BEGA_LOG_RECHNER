"""Passwort-Hashing (Abschnitt 13: Zugangsdaten nie im Klartext speichern).

bcrypt via passlib - Standardverfahren, kein Grund fuer eine eigene
Implementierung."""
from __future__ import annotations

from passlib.context import CryptContext

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain_password: str) -> str:
    return _pwd_context.hash(plain_password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    return _pwd_context.verify(plain_password, password_hash)
