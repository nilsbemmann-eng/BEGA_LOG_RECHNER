"""Login (Abschnitt 3, 10.3) - siehe app/auth.py fuer die Token-Validierung
und docs/OFFENE_ENTSCHEIDUNGEN.md fuer den Stand zu OAuth2/OIDC."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.config import Settings, get_settings
from app.database import get_db
from app.models.user import User
from app.schemas import ChangePasswordRequest, LoginRequest, TokenOut, UserOut
from app.security_jwt import create_access_token
from app.security_passwords import hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=TokenOut)
def login(request: LoginRequest, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)) -> TokenOut:
    user = db.execute(select(User).where(User.email == request.email)).scalars().first()
    # Bewusst dieselbe Fehlermeldung fuer "unbekannte E-Mail" und "falsches
    # Passwort" - verhindert, dass sich per Login-Endpunkt herausfinden
    # laesst, welche E-Mail-Adressen im System existieren.
    invalid_credentials = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="E-Mail oder Passwort ist falsch.")
    if user is None or not user.password_hash:
        raise invalid_credentials
    if not verify_password(request.password, user.password_hash):
        raise invalid_credentials
    if not user.active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Benutzer ist deaktiviert.")

    token = create_access_token(user.id, settings.jwt_secret_key, settings.jwt_algorithm, settings.jwt_expire_minutes)
    return TokenOut(access_token=token, expires_in_minutes=settings.jwt_expire_minutes, user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
def get_me(current_user: User = Depends(get_current_user)) -> User:
    return current_user


@router.post("/change-password", status_code=204, response_model=None)
def change_password(
    request: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    if not current_user.password_hash or not verify_password(request.current_password, current_user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Aktuelles Passwort ist falsch.")
    current_user.password_hash = hash_password(request.new_password)
    db.commit()
