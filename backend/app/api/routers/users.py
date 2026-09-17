"""Benutzerverwaltung (Abschnitt 3: Rollen Admin/Pruefer/Viewer) - nur fuer
Administratoren. Nutzer werden deaktiviert, nie geloescht (siehe
`User.active`), da bestehende `AuditLogEntry`/`AuditResult.approved_by`
weiterhin auf die Benutzer-ID verweisen (Nachvollziehbarkeit, Abschnitt 16.6)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_role
from app.database import get_db
from app.errors import EmailAlreadyExistsError, NotFoundError
from app.models.user import User, UserRole
from app.schemas import SetPasswordRequest, UserCreateRequest, UserOut, UserUpdateRequest
from app.security_passwords import hash_password

router = APIRouter(prefix="/api/users", tags=["users"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[UserOut])
def list_users(
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_role(UserRole.ADMIN)),
) -> list[User]:
    return list(db.execute(select(User).order_by(User.name)).scalars().all())


@router.post("", response_model=UserOut, status_code=201)
def create_user(
    request: UserCreateRequest,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_role(UserRole.ADMIN)),
) -> User:
    if db.execute(select(User).where(User.email == request.email)).scalars().first() is not None:
        raise EmailAlreadyExistsError(f"E-Mail-Adresse '{request.email}' ist bereits vergeben.")

    user = User(
        name=request.name,
        email=request.email,
        role=UserRole(request.role),
        password_hash=hash_password(request.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.patch("/{user_id}", response_model=UserOut)
def update_user(
    user_id: str,
    request: UserUpdateRequest,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_role(UserRole.ADMIN)),
) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise NotFoundError(f"Benutzer {user_id} nicht gefunden", entity_type="User", entity_id=user_id)

    if request.name is not None:
        user.name = request.name
    if request.role is not None:
        user.role = UserRole(request.role)
    if request.active is not None:
        user.active = request.active
    db.commit()
    db.refresh(user)
    return user


@router.post("/{user_id}/set-password", status_code=204, response_model=None)
def set_user_password(
    user_id: str,
    request: SetPasswordRequest,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_role(UserRole.ADMIN)),
) -> None:
    """Administrator setzt ein neues Passwort fuer einen Benutzer (Erstpasswort
    oder "Passwort vergessen" - kein Self-Service-Reset-per-E-Mail im MVP,
    siehe docs/OFFENE_ENTSCHEIDUNGEN.md)."""
    user = db.get(User, user_id)
    if user is None:
        raise NotFoundError(f"Benutzer {user_id} nicht gefunden", entity_type="User", entity_id=user_id)
    user.password_hash = hash_password(request.new_password)
    db.commit()
