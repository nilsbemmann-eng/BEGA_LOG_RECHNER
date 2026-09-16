from __future__ import annotations

import enum

from sqlalchemy import JSON, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, generate_uuid


class DocumentType(str, enum.Enum):
    """Dokumenttypen aus Abschnitt 4.3."""

    FRACHTRECHNUNG = "frachtrechnung"
    LADELISTE = "ladeliste"
    TRANSPORTAUFTRAG = "transportauftrag"
    ABLIEFERBELEG = "ablieferbeleg"
    PREISANGEBOT = "preisangebot"
    MAUTNACHWEIS = "mautnachweis"
    WARTEZEITNACHWEIS = "wartezeitnachweis"
    PALETTENTAUSCHBELEG = "palettentauschbeleg"
    SONSTIGES = "sonstiges"


class OcrStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    DONE = "done"
    ERROR = "error"


class Document(Base, TimestampMixin):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    attachment_id: Mapped[str] = mapped_column(ForeignKey("attachments.id"), nullable=False, unique=True)
    document_type: Mapped[DocumentType] = mapped_column(
        Enum(DocumentType, name="document_type"), nullable=False, default=DocumentType.SONSTIGES
    )
    classification_confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    ocr_status: Mapped[OcrStatus] = mapped_column(Enum(OcrStatus, name="ocr_status"), nullable=False, default=OcrStatus.PENDING)
    page_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    shipment_id: Mapped[str | None] = mapped_column(ForeignKey("shipments.id"), nullable=True)

    attachment: Mapped["Attachment"] = relationship(back_populates="document")  # noqa: F821
    pages: Mapped[list["DocumentPage"]] = relationship(back_populates="document", cascade="all, delete-orphan")
    extracted_fields: Mapped[list["ExtractedField"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )
    shipment: Mapped["Shipment | None"] = relationship(back_populates="documents")  # noqa: F821


class DocumentPage(Base, TimestampMixin):
    __tablename__ = "document_pages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), nullable=False)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    extracted_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    ocr_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    document: Mapped["Document"] = relationship(back_populates="pages")


class ExtractedField(Base, TimestampMixin):
    """Einzelnes extrahiertes Feld inkl. Konfidenz und Herkunft (Abschnitt 4.4).

    `original_value`/`corrected_value` bleiben getrennt (Abschnitt 12.2 und 16.6):
    eine manuelle Korrektur ueberschreibt niemals den urspruenglichen OCR-Wert.
    """

    __tablename__ = "extracted_fields"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), nullable=False)
    field_name: Mapped[str] = mapped_column(String(100), nullable=False)
    original_value: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    corrected_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    data_type: Mapped[str] = mapped_column(String(20), nullable=False, default="string")
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    source_page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_bbox: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    extraction_method: Mapped[str] = mapped_column(String(50), nullable=False, default="ocr")

    document: Mapped["Document"] = relationship(back_populates="extracted_fields")

    @property
    def effective_value(self) -> str | None:
        """Vom Pruefer korrigierter Wert hat Vorrang, sonst normalisierter, sonst Originalwert."""
        return self.corrected_value or self.normalized_value or self.original_value
