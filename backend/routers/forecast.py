from fastapi import APIRouter, HTTPException
from fastapi import Query
from services.data_loader import data_loader
from services.forecaster import forecaster

router = APIRouter(prefix="/forecast", tags=["forecast"])


@router.get("")
def get_forecast(
    city: str = Query(...),
    months: int = Query(6),
) -> dict:
    if months not in (3, 6, 12):
        raise HTTPException(status_code=422, detail="months must be 3, 6, or 12")
    monthly_counts = data_loader.get_monthly_counts(city)
    return forecaster.generate_forecast(city=city, monthly_counts=monthly_counts, months=months)
