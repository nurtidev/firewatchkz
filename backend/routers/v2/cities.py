"""
routers/v2/cities.py — Cities endpoints (API v2).

GET /api/v2/cities         → list all cities (public)
GET /api/v2/cities/{city_id} → single city config (public)
"""
from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException

from services.data_loader_v2 import DataLoaderV2

router = APIRouter()


@router.get("/cities", tags=["cities-v2"])
async def list_cities() -> List[Dict[str, Any]]:
    """Return list of all available cities. No auth required."""
    loader = DataLoaderV2()
    return await loader.get_cities()


@router.get("/cities/{city_id}", tags=["cities-v2"])
async def get_city(city_id: str) -> Dict[str, Any]:
    """Return config for a single city. No auth required."""
    loader = DataLoaderV2()
    cities = await loader.get_cities()
    for city in cities:
        if city["id"].lower() == city_id.lower():
            return city
    raise HTTPException(status_code=404, detail="Город не найден")
