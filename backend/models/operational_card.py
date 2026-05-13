from sqlalchemy import Column, String, Text, BigInteger, Integer, TIMESTAMP, ForeignKey
from sqlalchemy.sql import func
from db.base import Base

class OperationalCard(Base):
    __tablename__ = "operational_cards"

    id = Column(String, primary_key=True)
    building_id = Column(String, ForeignKey('buildings.id', ondelete='SET NULL'), nullable=True)
    uploaded_by = Column(String, ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    uploaded_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    file_url = Column(Text, nullable=False)
    file_name = Column(Text, nullable=False)
    file_size_bytes = Column(BigInteger, nullable=True)
    file_mime = Column(String, nullable=True)
    status = Column(String, nullable=False, server_default='uploaded')
    extraction_id = Column(String, ForeignKey('card_extractions.id', ondelete='SET NULL'), nullable=True)
    approved_at = Column(TIMESTAMP(timezone=True), nullable=True)
    approved_by = Column(String, ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    converted_key = Column(Text, nullable=True)
    thumbnail_key = Column(Text, nullable=True)
