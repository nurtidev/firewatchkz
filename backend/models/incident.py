from sqlalchemy import Column, String, Integer, Numeric, Text, Boolean, TIMESTAMP, ForeignKey
from sqlalchemy.sql import func
from geoalchemy2 import Geometry
from db.base import Base

class Incident(Base):
    __tablename__ = "incidents"

    id = Column(String, primary_key=True)
    occurred_at = Column(TIMESTAMP(timezone=True), nullable=False)
    geom = Column(Geometry('POINT', srid=4326), nullable=True)
    address_text = Column(Text, nullable=True)
    district = Column(String, nullable=True)
    building_id = Column(String, ForeignKey('buildings.id', ondelete='SET NULL'), nullable=True)
    incident_type = Column(String, nullable=True)
    building_type = Column(String, nullable=True)
    cause = Column(String, nullable=True)
    severity = Column(String, nullable=True)
    damage_tenge = Column(Numeric, nullable=True)
    casualties = Column(Integer, server_default='0', nullable=False)
    source = Column(String, nullable=False, server_default='csv')
    external_id = Column(String, nullable=True)
    lat = Column(Numeric, nullable=True)
    lon = Column(Numeric, nullable=True)
