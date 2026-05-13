from sqlalchemy import Column, String, Integer, Numeric, Text, TIMESTAMP, ForeignKey, UniqueConstraint
from sqlalchemy.sql import func
from geoalchemy2 import Geometry
from db.base import Base

class Building(Base):
    __tablename__ = "buildings"
    __table_args__ = (
        UniqueConstraint('source', 'external_id', name='uq_buildings_source_external_id'),
    )

    id = Column(String, primary_key=True)
    city_id = Column(String, ForeignKey('cities.id'), nullable=False)
    address = Column(Text, nullable=False)
    address_norm = Column(Text, nullable=False)
    geom = Column(Geometry('POLYGON', srid=4326), nullable=True)
    centroid = Column(Geometry('POINT', srid=4326), nullable=True)
    building_type = Column(String, nullable=True)
    floors_above = Column(Integer, nullable=True)
    floors_below = Column(Integer, nullable=True)
    height_m = Column(Numeric, nullable=True)
    total_area_sqm = Column(Numeric, nullable=True)
    year_built = Column(Integer, nullable=True)
    wall_material = Column(String, nullable=True)
    fire_resistance = Column(Integer, nullable=True)
    fire_hazard_class = Column(String, nullable=True)
    source = Column(String, nullable=False)
    external_id = Column(String, nullable=True)
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
