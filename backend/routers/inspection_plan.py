from fastapi import APIRouter
from fastapi import Query

from services.inspection_planner import inspection_planner

router = APIRouter(prefix="/inspection-plan", tags=["inspection-plan"])


@router.get("")
def get_inspection_plan(city: str = Query(...)) -> dict:
    return inspection_planner.generate_plan(city)
