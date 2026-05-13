from sqlalchemy import Column, String, Numeric, Boolean, TIMESTAMP, ForeignKey
from geoalchemy2 import Geometry
from db.base import Base

class Hydrant(Base):
    __tablename__ = "hydrants"

    id = Column(String, primary_key=True)
    city = Column(String, nullable=True)
    district = Column(String, nullable=True)
    geom = Column(Geometry('POINT', srid=4326), nullable=True)
    address = Column(String, nullable=True)
    status = Column(String, nullable=False, server_default='working')
    capacity_l_s = Column(Numeric, nullable=True)
    last_check_at = Column(TIMESTAMP(timezone=True), nullable=True)
    winter_access = Column(Boolean, server_default='true', nullable=False)
    lat = Column(Numeric, nullable=True)
    lon = Column(Numeric, nullable=True)
    external_id = Column(String, nullable=True)
