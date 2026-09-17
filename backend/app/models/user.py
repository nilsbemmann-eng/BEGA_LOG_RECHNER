from __future__ import annotations

import enum

from sqlalchemy import Boolean, Enum, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, generate_uuid


class UserRole(str, enum.Enum):
    """Rollen aus Abschnitt 3 des technischen Berichts."""

    ADMIN = "admin"
    PRUEFER = "pruefer"
    VIEWER = "viewer"


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole, name="user_role"), nullable=False, default=UserRole.VIEWER)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Nullable: Nutzer ohne Passwort (z. B. per Altbestand/Skript angelegt)
    # koennen sich nicht per Login anmelden, aber weiterhin ueber die
    # bestehenden Dev-Auth-Wege (X-User-Id, Default-Admin-Fallback in
    # Entwicklungsumgebungen) verwendet werden - siehe app/auth.py.
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<User {self.email} ({self.role})>"
