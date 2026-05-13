from sqlalchemy import Column, String, Numeric, Text, TIMESTAMP, ForeignKey
from db.base import Base

class Operation(Base):
    __tablename__ = "operations"

    id = Column(String, primary_key=True)
    date = Column(TIMESTAMP(timezone=True), nullable=True)
    city = Column(String, nullable=True)
    district = Column(String, nullable=True)
    station_id = Column(String, ForeignKey('fire_stations.id', ondelete='SET NULL'), nullable=True)
    incident_id = Column(String, ForeignKey('incidents.id', ondelete='SET NULL'), nullable=True)
    response_time_min = Column(Numeric, nullable=True)
    outcome = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
