"""JWT-Ausstellung/-Validierung fuer den Login (Abschnitt 10.3: perspektivisch
durch echte OAuth2/OIDC-Anbindung zu ersetzen, siehe
docs/OFFENE_ENTSCHEIDUNGEN.md). Bis dahin ist dies der einzige Mechanismus,
der einen Benutzer ueber ein selbst ausgestelltes, zeitlich begrenztes Token
authentifiziert (statt der bisherigen reinen `X-User-Id`-Kennzeichnung ohne
Passwortpruefung)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt


class InvalidTokenError(ValueError):
    """Das Token ist ungueltig, abgelaufen oder falsch signiert."""


def create_access_token(user_id: str, secret_key: str, algorithm: str, expire_minutes: int) -> str:
    now = datetime.now(timezone.utc)
    payload = {"sub": user_id, "iat": now, "exp": now + timedelta(minutes=expire_minutes)}
    return jwt.encode(payload, secret_key, algorithm=algorithm)


def decode_access_token(token: str, secret_key: str, algorithm: str) -> str:
    """Gibt die Benutzer-ID (`sub`-Claim) zurueck oder wirft `InvalidTokenError`."""
    try:
        payload = jwt.decode(token, secret_key, algorithms=[algorithm])
    except JWTError as exc:
        raise InvalidTokenError(str(exc)) from exc
    subject = payload.get("sub")
    if not subject:
        raise InvalidTokenError("Token enthaelt keinen 'sub'-Claim")
    return subject
