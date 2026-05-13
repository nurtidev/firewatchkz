from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, List


@dataclass
class BBox:
    min_lat: float
    min_lon: float
    max_lat: float
    max_lon: float

    def to_overpass(self) -> str:
        return f"{self.min_lat},{self.min_lon},{self.max_lat},{self.max_lon}"

    def to_wkt_polygon(self) -> str:
        return (
            f"POLYGON(({self.min_lon} {self.min_lat}, "
            f"{self.max_lon} {self.min_lat}, "
            f"{self.max_lon} {self.max_lat}, "
            f"{self.min_lon} {self.max_lat}, "
            f"{self.min_lon} {self.min_lat}))"
        )


@dataclass
class BuildingDTO:
    external_id: str
    source: str           # 'osm' | '2gis' | 'manual'
    address: str
    address_norm: str     # lowercased, stripped for dedup
    city_id: str          # 'astana'
    lat: Optional[float]
    lon: Optional[float]
    geom_wkt: Optional[str]       # WKT POLYGON or None
    centroid_wkt: Optional[str]   # WKT POINT or None
    building_type: Optional[str]  # residential/commercial/industrial/social/educational/medical
    floors_above: Optional[int]
    floors_below: Optional[int]
    height_m: Optional[float]
    total_area_sqm: Optional[float]
    year_built: Optional[int]
    wall_material: Optional[str]
    fire_resistance: Optional[int]
    fire_hazard_class: Optional[str]


class BuildingsProvider(ABC):
    @abstractmethod
    async def fetch_buildings(self, city_id: str, bbox: BBox) -> List[BuildingDTO]:
        """Fetch buildings within bbox for a given city. Returns list of BuildingDTOs."""

    @abstractmethod
    def source_name(self) -> str:
        """Return source identifier: 'osm' or '2gis'"""


def get_provider(name: Optional[str] = None) -> BuildingsProvider:
    """
    Factory. Reads BUILDINGS_PROVIDER env var ('osm' by default).
    Swap to '2gis' by setting env var when 2GIS key is available.
    """
    import os
    provider_name = name or os.getenv("BUILDINGS_PROVIDER", "osm")
    if provider_name == "osm":
        from services.providers.osm_provider import OSMProvider
        return OSMProvider()
    elif provider_name == "2gis":
        from services.providers.twogis_provider import TwoGISProvider
        return TwoGISProvider()
    else:
        raise ValueError(f"Unknown buildings provider: {provider_name}")
