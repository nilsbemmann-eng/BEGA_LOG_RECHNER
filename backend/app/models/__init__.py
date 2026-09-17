"""Alle Modelle werden hier importiert, damit `Base.metadata` (Alembic
Autogenerate, `create_all` in Tests) sie zuverlaessig findet."""
from app.models.address import Address
from app.models.attachment import Attachment
from app.models.audit import AuditResult, AuditRuleResult, AuditStatus, RuleStatus
from app.models.audit_log import AuditLogEntry
from app.models.base import Base
from app.models.document import Document, DocumentPage, DocumentType, ExtractedField, OcrStatus
from app.models.email import Email, EmailProcessingStatus
from app.models.import_job import ImportJob, ImportJobStatus, ImportSourceType
from app.models.mailbox import Mailbox
from app.models.party import Carrier, Customer
from app.models.routing import RoutingResult
from app.models.shipment import Shipment
from app.models.surcharge import SurchargeClaim, SurchargeStatus, SurchargeType
from app.models.tariff import Tariff, TariffRule, TariffRuleType, TariffStatus
from app.models.tour import Tour
from app.models.tour_origin_mapping import TourOriginMapping
from app.models.user import User, UserRole

__all__ = [
    "Base",
    "Address",
    "Attachment",
    "AuditLogEntry",
    "AuditResult",
    "AuditRuleResult",
    "AuditStatus",
    "RuleStatus",
    "Carrier",
    "Customer",
    "Document",
    "DocumentPage",
    "DocumentType",
    "ExtractedField",
    "OcrStatus",
    "Email",
    "EmailProcessingStatus",
    "ImportJob",
    "ImportJobStatus",
    "ImportSourceType",
    "Mailbox",
    "RoutingResult",
    "Shipment",
    "SurchargeClaim",
    "SurchargeStatus",
    "SurchargeType",
    "Tariff",
    "TariffRule",
    "TariffRuleType",
    "TariffStatus",
    "Tour",
    "User",
    "UserRole",
]
