from sqlalchemy import Column, String, TIMESTAMP
from sqlalchemy.sql import func
from db.base import Base

class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True)
    email = Column(String, unique=True, nullable=False)
    full_name = Column(String, nullable=True)
    role = Column(String, nullable=False)  # admin/analyst/inspector/viewer
    password_hash = Column(String, nullable=True)
    organization_id = Column(String, nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    last_login_at = Column(TIMESTAMP(timezone=True), nullable=True)
