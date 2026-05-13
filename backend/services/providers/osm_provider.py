import httpx
import logging
from typing import List, Optional

from services.providers.base import BuildingsProvider, BuildingDTO, BBox

logger = logging.getLogger(__name__)

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# Map OSM building tags to our categories
BUILDING_TYPE_MAP = {
    "residential": "residential",
    "apartments": "residential",
    "house": "residential",
    "detached": "residential",
    "commercial": "commercial",
    "retail": "commercial",
    "shop": "commercial",
    "supermarket": "commercial",
    "mall": "commercial",
    "industrial": "industrial",
    "warehouse": "industrial",
    "factory": "industrial",
    "school": "educational",
    "university": "educational",
    "college": "educational",
    "kindergarten": "educational",
    "hospital": "medical",
    "clinic": "medical",
    "doctors": "medical",
    "yes": None,  # generic — leave as None
}


def _normalize_address(address: str) -> str:
    return address.lower().strip()


def _osm_way_to_dto(element: dict, city_id: str) -> Optional[BuildingDTO]:
    """Convert Overpass API 'way' element to BuildingDTO."""
    tags = element.get("tags", {})
    geometry = element.get("geometry", [])

    if not geometry:
        return None

    # Build WKT polygon from node coordinates
    coords = [(node["lon"], node["lat"]) for node in geometry if "lat" in node and "lon" in node]
    if len(coords) < 4:
        return None

    coord_str = ", ".join(f"{lon} {lat}" for lon, lat in coords)
    geom_wkt = f"POLYGON(({coord_str}))"

    # Centroid: simple average (good enough for bbox-scale buildings)
    avg_lat = sum(c[1] for c in coords) / len(coords)
    avg_lon = sum(c[0] for c in coords) / len(coords)
    centroid_wkt = f"POINT({avg_lon} {avg_lat})"

    # Address
    addr_parts = []
    if tags.get("addr:street"):
        addr_parts.append(tags["addr:street"])
    if tags.get("addr:housenumber"):
        addr_parts.append(tags["addr:housenumber"])
    if tags.get("name"):
        addr_parts.insert(0, tags["name"])
    address = ", ".join(addr_parts) if addr_parts else f"OSM way {element['id']}"

    # Building type
    osm_building = tags.get("building", "yes")
    building_type = BUILDING_TYPE_MAP.get(osm_building)

    # Floors
    floors_above = None
    if tags.get("building:levels"):
        try:
            floors_above = int(tags["building:levels"])
        except (ValueError, TypeError):
            pass

    # Height
    height_m = None
    if tags.get("height"):
        try:
            height_m = float(tags["height"].replace("m", "").strip())
        except (ValueError, TypeError):
            pass

    # Year built
    year_built = None
    if tags.get("start_date"):
        try:
            year_built = int(tags["start_date"][:4])
        except (ValueError, TypeError):
            pass

    return BuildingDTO(
        external_id=str(element["id"]),
        source="osm",
        address=address,
        address_norm=_normalize_address(address),
        city_id=city_id,
        lat=avg_lat,
        lon=avg_lon,
        geom_wkt=geom_wkt,
        centroid_wkt=centroid_wkt,
        building_type=building_type,
        floors_above=floors_above,
        floors_below=None,
        height_m=height_m,
        total_area_sqm=None,
        year_built=year_built,
        wall_material=tags.get("building:material"),
        fire_resistance=None,
        fire_hazard_class=None,
    )


class OSMProvider(BuildingsProvider):
    def source_name(self) -> str:
        return "osm"

    async def fetch_buildings(self, city_id: str, bbox: BBox) -> List[BuildingDTO]:
        query = f"""
[out:json][timeout:60];
(
  way["building"]({bbox.to_overpass()});
);
out geom;
"""
        logger.info(f"OSM fetch for {city_id} bbox={bbox}")
        async with httpx.AsyncClient(timeout=90.0) as client:
            resp = await client.post(OVERPASS_URL, data={"data": query})
            resp.raise_for_status()
            data = resp.json()

        elements = data.get("elements", [])
        logger.info(f"OSM returned {len(elements)} elements")

        results = []
        for el in elements:
            if el.get("type") != "way":
                continue
            dto = _osm_way_to_dto(el, city_id)
            if dto:
                results.append(dto)

        logger.info(f"Parsed {len(results)} buildings from OSM")
        return results
