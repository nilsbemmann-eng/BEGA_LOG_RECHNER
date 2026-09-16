"""Authentifizierungs-/Autorisierungs-Platzhalter.

Abschnitt 10.3 fordert OAuth2/OpenID Connect. Diese Datei stellt bewusst nur
die Grenzflaeche bereit (`get_current_user`, `require_role`), damit
Router-Code bereits rollenbasiert (Abschnitt 3) geschrieben werden kann, ohne
sich an eine konkrete IdP-Implementierung zu binden.

MVP-Verhalten: der Benutzer wird ueber den Header `X-User-Id` (eine
`users.id`) identifiziert. Ist kein Header gesetzt, wird in der Entwicklung
ein Default-Admin-Benutzer angenommen. Fuer den produktiven Einsatz MUSS
dies durch eine echte OIDC-Anbindung (z. B. `fastapi`-Middleware mit
Token-Validierung gegen Azure AD/Keycloak/Auth0) ersetzt werden - siehe
docs/OFFENE_ENTSCHEIDUNGEN.md.
"""
from __future__ import annotations

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User, UserRole


def get_current_user(
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
    db: Session = Depends(get_db),
) -> User:
    if x_user_id:
        user = db.get(User, x_user_id)
        if user is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unbekannter Benutzer (X-User-Id).")
        if not user.active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Benutzer ist deaktiviert.")
        return user

    default_user = db.query(User).filter(User.role == UserRole.ADMIN, User.active.is_(True)).first()
    if default_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Kein Benutzer authentifiziert und kein Default-Admin vorhanden. "
            "Header 'X-User-Id' senden oder OIDC-Anbindung konfigurieren.",
        )
    return default_user


def require_role(*allowed_roles: UserRole):
    def _dependency(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Rolle '{current_user.role}' ist fuer diese Aktion nicht berechtigt.",
            )
        return current_user

    return _dependency
