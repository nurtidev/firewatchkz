from sqlalchemy import Column, String, Text, JSON, TIMESTAMP, ForeignKey
from sqlalchemy.sql import func
from db.base import Base

class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    action = Column(Text, nullable=False)
    entity_type = Column(String, nullable=False)
    entity_id = Column(String, nullable=True)
    changes = Column(JSON, nullable=True)
    ip_address = Column(String, nullable=True)
    occurred_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
