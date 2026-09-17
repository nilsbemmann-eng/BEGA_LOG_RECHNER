"""Verschluesselung fuer in der Datenbank gespeicherte API-Schluessel
(Abschnitt 13: Zugangsdaten duerfen nicht im Klartext liegen).

Admin-pflegbare Zugangsdaten (aktuell: TomTom-API-Key fuers Routing, siehe
`app/models/integration_credential.py`) werden mit Fernet (symmetrische,
authentifizierte Verschluesselung) verschluesselt gespeichert. Der
Verschluesselungsschluessel selbst ist NIE in der Datenbank, sondern
ausschliesslich eine Umgebungsvariable (`CREDENTIAL_ENCRYPTION_KEY`,
generiert via `Fernet.generate_key()`) - das ist dasselbe Prinzip wie fuer
alle anderen Zugangsdaten im Projekt (siehe app/config.py), nur dass hier
zusaetzlich der *Klartextwert* (der API-Key selbst) nicht im Code/ENV der
Anwendung liegt, sondern vom Administrator zur Laufzeit ueber die API
gepflegt wird.
"""
from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken


class CredentialEncryptionNotConfiguredError(RuntimeError):
    """CREDENTIAL_ENCRYPTION_KEY ist nicht gesetzt."""


class CredentialDecryptionError(RuntimeError):
    """Der gespeicherte Ciphertext konnte nicht entschluesselt werden (z. B.
    falscher/rotierter Schluessel)."""


def encrypt_credential(plaintext_value: str, encryption_key: str) -> str:
    return Fernet(encryption_key.encode()).encrypt(plaintext_value.encode()).decode()


def decrypt_credential(encrypted_value: str, encryption_key: str) -> str:
    try:
        return Fernet(encryption_key.encode()).decrypt(encrypted_value.encode()).decode()
    except InvalidToken as exc:
        raise CredentialDecryptionError("Gespeicherter Wert konnte nicht entschluesselt werden") from exc
