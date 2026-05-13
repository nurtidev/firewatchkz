from sqlalchemy import Column, String, Integer
from geoalchemy2 import Geometry
from db.base import Base
import uuid


class City(Base):
    __tablename__ = "cities"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    code = Column(String, unique=True, nullable=False)
    name = Column(String, nullable=False)
    center = Column(Geometry('POINT', srid=4326), nullable=True)
    zoom = Column(Integer, default=12)
