"""Import von Ladelisten-PDFs zu Touren (BEGA-Finetuning, Abschnitt 4.5-Erweiterung).

Eine Frachtrechnung bezieht sich auf die gesamte Tour (siehe
`app/models/tour.py`), daher legt dieser Import eine `Tour` mit einer
`Shipment`-Zeile je Auftrag der Ladeliste an - die Preispruefung erfolgt
anschliessend auf Tour-Ebene (`app/services/audit_service.py::run_tour_audit`).

Fuer Speicherung/Duplikaterkennung des Original-PDFs wird dieselbe
Persistenzlogik wie beim .msg-Upload wiederverwendet
(`app/services/email_service.py::persist_message`): das PDF wird als
einzelner Anhang einer synthetischen Nachricht in der
"Manueller Upload"-Pseudo-Mailbox abgelegt. Das spart eine eigene
Speicher-/Duplikaterkennung und macht das Original-PDF ueber
`Tour.source_document_id` nachvollziehbar.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.address import Address
from app.models.document import DocumentType
from app.models.import_job import ImportJob, ImportJobStatus, ImportSourceType
from app.models.party import Carrier
from app.models.shipment import Shipment
from app.models.tour import Tour
from app.providers.base import EmailAttachmentData, EmailMessage
from app.services.email_service import get_or_create_manual_upload_mailbox, persist_message
from app.services.ladeliste_pdf_parser import LadelistePdfParsingError, parse_ladeliste_pdf
from app.storage import StorageBackend, sha256_hex


def _fail(db: Session, job: ImportJob, message: str, records_failed: int) -> ImportJob:
    job.completed_at = datetime.now(timezone.utc)
    job.status = ImportJobStatus.FAILED
    job.records_failed = records_failed
    job.error_report_reference = message
    db.flush()
    return job


def _write_warnings_report(report_storage_path: str, job_id: str, warnings: list[str]) -> str:
    os.makedirs(report_storage_path, exist_ok=True)
    report_path = os.path.join(report_storage_path, f"{job_id}.json")
    with open(report_path, "w", encoding="utf-8") as handle:
        json.dump([{"warning": warning} for warning in warnings], handle, ensure_ascii=False, indent=2)
    return report_path


def import_ladeliste_pdf(
    db: Session,
    file_bytes: bytes,
    filename: str,
    storage: StorageBackend,
    report_storage_path: str,
) -> ImportJob:
    job = ImportJob(
        source_type=ImportSourceType.LADELISTE_UPLOAD,
        started_at=datetime.now(timezone.utc),
        status=ImportJobStatus.RUNNING,
        records_total=0,
    )
    db.add(job)
    db.flush()

    try:
        parsed = parse_ladeliste_pdf(file_bytes)
    except LadelistePdfParsingError as exc:
        return _fail(db, job, f"Ladeliste-PDF konnte nicht gelesen werden: {exc}", records_failed=1)

    job.records_total = len(parsed.orders)

    existing_tour = db.execute(select(Tour).where(Tour.tour_number == parsed.tour_number)).scalar_one_or_none()
    if existing_tour is not None:
        return _fail(
            db,
            job,
            f"Tour {parsed.tour_number} wurde bereits importiert (Tour-ID {existing_tour.id}).",
            records_failed=len(parsed.orders),
        )

    mailbox = get_or_create_manual_upload_mailbox(db)
    message = EmailMessage(
        external_message_id=f"ladeliste-pdf:{sha256_hex(file_bytes)}",
        sender="ladeliste-upload",
        recipients=[],
        cc_recipients=[],
        subject=f"Ladeliste {parsed.tour_number}",
        received_at=datetime.now(timezone.utc),
        body_text="",
        body_html=None,
        attachments=[EmailAttachmentData(filename=filename, mime_type="application/pdf", content=file_bytes)],
    )
    email, is_duplicate = persist_message(db, mailbox, message, storage)
    if is_duplicate or email is None:
        return _fail(
            db,
            job,
            "Diese Ladeliste-PDF-Datei wurde bereits hochgeladen (identischer Dateiinhalt).",
            records_failed=len(parsed.orders),
        )

    source_document = email.attachments[0].document
    source_document.document_type = DocumentType.LADELISTE

    warnings: list[str] = list(parsed.warnings)
    carrier: Carrier | None = None
    if parsed.carrier_name:
        carrier = db.execute(
            select(Carrier).where(func.lower(Carrier.name) == parsed.carrier_name.strip().lower())
        ).scalars().first()
        if carrier is None:
            warnings.append(
                f"Spediteur '{parsed.carrier_name}' ist nicht in den Frachtfuehrer-Stammdaten angelegt - "
                "Tour wurde ohne Carrier-Zuordnung importiert. Die Preispruefung schlaegt fehl, bis der "
                "Frachtfuehrer angelegt und ein Tarif hinterlegt ist."
            )

    tour = Tour(
        tour_number=parsed.tour_number,
        version=parsed.version,
        carrier_id=carrier.id if carrier else None,
        tour_date=parsed.tour_date,
        loading_date=parsed.loading_date,
        source_document_id=source_document.id,
    )
    db.add(tour)
    db.flush()

    for order in parsed.orders:
        destination_address = None
        if order.address is not None:
            destination_address = Address(
                original_text=order.address.original_text,
                street=order.address.street,
                postal_code=order.address.postal_code,
                city=order.address.city,
                country_code=order.address.country_code,
            )
        db.add(
            Shipment(
                shipment_number=order.order_number,
                tour_id=tour.id,
                carrier_id=carrier.id if carrier else None,
                transport_date=parsed.loading_date,
                destination_address=destination_address,
                weight_kg=order.weight_kg,
                volume_m3=order.volume_m3,
                packages=order.quantity_total,
            )
        )

    job.completed_at = datetime.now(timezone.utc)
    job.records_successful = len(parsed.orders)
    job.status = ImportJobStatus.COMPLETED if not warnings else ImportJobStatus.COMPLETED_WITH_ERRORS
    if warnings:
        job.error_report_reference = _write_warnings_report(report_storage_path, job.id, warnings)

    db.flush()
    return job
