from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, generate_uuid


class Customer(Base, TimestampMixin):
    __tablename__ = "customers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    address: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    tax_identifier: Mapped[str | None] = mapped_column(String(50), nullable=True)


class Carrier(Base, TimestampMixin):
    __tablename__ = "carriers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    carrier_code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    billing_rules_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
