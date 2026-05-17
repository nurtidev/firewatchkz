from __future__ import annotations

from typing import List, Literal, Optional, Union

from pydantic import BaseModel, Field


class FieldWithConfidence(BaseModel):
    """A single extracted field with an AI confidence score."""

    value: Optional[Union[str, int, float, bool]] = None
    confidence: float = Field(..., ge=0.0, le=1.0)
    source_page: Optional[int] = None  # page number where found


class FireSafetySystem(BaseModel):
    alarm_type: Optional[str] = None  # automatic/manual/combined/none
    sprinkler_present: Optional[bool] = None
    sprinkler_coverage_pct: Optional[float] = None
    smoke_extraction: Optional[bool] = None
    evacuation_exits: Optional[int] = None
    emergency_lighting: Optional[bool] = None


class Hydrant(BaseModel):
    distance_m: Optional[float] = None
    address: Optional[str] = None
    type: Optional[str] = None  # underground/pillar


class Vulnerability(BaseModel):
    severity: Literal["critical", "high", "medium", "low"]
    description: str
    regulation_violated: Optional[str] = None
    recommended_action: str


class OperationalCardExtraction(BaseModel):
    # Card metadata
    card_number: FieldWithConfidence
    approved_date: FieldWithConfidence  # ISO date string or None
    revision_date: FieldWithConfidence

    # Building identity
    building_name: FieldWithConfidence
    address: FieldWithConfidence
    city: FieldWithConfidence
    hazard_class: FieldWithConfidence  # Ф1-Ф5

    # Physical characteristics
    floors_above: FieldWithConfidence
    floors_below: FieldWithConfidence
    total_area_sqm: FieldWithConfidence
    height_m: FieldWithConfidence
    year_built: FieldWithConfidence
    wall_material: FieldWithConfidence  # brick/concrete/panel/wood/other
    fire_resistance_degree: FieldWithConfidence  # I-V (1-5)

    # Fire safety systems
    fire_safety: FireSafetySystem
    fire_safety_confidence: float = Field(..., ge=0.0, le=1.0)

    # Hydrants
    hydrants: List[Hydrant]

    # Occupancy / special risks
    max_occupancy: FieldWithConfidence
    has_gas_systems: FieldWithConfidence
    has_hazardous_materials: FieldWithConfidence
    hazardous_materials_description: FieldWithConfidence

    # Overall extraction quality
    overall_confidence: float = Field(..., ge=0.0, le=1.0)
    missing_fields: List[str]  # list of field names not found
    extraction_notes: Optional[str] = None  # anything the model wants to flag


class ExtractionResult(BaseModel):
    extraction: OperationalCardExtraction
    input_tokens: int
    output_tokens: int
    cost_usd: float
    pages_processed: int
