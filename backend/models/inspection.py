from sqlalchemy import Column, String, Integer, Text, TIMESTAMP, ForeignKey
from sqlalchemy.sql import func
from db.base import Base

class Inspection(Base):
    __tablename__ = "inspections"

    id = Column(String, primary_key=True)
    building_id = Column(String, ForeignKey('buildings.id', ondelete='CASCADE'), nullable=False)
    inspector_id = Column(String, ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    inspected_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    violations_count = Column(Integer, server_default='0', nullable=False)
    outcome = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
