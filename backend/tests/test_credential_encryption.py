import pytest
from cryptography.fernet import Fernet

from app.services.credential_encryption import CredentialDecryptionError, decrypt_credential, encrypt_credential


def test_encrypt_then_decrypt_round_trips() -> None:
    key = Fernet.generate_key().decode()
    ciphertext = encrypt_credential("super-secret-api-key", key)

    assert ciphertext != "super-secret-api-key"
    assert decrypt_credential(ciphertext, key) == "super-secret-api-key"


def test_decrypt_with_wrong_key_raises() -> None:
    key = Fernet.generate_key().decode()
    other_key = Fernet.generate_key().decode()
    ciphertext = encrypt_credential("super-secret-api-key", key)

    with pytest.raises(CredentialDecryptionError):
        decrypt_credential(ciphertext, other_key)
