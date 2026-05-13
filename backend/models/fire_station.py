from sqlalchemy import Column, String, Integer, Numeric, Text
from geoalchemy2 import Geometry
from db.base import Base

class FireStation(Base):
    __tablename__ = "fire_stations"

    id = Column(String, primary_key=True)
    city = Column(String, nullable=True)
    name = Column(String, nullable=False)
    district = Column(String, nullable=True)
    geom = Column(Geometry('POINT', srid=4326), nullable=True)
    address = Column(Text, nullable=True)
    units = Column(Integer, nullable=True)
    staff_count = Column(Integer, nullable=True)
    lat = Column(Numeric, nullable=True)
    lon = Column(Numeric, nullable=True)
