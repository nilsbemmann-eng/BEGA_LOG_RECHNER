from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.errors import NotFoundError
from app.models.audit_log import AuditLogEntry
from app.models.document import ExtractedField
from app.models.user import User
from app.schemas import ExtractedFieldCorrection, ExtractedFieldOut

router = APIRouter(prefix="/api/extracted-fields", tags=["extracted-fields"], dependencies=[Depends(get_current_user)])


@router.patch("/{field_id}", response_model=ExtractedFieldOut)
def correct_extracted_field(
    field_id: str,
    correction: ExtractedFieldCorrection,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ExtractedField:
    """Abschnitt 12.2/16.6: Originalwert bleibt erhalten, nur `corrected_value`
    wird gesetzt; die Korrektur wird mit Benutzer und Zeitpunkt protokolliert."""
    field = db.get(ExtractedField, field_id)
    if field is None:
        raise NotFoundError(f"Extrahiertes Feld {field_id} nicht gefunden", entity_type="ExtractedField", entity_id=field_id)

    old_value = field.corrected_value
    field.corrected_value = correction.corrected_value
    db.add(
        AuditLogEntry(
            user_id=current_user.id,
            entity_type="ExtractedField",
            entity_id=field.id,
            action="correct_value",
            old_value_json={"corrected_value": old_value, "original_value": field.original_value},
            new_value_json={"corrected_value": correction.corrected_value},
        )
    )
    db.commit()
    db.refresh(field)
    return field
