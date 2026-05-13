from sqlalchemy import Column, String, Text, Numeric, Integer, JSON, TIMESTAMP, ForeignKey
from sqlalchemy.sql import func
from db.base import Base

class CardExtraction(Base):
    __tablename__ = "card_extractions"

    id = Column(String, primary_key=True)
    card_id = Column(String, ForeignKey('operational_cards.id', ondelete='CASCADE'), nullable=False)
    model_version = Column(String, nullable=False)
    extracted_data = Column(JSON, nullable=False)
    field_confidences = Column(JSON, nullable=False)
    vulnerabilities = Column(JSON, nullable=True)
    raw_text = Column(Text, nullable=True)
    extraction_cost_usd = Column(Numeric, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
