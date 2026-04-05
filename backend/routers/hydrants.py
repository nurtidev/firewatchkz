from typing import Optional

from fastapi import APIRouter
from fastapi import Query

from services.data_loader import data_loader

ALLOWED_STATUSES = {"working", "maintenance", "out_of_service"}

router = APIRouter(prefix="/hydrants", tags=["hydrants"])


@router.get("")
def list_hydrants(
    city: str = Query(...),
    status: Optional[str] = Query(None),
) -> list[dict]:
    if status is not None and status not in ALLOWED_STATUSES:
        return []
    return data_loader.get_hydrants(city, status=status)
