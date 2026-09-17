from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.errors import NotFoundError
from app.models.tour import Tour
from app.schemas import TourOut

router = APIRouter(prefix="/api/tours", tags=["tours"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[TourOut])
def list_tours(db: Session = Depends(get_db)) -> list[TourOut]:
    tours = db.execute(select(Tour).order_by(Tour.created_at.desc())).scalars().unique().all()
    return [TourOut.from_orm_tour(t) for t in tours]


@router.get("/{tour_id}", response_model=TourOut)
def get_tour(tour_id: str, db: Session = Depends(get_db)) -> TourOut:
    tour = db.get(Tour, tour_id)
    if tour is None:
        raise NotFoundError(f"Tour {tour_id} nicht gefunden", entity_type="Tour", entity_id=tour_id)
    return TourOut.from_orm_tour(tour)
