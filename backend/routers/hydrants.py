from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from services.data_loader import data_loader

ALLOWED_STATUSES = {"working", "maintenance", "out_of_service"}

router = APIRouter(prefix="/hydrants", tags=["hydrants"])


class HydrantUpdate(BaseModel):
    status: Optional[str] = None
    last_checked: Optional[str] = None
    winter_accessible: Optional[bool] = None
    pressure_bar: Optional[float] = None
    notes: Optional[str] = None


@router.get("")
def list_hydrants(
    city: str = Query(...),
    status: Optional[str] = Query(None),
) -> list[dict]:
    if status is not None and status not in ALLOWED_STATUSES:
        return []
    return data_loader.get_hydrants(city, status=status)


@router.patch("/{hydrant_id}")
def update_hydrant(
    hydrant_id: str,
    body: HydrantUpdate,
    city: str = Query(...),
) -> dict:
    if body.status is not None and body.status not in ALLOWED_STATUSES:
        raise HTTPException(status_code=400, detail=f"Недопустимый статус: {body.status}")
    updated = data_loader.update_hydrant(city, hydrant_id, body.model_dump(exclude_none=False))
    if not updated:
        raise HTTPException(status_code=404, detail="Гидрант не найден")
    return updated
