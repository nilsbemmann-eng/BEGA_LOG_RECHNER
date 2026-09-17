"""Authentifizierung/Autorisierung (Abschnitt 3, 10.3).

Reihenfolge in `get_current_user`:
1. `Authorization: Bearer <token>` - echter Login-Token aus
   `POST /api/auth/login` (siehe `app/security_jwt.py`). Das ist der einzige
   Weg, der ein Passwort prueft.
2. `X-User-Id`-Header - Entwickler-/Integrations-Komfort (z. B. Tests,
   interne Skripte), keine Passwortpruefung.
3. Nur in Nicht-Produktivumgebungen (`Settings.environment != "production"`):
   Default-Admin-Fallback ohne jede Authentifizierung, damit lokale
   Entwicklung/Tests ohne Login-Zeremonie funktionieren.

Abschnitt 10.3 fordert perspektivisch echtes OAuth2/OpenID Connect (z. B.
Azure AD/Keycloak/Auth0) - der JWT-Login hier ist ein first-party Zwischenschritt,
kein Ersatz dafuer (siehe docs/OFFENE_ENTSCHEIDUNGEN.md).
"""
from __future__ import annotations

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database import get_db
from app.models.user import User, UserRole
from app.security_jwt import InvalidTokenError, decode_access_token


def get_current_user(
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> User:
    if authorization:
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Ungueltiges Authorization-Header-Format (erwartet: 'Bearer <token>').")
        try:
            user_id = decode_access_token(token, settings.jwt_secret_key, settings.jwt_algorithm)
        except InvalidTokenError as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Ungueltiges oder abgelaufenes Token: {exc}") from exc
        user = db.get(User, user_id)
        if user is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unbekannter Benutzer (Token).")
        if not user.active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Benutzer ist deaktiviert.")
        return user

    if x_user_id:
        user = db.get(User, x_user_id)
        if user is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unbekannter Benutzer (X-User-Id).")
        if not user.active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Benutzer ist deaktiviert.")
        return user

    if settings.environment != "production":
        default_user = db.query(User).filter(User.role == UserRole.ADMIN, User.active.is_(True)).first()
        if default_user is not None:
            return default_user

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Kein Benutzer authentifiziert. 'Authorization: Bearer <token>' (siehe POST /api/auth/login) "
        "oder 'X-User-Id' senden.",
    )


def require_role(*allowed_roles: UserRole):
    def _dependency(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Rolle '{current_user.role}' ist fuer diese Aktion nicht berechtigt.",
            )
        return current_user

    return _dependency
