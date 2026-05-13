from typing import List
from services.providers.base import BuildingsProvider, BuildingDTO, BBox


class TwoGISProvider(BuildingsProvider):
    def source_name(self) -> str:
        return "2gis"

    async def fetch_buildings(self, city_id: str, bbox: BBox) -> List[BuildingDTO]:
        raise NotImplementedError(
            "2GIS provider not implemented yet. "
            "Set BUILDINGS_PROVIDER=osm or implement TwoGISProvider "
            "once a commercial API key is available."
        )
