from pydantic import BaseModel, Field
from typing import Optional, Union, List, Literal


class FieldWithConfidence(BaseModel):
    value: Optional[Union[str, int, float, bool]] = None
    confidence: float = Field(..., ge=0.0, le=1.0)


class WaterSource(BaseModel):
    type: Literal["hydrant", "reservoir", "natural", "pond", "river"]
    distance_m: Optional[int] = None
    capacity_l_s: Optional[float] = None
    status: Optional[Literal["working", "broken", "seasonal", "unknown"]] = None
    notes: Optional[str] = None


class Vulnerability(BaseModel):
    severity: Literal["critical", "high", "medium", "low"]
    description: str
    regulation_violated: Optional[str] = None
    recommended_action: str


class OperationalCardExtraction(BaseModel):
    # Document metadata
    card_number: FieldWithConfidence
    approved_date: FieldWithConfidence
    last_revision_date: FieldWithConfidence

    # Object
    object_name: FieldWithConfidence
    address: FieldWithConfidence
    coordinates_lat: FieldWithConfidence
    coordinates_lng: FieldWithConfidence
    object_category: FieldWithConfidence
    owner: FieldWithConfidence
    responsible_name: FieldWithConfidence
    responsible_phone: FieldWithConfidence

    # Building
    floors_above: FieldWithConfidence
    floors_below: FieldWithConfidence
    height_m: FieldWithConfidence
    total_area_sqm: FieldWithConfidence
    year_built: FieldWithConfidence
    walls_material: FieldWithConfidence
    roof_material: FieldWithConfidence
    fire_resistance_degree: FieldWithConfidence
    functional_class: FieldWithConfidence
    structural_class: FieldWithConfidence

    # Occupancy
    max_people_day: FieldWithConfidence
    max_people_night: FieldWithConfidence
    vulnerable_groups: List[str] = []

    # Fire safety systems
    alarm_system_present: FieldWithConfidence
    alarm_system_type: FieldWithConfidence
    automatic_extinguishing: FieldWithConfidence
    fire_exits_count: FieldWithConfidence
    smoke_removal: FieldWithConfidence

    # Water supply
    internal_hydrants_count: FieldWithConfidence
    water_sources: List[WaterSource] = []

    # Hazards
    hazardous_materials: List[str] = []
    gas_systems: List[str] = []
    structural_concerns: List[str] = []

    # Access
    approach_roads: List[str] = []
    firefighting_clearance: FieldWithConfidence
    access_obstacles: List[str] = []

    # AI analysis (filled in second Claude pass)
    identified_vulnerabilities: List[Vulnerability] = []

    # Meta
    document_quality_notes: Optional[str] = None
    overall_confidence: float = Field(0.0, ge=0.0, le=1.0)
